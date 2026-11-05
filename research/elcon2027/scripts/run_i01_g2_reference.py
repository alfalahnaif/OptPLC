from pathlib import Path
from app.agents.validation_agent import SafetyInterlockValidator

SOURCE = "/tmp/E27-I01_reference.st"

SIGNALS = {
    "Guard_Closed",
    "E_Stop",
    "Reset_PB",
    "Fault_Input",
    "TwoHand_Left",
    "TwoHand_Right",
    "Machine_Enable",
}

source = Path(SOURCE).read_text(encoding="utf-8")

validator = SafetyInterlockValidator()

detected = validator.detect(
    signal_names=SIGNALS,
    source=source,
    plan_domain="Safety Interlock",
)

checks = validator.validate(
    source=source,
    signal_names=SIGNALS,
)

print("=== E27-I01 G2 SAFETY INTERLOCK VALIDATOR ===")
print("Domain detected:", detected)

overall = all(c.status == "passed" for c in checks)
print("Overall:", "PASS" if overall else "DETECT")

for c in checks:
    print(f"{c.id}: {c.status.upper()} - {c.description}")
    if c.details:
        print("   Details:", c.details)

