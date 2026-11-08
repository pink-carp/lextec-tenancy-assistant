"""Build bench/cases.json from the legal team's 9 example cases (legal-team-materials/example-cases/case-1.md to case-9.md).

Source files are read-only. All judgement calls are encoded in the SPEC dict below.
Markdown clean-up applied to extracted strings: remove ** / * emphasis markers and backslash
escapes (e.g. '\\!', '\\-', '4A\\_333'); wording is otherwise untouched.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "legal-team-materials" / "example-cases"
CORPUS = ROOT / "corpus" / "law_paragraphs.jsonl"
OUT = HERE / "cases.json"

# Per-case rules (line numbers are 1-based, inclusive, into the source file).
#  prompt    : (first, last) lines holding the client's own words. Chosen by hand because the
#              files have no uniform marker (case 2 has the client quote on one italic line
#              after a team-written intro line; cases 1 and 3 have several paragraphs).
#  lane      : expected lane / acceptable lanes / note (title text is ambiguous in cases 1,3,7,9).
#  questions : list of (first, last, kind, col). kind "list" = top-level bullet/numbered items,
#              kind "table" = markdown table body rows, col = column index used as the question text.
SPEC = {
    1: dict(prompt=(3, 7), lane=2, acc=[2],
            note="Header says 'lane 1 or 2' but the team's answer assigns Lane 2 -> expected 2; Lane 1 not listed as acceptable.",
            questions=[]),  # case 1 has no follow-up question list (only an 'Unknown:' fact list, not questions)
    2: dict(prompt=(5, 5), lane=3, acc=[3], note="",
            questions=[(21, 21, "list", 0), (24, 25, "list", 0), (53, 60, "table", 1)]),
    3: dict(prompt=(3, 7), lane=2, acc=[2],
            note="Title: 'should be lane 2'; the team itself calls it a borderline call (same legal stage as Case 2 but Lane 2: funds expected, no children, no deadline evident). Acceptable [2] only.",
            questions=[(34, 38, "list", 0), (83, 86, "list", 0), (90, 94, "list", 0)]),
    4: dict(prompt=(3, 3), lane=2, acc=[2], note="",
            questions=[(7, 9, "list", 0)]),
    5: dict(prompt=(3, 3), lane=2, acc=[2],
            note="Title: 'should be lane 2 but depends on information given, maybe mention mental support organisation'.",
            questions=[(7, 9, "list", 0), (14, 20, "table", 0)]),
    6: dict(prompt=(3, 3), lane=3, acc=[3], note="",
            questions=[(7, 7, "list", 0), (36, 40, "list", 0), (44, 48, "list", 0), (52, 53, "list", 0)]),
    7: dict(prompt=(3, 3), lane=2, acc=[2, 3],
            note="Title: 'probably lane 2, if landlord doesn't react reevaluation probably to lane 3' -> expected 2; acceptable alternative: 3.",
            questions=[(7, 8, "list", 0), (70, 75, "table", 0)]),
    8: dict(prompt=(3, 3), lane=3, acc=[3], note="",
            questions=[(7, 9, "list", 0), (37, 42, "table", 1), (50, 55, "table", 0)]),
    9: dict(prompt=(3, 3), lane=2, acc=[2],
            note="Title says lane 2; the team text ends 'Lane recommendation: B with escalation tripwires' (Route B = Lane 2, moved from an earlier Route C = Lane 3), with triggers that flip to C/Lane 3 (Art. 257d demand or termination notice).",
            questions=[(7, 11, "list", 0)]),
}

LAWS = "OR|ZPO|ZGB|VMWG"


def clean(s):
    s = re.sub(r"\\(.)", r"\1", s)
    s = s.replace("**", "")
    s = re.sub(r"(?<!\w)\*|\*(?!\w)", "", s)  # emphasis asterisks
    return re.sub(r"[ \t]+", " ", s).strip()


def load_corpus():
    arts = {}
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        arts.setdefault(d["law"], set()).add(d["article"])
    return arts


def suffix_key(a):
    m = re.fullmatch(r"(\d+)([a-z]*)", a)
    return int(m.group(1)), m.group(2)


def expand_range(a, b, law, corpus):
    na, sa = suffix_key(a)
    nb, sb = suffix_key(b)
    cands = [f"{n}{s}" for n in range(na, nb + 1) for s in [""] + list("abcdefghijklmnopqrstuvwxyz")]
    cands = [c for c in cands if (suffix_key(c) >= (na, sa)) and suffix_key(c) <= (nb, sb)]
    got = [c for c in cands if c in corpus.get(law, set())]
    return got or [a, b]


HEADER = re.compile(r"\b(?:Arts?\.|Articles?)\s+")
BODY_LAW = re.compile(
    r"(?P<body>(?:\d|[a-z]|\(|\)|\s|,|–|-|&|Arts?\.)*?)\s*(?:Swiss [A-Za-z ]+?\(|\()?(?P<law>%s)\b" % LAWS)


def extract_articles(text, corpus):
    found = []
    for h in HEADER.finditer(text):
        m = BODY_LAW.match(text, h.end())
        if not m:
            continue
        law, body = m.group("law"), m.group("body")
        body = re.sub(r"Arts?\.", " ", body)
        body = re.sub(r"(\(\w{1,2}\))+", "", body)  # drop paragraph / lit. parentheticals
        for r in re.finditer(r"(\d+[a-z]*)\s*[–-]\s*(\d+[a-z]*)", body):
            found += [(law, x) for x in expand_range(r.group(1), r.group(2), law, corpus)]
        body = re.sub(r"(\d+[a-z]*)\s*[–-]\s*(\d+[a-z]*)", " ", body)
        for t in re.finditer(r"\b\d+[a-z]{0,2}\b", body):
            found.append((law, t.group(0)))
    out = []
    for law, a in found:
        k = f"{law} {a}"
        if k not in out:
            out.append(k)
    return out


DECISION = re.compile(
    r"\bBGE\s+\d+\s+[IV]+[a-z]?\s+\d+\b|\b\d[A-Z]_\d+/\d{4}\b|\b(?:PD|MG|LF|RT|RU|NG|UE|LB|PP|ZR)\d{6}\b")


def extract_decisions(text):
    out = []
    for m in DECISION.finditer(text):
        d = re.sub(r"\s+", " ", m.group(0))
        if d not in out:
            out.append(d)
    return out


def extract_questions(lines, rules):
    qs = []
    for first, last, kind, col in rules:
        for ln in range(first, last + 1):
            raw = lines[ln - 1]
            if kind == "list":
                m = re.match(r"^(?:[-*]|\d+\.)\s+(.*\S)", raw)
                if m:  # indented sub-bullets do not match (they start with spaces)
                    qs.append({"text": clean(m.group(1)), "source": "list", "line": ln})
            else:
                if raw.startswith("|") and not re.match(r"^\|\s*-", raw):
                    cells = [c.strip() for c in raw.strip().strip("|").split("|")]
                    qs.append({"text": clean(cells[col]), "source": "table", "line": ln})
    return qs


DEADLINE = re.compile(
    r"deadline|\b\d+\s*days?\b|\b\d+\s*hours?\b|one-year|one year|seven-day|within a few|"
    r"mid-2027|end of November|early December|few weeks|\bperiod\b|retrospective", re.I)


def deadline_facts(team):
    out = []
    for line in team.splitlines():
        line = re.sub(r"^\s*(?:#+|[-*]|\d+\.)\s*", "", line)
        for cell in line.split("|"):  # table cells are separate snippets
            for s in re.split(r"(?<=[.!?])\s+(?=[A-Z*(])", cell):
                s = clean(s)
                if DEADLINE.search(s) and s not in out and len(s) < 400:
                    out.append(s)
    return out


def main():
    corpus = load_corpus()
    cases = []
    for n in range(1, 10):
        fname = f"case-{n}.md"
        lines = (SRC / fname).read_text(encoding="utf-8").splitlines()
        sp = SPEC[n]
        a, b = sp["prompt"]
        prompt = clean("\n".join(lines[a - 1:b]))
        prompt = re.sub(r"\n{3,}", "\n\n", prompt)
        if n == 2:  # client quote is wrapped in italic asterisks + curly quotes
            prompt = prompt.strip("“”\" ")
        team = "\n".join(lines[b:])
        arts = extract_articles(team, corpus)
        missing = [x for x in arts if x.split()[1] not in corpus.get(x.split()[0], set())]
        cases.append({
            "case_no": n,
            "file": fname,
            "prompt": prompt,
            "expected_lane": sp["lane"],
            "expected_lane_raw": clean(lines[0]),
            "expected_lane_note": sp["note"],
            "acceptable_lanes": sp["acc"],
            "gold_articles": arts,
            "gold_articles_missing_in_corpus": missing,
            "gold_decisions": extract_decisions(re.sub(r"\\(.)", r"\1", team)),  # unescape 4A\_333
            "gold_questions": extract_questions(lines, sp["questions"]),
            "deadline_facts": deadline_facts(team),
        })
    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
