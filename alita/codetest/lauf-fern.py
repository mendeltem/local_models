"""Derselbe Codetest, aber gegen ein fernes Modell ueber OpenRouter.

    export OPENROUTER_API_KEY=...
    python lauf-fern.py                          # Router waehlt
    python lauf-fern.py z-ai/glm-5.2:free        # feste Kennung
    python lauf-fern.py --art denken             # andere Neigung

Der Sinn: `lauf.py` misst das lokale Modell auf Alita, dieses hier ein fernes.
**Dieselben Aufgaben, dieselbe Pruefung, dieselben Parameter** -- sonst waere
der Vergleich wertlos. Der einzige Unterschied ist das Protokoll: llama.cpp
spricht `/completion`, OpenRouter spricht `/chat/completions`.

WAS HIER RAUSGEHT: die vier Aufgabentexte aus `aufgaben.py`. Keine Daten,
keine Pfade, kein Fallbezug -- nachlesbar in derselben Datei. Fuer alles mit
Patientenbezug ist dieses Skript der falsche Weg; dafuer gibt es Alita.

WARUM EINE AUSWEICHKETTE: freie Modelle sind ratenbegrenzt. Bei 429 oder 503
geht es mit dem naechsten weiter, statt den Lauf abzubrechen. Welches Modell
tatsaechlich geantwortet hat, steht in jeder Zeile -- sonst vergleicht man
am Ende gegen etwas anderes, als man glaubt.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))          # aufgaben.py liegt daneben, nicht in /tmp

from aufgaben import AUFGABEN          # noqa: E402
from router import schluessel, waehle  # noqa: E402

URL = "https://openrouter.ai/api/v1/chat/completions"


def frage(modell: str, prompt: str, key: str, n: int = 900, timeout: float = 300.0):
    """Eine Anfrage. Gibt (text, tokens, sekunden) oder wirft.

    temperature 0 und n_predict 900 wie in `lauf.py` -- die Parameter muessen
    gleich sein, sonst misst man die Einstellung statt das Modell.
    """
    daten = json.dumps({
        "model": modell,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": n,
    }).encode()
    anfrage = urllib.request.Request(URL, data=daten, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
        # OpenRouter bittet um beides; ohne sie laeuft es auch.
        "HTTP-Referer": "https://github.com/mendeltem/local_models",
        "X-Title": "local_models codetest",
    })
    t0 = time.time()
    with urllib.request.urlopen(anfrage, timeout=timeout) as a:
        j = json.loads(a.read())
    if "choices" not in j:
        raise RuntimeError(str(j.get("error", j))[:120])
    text = j["choices"][0]["message"].get("content") or ""
    tok = (j.get("usage") or {}).get("completion_tokens", 0)
    return text, tok, time.time() - t0


def frage_mit_ausweichen(kette: list[str], prompt: str, key: str, gemieden: set):
    """Arbeitet die Kette ab, bis eines antwortet. Gibt zusaetzlich das Modell."""
    letzter = ""
    for modell in kette:
        if modell in gemieden:
            continue
        try:
            text, tok, dt = frage(modell, prompt, key)
            if text.strip():
                return text, tok, dt, modell, ""
            letzter = "leere Antwort"
        except urllib.error.HTTPError as e:
            letzter = "HTTP %d" % e.code
            if e.code in (429, 402, 503):
                gemieden.add(modell)     # ratenbegrenzt: fuer den Rest des Laufs meiden
            continue
        except Exception as e:                       # noqa: BLE001
            letzter = type(e).__name__
            continue
        gemieden.add(modell)
    return "", 0, 0.0, "", letzter or "kein Modell antwortete"


def code_holen(t: str) -> str:
    """Den Python-Block herausschneiden. Denkende Modelle schreiben davor.

    Wortgleich mit `lauf.py` -- absichtlich. Wer hier anders schneidet, misst
    das Schneiden mit.
    """
    for m in re.findall(r"```(?:python)?\n(.*?)```", t, re.S):
        if "def " in m:
            return m
    i = t.find("def ")
    return t[i:] if i >= 0 else ""


def main() -> int:
    args = [a for a in sys.argv[1:]]
    art = "code"
    if "--art" in args:
        i = args.index("--art")
        art = args[i + 1]
        del args[i:i + 2]
    festes = args[0] if args else None

    key = schluessel()
    if festes:
        kette = [festes]
        print("Modell: %s (fest vorgegeben)" % festes)
    else:
        kette = waehle(art, mindest_kontext=8000)
        if not kette:
            print("Katalog leer oder nicht erreichbar.", file=sys.stderr)
            return 1
        print("Ausweichkette (art=%s): %s" % (art, ", ".join(kette[:4])
              + (" ..." if len(kette) > 4 else "")))
    print()

    print(f"{'Aufgabe':<24}{'Ergebnis':<12}{'Token':>7}{'Zeit':>8}   "
          f"{'Modell':<34}Fehler")
    print("-" * 118)

    gemieden: set[str] = set()
    ok = 0
    gesamt_t = gesamt_s = 0.0
    for a in AUFGABEN:
        antwort, tok, dt, modell, grund = frage_mit_ausweichen(
            kette, a["prompt"], key, gemieden)
        gesamt_t += tok
        gesamt_s += dt
        fehler = ""
        if not antwort:
            stand, modell = "KEINE ANTWORT", "-"
            fehler = grund
        else:
            code = code_holen(antwort)
            if not code:
                stand = "KEIN CODE"
            else:
                raum: dict = {}
                try:
                    exec(code, raum)          # noqa: S102
                    exec(a["pruefe"], raum)   # noqa: S102
                    stand = "richtig"
                    ok += 1
                except AssertionError as e:
                    stand, fehler = "FALSCH", str(e)[:40]
                except Exception as e:        # noqa: BLE001
                    stand, fehler = type(e).__name__, str(e)[:40]
        print(f"{a['name']:<24}{stand:<12}{tok:>7}{dt:>7.1f}s   "
              f"{modell[:33]:<34}{fehler}")

    print("-" * 118)
    rate = (gesamt_t / gesamt_s) if gesamt_s > 0 else 0.0
    print(f"{ok} von {len(AUFGABEN)} richtig, {int(gesamt_t)} Token in "
          f"{gesamt_s:.0f} s ({rate:.1f} tok/s)")
    if gemieden:
        print("gemieden nach Fehler: " + ", ".join(sorted(gemieden)))
    print()
    print("Zum Vergleich, lokal auf Alita:  python lauf.py http://127.0.0.1:8000 "
          "\"Qwen3.8-27B\"")
    return 0 if ok == len(AUFGABEN) else 1


if __name__ == "__main__":
    raise SystemExit(main())
