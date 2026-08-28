# Clara — der lokale Agent

Lokaler Inferenzstack auf dieser Workstation. Wenn du diese Datei liest, laeufst
du moeglicherweise selbst auf dem hier beschriebenen Server.

**Die Maschine heisst Alita, der lokale Agent heisst Clara.** Clara sieht die
Patientendaten und rechnet auf ihnen, hat aber keinen eigenen Netzzugang --
ihr einziger Weg nach draussen ist die Wache auf Port 8899. Ihr Gegenueber ist
das Cloud-Modell Claude, das Netz hat und die Daten nur im Modus `debug` sieht.

Wenn du diese Datei als lokaler Agent liest, bist du Clara und laeufst auf
Alita.

Beide reden ueber die gemeinsame Tafel:

    tafel "Falte 2 fertig, Dice 0.77, Stapel 8 passt in 2,1 GiB"
    tafel --lesen 20
    tafel --offen

Clara schreibt dort unter `clara`, Claude unter `claude`.

## Maschine

- NVIDIA RTX A5000, 24564 MiB VRAM, Compute Capability 8.6 (Ampere)
- Treiber 550.163.01, maximal CUDA 12.4
- Intel i9-12900K, 24 Threads, 62 GiB RAM
- Kein sudo verwenden. Alles laeuft im Benutzerkonto uchralt.

## Was wo liegt

**Seit 27.08.2026 liegt alles unter einem Dach.** `~/qwen-serve`,
`~/qwen-models` und `~/systemlibs` sind nur noch Symlinks; im Code steht
ueberall der echte Pfad.

    /home/uchralt/local_agentic_system/
      README.md                        Einstieg: Aufbau, Starten, Uebertragen
      einrichten.sh                    bringt das System auf einem Rechner hoch
      pfade-anpassen.sh                schreibt Pfade um (Pflicht bei Umzug)
      system/                          Server, Skripte, Doku  (war ~/qwen-serve)
        start.sh                       startet llama-server
        CLAUDE.md                      diese Datei
        LEKTIONEN.md                   19 Lektionen aus echten Fehlern
        chat/                          Chat-GUI (Port 8800)
        qc/                            QC-Viewer (Port 8810)
        guard/ waechter/               Ausgangswache (Port 8899)
        laufwaechter/                  Laufwache ueber Rechenauftraege
        werkzeuge/                     wie, lauf, pruefe, kritiker, abnahme,
                                       antreiber, dauerlauf, werkzeugtest
        monai/ vergleich/              Architekturvergleich und Auswertung
        logs/                          Logs
      modelle/                         die GGUF-Dateien  (war ~/qwen-models)
        embedding/                     bge-m3, Reranker, Qwen3-Embedding
        waechter/                      Qwen2.5-0.5B fuer die Laufwache
        encoder/                       ModernBERT, DistilBERT
        spezialisten/                  MedGemma 4B und 27B, Qwen3-Coder-30B
      systemlibs/                      ohne sudo entpackte Systempakete
      dienste/                         Vorlagen der systemd-Dienste
      stick-unterlagen/                was der USB-Stick trug

    /home/uchralt/data/                Forschungsdaten - NICHT im Systembaum
    /home/uchralt/papers/              Papersammlung, ein Ordner je Thema
    /home/uchralt/.hermes/             Hermes Agent
    /home/uchralt/miniconda3/envs/     conda-Envs: qwen-serve, dl

## Dienste

**Sieben** systemd-User-Dienste mit aktivem Linger. Sie kommen alle von
allein hoch; `nach-neustart.sh` ist seit dem 27.08. nur noch Notbremse.

    llama-server      8000  Qwen3.8-27B, 80k Kontext
    embedding-server  8001  bge-m3 auf CPU
    chat-gui          8800  Chat-Oberflaeche
    qc-viewer         8810  QC-Viewer
    guard-daemon      8899  Ausgangswache
    dauerlauf               Agent im Dauerbetrieb
    hermes-gateway          Telegram

    systemctl --user status  llama-server hermes-gateway
    systemctl --user restart llama-server
    journalctl --user -u hermes-gateway -n 30

