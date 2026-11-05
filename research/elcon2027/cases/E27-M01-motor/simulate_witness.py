def reference_step(state, inp):
    run_latched, fault_latched = state
    if (not inp["Emergency_Stop"]) or inp["Overload"]:
        fault_latched = True
    if inp["Reset_PB"] and inp["Emergency_Stop"] and (not inp["Overload"]) and inp["Stop_PB"]:
        fault_latched = False
    if (not inp["Stop_PB"]) or fault_latched:
        run_latched = False
    elif inp["Start_PB"] and inp["Emergency_Stop"] and (not inp["Overload"]):
        run_latched = True
    motor = run_latched and (not fault_latched)
    return (run_latched, fault_latched), motor


def mutant_m3_step(state, inp):
    run_latched, fault_latched = state
    if (not inp["Emergency_Stop"]) or inp["Overload"]:
        fault_latched = True
    if inp["Emergency_Stop"] and (not inp["Overload"]) and inp["Stop_PB"]:
        fault_latched = False
    if (not inp["Stop_PB"]) or fault_latched:
        run_latched = False
    elif inp["Start_PB"] and inp["Emergency_Stop"] and (not inp["Overload"]):
        run_latched = True
    motor = run_latched and (not fault_latched)
    return (run_latched, fault_latched), motor

trace = [
    {"Start_PB": True, "Stop_PB": True, "Emergency_Stop": True,  "Reset_PB": False, "Overload": False},
    {"Start_PB": True, "Stop_PB": True, "Emergency_Stop": False, "Reset_PB": False, "Overload": False},
    {"Start_PB": True, "Stop_PB": True, "Emergency_Stop": True,  "Reset_PB": False, "Overload": False},
]
ref_state = (False, False)
mut_state = (False, False)
print("scan,reference_motor,mutant_m3_motor")
for i, inp in enumerate(trace, start=1):
    ref_state, ref_motor = reference_step(ref_state, inp)
    mut_state, mut_motor = mutant_m3_step(mut_state, inp)
    print(f"{i},{int(ref_motor)},{int(mut_motor)}")
