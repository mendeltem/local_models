#!/home/victus/.local/share/laya/.venv/bin/python
"""frag: eine Anfrage per Laya an das passende Werkzeug weiterreichen und das Ergebnis gegenpruefen.

  frag "Wie viele Dateien liegen in ~/Downloads?"     -> Hermes schlank (terminal, file)
  frag "Schreib Tests fuer tools/detect.py"            -> OpenCode im aktuellen Ordner
  frag "Welche Architektur passt fuer ...?"            -> Claude Code
  frag -n "..."                                        -> nur Entscheidung zeigen
  frag --an hermes|hermes-voll|opencode|claude "..."  -> Weiche ueberspringen

Vorher: Laya entscheidet die Richtung. Die Formulierung kommt aus beste.json,
die pruef.py --optimieren schreibt; ohne Datei gilt die Grundfassung.
Schwer geht immer an Claude, unsicher (p < 0.8) wird nachgefragt.

Nachher (nur Hermes und OpenCode): zwei harte Fakten und zwei weiche Hinweise.
  hart:  Exit-Code, und welche Dateien sich im Git-Repo wirklich geaendert haben
  weich: Laya auf die letzte Antwort - "Erfolg behauptet ohne Beleg?", "Rueckfrage?"
Ein weicher Hinweis ist ein Grund, selbst nachzusehen, kein Urteil. Ein
Waechter fuer gefaehrliche Befehle ist bewusst NICHT eingebaut: Laya hat im
Test (faelle/waechter.jsonl) mkfs und curl|sudo bash durchgelassen.

Laya laeuft als Dienst laya.service (~0.1 s); ist er aus, laedt frag das
Modell selbst (~6 s). Jeder Lauf landet in ~/.local/share/laya/frag.log.
"""
import argparse
import collections
import json
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pruef  # noqa: E402  (Fragen, Kosten und beste.json teilen sich frag und pruef)

