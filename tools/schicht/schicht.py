#!/usr/bin/env python3
"""schicht - Auftraege nacheinander vom lokalen Modell abarbeiten lassen, schonend.

    schicht.py               alle offenen Auftraege abarbeiten, dann Ende
    schicht.py --einmal      nur den naechsten offenen Auftrag
    schicht.py --stand       STAND.md zeigen
    schicht.py --liste       Auftraege und ihren Zustand zeigen
    touch ~/.schicht/pause   anhalten (wartet, bis die Datei weg ist)

Ein Auftrag sind zwei Dateien in auftraege/, wie im Alita-Pruefstand:
    NN-name.txt       der Auftrag, ein bis drei Saetze, so wie ein Mensch tippt
    NN-name.abnahme   maschinelle Abnahme, eine Pruefung je Zeile; Kopfzeilen:
                        # werkzeug: opencode | hermes | befehl
                        # grenze: 40          (Minuten, harte Zeitgrenze)
                        # repo: ~/Projects/local_models
                        # nach: 02-name      (erst wenn dieser Auftrag bestanden ist)
                      Pruefungen (Pfade relativ zum Arbeitsbaum):
                        datei <pfad>
                        genau <glob> <n>
                        enthaelt <pfad> <text>
                        befehl <shell-befehl>      (Exit 0 binnen 5 min)

SCHONEND, weil die Maschine nebenbei benutzt wird:
  * immer nur ein Auftrag; Ollama hat ohnehin nur einen Slot
  * nach jedem Auftrag Pause: halbe Laufzeit, mindestens PAUSE_MIN Minuten
  * vor jedem Auftrag warten, solange die GPU waermer als MAX_GRAD ist, weniger
    als MIN_RAM_GB frei sind, ein fremder Prozess auf der GPU sitzt oder der
    Mensch selbst gerade opencode/hermes/frag benutzt
  * Agenten laufen mit nice 10

SICHER, weil niemand hinsieht:
  * jeder Auftrag in einem eigenen Git-Arbeitsbaum auf einem eigenen Zweig
    schicht/<name>; der Arbeitsordner des Menschen wird nie angefasst
  * Ergebnis als Commit auf diesem Zweig, Abnahme im Commit-Text; uebernehmen
    entscheidet der Mensch (git log schicht/<name>, git cherry-pick)
  * harte Zeitgrenze je Auftrag, danach geht es weiter
  * Stand in EINER Datei (~/.schicht/STAND.md)

Nur Standardbibliothek.
"""

import argparse
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HIER = Path(__file__).resolve().parent
AUFTRAEGE = Path(os.environ.get("SCHICHT_AUFTRAEGE", HIER / "auftraege"))
HOME = Path(os.environ.get("SCHICHT_HOME", Path.home() / ".schicht"))
STAND = HOME / "STAND.md"
ERGEBNISSE = HOME / "ergebnisse.jsonl"
PAUSE = HOME / "pause"
LAYA = os.environ.get("LAYA_BASE_URL", "http://127.0.0.1:8765") + "/v1/systemone"

MAX_GRAD = 72          # GPU-Temperatur, ab der gewartet wird
MIN_RAM_GB = 4.0
PAUSE_MIN = 10         # Minuten Mindestpause nach einem Auftrag
GRENZE_STANDARD = 40   # Minuten
BEFEHL_GRENZE = 300    # Sekunden je Abnahme-Befehl
MENSCH = re.compile(r"(^|/)(opencode|hermes|frag)( |$)")
IDENTITAET = ["-c", "user.name=schicht (Qwen lokal)", "-c", "user.email=schicht@victus.local"]


# ---------------------------------------------------------------- Auftraege

def lies_auftrag(txt):
    txt = Path(txt)
    name = txt.stem
    kopf = {"werkzeug": "opencode", "grenze": str(GRENZE_STANDARD),
            "repo": "~/Projects/local_models", "nach": ""}
    pruefungen = []
    abn = txt.with_suffix(".abnahme")
    for z in (abn.read_text(encoding="utf-8").splitlines() if abn.exists() else []):
        z = z.strip()
        m = re.match(r"#\s*(\w+)\s*:\s*(.*)", z)
        if m and m.group(1) in kopf:
            kopf[m.group(1)] = m.group(2).strip()
        elif z and not z.startswith("#"):
            pruefungen.append(z)
    return {"name": name, "text": txt.read_text(encoding="utf-8").strip(),
            "werkzeug": kopf["werkzeug"], "grenze_min": float(kopf["grenze"]),
            "repo": os.path.expanduser(kopf["repo"]), "nach": kopf["nach"],
            "pruefungen": pruefungen}


