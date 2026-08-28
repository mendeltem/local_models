# Alita-MS-7D91

*2026-08-28 erfasst mit `maschinen/erfassen.sh`. Alle Zahlen gemessen.
*Captured 2026-08-28. Every number measured, none from a spec sheet.*

## Hardware

| | |
|---|---|
| GPU | NVIDIA RTX A5000, 24564 MiB |
| Treiber / driver | 550.163.01 |
| Compute Capability | 8.6 (bfloat16 ja, FP8 nein) |
| CPU | 12th Gen Intel(R) Core(TM) i9-12900K |
| Kerne / cores | 24 Threads, 16 Kerne je Sockel |
| RAM | 62.6 GiB |
| Swap | 8.0 GiB |
| System | Ubuntu 24.04.3 LTS, Kernel 6.14.0-27-generic |
| Platte / disk | 635G frei von 915G |
| Rechte / privileges | in der sudo-Gruppe, verlangt Passwort — Betriebsregel: im Alltag kein sudo |

## Im Betrieb gemessen / measured under load

| | |
|---|---|
| VRAM belegt / used | 21777 von 24564 MiB |
| VRAM frei / free | **2787 MiB** |
| haelt VRAM / holding VRAM | llama-server (220 MiB); llama-server (20870 MiB); llama-cli (332 MiB) |
| RAM verfuegbar / available | 49.9 GiB |
| Uptime | 22 hours, 27 minutes |

| Agenten-Netzsperre | Gruppe `agent-net` vorhanden |
| Sperre wirksam? | ja, gemessen: kein Zugang aus `agent-net` |

## Was laeuft / what is running

53 systemd-Benutzerdienste. Auf Loopback horchende Ports:

```
  34783  llama-cli
  631    
  8000   llama-server
  8001   llama-server
  8800   python
  8810   python
  8899   python3
```

## Modelle auf der Platte / models on disk

`/home/uchralt/local_agentic_system/modelle`

```
4.0K	  HERKUNFTS-PRUEFSUMMEN.txt
4.0K	  ZURUECK-AM-ZIELRECHNER.txt
548M	  ggml-large-v3-turbo-q5_0.bin
885M	  mmproj-F16.gguf
1.1G	  encoder
1.1G	  waechter
1.3G	  mtp-Qwen3.8-27B-Q4_0.gguf
1.8G	  embedding
8.7G	  schnell
16G	  Qwen3.8-27B-UD-Q4_K_M.gguf
19G	  Qwen3.8-27B-UD-Q5_K_M.gguf
36G	  spezialisten
```

`/home/uchralt/qwen-models`

```
4.0K	  HERKUNFTS-PRUEFSUMMEN.txt
4.0K	  ZURUECK-AM-ZIELRECHNER.txt
548M	  ggml-large-v3-turbo-q5_0.bin
885M	  mmproj-F16.gguf
1.1G	  encoder
1.1G	  waechter
1.3G	  mtp-Qwen3.8-27B-Q4_0.gguf
1.8G	  embedding
8.7G	  schnell
16G	  Qwen3.8-27B-UD-Q4_K_M.gguf
19G	  Qwen3.8-27B-UD-Q5_K_M.gguf
36G	  spezialisten
```


## Rechenumgebung / compute environment

| | |
|---|---|
| conda `dl` | Python 3.12.14, torch 2.6.0+cu124, CUDA True |
| conda `qwen-serve` | Python 3.12.14, kein torch |
| `git` | /usr/bin/git |
| `gh` | /home/uchralt/.local/bin/gh |
| `python3` | /home/uchralt/miniconda3/bin/python3 |

## Bildgebung / imaging tools

```
  bet                  ~/fsl/share/fsl/bin/bet
  flirt                ~/fsl/share/fsl/bin/flirt
  fslmaths             ~/fsl/share/fsl/bin/fslmaths
  bianca               ~/fsl/share/fsl/bin/bianca
```

---

*Erneuern mit `./maschinen/erfassen.sh`. Was ueber diese Maschine hinausgeht --
welches Modell wie schnell laeuft -- steht in [tools/](../tools/) und [docs/](../docs/).*
