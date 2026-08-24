# 04 — Docker: dieselbe Umgebung auf anderen Workstations

> **Ungetestet.** Auf dem Referenzsystem ist kein Docker installiert, die Dateien
> hier sind nicht gegen eine laufende Engine geprüft. Sie folgen der offiziellen
> llama.cpp-Docker-Dokumentation.

## Wofür Docker hier taugt — und wofür nicht

**Ja, für Portabilität.** Ein Image mit llama.cpp, CUDA und den Werkzeugen ist das
richtige Transportformat für andere Workstations. Kein Nachbauen der CUDA-Version,
kein Entpacken von zwei Zips in denselben Ordner.

**Nein, als lokale Laufzeit auf einem Windows-Laptop.** Docker Desktop läuft dort
über WSL2, und das kostet doppelt:

- WSL nimmt ohne `.wslconfig` **50 % des RAM**. Bei 31 GB sind das 15,6 GB — weniger
  als ein 17,7-GB-Modell. Man müsste erst `memory=24GB` konfigurieren.
- Der VM-Layer hat einen eigenen Speicherpool. Auf einer Maschine, deren
  Engpass ohnehin RAM ist, macht das die Sache schlechter.

Auf einem Linux-Host mit NVIDIA Container Toolkit gilt der Einwand nicht.

## Voraussetzungen auf dem Zielrechner

- Docker
- NVIDIA Container Toolkit (damit `--gpus all` funktioniert)
- Der NVIDIA-Treiber gehört auf den **Host**, nicht ins Image

## Modell nicht ins Image

Das Modell wird als Volume gemountet, nicht einkopiert. Ein 18-GB-Layer macht das
Image unbenutzbar — jeder Rebuild, jeder Push, jeder Pull schleppt es mit. Das Image
bleibt so bei einigen hundert MB.

## Benutzung

```bash
docker build -f docker/Dockerfile -t local-models/llama:cuda13 .

docker run --rm --gpus all \
  -v /pfad/zu/models:/models:ro \
  -p 8080:8080 \
  -e LOK_MODEL_PATH=/models/mein-modell.gguf \
  local-models/llama:cuda13
```

Oder mit Compose:

```bash
MODELS_DIR=/pfad/zu/models docker compose -f docker/docker-compose.yml up
```

## Der Trick: der Container vermisst sich selbst

`entrypoint.sh` ruft beim Start `detect.py --print-args`. Das liest die
Tensor-Tabelle des gemounteten Modells, fragt `nvidia-smi` nach freiem VRAM und
berechnet daraus `-ncmoe`, Threads und Lademodus.

Dasselbe Image ergibt damit auf einer RTX 4090 mit 24 GB etwa `-ncmoe 0` (alle
Experten auf der GPU) und auf einer RTX 3060 mit 12 GB etwa `-ncmoe 25`. Ohne dass
irgendjemand eine Zahl pflegt.

Eigene Argumente überschreiben die Automatik:

```bash
docker run ... local-models/llama:cuda13 -ngl 99 -ncmoe 20 -c 8192
```

## CUDA-Variante

Das Basis-Image gibt es in mehreren Ausführungen:

| Tag | wofür |
|---|---|
| `ghcr.io/ggml-org/llama.cpp:server-cuda13` | NVIDIA, CUDA 13 (Default hier) |
| `ghcr.io/ggml-org/llama.cpp:server-cuda` | NVIDIA, CUDA 12 — für ältere Treiber |
| `ghcr.io/ggml-org/llama.cpp:server-rocm` | AMD |
| `ghcr.io/ggml-org/llama.cpp:server-vulkan` | herstellerunabhängig, langsamer |

Passt der Treiber auf dem Zielrechner nicht zu CUDA 13, im `Dockerfile` die erste
Zeile auf `server-cuda` ändern.

## Wenn es doch unter Windows laufen soll

`C:\Users\<du>\.wslconfig` anlegen:

```ini
[wsl2]
memory=24GB
processors=8
swap=0
```

`swap=0` ist Absicht: Auslagerung innerhalb der VM würde auf die SSD schreiben und
gleichzeitig alles ausbremsen. Danach `wsl --shutdown`, damit es greift.

Und dann trotzdem messen, ob es sich gegenüber dem nativen Start lohnt.
