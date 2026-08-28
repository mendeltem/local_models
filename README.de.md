# local_models

*[English version: README.md](README.md)*

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
| [`alita/system.html`](alita/system.html) | **Systemübersicht der Workstation als eine Seite** — Hardware, Dienste, Modelle, Messwerte und ein Flussdiagramm; ohne Netz lauffähig, zweisprachig |
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

## Wo die Ergebnisse liegen

Was diese Maschine tatsaechlich rechnet, wird getrennt veroeffentlicht -- damit
dieses Repository ein Werkzeugkasten bleibt und keine Ergebnishalde:

**<https://mendeltem.github.io/clara_working_station/>** -- eine Adresse fuer
alle Projekte, darunter die WMH-Qualitaetskontrolle (elf Segmentierungs-
verfahren je Patient, multiplanar und 3D, ohne externe Anfragen).

Veroeffentlicht wird dort nur, was auf oeffentlichen Datensaetzen gerechnet
wurde. Patientendaten und Ergebnisse auf eigenen Kohorten bleiben auf der
Maschine.

## Dokumentation

- **[01 — Einrichtung](docs/01-setup.md)** — llama.cpp und Modell unter Windows, von null auf laufend
- **[02 — Tuning](docs/02-tuning.md)** — wie man herausfindet, was auf die eigene GPU passt, und was das bringt
- **[03 — Modell-Wiki](docs/03-model-wiki.md)** — welche Aufgabe mit welchen Einstellungen, und wo das Modell zuverlässig scheitert
- **[04 — Docker](docs/04-docker.md)** — dieselbe Umgebung auf anderen Workstations

## Referenzsysteme

Die Messungen stammen aus **zwei** Maschinen. Welche gemeint ist, steht an
jeder Zahl — sie sind nicht miteinander vergleichbar.

### Laptop — die Messungen in `tools/` und `docs/`

| | |
|---|---|
| GPU | RTX 4070 Laptop, 8 GB VRAM |
| CPU | Ryzen 7 7840HS, 8 Kerne / 16 Threads |
| RAM | 31,3 GB DDR5 |
| Modell | Qwen3.6-35B-A3B, GGUF `UD-IQ4_XS`, 17,7 GB |
| llama.cpp | b10603, CUDA 13.3 |
| [`docs/05-scaffolding.md`](docs/05-scaffolding.md) | der modellunabhängige Teil: was einen Agenten fertig werden lässt, und wie man ein anderes Modell einsetzt |

Ergebnis nach dem Tuning aus [docs/02](docs/02-tuning.md): **19,4 Token/s** beim
Decoding, **306 Token/s** beim warmen Prefill. Ein 35-B-Modell auf einem Laptop
mit 8 GB VRAM, interaktiv benutzbar. **Das ist der Punkt dieses Repos:** ein
Modell nutzen, das eigentlich nicht auf die Karte passt.

### Alita — die Messungen in `alita/`

| | |
|---|---|
| GPU | RTX A5000, 24 564 MiB VRAM, Compute Capability 8.6 |
| CPU | Intel i9-12900K, 16 Kerne / 24 Threads |
| RAM | 62 GiB |
| System | Ubuntu 24.04.3, Kernel 6.14, **kein sudo** |
| Modell | Qwen3.8-27B, GGUF `UD-Q4_K_M`, 16 GB, 80k Kontext |

Eine Workstation, auf der ein Agent unbeaufsichtigt auf Daten arbeitet, die den
Rechner nicht verlassen dürfen. Hier ist der Engpass nicht die Kartengröße,
sondern dass **Sprachmodell und Training gleichzeitig** in dieselben 24,5 GiB
müssen: `llama-server` hält 21 451 MiB, für alles andere bleiben 3 113 MiB.

Die Zahlen der beiden Maschinen taugen nicht zum Vergleich — der Laptop misst,
wie weit man mit zu wenig VRAM kommt, Alita misst, was neben einem dauerhaft
geladenen Modell noch Platz hat.

## Was portabel ist und was nicht

Alles in diesem Repo ist maschinenunabhängig. Die maschinenspezifischen Werte
— Pfade, `-ncmoe`, Threads, Lademodus — stehen in `tools/profiles/*.json`, werden
von `detect.py` **erzeugt** und von `.gitignore` ausgeschlossen.

Auf einer neuen Workstation kopierst du das Repo, rufst einmal `detect.py` und
hast ein passendes Profil. Keine Handarbeit, kein Abschreiben von Werten, die
für eine andere GPU galten.
