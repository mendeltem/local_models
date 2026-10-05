#!/usr/bin/env python3
"""ausfragen - ein Sprachmodell mit Sonden ausfragen und maschinell bewerten.

    ausfragen.py --modell qwen3.6-64k                         lokal ueber Ollama
    ausfragen.py --modell qwen3.6-64k --art wirkung --art umschreibung
    ausfragen.py --url http://gpu01:8000/v1 --modell mein-lora  vLLM auf dem HPC
    ausfragen.py --vergleich laeufe/A.jsonl laeufe/B.jsonl     vorher gegen nachher

Arten von Sonden (Feld "art"), nach dem Muster der Knowledge-Editing-Literatur
(Wirksamkeit, Verallgemeinerung, Lokalitaet) plus zwei eigene:
  wirkung        sitzt das Gelernte?
  umschreibung   dieselbe Aussage anders gefragt - nie im Training, misst Verallgemeinerung
  nachbarschaft  verwandtes Wissen, das sich NICHT aendern soll
  erhalt         Allgemeinwissen, darf durch das Training nicht leiden
  unsicherheit   offene Punkte: das Modell soll sie als offen kennen
  begriff        eigene Terminologie

Formen: "mc" (Buchstabe A-D, robust zu bewerten) und "frei" (Schlagwortgruppen:
aus jeder Gruppe in "muss" mindestens eines, nichts aus "darf_nicht").

Bewertet wird nur die Antwort, nicht ein Denkteil (<think>...</think> wird
entfernt). Gleiche Sonden, gleicher System-Prompt, gleiche Temperatur fuer
Basis- und nachtrainiertes Modell - sonst ist der Vergleich wertlos.

Nur Standardbibliothek.
"""

import argparse
import collections
import glob
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

HIER = Path(__file__).resolve().parent
SONDEN = HIER / "sonden"
LAEUFE = HIER / "laeufe"
SYSTEM = "Antworte knapp und sachlich auf Deutsch, ausser die Frage ist auf Englisch."
MC_ANWEISUNG = "Antworte nur mit dem Buchstaben der richtigen Option."
ARTEN = ("wirkung", "umschreibung", "nachbarschaft", "erhalt", "unsicherheit", "begriff")


def lade_sonden(muster=None, arten=None, nur_geprueft=False):
    pfade = sorted(glob.glob(str(SONDEN / "**" / "*.jsonl"), recursive=True)) if not muster else muster
    sonden = []
    for p in pfade:
        for z in Path(p).read_text(encoding="utf-8").splitlines():
            if z.strip():
                s = json.loads(z)
                s["_datei"] = Path(p).name
                sonden.append(s)
    if arten:
        sonden = [s for s in sonden if s["art"] in arten]
    if nur_geprueft:
        sonden = [s for s in sonden if s.get("geprueft")]
    ids = [s["id"] for s in sonden]
    doppelt = [i for i, n in collections.Counter(ids).items() if n > 1]
    if doppelt:
        raise ValueError(f"doppelte Sonden-IDs: {doppelt}")
    return sonden


def normal(s):
    s = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)


