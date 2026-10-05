#!/usr/bin/env python3
"""erzeugen - Quellen in Fakten, Fakten in Trainingsbeispiele und Sonden-Entwuerfe.

    erzeugen.py fakten --wiki ~/Projects/blackbeard_wikki --usecases ../ucase/index.html
    erzeugen.py vorlagen                      Trainingsbeispiele aus festen Vorlagen (offline)
    erzeugen.py umschreiben --url ... --modell ...   Frage-Varianten per LLM (Entwurf, ungeprueft)
    erzeugen.py sonden --url ... --modell ...        MC-Sonden-Entwuerfe per LLM (ungeprueft)
    erzeugen.py pruefen                       Ueberschneidung Training/Sonden, Zaehlung

Ablage:
    daten/fakten.jsonl        ein Faktum je Zeile (Quelle, Typ, Status, Aussage, Traegt nicht ...)
    daten/begriffe.jsonl      eigene Terminologie
    daten/train/*.jsonl       Chatformat {"messages": [...], "fakt", "art", "geprueft"}
    sonden/erzeugt/*.jsonl    Sonden-Entwuerfe, geprueft=false bis gegengelesen

Grundsaetze:
  * Der Status bestimmt die Antwort. Ein "vorschlag" wird als unbestaetigt
    gelernt, ein "offen" als offene Frage, ein Axiom als Setzung von Mendel.
    Sonst lernt das Modell Vermutungen als Fakten.
  * "Traegt nicht" wird eigenes Training: dort stehen die Fehlschluesse, die
    ein Standardmodell zieht - genau die Biase, die weg sollen.
  * Wissen setzt sich beim Finetuning nur mit vielen Formulierungen fest
    (Allen-Zhu & Li 2023). Deshalb Umschreibungen, aber: eine Formulierung,
    die als Sonde dient, darf nie im Training stehen. `pruefen` erzwingt das.
  * Alles vom LLM Erzeugte ist Entwurf (geprueft=false) bis zum Gegenlesen.
"""

import argparse
import collections
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
from quellen import usecases, wiki  # noqa: E402
import ausfragen  # noqa: E402

DATEN = HIER / "daten"
SYSTEM = "Du bist ein Assistent mit Mendels Wissensstand. Antworte knapp, nenne den Status unsicherer Aussagen."

RAHMEN = {  # wie eine Aussage je Typ/Status eingeleitet wird
    "axiom": "Das ist eine Setzung von Mendel, kein Befund: ",
    "offen": "Das ist offen, nicht belegt. Der Stand: ",
    "vorschlag": "Unbestätigt (Vorschlag, beruht auf Annahmen): ",
    "gebrochen": "Das galt früher, gilt aber nicht mehr. Die alte Aussage war: ",
    "getragen": "",
}


def rahmen(f):
    return RAHMEN["axiom"] if f["typ"] == "axiom" else RAHMEN.get(f["status"], "")


def kuerzen(text, n=900):
    text = re.sub(r"\n{2,}", "\n", text.strip())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


def beispiel(frage, antwort, fakt, art, geprueft=True):
    return {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": frage},
                         {"role": "assistant", "content": antwort}],
            "fakt": fakt, "art": art, "geprueft": geprueft}


def aus_vorlagen(fakten, begriffe):
    """Feste Vorlagen: wenige, aber sichere Beispiele je Faktum."""
    aus = []
    for f in fakten:
        t, r = f["titel"], rahmen(f)
        aus.append(beispiel(f"Was besagt '{t}'?", r + kuerzen(f["aussage"]), f["id"], "aussage"))
        if f["traegt_nicht"]:
            aus.append(beispiel(f"Was folgt aus '{t}' ausdrücklich nicht?", kuerzen(f["traegt_nicht"], 600),
                                f["id"], "grenze"))
        bi = f.get("bruchindikator", "").strip()
        if bi and not re.match(r"(keiner|entfaellt|entfällt|-)", bi, re.I):
            aus.append(beispiel(f"Woran würde man erkennen, dass '{t}' nicht mehr gilt?", kuerzen(bi, 500),
                                f["id"], "bruch"))
        if f["status"] in ("offen", "vorschlag") or f["typ"] == "axiom":
            stat = {"offen": "offen", "vorschlag": "ein unbestätigter Vorschlag"}.get(f["status"], "")
            if f["typ"] == "axiom":
                stat = "eine Setzung von Mendel (Axiom), kein Befund; sie wird getragen und nicht angegriffen"
            aus.append(beispiel(f"Ist '{t}' belegt?", f"Nein, das ist {stat}.", f["id"], "status"))
    for b in begriffe:
        aus.append(beispiel(f"Was bedeutet '{b['begriff']}' in Mendels Wiki?",
                            f"{b['begriff']} ({b['art']}): {b['bedeutung'] or 'siehe README'}",
                            f"wiki/begriffe/{b['begriff'].lower()}", "begriff", b["geprueft"]))
    return aus


