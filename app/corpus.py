"""Local legal corpus: statute paragraphs, cross-references, court decisions, commentary.

All retrieval rules live here in code, so the same input always retrieves the same sources.
"""
import glob
import json
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"

# Scope rule: residential lease only, so the Pacht provisions (OR 275-304) are never pulled in automatically.
PACHT = range(275, 305)

# Parts of other laws the AI may pick from (shown as a table of contents, fetched in full on demand).
TOC_RANGES = {
    "OR": [(1, 183), (530, 551)],   # general part (formation, performance, time limits, limitation, joint debts); simple partnership
    "ZPO": [(1, 408)],              # civil procedure, whole code
    "ZGB": [(1, 10), (159, 180), (276, 295)],  # general rules, effects of marriage (incl. family home Art. 169), parental maintenance
    "VMWG": [(1, 30)],              # tenancy ordinance, whole
    "Samstagsgesetz": [(1, 2)],
}


def art_num(article: str) -> int:
    m = re.match(r"(\d+)", article)
    return int(m.group(1)) if m else -1


def article_key(law: str, article: str) -> str:
    return f"{law} {article}"   # e.g. "OR 257d" (article level)


@lru_cache(maxsize=1)
def paragraphs():
    return [json.loads(l) for l in open(CORPUS / "law_paragraphs.jsonl", encoding="utf-8")]


@lru_cache(maxsize=1)
def by_id():
    return {p["id"]: p for p in paragraphs()}


@lru_cache(maxsize=1)
def by_article():
    out = defaultdict(list)
    for p in paragraphs():
        out[article_key(p["law"], p["article"])].append(p)
    return dict(out)


def is_tenancy(p) -> bool:
    return p["law"] == "OR" and 253 <= art_num(p["article"]) <= 274


def tenancy_paragraphs():
    return [p for p in paragraphs() if is_tenancy(p)]


def tenancy_text() -> str:
    """The full residential-tenancy law (OR 253-274g), one line per paragraph with its citation ID."""
    return "\n".join(f"[{p['id']}] {p['text']}" for p in tenancy_paragraphs())


@lru_cache(maxsize=1)
def toc_articles():
    """Article-level keys outside the tenancy chapter that the AI may choose from."""
    keys, lines = [], []
    seen = set()
    for p in paragraphs():
        ranges = TOC_RANGES.get(p["law"], [])
        n = art_num(p["article"])
        if not any(a <= n <= b for a, b in ranges) or is_tenancy(p):
            continue
        k = article_key(p["law"], p["article"])
        if k in seen:
            continue
        seen.add(k)
        keys.append(k)
        head = (p["headings"][-1] if p["headings"] else p["text"][:70]).strip()
        lines.append(f"{k}: {head}")
    return keys, "\n".join(lines)


def tenancy_article_keys():
    seen = []
    for p in tenancy_paragraphs():
        k = article_key(p["law"], p["article"])
        if k not in seen:
            seen.append(k)
    return seen


def all_article_keys():
    return tenancy_article_keys() + toc_articles()[0]


# ---------------------------------------------------------------- cross-references

_REF = re.compile(
    r"Art(?:\.|ikel|ikeln)\s*(\d+[a-z]?)(?:\s*(?:Abs\.|Absatz)\s*\d+)?(?:\s*(?:lit\.|Bst\.)\s*[a-z])?"
    r"(?:\s*(?:[–-]|bis)\s*(\d+[a-z]?))?(?:\s+(OR|ZGB|ZPO|SchKG))?")


def _expand_range(law, a, b):
    """'266l'-'266o' -> all existing articles in between (same law)."""
    keys = list(by_article().keys())
    start, end = article_key(law, a), article_key(law, b)
    if start in keys and end in keys:
        i, j = keys.index(start), keys.index(end)
        if i <= j:
            return keys[i:j + 1]
    return [start, end]


@lru_cache(maxsize=1)
def reference_graph():
    """forward[k] = articles k refers to; backward[k] = articles referring to k (article level)."""
    fwd, bwd = defaultdict(set), defaultdict(set)
    arts = by_article()
    for p in paragraphs():
        src = article_key(p["law"], p["article"])
        for m in _REF.finditer(p["text"]):
            law = m.group(3) or p["law"]
            targets = _expand_range(law, m.group(1), m.group(2)) if m.group(2) else [article_key(law, m.group(1))]
            for t in targets:
                if t in arts and t != src:
                    fwd[src].add(t)
                    bwd[t].add(src)
    return fwd, bwd


