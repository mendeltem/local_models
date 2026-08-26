# stimme — Text zu Sprache, lokal

Ein Satz hinein, eine Audiodatei heraus. Läuft auf der eigenen
Grafikkarte, ohne Netz, für jedes Projekt gleich.

```bash
stimme "Guten Morgen." --stimme frau -o gruss.mp3
stimme --datei zeilen.txt --ordner ausgabe/ -s mann
echo "Noch ein Satz." | stimme -o satz.mp3
stimme --stimmen          # welche Vorlagen es gibt
stimme --liste …          # zeigen, was entstünde, ohne zu schreiben
```

Der Aufruf geht von überall, wenn dieser Ordner im `PATH` steht;
sonst mit vollem Pfad auf `stimme.cmd`. Das Skript findet seine eigene
Umgebung selbst.

## Was wo liegt

| | |
|---|---|
| `stimme.py` | das Werkzeug |
| `stimme.cmd` | ruft es mit der eigenen Umgebung auf, egal von wo |
| `stimmen/` | **die Vorlagen, aus denen geklont wird** — je eine `.wav` und die gleichnamige `.txt` mit dem Wortlaut |
| `vorlagen/` | die vollen Originalaufnahmen, aus denen die Vorlagen geschnitten sind |
| `proben/` | Probeläufe zum Hineinhören, gehören zu keinem Projekt |
| `anforderungen.txt` | die eingefrorenen Versionen |
| `.venv/` | die Umgebung, rund 2,5 GB |

## Eine Stimme dazulegen

Zwei Dateien nach `stimmen/`, gleicher Name:

```
stimmen/annika.wav     15 bis 20 Sekunden, mono, ruhig gesprochen
stimmen/annika.txt     was darauf gesagt wird, wortgleich
```

Mehr nicht — kein Code, keine Liste, die gepflegt werden müsste.
`--stimmen` zeigt danach die neue an und meldet **OHNE TEXT**, falls die
`.txt` fehlt.

**Der Wortlaut ist Pflicht, nicht Empfehlung.** Das Modell trennt damit
Stimme von Inhalt und bricht ohne ihn ab. Das Werkzeug sagt es sofort,
statt erst nach dem Laden der Gewichte.

**Und die Vorlage muss jemandem gehören, der einverstanden ist.** Beide
Stimmen hier stammen von LibriVox — dort widmen die Sprecher ihre
Aufnahmen der Gemeinfreiheit, und der Buchtext liefert den Wortlaut
gleich mit. Eine fremde Stimme aus einem Video oder Podcast zu klonen,
ist etwas anderes, und die Modellkarte sagt dasselbe.

## Eine Vorlage ohne Audiodatei

Das Modell nimmt statt einer Aufnahme auch die Codes, die sein Codec
daraus macht. Aus 1,7 MB `wav` werden 8 KB, und in `stimmen/` liegt
nichts mehr, was ein Abspieler öffnet.

```bash
stimme --einfrieren mann                 # stimmen/mann.stimme,  8 KB
stimme --einfrieren mann --schluessel    # stimmen/mann.stimme.gpg, verschlossen
```

Der Wortlaut steckt mit im Behälter — die `.txt` daneben entfällt. Beim
Sprechen ändert sich nichts: `-s mann` findet die eingefrorene Vorlage
genauso wie die Aufnahme. Liegen beide da, gewinnt die Aufnahme.

**Die Codes sind eine Verkleinerung und kein Schutz.** `decode_audio`
rechnet sie zurück in Sprache, und heraus kommt die Aufnahme — hörbar
dieselbe Person. Wer die Codes hat, hat die Stimme. Für ein
öffentliches Repository gehört deshalb `--schluessel` dazu.

## Auf einen anderen Rechner

Zu übertragen sind drei Dinge, und nur eines davon ist heikel.

**Das Werkzeug** ist Text: `stimme.py`, `stimme.cmd`, `LIESMICH.md`,
`anforderungen.txt`. Das gehört ins Repository.

