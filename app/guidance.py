"""The legal team's method documents, loaded verbatim for the prompts (with two agreed clean-ups)."""
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(name):
    return (ROOT / "legal-team-materials" / name).read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def legal_workflow():
    t = _read("legal-workflow.md")
    t = t.replace("\\[DR1\\]", "")
    t = re.sub(r"\n---\s*\n.*$", "", t, flags=re.S)  # leftover editor note "[DR1] ... chatgpt"
    # the team asked to ignore the unfinished last sentence
    t = re.sub(r"Remember, your job is to help the social worker ask the right questions to assess the situation that lead\s*$",
               "", t.strip())
    return t.strip()


@lru_cache(maxsize=None)
def escalation():
    return _read("escalation-indices.md").strip()


@lru_cache(maxsize=None)
def output_rules():
    return _read("output-specification.md").strip()


@lru_cache(maxsize=None)
def deadlines():
    return _read("deadline-calculation-rules.md").strip()


def section(text, start, end=None):
    """Cut a section of a markdown file between two headings (literal markers)."""
    i = text.find(start)
    if i < 0:
        raise KeyError(start)
    j = text.find(end, i + len(start)) if end else -1
    return text[i: j if j > 0 else None].strip()
