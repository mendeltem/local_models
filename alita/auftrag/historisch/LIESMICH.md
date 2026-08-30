# Historische Aufträge — Prüfsteine für `vorflug`

Zwei Aufträge, die tatsächlich gelaufen sind, rekonstruiert aus der Tafel. Sie
sind der Maßstab für [`werkzeuge/vorflug`](../../werkzeuge/vorflug): ein Linter,
der nach Geschmack gebaut ist, misst Geschmack. Einer, der gegen Fälle gebaut
ist, die Stunden gekostet haben, misst etwas.

| Datei | Urteil | Warum |
|---|---|---|
| [`microbleed-27-08.auftrag`](microbleed-27-08.auftrag) | **abgelehnt** | Die Quelle des einzigen Ziels existiert, ist aber leer. Dem Auftrag fehlt die erste Stufe. |
| [`microbleed-28-08.auftrag`](microbleed-28-08.auftrag) | **startklar** | Alles erfüllbar — und der Lauf scheiterte trotzdem: 173 Aufrufe, 966 500 Token, 2 h 17 min, null Dateien. |

Die zweite Zeile ist die wichtigere. Sie steht hier, damit niemand `vorflug` für
mehr hält, als es ist: **es prüft Erfüllbarkeit, nicht Größe.** `BLACKBOARD [26]`
verlangt von jedem, der einen Indikator baut, vorher zu sagen, welchen Fall er
nicht erkennt. Diese Datei ist die Antwort.

## Was hier nicht steht

`unet-qc` und `mb1` — die beiden gelungenen Aufträge — fehlen absichtlich. Sie
ließen sich aus der Tafel nur teilweise rekonstruieren: bei `unet-qc` ist von
den 15 Abnahmekriterien genau eines wörtlich überliefert (`enthaelt bericht.md
Dice`, `BLACKBOARD [15]`), bei `mb1` lässt sich die Zahl 424 aus `docs/05` nicht
mit den 62+150 aus `BLACKBOARD [2]` zusammenbringen.

`docs/06-vorhaben.md` Teil A2 sagt dazu: *„Ein Linter, dessen Zustimmung auf
einer erfundenen Rekonstruktion beruht, ist schädlicher als einer, der nur
ablehnt."* Deshalb warten die positiven Fälle, bis sie auf Alita an den echten
Pfaden nachgeschlagen werden können.

## Auf Victus prüfbar, auf Alita beurteilbar

Die Pfade in diesen Dateien sind Alita-Pfade. Auf Victus gibt es sie nicht —
dort lässt sich nur prüfen, dass die Dateien **lesbar** sind:

```bash
python alita/werkzeuge/vorflug alita/auftrag/historisch/microbleed-27-08.auftrag --zeigen
```

Das macht `pruefe-vorflug.py` bei jedem Lauf mit. Das **Urteil** aus der Tabelle
oben lässt sich erst auf Alita nachvollziehen, und auch dort nur, wenn der
Zustand von damals wiederhergestellt ist — die Verzeichnisse sind seit dem
28.08. gefüllt.

Der maschinenunabhängige Ersatz dafür sind die Fälle in `pruefe-vorflug.py`:
`quelle-existiert-aber-leer` bildet die Form vom 27.08. nach und baut sich
seine leeren Verzeichnisse selbst.

## Was beim Rekonstruieren aufgefallen ist

**Der 27.08. hatte zwei unabhängige Ursachen, nicht eine.** `BLACKBOARD [2]`
nennt die fehlende erste Stufe, `BLACKBOARD [4]` nennt `system/current-quant`
auf `q5` — 32768 Kontext, während Hermes mindestens 64000 verlangt. Der Agent
kam nie hoch. `vorflug` sieht davon genau eine Ursache. Wer nach einer
bestandenen Vorflugprüfung annimmt, der Auftrag könne jetzt nur noch am Inhalt
scheitern, irrt.

**Zeilennummern taugen nicht als Beleg.** Beim Rekonstruieren waren mehrere
Fundstellen schon veraltet, weil die zitierten Dateien zwischenzeitlich
gewachsen sind. Eintragsnummern (`BLACKBOARD [2]`) und wörtliche Zitate halten,
Zeilennummern nicht.