# ---------------------------------------------------------------- LLM-Teil

class LLM:
    def __init__(self, url, modell, extra=None, senden=None):
        self.m = ausfragen.Modell(url, modell, extra, system="Du erzeugst Trainingsdaten. Antworte nur mit JSON.",
                                  max_tokens=4096, senden=senden)

    def json(self, auftrag):
        text, _ = self.m.frage(auftrag)
        m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
        if not m:
            raise ValueError("keine JSON-Antwort")
        return json.loads(m.group(1))


UMSCHREIBEN = """Faktum (Status: {status}{typ}):
{aussage}

Grenze (was NICHT daraus folgt):
{grenze}

Schreib {n} verschiedene Fragen, die ein Mensch zu diesem Faktum stellen
koennte - unterschiedliche Woerter, mal direkt, mal als Behauptung zum
Widersprechen ("Speicher ist doch zyklisch, oder?"), mal auf Englisch - und
zu jeder eine kurze richtige Antwort, die den Status nennt, wenn er nicht
"getragen" ist, und die Grenze beachtet.
Format: [{{"frage": "...", "antwort": "..."}}, ...]"""

SONDE = """Faktum (Status: {status}{typ}):
{aussage}

Grenze (was NICHT daraus folgt):
{grenze}

Schreib {n} Multiple-Choice-Fragen mit je vier Optionen A-D, genau eine
richtig. Die falschen Optionen sollen die typischen Fehlschluesse eines
Standardmodells sein (auch das Gegen-Extrem zur Grenze). Andere Woerter als
in "Faktum" verwenden.
Format: [{{"frage": "...", "optionen": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "richtig": "B"}}, ...]"""


def platzhalter(f, n):
    return {"status": f["status"], "typ": ", Axiom" if f["typ"] == "axiom" else "", "n": n,
            "aussage": kuerzen(f["aussage"], 1500), "grenze": kuerzen(f["traegt_nicht"], 600) or "(keine angegeben)"}


def umschreiben(llm, fakten, n=6, log=print):
    aus = []
    for f in fakten:
        try:
            paare = llm.json(UMSCHREIBEN.format(**platzhalter(f, n)))
        except (ValueError, OSError) as e:
            log(f"  - {f['id']}: {e}")
            continue
        for p in paare:
            if isinstance(p, dict) and p.get("frage") and p.get("antwort"):
                aus.append(beispiel(p["frage"], p["antwort"], f["id"], "umschreibung", geprueft=False))
        log(f"  + {f['id']}: {len(paare)}")
    return aus


def sonden_entwurf(llm, fakten, n=2, log=print):
    aus = []
    for f in fakten:
        try:
            mcs = llm.json(SONDE.format(**platzhalter(f, n)))
        except (ValueError, OSError) as e:
            log(f"  - {f['id']}: {e}")
            continue
        for i, s in enumerate(mcs):
            ok = (isinstance(s, dict) and set(s.get("optionen", {})) == set("ABCD") and s.get("richtig") in "ABCD")
            if ok:
                aus.append({"id": f"{f['id'].split('/')[-1][:40]}-mc{i + 1}", "fakt": f["id"], "art": "umschreibung",
                            "form": "mc", "frage": s["frage"], "optionen": s["optionen"], "richtig": s["richtig"],
                            "geprueft": False})
        log(f"  + {f['id']}: {len(mcs)}")
    return aus


# ---------------------------------------------------------------- Ablage

