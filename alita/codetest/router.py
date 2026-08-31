"""Waehlt ein kostenloses OpenRouter-Modell nach Aufgabenart und Kontextlaenge.

    from router import waehle
    modell = waehle("code", mindest_kontext=8000)

Warum der Katalog zur Laufzeit gelesen wird und nicht als Liste im Code steht:
kostenlose Modelle verschwinden, kommen dazu und wechseln ihre Kennung. Eine
feste Liste ist nach zwei Wochen falsch, und zwar stumm -- der Aufruf schlaegt
dann mit 404 fehl statt mit "Modell gibt es nicht mehr".

Ebenso wichtig: **eine Ausweichkette.** Freie Modelle sind ratenbegrenzt. Wer
nur eines waehlt, steht bei 429 still. `waehle` liefert deshalb eine
geordnete Liste, und der Aufrufer arbeitet sie ab.

WOFUER DAS GEDACHT IST -- und wofuer nicht:

Fuer Aufgaben ohne Patientenbezug. Der Codetest ist der Fall, fuer den es
gebaut wurde: vier Programmieraufgaben, keine Daten. Bei kostenlosen Modellen
duerfen die Anbieter Eingaben in aller Regel zum Training verwenden -- wer
nichts zahlt, zahlt mit dem, was er schickt. Alles mit Fallbezug bleibt auf
Alita.
"""

from __future__ import annotations

import json
import os
import urllib.request

KATALOG_URL = "https://openrouter.ai/api/v1/models"

# Schluesselwoerter je Aufgabenart, in der Modellkennung gesucht.
# Grob, aber nachvollziehbar -- und es steht hier statt in einem Kommentar.
NEIGUNG = {
    "code":      ("code", "coder", "devstral", "laguna", "qwen"),
    "denken":    ("reasoning", "thinking", "nemotron", "ultra", "glm", "inkling"),
    "klein":     ("nano", "mini", "small", "flash", "lite", "lfm", "2b", "3b", "4b"),
    "allgemein": (),
}


def katalog(timeout: float = 30.0) -> list[dict]:
    """Alle Modelle, deren Preis fuer Prompt UND Antwort null ist."""
    with urllib.request.urlopen(KATALOG_URL, timeout=timeout) as a:
        daten = json.load(a)
    frei = []
    for m in daten.get("data", []):
        p = m.get("pricing") or {}
        try:
            if float(p.get("prompt", "1")) != 0 or float(p.get("completion", "1")) != 0:
                continue
        except (TypeError, ValueError):
            continue
        frei.append({
            "id": m["id"],
            "kontext": m.get("context_length") or 0,
            "name": m.get("name") or m["id"],
        })
    return frei


def waehle(art: str = "allgemein", mindest_kontext: int = 0,
           ausser: tuple[str, ...] = (), modelle: list[dict] | None = None
           ) -> list[str]:
    """Geordnete Ausweichkette fuer diese Aufgabenart.

    Vorne steht, was zur Art passt und genug Kontext hat; dahinter der Rest
    als Rueckfall. Nie leer, solange der Katalog etwas hergibt -- lieber ein
    unpassendes Modell als gar keine Antwort.
    """
    if modelle is None:
        modelle = katalog()

    passend = [m for m in modelle
               if m["kontext"] >= mindest_kontext and m["id"] not in ausser]
    if not passend:
        # Kontextforderung war zu hoch -- lieber melden als still ignorieren.
        passend = [m for m in modelle if m["id"] not in ausser]
        if not passend:
            return []

    schluessel = NEIGUNG.get(art, ())

    def rang(m: dict) -> tuple:
        kennung = m["id"].lower()
        # OpenRouter markiert dauerhaft freie Textmodelle mit ":free".
        # Ohne diese Marke stehen auch Vorschauen mit Preis null in der
        # Liste -- darunter Musik- und Bildmodelle, die auf eine
        # Programmieraufgabe nie antworten koennen.
        markiert = 0 if kennung.endswith(":free") else 1
        treffer = 0 if any(s in kennung for s in schluessel) else 1
        # Bei "klein" ist wenig Kontext kein Nachteil, sonst mehr besser.
        return (markiert, treffer, m["kontext"] if art == "klein" else -m["kontext"])

    return [m["id"] for m in sorted(passend, key=rang)]


def schluessel() -> str:
    """Der Schluessel kommt aus der Umgebung, nie aus der Kommandozeile.

    Ein Schluessel in argv steht in `ps`, in der Shell-Historie und in jedem
    Prozessprotokoll. Aus der Umgebung gelesen bleibt er wenigstens dort.
    """
    s = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not s:
        raise SystemExit(
            "OPENROUTER_API_KEY ist nicht gesetzt.\n"
            "  export OPENROUTER_API_KEY=...   (Linux)\n"
            "  $env:OPENROUTER_API_KEY='...'   (PowerShell)")
    return s


if __name__ == "__main__":
    import sys
    art = sys.argv[1] if len(sys.argv) > 1 else "allgemein"
    mind = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    ms = katalog()
    print(f"{len(ms)} kostenlose Modelle im Katalog")
    print(f"\nAusweichkette fuer art={art}, mindest_kontext={mind}:\n")
    kette = waehle(art, mind, modelle=ms)
    nach_id = {m["id"]: m for m in ms}
    for i, mid in enumerate(kette[:12], 1):
        print("  %2d. %-52s %8d" % (i, mid[:52], nach_id[mid]["kontext"]))
    if len(kette) > 12:
        print("      ... und %d weitere als Rueckfall" % (len(kette) - 12))