def _in_scope(key: str) -> bool:
    law, art = key.split(" ", 1)
    return not (law == "OR" and art_num(art) in PACHT)


@lru_cache(maxsize=1)
def subsection_groups():
    """Articles under the same lettered sub-heading group ("6. Hinterlegung: a. Grundsatz /
    b. Herausgabe / c. Verfahren") belong together."""
    groups = defaultdict(list)
    for k, ps in by_article().items():
        h = ps[0]["headings"]
        if len(h) >= 2 and re.match(r"^[a-z]\.\s", h[-1]):
            g = (ps[0]["law"],) + tuple(h[:-1])
            if k not in groups[g]:
                groups[g].append(k)
    member = {}
    for g, ks in groups.items():
        for k in ks:
            member[k] = ks
    return member


def expand_articles(selected):
    """Add related articles by code: articles that refer to a selected one (often exceptions,
    e.g. 257d -> 272a), articles a selected one refers to, articles under the same lettered
    sub-heading (259g -> 259h, 259i), and the lettered articles that follow an unlettered one
    (272 -> 272a-272d). Returns (ordered list, reasons)."""
    fwd, bwd = reference_graph()
    groups = subsection_groups()
    keys = list(by_article().keys())
    out, reasons = [], {}

    def add(k, why):
        if k in by_article() and _in_scope(k) and k not in out:
            out.append(k)
            reasons[k] = why

    for k in selected:
        add(k, "chosen by the AI")
    for k in list(selected):
        for r in sorted(bwd.get(k, ())):
            add(r, f"refers to {k}")
        for r in sorted(fwd.get(k, ())):
            add(r, f"referred to by {k}")
        for r in groups.get(k, ()):
            add(r, f"same sub-section as {k}")
        law, art = k.split(" ", 1)
        if art.isdigit() and k in keys:
            i = keys.index(k) + 1
            while i < len(keys) and keys[i].startswith(f"{law} {art}") and keys[i] != k and re.fullmatch(rf"{art}[a-z]", keys[i].split(" ", 1)[1]):
                add(keys[i], f"lettered article following {k}")
                i += 1
    return out, reasons


def paragraphs_for(article_keys):
    out = []
    for k in article_keys:
        out.extend(by_article().get(k, []))
    return out


# ---------------------------------------------------------------- BM25 (small, local)

_WORD = re.compile(r"[a-zäöüßéèàç0-9]+")
_STOP = set("der die das und oder in im ist sind ein eine einer eines des dem den zu zur zum von mit auf für bei als nicht sich es wird werden wurde auch nach an aus so dass wenn sie er hat haben kann können sein".split())


def tokens(text):
    return [w[:7] for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]


def bm25_rank(query, docs, k1=1.5, b=0.75):
    """Return indices of docs sorted by BM25 score for the query (best first) and the scores."""
    toks = [tokens(d) for d in docs]
    n = len(docs)
    if n == 0:
        return [], []
    avg = sum(len(t) for t in toks) / n or 1
    df = Counter(w for t in toks for w in set(t))
    q = tokens(query)
    scores = []
    for t in toks:
        tf = Counter(t)
        s = 0.0
        for w in q:
            if w in tf:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(t) / avg))
        scores.append(s)
    order = sorted(range(n), key=lambda i: -scores[i])
    return order, scores


# ---------------------------------------------------------------- court decisions

def decision_label(did: str) -> str:
    if did.startswith("bge_"):
        return "BGE " + did[4:]
    if did.startswith("bger_"):
        p = did[5:].split("_")
        return f"BGer {p[0]}_{p[1]}/{p[2]}" if len(p) == 3 else "BGer " + did[5:]
    m = re.match(r"zh_(obergericht|mietgericht|handelsgericht)_(.+)", did)
    if m:
        court = {"obergericht": "OGer ZH", "mietgericht": "MietGer ZH", "handelsgericht": "HGer ZH"}[m.group(1)]
        return f"{court} {m.group(2)}"
    return did


_STAT = re.compile(r"Art\.\s*(\d+[a-z]?)(?:\s*Abs\.\s*\d+)?\s+(OR|ZPO|ZGB)\b")


