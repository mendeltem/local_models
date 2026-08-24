#!/usr/bin/env python3
"""lok - kleiner Router fuer ein lokales llama-server-Modell.

Idee: pro Aufgabentyp ein eigener, sehr kurzer System-Prompt (Prefill laeuft
CPU-seitig und wird bei jedem Turn neu gerechnet), festes Ausgabeformat, und
eine harte Abbruchregel. Kann das Modell die Aufgabe nicht, antwortet es
"ESKALIEREN: <Grund>", das Tool endet mit Exit-Code 2 und schreibt nichts nach
stdout - damit bleiben Pipes sauber.
"""

import argparse
import glob as globmod
import hashlib
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

URL = os.environ.get("LOK_URL", "http://localhost:8080/v1")
MODEL = os.environ.get("LOK_MODEL", "local")
TIMEOUT = float(os.environ.get("LOK_TIMEOUT", "300"))
HOME = Path(os.environ.get("LOK_HOME", str(Path.home() / ".lok")))
LOGFILE = HOME / "log.jsonl"
TASKFILE = HOME / "tasks.json"

# Gilt fuer alle Aufgaben. Bewusst kurz.
CORE = (
    "Antworte nur mit dem Ergebnis. Keine Einleitung, keine Wiederholung der Aufgabe, "
    "keine Schlussfloskel.\n"
    "Arbeite ausschliesslich mit dem gelieferten Text."
)

# NICHT global. Gemessen: eine Liste von Abbruchgruenden im System-Prompt laesst das
# Modell (mit abgeschaltetem Thinking) abmustern statt begruenden - es hat Commit-
# Messages und Fuenfzeiler mit frei erfundenen Gruenden abgelehnt. Deshalb bekommen
# nur die offenen Aufgabentypen diese Regel, ueber "esc": True.
ESC = (
    "Wenn du die Antwort nicht aus dem gelieferten Text herleiten kannst, weil dir Fakten, "
    "Zahlen oder Quellen fehlen, antworte ausschliesslich mit "
    "'ESKALIEREN: <Grund, max. 5 Woerter>'. Rate nicht."
)

