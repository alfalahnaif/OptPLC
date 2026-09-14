"""Create a dated, verified backup of OptPLC runtime data (plan item P0-03).

Backs up the SQLite database through the sqlite3 online-backup API, copies the
benchmark result files, and writes a manifest with sizes, SHA-256 hashes, table
row counts, an integrity check, and a provenance label for every result file.

The database copy is verified on its logical content (a SHA-256 of the full SQL
dump) because the backup API rewrites the destination file header, so raw file
hashes are not expected to match. Result files are verified byte for byte.

Nothing inside the repository is modified and secrets (.env) are never copied.

Usage:
    python scripts/backup_runtime_data.py [--dest DIR]

Default destination: <repo>/../PLC_AI_backups/<UTC timestamp>/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "backend" / "plcforge.db"
RESULTS_DIR = REPO_ROOT / "backend" / "benchmark" / "results"

# Only test_one_failed_mode_does_not_stop_comparison submits a blank requirement.
BLANK_REQUIREMENT_ERROR = "Requirement text must not be empty."
TEST_BURST_WINDOW = timedelta(seconds=2)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def logical_sha256(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for statement in connection.iterdump():
        digest.update(statement.encode("utf-8") + b"\n")
    return digest.hexdigest()


def backup_database(dest: Path) -> dict:
    target = dest / DB_PATH.name
    source = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    copy = sqlite3.connect(target)
    try:
        source.backup(copy)
        page_size = source.execute("PRAGMA page_size").fetchone()[0]
        page_count = source.execute("PRAGMA page_count").fetchone()[0]
        freelist_pages = source.execute("PRAGMA freelist_count").fetchone()[0]
        source_logical = logical_sha256(source)
        backup_logical = logical_sha256(copy)
        integrity = copy.execute("PRAGMA integrity_check").fetchone()[0]
        tables = [row[0] for row in copy.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        row_counts = {name: copy.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in tables}
    finally:
        source.close()
        copy.close()

    if source_logical != backup_logical:
        raise RuntimeError("Logical content of the backup differs from the source database.")
    if integrity != "ok":
        raise RuntimeError(f"Backup failed PRAGMA integrity_check: {integrity}")

    return {
        "source": str(DB_PATH),
        "backup": str(target),
        "method": "sqlite3 online backup API (read-only source)",
        "source_bytes": DB_PATH.stat().st_size,
        "backup_bytes": target.stat().st_size,
        "source_sha256": sha256(DB_PATH),
        "backup_sha256": sha256(target),
        "byte_hash_note": "Raw hashes may differ: the backup API rewrites the destination header (change counter).",
        "source_logical_sha256": source_logical,
        "backup_logical_sha256": backup_logical,
        "logical_content_identical": True,
        "integrity_check": integrity,
        "page_size": page_size,
        "page_count": page_count,
        "freelist_pages": freelist_pages,
        "free_bytes": freelist_pages * page_size,
        "row_counts": row_counts,
    }


def _stamp(path: Path) -> datetime | None:
    raw = path.stem.rsplit("_", 1)[-1]
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def backup_results(dest: Path) -> list[dict]:
    target_dir = dest / "benchmark_results"
    target_dir.mkdir()
    files = sorted(RESULTS_DIR.glob("*.json")) if RESULTS_DIR.exists() else []
    payloads = {path: json.loads(path.read_text(encoding="utf-8")) for path in files}
    blank_stamps = [_stamp(path) for path, data in payloads.items() if data.get("error") == BLANK_REQUIREMENT_ERROR]

    entries: list[dict] = []
    for path, data in payloads.items():
        stamp = _stamp(path)
        if data.get("error") == BLANK_REQUIREMENT_ERROR:
            provenance = "test_artifact"
            reason = "blank-requirement error is produced only by test_benchmarks.py"
        elif stamp and any(other and abs(stamp - other) <= TEST_BURST_WINDOW for other in blank_stamps):
            provenance = "probable_test_artifact"
            reason = "written within 2 s of a confirmed test artifact (pytest burst)"
        else:
            provenance = "unknown_origin"
            reason = "no test signature; may be a manual run"

        copied = target_dir / path.name
        shutil.copy2(path, copied)
        source_hash = sha256(path)
        if sha256(copied) != source_hash:
            raise RuntimeError(f"Hash mismatch after copying {path.name}")

        entries.append({
            "file": path.name,
            "bytes": path.stat().st_size,
            "sha256": source_hash,
            "mode": data.get("mode"),
            "verified": data.get("verified"),
            "validationStatus": data.get("validationStatus"),
            "error": data.get("error"),
            "provenance": provenance,
            "provenance_reason": reason,
            "valid_experimental_evidence": False,
        })
    return entries


RESTORE_NOTE = """OptPLC runtime backup

Restore the database (stop the backend first):
    copy plcforge.db  <repo>/backend/plcforge.db

Restore benchmark results:
    copy benchmark_results/*.json  <repo>/backend/benchmark/results/

See backup_manifest.json for hashes, row counts and the provenance of every
result file. No result file in this backup is valid experimental evidence.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dest", type=Path, help="Backup directory (must not exist and must be outside the repo).")
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).replace(microsecond=0)
    dest = (args.dest or REPO_ROOT.parent / "PLC_AI_backups" / created_at.strftime("%Y%m%dT%H%M%SZ")).resolve()
    if dest == REPO_ROOT or REPO_ROOT in dest.parents:
        raise SystemExit(f"Refusing to write a backup inside the repository: {dest}")
    if dest.exists():
        raise SystemExit(f"Refusing to overwrite an existing backup directory: {dest}")
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    dest.mkdir(parents=True)
    manifest = {
        "created_at": created_at.isoformat(),
        "plan_item": "P0-03",
        "repo_root": str(REPO_ROOT),
        "excluded": ["backend/.env (secrets)", "rag_db/ (regenerable cache)"],
        "database": backup_database(dest),
        "benchmark_results": backup_results(dest),
    }
    (dest / "backup_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (dest / "README.txt").write_text(RESTORE_NOTE, encoding="utf-8")

    database = manifest["database"]
    labels: dict[str, int] = {}
    for entry in manifest["benchmark_results"]:
        labels[entry["provenance"]] = labels.get(entry["provenance"], 0) + 1
    print(f"Backup written to: {dest}")
    print(
        f"Database: {database['backup_bytes']} bytes, integrity={database['integrity_check']}, "
        f"logical_identical={database['logical_content_identical']}, rows={database['row_counts']}, "
        f"free_pages={database['freelist_pages']}/{database['page_count']} ({database['free_bytes']} bytes)"
    )
    print(f"Benchmark results: {len(manifest['benchmark_results'])} files, provenance={labels}")


if __name__ == "__main__":
    main()
