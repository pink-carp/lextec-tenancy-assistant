"""Code checks on AI-written text. Anything that fails is removed and listed, never silently shown."""
import re
from datetime import date

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]

# "ZPO Art. 145 Abs. 1" (our source-ID style: law first)
_ART_LAWFIRST = re.compile(r"\b(OR|ZPO|ZGB|VMWG|Samstagsgesetz)\s+Art\.?\s*(\d+[a-z]?)")
# "Art. 257d Abs. 1 OR", "Art 999", "Arts. 259g-259h OR", "Article 273(1) CO"
_ART = re.compile(r"\bArt(?:icles?|s)?\.?\s*(\d+[a-z]?)(?:\s*(?:[–-]|to|and)\s*(\d+[a-z]?))?(?:\s*(?:para\.?|Abs\.|\(\d+\))\s*\d*\)?)*\s*(OR|CO|ZPO|CPC|ZGB|CC|VMWG)?", re.I)
_DEC = re.compile(r"\b(?:BGE|ATF|DTF)\s+\d{2,3}\s+[IV]{1,3}\s+\d+|\b\d[A-Z]_\d+/\d{4}\b|\b(?:PD|LF|MG|NG|LB)\d{6}\b")
_ISO = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
_DMY = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(20\d\d)\b")
_DMONY = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d\d)\b", re.I)
_MONDY = re.compile(r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2}),?\s+(20\d\d)\b", re.I)

LAW_ALIASES = {"CO": "OR", "CPC": "ZPO", "CC": "ZGB"}


def sentences(text):
    # split only where the next sentence starts with a capital, so "Art. 257d" and "Abs. 1" stay whole
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ\"“(\[])", text.strip()) if s]


def mentioned_articles(text, default_law="OR"):
    out = set()
    for m in _ART_LAWFIRST.finditer(text):
        out.add(f"{m.group(1)} {m.group(2).lower()}")
    text = _ART_LAWFIRST.sub(" ", text)
    for m in _ART.finditer(text):
        law = LAW_ALIASES.get((m.group(3) or default_law).upper(), (m.group(3) or default_law).upper())
        out.add(f"{law} {m.group(1).lower()}")
        if m.group(2):
            out.add(f"{law} {m.group(2).lower()}")
    return out


def mentioned_decisions(text):
    return {re.sub(r"^(ATF|DTF)", "BGE", m.group(0)) for m in _DEC.finditer(text)}


def _safe_date(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:  # e.g. "31.02.2026" or a reference number that looks like a date
        return None


def mentioned_dates(text):
    found = []
    found += [_safe_date(y, m, d) for y, m, d in _ISO.findall(text)]
    found += [_safe_date(y, m, d) for d, m, y in _DMY.findall(text)]
    found += [_safe_date(y, MONTHS.index(mon.lower()) + 1, d) for d, mon, y in _DMONY.findall(text)]
    found += [_safe_date(y, MONTHS.index(mon.lower()) + 1, d) for mon, d, y in _MONDY.findall(text)]
    return {d for d in found if d}


def clean_text(text, allowed_articles, allowed_decisions, allowed_dates, where, removed):
    """Drop each sentence that names an article/decision outside the allowed set or a date
    that is not a computed deadline or a recorded fact. Record what was dropped and why."""
    keep = []
    for s in sentences(text or ""):
        bad_art = {a for a in mentioned_articles(s) if a not in allowed_articles}
        bad_dec = {d for d in mentioned_decisions(s) if not any(d in a or a in d for a in allowed_decisions)}
        bad_date = {d for d in mentioned_dates(s) if d not in allowed_dates}
        if bad_art or bad_dec or bad_date:
            why = []
            if bad_art:
                why.append("names law not among the sources used: " + ", ".join(sorted(bad_art)))
            if bad_dec:
                why.append("names a decision not among the sources used: " + ", ".join(sorted(bad_dec)))
            if bad_date:
                why.append("contains a date that is neither a computed deadline nor a recorded fact: "
                           + ", ".join(d.isoformat() for d in sorted(bad_date)))
            removed.append({"where": where, "sentence": s, "reason": "; ".join(why)})
        else:
            keep.append(s)
    return " ".join(keep)


def source_article(source_id: str):
    """'OR Art. 257d Abs. 1' -> 'OR 257d'"""
    m = re.match(r"(\w+) Art\. (\S+)", source_id)
    return f"{m.group(1)} {m.group(2)}" if m else None
