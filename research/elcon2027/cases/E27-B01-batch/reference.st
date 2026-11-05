PROGRAM SequentialBatch

VAR_INPUT
    Start_PB       : BOOL;
    E_Stop         : BOOL;
    Abort       : BOOL;
    Reset_PB       : BOOL;
    High_Level     : BOOL;
    Low_Level      : BOOL;
    Mix_Timer_Done : BOOL;
END_VAR

VAR_OUTPUT
    Fill_Valve     : BOOL;
    Mixer_Motor    : BOOL;
    Drain_Valve    : BOOL;
    Batch_Complete : BOOL;
END_VAR

VAR
    Step_State    : INT := 0;
    Fault_Latched : BOOL := FALSE;
    Safety_OK     : BOOL;
END_VAR

Safety_OK := E_Stop AND (NOT Abort);

IF (NOT E_Stop) OR Abort THEN
    Fault_Latched := TRUE;
    Step_State := 0;
END_IF;

IF Reset_PB AND Safety_OK THEN
    Fault_Latched := FALSE;
END_IF;

Fill_Valve := FALSE;
Mixer_Motor := FALSE;
Drain_Valve := FALSE;

CASE Step_State OF

    0:
        Batch_Complete := FALSE;

        IF Start_PB AND Safety_OK AND (NOT Fault_Latched) THEN
            Fill_Valve := TRUE;
            Step_State := 1;
        END_IF;

    1:
        Fill_Valve := TRUE;

        IF High_Level THEN
            Step_State := 2;
        END_IF;

    2:
        Mixer_Motor := TRUE;

        IF Mix_Timer_Done THEN
            Step_State := 3;
        END_IF;

    3:
        Drain_Valve := TRUE;

        IF Low_Level THEN
            Step_State := 4;
        END_IF;

    4:
        Batch_Complete := TRUE;

        IF Start_PB AND Safety_OK AND (NOT Fault_Latched) THEN
            Batch_Complete := FALSE;
            Fill_Valve := TRUE;
            Step_State := 1;
        END_IF;

ELSE
    Fill_Valve := FALSE;
    Mixer_Motor := FALSE;
    Drain_Valve := FALSE;
    Batch_Complete := FALSE;
    Step_State := 0;
    Fault_Latched := TRUE;

END_CASE;

IF (NOT E_Stop) OR Abort OR Fault_Latched THEN
    Fill_Valve := FALSE;
    Mixer_Motor := FALSE;
    Drain_Valve := FALSE;
    Batch_Complete := FALSE;
END_IF;

END_PROGRAM