**Die Umgebung** wird drüben neu gebaut, nicht kopiert — `.venv` sind
2,5 GB und an den Rechner gebunden. Das Modell lädt beim ersten Lauf
selbst nach.

**Die Vorlagen.** Gemeinfreies (LibriVox) kann offen mitfahren. Die
eigene Stimme nicht: `--einfrieren --schluessel` macht daraus 8 KB
AES-256, und die dürfen in ein öffentliches Repository. Auf dem anderen
Rechner fragt `gpg` beim ersten Sprechen nach der Passphrase und
entschlüsselt nur in den Arbeitsspeicher; auf der Platte bleibt es
verschlossen.

```bash
git clone …
python -m venv .venv
.venv\Scripts\python -m pip install -r anforderungen.txt
stimme "Probe." -s mann -o probe.mp3     # gpg fragt nach der Passphrase
```

Die Passphrase gehört in den Kopf oder in einen Passwortspeicher, nicht
ins Repository. `STIMME_KENNWORT` gibt es für Skripte — dort steht das
Kennwort in der Prozessliste, also nur benutzen, wo das nichts ausmacht.

Was **nicht** mitfährt: `vorlagen/` (die vollen Originalaufnahmen),
`proben/`, `test/`, `.venv/` und offene `stimmen/*.wav`, sofern sie
nicht gemeinfrei sind.

## Wie die Dateien heißen

Nach ihrem Satz: acht Zeichen aus dessen Prüfsumme. Das hat drei
Folgen, und alle drei sind der Grund für diese Bauart.

Ein zweiter Lauf **überspringt, was schon da ist** — man kann abbrechen
und weitermachen, und eine einzelne Zeile nachziehen, indem man ihre
Datei löscht.

Ändert sich ein Satz, **ändert sich sein Name**. Eine alte Aufnahme wird
also nie stillschweigend zu einem geänderten Text weiterbenutzt; sie
verwaist, sichtbar.

Und ein Projekt kann denselben Namen ausrechnen, ohne dass hier eine
Liste gepflegt werden müsste.

Mit `-o` gibt man den Namen selbst vor, wenn es nur ein Satz ist.

## Der Pegel wird gemessen, nicht geraten

`ffmpeg` liest die tatsächliche Spitze ab, und genau die Differenz wird
angewendet — Ziel sind −6 dB, änderbar mit `--spitze`. Stille am Anfang
und Ende fällt weg. Das ist kein Schönheitsschritt: dasselbe Modell
liefert je nach Vorlage und Satzlänge um mehr als 9 dB verschieden
laut, und ohne diesen Schritt wären die Zeilen einer Figur untereinander
unbrauchbar ungleich.

Ohne `ffmpeg` im Pfad bleibt es bei rohem WAV, und das Werkzeug sagt es.

## Das Modell

`Audio8/Audio8-TTS-Preview-0.1b` — 170M Parameter plus 120M für den
Decoder, 44,1 kHz, Zero-Shot-Klon. Deutsch ist dort **experimentell**;
Hauptsprachen sind Chinesisch und Englisch. Es klingt trotzdem
brauchbar, aber das ist Glück und kein Versprechen.

Die Lizenz ist umsatzgedeckelt (*Audio8 Community License v1.0*):
nichtkommerziell frei, Firmen unter zwei Millionen Umsatz frei, darüber
schriftlich. Kein offener Standard also — für ein kostenloses Spiel
unproblematisch, für ein Produkt nachzulesen.

Ein anderes Modell nimmt man mit `--modell` oder der Umgebungsvariablen
`STIMME_MODELL`.

## Wenn die Umgebung neu muss

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r anforderungen.txt
```

**Nicht** einfach `pip install transformers`: das Modell hängt an 4.x
und stirbt an 5.x mit einem fehlenden Import. Genau dafür sind die
Versionen eingefroren.
