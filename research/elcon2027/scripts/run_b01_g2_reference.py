from pathlib import Path
from app.agents.validation_agent import SequentialBatchValidator

SOURCE = "/tmp/E27-B01_reference.st"

SIGNALS = {
    "Start_PB",
    "E_Stop",
    "Abort",
    "Reset_PB",
    "High_Level",
    "Low_Level",
    "Mix_Timer_Done",
    "Fill_Valve",
    "Mixer_Motor",
    "Drain_Valve",
    "Batch_Complete",
}

source = Path(SOURCE).read_text(encoding="utf-8")
validator = SequentialBatchValidator()

detected = validator.detect(
    signal_names=SIGNALS,
    source=source,
    plan_domain="Sequential Batch",
)

checks = validator.validate(
    source=source,
    signal_names=SIGNALS,
)

overall = all(c.status == "passed" for c in checks)

print("=== E27-B01 G2 SEQUENTIAL BATCH VALIDATOR ===")
print("Domain detected:", detected)
print("Overall:", "PASS" if overall else "DETECT")

for c in checks:
    print(f"{c.id}: {c.status.upper()} - {c.description}")
    if c.details:
        print("   Details:", c.details)

