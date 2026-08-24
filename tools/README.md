# lok

Kleiner CLI-Router auf ein lokales llama-server-Modell (OpenAI-kompatible API).
Keine Abhängigkeiten außer Python 3.9+.

Prinzip: **ein kurzer System-Prompt pro Aufgabentyp** statt eines großen Allzweck-Prompts.
Der Prefill läuft bei einer MoE mit `--n-cpu-moe` auf der CPU und wird bei jedem Turn neu
gerechnet — jeder gesparte System-Token zahlt sich bei jedem Aufruf aus. Aktuell ~130 Token
Systemanteil pro Aufruf.

Zweite Hälfte des Prinzips: die **Abbruchregel**. Kann das Modell die Aufgabe nicht sauber
lösen (Websuche, aktuelle Fakten, mehr als 30 Zeilen Code, mehrere Dateien, offene Bewertung),
antwortet es `ESKALIEREN: <Grund>`. Dann geht nichts nach stdout, der Exit-Code ist 2, und die
Aufgabe wandert an das große Modell. Die Ersparnis entsteht an dieser Grenze, nicht am Prompt.

## Server

```powershell
C:\Users\Mendel\Projects\lok\start-llm.ps1
```

Das Skript startet `llama-server` mit geprüften Flags für diese Maschine
(RTX 4070 Laptop 8 GB, Ryzen 7 7840HS, 31 GB RAM, Build b10603).
Tuning läuft über einen Parameter:

```powershell
C:\Users\Mendel\Projects\lok\start-llm.ps1 -NCpuMoe 40
```

`-NCpuMoe` (= `-ncmoe`) hält die Expert-Layer der ersten N Layer auf der CPU. Mit 99 starten,
dann schrittweise senken (99 → 40 → 34 → 30), bis der Start an VRAM scheitert; eine Stufe
zurück ist der Wert. Jede Stufe bringt ein paar Prozent.

Zwei Flags aus älteren Anleitungen sind in b10603 überholt: `--jinja` ist **Default**, und für
Thinking gibt es jetzt `-rea on|off|auto` plus `--reasoning-budget` statt der
`--chat-template-kwargs`-Krücke. `-fa` nimmt optional `on|off|auto`.

## Benutzung

```bash
python lok.py ping
python lok.py tasks
python lok.py kurz "langer Text ..."
python lok.py en -f notiz.md
git diff --staged | python lok.py commit -q
python lok.py json -c "Felder: name, datum, betrag" -f rechnung.txt
python lok.py label -c "Labels: bug, feature, frage" "App stuerzt beim Start ab"
python lok.py stats --days 14
```

Eingabe kommt aus dem Argument, aus `-f DATEI` oder von stdin (Pipe).
Das Ergebnis geht nach stdout, die Metrikzeile nach stderr — `-q` schaltet sie ab,
`--json` gibt Ergebnis plus Messwerte als JSON aus.

## Batch

Der Modus, in dem sich das lokale Modell wirklich rechnet: viele gleichartige Eingaben,
unbeaufsichtigt, ohne Kosten und ohne Rate Limit.

**Dateimodus** — jede Datei eine Eingabe, Ergebnis als Datei:

```bash
python lok.py batch en docs/ -o docs_en --suffix .en
```

**Zeilenmodus** — jede Zeile einer Textdatei eine Eingabe, Ergebnis als JSONL:

```bash
python lok.py batch label tickets.txt --lines -c "Labels: bug, feature, frage" -o labels.jsonl
```

Beides ist **wiederaufsetzbar**: nach jedem Eintrag wird der Fortschritt in
`~/.lok/batch-<id>.jsonl` festgehalten. Ctrl+C oder Absturz kosten höchstens den laufenden
Eintrag — derselbe Aufruf macht dort weiter, wo er aufgehört hat. Eskalierte Einträge bleiben
liegen und lassen sich später mit `--retry-escalated` nachziehen.

Vorher ansehen, was liefe: `--dry-run`. Erst mal klein testen: `--limit 5`.

Der Fortschritt geht nach stderr (mit ETA aus dem Median der bisherigen Läufe), im
Zeilenmodus ohne `-o` das JSONL nach stdout — damit bleibt die Pipe nutzbar.

## Exit-Codes

| Code | Bedeutung |
|---|---|
| 0 | Ergebnis auf stdout |
| 2 | eskaliert, Grund auf stderr, stdout leer |
| 3 | Server nicht erreichbar oder API-Fehler |
| 64 | unbekannte Aufgabe / keine Eingabe |

Damit lässt sich der Fallback in einem Skript verdrahten:

```bash
python lok.py um "$TEXT" || echo "geht ans grosse Modell"
```

## Aufgabentypen

`kurz um fix de en tldr json label regex sh commit name doc err ask`

`ask` ist der Fallback ohne festes Format — bewusst der schwächste Modus, weil kleine Modelle
an offenen Aufgaben scheitern. Wenn du ihn oft brauchst, fehlt ein eigener Typ.

## Eigene Aufgabentypen

`~/.lok/tasks.json` überschreibt und ergänzt die eingebauten:

```json
{
  "sql": {
    "desc": "SQL aus Beschreibung",
    "sys": "Gib eine einzelne SQL-Abfrage aus, keine Erklaerung, kein Codefence. Nur Tabellen und Spalten, die im Text vorkommen.",
    "temp": 0.1
  },
  "sh": { "sys": "Gib einen bash-Einzeiler aus: erste Zeile der Befehl, zweite Zeile was er tut." }
}
```

## Umgebungsvariablen

`LOK_URL` (Default `http://localhost:8080/v1`), `LOK_MODEL`, `LOK_TIMEOUT`,
`LOK_HOME` (Default `~/.lok`), `LOK_API_KEY`.

## Messen

Jeder Lauf landet in `~/.lok/log.jsonl`. `lok stats` zeigt pro Aufgabentyp: Anzahl,
Eskalationsquote, Median-Dauer, t/s, Prompt-Tokens.

Abnahmekriterium: liegt die Eskalationsquote eines Typs dauerhaft über ~30 %, liegt es am
Zuschnitt der Aufgabe, nicht am Prompt — diese Kategorie gar nicht erst lokal schicken.

## PowerShell-Alias

```powershell
Set-Alias lok C:\Users\Mendel\Projects\lok\lok.cmd
```

(dauerhaft: Zeile in `$PROFILE` eintragen)

## Thinking

Ist per Default aus (`chat_template_kwargs: {"enable_thinking": false}` im Request). Für
Umformulieren, Regex oder Klassifikation bringt es nichts und kostet bei 15 t/s die halbe
Wartezeit. `--think` schaltet es fallweise an.

Falls das Modell den Request-Schalter ignoriert (an `<think>`-Blöcken bzw. hohen
Completion-Token-Zahlen in der Metrikzeile erkennbar): serverseitig mit `-rea off` abschalten.
Dann wirkt `--think` allerdings nicht mehr.

## Setup-Stand

Installiert am 24.08.2026: llama.cpp b10603 (CUDA 13.3) in `C:\Users\Mendel\llama.cpp`,
Modell `Qwen3.6-35B-A3B-UD-IQ4_XS.gguf` (17,7 GB) in `C:\Users\Mendel\models`.
Die Setup-Zips liegen noch in `C:\Users\Mendel\llama.cpp\_dl` (537 MB) und können weg.
