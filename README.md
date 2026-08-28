# local_models

*[Deutsche Fassung: README.de.md](README.de.md)*

Running local LLMs on consumer hardware — tools, measurement methods and
operating rules. Not a framework, just the minimum you need to get real use out
of a MoE model on a machine with too little VRAM.

At the core of this repository is a stance: **measure, don't estimate.** Every
number here comes from a run on real hardware, not from a model card.

## What is in here

| | |
|---|---|
| [`tools/lok.py`](tools/lok.py) | CLI for small jobs against the local model — fixed output formats, escalation rule, batch mode, statistics |
| [`tools/detect.py`](tools/detect.py) | measures GPU, RAM and model, then computes the launch parameters — the reason this repo works on someone else's hardware |
| [`tools/start-llm.ps1`](tools/start-llm.ps1) | launch script for `llama-server` on Windows |
| [`tools/stimme/`](tools/stimme/) | text to speech on the same card — cloned voices from 8 KB samples, no network |
| [`docker/`](docker/) | the same thing as a container, for other workstations |
| [`docs/`](docs/) | setup, tuning method, model wiki |
| [`alita/system.html`](alita/system.html) | **the whole workstation on one page** — hardware, services, models, measurements and a flowchart; runs without a network, bilingual |
| [`alita/`](alita/) | a local agentic system: an agent working unsupervised on data that must not leave the machine — blackboard, guards, measuring tools ([Deutsch](alita/README.de.md)) |

## Quick start

```bash
# 1. Get llama.cpp (see docs/01-setup.md)
# 2. Get a GGUF model
# 3. Measure the machine and generate a profile
python tools/detect.py /path/to/model.gguf -o tools/profiles/$(hostname).json

# 4. Start the server (Windows)
powershell -ExecutionPolicy Bypass -File tools/start-llm.ps1

# 5. Check
python tools/lok.py ping
python tools/lok.py en "The server is running."
```

You do not need to install a graphical interface: `llama-server` ships with one
at `http://127.0.0.1:8080`.

## Where the results are

What this machine actually computes is published separately, so this repository
stays a toolbox rather than a result dump:

**<https://mendeltem.github.io/clara_working_station/>** — one address for all
projects, including the WMH quality-control pages (eleven segmentation methods
per patient, multiplanar and 3D, no external requests).

Only work on public datasets is published there. Patient data and results on
in-house cohorts stay on the machine.

## Documentation

The documents below are in German.

- **[01 — Setup](docs/01-setup.md)** — llama.cpp and a model on Windows, from nothing to running
- **[02 — Tuning](docs/02-tuning.md)** — how to find out what fits on your own GPU, and what it buys you
- **[03 — Model wiki](docs/03-model-wiki.md)** — which task with which settings, and where the model reliably fails
- **[04 — Docker](docs/04-docker.md)** — the same environment on other workstations

## Reference systems

The measurements come from **two** machines. Which one is meant is stated at
every number — they are not comparable with each other.

### Laptop — the measurements in `tools/` and `docs/`

| | |
|---|---|
| GPU | RTX 4070 Laptop, 8 GB VRAM |
| CPU | Ryzen 7 7840HS, 8 cores / 16 threads |
| RAM | 31.3 GB DDR5 |
| Model | Qwen3.6-35B-A3B, GGUF `UD-IQ4_XS`, 17.7 GB |
| llama.cpp | b10603, CUDA 13.3 |
| [`docs/05-scaffolding.md`](docs/05-scaffolding.md) | the model-agnostic part: what makes an agent finish work, and how to point it at a different model |

Result after the tuning described in [docs/02](docs/02-tuning.md): **19.4 tokens/s**
decoding, **306 tokens/s** on a warm prefill. A 35 B model on a laptop with 8 GB
of VRAM, usable interactively. **That is the point of this repository:** running
a model that does not actually fit on the card.

### Alita — the measurements in `alita/`

| | |
|---|---|
| GPU | RTX A5000, 24,564 MiB VRAM, compute capability 8.6 |
| CPU | Intel i9-12900K, 16 cores / 24 threads |
| RAM | 62 GiB |
| System | Ubuntu 24.04.3, kernel 6.14, **no sudo** |
| Model | Qwen3.8-27B, GGUF `UD-Q4_K_M`, 16 GB, 80k context |

A workstation where an agent works unsupervised on data that must not leave the
machine. Here the bottleneck is not the size of the card but that **the language
model and a training run have to share the same 24.5 GiB**: `llama-server` holds
21,451 MiB, leaving 3,113 MiB for everything else.

The numbers from the two machines are not comparable — the laptop measures how
far you get with too little VRAM, Alita measures what still fits beside a model
that stays loaded.

## What is portable and what is not

Everything in this repository is machine-independent. The machine-specific
values — paths, `-ncmoe`, threads, load mode — live in `tools/profiles/*.json`,
are **generated** by `detect.py`, and are excluded by `.gitignore`.

On a new workstation you copy the repo, run `detect.py` once, and have a
matching profile. No manual work, no copying values that were true for a
different GPU.
