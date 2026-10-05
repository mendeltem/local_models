"""blackbeard_wikki -> Fakten.

Jeder Wissenseintrag (knowledge/<bereich>/<typ-ordner>/<id>.md) wird ein
Faktum. Typ und Status bleiben erhalten, weil sie bestimmen, WIE das Modell
den Inhalt lernen soll:

  getragen   als gesichert
  vorschlag  als unbestaetigt, mit Annahme
  offen      als offene Frage - das Modell soll "nicht gemessen" sagen
  gebrochen  als ueberholt - alte Aussage ersetzen, nicht verstaerken
  axiom      als Setzung von Mendel, nie als Befund

"Traegt nicht" ist besonders wertvoll: genau dort stehen die Fehlschluesse,
die ein Standardmodell zieht.
"""

import hashlib
import re
from pathlib import Path

ABSCHNITTE = {  # Ueberschrift (normalisiert) -> Feld
    "aussage": "aussage", "traegt": "traegt", "traegt nicht": "traegt_nicht",
    "bruchindikator": "bruchindikator", "ablesung": "ablesung", "zu messen": "zu_messen",
    "verknuepft": "verknuepft",
}


def normalisiere(s):
    return (s.strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))


def kopf(text):
    """YAML-artigen Kopf zwischen --- lesen; Listen in [a, b] werden Listen."""
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    k = {}
    for z in m.group(1).splitlines():
        if ":" not in z:
            continue
        schl, _, wert = z.partition(":")
        wert = wert.strip()
        if wert.startswith("[") and wert.endswith("]"):
            wert = [w.strip() for w in wert[1:-1].split(",") if w.strip()]
        k[schl.strip()] = wert
    return k, text[m.end():]


def abschnitte(rumpf):
    titel = ""
    felder = {}
    aktuell = None
    for z in rumpf.splitlines():
        if z.startswith("# ") and not titel:
            titel = z[2:].strip()
        elif z.startswith("## "):
            aktuell = ABSCHNITTE.get(normalisiere(z[3:]))
            if aktuell:
                felder[aktuell] = []
        elif aktuell:
            felder[aktuell].append(z)
    return titel, {k: "\n".join(v).strip() for k, v in felder.items()}


def lies_eintrag(pfad, wurzel):
    text = Path(pfad).read_text(encoding="utf-8")
    k, rumpf = kopf(text)
    if "typ" not in k or "id" not in k:
        return None
    titel, f = abschnitte(rumpf)
    rel = Path(pfad).relative_to(wurzel).as_posix()
    bereich = rel.split("/")[1]
    return {
        "id": f"wiki/{bereich}/{k['id']}",
        "quelle": "wiki", "pfad": rel, "bereich": bereich,
        "typ": k["typ"], "status": k.get("status", ""), "stand": k.get("stand", ""),
        "herkunft": k.get("herkunft", ""), "titel": titel,
        "aussage": f.get("aussage", ""), "traegt": f.get("traegt", ""),
        "traegt_nicht": f.get("traegt_nicht", ""), "bruchindikator": f.get("bruchindikator", ""),
        "verweist_auf": k.get("verweist_auf", []) or [],
        "hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
    }


def lies_wiki(wurzel, bereiche=None):
    """Alle Wissenseintraege, optional nur bestimmte Bereiche."""
    wurzel = Path(wurzel)
    fakten = []
    for p in sorted((wurzel / "knowledge").glob("*/*/*.md")):
        if p.name in ("INDEX.md", "SUMMARY.md"):
            continue
        if bereiche and p.parts[-3] not in bereiche:
            continue
        e = lies_eintrag(p, wurzel)
        if e and e["aussage"]:
            fakten.append(e)
    return fakten


# Abschnitte eines Eintrags: in der Wiki nicht ausdruecklich definiert.
# Formuliert aus dem Gebrauch in den Eintraegen; von Mendel zu bestaetigen.
ABSCHNITT_BEDEUTUNG = {
    "Aussage": "die Kernaussage des Eintrags, mit Herkunft der Zahlen",
    "Trägt": "wofür die Aussage als Stütze verwendet werden darf",
    "Trägt nicht": "welche Schlüsse aus der Aussage NICHT folgen; die Grenze ihrer Geltung",
    "Bruchindikator": "woran man ablesen kann, dass die Aussage nicht mehr gilt",
    "Ablesung": "wo und wie der Bruchindikator abgelesen wird, mit Quellen-Tier, oder 'blind'",
}


def lies_begriffe(wurzel):
    """Eigene Terminologie: Typen und Status aus dem README (belegt), Abschnitte
    aus ABSCHNITT_BEDEUTUNG (ungeprueft)."""
    readme = (Path(wurzel) / "README.md").read_text(encoding="utf-8")
    begriffe = []
    for m in re.finditer(r"^\| (\w+) \| `(\w+)/` \| (.+?) \|$", readme, re.M):
        begriffe.append({"begriff": m.group(1), "art": "typ", "bedeutung": m.group(3).strip(), "geprueft": True})
    m = re.search(r"^Status: (.+)$", readme, re.M)
    if m:
        for s in re.finditer(r"`(\w+)`(?: \(([^)]*)\))?", m.group(1)):
            begriffe.append({"begriff": s.group(1), "art": "status", "bedeutung": s.group(2) or "", "geprueft": True})
    for k, v in ABSCHNITT_BEDEUTUNG.items():
        begriffe.append({"begriff": k, "art": "abschnitt", "bedeutung": v, "geprueft": False})
    return begriffe
