# Woher diese Vorlagen stammen

Beide sind **LibriVox** — gemeinfrei, weil die Sprecher ihre Einspielungen
der Gemeinfreiheit widmen. Deshalb dürfen sie hier offen liegen.

| Vorlage | Aufnahme | Sprecher |
|---|---|---|
| `frau.stimme` | *Denkwürdigkeiten eines englischen Edelmannes aus dem großen Kriege* | LibriVox |
| `mann.stimme` | Brüder Grimm, *Die Haselrute* | Reiner Opgen-Rhein |

Beide sind auf rund 20 Sekunden geschnitten und eingefroren: statt der
`wav` liegen hier die Codec-Codes, 8 KB je Stimme, mit dem Wortlaut im
selben Behälter. `stimme --stimmen` zeigt sie an, `-s frau` benutzt sie.

## Eine eigene Stimme dazulegen

Nicht offen. Die Codes lassen sich in hörbare Sprache zurückrechnen —
wer sie hat, hat die Stimme. Für alles, was nicht gemeinfrei ist:

```bash
stimme --einfrieren meinname --schluessel
```

Das ergibt `meinname.stimme.gpg`, AES-256, und die Passphrase bleibt bei
dir. Näheres im `LIESMICH.md` unter *Auf einen anderen Rechner*.

Und was für jedes Klonverfahren gilt: eine fremde Stimme nur mit dem
Einverständnis dessen, dem sie gehört.
