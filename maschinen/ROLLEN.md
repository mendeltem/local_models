# Welche Maschine wofür

Die Aufteilung stand bisher nur auf dem USB-Stick (`WELCHE-MASCHINE.md`) und
war damit nirgends versioniert. Wer einen Befehl auf der falschen Maschine
laufen lässt, verliert im besten Fall Zeit — im schlechteren misst er etwas,
das für die Zielmaschine nichts aussagt.

| Maschine | Rolle | Was dort **nicht** hingehört |
|---|---|---|
| **Victus** | Recherche und Strategie. Lesen, denken, Werkzeuge bauen, Pläne schreiben. | Messen und Testen. Laden. |
| **PC_1** | Laden. Alles, was über eine brauchbare Leitung kommen muss. | Rechnen. Entscheiden. |
| **Alita** | Die wirkliche Arbeit: verbessern, messen, testen. | Laden — 36 Byte/s. |

## Warum das nicht Geschmack ist

**Alita lädt nichts.** Gemessen 36 Byte/s. Damit ist selbst ein Gigabyte
unerreichbar, und alles, was größer als ein paar Megabyte ist, muss über
`alita/ZU-LADEN.md` und den Stick oder die Freigabe kommen. Die Bestellliste
dort ist der vorgesehene Weg; eine zweite Liste anzulegen, schafft nur eine
zweite Wahrheit.

**Victus misst nichts, was für Alita zählt.** Der Laptop trägt eine RTX 4070
Laptop mit 8 GB und ein MoE-Modell mit 8 von 256 aktiven Experten; Alita trägt
eine A5000 mit 24 GB und ein dichtes 27-B-Modell. Ein Durchsatzwert vom Laptop
sagt über die Workstation nichts — im ungünstigen Fall sogar das Gegenteil.
Wertvoll ist deshalb das **Werkzeug**, das eine Messung durchführt, nicht die
Zahl, die es auf Victus liefert.

**Was auf Victus trotzdem richtig ist:** alles, was maschinenunabhängig ist.
Ein Linter, ein Auftragsformat, eine Testbatterie, ein Plan, eine Recherche.
Diese Dinge kommen per `git pull` auf Alita an und funktionieren dort
unverändert — sie brauchen weder GPU noch Daten noch Leitung.

## Die Faustregel

> Wenn das Ergebnis eine **Zahl** ist, gehört es auf Alita.
> Wenn es eine **Datei aus dem Netz** ist, gehört es auf PC_1.
> Wenn es ein **Werkzeug oder ein Gedanke** ist, darf es auf Victus entstehen.

## Offen

- Welcher Rechner genau **PC_1** ist, steht hier nicht. `alita/ZU-LADEN.md`
  nennt als Kandidaten mit Leitung `s-c15-csb-app01` (~20 MB/s),
  `s-csb-wiki-hub` (~23 MB/s) und einen Windows-Rechner hinter einem Proxy
  (0,15–10 MB/s), der `E:` (Stick) und `S:` (Freigabe) sieht. Wer das weiß,
  trägt es hier ein.
- `WELCHE-MASCHINE.md` auf dem Stick ist ausführlicher und nennt Befehle je
  Rechner. Solange beide Fassungen nebeneinander stehen, gilt die auf dem
  Stick — sie war am 28.08. schon einmal die neuere von beiden
  (`BLACKBOARD [18]`: die lokale Fassung trug eine kaputte Sollgröße, die auf
  dem Stick die richtige).