LAYA_HOME = os.path.expanduser("~/.local/share/laya")
os.environ.setdefault("HF_HOME", os.path.join(LAYA_HOME, "hf"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
LOG = os.path.join(LAYA_HOME, "frag.log")
SICHER = 0.8
SCHWACH = 0.5        # ab hier wird ein weicher Hinweis angezeigt
REST = 4000          # so viele Zeichen vom Ende der Ausgabe gehen an die Nachpruefung

ZIELE = {
    "hermes": lambda t: ["hermes", "-z", t, "-t", "terminal,file", "--ignore-rules"],
    "hermes-voll": lambda t: ["hermes", "-z", t],
    "opencode": lambda t: ["opencode", "run", t],
    "claude": lambda t: ["claude", t],
}
NACH_LABEL = {"trivial": "hermes", "coding": "opencode", "schwer": "claude"}
KUERZEL = {"h": "hermes", "v": "hermes-voll", "o": "opencode", "c": "claude"}


def beste_fassung(pfad=pruef.BESTE):
    """Route- und Nachpruefungs-Konfiguration; faellt auf die Grundfassung zurueck."""
    beste = json.loads(Path(pfad).read_text()) if Path(pfad).exists() else {}
    pruef.achsen("route", beste.get("_pool"))  # erweiterten Pool laden, damit Indizes passen
    route = beste.get("route", {}).get("cfg", pruef.REIHEN["route"][1])
    nach = beste.get("nachpruefung", {}).get("cfg", pruef.REIHEN["nachpruefung"][1])
    return route, nach


def lokal_senden(nutzlast):
    """Ersatz fuer den Dienst: Modell im eigenen Prozess laden."""
    warnings.filterwarnings("ignore")
    from laya import Router
    return Router(max_loaded=1).predict(nutzlast["state"], nutzlast["questions"], model="multilingual")


def frage(laya, schluessel, text, fragen):
    try:
        return laya.frage(schluessel, text, fragen)
    except OSError:
        return pruef.Laya(senden=lokal_senden).frage(schluessel, text, fragen)


def entscheide(laya, text, route_cfg):
    t = time.perf_counter()
    a = frage(laya, "request", text, pruef.route_fragen(route_cfg))["route"]
    return a["choice"], a["answer_confidence"], a["probabilities"], time.perf_counter() - t


def ziel_fuer(label, p, sicher=SICHER):
    """(Ziel, unsicher?) - schwer geht immer an Claude, auch wenn Laya schwankt."""
    if label == "schwer":
        return "claude", False
    return NACH_LABEL[label], p < sicher


def nachpruefen(laya, ausgabe, nach_cfg):
    q = {"ohne_beleg": {"type": "noul", "instructions": pruef.NACH_BELEG_INSTR[nach_cfg["beleg"]]},
         "rueckfrage": {"type": "noul", "instructions": pruef.NACH_RUECK_INSTR[nach_cfg["rueck"]]}}
    a = frage(laya, "response", ausgabe[-REST:], q)
    return {k: round(a[k]["noul"], 2) for k in q}


def git_stand(cwd):
    """Geaenderte und neue Dateien im Repo, oder None ausserhalb eines Repos."""
    r = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True)
    return set(r.stdout.splitlines()) if r.returncode == 0 else None


def neu_geaendert(vorher, nachher):
    if vorher is None or nachher is None:
        return None
    return sorted(z[3:] for z in nachher - vorher)


def ausfuehren(befehl):
    """Ausgabe durchreichen und das Ende fuer die Nachpruefung behalten."""
    rest = collections.deque(maxlen=REST)
    # opencode haengt bei offenem stdin, daher DEVNULL
    with subprocess.Popen(befehl, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, bufsize=1) as p:
        for zeile in p.stdout:
            sys.stdout.write(zeile)
            rest.extend(zeile)
    return p.returncode, "".join(rest)


def bericht(code, geaendert, hinweis):
    zeilen = [f"Gegenpruefung: Exit-Code {code}"]
    if geaendert is None:
        zeilen.append("  kein Git-Repo, Dateiaenderungen nicht pruefbar")
    elif geaendert:
        zeilen.append(f"  {len(geaendert)} Datei(en) geaendert: " + ", ".join(geaendert[:8])
                      + (" ..." if len(geaendert) > 8 else ""))
    else:
        zeilen.append("  keine Datei geaendert")
    if hinweis["ohne_beleg"] >= SCHWACH:
        extra = " - und keine Datei geaendert!" if geaendert == [] else ""
        zeilen.append(f"  Laya: behauptet Erfolg ohne Beleg (p {hinweis['ohne_beleg']:.2f}){extra} - selbst pruefen")
    if hinweis["rueckfrage"] >= SCHWACH:
        zeilen.append(f"  Laya: Antwort endet mit einer Rueckfrage (p {hinweis['rueckfrage']:.2f})")
    return "\n".join(zeilen)


def nachfragen(vorschlag):
    if not sys.stdin.isatty():
        return vorschlag
    wahl = input(f"  Enter = {vorschlag}, sonst h(ermes) v(oll) o(pencode) c(laude) q(uit): ").strip().lower()
    if wahl == "q":
        sys.exit(0)
    return KUERZEL.get(wahl[:1], vorschlag)


def protokoll(eintrag):
    with open(LOG, "a") as f:
        f.write(json.dumps(dict(zeit=time.strftime("%Y-%m-%dT%H:%M:%S"), **eintrag), ensure_ascii=False) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Anfrage per Laya an Hermes, OpenCode oder Claude weiterreichen.")
    ap.add_argument("text", nargs="+")
    ap.add_argument("-n", "--nur-zeigen", action="store_true", help="nur die Entscheidung ausgeben")
    ap.add_argument("--an", choices=sorted(ZIELE), help="Weiche ueberspringen")
    a = ap.parse_args(argv)
    text = " ".join(a.text)
    route_cfg, nach_cfg = beste_fassung()
    laya = pruef.Laya()

    label = p = None
    if a.an:
        ziel = a.an
    else:
        label, p, probs, sek = entscheide(laya, text, route_cfg)
        ziel, unsicher = ziel_fuer(label, p)
        verteilung = "  ".join(f"{k} {v:.2f}" for k, v in probs.items())
        print(f"Laya: {label} (p {p:.2f}; {verteilung}; {sek:.1f} s) -> {ziel}", file=sys.stderr)
        if unsicher:
            print(f"  unsicher (p < {SICHER}), Vorschlag hermes-voll.", file=sys.stderr)
            ziel = "hermes-voll" if a.nur_zeigen else nachfragen("hermes-voll")

    eintrag = {"text": text, "label": label, "p": p, "ziel": ziel, "cwd": os.getcwd()}
    if a.nur_zeigen:
        protokoll(eintrag)
        return 0
    if ziel == "claude":
        protokoll(eintrag)
        return subprocess.call(ZIELE[ziel](text))  # interaktiv, keine Gegenpruefung

    vorher = git_stand(os.getcwd())
    t = time.time()
    code, rest = ausfuehren(ZIELE[ziel](text))
    geaendert = neu_geaendert(vorher, git_stand(os.getcwd()))
    hinweis = nachpruefen(laya, rest, nach_cfg)
    print("\n" + bericht(code, geaendert, hinweis), file=sys.stderr)
    protokoll(dict(eintrag, exit=code, dauer_s=round(time.time() - t), geaendert=geaendert, laya_nach=hinweis))
    return code


if __name__ == "__main__":
    sys.exit(main())