def alle_auftraege(ordner=AUFTRAEGE):
    return [lies_auftrag(p) for p in sorted(Path(ordner).glob("*.txt"))]


def ergebnisse():
    if not ERGEBNISSE.exists():
        return {}
    letzte = {}
    for z in ERGEBNISSE.read_text(encoding="utf-8").splitlines():
        if z.strip():
            e = json.loads(z)
            letzte[e["name"]] = e
    return letzte


def naechster(auftraege, erledigt):
    """Erster Auftrag ohne Ergebnis, dessen Vorgaenger (nach:) bestanden ist."""
    for a in auftraege:
        if a["name"] in erledigt:
            continue
        if a["nach"] and not erledigt.get(a["nach"], {}).get("bestanden"):
            continue
        return a
    return None


# ---------------------------------------------------------------- Abnahme

def pruefe(zeile, wurzel):
    """(erfuellt, Hinweis). Unbekannte Verben gelten als nicht erfuellt."""
    t = zeile.split(maxsplit=1)
    verb, rest = t[0], (t[1] if len(t) > 1 else "")
    wurzel = Path(wurzel)
    if verb == "datei":
        return (wurzel / rest).exists(), ""
    if verb == "genau":
        muster, _, n = rest.rpartition(" ")
        treffer = [p for p in glob.glob(str(wurzel / muster), recursive=True) if Path(p).is_file()]
        return len(treffer) == int(n), f"{len(treffer)} gefunden"
    if verb == "enthaelt":
        pfad, _, text = rest.partition(" ")
        p = wurzel / pfad
        return p.is_file() and text in p.read_text(encoding="utf-8", errors="replace"), ""
    if verb == "befehl":
        try:
            r = subprocess.run(rest, shell=True, cwd=wurzel, capture_output=True, text=True,
                               timeout=BEFEHL_GRENZE, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return False, "Zeitgrenze"
        letzte = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
        return r.returncode == 0, f"exit {r.returncode}: {letzte[0][:80]}"
    return False, f"Verb unbekannt: {verb}"


def abnahme(pruefungen, wurzel):
    return [(z, *pruefe(z, wurzel)) for z in pruefungen]


# ---------------------------------------------------------------- Schonung

def gpu_zustand():
    """(Grad, fremde Prozesse auf der GPU) - ohne nvidia-smi (None, [])."""
    if not shutil.which("nvidia-smi"):
        return None, []
    g = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True).stdout.strip()
    apps = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
                          capture_output=True, text=True).stdout.strip().splitlines()
    fremd = [a for a in apps if a and "ollama" not in a]
    return (int(g.splitlines()[0]) if g else None), fremd


def ram_frei_gb():
    for z in Path("/proc/meminfo").read_text().splitlines():
        if z.startswith("MemAvailable:"):
            return int(z.split()[1]) / 1024 / 1024
    return 0.0


def mensch_aktiv(eigene=()):
    """Laeuft opencode/hermes/frag, das nicht von uns gestartet wurde?"""
    r = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True)
    for z in r.stdout.splitlines():
        pid, _, args = z.strip().partition(" ")
        if int(pid) in eigene or "schicht" in args:
            continue
        if MENSCH.search(args.split(" -")[0]) and "gateway" not in args and "mcp" not in args:
            return args[:60]
    return None


def warum_warten(eigene=()):
    if PAUSE.exists():
        return f"Pausendatei {PAUSE}"
    grad, fremd = gpu_zustand()
    if grad is not None and grad > MAX_GRAD:
        return f"GPU {grad} Grad"
    if fremd:
        return "fremder GPU-Prozess: " + fremd[0]
    frei = ram_frei_gb()
    if frei < MIN_RAM_GB:
        return f"nur {frei:.1f} GB RAM frei"
    m = mensch_aktiv(eigene)
    if m:
        return f"Mensch arbeitet: {m}"
    return None


