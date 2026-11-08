"""Download the court decisions cited in the team's example cases and deadlines.md
from the public OpenCaseLaw API (https://mcp.opencaselaw.ch/api/docs, data CC0).

Only case numbers are sent; no client data. Output: corpus/decisions/<id>.json
"""
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

API = "https://mcp.opencaselaw.ch/api"
HEADERS = {"User-Agent": "lextec-hackathon-prototype/0.1"}
OUT = Path(__file__).parent / "decisions"

CITED = [
    "BGE 119 II 147", "BGE 140 III 244", "BGE 138 III 615", "BGE 140 III 491", "BGE 142 III 557",
    "4A_333/2022", "4A_345/2007", "5A_691/2023",
    "PD190002", "PD140009", "LF190080", "MG170019",
]


def get(path, **params):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}" if params else f"{API}{path}"
    # curl, because Python's urllib reads were cut off at 20 KB behind the local proxy
    out = subprocess.run(["curl", "-sS", "-f", "-m", "60", "-A", HEADERS["User-Agent"], url],
                         capture_output=True, check=True)
    return json.loads(out.stdout)


def main():
    OUT.mkdir(exist_ok=True)
    report = []
    for ref in CITED:
        hits = get("/lookup", q=ref, limit=3)
        items = hits.get("results", hits) if isinstance(hits, dict) else hits
        if not items:  # Zurich docket numbers are not recognised by /lookup; use search, exact docket match only
            found = get("/decisions", q=ref, canton="ZH")
            found = found.get("results", found) if isinstance(found, dict) else found
            items = [x for x in (found or []) if x.get("docket_number") == ref]
        if not items:
            report.append((ref, "NOT FOUND", ""))
            continue
        top = items[0]
        did = top.get("decision_id") or top.get("id")
        full = get(f"/decisions/{urllib.parse.quote(did, safe='')}", full_text="true")
        fname = OUT / (ref.replace("/", "_").replace(" ", "_") + ".json")
        fname.write_text(json.dumps({"cited_as": ref, "lookup_top": top, "decision": full}, ensure_ascii=False, indent=1))
        txt = (full.get("full_text") or full.get("text") or "")
        report.append((ref, did, f"{len(txt.split())} words"))
        time.sleep(0.5)
    for r in report:
        print(" | ".join(r))


if __name__ == "__main__":
    sys.exit(main())
