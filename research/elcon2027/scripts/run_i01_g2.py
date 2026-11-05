import json
from pathlib import Path
from app.agents.validation_agent import SafetyInterlockValidator

SIGNALS = {
    "Guard_Closed",
    "E_Stop",
    "Reset_PB",
    "Fault_Input",
    "TwoHand_Left",
    "TwoHand_Right",
    "Machine_Enable",
}

FILES = {
    "reference": "/tmp/E27-I01_reference.st",
}

for p in sorted(Path("/tmp").glob("I-M*.st")):
    FILES[p.stem.split("_", 1)[0]] = str(p)

validator = SafetyInterlockValidator()
results = {}

for label, filepath in FILES.items():
    source = Path(filepath).read_text(encoding="utf-8")

    detected = validator.detect(
        signal_names=SIGNALS,
        source=source,
        plan_domain="Safety Interlock",
    )

    checks = validator.validate(
        source=source,
        signal_names=SIGNALS,
    )

    overall = all(c.status == "passed" for c in checks)

    results[label] = {
        "domain_detected": detected,
        "overall": "PASS" if overall else "DETECT",
        "rules": [
            {
                "id": c.id,
                "status": c.status,
                "description": c.description,
                "details": c.details,
            }
            for c in checks
        ],
    }

print("\n=== E27-I01 G2 SAFETY INTERLOCK VALIDATOR ===")

for label, result in results.items():
    print(f"\n{label.upper()}")
    print("Domain detected:", result["domain_detected"])
    print("Overall:", result["overall"])

    for rule in result["rules"]:
        print(f"{rule['id']}: {rule['status'].upper()} - {rule['description']}")
        if rule["details"]:
            print("   Details:", rule["details"])

Path("/tmp/E27-I01_G2_result.json").write_text(
    json.dumps(results, indent=2),
    encoding="utf-8",
)
