from pathlib import Path
from app.agents.validation_agent import SequentialBatchValidator

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

FILES = {
    "reference": "/tmp/E27-B01_reference.st",
}

for p in sorted(Path("/tmp").glob("B-M*.st")):
    FILES[p.stem.split("_", 1)[0]] = str(p)

validator = SequentialBatchValidator()

print("\n=== E27-B01 G2 SEQUENTIAL BATCH VALIDATOR ===")

for label, filepath in FILES.items():
    source = Path(filepath).read_text(encoding="utf-8")

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

    print(f"\n{label.upper()}")
    print("Domain detected:", detected)
    print("Overall:", "PASS" if overall else "DETECT")

    for c in checks:
        print(f"{c.id}: {c.status.upper()} - {c.description}")
        if c.details:
            print("   Details:", c.details)