"""Checks on the situation modules (corpus/modules/*.json): format, references, conditions, and the error patterns
found in the blind reviews of 2026-11-08. Run: .venv/bin/python -m pytest tests/test_modules.py"""
import re

import pytest

from app import corpus, events, modules

MODS = modules.load()
ITEMS = [(mid, kind, it) for mid, m in MODS.items() for kind in ("questions", "points", "actions") for it in m.get(kind) or []]
CTX = {"events": {}, "answers": {}, "deadlines": set(), "situations": set(), "docs": set()}


def test_modules_exist():
    assert len(MODS) >= 8


@pytest.mark.parametrize("mid,kind,it", ITEMS, ids=[f"{m}:{it['id']}" for m, _, it in ITEMS])
def test_item_format(mid, kind, it):
    assert it.get("id") and it.get("text")
    for pid in it.get("basis") or []:
        assert pid in corpus.by_id(), f"unknown paragraph {pid}"
    for atom in it.get("show_if") or []:
        modules.holds(atom, CTX)  # raises on an unknown atom
        m = re.match(r"(E\d+)", atom)
        if m:
            assert m.group(1) in events.events(), f"unknown event {m.group(1)}"
    if kind == "questions":
        assert it["input"] in ("date", "yes_no_unknown", "number", "short_text", "upload")
    if kind == "actions":
        assert it["who"] in ("client", "social_worker", "professional")
        assert it["group"] in ("referral", "immediate", "now", "needs_clarification")


@pytest.mark.parametrize("mid", list(MODS))
def test_triggers_and_question_refs(mid):
    m = MODS[mid]
    for t in m.get("triggers") or []:
        for a in t.split("&"):
            modules.holds(a, CTX | {"vuln": set()})
    qids = {q["id"] for mm in MODS.values() for q in mm.get("questions") or []}
    for kind in ("questions", "points", "actions"):
        for it in m.get(kind) or []:
            for atom in it.get("show_if") or []:
                q = re.match(r"q:(\w+)", atom)
                if q:
                    assert q.group(1) in qids, f"{it['id']} refers to unknown question {q.group(1)}"


# error patterns seen in the reviews (each pattern: regex that must NOT match, unless the allow-regex matches too)
BAD = [
    (r"\bwithh(o|e)ld", r"\b(not|never|no right|don't|do not|isn't|is not|cannot)\b"),
    (r"cohabit", None),
    (r"support animal|reasonable accommodation", None),
    (r"\b(immediately|without notice)\b.*\bterminat|\bterminat\w*\b.*\b(immediately|without notice)\b", r"\b(not|never)\b"),
    (r"\b(tenant|you)\s+(must|need|needs|should|has to|have to)\b[^.]*\b(official|approved|cantonal) form", r"\b(not|only the landlord|does not|don't|no need)\b"),
]


@pytest.mark.parametrize("mid,kind,it", ITEMS, ids=[f"{m}:{it['id']}" for m, _, it in ITEMS])
def test_known_error_patterns(mid, kind, it):
    for field in ("text", "client_text", "why"):
        t = (it.get(field) or "").lower()
        for bad, allow in BAD:
            if re.search(bad, t):
                assert allow and re.search(allow, t), f"{field} matches known error pattern '{bad}': {t}"
