# Bestellliste — was auf Alita fehlt

*Stand 2026-08-28. Diese Datei liest die Maschine, die eine brauchbare Leitung
hat. Alita hat Netz, aber **gemessen 36 Byte/s** — damit ist selbst 1 GB
unerreichbar.*

*A shopping list for whichever machine has real bandwidth. Alita is online but
measured at 36 B/s, so anything above a few MB has to come this way.*

---

## Wie das hier funktioniert

Alita trägt ein, was fehlt. Eine Maschine mit Leitung lädt es, legt es auf den
USB-Stick oder die Freigabe, und hakt hier ab. Erledigtes bleibt stehen, damit
niemand zweimal lädt.

    s-c15-csb-app01     Linux, ~20 MB/s   ~/CSB_NeuroRad/temuuleu/
    s-csb-wiki-hub      Linux, ~23 MB/s   dieselbe Freigabe
    Windows-Rechner     Proxy, 0,15–10 MB/s, sieht E: (Stick) und S: (Freigabe)
    Alita               36 B/s — lädt nichts

**Vor dem Laden:** `WELCHE-MASCHINE.md` auf dem Stick sagt, welcher Befehl
wohin gehört. **Nach dem Laden:** `vollkopie.py` schreibt auf den Stick und
liest zurück gegen die Anbieter-sha256 — nicht auslassen, am 27.08. kam so
eine Datei mit vorangestelltem Bruchstück durch.

---

## Offen — nach Nutzen sortiert

### 1. Zweiter microbleednet-Modellsatz · klein · **blockiert einen laufenden Auftrag**

Das README des Pakets nennt **zwei** Kohorten, MWSC und UKB. Auf Alita liegen
nur vier Gewichtsdateien — das sieht nach einem Satz aus, nicht nach zweien.

    https://drive.google.com/drive/folders/1pqTFbvPVANFngMx0Z6Z352k0xPIMa9JA

Google Drive geht nicht mit `curl`. Entweder `pip install gdown` und
`gdown --folder <url>`, oder im Browser „Alle herunterladen".
**Dateien NICHT umbenennen**, alle in EIN Verzeichnis.

Ziel: `data/models/vortrainiert/microbleednet/`
Was schon da ist: `Microbleednet_cdet_model.pth`, `_cdisc_student_model.pth`,
`_cdisc_teacher_class_model.pth`, `_cdisc_teacher_model.pth`

### 2. EEGMMIDB · 3,1 GB, davon 61 % geladen

Teildatei liegt auf Alita unter
`data/sourcedata/eeg-fnirs-dot/physionet-eegmmidb/…zip.laedt`.
Sie muss zum Fortsetzen **mit auf den Stick**.

    https://physionet.org/files/eegmmidb/1.0.0/

PhysioNet lieferte am 27.08. von **allen drei** Maschinen nur 0,15–0,22 MB/s —
die Quelle ist die Bremse, nicht die Leitung. Mit `hartnaeckig.sh` laden, es
setzt bei Abbruch wieder auf.

### 3. wmh.isi.uu.nl über DataverseNL · Größe unbekannt

Antwortete über den Charité-Proxy nicht (Code 000), **von Alita aus jetzt 200**.
Von einer Maschine mit Leitung also erreichbar.

    DOI 10.34894/AECRSD

Enthält unter anderem die Zusatzannotationen zweier Zweitbefunder, die schon
auf Alita liegen — prüfen, was darüber hinaus dort ist.

### 4. MRBrainS18 · ~2 GB · Registrierung

Utrecht, WMH als **eigene Label-Klasse**. Damit ließe sich der Label-2-Punkt
klären, den Clara am 28.08. selbst gefunden hat: sie zählt Label 1+2 als
Läsion, die offizielle Challenge-Auswertung schließt Label 2 aus.

    https://mrbrains18.isi.uu.nl/

### 5. ATLAS v2.0 · ~15 GB · Registrierung

Schlaganfallläsionen, 955 Fälle. Für den Architekturvergleich auf einer
zweiten Läsionsart.

    https://fcon_1000.projects.nitrc.org/indi/retro/atlas.html

### 6. Shifts 2.0 · zugangsbeschränkt

MS-Läsionen mit Verteilungsverschiebung — der passendste Datensatz für die
Amsterdam-Frage (dort liegen alle Verfahren am schlechtesten, und zwei
menschliche Befunder ebenfalls). Zenodo 7051658 meldete null Dateien.
**Antrag nötig, kein Download.**

### 7. GSP1000-Konnektom · **219 GB** · nur mit Plan

Voraussetzung für Lesion Network Mapping: welche Netzwerke sind durch die
Läsionen unterbrochen, statt nur wie viel Läsion da ist. Platz auf Alita ist
da (614 GB frei), aber 219 GB über den Stick sind vier Fahrten. Erst holen,
wenn die Fragestellung steht.

---

## Erledigt — nicht noch einmal laden

    Qwen3.8-27B Q4 und Q5, mtp-Entwurfsmodell        auf Alita
    MedGemma 4B und 27B, Qwen3-Coder-30B             auf Alita
    Llama-3.1-8B, Qwen3-4B, Qwen3-1.7B               auf Alita
    ModernBERT, DistilBERT, bge-m3 + Reranker        auf Alita
    Qwen2.5-0.5B (Laufwache)                         auf Alita
    WMH Challenge, 170 Fälle + Zweitbefunder         auf Alita
    ISLES 2022, MSD Task04                           auf Alita
    Shin 2018 EEG+fNIRS, NeuroDOT, MNE-fNIRS-Motor   auf Alita
    model_swinvit.pt, swin_unetr_btcv, brats_mri     auf Alita, repariert
    Wheels cp310–cp313                               auf Alita
    peft, bitsandbytes, trl, datasets                über Alitas eigene Leitung

**`model_swinvit.pt` war kaputt** — 448 923 293 statt 411 162 269 Bytes, ein
abgebrochenes Bruchstück mit dem vollständigen Download dahinter. Am 28.08.
ersetzt und gegen `1cf19eca…c988` geprüft. Falls die Datei anderswo noch in
der falschen Größe liegt: ersetzen.

---

## Nicht laden

**Qwen3.8-Flash-Next.** Kleinste Fassung 67,6 GiB, passt weder in Alitas
24,5 GiB VRAM noch in 62 GiB RAM. Auf dem Laptop mit 8 GB wäre es die
interessantere Frage — dort ist Offloading ohnehin das Prinzip. Begründung
vollständig in `BLACKBOARD.md`, Eintrag [17].
