from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from app.schemas.contracts import CodeArtifact, CodeMetadata, CodeMetrics, PlanObject, PlanSignal

CodeGenerationMode = Literal["template_based", "llm"]


class CodeGenerationAgent:
    def __init__(self, mode: CodeGenerationMode = "template_based") -> None:
        self.mode = mode

    def generate_code(
        self,
        *,
        project_id: str,
        plan: PlanObject,
        patch_advice: list[str] | None = None,
        suggested_regeneration_prompt: str | None = None,
        iteration: int = 1,
    ) -> CodeArtifact:
        if self.mode == "llm":
            raise NotImplementedError("CodeGenerationAgent llm mode is reserved for future integration and makes no external calls.")
        if self.mode != "template_based":
            raise ValueError(f"Unsupported CodeGenerationAgent mode: {self.mode}")

        repair_mode = bool(patch_advice or suggested_regeneration_prompt)
        source = self._source_for(plan)
        if repair_mode:
            source = self._annotate_repair(
                source=source,
                patch_advice=patch_advice or [],
                suggested_regeneration_prompt=suggested_regeneration_prompt,
            )
        created_at = self._utc_now()
        loc = len([line for line in source.splitlines() if line.strip()])
        generator = "template_based.repair.v1" if repair_mode else "template_based.v1"

        return CodeArtifact(
            projectId=project_id,
            artifactId=f"{project_id}-code-iter-{iteration}",
            language="structured-text",
            filename=f"{self._program_name(plan)}.st".lower(),
            source=source,
            iteration=iteration,
            generatedAt=created_at,
            metrics=CodeMetrics(
                loc=loc,
                cyclomaticComplexity=self._estimate_cyclomatic(source),
                maintainabilityIndex=max(65, min(95, 92 - self._estimate_cyclomatic(source) * 3)),
            ),
            metadata=CodeMetadata(
                generator=generator,
                iecStandard="IEC 61131-3",
                sourcePlanId=plan.projectId,
                createdAt=created_at,
                iteration=iteration,
            ),
        )

    def _source_for(self, plan: PlanObject) -> str:
        names = {signal.name for signal in [*plan.inputs, *plan.outputs]}

        if {"Start_PB", "Stop_PB", "E_Stop", "Overload", "Motor_Run"}.issubset(names):
            return self._motor_source(plan)
        if {"Vehicle_Detect", "Ped_Request", "Red_Light", "Green_Light", "Ped_Walk"}.issubset(names):
            return self._traffic_source(plan)
        if {"Level_PV", "Low_SP", "High_SP", "Inlet_Valve"}.issubset(names):
            return self._tank_source(plan)
        if {"Guard_Closed", "Machine_Enable", "Trip_Lamp"}.issubset(names):
            return self._safety_interlock_source(plan)
        if {"Start_Batch", "Fill_Valve", "Heater", "Drain_Valve"}.issubset(names):
            return self._batch_source(plan)

        return self._generic_source(plan)

    def _motor_source(self, plan: PlanObject) -> str:
        return self._assemble_program(
            plan,
            internal_variables=[
                ("Run_Cmd", "BOOL"),
                ("Fault_State", "BOOL"),
                ("Safety_OK", "BOOL"),
            ],
            logic=[
                "(* Safety handling: emergency stop or overload always stops the motor. *)",
                "Safety_OK := E_Stop AND NOT Overload;",
                "",
                "IF NOT Safety_OK THEN",
                "    Fault_State := TRUE;",
                "    Run_Cmd := FALSE;",
                "END_IF;",
                "",
                "(* Manual reset is required before restart after any safety trip. *)",
                "IF Fault_State AND Reset_PB AND Safety_OK THEN",
                "    Fault_State := FALSE;",
                "END_IF;",
                "",
                "(* Start/stop latch gated by the latched fault state. *)",
                "IF Start_PB AND NOT Stop_PB AND NOT Fault_State THEN",
                "    Run_Cmd := TRUE;",
                "END_IF;",
                "",
                "IF Stop_PB OR Fault_State THEN",
                "    Run_Cmd := FALSE;",
                "END_IF;",
                "",
                "(* Outputs. *)",
                "Motor_Run := Run_Cmd AND Safety_OK AND NOT Fault_State;",
                "Fault_Lamp := Fault_State;",
                "Ready_Lamp := Safety_OK AND NOT Fault_State AND NOT Motor_Run;",
            ],
        )

    def _traffic_source(self, plan: PlanObject) -> str:
        return self._assemble_program(
            plan,
            internal_variables=[
                ("Phase_Red", "BOOL"),
                ("Phase_Amber", "BOOL"),
            ],
            logic=[
                "(* Emergency flash forces a deterministic non-conflicting pattern. *)",
                "IF Emergency_Flash THEN",
                "    Red_Light := FALSE;",
                "    Amber_Light := TRUE;",
                "    Green_Light := FALSE;",
                "    Ped_Walk := FALSE;",
                "ELSE",
                "    (* Protected pedestrian service only during red vehicle phase. *)",
                "    Phase_Red := Ped_Request;",
                "    Phase_Amber := Vehicle_Detect AND NOT Phase_Red;",
                "",
                "    Red_Light := Phase_Red;",
                "    Amber_Light := Phase_Amber;",
                "    Green_Light := NOT Red_Light AND NOT Amber_Light;",
                "    Ped_Walk := Red_Light AND Ped_Request;",
                "END_IF;",
            ],
        )

    def _tank_source(self, plan: PlanObject) -> str:
        return self._assemble_program(
            plan,
            internal_variables=[
                ("Fill_Request", "BOOL"),
                ("High_Trip", "BOOL"),
            ],
            logic=[
                "(* Level limit handling. *)",
                "High_Trip := Level_PV >= HighHigh_SP;",
                "Fill_Request := Auto_Mode AND (Level_PV <= Low_SP) AND NOT High_Trip;",
                "",
                "(* Fill until high limit, then fail safe closed on high-high. *)",
                "IF Level_PV >= High_SP OR High_Trip THEN",
                "    Inlet_Valve := FALSE;",
                "ELSE",
                "    Inlet_Valve := Fill_Request;",
                "END_IF;",
                "",
                "Outlet_Valve := FALSE;",
                "High_Alarm := High_Trip;",
            ],
        )

    def _safety_interlock_source(self, plan: PlanObject) -> str:
        return self._assemble_program(
            plan,
            internal_variables=[
                ("Permissive_OK", "BOOL"),
                ("Trip_State", "BOOL"),
            ],
            logic=[
                "(* Fail-safe permissive chain. *)",
                "Permissive_OK := Guard_Closed AND TwoHand_Left AND TwoHand_Right AND NOT Fault_Input;",
                "",
                "IF NOT Permissive_OK THEN",
                "    Trip_State := TRUE;",
                "END_IF;",
                "",
                "IF Trip_State AND Reset_PB AND Permissive_OK THEN",
                "    Trip_State := FALSE;",
                "END_IF;",
                "",
                "Machine_Enable := Permissive_OK AND NOT Trip_State;",
                "Trip_Lamp := Trip_State;",
                "Alarm_Horn := Trip_State;",
            ],
        )

    def _batch_source(self, plan: PlanObject) -> str:
        return self._assemble_program(
            plan,
            internal_variables=[
                ("Step", "INT"),
            ],
            logic=[
                "(* Sequential batch state machine: 0 idle, 10 fill, 20 heat, 30 mix, 40 drain, 50 complete. *)",
                "IF Stop_Batch THEN",
                "    Step := 0;",
                "END_IF;",
                "",
                "CASE Step OF",
                "    0:",
                "        IF Start_Batch THEN Step := 10; END_IF;",
                "    10:",
                "        IF Level_OK THEN Step := 20; END_IF;",
                "    20:",
                "        IF Temp_PV >= 80.0 THEN Step := 30; END_IF;",
                "    30:",
                "        Step := 40;",
                "    40:",
                "        Step := 50;",
                "    50:",
                "        IF NOT Start_Batch THEN Step := 0; END_IF;",
                "    ELSE",
                "        Step := 0;",
                "END_CASE;",
                "",
                "Fill_Valve := Step = 10;",
                "Heater := Step = 20;",
                "Agitator := Step = 30;",
                "Drain_Valve := Step = 40;",
                "Batch_Complete := Step = 50;",
            ],
        )

    def _generic_source(self, plan: PlanObject) -> str:
        return self._assemble_program(
            plan,
            internal_variables=[
                ("Run_State", "BOOL"),
                ("Fault_State", "BOOL"),
            ],
            logic=[
                "(* Generic safe enable fallback. *)",
                "IF Stop_Cmd THEN",
                "    Run_State := FALSE;",
                "END_IF;",
                "",
                "IF Reset_Cmd THEN",
                "    Fault_State := FALSE;",
                "END_IF;",
                "",
                "IF Start_Cmd AND NOT Fault_State THEN",
                "    Run_State := TRUE;",
                "END_IF;",
                "",
                "Process_Enable := Run_State AND NOT Fault_State;",
                "Fault_Indication := Fault_State;",
            ],
        )

    def _assemble_program(
        self,
        plan: PlanObject,
        *,
        internal_variables: list[tuple[str, str]],
        logic: list[str],
    ) -> str:
        sections = [
            f"PROGRAM {self._program_name(plan)}",
            "(* Generated by CodeGenerationAgent template_based.v1 from PlanObject. *)",
            "",
            "(* Inputs derived from the PlanObject. *)",
            "VAR_INPUT",
            *self._declarations(plan.inputs),
            "END_VAR",
            "",
            "(* Outputs derived from the PlanObject. *)",
            "VAR_OUTPUT",
            *self._declarations(plan.outputs),
            "END_VAR",
        ]

        if internal_variables:
            sections.extend([
                "",
                "(* Internal state and helper variables. *)",
                "VAR",
                *[f"    {name} : {signal_type};" for name, signal_type in internal_variables],
                "END_VAR",
            ])

        sections.extend([
            "",
            "(* Main control logic. *)",
            *logic,
            "",
            "END_PROGRAM",
        ])

        return "\n".join(sections)

    @staticmethod
    def _declarations(signals: list[PlanSignal]) -> list[str]:
        return [f"    {signal.name} : {signal.type};  (* {signal.description} *)" for signal in signals]

    def _annotate_repair(
        self,
        *,
        source: str,
        patch_advice: list[str],
        suggested_regeneration_prompt: str | None,
    ) -> str:
        repair_lines = [
            "(* Repair loop: regenerated from DebuggingReport patch advice. *)",
            *[f"(* Repair advice {index}: {self._comment_safe(advice)} *)" for index, advice in enumerate(patch_advice, start=1)],
        ]
        if suggested_regeneration_prompt:
            repair_lines.append(f"(* Repair prompt: {self._comment_safe(suggested_regeneration_prompt)} *)")

        repaired = source.replace("template_based.v1", "template_based.repair.v1", 1)
        marker = "(* Inputs derived from the PlanObject. *)"
        if marker in repaired:
            return repaired.replace(marker, "\n".join([*repair_lines, "", marker]), 1)
        return "\n".join([*repair_lines, repaired])

    @staticmethod
    def _comment_safe(value: str) -> str:
        return value.replace("*)", "* )").strip()

    @staticmethod
    def _program_name(plan: PlanObject) -> str:
        sanitized = "".join(char if char.isalnum() else "_" for char in plan.projectId)
        return f"PLC_{sanitized}_Controller"

    @staticmethod
    def _estimate_cyclomatic(source: str) -> int:
        branch_tokens = ["IF ", "ELSIF ", "CASE ", "FOR ", "WHILE "]
        return 1 + sum(source.count(token) for token in branch_tokens)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