@lru_cache(maxsize=1)
def decisions():
    out = {}
    for f in glob.glob(str(CORPUS / "decisions" / "*.json")):
        d = json.load(open(f, encoding="utf-8"))["decision"]
        did = d["decision_id"]
        text = d.get("full_text") or ""
        statutes = set()
        for m in _STAT.finditer(str(d.get("statutes") or "") + "\n" + text[:20000]):
            statutes.add(article_key(m.group(2), m.group(1)))
        out[did] = {
            "id": decision_label(did), "decision_id": did, "date": d.get("decision_date"),
            "court": d.get("court_name") or d.get("court"), "language": d.get("language"),
            "regeste": re.sub(r"\s+", " ", (d.get("regeste") or "").replace("Regeste", "")).strip(),
            "text": text, "statutes": statutes,
            "citations": int(d.get("citation_count") or 0),
            "url": d.get("canonical_url") or f"https://mcp.opencaselaw.ch/entscheid/{did}",
        }
    return out


@lru_cache(maxsize=1)
def decisions_by_article():
    idx = defaultdict(set)
    lead = json.load(open(CORPUS / "leading_cases_index.json", encoding="utf-8"))
    for key, rows in lead.items():
        law, art = key.split(" Art. ")
        for r in rows:
            idx[article_key(law, art)].add(r["decision_id"])
    for did, d in decisions().items():
        for k in d["statutes"]:
            idx[k].add(did)
    return idx


def _passages(text, size=900):
    """Split a decision into ~size-character passages along line breaks."""
    out, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) > size and cur:
            out.append(cur.strip())
            cur = ""
        cur += line + " "
    if cur.strip():
        out.append(cur.strip())
    return out


def relevant_decisions(article_keys, query, k=6):
    """Pick decisions for the chosen articles: score = articles covered x log(citations) x keyword match.
    Return each with its head-note and the best-matching passage."""
    cand = Counter()
    for a in article_keys:
        for did in decisions_by_article().get(a, ()):
            cand[did] += 1
    decs = decisions()
    scored = []
    for did, n_art in cand.items():
        d = decs.get(did)
        if not d or not d["text"]:
            continue
        kw = bm25_rank(query, [d["regeste"] + " " + d["text"][:6000]])[1][0] if query else 0
        scored.append((n_art * (1 + math.log1p(d["citations"])) * (1 + kw), did))
    scored.sort(reverse=True)
    out = []
    for _, did in scored[:k]:
        d = decs[did]
        ps = _passages(d["text"])
        order, scores = bm25_rank(query + " " + " ".join(article_keys), ps)
        best = ps[order[0]] if order else ""
        out.append({"id": d["id"], "decision_id": did, "date": d["date"], "court": d["court"],
                    "regeste": d["regeste"][:700], "passage": best[:900], "url": d["url"]})
    return out


# ---------------------------------------------------------------- commentary (team-supplied, copyrighted)

COMMENTARY_DIR = ROOT / "case 1 - legal commentary"


@lru_cache(maxsize=1)
def commentary_chunks():
    """Text chunks of the team's commentary PDFs, keyed by the OR article in the file name.
    Used as background only; the service cites the legal source the commentary names."""
    cache = CORPUS / "commentary_chunks.jsonl"
    if cache.exists():
        return [json.loads(l) for l in open(cache, encoding="utf-8")]
    if not COMMENTARY_DIR.exists():
        return []
    import pdfplumber
    rows = []
    for f in sorted(COMMENTARY_DIR.glob("*.pdf")):
        arts = re.findall(r"Art\. (\d+[a-z]?)(?:-([a-z]))?", f.name)
        if not arts:
            continue  # court decisions in the folder are covered by the decision corpus
        a, upto = arts[0]
        covered = [a] if not upto else [a[:-1] + chr(c) for c in range(ord(a[-1]), ord(upto) + 1)]
        with pdfplumber.open(f) as pdf:
            text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
        text = re.sub(r"-\n(?=[a-zäöü])", "", text)
        text = "\n".join(l for l in text.split("\n") if not re.match(r"^\s*(\d+|Ausdruckseite.*|©.*)\s*$", l))
        source = f.stem
        for i, chunk in enumerate(_passages(text, 1200)):
            rows.append({"source": source, "articles": [f"OR {x}" for x in covered], "n": i, "text": chunk})
    with open(cache, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


def relevant_commentary(article_keys, query, k=3):
    rows = [r for r in commentary_chunks() if set(r["articles"]) & set(article_keys)]
    if not rows:
        return []
    order, _ = bm25_rank(query + " " + " ".join(article_keys), [r["text"] for r in rows])
    return [rows[i] for i in order[:k]]