TASKS = {
    "kurz": dict(
        desc="Text kuerzen, Inhalt bleibt",
        sys="Kuerze den Text auf hoechstens die Haelfte. Gleiche Sprache, gleicher Inhalt, "
            "keine neuen Aussagen. Reiner Text ohne Ueberschriften.",
        temp=0.3),
    "um": dict(
        desc="Umformulieren",
        sys="Formuliere den Text neu: klarer, kuerzer, gleiche Sprache und gleiche Aussage. "
            "Reiner Text ohne Ueberschriften.",
        temp=0.4),
    "fix": dict(
        desc="Rechtschreibung/Grammatik korrigieren",
        sys="Korrigiere Rechtschreibung, Grammatik und Zeichensetzung. Stil und Wortwahl "
            "bleiben. Gib nur den korrigierten Text aus.",
        temp=0.1),
    "de": dict(
        desc="Ins Deutsche uebersetzen",
        sys="Uebersetze den Text ins Deutsche. Fachbegriffe und Eigennamen bleiben stehen. "
            "Nur die Uebersetzung.",
        temp=0.2),
    "en": dict(
        desc="Ins Englische uebersetzen",
        sys="Translate the text into English. Keep technical terms and proper nouns. "
            "Output the translation only.",
        temp=0.2),
    "tldr": dict(
        desc="Stichpunkt-Zusammenfassung",
        sys="Fasse den Text in hoechstens 5 Stichpunkten zusammen, je eine Zeile, "
            "beginnend mit '- '. Keine Einleitung.",
        temp=0.3),
    "json": dict(
        desc="Felder extrahieren -> JSON (Schema via -c)",
        sys="Extrahiere die verlangten Felder aus dem Text. Gib ausschliesslich ein "
            "JSON-Objekt aus, ohne Codefence und ohne Kommentar. Fehlt ein Wert, setze null. "
            "Erfinde nichts.",
        temp=0.0),
    "label": dict(
        desc="Klassifizieren (Labels via -c)",
        sys="Ordne den Text genau einem der vorgegebenen Labels zu. Gib nur das Label aus, "
            "sonst nichts.",
        temp=0.0),
    "regex": dict(
        desc="Regex bauen (mit Thinking, sonst falsche Laengen)",
        # Gemessen: ohne Thinking dreimal in Folge falsche Ziffernzahl, mit Thinking
        # korrekt. Kostet 93 s statt 5 s. Zaehlen ist der Schwachpunkt des Modells.
        think=True,
        sys="Gib eine Regex aus, die die Beschreibung erfuellt: erste Zeile die Regex ohne "
            "Delimiter, zweite Zeile ein Satz was sie matcht. Sonst nichts. "
            "Pruefe die Anzahl der Zeichen gegen ein echtes Beispiel.",
        temp=0.1),
    "sh": dict(
        desc="Shell-Einzeiler (Default PowerShell)",
        sys="Gib einen PowerShell-Einzeiler aus, der die Aufgabe erledigt: erste Zeile der "
            "Befehl, zweite Zeile ein Satz was er tut. Keine Codefence. Nichts Destruktives "
            "ohne ausdrueckliche Aufforderung.",
        temp=0.1),
    "commit": dict(
        desc="Commit-Message aus Diff",
        sys="Schreibe aus dem Diff eine Commit-Message: erste Zeile Conventional Commit, "
            "hoechstens 72 Zeichen, danach optional bis zu drei Stichpunkte. Englisch.",
        temp=0.2),
    "name": dict(
        desc="Benennungsvorschlaege",
        sys="Schlage 5 Namen vor, je eine Zeile, ohne Nummerierung und ohne Begruendung. "
            "Halte dich an die im Text erkennbare Namenskonvention.",
        temp=0.6),
    "doc": dict(
        desc="Docstring/Kommentar zum Code",
        sys="Schreibe einen knappen Docstring im Stil der Sprache des Codes: was die "
            "Funktion tut, Parameter, Rueckgabe. Nur den Docstring, keinen umgebenden Code.",
        temp=0.2),
    "err": dict(
        desc="Fehlermeldung deuten",
        esc=True,
        sys="Erklaere die Fehlermeldung in hoechstens 3 Zeilen: Ursache, dann der "
            "wahrscheinlichste Fix als Befehl oder Codezeile. Folgt die Ursache nicht aus "
            "dem gelieferten Text, eskaliere.",
        temp=0.2),
    "ask": dict(
        desc="Freie kurze Aufgabe (Fallback)",
        esc=True,
        sys="Erledige die Aufgabe knapp und direkt. Hoechstens 10 Zeilen.",
        temp=0.4),
}


def load_tasks():
    tasks = {k: dict(v) for k, v in TASKS.items()}
    if TASKFILE.exists():
        try:
            for name, spec in json.loads(TASKFILE.read_text(encoding="utf-8")).items():
                base = tasks.get(name, {"desc": "(eigene Aufgabe)", "temp": 0.3})
                base.update(spec)
                tasks[name] = base
        except Exception as e:
            print("lok: %s unlesbar (%s), ignoriert" % (TASKFILE, e), file=sys.stderr)
    return tasks


