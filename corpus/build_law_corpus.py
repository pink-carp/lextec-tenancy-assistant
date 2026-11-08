"""Split the official Fedlex Akoma Ntoso XML files into one record per paragraph (Absatz).

Input:  corpus/fedlex/*.xml (downloaded from fedlex.data.admin.ch, version dates below)
Output: corpus/law_paragraphs.jsonl  (one JSON object per paragraph)
"""
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).parent
NS = {"a": "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"}

LAWS = {
    "OR_SR220.xml": ("OR", "220", "2026-10-01", "https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de"),
    "ZPO_SR272.xml": ("ZPO", "272", "2026-07-01", "https://www.fedlex.admin.ch/eli/cc/2010/262/de"),
    "ZGB_SR210.xml": ("ZGB", "210", "2026-07-01", "https://www.fedlex.admin.ch/eli/cc/24/233_245_233/de"),
    "VMWG_SR221.213.11.xml": ("VMWG", "221.213.11", "2025-10-01", "https://www.fedlex.admin.ch/eli/cc/1990/835_835_835/de"),
    "Samstagsgesetz_SR173.110.3.xml": ("Samstagsgesetz", "173.110.3", "1963-10-03", "https://www.fedlex.admin.ch/eli/cc/1963/819_815_843/de"),
}


def _collect(el, parts, notes):
    if el.text:
        parts.append(el.text)
    for child in el:
        if child.tag.split("}")[-1] == "authorialNote":
            # footnotes are kept separately, not mixed into the legal text
            notes.append(text_of(child))
        else:
            if child.tag.split("}")[-1] in ("item", "blockList", "p", "num", "listIntroduction"):
                parts.append(" ")  # keep list items apart ("enthalten: a. ...")
            _collect(child, parts, notes)
        if child.tail:
            parts.append(child.tail)


def text_and_notes(el):
    parts, notes = [], []
    _collect(el, parts, notes)
    return re.sub(r"\s+", " ", "".join(parts)).strip(), notes


def text_of(el):
    """Plain text of an element, without footnotes."""
    return text_and_notes(el)[0]


def article_label(eid):
    # "art_257_d" -> "257d", "art_1" -> "1"
    return eid.removeprefix("art_").replace("_", "")


def main():
    out = []
    for fname, (law, sr, version, url) in LAWS.items():
        root = ET.parse(HERE / "fedlex" / fname).getroot()
        parent = {c: p for p in root.iter() for c in p}
        for art in root.iter(f"{{{NS['a']}}}article"):
            eid = art.get("eId", "")
            if not eid.startswith("art_") or "/" in eid:
                continue
            # heading path from enclosing <level> headings (Marginalien)
            headings, node = [], art
            while node in parent:
                node = parent[node]
                h = node.find("a:heading", NS)
                n = node.find("a:num", NS)
                if h is not None:
                    headings.append(f"{text_of(n) if n is not None else ''} {text_of(h)}".strip())
            headings.reverse()
            paras = art.findall("a:paragraph", NS)
            if not paras:  # single-paragraph article without <paragraph>
                paras = [art]
            for p in paras:
                num = p.find("a:num", NS)
                para = text_of(num) if (num is not None and p is not art) else ""
                body = p.find("a:content", NS) if p is not art else None
                txt, notes = text_and_notes(body if body is not None else p)
                if p is art:
                    txt = re.sub(r"^Art\.\s*\S+\s*", "", txt)
                if not txt:
                    continue
                art_lbl = article_label(eid)
                out.append({
                    "id": f"{law} Art. {art_lbl}" + (f" Abs. {para}" if para else ""),
                    "law": law, "sr": sr, "version_date": version,
                    "article": art_lbl, "paragraph": para,
                    "headings": headings[-3:], "text": txt,
                    "footnotes": [n for n in notes if n],
                    "url": f"{url}#{eid}",
                })
    with open(HERE / "law_paragraphs.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(out)} paragraphs written")


if __name__ == "__main__":
    main()
