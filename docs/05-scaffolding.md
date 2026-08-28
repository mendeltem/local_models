# Model-agnostic scaffolding

*[Deutsche Fassung weiter unten](#geruest-modellunabhaengig)*

The point of this repository is not to tune one model. It is to build the
**scaffolding an agent needs to finish work** — so that when a better model
arrives, the scaffolding still holds and only the model is swapped.

## Why scaffolding and not prompting

Measured over four jobs on one machine, with one local model:

| Job | Outcome |
|---|---|
| `unet-qc` — build a U-Net, 5-fold CV, train, produce a QC page | **finished unattended and passed acceptance** |
| `mb1` — link 424 cases into a working directory | **finished unattended** |
| `microbleed-gesamt` — "run microbleednet on the cohort and report" | ran twice for over two hours, **produced no file** |
| `mb2` — one smoke test, four cases, one question to answer | 50 minutes of reading source before the first directory appeared |

Same model, same machine, opposite outcomes. The difference is not capability.
It is whether the job had **one checkable deliverable** and an acceptance list
that makes "done" objective.

The honest summary: this agent is a good executor and a poor scoper. It will
work for hours without supervision on a job that is cut small enough, and it
will explore indefinitely on one that is not. Cutting the job small is, for
now, a human's job — and the scaffolding is what makes a small job worth
cutting.

## The parts

| Tool | What it does | Model-specific? |
|---|---|---|
| `antreiber` | drives the agent in rounds, re-reads the protocol each round | no |
| `abnahme` | acceptance list — checks files, counts, contents, exit codes | no |
| `protokoll` | append-only log the agent reads before every round | no |
| `tafel` | shared blackboard between the local agent and the cloud model | no |
| `pruefe-markdown` | catches leaked f-strings, broken tables, unclosed fences | no |
| `beobachter` | samples VRAM/RAM, kills the child before CUDA-OOM kills the server | comment only |
| `laufwache` | watchdog over the agent's own state database | path, configurable |
| `grossauftrag` | queues jobs, stops the model server when a job needs the GPU | service name, configurable |
| `konsil` | consults a second, medical model | yes — it *is* that model |

**Seven of nine are model-free**, because they check results in the file
system rather than model output. That is the load-bearing design decision: an
acceptance criterion like

    genau /path/to/probe/bilder/*.nii.gz 4
    datei /path/to/rauchtest.md
    enthaelt /path/to/rauchtest.md VRAM

is true or false regardless of which model produced the files.

## Pointing it at a different model

Everything that must know the model's name reads `system/modell.conf`:

```
MODELL_DIENST=llama-server                          # systemd user unit
MODELL_ENDPUNKT=http://127.0.0.1:8000/v1/models     # readiness probe
MODELL_VRAM_GIB=21                                  # for the stop/restart decision
AGENT_DB=~/.hermes/profiles/projekt/state.db        # agent framework state
```

Environment variables of the same name take precedence. Swapping the model is
one line, not a search through the tools.

What is *not* configurable, deliberately: the acceptance lists. They describe
the result, not how it was produced.

## What is still coupled

- `konsil` is a wrapper around a specific medical model and is not meant to be
  generic.
- `werkzeugtest` checks that the actual services on this machine answer, so it
  necessarily names them.
- `beobachter` mentions `llama-server` in one hint message. Cosmetic.

---

<a name="geruest-modellunabhaengig"></a>

# Gerüst, modellunabhängig

Dieses Repository will kein Modell tunen. Es baut das **Gerüst, das ein Agent
braucht, um eine Arbeit zu Ende zu bringen** — damit beim nächsten, besseren
Modell das Gerüst stehen bleibt und nur das Modell getauscht wird.

## Warum Gerüst und nicht Prompt

Über vier Aufträge gemessen, eine Maschine, ein lokales Modell:

| Auftrag | Ergebnis |
|---|---|
| `unet-qc` — U-Net bauen, 5-fach CV, trainieren, QC-Seite erzeugen | **allein fertig geworden und abgenommen** |
| `mb1` — 424 Fälle in ein Arbeitsverzeichnis verlinken | **allein fertig geworden** |
| `microbleed-gesamt` — „microbleednet auf der Kohorte rechnen und berichten" | zweimal über zwei Stunden gelaufen, **keine Datei** |
| `mb2` — ein Rauchtest, vier Fälle, eine Frage | 50 Minuten Quelltext lesen, bevor das erste Verzeichnis entstand |

Dasselbe Modell, dieselbe Maschine, gegenteiliger Ausgang. Der Unterschied ist
nicht Können, sondern ob der Auftrag **ein prüfbares Ergebnis** hatte und eine
Abnahmeliste, die „fertig" objektiv macht.

Ehrlich gesagt: dieser Agent ist ein guter Ausführender und ein schlechter
Zuschneider. Er arbeitet stundenlang unbeaufsichtigt an einem klein genug
geschnittenen Auftrag und erkundet endlos bei einem, der es nicht ist. Das
Zuschneiden ist vorerst Menschenarbeit — und das Gerüst ist der Grund, warum
sich das Zuschneiden lohnt.

## Ein anderes Modell einsetzen

Alles, was den Namen des Modells kennen muss, liest `system/modell.conf`.
Umgebungsvariablen gleichen Namens haben Vorrang. Ein Modellwechsel ist eine
Zeile, kein Suchlauf durch die Werkzeuge.

Bewusst **nicht** konfigurierbar sind die Abnahmelisten: sie beschreiben das
Ergebnis, nicht seinen Weg.
