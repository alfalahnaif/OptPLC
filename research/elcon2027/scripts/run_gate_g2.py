import json
from pathlib import Path

from app.agents.validation_agent import MotorControlValidator

SIGNALS = {
    "Start_PB",
    "Stop_PB",
    "E_Stop",
    "Reset_PB",
    "Overload",
    "Motor",
}

FILES = {
    "reference": "/tmp/reference.st",
}

for p in sorted(Path("/tmp").glob("M-M*.st")):
    label = p.stem.split("_", 1)[0]
    FILES[label] = str(p)

validator = MotorControlValidator()
results = {}

for label, filepath in FILES.items():
    source = Path(filepath).read_text(encoding="utf-8")

    detected = validator.detect(
        signal_names=SIGNALS,
        source=source,
        plan_domain="Motor Control",
    )

    checks = validator.validate(
        source=source,
        signal_names=SIGNALS,
    )

    result_rows = []
    for check in checks:
        result_rows.append({
            "id": check.id,
            "description": check.description,
            "status": check.status,
            "details": check.details,
        })

    overall_pass = all(c.status == "passed" for c in checks)

    results[label] = {
        "domain_detected": detected,
        "overall": "PASS" if overall_pass else "DETECT",
        "rules": result_rows,
    }

print("\n=== GATE G2 — MOTOR DOMAIN VALIDATOR ===")

for label, result in results.items():
    print(f"\n{label.upper()}")
    print(f"Domain detected: {result['domain_detected']}")
    print(f"Overall: {result['overall']}")

    for rule in result["rules"]:
        print(
            f"{rule['id']}: {rule['status'].upper()} "
            f"- {rule['description']}"
        )
        if rule["details"]:
            print(f"    Details: {rule['details']}")

Path("/tmp/E27-M01_G2_result.json").write_text(
    json.dumps(results, indent=2),
    encoding="utf-8",
)

print("\nSaved: /tmp/E27-M01_G2_result.json")
