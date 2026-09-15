from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app.agents.domains import canonical_domain
from app.agents.llm_client import llm_complete
from app.schemas.contracts import InternalVar, PerformanceTargets, PlanObject, PlanScope, PlanSignal

PlanningMode = Literal["rule_based", "llm"]

logger = logging.getLogger(__name__)

PLANNING_SYSTEM_PROMPT = """You are an expert IEC 61131-3 PLC planning agent.
Extract a precise structured plan from the engineer's requirement.

OUTPUT FORMAT: Return ONLY valid JSON — no prose, no markdown fences.
Schema:
{
  "projectId": "<will be set programmatically>",
  "agent": "PlanningAgent/llm.v1",
  "generatedAt": "<ISO timestamp>",
  "inputs": [
    {"name": str, "type": "BOOL|INT|REAL|TIME",
     "source": str, "address": null, "description": str}
  ],
  "outputs": [
    {"name": str, "type": "BOOL|INT|REAL|TIME",
     "address": null, "description": str}
  ],
  "internalVars": [
    {"name": str, "type": "BOOL|INT", "description": str}
  ],
  "controlLogic": [str],
  "safetyConstraints": [str],
  "performanceTargets": {},
  "scope": {
    "standard": "IEC 61131-3",
    "edition": "3rd ed. (2013)",
    "language": "Structured Text",
    "runtime": "CODESYS / TwinCAT compatible"
  },
  "domain": str,
  "complexityTier": "simple|medium|complex"
}

RULES — violations produce unusable output:
1. Variable names: PascalCase, valid IEC identifiers, max 32 chars, no spaces
2. controlLogic: imperative English, present tense, max 20 words each, min 3 rules
3. safetyConstraints: copy EXACTLY from user input — never paraphrase
4. Infer internalVars needed for latching, state tracking, timers, fault flags
   internalVars: internal state variables needed for step tracking, fault latching, timers.
   These are NOT physical I/O. Examples: Step_State (INT), Fault_State (BOOL), Run_Latch (BOOL)
5. If no safety constraints stated by user: return empty list []
6. complexityTier: simple=≤5 rules, medium=6-9, complex=≥10 or state machines
7. All outputs must be FALSE when any emergency/abort input is active"""


@dataclass(frozen=True)
class PlanningTemplate:
    inputs: list[PlanSignal]
    outputs: list[PlanSignal]
    logic_rules: list[str]
    safety_constraints: list[str]