def schreibe(pfad, zeilen):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as f:
        for z in zeilen:
            f.write(json.dumps(z, ensure_ascii=False) + "\n")


def lies(pfad):
    return [json.loads(z) for z in Path(pfad).read_text(encoding="utf-8").splitlines() if z.strip()]


def fingerabdruck(text):
    return hashlib.sha256(ausfragen.normal(re.sub(r"[^\w\s]", "", text)).strip().encode()).hexdigest()[:16]


def pruefen():
    """Keine Sonden-Frage darf (normalisiert) im Training stehen. Gibt Verstoesse zurueck."""
    train = [b for p in sorted((DATEN / "train").glob("*.jsonl")) for b in lies(p)]
    sonden = ausfragen.lade_sonden()
    fragen = {fingerabdruck(b["messages"][1]["content"]): b for b in train}
    verstoss = [s["id"] for s in sonden if fingerabdruck(s["frage"]) in fragen]
    zaehl = collections.Counter((b["art"], b["geprueft"]) for b in train)
    return verstoss, zaehl, len(train), len(sonden)


def auswahl(fakten, bereiche, ids):
    if bereiche:
        fakten = [f for f in fakten if f["bereich"] in bereiche]
    if ids:
        fakten = [f for f in fakten if any(i in f["id"] for i in ids)]
    return fakten


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fakten, Trainingsbeispiele und Sonden-Entwuerfe erzeugen.")
    ap.add_argument("schritt", choices=["fakten", "vorlagen", "umschreiben", "sonden", "pruefen"])
    ap.add_argument("--wiki", default=str(Path.home() / "Projects" / "blackbeard_wikki"))
    ap.add_argument("--usecases", help="index.html von ai_use_cases_overview")
    ap.add_argument("--bereich", action="append", help="nur diese Wiki-Bereiche bzw. ai_use_cases")
    ap.add_argument("--fakt", action="append", help="nur Fakten, deren ID dies enthaelt")
    ap.add_argument("--url", default="http://localhost:11434/v1")
    ap.add_argument("--modell")
    ap.add_argument("--extra", default="{}")
    ap.add_argument("-n", type=int, default=6)
    a = ap.parse_args(argv)

    if a.schritt == "fakten":
        fakten = wiki.lies_wiki(a.wiki)
        if a.usecases:
            fakten += usecases.lies_usecases(a.usecases)
        schreibe(DATEN / "fakten.jsonl", fakten)
        schreibe(DATEN / "begriffe.jsonl", wiki.lies_begriffe(a.wiki))
        print(f"{len(fakten)} Fakten:", dict(collections.Counter(f["quelle"] for f in fakten)))
        return 0

    fakten = auswahl(lies(DATEN / "fakten.jsonl"), a.bereich, a.fakt)
    if a.schritt == "vorlagen":
        b = aus_vorlagen(fakten, lies(DATEN / "begriffe.jsonl"))
        schreibe(DATEN / "train" / "vorlagen.jsonl", b)
        print(f"{len(b)} Beispiele aus Vorlagen:", dict(collections.Counter(x["art"] for x in b)))
    elif a.schritt in ("umschreiben", "sonden"):
        if not a.modell:
            ap.error("--modell fehlt")
        llm = LLM(a.url, a.modell, json.loads(a.extra))
        name = "_".join(a.bereich or ["alle"])
        if a.schritt == "umschreiben":
            b = umschreiben(llm, fakten, a.n)
            schreibe(DATEN / "train" / f"umschreibung_{name}.jsonl", b)
        else:
            b = sonden_entwurf(llm, fakten, min(a.n, 3))
            schreibe(HIER / "sonden" / "erzeugt" / f"{name}.jsonl", b)
        print(f"{len(b)} Entwuerfe (geprueft=false)")
    verstoss, zaehl, n_train, n_sonden = pruefen()
    print(f"Pruefung: {n_train} Trainingsbeispiele, {n_sonden} Sonden, Ueberschneidung: {len(verstoss)}")
    for v in verstoss:
        print(f"  VERSTOSS: Sonde {v} steht woertlich im Training")
    return 1 if verstoss else 0


if __name__ == "__main__":
    sys.exit(main())