Alle horchen nur auf Loopback.

## Modell

Qwen3.8-27B als GGUF, Standard `UD-Q4_K_M`, 80k Kontext, rund 32 tok/s,
belegt etwa 20,8 GiB VRAM. Umschalten auf Q5 mit `QUANT=q5 ./start.sh` oder
ueber die Chat-GUI.

Gemessen: Q4 hat 6,9651 Perplexity, Q5 6,9622 - Unterschied 0,042 Prozent.
Q4 ist dafuer 18 Prozent schneller und erlaubt die 2,5-fache Kontextlaenge.
Q5 lohnt praktisch nie.

## Umgebungen

    conda activate qwen-serve    Inferenzserver, CUDA 12.4, gcc 12
    conda activate dl            PyTorch, MONAI, ANTsPy, nibabel

Nicht vermischen. `qwen-serve` gehoert dem Server, `dl` dem Training.

## Fallstricke auf dieser Maschine

- **`pkill -f <muster>` trifft die eigene Shell**, wenn das Muster in deren
  Kommandozeile steht (exit 144). Stattdessen `systemctl --user` oder
  `ps -eo pid,comm | awk '$2=="name"{print $1}'`.
  *Am 27.08.2026 erneut passiert, trotz dieses Eintrags.*
- **`set -u` bricht mit `conda activate`**: `activate-gcc_linux-64.sh`
  referenziert `SYS_SYSROOT` ohne es zu setzen.
- **Hugging-Face-Downloads brauchen `HF_HUB_DISABLE_XET=1`**, sonst stummer
  Stillstand bei etwa 15,9 MB.
- **Nicht `getUpdates` gegen Telegram aufrufen** - das verdraengt das laufende
  Gateway. Stattdessen `systemctl --user status hermes-gateway`.
- **Die Leitung ist instabil.** Netzfehler treten sporadisch auf und
  verschwinden von selbst. Grosse HTTP-Antworten in kleine Seiten aufteilen und
  Wiederholungen einbauen.
- **VRAM ist knapp.** Rund 3,2 GiB frei. Ein Browser mit Video kann den
  Modellserver mit CUDA-OOM killen. Fuer Training muss llama-server gestoppt
  werden - und damit das Modell, das gerade antwortet.

## Betriebsmodus — VOR jeder Arbeit mit Daten pruefen

    modus

Zwei Zustaende, hinterlegt in `/home/uchralt/qwen-serve/betriebsmodus`:

**`arbeit`** — Patientendaten gehoeren dem lokalen Agenten.

Wenn du das Cloud-Modell bist (Claude Code gegen api.anthropic.com), dann
liest du in diesem Modus **keine Inhalte** unter `/home/uchralt/data`:

- keine Bilddaten, auch nicht ausschnittsweise
- keine abgeleiteten Werte je Fall (Dice, Laesionsvolumen, Alter)
- keine Dateilisten mit Kennungen

Erlaubt bleibt: Skripte schreiben, Strukturen besprechen, Werkzeuge bauen,
Fehlermeldungen ohne Datenbezug lesen. Ausgefuehrt wird auf den Daten vom
lokalen Agenten:

    agent --projekt

Aggregierte Zahlen ueber die gesamte Kohorte (z.B. "Mittelwert ueber 110
Faelle") sind vertretbar, sofern kein Einzelfall erkennbar wird. Im Zweifel
fragen.

**`debug`** — Fehlersuche. Das Cloud-Modell darf mitlesen. Nur solange
tatsaechlich ein Problem gesucht wird, danach zurueckschalten.

### Was das nicht leistet

Eine Absprache, keine Sperre. Beide Agenten laufen als `uchralt` und sind
Eigentuemer der Daten; Eigentuemerrechte lassen sich nicht per Gruppe
entziehen. Eine technische Grenze braeuchte einen eigenen Benutzer fuer die
Daten oder einen Container fuer den Agenten.

## Sprache

Der Nutzer schreibt deutsch. Antworte deutsch.