class PlanningAgent:
    def __init__(self, mode: PlanningMode = "rule_based") -> None:
        self.mode = mode

    async def generate_plan(
        self,
        *,
        project_id: str,
        requirement_text: str,
        safety_constraints: list[str] | None = None,
        performance_targets: PerformanceTargets | dict[str, int | float] | None = None,
        confirmed_outputs: list[str] | None = None,
        domain: str = "",
        complexity_tier: str = "medium",
    ) -> PlanObject:
        if self.mode == "llm":
            return await self._generate_with_llm(
                project_id=project_id,
                requirement_text=requirement_text,
                safety_constraints=safety_constraints,
                performance_targets=performance_targets,
                confirmed_outputs=confirmed_outputs,
                domain=domain,
                complexity_tier=complexity_tier,
            )
        if self.mode != "rule_based":
            raise ValueError(f"Unsupported PlanningAgent mode: {self.mode}")
        return self._generate_rule_based(
            project_id=project_id,
            requirement_text=requirement_text,
            safety_constraints=safety_constraints,
            performance_targets=performance_targets,
            confirmed_outputs=confirmed_outputs,
            domain=domain,
            complexity_tier=complexity_tier,
        )

    async def _generate_with_llm(
        self,
        *,
        project_id: str,
        requirement_text: str,
        safety_constraints: list[str] | None,
        performance_targets: PerformanceTargets | dict[str, int | float] | None,
        confirmed_outputs: list[str] | None,
        domain: str,
        complexity_tier: str,
    ) -> PlanObject:
        if not requirement_text.strip():
            raise ValueError("Requirement text must not be empty.")

        normalized_constraints = [item for item in (safety_constraints or []) if item.strip()]
        normalized_targets = self._normalize_performance_targets(performance_targets, complexity_tier)
        safety_list_or_none = normalized_constraints if normalized_constraints else "None"
        confirmed_outputs_or_none = confirmed_outputs if confirmed_outputs else "None"
        domain_hint = domain or "Generic"
        plan_rag_context = ""
        try:
            from app.services.rag_service import get_rag_service

            rag = get_rag_service()
            patterns = rag.retrieve(
                query=f"{domain_hint} {requirement_text[:200]}",
                domain=domain_hint,
                n_results=2,
            )
            if patterns:
                plan_rag_context = "\n\nRELEVANT DOMAIN PATTERNS:\n"
                for pattern in patterns:
                    plan_rag_context += (
                        f"- {pattern['name']}: {pattern['safetyNotes']}\n"
                        f"  Common mistakes: {'; '.join(pattern['commonMistakes'][:2])}\n"
                    )
        except Exception:
            plan_rag_context = ""

        user_message = (
            f"REQUIREMENT:\n{requirement_text}\n\n"
            f"SAFETY CONSTRAINTS STATED BY USER:\n{safety_list_or_none}\n\n"
            f"DOMAIN HINT: {domain}\n"
            f"COMPLEXITY HINT: {complexity_tier}\n"
            f"CONFIRMED OUTPUTS: {confirmed_outputs_or_none}"
            f"{plan_rag_context}"
        )
        messages: list[dict[str, str]] = [{"role": "user", "content": user_message}]

        llm_response = await llm_complete(
            system=PLANNING_SYSTEM_PROMPT,
            messages=messages,
            temperature=0.1,
            max_tokens=1500,
        )
        tokens_used = getattr(llm_response, "tokens", llm_response.input_tokens + llm_response.output_tokens)
        response_cost = getattr(llm_response, "cost", llm_response.cost_usd)
        logger.info(f"PlanningAgent LLM: {tokens_used} tokens, ${response_cost:.4f}")

        final_llm_response = llm_response
        try:
            parsed_payload = self._parse_llm_json(llm_response.content)
        except json.JSONDecodeError:
            correction_message = (
                "Your previous answer was invalid JSON. "
                "Return ONLY strict JSON that matches the requested schema. "
                "Do not include markdown fences, comments, or prose."
            )
            retry_messages = [
                *messages,
                {"role": "assistant", "content": llm_response.content},
                {"role": "user", "content": correction_message},
            ]
            retry_response = await llm_complete(
                system=PLANNING_SYSTEM_PROMPT,
                messages=retry_messages,
                temperature=0.1,
                max_tokens=1500,
            )
            final_llm_response = retry_response
            retry_tokens = getattr(retry_response, "tokens", retry_response.input_tokens + retry_response.output_tokens)
            retry_cost = getattr(retry_response, "cost", retry_response.cost_usd)
            logger.info(f"PlanningAgent LLM: {retry_tokens} tokens, ${retry_cost:.4f}")
            try:
                parsed_payload = self._parse_llm_json(retry_response.content)
            except json.JSONDecodeError:
                logger.exception("PlanningAgent llm mode JSON parsing failed twice; falling back to rule_based mode.")
                return self._generate_rule_based(
                    project_id=project_id,
                    requirement_text=requirement_text,
                    safety_constraints=safety_constraints,
                    performance_targets=performance_targets,
                    confirmed_outputs=confirmed_outputs,
                    domain=domain,
                    complexity_tier=complexity_tier,
                )

        plan_payload = self._normalize_llm_plan_payload(
            parsed_payload=parsed_payload,
            project_id=project_id,
            domain=domain,
            complexity_tier=complexity_tier,
            normalized_constraints=normalized_constraints,
            normalized_targets=normalized_targets,
            llm_provider=final_llm_response.provider,
            llm_model=final_llm_response.model,
            tokens_used=final_llm_response.input_tokens + final_llm_response.output_tokens,
        )
        return PlanObject(**plan_payload)

    def _generate_rule_based(
        self,
        *,
        project_id: str,
        requirement_text: str,
        safety_constraints: list[str] | None,
        performance_targets: PerformanceTargets | dict[str, int | float] | None,
        confirmed_outputs: list[str] | None,
        domain: str,
        complexity_tier: str,
    ) -> PlanObject:
        if not requirement_text.strip():
            raise ValueError("Requirement text must not be empty.")

        canonical_requirement_text = self._canonicalize_emergency_stop_aliases(requirement_text)
        self._normalize_performance_targets(performance_targets, complexity_tier)
        normalized_constraints = self._normalize_constraints(safety_constraints)
        template = self._template_for(
            domain=domain,
            requirement_text=canonical_requirement_text,
            confirmed_outputs=confirmed_outputs,
            safety_constraints=normalized_constraints,
        )

        return PlanObject(
            projectId=project_id,
            domain=domain,
            agent="PlanningAgent/rule_based.v1",
            generatedAt=self._utc_now(),
            inputs=template.inputs,
            outputs=template.outputs,
            logicRules=template.logic_rules,
            safetyConstraints=normalized_constraints,
            scope=PlanScope(
                standard="IEC 61131-3",
                edition="3rd ed. (2013)",
                language="Structured Text",
                runtime="CODESYS / TwinCAT compatible",
            ),
        )

    @staticmethod
    def _strip_markdown_fences(content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        return stripped

    @classmethod
    def _parse_llm_json(cls, content: str) -> dict:
        sanitized = cls._strip_markdown_fences(content)
        try:
            return json.loads(sanitized)
        except json.JSONDecodeError:
            first_brace = sanitized.find("{")
            last_brace = sanitized.rfind("}")
            if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
                raise
            return json.loads(sanitized[first_brace : last_brace + 1])

    @staticmethod
    def _normalize_llm_plan_payload(
        *,
        parsed_payload: dict,
        project_id: str,
        domain: str,
        complexity_tier: str,
        normalized_constraints: list[str],
        normalized_targets: PerformanceTargets,
        llm_provider: str,
        llm_model: str,
        tokens_used: int,
    ) -> dict:
        _ = complexity_tier
        _ = normalized_targets
        payload = dict(parsed_payload)
        payload["projectId"] = project_id
        payload["generatedAt"] = PlanningAgent._utc_now()
        payload["agent"] = "PlanningAgent/llm.v1"
        payload["domain"] = str(payload.get("domain") or domain or "Generic")
        payload["logicRules"] = payload.get("logicRules") or payload.get("controlLogic") or []
        payload["safetyConstraints"] = normalized_constraints
        payload["internalVars"] = PlanningAgent._normalize_internal_vars(payload.get("internalVars"))
        payload["llmProvider"] = llm_provider
        payload["llmModel"] = llm_model
        payload["tokensUsed"] = tokens_used
        payload["scope"] = payload.get("scope") or {
            "standard": "IEC 61131-3",
            "edition": "3rd ed. (2013)",
            "language": "Structured Text",
            "runtime": "CODESYS / TwinCAT compatible",
        }
        payload.pop("controlLogic", None)
        payload.pop("performanceTargets", None)
        payload.pop("complexityTier", None)
        return payload

    @staticmethod
    def _normalize_internal_vars(value: object) -> list[dict]:
        if not isinstance(value, list):
            return []

        normalized: list[dict] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            var_type = str(item.get("type", "BOOL")).upper()
            if var_type not in {"BOOL", "INT", "REAL", "TIME"}:
                var_type = "BOOL"
            type_value: Literal["BOOL", "INT", "REAL", "TIME"] = (
                "BOOL" if var_type == "BOOL" else
                "INT" if var_type == "INT" else
                "REAL" if var_type == "REAL" else
                "TIME"
            )
            normalized.append(
                InternalVar(
                    name=name,
                    type=type_value,
                    description=str(item.get("description", "")),
                ).model_dump()
            )
        return normalized

    def _template_for(
        self,
        *,
        domain: str,
        requirement_text: str,
        confirmed_outputs: list[str] | None = None,
        safety_constraints: list[str] | None = None,
    ) -> PlanningTemplate:
        key = f"{domain} {requirement_text}".lower()
        normalized_domain = canonical_domain(domain)
        confirmed = [name.strip() for name in (confirmed_outputs or []) if name.strip()]
        normalized_constraints_text = " ".join((safety_constraints or [])).lower()

        # Prefer explicit project domain over generic keyword matching.
        if normalized_domain == "motor control":
            return self._motor_template(
                requirement_text=requirement_text,
                confirmed_outputs=confirmed,
                normalized_constraints_text=normalized_constraints_text,
            )
        if normalized_domain == "traffic control":
            return self._traffic_template()
        if normalized_domain in {"process control", "tank"}:
            return self._tank_template()
        if normalized_domain == "safety interlocks":
            return self._safety_interlock_template()
        if normalized_domain == "sequential batch":
            return self._batch_template(
                requirement_text=requirement_text,
                confirmed_outputs=confirmed,
            )

        # Fallback for incomplete/legacy domain values.
        if self._matches(key, ["motor", "conveyor", "start", "overload"]):
            return self._motor_template(
                requirement_text=requirement_text,
                confirmed_outputs=confirmed,
                normalized_constraints_text=normalized_constraints_text,
            )
        if self._matches(key, ["traffic", "signal", "pedestrian", "intersection"]):
            return self._traffic_template()
        if self._matches(key, ["tank", "level", "pump", "valve"]):
            return self._tank_template()
        if self._matches(key, ["safety", "interlock", "guard", "permissive", "press"]):
            return self._safety_interlock_template()
        if self._matches(key, ["batch", "sequence", "reactor", "fill", "drain"]):
            return self._batch_template(
                requirement_text=requirement_text,
                confirmed_outputs=confirmed,
            )

        return self._generic_template()

    @staticmethod
    def _matches(text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _normalize_performance_targets(
        targets: PerformanceTargets | dict[str, int | float] | None,
        complexity_tier: str,
    ) -> PerformanceTargets:
        if targets is None:
            defaults = {
                "simple": {
                    "maxScanTimeMs": 3,
                    "maxCyclomaticComplexity": 5,
                    "minMaintainabilityIndex": 80,
                    "maxIterations": 3,
                },
                "medium": {
                    "maxScanTimeMs": 5,
                    "maxCyclomaticComplexity": 8,
                    "minMaintainabilityIndex": 75,
                    "maxIterations": 5,
                },
                "complex": {
                    "maxScanTimeMs": 10,
                    "maxCyclomaticComplexity": 12,
                    "minMaintainabilityIndex": 70,
                    "maxIterations": 7,
                },
            }
            return PerformanceTargets(**defaults.get(complexity_tier.lower(), defaults["medium"]))

        if isinstance(targets, PerformanceTargets):
            return targets

        return PerformanceTargets(**targets)

    @staticmethod
    def _normalize_constraints(provided: list[str] | None) -> list[str]:
        constraints: list[str] = []
        for constraint in provided or []:
            clean = PlanningAgent._canonicalize_emergency_stop_aliases(constraint).strip()
            if clean and clean not in constraints:
                constraints.append(clean)
        return constraints

    @staticmethod
    def _canonicalize_emergency_stop_aliases(text: str) -> str:
        canonical = text
        canonical = canonical.replace("E-Stop", "Emergency_Stop").replace("E-stop", "Emergency_Stop")
        canonical = canonical.replace("E_Stop", "Emergency_Stop")
        canonical = canonical.replace("Emergency Stop", "Emergency_Stop").replace("emergency stop", "Emergency_Stop")
        return canonical

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _motor_template(
        *,
        requirement_text: str,
        confirmed_outputs: list[str],
        normalized_constraints_text: str,
    ) -> PlanningTemplate:
        key = requirement_text.lower()
        confirmed_lookup = {name.lower() for name in confirmed_outputs}
        include_fault_lamp = "fault_lamp" in confirmed_lookup or "fault lamp" in key or "fault indicator" in key
        include_ready_lamp = "ready_lamp" in confirmed_lookup or "ready lamp" in key or "ready indicator" in key
        include_start = "start" in key
        include_stop = "stop" in key
        include_emergency = "emergency_stop" in key
        include_overload = "overload" in key
        include_reset = "reset" in key or "reset" in normalized_constraints_text

        outputs = [
            PlanSignal(name="Motor_Run", type="BOOL", address="DO-01", description="Motor contactor coil"),
        ]
        if include_fault_lamp:
            outputs.append(PlanSignal(name="Fault_Lamp", type="BOOL", address="DO-02", description="Latched fault indicator"))
        if include_ready_lamp:
            outputs.append(PlanSignal(name="Ready_Lamp", type="BOOL", address="DO-03", description="Ready-to-start indicator"))

        logic_rules = ["Implement the controller as an IEC 61131-3 PROGRAM POU"]
        if include_start and include_stop and (include_emergency or include_overload):
            logic_rules.append("Start command latches only while stop and safety permissives are clear")
        if include_emergency or include_overload:
            logic_rules.append("Safety trip sets a latched Fault_State and drops Motor_Run")
        if include_reset:
            logic_rules.append("Fault_State clears only after Reset_PB while all safety sources are clear")
        if include_ready_lamp:
            logic_rules.append("Ready_Lamp is true only when no fault is latched and Motor_Run is false")

        inputs: list[PlanSignal] = []
        if include_start:
            inputs.append(PlanSignal(name="Start_PB", type="BOOL", source="DI-04", description="Momentary start pushbutton"))
        if include_stop:
            inputs.append(PlanSignal(name="Stop_PB", type="BOOL", source="DI-05", description="Momentary stop pushbutton, normally closed"))
        if include_emergency:
            inputs.append(PlanSignal(name="Emergency_Stop", type="BOOL", source="DI-06", description="Emergency stop input, normally closed safety relay contact"))
        if include_overload:
            inputs.append(PlanSignal(name="Overload", type="BOOL", source="DI-07", description="Thermal overload relay contact"))
        if include_reset:
            inputs.append(PlanSignal(name="Reset_PB", type="BOOL", source="DI-08", description="Operator fault acknowledgement pushbutton"))

        return PlanningTemplate(
            inputs=inputs,
            outputs=outputs,
            logic_rules=logic_rules,
            safety_constraints=[],
        )

    @staticmethod
    def _traffic_template() -> PlanningTemplate:
        return PlanningTemplate(
            inputs=[
                PlanSignal(name="Vehicle_Detect", type="BOOL", source="DI-01", description="Vehicle presence detector on the main approach"),
                PlanSignal(name="Ped_Request", type="BOOL", source="DI-02", description="Pedestrian crossing request pushbutton"),
                PlanSignal(name="Emergency_Flash", type="BOOL", source="DI-03", description="Emergency flash mode command"),
                PlanSignal(name="Cycle_Timer", type="TIME", description="Configured phase timer for the signal sequence"),
            ],
            outputs=[
                PlanSignal(name="Red_Light", type="BOOL", address="DO-01", description="Red traffic signal lamp"),
                PlanSignal(name="Amber_Light", type="BOOL", address="DO-02", description="Amber traffic signal lamp"),
                PlanSignal(name="Green_Light", type="BOOL", address="DO-03", description="Green traffic signal lamp"),
                PlanSignal(name="Ped_Walk", type="BOOL", address="DO-04", description="Pedestrian walk indication"),
            ],
            logic_rules=[
                "Implement the controller as an IEC 61131-3 PROGRAM POU",
                "Cycle through green, amber, red, and pedestrian phases using Cycle_Timer",
                "Ped_Request is served only during a protected red vehicle phase",
                "Emergency_Flash forces Amber_Light flashing and all other outputs off",
                "Never energize conflicting green and pedestrian walk indications together",
            ],
            safety_constraints=[
                "Conflicting vehicle and pedestrian movements must never be active together",
                "Red clearance must occur before Ped_Walk is energized",
                "Emergency flash mode must force a deterministic safe output pattern",
            ],
        )

    @staticmethod
    def _tank_template() -> PlanningTemplate:
        return PlanningTemplate(
            inputs=[
                PlanSignal(name="Level_PV", type="REAL", source="AI-01", description="Measured tank level process value"),
                PlanSignal(name="Low_SP", type="REAL", description="Low level setpoint for fill request"),
                PlanSignal(name="High_SP", type="REAL", description="High level setpoint for fill cutoff"),
                PlanSignal(name="HighHigh_SP", type="REAL", description="High-high trip setpoint"),
                PlanSignal(name="Auto_Mode", type="BOOL", source="DI-01", description="Automatic control mode selector"),
            ],
            outputs=[
                PlanSignal(name="Inlet_Valve", type="BOOL", address="DO-01", description="Fill valve command"),
                PlanSignal(name="Outlet_Valve", type="BOOL", address="DO-02", description="Drain valve command"),
                PlanSignal(name="High_Alarm", type="BOOL", address="DO-03", description="High level alarm indication"),
            ],
            logic_rules=[
                "Implement the controller as an IEC 61131-3 PROGRAM POU",
                "Open Inlet_Valve in Auto_Mode when Level_PV is below Low_SP",
                "Close Inlet_Valve when Level_PV reaches High_SP or HighHigh_SP",
                "Set High_Alarm when Level_PV is greater than or equal to HighHigh_SP",
                "Prevent simultaneous inlet and outlet valve commands",
            ],
            safety_constraints=[
                "High-high level must close the inlet valve",
                "Inlet and outlet valves must not be commanded open at the same time",
                "Control must fail safe if Auto_Mode is not active",
            ],
        )

    @staticmethod
    def _safety_interlock_template() -> PlanningTemplate:
        return PlanningTemplate(
            inputs=[
                PlanSignal(name="Guard_Closed", type="BOOL", source="DI-01", description="Machine guard closed confirmation"),
                PlanSignal(name="TwoHand_Left", type="BOOL", source="DI-02", description="Left two-hand control input"),
                PlanSignal(name="TwoHand_Right", type="BOOL", source="DI-03", description="Right two-hand control input"),
                PlanSignal(name="Reset_PB", type="BOOL", source="DI-04", description="Manual reset pushbutton"),
                PlanSignal(name="Fault_Input", type="BOOL", source="DI-05", description="External safety relay fault input"),
            ],
            outputs=[
                PlanSignal(name="Machine_Enable", type="BOOL", address="DO-01", description="Permissive enable for machine motion"),
                PlanSignal(name="Trip_Lamp", type="BOOL", address="DO-02", description="Safety trip indicator"),
                PlanSignal(name="Alarm_Horn", type="BOOL", address="DO-03", description="Audible alarm output"),
            ],
            logic_rules=[
                "Implement the controller as an IEC 61131-3 PROGRAM POU",
                "Machine_Enable requires Guard_Closed and both two-hand inputs",
                "Fault_Input or open guard latches Trip_State",
                "Trip_State clears only after Reset_PB while all permissives are healthy",
                "Trip_Lamp and Alarm_Horn follow Trip_State",
            ],
            safety_constraints=[
                "Machine enable must drop immediately when any permissive is lost",
                "Trip reset must be manual and deliberate",
                "Fault indication must remain latched until reset",
            ],
        )

    @staticmethod
    def _batch_template(
        *,
        requirement_text: str,
        confirmed_outputs: list[str],
    ) -> PlanningTemplate:
        key = requirement_text.lower()
        output_catalog: list[tuple[str, PlanSignal, list[str]]] = [
            (
                "Fill_Valve",
                PlanSignal(name="Fill_Valve", type="BOOL", address="DO-01", description="Fill valve command"),
                ["fill_valve", "fill valve", "fill"],
            ),
            (
                "Mixer_Motor",
                PlanSignal(name="Mixer_Motor", type="BOOL", address="DO-02", description="Mixer motor command"),
                ["mixer_motor", "mixer motor", "mix"],
            ),
            (
                "Drain_Valve",
                PlanSignal(name="Drain_Valve", type="BOOL", address="DO-03", description="Drain valve command"),
                ["drain_valve", "drain valve", "drain"],
            ),
            (
                "Batch_Complete",
                PlanSignal(name="Batch_Complete", type="BOOL", address="DO-04", description="Batch complete indication"),
                ["batch_complete", "batch complete", "complete batch"],
            ),
            (
                "Motor_Run",
                PlanSignal(name="Motor_Run", type="BOOL", address="DO-05", description="Generic motor run command"),
                ["motor_run", "motor run", "contactor"],
            ),
        ]
        catalog_by_lower = {name.lower(): signal for name, signal, _ in output_catalog}
        ordered_confirmed: list[PlanSignal] = []
        if confirmed_outputs:
            for name in confirmed_outputs:
                signal = catalog_by_lower.get(name.lower())
                if signal and signal.name not in {item.name for item in ordered_confirmed}:
                    ordered_confirmed.append(signal)
        if ordered_confirmed:
            outputs = ordered_confirmed
        else:
            outputs = [
                signal
                for _, signal, hints in output_catalog
                if any(hint in key for hint in hints)
            ]
        return PlanningTemplate(
            inputs=[
                PlanSignal(name="Start_PB", type="BOOL", source="DI-01", description="Batch start pushbutton"),
                PlanSignal(name="Emergency_Stop", type="BOOL", source="DI-02", description="Emergency stop safety input"),
                PlanSignal(name="Abort_PB", type="BOOL", source="DI-03", description="Batch abort pushbutton"),
                PlanSignal(name="Reset_PB", type="BOOL", source="DI-04", description="Fault reset pushbutton"),
                PlanSignal(name="High_Level", type="BOOL", source="DI-05", description="High level switch indication"),
                PlanSignal(name="Low_Level", type="BOOL", source="DI-06", description="Low level switch indication"),
                PlanSignal(name="Mix_Timer_Done", type="BOOL", source="DI-07", description="Mix timer completion"),
            ],
            outputs=outputs,
            logic_rules=[
                "Implement the controller as an IEC 61131-3 PROGRAM POU",
                "Define internal variables: Step_State : INT, Fault_State : BOOL, Safety_OK : BOOL",
                "Fill step: open Fill_Valve until High_Level is true, then advance sequence",
                "Mix step: run Mixer_Motor until Mix_Timer_Done is true, then advance sequence",
                "Drain step: open Drain_Valve until Low_Level is true, then set Batch_Complete",
                "Emergency/abort shutdown: Emergency_Stop or Abort_PB immediately de-energizes all outputs and latches Fault_State",
                "Reset after fault: Reset_PB clears Fault_State only when Safety_OK is restored",
                "Return to idle after complete: clear Batch_Complete and return Step_State to idle on next start cycle",
            ],
            safety_constraints=[
                "Emergency_Stop or Abort_PB must force all outputs off",
                "Fill_Valve and Drain_Valve must never be active together",
                "Mixer_Motor may run only during the mix step when Safety_OK is true",
            ],
        )

    @staticmethod
    def _generic_template() -> PlanningTemplate:
        return PlanningTemplate(
            inputs=[
                PlanSignal(name="Start_Cmd", type="BOOL", source="DI-01", description="Operator start command"),
                PlanSignal(name="Stop_Cmd", type="BOOL", source="DI-02", description="Operator stop command"),
                PlanSignal(name="Reset_Cmd", type="BOOL", source="DI-03", description="Manual reset command"),
            ],
            outputs=[
                PlanSignal(name="Process_Enable", type="BOOL", address="DO-01", description="Generic controlled process enable"),
                PlanSignal(name="Fault_Indication", type="BOOL", address="DO-02", description="Generic latched fault indication"),
            ],
            logic_rules=[
                "Implement the controller as an IEC 61131-3 PROGRAM POU",
                "Start_Cmd enables the process only when no fault is active",
                "Stop_Cmd disables the process immediately",
                "Fault_Indication remains latched until Reset_Cmd",
            ],
            safety_constraints=[
                "Process output must de-energize on stop or fault",
                "Fault reset must require explicit operator action",
                "Outputs must default to a safe false state",
            ],
        )
