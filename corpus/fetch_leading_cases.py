"""Pre-fetch the most-cited leading decisions for every tenancy article (OR 253-274g)
and the key ZPO procedure articles, from the public OpenCaseLaw API (data CC0).

Only article numbers are sent; no client data.
Output: corpus/decisions/<decision_id>.json and corpus/leading_cases_index.json
        (article -> ranked list of decision ids with regeste)
"""
import json
import re
from pathlib import Path

from fetch_decisions import OUT, get

HERE = Path(__file__).parent
TOP_N = 5

ZPO_ARTICLES = ["137", "138", "142", "143", "145", "146", "148", "197", "198", "200", "201", "202",
                "209", "210", "211", "212", "243", "257"]


def tenancy_articles():
    seen = []
    for line in open(HERE / "law_paragraphs.jsonl", encoding="utf-8"):
        r = json.loads(line)
        m = re.match(r"(\d+)", r["article"])
        if r["law"] == "OR" and m and 253 <= int(m.group(1)) <= 274 and r["article"] not in seen:
            seen.append(r["article"])
    return seen


def main():
    OUT.mkdir(exist_ok=True)
    index = {}
    targets = [("OR", a) for a in tenancy_articles()] + [("ZPO", a) for a in ZPO_ARTICLES]
    for law, art in targets:
        res = get("/leading-cases", law_code=law, article=art, limit=TOP_N)
        rows = res.get("results", [])
        index[f"{law} Art. {art}"] = [
            {"decision_id": x["decision_id"], "date": x.get("decision_date"),
             "citation_count": x.get("citation_count"), "regeste": (x.get("regeste") or "")[:600]}
            for x in rows
        ]
        for x in rows:
            did = x["decision_id"]
            f = OUT / (re.sub(r"[^\w.-]", "_", did) + ".json")
            if f.exists():
                continue
            full = get(f"/decisions/{did.replace(' ', '%20')}", full_text="true")
            f.write_text(json.dumps({"decision_id": did, "decision": full}, ensure_ascii=False, indent=1))
        print(f"{law} Art. {art}: {len(rows)}", flush=True)
    (HERE / "leading_cases_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1))
    print("done:", len(index), "articles,", len(list(OUT.glob("*.json"))), "decision files")


if __name__ == "__main__":
    main()
