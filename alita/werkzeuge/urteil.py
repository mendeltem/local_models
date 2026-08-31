"""Stufe 2 der Laufwache -- der Modellaufruf, reparierte Fassung.

Ersetzt `referenz/watcher.py`. Drei Aenderungen gegenueber der Vorlage, alle
am 27.08.2026 auf dieser Maschine gemessen (siehe BEFUND.md):

1. **Label auf Token 1, mit Schalter fuer spaetes Constrainen.** Ein erster
   Durchlauf ergab 1/4 fuer frueh und 3/4 fuer spaet und war der Grund,
   hier zunaechst `frei_denken=True` vorzugeben. Diese Zahl war falsch: die
   Zeitueberschreitungen des alten `watcher.py` wurden zu `ok_weiter`, die
   vermeintlichen Urteile waren Rueckfallwerte -- derselbe Fehler aus Punkt 2
   hat also die Messung ueber ihn verdorben (LAUFWAECHTER-BEFUND.md, Abschn. 2).
   Mit reparierter Grammatik nachgemessen liefern **beide** Varianten 3 von 4,
   und es faellt dieselbe Klasse durch. Spaetes Constrainen kostet dabei rund
   600 zusaetzliche Token je Aufruf. Vorgabe ist deshalb `frei_denken=False`;
   der Schalter bleibt, weil vier Beispiele kein Testsatz sind, mit dem sich
   das allgemein entscheiden liesse.

2. **`unentschieden` ist ein eigenes Ergebnis.** Die Vorlage gab bei JEDEM
   Fehler `ok_weiter` zurueck -- kein Backend, Zeitueberschreitung, kaputte
   Grammatik, leere Antwort. Die Grammatik war kaputt, also haette sie immer
   "alles in Ordnung" gesagt, ohne dass es auffaellt. Wer nicht urteilen
   konnte, sagt das jetzt.

3. **Fehler werden benannt, nicht verschluckt.** Jeder Rueckgabewert traegt,
   woher er kommt und was schiefging.

Die Richtung der Vorsicht bleibt: im Zweifel zwischen `ok_weiter` und einem
Abbruch gilt `ok_weiter`. Aber "ich konnte nicht" ist kein Zweifel, sondern
ein Ausfall, und der gehoert der Zustandsmaschine gemeldet.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

LABELS = frozenset({
    "ok_weiter",
    "wiederholung_erkannt_abbruch",
    "eskalation_cloud",
    "statusdatei_widerspricht_log",
})

UNENTSCHIEDEN = "unentschieden"

HIER = Path(__file__).resolve().parent
GRAMMATIK = HIER / "grammatik" / "watcher.gbnf"
VORLAGE = HIER / "prompt-vorlage.md"

GROSSES_MODELL = "http://127.0.0.1:8000"
KLEINES_MODELL = "http://127.0.0.1:8002"


@dataclass
class Urteil:
    """Was die Wache sagt -- samt Herkunft und, wenn noetig, Ursache."""

    label: str
    herkunft: str
    grund: str = ""
    analyse: str = ""

    @property
    def entschieden(self) -> bool:
        return self.label in LABELS

    def __str__(self) -> str:
        s = f"{self.label} ({self.herkunft})"
        return f"{s}: {self.grund}" if self.grund else s


def nachvalidieren(roh: str) -> str | None:
    """Die einzige Stelle, an der eine Modellausgabe zum Label wird.

    Nicht optional: llama-server kann bei fehlgeschlagenem Grammar-Parsing
    ohne Constraint weiterlaufen. Der Zwang garantiert die Form nur, solange
    er ueberhaupt greift.
    """
    kandidat = roh.strip().strip('"').strip().lower()
    if kandidat in LABELS:
        return kandidat
    for label in LABELS:
        if kandidat.startswith(label):
            return label
    return None


def laeuft(basis: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"{basis}/health", timeout=timeout) as antwort:
            return antwort.status == 200
    except (urllib.error.URLError, OSError):
        return False


def frage_server(
    basis: str,
    prompt: str,
    grammatik: str | None = None,
    n_predict: int = 12,
    timeout: float = 120.0,
) -> tuple[str | None, str]:
    """Ein Aufruf gegen llama-server. Liefert (inhalt, fehlergrund)."""
    nutzlast: dict = {
        "prompt": prompt,
        "temperature": 0.0,
        "n_predict": n_predict,
        "cache_prompt": True,
    }
    if grammatik:
        nutzlast["grammar"] = grammatik

    anfrage = urllib.request.Request(
        f"{basis}/completion",
        data=json.dumps(nutzlast).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=timeout) as antwort:
            return json.loads(antwort.read()).get("content", ""), ""
    except urllib.error.HTTPError as e:
        # Genau hier lag der Fehler: HTTP 400 wegen unparsbarer Grammatik.
        # Frueher wurde das zu ok_weiter. Jetzt steht es im Grund.
        try:
            meldung = json.loads(e.read()).get("error", {}).get("message", "")
        except Exception:
            meldung = ""
        return None, f"HTTP {e.code} {meldung}".strip()
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as e:
        return None, f"{type(e).__name__}: {e}"


def frage_cli(
    modell: Path, prompt: str, threads: int = 3, timeout: float = 180.0
) -> tuple[str | None, str]:
    """Rueckfall ohne laufenden Server.

    `threads` bewusst klein. CPU-Inferenz ist speicherbandbreitengebunden,
    nicht rechengebunden -- mehr Kerne nehmen dem Haupttraining Bandbreite
    weg, ohne selbst schneller zu werden.
    """
    befehl = [
        "llama-cli", "-m", str(modell),
        "--grammar-file", str(GRAMMATIK),
        "-p", prompt, "-n", "12", "--temp", "0",
        "--threads", str(threads), "--no-display-prompt",
    ]
    try:
        fertig = subprocess.run(
            befehl, capture_output=True, text=True, timeout=timeout, check=False
        )
        if fertig.returncode != 0:
            return None, f"llama-cli Rueckgabewert {fertig.returncode}"
        return fertig.stdout, ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return None, f"{type(e).__name__}: {e}"


def lade_vorlage() -> tuple[str, str]:
    """Systemprompt und Few-Shot-Block aus prompt-vorlage.md.

    Die Vorlage ist die Wahrheit ueber die vier Klassen; sie hier noch einmal
    hinzuschreiben hiesse, zwei Fassungen zu pflegen.
    """
    text = VORLAGE.read_text(encoding="utf-8")
    entruecken = lambda s: "\n".join(
        z[4:] if z.startswith("    ") else z for z in s.strip().splitlines()
    )
    system = entruecken(text.split("## Systemprompt")[1].split("## Nutzerprompt")[0])
    beispiele = entruecken(text.split("## Few-Shot-Beispiele")[1])
    return system, beispiele


def urteile(
    statusdatei: str,
    logzeilen: list[str],
    stufe1_befund: str,
    systemprompt: str | None = None,
    beispiele: str | None = None,
    kleines_modell_datei: Path | None = None,
    frei_denken: bool = False,
) -> Urteil:
    """Liefert ein Urteil -- oder sagt, dass es keines faellen konnte.

    `frei_denken=True` laesst das Modell erst frei analysieren und constrained
    erst das Label. Auf den vier Beispielen aus `prompt-vorlage.md` bringt das
    nichts -- 3 von 4 wie ohne, dieselbe Klasse faellt durch -- und kostet rund
    600 Token je Aufruf. Deshalb nicht die Vorgabe. Bei einem groesseren
    Testsatz ist die Frage neu zu stellen.
    """
    if systemprompt is None or beispiele is None:
        try:
            s, b = lade_vorlage()
        except (OSError, IndexError) as e:
            return Urteil(UNENTSCHIEDEN, "vorlage", f"prompt-vorlage.md unlesbar: {e}")
        systemprompt = systemprompt if systemprompt is not None else s
        beispiele = beispiele if beispiele is not None else b

    try:
        grammatik = GRAMMATIK.read_text(encoding="utf-8")
    except OSError as e:
        # Ohne Grammatik lieber gar nicht fragen als unkontrolliert fragen.
        return Urteil(UNENTSCHIEDEN, "grammatik", f"{GRAMMATIK} unlesbar: {e}")

    ausschnitt = "\n".join(logzeilen[-40:])
    basis = (
        f"{systemprompt}\n\n{beispiele}\n\n"
        f"STATUSDATEI:\n{statusdatei}\n\n"
        f"LOG, letzte {min(len(logzeilen), 40)} Zeilen:\n{ausschnitt}\n\n"
        f"STUFE-1-BEFUND:\n{stufe1_befund}\n\n"
    )

    gruende: list[str] = []
    for server, name in ((GROSSES_MODELL, "27b"), (KLEINES_MODELL, "0.5b-server")):
        if not laeuft(server):
            gruende.append(f"{name}: antwortet nicht")
            continue

        analyse = ""
        if frei_denken:
            analyse, fehler = frage_server(server, basis + "Analyse:", n_predict=600)
            if not analyse or not analyse.strip():
                # Leer ist nicht dasselbe wie unauffaellig. Ohne Analyse
                # waere der zweite Aufruf wieder der blinde Fall.
                gruende.append(f"{name}: freie Analyse leer ({fehler or 'kein Grund'})")
                continue
            prompt = basis + "Analyse:" + analyse + "\n\nLabel:"
        else:
            prompt = basis + "Label:"

        roh, fehler = frage_server(server, prompt, grammatik=grammatik)
        if roh is None:
            gruende.append(f"{name}: {fehler}")
            continue
        label = nachvalidieren(roh)
        if label:
            return Urteil(label, name, analyse=analyse.strip())
        gruende.append(f"{name}: Ausgabe ausserhalb der erlaubten Menge: {roh!r:.60}")

    if kleines_modell_datei and kleines_modell_datei.exists():
        roh, fehler = frage_cli(kleines_modell_datei, basis + "Label:")
        if roh:
            label = nachvalidieren(roh)
            if label:
                return Urteil(label, "0.5b-cli")
            gruende.append(f"0.5b-cli: Ausgabe ungueltig: {roh!r:.60}")
        else:
            gruende.append(f"0.5b-cli: {fehler}")

    return Urteil(UNENTSCHIEDEN, "kein-backend", "; ".join(gruende))
