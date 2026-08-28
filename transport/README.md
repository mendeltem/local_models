# transport — Modelle auf eine Maschine ohne Netz bringen

`tools/` betreibt lokale Modelle, `alita/` lässt einen Agenten damit arbeiten.
Hier steht die Frage davor: **wie die Modelle überhaupt dorthin kommen, wo
kein Netz ist.**

Die Werkzeuge stammen aus einem Tag, an dem 60 GB über drei Rechner, eine
Netzfreigabe und einen USB-Stick auf eine Maschine ohne Internetzugang
gebracht wurden. Jede Vorsichtsmaßnahme darin entstand aus einem Fehler, der
tatsächlich passiert ist — keine ist vorsorglich.

## Die Werkzeuge

| | |
|---|---|
| [`alles-laden.sh`](alles-laden.sh) | Bestandstabelle mit Sollgrößen, Wiederaufnahme, Abschnittswahl, Bericht |
| [`rest_download.sh`](rest_download.sh) | zweiter paralleler Lauf mit Sperren, damit sich zwei Läufe nicht dieselbe Datei zerschreiben |
| [`hartnaeckig.sh`](hartnaeckig.sh) | ein einzelner Download, der Abbruch und Stillstand übersteht |
| [`einsammeln.py`](einsammeln.py) | sammelt fertige Dateien aus einem gemeinsamen Speicher ein und sortiert sie ein |
| [`vollkopie.py`](vollkopie.py) | Freigabe → Datenträger, mit Rücklesen gegen die Herkunftssumme |
| [`nachliefern.py`](nachliefern.py) | nur das Neue kopieren statt alles |
| [`abfahrbereit.py`](abfahrbereit.py) | Prüfsummen nur für das, was sie wirklich braucht |
| [`WELCHE-MASCHINE.md`](WELCHE-MASCHINE.md) | welcher Befehl auf welchen Rechner gehört |
| [`REPARATUR.md`](REPARATUR.md) | ein ausgelieferter Schaden und wie er entstand |

## Was gemessen wurde

Durchsatz derselben Quelle von drei Maschinen, gleicher Tag:

    Hugging Face   ueber Proxy      4-10 MB/s
    Hugging Face   direkt          23-50 MB/s
    PhysioNet      ueber Proxy       0,15 MB/s
    PhysioNet      direkt            0,22 MB/s

Der Proxy ist bei Hugging Face die Bremse. Bei PhysioNet ist es die Quelle —
dort hilft keine bessere Leitung. Das zu wissen, spart Stunden: MedGemma-27B
mit 15,4 GB brauchte direkt 11 Minuten und über den Proxy geschätzte drei
Stunden.

## Die sechs Lehren

### 1. Ein Wiederaufnahmeversuch kann die Datei vergrößern

`curl -C -` schickt einen Range-Wunsch. Verwirft der Server ihn — GitHub tut
das bei der Weiterleitung auf sein CDN —, kommt die Antwort ab Byte 0 und
wird an das Bruchstück **angehängt**:

    37 761 024 + 411 162 269 = 448 923 293

`curl` meldet Erfolg. Die Datei ist zu groß statt zu klein, sieht vollständig
aus, und lässt sich nicht laden. Wir haben genau diese Datei ausgeliefert;
siehe [REPARATUR.md](REPARATUR.md).

### 2. Die Sollgröße darf nie aus der eigenen Datei stammen

Als ein Bereichsabruf 411 162 269 meldete und die vorhandene Datei
448 923 293 hatte, wurde der Header für falsch gehalten und die erwartete
Größe auf den kaputten Wert gesetzt. Damit galt die defekte Datei als Norm
und die intakte als unvollständig.

**Die Größe wird bei der Quelle erfragt, nicht aus dem Vorhandenen
abgeleitet.** Bei GitHub-Releases über die API, bei Hugging Face über
`/api/models/<repo>/tree/main`.

### 3. Eine Datei trägt ihren Namen erst, wenn sie fertig ist

Geladen wird nach `<name>.laedt`, umbenannt wird nach bestandener Prüfung.
`mv` innerhalb eines Dateisystems ist atomar — es gibt keinen Moment, in dem
die Datei unter ihrem echten Namen unvollständig existiert.

Das ist der einzige Schutz, der auch für **fremde** Prozesse trägt: eine
andere Maschine, die nur ins Verzeichnis schaut, kann eine halbe GGUF nicht
für ein Modell halten.

### 4. Ein toter Download sieht aus wie ein langsamer

Ein Download stand eine halbe Stunde bei 359 MB und wurde für „langsam"
gehalten. Dagegen hilft:

    --speed-limit 10240 --speed-time 60

Bricht ab, wenn 60 Sekunden lang unter 10 KB/s. Zusammen mit der
Wiederaufnahme kostet das nichts und macht Stillstand sichtbar.

### 5. Eigene Prüfsummen beweisen nur Selbsttreue

`sha256sum -c` gegen eine selbst erzeugte Liste zeigt, dass der Datenträger
sich nicht verändert hat. Ob der Download je korrekt war, sagt es nicht.

Hugging Face veröffentlicht die sha256 als LFS-`oid`. Ein Vergleich damit
beweist Byte-Gleichheit mit dem Original:

```bash
curl -s "https://huggingface.co/api/models/$REPO/tree/main" \
  | python -c "import sys,json;[print(x['lfs']['oid'],x['lfs']['size'],x['path']) for x in json.load(sys.stdin) if x.get('lfs')]"
```

So wurden zehn Modelldateien belegt. Die eine beschädigte Datei kam von
GitHub — dort gibt es keine veröffentlichte Summe, und genau dort ist der
Schaden entstanden. **Wo keine Herkunftssumme existiert, muss wenigstens
geprüft werden, ob sich das Archiv öffnen lässt** (`zipfile.is_zipfile`,
`tar -t`); ein vorangestelltes Bruchstück fällt dabei sofort auf.

### 6. Mehrere Maschinen brauchen eine gemeinsame Liste, nicht gemeinsame Dateien

Ein Server sieht den USB-Stick nicht — wohl aber eine Inventarliste auf der
Freigabe. `alles-laden.sh` liest sie über `BEKANNT=` und überspringt, was
dort schon vollständig liegt:

```bash
BEKANNT=./INVENTAR-usb.txt bash alles-laden.sh
```

Entscheidend ist, dass die Liste **Größen** enthält, nicht nur Namen. Sonst
melden sich drei Maschinen gegenseitig halbe Modelle als fertig.

## Gebrauch

```bash
bash alles-laden.sh bericht     # zeigt, was fehlt, laedt nichts
bash alles-laden.sh             # holt alles Fehlende
bash alles-laden.sh modelle     # nur einen Abschnitt
```

Ziel ist standardmäßig `./offline-bundle` neben dem Skript; `ZIEL=` setzt es
um, `PROXY_URL=` leert oder ändert den Proxy.

Die Bestandstabelle in `alles-laden.sh` ist auf ein konkretes Vorhaben
zugeschnitten — Wächter-Modelle, Encoder, medizinische Segmentierer,
EEG/fNIRS-Daten. Für ein anderes Vorhaben ersetzt man die Tabelle und behält
den Rest.
