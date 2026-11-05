PROGRAM MotorControl
VAR_INPUT
    Start_PB       : BOOL;
    Stop_PB        : BOOL;
    Emergency_Stop : BOOL;
    Reset_PB       : BOOL;
    Overload       : BOOL;
END_VAR

VAR_OUTPUT
    Motor : BOOL;
END_VAR

VAR
    Run_Latched   : BOOL := FALSE;
    Fault_Latched : BOOL := FALSE;
END_VAR

(* Latch emergency-stop or overload faults. *)
IF (NOT Emergency_Stop) THEN
    Fault_Latched := TRUE;
END_IF;

(* Reset is allowed only when the safety circuit is healthy. *)
IF Reset_PB AND Emergency_Stop AND (NOT Overload) AND Stop_PB THEN
    Fault_Latched := FALSE;
END_IF;

(* Stop and latched faults have priority over Start. *)
IF (NOT Stop_PB) OR Fault_Latched THEN
    Run_Latched := FALSE;
ELSIF Start_PB AND Emergency_Stop AND (NOT Overload) THEN
    Run_Latched := TRUE;
END_IF;

Motor := Run_Latched AND (NOT Fault_Latched);

END_PROGRAM