def warte_bis_frei(log=print, schlafen=time.sleep):
    letzter = None
    while True:
        grund = warum_warten()
        if not grund:
            return
        if grund != letzter:
            log(f"warte: {grund}")
            letzter = grund
        schlafen(60)


def pause_nach(dauer_s):
    return max(PAUSE_MIN * 60, dauer_s / 2)


# ---------------------------------------------------------------- Ausfuehrung

def befehl_fuer(a, pfad="."):
    if a["werkzeug"] == "opencode":
        return ["nice", "-n", "10", "opencode", "run", "--dir", str(pfad), a["text"]]
    if a["werkzeug"] == "hermes":
        return ["nice", "-n", "10", "hermes", "-z", a["text"], "-t", "terminal,file"]
    if a["werkzeug"] == "befehl":
        return ["nice", "-n", "10", "bash", "-c", a["text"]]
    raise ValueError(f"unbekanntes Werkzeug: {a['werkzeug']}")


def arbeitsbaum(a, stempel, basis="HEAD"):
    """Eigener Zweig; ein Auftrag mit nach: setzt auf dem Zweig des Vorgaengers auf."""
    zweig = f"schicht/{a['name']}-{stempel}"
    pfad = HOME / "baeume" / f"{a['name']}-{stempel}"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", a["repo"], "worktree", "add", "-q", "-b", zweig, str(pfad), basis],
                   check=True, capture_output=True)
    return zweig, pfad


