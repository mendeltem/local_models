<#
    Startet llama-server fuer lok.
    Getestet gegen Build b10603 (llama.cpp), RTX 4070 Laptop 8 GB / Ryzen 7 7840HS / 31 GB RAM.

    Tuning-Reihenfolge:
      1. Mit -NCpuMoe 99 starten (alle Expert-Layer auf der CPU) -> laeuft garantiert.
      2. Zahl schrittweise senken: 99 -> 40 -> 34 -> 30 ...
         Jede Stufe schiebt Expert-Layer auf die GPU und bringt ein paar Prozent.
      3. Sobald der Start mit "out of memory" abbricht oder nvidia-smi voll ist:
         eine Stufe zurueck. Das ist dein Wert.
#>
param(
    [int]$NCpuMoe = 34,        # gemessen: 34 passt in 8 GB VRAM (6733 MiB belegt)
    [int]$Ctx     = 16384,
    [int]$Port    = 8080,
    [int]$Threads = 8,          # physische Kerne, nicht 16
    [string]$Model = "C:\Users\Mendel\models\Qwen3.6-35B-A3B-UD-IQ4_XS.gguf",
    [string]$Exe   = "C:\Users\Mendel\llama.cpp\llama-server.exe",

    # SSD-Schonung. Verschleiss entsteht durch SCHREIBEN, nicht durch Lesen.
    #   mmap        - Modellseiten sind dateigebunden und sauber. Unter Speicherdruck
    #                 werden sie verworfen und neu GELESEN, nie geschrieben.
    #                 Kein SSD-Verschleiss, aber langsamer Prefill bei RAM-Mangel.
    #   mmap+mlock  - wie mmap, zusaetzlich resident gepinnt: keine Verdraengung,
    #                 keine Re-Reads, keine Pagefile-Schreibvorgaenge. Das Optimum,
    #                 ABER nur wenn 17,7 GB frei sind. Sonst drueckt es andere
    #                 Prozesse ins Pagefile und macht es schlimmer.
    #   none        - anonymer Speicher. Bei RAM-Mangel landet das Modell im
    #                 Pagefile = echte Schreibvorgaenge. Nur bei viel freiem RAM.
    [ValidateSet("auto","mmap","mmap+mlock","mlock","none","dio")]
    [string]$LoadMode = "mmap"
)

if (-not (Test-Path $Model)) { Write-Error "Modell fehlt: $Model"; exit 1 }
if (-not (Test-Path $Exe))   { Write-Error "llama-server fehlt: $Exe"; exit 1 }

$srvArgs = @(
    "-m", $Model
    "-ngl", "99"                # alles was geht auf die GPU ...
    "-ncmoe", "$NCpuMoe"        # ... ausser den Expert-Layern der ersten N Layer
    "-c", "$Ctx"
    "-t", "$Threads"
    "-fa", "on"                 # Flash Attention
    "-np", "1"                  # EIN Slot: lok ist ein sequenzieller Client.
                                # Mit 4 Slots landet jeder Aufruf in einem anderen
                                # Prefix-Cache und der System-Prompt wird jedes Mal
                                # neu prefillt. Ob dadurch auch VRAM frei wird, haengt
                                # an kv_unified - nach dem Start mit nvidia-smi pruefen.
    "-lm", $LoadMode            # SSD-Schonung: siehe Kommentar am Parameter
    "--host", "127.0.0.1"
    "--port", "$Port"
    "--metrics"                 # /metrics fuer Durchsatzmessung
)

Write-Host "llama-server: -ncmoe $NCpuMoe  -c $Ctx  -t $Threads  Port $Port" -ForegroundColor Cyan
Write-Host "Test in zweiter Shell: python tools\lok.py ping" -ForegroundColor DarkGray
& $Exe @srvArgs
