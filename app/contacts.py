"""Choose contacts from the legal team's resources.md (structured in data/resources.json) by rule.
Contact details are never written by the AI; they are copied from the file."""
import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "resources.json"

CITY_ZURICH = {"zürich", "zurich", "zuerich"}


@lru_cache(maxsize=1)
def resources():
    return json.loads(DATA.read_text(encoding="utf-8"))["entries"]


def _place(municipality: str) -> str:
    m = (municipality or "").strip().lower()
    if not m:
        return "unknown"
    if any(m.startswith(c) for c in CITY_ZURICH):
        return "city_zurich"
    if m.startswith("winterthur"):
        return "winterthur"
    return "canton_zurich"


def _geo_ok(entry_geo: str, place: str) -> bool:
    if entry_geo in ("switzerland", "canton_zurich"):
        return True
    if place == "unknown":
        return True  # shown, with the geography note, for the social worker to check
    return entry_geo == place


def _audience_ok(e, gender):
    """Women-only services are left out when the description clearly says the client is a man."""
    aud = (e.get("audience") or "").lower()
    return not ("women" in aud and gender == "male")


def select(lane: int, levels: dict, topics: list, municipality: str, immediate_danger: bool, gender: str = "unknown"):
    """Return a list of {entry, reason} in a fixed order."""
    place = _place(municipality)
    chosen, out = set(), []

    def add(e, reason):
        if not _audience_ok(e, gender):
            return
        if (e.get("audience") or "").lower().find("women") >= 0 and gender == "unknown":
            reason += " (service for women)"
        if e["id"] not in chosen:
            chosen.add(e["id"])
            out.append({"id": e["id"], "reason_rule": reason, **e})

    by_id = {e["id"]: e for e in resources()}
    if immediate_danger:
        for k in ("emergency_117_police", "emergency_142_victim_support"):
            add(by_id[k], "Immediate danger was indicated")
    # tenancy-law advice whenever a human should look at the case or a deadline may run
    if lane >= 2 or levels.get("urgency") != "low" or levels.get("complexity") != "low":
        for e in resources():
            if "tenancy_legal" in e["topics"] and _geo_ok(e["geography"], place):
                add(e, "Tenancy-law advice (lane, urgency or complexity)")
    topic_map = {
        "debt": "debt", "domestic_violence": "domestic_violence", "sexual_violence": "sexual_violence",
        "asylum_migration": "asylum_migration", "disability": "disability", "children_youth": "children_youth",
        "trafficking_exploitation": "trafficking_exploitation", "isolation_stress": "peer_support",
        "financial_hardship": "social_counselling", "language_barrier": "multilingual",
    }
    for t in topics:
        tag = topic_map.get(t)
        if not tag:
            continue
        for e in resources():
            if e["kind"] == "organisation" and tag in e["topics"] and _geo_ok(e["geography"], place):
                add(e, f"Topic identified in the case: {t.replace('_', ' ')}")
    return out[:7]