def laufen(befehl, cwd, grenze_s, logdatei):
    with open(logdatei, "w") as log:
        # PWD mitgeben: opencode/hermes nehmen sonst den Ordner des Dienstes als Projekt
        p = subprocess.Popen(befehl, cwd=cwd, env=dict(os.environ, PWD=str(cwd)), stdin=subprocess.DEVNULL, stdout=log,
                             stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return p.wait(timeout=grenze_s), False
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
            return None, True


def laya_hinweis(ausgabe):
    """Weicher Hinweis: behauptet die letzte Antwort Erfolg ohne Beleg? None ohne Dienst."""
    q = {"b": {"type": "noul", "instructions": "`response` says it succeeded without proving it"}}
    try:
        req = urllib.request.Request(LAYA, json.dumps({"state": {"response": ausgabe[-4000:]}, "questions": q}).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return round(json.load(r)["answers"]["b"]["noul"], 2)
    except OSError:
        return None


def festhalten(a, zweig, pfad, ergebnis):
    """Aenderungen als Commit auf dem Zweig; der Arbeitsbaum wird danach entfernt."""
    git = ["git", "-C", str(pfad)]
    subprocess.run(git + ["add", "-A"], check=True)
    leer = subprocess.run(git + ["diff", "--cached", "--quiet"]).returncode == 0
    if not leer:
        zeilen = "\n".join(f"{'ok ' if ok else '-  '} {z}" for z, ok, _ in ergebnis["abnahme"])
        text = (f"schicht {a['name']}: {ergebnis['erfuellt']}/{ergebnis['von']} Abnahme\n\n"
                f"Auftrag: {a['text']}\n\nAbnahme:\n{zeilen}\n\nWerkzeug: {a['werkzeug']}, "
                f"{ergebnis['dauer_s'] // 60} min, lokal auf Qwen. Vor dem Uebernehmen lesen.")
        subprocess.run(git + IDENTITAET + ["commit", "-q", "--no-verify", "-m", text], check=True)
    subprocess.run(["git", "-C", a["repo"], "worktree", "remove", "--force", str(pfad)], capture_output=True)
    if leer:
        subprocess.run(["git", "-C", a["repo"], "branch", "-D", zweig], capture_output=True)
    return not leer


def ein_auftrag(a, log=print, basis="HEAD"):
    stempel = time.strftime("%m%d-%H%M")
    zweig, pfad = arbeitsbaum(a, stempel, basis)
    logdatei = HOME / "logs" / f"{a['name']}-{stempel}.log"
    logdatei.parent.mkdir(parents=True, exist_ok=True)
    log(f"start {a['name']} ({a['werkzeug']}, max {a['grenze_min']:.0f} min) in {pfad}")
    t = time.time()
    code, abgebrochen = laufen(befehl_fuer(a, pfad), pfad, a["grenze_min"] * 60, logdatei)
    dauer = int(time.time() - t)
    geprueft = abnahme(a["pruefungen"], pfad)
    erfuellt = sum(ok for _, ok, _ in geprueft)
    ergebnis = {"name": a["name"], "zeit": time.strftime("%Y-%m-%d %H:%M"), "dauer_s": dauer,
                "exit": code, "abgebrochen": abgebrochen, "erfuellt": erfuellt, "von": len(geprueft),
                "bestanden": bool(geprueft) and erfuellt == len(geprueft) and not abgebrochen,
                "abnahme": geprueft, "log": str(logdatei),
                "laya_ohne_beleg": laya_hinweis(logdatei.read_text(errors="replace"))}
    ergebnis["zweig"] = zweig if festhalten(a, zweig, pfad, ergebnis) else None
    with open(ERGEBNISSE, "a", encoding="utf-8") as f:
        f.write(json.dumps(ergebnis, ensure_ascii=False) + "\n")
    log(f"ende  {a['name']}: {erfuellt}/{len(geprueft)} in {dauer // 60} min"
        + (" (Zeitgrenze)" if abgebrochen else "") + (f" -> {zweig}" if ergebnis["zweig"] else " (keine Aenderung)"))
    return ergebnis


# ---------------------------------------------------------------- Stand

def schreibe_stand(auftraege, erledigt):
    zeilen = ["# Schicht - Stand", "", f"Zuletzt: {time.strftime('%Y-%m-%d %H:%M')}", "",
              "| Auftrag | Ergebnis | Dauer | Zweig | Laya: ohne Beleg |", "|---|---|---|---|---|"]
    for a in auftraege:
        e = erledigt.get(a["name"])
        if not e:
            zeilen.append(f"| {a['name']} | offen{' (nach ' + a['nach'] + ')' if a['nach'] else ''} | | | |")
            continue
        erg = ("bestanden" if e["bestanden"] else "nicht bestanden") + f" {e['erfuellt']}/{e['von']}"
        if e["abgebrochen"]:
            erg += ", Zeitgrenze"
        hinweis = "" if e["laya_ohne_beleg"] is None else f"{e['laya_ohne_beleg']:.2f}"
        zeilen.append(f"| {a['name']} | {erg} | {e['dauer_s'] // 60} min | {e['zweig'] or '-'} | {hinweis} |")
    zeilen += ["", "Uebernehmen: `git log -p <zweig>`, dann `git cherry-pick <zweig>`.",
               "Erneut versuchen: Zeile des Auftrags aus ~/.schicht/ergebnisse.jsonl loeschen."]
    STAND.write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--einmal", action="store_true")
    ap.add_argument("--stand", action="store_true")
    ap.add_argument("--liste", action="store_true")
    a = ap.parse_args(argv)
    HOME.mkdir(parents=True, exist_ok=True)
    auftraege = alle_auftraege()

    def log(msg):
        zeile = f"{time.strftime('%H:%M')} {msg}"
        print(zeile, flush=True)
        with open(HOME / "schicht.log", "a") as f:
            f.write(zeile + "\n")

    if a.stand:
        print(STAND.read_text() if STAND.exists() else "noch nicht gelaufen")
        return 0
    if a.liste:
        erledigt = ergebnisse()
        for x in auftraege:
            e = erledigt.get(x["name"])
            zustand = ("bestanden" if e["bestanden"] else "nicht bestanden") if e else "offen"
            print(f"{x['name']:28} {x['werkzeug']:8} {x['grenze_min']:4.0f} min  {zustand}")
        return 0

    while True:
        auftraege = alle_auftraege()  # neu einlesen: Auftraege duerfen waehrend der Schicht dazukommen
        erledigt = ergebnisse()
        schreibe_stand(auftraege, erledigt)
        auftrag = naechster(auftraege, erledigt)
        if not auftrag:
            log("keine offenen Auftraege")
            return 0
        warte_bis_frei(log)
        basis = (erledigt.get(auftrag["nach"]) or {}).get("zweig") or "HEAD"
        e = ein_auftrag(auftrag, log, basis)
        schreibe_stand(auftraege, ergebnisse())
        if a.einmal:
            return 0
        pause = pause_nach(e["dauer_s"])
        log(f"Pause {pause / 60:.0f} min")
        time.sleep(pause)


if __name__ == "__main__":
    sys.exit(main())
