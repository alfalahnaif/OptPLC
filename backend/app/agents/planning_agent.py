from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app.schemas.contracts import PerformanceTargets, PlanObject, PlanScope, PlanSignal

PlanningMode = Literal["rule_based", "llm"]


@dataclass(frozen=True)
class PlanningTemplate:
    inputs: list[PlanSignal]
    outputs: list[PlanSignal]
    logic_rules: list[str]
    safety_constraints: list[str]


class PlanningAgent:
    def __init__(self, mode: PlanningMode = "rule_based") -> None:
        self.mode = mode

    def generate_plan(
        self,
        *,
        project_id: str,
        requirement_text: str,
        safety_constraints: list[str] | None = None,
        performance_targets: PerformanceTargets | dict[str, int | float] | None = None,
        domain: str = "",
        complexity_tier: str = "medium",
    ) -> PlanObject:
        if self.mode == "llm":
            raise NotImplementedError("PlanningAgent llm mode is reserved for future integration and makes no external calls.")
        if self.mode != "rule_based":
            raise ValueError(f"Unsupported PlanningAgent mode: {self.mode}")
        if not requirement_text.strip():
            raise ValueError("Requirement text must not be empty.")

        self._normalize_performance_targets(performance_targets, complexity_tier)
        template = self._template_for(domain=domain, requirement_text=requirement_text)
        merged_constraints = self._merge_constraints(safety_constraints, template.safety_constraints)

        return PlanObject(
            projectId=project_id,
            agent="PlanningAgent/rule_based.v1",
            generatedAt=self._utc_now(),
            inputs=template.inputs,
            outputs=template.outputs,
            logicRules=template.logic_rules,
            safetyConstraints=merged_constraints,
            scope=PlanScope(
                standard="IEC 61131-3",
                edition="3rd ed. (2013)",
                language="Structured Text",
                runtime="CODESYS / TwinCAT compatible",
            ),
        )

    def _template_for(self, *, domain: str, requirement_text: str) -> PlanningTemplate:
        key = f"{domain} {requirement_text}".lower()

        if self._matches(key, ["motor", "conveyor", "start", "overload"]):
            return self._motor_template()
        if self._matches(key, ["traffic", "signal", "pedestrian", "intersection"]):
            return self._traffic_template()
        if self._matches(key, ["tank", "level", "pump", "valve"]):
            return self._tank_template()
        if self._matches(key, ["safety", "interlock", "guard", "permissive", "press"]):
            return self._safety_interlock_template()
        if self._matches(key, ["batch", "sequence", "reactor", "fill", "drain"]):
            return self._batch_template()

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
    def _merge_constraints(provided: list[str] | None, defaults: list[str]) -> list[str]:
        constraints: list[str] = []
        for constraint in [*(provided or []), *defaults]:
            clean = constraint.strip()
            if clean and clean not in constraints:
                constraints.append(clean)
        return constraints

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _motor_template() -> PlanningTemplate:
        return PlanningTemplate(
            inputs=[
                PlanSignal(name="Start_PB", type="BOOL", source="DI-04", description="Momentary start pushbutton"),
                PlanSignal(name="Stop_PB", type="BOOL", source="DI-05", description="Momentary stop pushbutton, normally closed"),
                PlanSignal(name="E_Stop", type="BOOL", source="DI-06", description="Emergency stop input, normally closed safety relay contact"),
                PlanSignal(name="Overload", type="BOOL", source="DI-07", description="Thermal overload relay contact"),
                PlanSignal(name="Reset_PB", type="BOOL", source="DI-08", description="Operator fault acknowledgement pushbutton"),
            ],
            outputs=[
                PlanSignal(name="Motor_Run", type="BOOL", address="DO-01", description="Motor contactor coil"),
                PlanSignal(name="Fault_Lamp", type="BOOL", address="DO-02", description="Latched fault indicator"),
                PlanSignal(name="Ready_Lamp", type="BOOL", address="DO-03", description="Ready-to-start indicator"),
            ],
            logic_rules=[
                "Implement the controller as an IEC 61131-3 PROGRAM POU",
                "Start command latches only while Stop, E_Stop, and Overload are clear",
                "E_Stop or Overload sets a latched Fault_State and drops Motor_Run",
                "Fault_State clears only after Reset_PB while all safety sources are clear",
                "Ready_Lamp is true only when no fault is latched and Motor_Run is false",
            ],
            safety_constraints=[
                "Motor must not restart automatically after E-stop or overload",
                "E-stop input must be normally closed; loss of signal triggers fault",
                "Reset must require explicit operator action",
                "Fault lamp must reflect latched fault, not transient signal",
            ],
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
    def _batch_template() -> PlanningTemplate:
        return PlanningTemplate(
            inputs=[
                PlanSignal(name="Start_Batch", type="BOOL", source="DI-01", description="Batch start command"),
                PlanSignal(name="Stop_Batch", type="BOOL", source="DI-02", description="Batch stop command"),
                PlanSignal(name="Level_OK", type="BOOL", source="DI-03", description="Batch fill level reached"),
                PlanSignal(name="Temp_PV", type="REAL", source="AI-01", description="Reactor temperature process value"),
                PlanSignal(name="Step_Timer", type="TIME", description="Timer used for heat, mix, and drain steps"),
            ],
            outputs=[
                PlanSignal(name="Fill_Valve", type="BOOL", address="DO-01", description="Fill valve command"),
                PlanSignal(name="Heater", type="BOOL", address="DO-02", description="Heating element command"),
                PlanSignal(name="Agitator", type="BOOL", address="DO-03", description="Mixer motor command"),
                PlanSignal(name="Drain_Valve", type="BOOL", address="DO-04", description="Drain valve command"),
                PlanSignal(name="Batch_Complete", type="BOOL", address="DO-05", description="Batch complete indication"),
            ],
            logic_rules=[
                "Implement the controller as an IEC 61131-3 PROGRAM POU",
                "Advance through idle, fill, heat, mix, drain, and complete states",
                "Fill_Valve remains open until Level_OK is true",
                "Heater and Agitator operate only in their assigned sequence states",
                "Stop_Batch returns outputs to a safe idle state",
            ],
            safety_constraints=[
                "Only one material transfer valve may be open during a sequence step",
                "Heater must be off outside the heat step",
                "Stop command must de-energize all process outputs",
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