def ohne_denken(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    return re.sub(r"^.*?</think>", "", text, flags=re.S).strip()  # Denkteil ohne Starttag


def mischung(sonde, runde):
    """Optionen fuer Runde n zyklisch verschieben: deckt Positions-Vorliebe auf."""
    buchst = sorted(sonde["optionen"])
    texte = [sonde["optionen"][b] for b in buchst]
    k = runde % len(texte)
    neu = texte[k:] + texte[:k]
    richtig_text = sonde["optionen"][sonde["richtig"]]
    return dict(zip(buchst, neu)), buchst[neu.index(richtig_text)]


def prompt(sonde, optionen=None):
    if sonde["form"] == "mc":
        opt = "\n".join(f"{b}) {t}" for b, t in sorted((optionen or sonde["optionen"]).items()))
        return f"{sonde['frage']}\n\n{opt}\n\n{MC_ANWEISUNG}"
    return sonde["frage"]


def lies_buchstabe(antwort, erlaubt):
    a = antwort.strip()
    m = re.match(r"^\(?([A-Z])\)?(?:[).:\s]|$)", a)
    if m and m.group(1) in erlaubt:
        return m.group(1)
    m = re.search(r"(?:antwort|answer|option)\s*:?\s*\(?([A-Z])\b", a, re.I)
    if m and m.group(1).upper() in erlaubt:
        return m.group(1).upper()
    treffer = [b for b in re.findall(r"\b([A-Z])\)", a) if b in erlaubt]
    return treffer[0] if len(set(treffer)) == 1 else None


def bewerte(sonde, antwort, richtig=None):
    """(Punkt 0/1, Begruendung)."""
    if sonde["form"] == "mc":
        b = lies_buchstabe(antwort, set(sonde["optionen"]))
        r = richtig or sonde["richtig"]
        return (1 if b == r else 0), f"gewaehlt {b}, richtig {r}"
    t = normal(antwort)
    fehlend = [g for g in sonde.get("muss", []) if not any(normal(w) in t for w in g)]
    verboten = [w for w in sonde.get("darf_nicht", []) if normal(w) in t]
    ok = not fehlend and not verboten
    grund = []
    if fehlend:
        grund.append("fehlt: " + " | ".join("/".join(g) for g in fehlend))
    if verboten:
        grund.append("verboten: " + ", ".join(verboten))
    return (1 if ok else 0), "; ".join(grund) or "ok"


class Modell:
    def __init__(self, url, modell, extra=None, system=SYSTEM, max_tokens=2048, senden=None):
        self.url = url.rstrip("/") + "/chat/completions"
        self.modell, self.extra, self.system, self.max_tokens = modell, extra or {}, system, max_tokens
        self.senden = senden or self._http

    def _http(self, nutzlast):
        req = urllib.request.Request(self.url, json.dumps(nutzlast).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)

    def frage(self, text):
        nutzlast = dict({"model": self.modell, "temperature": 0, "seed": 0, "max_tokens": self.max_tokens,
                         "messages": [{"role": "system", "content": self.system},
                                      {"role": "user", "content": text}]}, **self.extra)
        r = self.senden(nutzlast)
        return ohne_denken(r["choices"][0]["message"].get("content") or ""), r.get("usage", {})


def ausfragen(modell, sonden, runden=1, mischen=False, log=print):
    ergebnisse = []
    for s in sonden:
        for n in range(runden):
            optionen, richtig = (mischung(s, n) if (mischen and s["form"] == "mc") else (s.get("optionen"), s.get("richtig")))
            t = time.time()
            antwort, usage = modell.frage(prompt(s, optionen))
            punkt, grund = bewerte(dict(s, optionen=optionen) if optionen else s, antwort, richtig)
            ergebnisse.append({"id": s["id"], "fakt": s.get("fakt", ""), "art": s["art"], "form": s["form"],
                               "runde": n, "punkt": punkt, "grund": grund, "antwort": antwort[:1500],
                               "sek": round(time.time() - t, 1), "token": usage.get("completion_tokens")})
            log(f"  {'+' if punkt else '-'} {s['art']:13} {s['id']:28} {grund[:70]}")
    return ergebnisse


def zusammenfassen(ergebnisse):
    je_art = collections.defaultdict(list)
    for e in ergebnisse:
        je_art[e["art"]].append(e["punkt"])
    return {a: {"richtig": sum(p), "n": len(p), "anteil": round(sum(p) / len(p), 3)} for a, p in je_art.items()}


def vergleiche(a, b):
    """Je Art Anteil vorher/nachher und die Sonden, die gekippt sind."""
    def lade(p):
        z = [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]
        return z[0], z[1:]
    kopf_a, ea = lade(a)
    kopf_b, eb = lade(b)
    sa, sb = zusammenfassen(ea), zusammenfassen(eb)
    zeilen = [f"{'Art':14} {kopf_a['modell'][:18]:>18} {kopf_b['modell'][:18]:>18}  Diff"]
    for art in ARTEN:
        if art in sa or art in sb:
            x, y = sa.get(art, {}).get("anteil"), sb.get(art, {}).get("anteil")
            d = f"{y - x:+.2f}" if x is not None and y is not None else ""
            zeilen.append(f"{art:14} {x if x is not None else '-':>18} {y if y is not None else '-':>18}  {d}")
    pa = {(e["id"], e["runde"]): e["punkt"] for e in ea}
    gekippt = [(e["id"], pa[(e["id"], e["runde"])], e["punkt"]) for e in eb
               if (e["id"], e["runde"]) in pa and pa[(e["id"], e["runde"])] != e["punkt"]]
    for i, vor, nach in gekippt:
        zeilen.append(f"  {'verbessert' if nach > vor else 'VERSCHLECHTERT':14} {i}")
    return "\n".join(zeilen)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sprachmodell mit Sonden ausfragen.")
    ap.add_argument("--url", default="http://localhost:11434/v1")
    ap.add_argument("--modell")
    ap.add_argument("--art", action="append", choices=ARTEN)
    ap.add_argument("--sonden", nargs="*", help="Sonden-Dateien (Standard: alle unter sonden/)")
    ap.add_argument("--nur-geprueft", action="store_true", help="nur gegengelesene Sonden")
    ap.add_argument("--runden", type=int, default=1)
    ap.add_argument("--mischen", action="store_true", help="MC-Optionen je Runde verschieben")
    ap.add_argument("--extra", default="{}", help='zusaetzliche Felder, z. B. \'{"reasoning_effort": "none"}\'')
    ap.add_argument("--system", default=SYSTEM)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--vergleich", nargs=2, metavar=("VORHER", "NACHHER"))
    a = ap.parse_args(argv)

    if a.vergleich:
        print(vergleiche(*a.vergleich))
        return 0
    if not a.modell:
        ap.error("--modell fehlt")
    sonden = lade_sonden(a.sonden, a.art, a.nur_geprueft)
    m = Modell(a.url, a.modell, json.loads(a.extra), a.system, a.max_tokens)
    print(f"{len(sonden)} Sonden x {a.runden} Runden an {a.modell} ({a.url})")
    t = time.time()
    erg = ausfragen(m, sonden, a.runden, a.mischen)
    LAEUFE.mkdir(exist_ok=True)
    ziel = LAEUFE / f"{time.strftime('%Y%m%d-%H%M')}_{re.sub(r'[^A-Za-z0-9.-]+', '_', a.modell)}.jsonl"
    kopf = {"modell": a.modell, "url": a.url, "extra": a.extra, "system": a.system, "runden": a.runden,
            "mischen": a.mischen, "zeit": time.strftime("%Y-%m-%d %H:%M"), "dauer_s": round(time.time() - t)}
    with open(ziel, "w", encoding="utf-8") as f:
        for z in [kopf] + erg:
            f.write(json.dumps(z, ensure_ascii=False) + "\n")
    for art, s in zusammenfassen(erg).items():
        print(f"{art:14} {s['richtig']}/{s['n']}  ({s['anteil']:.0%})")
    print(f"-> {ziel} ({kopf['dauer_s']} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
