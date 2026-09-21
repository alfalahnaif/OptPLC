"""Reproducible literature search for R0-02 (systematic review, D-035).

Runs the query strings fixed in docs/research/related-work/SLR_PROTOCOL.md against
OpenAlex and the arXiv API, resolves the seed papers and collects the works that cite
them (forward snowballing), then deduplicates everything into one candidate list for
title/abstract screening.

Usage (from the repository root):
    python scripts/research/slr_search.py --out docs/research/related-work/search_<date>

Only the Python standard library is used. The system proxy is bypassed on purpose:
both APIs are reachable directly from this machine, while the Windows SOCKS proxy
breaks urllib (see D-027).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

USER_AGENT = "OptPLC-literature-review/0.1"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
CURL = shutil.which("curl") or "curl"

# Query strings are part of the protocol. Change them only with a logged deviation.
DOMAIN = ('("PLC" OR "programmable logic controller" OR "IEC 61131" OR "IEC 61131-3" OR '
          '"structured text" OR "ladder diagram" OR "ladder logic" OR "IEC 61499" OR "control logic")')
LLM = '("large language model" OR "large language models" OR "LLM" OR "LLMs" OR "GPT" OR "ChatGPT" OR "language model")'

OPENALEX_QUERIES = {
    "OA1_llm_plc": (f"{DOMAIN} AND {LLM}", "2021-01-01"),
    "OA2_plc_spec_adequacy": (
        '("PLC" OR "programmable logic controller" OR "IEC 61131") AND '
        '("mutation" OR "mutant" OR "specification coverage" OR "vacuity" OR "specification completeness" '
        'OR "requirements coverage") AND ("model checking" OR "formal verification" OR "specification" OR "property")',
        None,
    ),
    "OA3_llm_spec_adequacy": (
        f"{LLM} AND "
        '("formal specification" OR "formal specifications" OR "temporal logic" OR "LTL" OR "postcondition" '
        'OR "postconditions") AND ("completeness" OR "adequacy" OR "mutation" OR "mutant" OR "mutants" OR "vacuity")',
        "2022-01-01",
    ),
    "OA4_llm_nl_to_temporal_logic": (
        f"{LLM} AND "
        '("LTL" OR "linear temporal logic" OR "temporal logic" OR "signal temporal logic" OR "CTL") AND '
        '("requirement" OR "requirements") AND ("formalization" OR "formalisation" OR "translation" OR "generation")',
        "2022-01-01",
    ),
    "OA5_interactive_intent": (
        f"{LLM} AND "
        '("user intent" OR "intent formalization" OR "intent clarification" OR "specification") AND '
        '("disambiguation" OR "disambiguate" OR "clarification" OR "clarifying" OR "distinguishing") AND '
        '("test" OR "tests" OR "trace" OR "traces" OR "scenario" OR "scenarios" OR "example" OR "examples")',
        "2021-01-01",
    ),
    "OA6_plc_benchmark": (
        '("benchmark" OR "dataset") AND '
        '("PLC" OR "programmable logic controller" OR "IEC 61131" OR "structured text" OR "ladder logic") AND '
        '("code generation" OR "language model" OR "LLM" OR "formal verification" OR "model checking")',
        "2022-01-01",
    ),
}

ARXIV_QUERIES = {
    "AX1_llm_plc": (
        '(all:"IEC 61131" OR all:PLC OR all:"programmable logic controller" OR all:"structured text" '
        'OR all:"ladder logic" OR all:"ladder diagram") AND (all:LLM OR all:"large language model" OR all:"language models")'
    ),
    "AX2_llm_spec_adequacy": (
        '(all:LLM OR all:"large language model" OR all:"large language models") AND '
        '(all:"temporal logic" OR all:LTL OR all:"formal specification" OR all:postcondition OR all:postconditions) AND '
        '(all:completeness OR all:mutation OR all:mutants OR all:adequacy OR all:vacuity)'
    ),
    "AX3_intent_formalization": '(all:"intent formalization" OR all:"user intent formalization")',
}

# Seed papers for forward snowballing (works that cite them). DOIs as registered.
SEEDS = {
    "agents4plc_arxiv": "10.48550/arxiv.2410.14209",
    "llm4plc_icse_seip": "10.1145/3639477.3639743",
    "llm4plc_arxiv": "10.48550/arxiv.2401.05443",
    "nl2postcond_fse": "10.1145/3660791",
    "ticoder_arxiv": "10.48550/arxiv.2208.05950",
    "haag_st_feedback_arxiv": "10.48550/arxiv.2410.22159",
    "autoplc_arxiv": "10.48550/arxiv.2412.02410",
    "chockler_coverage_tacas01": "10.1007/3-540-45319-9_36",
    "stmutants_arxiv": "10.48550/arxiv.2606.05499",
    "esbmc_plcplus_arxiv": "10.48550/arxiv.2606.23870",
}
# Seeds with very many citations: keep only citing works that match these terms.
SEED_FILTER = {"chockler_coverage_tacas01": '("large language model" OR "LLM" OR "PLC" OR "IEC 61131")'}

OA_FIELDS = ("id,doi,title,publication_year,type,cited_by_count,primary_location,authorships,"
             "abstract_inverted_index,ids")


def fetch(url: str) -> bytes:
    # The arXiv API answers urllib with HTTP 406 but serves curl (seen 2026-09-21), so arXiv
    # goes through the curl executable. OpenAlex works with urllib.
    for attempt in range(4):
        try:
            if "arxiv.org" in url:
                done = subprocess.run(
                    [CURL, "-sS", "--fail", "--max-time", "90", "-A", USER_AGENT, url],
                    capture_output=True, check=True, env={**os.environ, "NO_PROXY": "*"})
                return done.stdout
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with OPENER.open(request, timeout=60) as response:
                return response.read()
        except Exception as error:  # noqa: BLE001 - retried, then re-raised
            if attempt == 3:
                raise
            print(f"  retry {attempt + 1} after {error}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


def abstract_from_index(index: dict | None) -> str:
    if not index:
        return ""
    positions = [(pos, word) for word, places in index.items() for pos in places]
    return " ".join(word for _, word in sorted(positions))


def openalex_record(work: dict, origin: str) -> dict:
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    ids = work.get("ids") or {}
    authors = [a.get("author", {}).get("display_name", "") for a in work.get("authorships", [])[:3]]
    return {
        "title": work.get("title") or "",
        "year": work.get("publication_year"),
        "venue": source.get("display_name") or "",
        "type": work.get("type") or "",
        "doi": (work.get("doi") or "").replace("https://doi.org/", "").lower(),
        "arxiv_id": "",
        "openalex_id": (work.get("id") or "").replace("https://openalex.org/", ""),
        "authors": "; ".join(authors),
        "cited_by": work.get("cited_by_count"),
        "abstract": abstract_from_index(work.get("abstract_inverted_index")),
        "origins": [origin],
        "pmid": ids.get("pmid", ""),
    }


def openalex_search(filter_expr: str, origin: str, cap: int = 2000) -> tuple[int, list[dict]]:
    records: list[dict] = []
    cursor, total = "*", 0
    while cursor and len(records) < cap:
        query = urllib.parse.urlencode(
            {"filter": filter_expr, "per-page": 200, "cursor": cursor, "select": OA_FIELDS})
        data = json.loads(fetch(f"https://api.openalex.org/works?{query}"))
        total = data["meta"]["count"]
        records += [openalex_record(work, origin) for work in data["results"]]
        cursor = data["meta"].get("next_cursor") if data["results"] else None
        time.sleep(0.2)
    return total, records


def arxiv_search(query: str, origin: str, cap: int = 1000) -> tuple[int, list[dict]]:
    ns = {"a": "http://www.w3.org/2005/Atom", "o": "http://a9.com/-/spec/opensearch/1.1/"}
    records: list[dict] = []
    start, total = 0, 0
    while start < cap:
        params = urllib.parse.urlencode(
            {"search_query": query, "start": start, "max_results": 200, "sortBy": "submittedDate"})
        root = ET.fromstring(fetch(f"https://export.arxiv.org/api/query?{params}"))
        total = int(root.find("o:totalResults", ns).text)
        entries = root.findall("a:entry", ns)
        for entry in entries:
            arxiv_id = re.sub(r"v\d+$", "", entry.find("a:id", ns).text.rsplit("/abs/", 1)[-1])
            authors = [a.find("a:name", ns).text for a in entry.findall("a:author", ns)[:3]]
            records.append({
                "title": " ".join(entry.find("a:title", ns).text.split()),
                "year": int(entry.find("a:published", ns).text[:4]),
                "venue": "arXiv",
                "type": "preprint",
                "doi": f"10.48550/arxiv.{arxiv_id}".lower(),
                "arxiv_id": arxiv_id,
                "openalex_id": "",
                "authors": "; ".join(authors),
                "cited_by": None,
                "abstract": " ".join(entry.find("a:summary", ns).text.split()),
                "origins": [origin],
                "pmid": "",
            })
        start += 200
        if not entries or start >= total:
            break
        time.sleep(3.5)  # arXiv asks for at least 3 seconds between calls
    return total, records


def resolve_seed(doi: str) -> str | None:
    try:
        work = json.loads(fetch(f"https://api.openalex.org/works/doi:{doi}?select=id,title"))
    except Exception as error:  # noqa: BLE001 - reported in the log
        print(f"  seed {doi} not resolved: {error}")
        return None
    return work["id"].replace("https://openalex.org/", "")


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def merge(records: list[dict]) -> list[dict]:
    """Deduplicate by DOI, then arXiv id, then normalized title. Origins are unioned."""
    merged: dict[str, dict] = {}
    alias: dict[str, str] = {}
    for record in records:
        keys = [k for k in (record["doi"], record["arxiv_id"] and f"arxiv:{record['arxiv_id']}",
                            f"title:{normalize_title(record['title'])}") if k]
        found = next((alias[k] for k in keys if k in alias), None)
        if found is None:
            found = keys[0]
            merged[found] = dict(record)
        else:
            kept = merged[found]
            kept["origins"] = sorted(set(kept["origins"]) | set(record["origins"]))
            for field in ("venue", "openalex_id", "arxiv_id", "abstract", "cited_by", "doi"):
                if not kept.get(field) and record.get(field):
                    kept[field] = record[field]
        for k in keys:
            alias[k] = found
    return list(merged.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log: dict = {"run_date": date.today().isoformat(), "queries": {}, "seeds": {}}
    everything: list[dict] = []

    for qid, (expr, since) in OPENALEX_QUERIES.items():
        filter_expr = f"title_and_abstract.search:{expr}"
        if since:
            filter_expr += f",from_publication_date:{since}"
        total, records = openalex_search(filter_expr, qid)
        print(f"{qid}: {total} hits, {len(records)} fetched")
        log["queries"][qid] = {"source": "openalex", "filter": filter_expr, "hits": total, "fetched": len(records)}
        everything += records

    for qid, expr in ARXIV_QUERIES.items():
        total, records = arxiv_search(expr, qid)
        print(f"{qid}: {total} hits, {len(records)} fetched")
        log["queries"][qid] = {"source": "arxiv", "search_query": expr, "hits": total, "fetched": len(records)}
        everything += records

    for name, doi in SEEDS.items():
        work_id = resolve_seed(doi)
        if not work_id:
            log["seeds"][name] = {"doi": doi, "resolved": None}
            continue
        filter_expr = f"cites:{work_id}"
        if name in SEED_FILTER:
            filter_expr += f",title_and_abstract.search:{SEED_FILTER[name]}"
        total, records = openalex_search(filter_expr, f"FWD_{name}")
        print(f"FWD_{name} ({work_id}): {total} citing, {len(records)} fetched")
        log["seeds"][name] = {"doi": doi, "resolved": work_id, "filter": filter_expr, "citing": total,
                              "fetched": len(records)}
        everything += records

    candidates = merge(everything)
    candidates.sort(key=lambda r: (-(r["year"] or 0), r["title"].lower()))
    log["records_before_dedup"] = len(everything)
    log["candidates_after_dedup"] = len(candidates)
    print(f"{len(everything)} records, {len(candidates)} after deduplication")

    (out / "search_log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8",
                                      newline="\n")
    with (out / "candidates.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for index, record in enumerate(candidates, 1):
            record["key"] = f"C{index:04d}"
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    with (out / "candidates.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["key", "year", "title", "venue", "type", "doi", "origins", "cited_by"])
        for record in candidates:
            writer.writerow([record["key"], record["year"], record["title"], record["venue"], record["type"],
                             record["doi"], "|".join(record["origins"]), record["cited_by"]])


if __name__ == "__main__":
    main()
