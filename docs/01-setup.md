# 01 — Einrichtung unter Windows

Von null auf laufendes Modell. Dauer: etwa 40 Minuten, davon 35 Warten auf den
Download.

Voraussetzungen: NVIDIA-GPU, aktueller Treiber, Python 3.9+, genug Platz für das
Modell (zweistellige GB).

## 1. llama.cpp

Es gibt fertige Windows-Binaries, man muss nichts kompilieren. Von den
[Releases](https://github.com/ggml-org/llama.cpp/releases) zwei Archive holen:

- `llama-b<nummer>-bin-win-cuda-<version>-x64.zip` — die Programme
- `cudart-llama-bin-win-cuda-<version>-x64.zip` — die CUDA-Runtime-DLLs

**Beide ins gleiche Verzeichnis entpacken**, sonst startet `llama-server.exe` nicht.
Welche CUDA-Version: `nvidia-smi` zeigt den Treiber; neue Treiber können CUDA 13,
ältere brauchen die 12er-Variante.

```powershell
mkdir C:\Users\<du>\llama.cpp
# beide Zips dorthin entpacken
C:\Users\<du>\llama.cpp\llama-server.exe --version
C:\Users\<du>\llama.cpp\llama-server.exe --list-devices
```

`--list-devices` muss die GPU zeigen. Tut es das nicht, fehlt die CUDA-Runtime oder
die Variante passt nicht zum Treiber.

## 2. Modell

GGUF-Dateien liegen auf Hugging Face, meist von `unsloth` oder `bartowski`.

**Welches Quant?** Faustregel: das größte, das mit Reserve in RAM + VRAM passt.
Bei knappem RAM ist das kleinere Quant die bessere Wahl, weil Paging mehr kostet als
die Genauigkeit bringt.

Auf dem Referenzsystem (8 GB VRAM, 31 GB RAM) fiel die Wahl auf `UD-IQ4_XS` mit
17,7 GB statt `UD-Q4_K_M` mit 22,1 GB — 4,4 GB mehr Luft, mehr Layer auf der GPU,
bei einer MoE kaum Qualitätsverlust.

```powershell
mkdir C:\Users\<du>\models
curl.exe -L -C - -o C:\Users\<du>\models\<modell>.gguf `
  "https://huggingface.co/<repo>/resolve/main/<modell>.gguf"
```

`-C -` erlaubt Fortsetzen nach Abbruch. Nach dem Download **Größe prüfen** — sie muss
exakt der Angabe auf Hugging Face entsprechen. Die ersten vier Bytes müssen `GGUF`
sein.

## 3. Vermessen

```powershell
python tools\detect.py C:\Users\<du>\models\<modell>.gguf -o tools\profiles\meinpc.json
```

Gibt aus, wie viele Expert-Layer auf die GPU passen und welchen `-ncmoe`-Wert das
bedeutet. **Vorher alle GPU-Verbraucher schließen**, sonst misst man den Browser mit.

## 4. Starten

```powershell
powershell -ExecutionPolicy Bypass -File tools\start-llm.ps1
```

Das `-ExecutionPolicy Bypass` braucht es nur, wenn die Ausführung von Skripten auf
dem System gesperrt ist — es ändert nichts an der Systemeinstellung, sondern gilt
für diesen einen Aufruf.

Der Server meldet `listening on http://127.0.0.1:8080`.

## 5. Benutzen

**Grafisch:** `http://127.0.0.1:8080` im Browser. `llama-server` bringt eine Web-UI
mit — Chat, Einstellungen, MCP-Server-Anbindung. Nichts zu installieren.

**Auf der Kommandozeile:**

```powershell
python tools\lok.py ping
python tools\lok.py en "Der Server laeuft."
python tools\lok.py tasks
```

## Stolpersteine

| Symptom | Ursache |
|---|---|
| `llama-server.exe` nicht gefunden | Zips nicht entpackt oder in verschiedene Ordner |
| Startet, findet keine GPU | `cudart`-Zip fehlt oder CUDA-Version passt nicht zum Treiber |
| Sehr langsamer Prefill (< 20 t/s) | RAM-Mangel, Modellseiten werden von SSD nachgeladen — Browser schließen |
| Skript startet nicht | ExecutionPolicy, siehe oben |
| Erster Aufruf dauert ewig | mmap lädt Seiten bei Bedarf; der zweite Aufruf ist schnell |
| Jeder Aufruf gleich langsam | mehrere Slots, jeder mit eigenem Prefix-Cache — `-np 1` setzen |