def chat(system, user, temp, think, model, url, timeout, max_tokens):
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temp,
        "stream": False,
        "cache_prompt": True,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if not think:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(
        url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    key = os.environ.get("LOK_API_KEY")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    dt = time.time() - t0
    text = data["choices"][0]["message"].get("content") or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```[a-zA-Z0-9]*\n(.*)\n```$", r"\1", text, flags=re.S).strip()
    return text, dt, data.get("usage") or {}


def build_system(spec):
    return CORE + ("\n" + ESC if spec.get("esc") else "") + "\n\n" + spec["sys"]


def log(rec):
    try:
        HOME.mkdir(parents=True, exist_ok=True)
        with LOGFILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def cmd_batch(argv, tasks):
    """Eine Aufgabe ueber viele Eingaben laufen lassen, wiederaufsetzbar.

    Zwei Modi:
      Dateien: jede Datei ist eine Eingabe, Ergebnis landet als Datei in --out
      --lines: jede Zeile einer Textdatei ist eine Eingabe, Ergebnis als JSONL
    """
    p = argparse.ArgumentParser(
        prog="lok batch",
        description="Aufgabe ueber viele Eingaben. Bricht sauber ab und setzt wieder auf.")
    p.add_argument("task")
    p.add_argument("input", help="Glob, Verzeichnis, oder Textdatei bei --lines")
    p.add_argument("--lines", action="store_true", help="jede Zeile ist eine Eingabe")
    p.add_argument("-o", "--out", help="Zielverzeichnis, bzw. Ziel-JSONL bei --lines")
    p.add_argument("--suffix", default="", help="an den Zieldateinamen anhaengen, z.B. .en")
    p.add_argument("-c", "--ctx", default="", help="Schema, Labels, Zielsprache")
    p.add_argument("--think", dest="think", action="store_true", default=None)
    p.add_argument("--no-think", dest="think", action="store_false")
    p.add_argument("--temp", type=float)
    p.add_argument("--max-tokens", type=int, default=0)
    p.add_argument("--model", default=MODEL)
    p.add_argument("--url", default=URL)
    p.add_argument("--timeout", type=float, default=TIMEOUT)
    p.add_argument("--limit", type=int, default=0, help="nur die ersten N Eintraege")
    p.add_argument("--retry-escalated", action="store_true", help="Eskalierte erneut versuchen")
    p.add_argument("--state", help="Fortschrittsdatei (Default: unter LOK_HOME)")
    p.add_argument("--overwrite", action="store_true", help="Zieldateien ueberschreiben")
    p.add_argument("--dry-run", action="store_true", help="nur zeigen, was liefe")
    a = p.parse_args(argv[2:])

    if a.task not in tasks:
        print("lok: unbekannte Aufgabe '%s'" % a.task, file=sys.stderr)
        return 64
    spec = tasks[a.task]

    # --- Eingaben sammeln -------------------------------------------------
    src = Path(a.input)
    if a.lines:
        if not src.is_file():
            print("lok: --lines braucht eine Textdatei, '%s' ist keine" % a.input, file=sys.stderr)
            return 64
        raw = src.read_text(encoding="utf-8", errors="replace").splitlines()
        items = [(i, ln.strip()) for i, ln in enumerate(raw) if ln.strip()]
        keyof = lambda it: "line:%d" % it[0]
    else:
        if src.is_dir():
            paths = sorted(q for q in src.iterdir() if q.is_file())
        else:
            paths = sorted(Path(q) for q in globmod.glob(a.input, recursive=True)
                           if os.path.isfile(q))
        items = [(i, q) for i, q in enumerate(paths)]
        keyof = lambda it: str(it[1].resolve())
        if not a.out:
            print("lok: Dateimodus braucht -o ZIELVERZEICHNIS", file=sys.stderr)
            return 64
        outdir = Path(a.out)
        if not a.dry_run:
            outdir.mkdir(parents=True, exist_ok=True)

    if not items:
        print("lok: keine Eingaben gefunden fuer '%s'" % a.input, file=sys.stderr)
        return 64
    if a.limit:
        items = items[:a.limit]

    # --- Fortschrittsdatei ------------------------------------------------
    jid = hashlib.sha1(("%s|%s|%s|%s" % (a.task, Path(a.input).resolve(), a.lines, a.ctx))
                       .encode("utf-8")).hexdigest()[:12]
    statefile = Path(a.state) if a.state else HOME / ("batch-%s.jsonl" % jid)
    done = {}
    if statefile.exists():
        for line in statefile.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("escalated") and a.retry_escalated:
                continue
            done[r.get("key")] = r

    todo = [it for it in items if keyof(it) not in done]
    print("Aufgabe %s | %d Eintraege, %d schon erledigt, %d offen | Status: %s"
          % (a.task, len(items), len(items) - len(todo), len(todo), statefile), file=sys.stderr)
    if a.dry_run:
        for it in todo[:20]:
            print("  " + keyof(it), file=sys.stderr)
        if len(todo) > 20:
            print("  ... und %d weitere" % (len(todo) - 20), file=sys.stderr)
        return 0
    if not todo:
        return 0

    system = build_system(spec)
    temp = a.temp if a.temp is not None else spec.get("temp", 0.3)
    think = a.think if a.think is not None else bool(spec.get("think"))
    HOME.mkdir(parents=True, exist_ok=True)
    outfh = None
    if a.lines and a.out:
        outfh = open(a.out, "a", encoding="utf-8")

    n_ok = n_esc = n_err = 0
    durations = []
    t_start = time.time()
    try:
        for n, it in enumerate(todo, 1):
            key = keyof(it)
            if a.lines:
                body, label = it[1], "Zeile %d" % (it[0] + 1)
            else:
                body = it[1].read_text(encoding="utf-8", errors="replace")
                label = it[1].name
            user = a.ctx.strip() + "\n\n---\n" + body if a.ctx.strip() else body

            try:
                text, dt, usage = chat(system, user, temp, think, a.model, a.url,
                                       a.timeout, a.max_tokens)
                err = None
            except Exception as e:
                text, dt, usage, err = "", 0.0, {}, str(e)

            esc = bool(text) and text.upper().startswith("ESKALIEREN")
            if err:
                n_err += 1
                status = "FEHLER"
            elif esc:
                n_esc += 1
                status = "eskaliert"
            else:
                n_ok += 1
                status = "ok"
                if a.lines:
                    rec = json.dumps({"input": body, "result": text}, ensure_ascii=False)
                    (outfh.write(rec + "\n"), outfh.flush()) if outfh else print(rec)
                else:
                    target = outdir / (it[1].name + a.suffix)
                    if target.resolve() == it[1].resolve() and not a.overwrite:
                        print("lok: %s wuerde die Quelle ueberschreiben, uebersprungen "
                              "(--suffix oder --overwrite)" % target, file=sys.stderr)
                        n_ok -= 1
                        n_err += 1
                        status = "FEHLER"
                    else:
                        target.write_text(text.rstrip("\n") + "\n", encoding="utf-8")

            if dt:
                durations.append(dt)
            with statefile.open("a", encoding="utf-8") as sf:
                sf.write(json.dumps({"key": key, "task": a.task, "escalated": esc,
                                     "error": err, "s": round(dt, 2),
                                     "out": usage.get("completion_tokens")},
                                    ensure_ascii=False) + "\n")
            log({"ts": time.time(), "task": a.task, "escalated": esc, "s": round(dt, 2),
                 "in": usage.get("prompt_tokens"), "out": usage.get("completion_tokens"),
                 "think": think, "batch": True})

            eta = ""
            if durations and n < len(todo):
                eta = "  ETA %s" % _dur(statistics.median(durations) * (len(todo) - n))
            print("[%d/%d] %-34s %5.1fs  %s%s"
                  % (n, len(todo), label[:34], dt, status,
                     "" if not err else " " + err[:60]) + eta, file=sys.stderr)
    except KeyboardInterrupt:
        print("\nabgebrochen - erneut aufrufen setzt an dieser Stelle wieder auf",
              file=sys.stderr)
    finally:
        if outfh:
            outfh.close()

    print("-" * 60, file=sys.stderr)
    print("ok %d | eskaliert %d | Fehler %d | Gesamt %s"
          % (n_ok, n_esc, n_err, _dur(time.time() - t_start)), file=sys.stderr)
    if n_esc:
        print("Eskalierte erneut versuchen: --retry-escalated", file=sys.stderr)
    return 0 if not n_err else 1


def _dur(sec):
    sec = int(sec)
    if sec < 60:
        return "%ds" % sec
    if sec < 3600:
        return "%dm %02ds" % (sec // 60, sec % 60)
    return "%dh %02dm" % (sec // 3600, (sec % 3600) // 60)


def cmd_tasks(tasks):
    width = max(len(k) for k in tasks)
    for name in sorted(tasks):
        print("  %s  %s" % (name.ljust(width), tasks[name]["desc"]))
    print('\nEigene Aufgaben: %s' % TASKFILE)
    print('Format: {"name": {"sys": "...", "desc": "...", "temp": 0.3}}')
    return 0


def cmd_stats(days):
    if not LOGFILE.exists():
        print("Noch keine Laeufe protokolliert.")
        return 0
    cutoff = time.time() - days * 86400 if days else 0
    rows = []
    for line in LOGFILE.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("ts", 0) >= cutoff:
            rows.append(r)
    if not rows:
        print("Keine Laeufe im Zeitraum.")
        return 0
    by = {}
    for r in rows:
        by.setdefault(r.get("task", "?"), []).append(r)
    print("%-10s%5s%9s%10s%8s%12s" % ("Aufgabe", "n", "Eskal.", "Median s", "t/s", "Prompt-Tok"))
    print("-" * 54)
    for task in sorted(by, key=lambda t: -len(by[t])):
        rs = by[task]
        esc = sum(1 for r in rs if r.get("escalated"))
        secs = [r["s"] for r in rs if r.get("s")]
        tps = [r["out"] / r["s"] for r in rs if r.get("s") and r.get("out")]
        ptk = [r["in"] for r in rs if r.get("in")]
        print("%-10s%5d%8.0f%%%10.1f%8.1f%12.0f" % (
            task, len(rs), esc / len(rs) * 100,
            statistics.median(secs) if secs else 0,
            statistics.median(tps) if tps else 0,
            statistics.median(ptk) if ptk else 0))
    total_esc = sum(1 for r in rows if r.get("escalated"))
    print("-" * 54)
    print("%-10s%5d%8.0f%%" % ("gesamt", len(rows), total_esc / len(rows) * 100))
    if total_esc / len(rows) > 0.3:
        print("\n> Ueber 30% Eskalation: der Aufgabenzuschnitt passt nicht, nicht der Prompt.")
    return 0


def cmd_ping(url, timeout):
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/models", timeout=min(timeout, 10)) as r:
            data = json.loads(r.read().decode("utf-8"))
        ids = [m.get("id") for m in data.get("data", []) if m.get("id")]
        print("ok: %s  Modelle: %s" % (url, ", ".join(ids) or "(keine Angabe)"))
        return 0
    except Exception as e:
        print("nicht erreichbar: %s (%s)" % (url, e), file=sys.stderr)
        return 1


def main(argv):
    tasks = load_tasks()
    if len(argv) > 1 and argv[1] == "tasks":
        return cmd_tasks(tasks)
    if len(argv) > 1 and argv[1] == "batch":
        return cmd_batch(argv, tasks)
    if len(argv) > 1 and argv[1] == "stats":
        p = argparse.ArgumentParser(prog="lok stats")
        p.add_argument("--days", type=int, default=0, help="nur die letzten N Tage")
        return cmd_stats(p.parse_args(argv[2:]).days)

    p = argparse.ArgumentParser(
        prog="lok",
        description="Kleine Aufgaben an das lokale Modell geben. 'lok tasks' listet die "
                    "Aufgabentypen, 'lok stats' zeigt die Eskalationsquote.",
        epilog="Text kommt aus dem Argument, aus -f oder von stdin. "
               "Exit 0 = Ergebnis, 2 = eskaliert, 3 = Server weg, 64 = Bedienfehler.")
    p.add_argument("task", help="Aufgabentyp, oder 'ping'")
    p.add_argument("text", nargs="*", help="Eingabetext")
    p.add_argument("-f", "--file", help="Eingabe aus Datei")
    p.add_argument("-c", "--ctx", default="", help="Zusatzangabe: Schema, Labels, Zielsprache")
    p.add_argument("--think", dest="think", action="store_true", default=None,
                   help="Reasoning erzwingen (langsam, aber genau beim Zaehlen)")
    p.add_argument("--no-think", dest="think", action="store_false",
                   help="Reasoning abschalten, auch wenn der Aufgabentyp es vorsieht")
    p.add_argument("--temp", type=float, help="Temperatur ueberschreiben")
    p.add_argument("--max-tokens", type=int, default=0)
    p.add_argument("--model", default=MODEL)
    p.add_argument("--url", default=URL)
    p.add_argument("--timeout", type=float, default=TIMEOUT)
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="Ergebnis und Metriken als JSON")
    p.add_argument("-q", "--quiet", action="store_true", help="keine Metrikzeile auf stderr")
    p.add_argument("--no-log", action="store_true")
    a = p.parse_args(argv[1:])

    if a.task == "ping":
        return cmd_ping(a.url, a.timeout)
    if a.task not in tasks:
        print("lok: unbekannte Aufgabe '%s'. Bekannt:" % a.task, file=sys.stderr)
        print(", ".join(sorted(tasks)), file=sys.stderr)
        return 64

    parts = []
    if a.file:
        parts.append(Path(a.file).read_text(encoding="utf-8", errors="replace"))
    if a.text:
        parts.append(" ".join(a.text))
    if not parts and not sys.stdin.isatty():
        parts.append(sys.stdin.read())
    body = "\n\n".join(x for x in parts if x.strip())
    if not body.strip():
        print("lok: keine Eingabe (Argument, -f oder stdin)", file=sys.stderr)
        return 64

    spec = tasks[a.task]
    system = CORE + ("\n" + ESC if spec.get("esc") else "") + "\n\n" + spec["sys"]
    user = a.ctx.strip() + "\n\n---\n" + body if a.ctx.strip() else body
    temp = a.temp if a.temp is not None else spec.get("temp", 0.3)
    think = a.think if a.think is not None else bool(spec.get("think"))

    try:
        text, dt, usage = chat(system, user, temp, think, a.model, a.url,
                               a.timeout, a.max_tokens)
    except urllib.error.URLError as e:
        print("lok: kein Kontakt zu %s (%s). Laeuft llama-server?" % (a.url, e.reason),
              file=sys.stderr)
        return 3
    except Exception as e:
        print("lok: Fehler (%s)" % e, file=sys.stderr)
        return 3

    escalated = text.upper().startswith("ESKALIEREN")
    if not a.no_log:
        log({"ts": time.time(), "task": a.task, "escalated": escalated,
             "s": round(dt, 2), "in": usage.get("prompt_tokens"),
             "out": usage.get("completion_tokens"), "think": think})

    if a.as_json:
        print(json.dumps({"task": a.task, "escalated": escalated, "result": text,
                          "seconds": round(dt, 2), "usage": usage}, ensure_ascii=False))
        return 2 if escalated else 0

    if escalated:
        print(text, file=sys.stderr)
        return 2
    print(text)
    if not a.quiet:
        out = usage.get("completion_tokens") or 0
        tps = ("%.1f t/s" % (out / dt)) if dt and out else "-"
        print("[%s %.1fs %s->%s tok %s]" % (a.task, dt, usage.get("prompt_tokens", "?"),
                                            out or "?", tps), file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(130)
