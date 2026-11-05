PROGRAM SafetyGateInterlock

VAR_INPUT
    Guard_Closed   : BOOL;
    E_Stop: BOOL;
    Reset_PB       : BOOL;
    Fault_Input    : BOOL;
    TwoHand_Left   : BOOL;
    TwoHand_Right  : BOOL;
END_VAR

VAR_OUTPUT
    Machine_Enable : BOOL;
END_VAR

VAR
    Safety_Permissive : BOOL;
    Fault_Latched     : BOOL := TRUE;
END_VAR

Fault_Latched := (NOT Guard_Closed) OR (NOT E_Stop) OR Fault_Input;

Safety_Permissive :=
    Guard_Closed
    AND E_Stop
    AND (NOT Fault_Input)
    AND (NOT Fault_Latched);

Machine_Enable :=
    Safety_Permissive
    AND TwoHand_Left
    AND TwoHand_Right;

END_PROGRAM


