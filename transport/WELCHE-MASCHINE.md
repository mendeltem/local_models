# Welcher Befehl gehört auf welche Maschine

Vier Rechner, vier verschiedene Rollen. Die häufigste Fehlerquelle am
27.08.2026 war nicht ein falscher Befehl, sondern ein richtiger Befehl auf der
falschen Maschine — dreimal hintereinander. Deshalb diese Tafel.

    s-c15-csb-app01     Linux, schnelles Netz, base = Python 3.9.7
    s-csb-wiki-hub      Linux, schnelles Netz
    Windows-Rechner     Proxy, sieht den USB-Stick als E: und die Freigabe als S:
    Alita-MS-7D91       KEIN Netz, conda-Umgebung `dl`, sieht nur den Stick

Alle vier sehen die Freigabe unter verschiedenen Namen — **es ist derselbe
Speicher**:

    Linux    ~/CSB_NeuroRad/temuuleu/
    Windows  S:\AG\AG-CSB_NeuroRad\temuuleu\

---

## Auf den Linux-Servern

Herunterladen. Sonst nichts.

    cd ~/CSB_NeuroRad/temuuleu/download/offline-bundle/07-experimentelle-modelle
    hol() { n=$(basename "$1"); curl -L --fail --retry 8 --retry-all-errors \
      --retry-delay 5 --speed-limit 10240 --speed-time 60 -C - -o "$n.laedt" "$1" \
      && mv "$n.laedt" "$n" && echo "ok $n $(stat -c%s "$n")"; }

**Nicht dort ausführen:** alles mit `conda activate dl` (die Umgebung gibt es
nur auf Alita) und alles mit `/media/uchralt/QWEN/` (das ist der
Einhängepunkt des Sticks auf Alita).

## Auf dem Windows-Rechner

Stick befüllen und prüfen. Der Stick ist dort `E:`.

## Auf Alita

Erst wenn der Stick dort steckt.

    # welche Wheel-Fassung passt?
    conda activate dl
    python -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}')"

    # mit dem Verzeichnis, das der Befehl oben nennt:
    pip install --no-index \
      --find-links /media/uchralt/QWEN/offline-bundle/05-wheels/cp311/ \
      mne-nirs seaborn statsmodels

    # ist der Stick heil angekommen?
    cd /media/uchralt/QWEN/offline-bundle
    sha256sum -c <(awk '{print $1"  "$3}' PRUEFSUMMEN.txt)

    # waren die Downloads ueberhaupt je korrekt?
    sha256sum -c <(awk '!/^#/{print $1"  ./"$3}' HERKUNFTS-PRUEFSUMMEN.txt)

---

## Warum die Wheels in vier Fassungen vorliegen

Ein Wheel wie `h5py-3.14.0-cp311-cp311-...whl` läuft **nur** unter Python
3.11. Alitas Version war beim Packen nicht bekannt, und ohne Netz lässt sich
dort nichts nachbessern.

Eingrenzen liess sie sich trotzdem, ohne jemanden zu fragen:

* **nach unten:** auf Alita läuft MNE 1.12, und dessen Metadaten verlangen
  `Requires-Python: >=3.10`. Damit ist 3.9 ausgeschlossen.
* **nach oben:** torch 2.6 unterstützt höchstens 3.13.

Bleiben vier Möglichkeiten, alle vier liegen bei — zusammen 535 MB. Billiger
als eine Fahrt umsonst.
