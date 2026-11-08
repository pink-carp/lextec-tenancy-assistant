#!/usr/bin/env python3
"""Parse ../resources.md (legal team referral list) into data/resources.json.

Run: python3 build_resources.py
All tagging is defined explicitly in TAGS / EMERGENCY below (each with a comment quoting the
source text that justifies it). Everything else is extracted by fixed rules from the markdown.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "legal-team-materials" / "social-service-contacts.md"
OUT = HERE / "data" / "resources.json"
SOURCE_NOTE = ("resources.md (legal team), contact details to be verified by the social worker "
               "before passing on")

SECTIONS = {  # heading number -> section id
    "1": "legal_urgency", "2": "severity", "3": "vulnerability", "4": "complexity",
}
TOPICS = {"asylum_migration", "tenancy_legal", "legal_general", "debt", "social_counselling",
          "disability", "domestic_violence", "sexual_violence", "trafficking_exploitation",
          "children_youth", "peer_support", "multilingual"}
GEOS = {"city_zurich", "canton_zurich", "winterthur", "switzerland"}

# id: (name prefix as in source, topics, geography, audience)
# Where the source does not state the geographic scope, "canton_zurich" is used (broadest Zurich
# value, so city residents still match) and the case is flagged in the report.
TAGS = {
    # "provides legal advice to people seeking protection in Switzerland"
    "asylex": ("AsyLex", ["asylum_migration", "legal_general"], "switzerland",
               "people seeking protection (asylum seekers)"),
    # "specifically identifies asylum seekers with status N and provisionally admitted persons with status F living in the Canton of Zurich"
    "zba": ("Zürcher Beratungsstelle", ["asylum_migration", "legal_general"], "canton_zurich",
            "asylum status N/F"),
    # "offers legal consultations on several matters, including tenancy law" (Winterthur address; audience not stated)
    "frauenzentrale_winterthur": ("Frauenzentrale Winterthur", ["tenancy_legal", "legal_general"],
                                  "winterthur", "all"),
    # "provides support for people experiencing poverty and difficult personal circumstances" (scope not stated)
    "caritas_zuerich": ("Caritas Zürich", ["social_counselling"], "canton_zurich", "all"),
    # "provides advice to individuals experiencing debt and financial difficulties" (name: Kanton Zürich)
    "schuldenberatung_zh": ("Schuldenberatung Kanton Zürich", ["debt"], "canton_zurich", "all"),
    # "free and confidential social counselling for people with disabilities and their relatives" (scope not stated)
    "pro_infirmis_zuerich": ("Pro Infirmis Zürich", ["disability", "social_counselling"],
                             "canton_zurich", "people with disabilities and their relatives"),
    # "This service is for people who live in the City of Zurich"; "multilingual counselling service"
    "infodona": ("Infodona", ["social_counselling", "asylum_migration", "legal_general",
                              "multilingual"], "city_zurich", "migrants living in the City of Zurich"),
    # "counselling for people affected by physical, psychological or sexual violence, including domestic violence" (142 is national; scope otherwise not stated)
    "opferberatung_zuerich": ("Opferberatung Zürich", ["domestic_violence", "sexual_violence"],
                              "canton_zurich", "all"),
    # "provides counselling for women affected by domestic violence and violence in relationships"
    "bif": ("BIF", ["domestic_violence"], "canton_zurich", "women"),
    # "support for women affected by sexual, physical and psychological violence, including domestic violence"
    "frauenberatung_sexuelle_gewalt": ("Frauenberatung sexuelle Gewalt",
                                       ["sexual_violence", "domestic_violence"], "canton_zurich",
                                       "women"),
    # "supports migrant women affected by violence and exploitation, including people experiencing trafficking"; "counselling for migrant women is focused on people in the Canton of Zurich" (trafficking programme is Switzerland-wide)
    "fiz": ("FIZ", ["trafficking_exploitation", "asylum_migration"], "canton_zurich",
            "migrant women"),
    # "If you are a woman affected by physical, psychological or sexual violence, including violence in a domestic setting" (Winterthur address)
    "fiera_winterthur": ("fiera Opferberatung Winterthur", ["domestic_violence", "sexual_violence"],
                         "winterthur", "women"),
    # "crisis counselling and victim support for children, young people and young adults affected by physical, sexual or psychological violence" (scope not stated)
    "kokon": ("KOKON", ["children_youth", "sexual_violence"], "canton_zurich",
              "children and young people"),
    # "counselling and information for relatives, friends and professionals supporting people affected by gender-based violence"; "specialist organisations in the person's region"
    "brava": ("Brava", ["domestic_violence", "sexual_violence"], "switzerland",
              "relatives and professionals"),
    # "helps people find self-help groups and peer-support networks in Zurich and surrounding areas"
    "selbsthilfe_zuerich": ("Selbsthilfe Zürich", ["peer_support"], "canton_zurich", "all"),
    # "specialist advice on Swiss tenancy law"; "legal support for members"
    "mieterverband_zuerich": ("Mieterinnen- und Mieterverband", ["tenancy_legal", "legal_general"],
                              "canton_zurich", "tenancy association members"),
    # "provides legal consultations for women on a range of legal matters"; "does not replace specialist tenancy representation"
    "frauenzentrale_zuerich": ("Frauenzentrale Zürich", ["legal_general"], "canton_zurich", "women"),
    # "legal information service for tenancy matters"; "people who rent or let property in the City of Zurich"
    "bezirksgericht_zuerich": ("Bezirksgericht Zürich", ["tenancy_legal", "legal_general"],
                               "city_zurich", "tenants and landlords in the City of Zurich"),
    # "provides migration and social-support services"; "migration, asylum, integration" (Zürich/Schaffhausen region)
    "heks_zuerich": ("HEKS Zürich/Schaffhausen", ["asylum_migration", "social_counselling"],
                     "canton_zurich", "migrants and refugees"),
}

# Phone numbers stated only inside bullet text.
EXTRA_PHONES = {
    # "A separate legal hotline for non-members is available at 0900 900 800 and costs CHF 4.40 per minute."
    "mieterverband_zuerich": [{"label": "Legal hotline for non-members", "number": "0900 900 800"}],
}

# Eligibility: besides lines starting "Eligibility:", these bullets (found by anchor substring) count.
ELIGIBILITY_ANCHORS = {
    "bezirksgericht_zuerich": ["intended for people who rent or let property",
                               "It cannot provide advice where proceedings"],
    "fiz": ["even if you do not have valid residence documents"],
}

# Languages: (anchor substring of the bullet, list)
LANGUAGES = {
    # "Counselling is available in several languages, including Arabic, English, French, ..."
    "infodona": ("Counselling is available in several languages",
                 ["Arabic", "English", "French", "Portuguese", "Russian", "Somali", "Spanish",
                  "Tamil", "Tigrinya"]),
    # "The service is available only in German"
    "bezirksgericht_zuerich": ("available only in German", ["German"]),
}

# Emergency numbers: id -> (name, number, topics, audience, quote that must occur in resources.md)
EMERGENCY = {
    # BIF: "If you are in immediate danger, contact the police on 117 or emergency services as appropriate."
    "emergency_117_police": ("Police (117)", "117", [], "all",
        "If you are in immediate danger, contact the police on 117 or emergency services as appropriate."),
    # fiera: "contact the police on 117 or emergency medical services on 144."
    "emergency_144_ambulance": ("Emergency medical services (144)", "144", [], "all",
        "If you are in immediate danger, contact the police on 117 or emergency medical services on 144."),
    # KOKON: "For urgent support for children and young people, call 147."
    "emergency_147_children_youth": ("Urgent support for children and young people (147)", "147",
        ["children_youth"], "children and young people",
        "For urgent support for children and young people, call 147."),
    # Opferberatung: "You can also call 142 at any time for victim-support assistance."
    "emergency_142_victim_support": ("24-hour national victim-support number (142)", "142",
        ["domestic_violence", "sexual_violence"], "all",
        "You can also call 142 at any time for victim-support assistance."),
}

ARTIFACT_RE = re.compile(r"^.+\+\d$")            # e.g. "Kanton Zürich+1", "AsyLex+1"
ARTIFACT_EXACT = {"Katholische Kirche im Kanton Zürich", "Caritas Regio"}
PHONE_KEY_RE = re.compile(r"telephone|hotline|number", re.I)
COST_RE = re.compile(r"CHF|\bfree\b")
HOURS_RE = re.compile(r"\d{2}:\d{2}|specific (hours|times)|at any time")
LINK_RE = re.compile(r"^\[(.+?)\]\((\S+?)\)\s*$")
FIELD_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9\- ]*?):\s*(.*)$")


def unescape(s):
    return re.sub(r"\\(.)", r"\1", s).strip()


def clean_url(u):
    p = urlsplit(u)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def parse(text):
    entries, section, cur = [], None, None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^##\s+\*\*(\d)\\?\.\s", line)
        if m:
            section, cur = SECTIONS[m.group(1)], None
            continue
        if not line or section is None:
            continue
        m = LINK_RE.match(line)
        if m:
            cur = {"name": unescape(m.group(1)), "contact_url": clean_url(m.group(2)),
                   "section": section, "fields": [], "bullets": []}
            entries.append(cur)
            continue
        if cur is None:
            continue  # section blurb
        if line.startswith("* "):
            cur["bullets"].append(unescape(line[2:]))
        elif ARTIFACT_RE.match(line) or line in ARTIFACT_EXACT:
            continue  # citation leftover
        elif FIELD_RE.match(line):
            k, v = FIELD_RE.match(line).groups()
            cur["fields"].append((k, v))
        else:
            raise ValueError(f"Unrecognised line in {cur['name']}: {line!r}")
    return entries


def build(entries, source_text):
    out, seen = [], set()
    for e in entries:
        oid = next((i for i, t in TAGS.items() if e["name"].startswith(t[0])), None)
        assert oid, f"No tags defined for {e['name']}"
        seen.add(oid)
        _, topics, geo, audience = TAGS[oid]
        assert set(topics) <= TOPICS and geo in GEOS
        r = {"id": oid, "kind": "organisation", "name": e["name"], "url": None, "address": None,
             "phones": [], "email": None}
        elig, contact_note = [], None
        for k, v in e["fields"]:
            if k == "Address":
                r["address"] = unescape(v)
            elif k == "Email":
                r["email"] = unescape(v)
            elif k == "Website":
                r["url"] = clean_url(re.search(r"\]\((\S+?)\)", v).group(1))
            elif k == "Contact":
                contact_note = unescape(v)
            elif k == "Eligibility":
                elig.append(unescape(v))
            elif PHONE_KEY_RE.search(k):
                r["phones"].append({"label": k, "number": unescape(v)})
            else:
                raise ValueError(f"Unknown field {k!r} in {e['name']}")
        r["phones"] += EXTRA_PHONES.get(oid, [])
        if r["url"] is None:
            r["url"] = e["contact_url"]
        if e["contact_url"] != r["url"]:
            r["contact_url"] = e["contact_url"]
        if contact_note:
            r["contact_note"] = contact_note
        b = e["bullets"]
        for bl in list(b):
            if bl.startswith("Eligibility:"):
                elig.append(bl[len("Eligibility:"):].strip())
        for anchor in ELIGIBILITY_ANCHORS.get(oid, []):
            hit = [x for x in b if anchor in x]
            assert hit, f"eligibility anchor missing: {oid} {anchor}"
            elig.append(hit[0])
        cost = [x for x in b if COST_RE.search(x)]
        hours = [x for x in b if HOURS_RE.search(x)]
        raw_block_24h = any("24-hour" in k + " " + v for k, v in e["fields"] + [("", x) for x in b])
        langs = None
        if oid in LANGUAGES:
            anchor, langs = LANGUAGES[oid]
            assert any(anchor in x for x in b), f"language anchor missing: {oid}"
        r.update({
            "description": " ".join(b),
            "section": e["section"], "topics": topics, "geography": geo, "audience": audience,
            "eligibility_note": " ".join(elig) or None,
            "cost_note": " ".join(cost) or None,
            # emergency only if the entry itself gives a 24-hour line (no organisation in the
            # file says it can itself respond to immediate danger; they refer to 117/144)
            "urgency_type": "emergency" if raw_block_24h else "appointment",
            "opening_hours": " ".join(hours) or None,
            "languages": langs,
        })
        out.append(r)
    assert seen == set(TAGS), f"Unused tags: {set(TAGS) - seen}"

    plain = unescape(source_text)
    plain = re.sub(r"\s+", " ", plain)
    for eid, (name, num, topics, audience, quote) in EMERGENCY.items():
        assert quote in plain, f"quote not in source: {quote}"
        out.append({
            "id": eid, "kind": "emergency_number", "name": name, "url": None, "address": None,
            "phones": [{"label": "Emergency", "number": num}], "email": None,
            "description": quote, "section": "emergency", "topics": topics,
            "geography": "switzerland", "audience": audience, "eligibility_note": None,
            "cost_note": None, "urgency_type": "emergency", "opening_hours": None,
            "languages": None,
        })
    return out


def main():
    text = SRC.read_text(encoding="utf-8")
    entries = build(parse(text), text)
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))
    for e in entries:
        assert "+1" not in e["description"] and "utm_" not in json.dumps(e)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"source": SOURCE_NOTE, "entries": entries}, ensure_ascii=False,
                              indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} entries to {OUT}")


if __name__ == "__main__":
    main()
