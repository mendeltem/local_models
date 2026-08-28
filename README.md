# local_models

Lokale LLMs auf Consumer-Hardware betreiben — Werkzeuge, Messmethoden und
Betriebsregeln. Kein Framework, sondern das Minimum, das man braucht, um ein
MoE-Modell auf einer Maschine mit zu wenig VRAM sinnvoll zu nutzen.

Der Kern des Repos ist eine Haltung: **messen statt schätzen.** Jede Zahl hier
stammt aus einem Lauf auf echter Hardware, nicht aus einer Modellkarte.

## Was hier drin ist

| | |
|---|---|
| [`tools/lok.py`](tools/lok.py) | CLI für kleine Aufgaben am lokalen Modell — feste Ausgabeformate, Eskalationsregel, Batch-Modus, Statistik |
| [`tools/detect.py`](tools/detect.py) | misst GPU, RAM und Modell und berechnet die Startparameter — der Grund, warum das Repo auf fremder Hardware funktioniert |
| [`tools/start-llm.ps1`](tools/start-llm.ps1) | Startskript für `llama-server` unter Windows |
| [`tools/stimme/`](tools/stimme/) | Text zu Sprache auf derselben Karte — geklonte Stimmen aus 8-KB-Vorlagen, ohne Netz |
| [`docker/`](docker/) | dasselbe als Container, für andere Workstations |
| [`docs/`](docs/) | Einrichtung, Tuning-Methode, Modell-Wiki |
| [`alita/`](alita/) | ein lokales agentisches System: ein Agent, der unbeaufsichtigt auf Daten arbeitet, die den Rechner nicht verlassen duerfen — Tafel, Wachen, Messwerkzeuge ([English](alita/README.md)) |

## Schnellstart

```bash
# 1. llama.cpp besorgen (siehe docs/01-setup.md)
# 2. Ein GGUF-Modell besorgen
# 3. Maschine vermessen und Profil erzeugen
python tools/detect.py /pfad/zum/modell.gguf -o tools/profiles/$(hostname).json

# 4. Server starten (Windows)
powershell -ExecutionPolicy Bypass -File tools/start-llm.ps1

# 5. Prüfen
python tools/lok.py ping
python tools/lok.py en "Der Server laeuft."
```

Die grafische Oberfläche musst du nicht installieren: `llama-server` bringt eine
mit, erreichbar unter `http://127.0.0.1:8080`.

## Dokumentation

- **[01 — Einrichtung](docs/01-setup.md)** — llama.cpp und Modell unter Windows, von null auf laufend
- **[02 — Tuning](docs/02-tuning.md)** — wie man herausfindet, was auf die eigene GPU passt, und was das bringt
- **[03 — Modell-Wiki](docs/03-model-wiki.md)** — welche Aufgabe mit welchen Einstellungen, und wo das Modell zuverlässig scheitert
- **[04 — Docker](docs/04-docker.md)** — dieselbe Umgebung auf anderen Workstations

## Referenzsystem

Alle Messungen in diesem Repo stammen von dieser Maschine:

| | |
|---|---|
| GPU | RTX 4070 Laptop, 8 GB VRAM |
| CPU | Ryzen 7 7840HS, 8 Kerne / 16 Threads |
| RAM | 31,3 GB DDR5 |
| Modell | Qwen3.6-35B-A3B, GGUF `UD-IQ4_XS`, 17,7 GB |
| llama.cpp | b10603, CUDA 13.3 |

Ergebnis nach dem Tuning aus [docs/02](docs/02-tuning.md): **19,4 Token/s** beim
Decoding, **306 Token/s** beim warmen Prefill. Ein 35-B-Modell auf einem Laptop
mit 8 GB VRAM, interaktiv benutzbar.

## Was portabel ist und was nicht

Alles in diesem Repo ist maschinenunabhängig. Die maschinenspezifischen Werte
— Pfade, `-ncmoe`, Threads, Lademodus — stehen in `tools/profiles/*.json`, werden
von `detect.py` **erzeugt** und von `.gitignore` ausgeschlossen.

Auf einer neuen Workstation kopierst du das Repo, rufst einmal `detect.py` und
hast ein passendes Profil. Keine Handarbeit, kein Abschreiben von Werten, die
für eine andere GPU galten.
