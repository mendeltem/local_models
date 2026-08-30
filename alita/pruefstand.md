# Prüfstand — kann Clara die Arbeit allein?

> Auf Victus geschrieben, auf **Lesbarkeit** geprüft. Kein Skript hier ist auf
> Alita gelaufen. Die Netzsperre ist der riskanteste Teil: sie hängt an
> `unshare` und an Kernel-Einstellungen, die ich von hier aus nicht sehen kann.
> Erst Schritt 0 dieser Seite abarbeiten, dann dem Rest glauben.

Die Frage ist **nicht** „ist Clara so gut wie Claude". Die Antwort darauf steht
vorher fest und beantwortet nichts. Die Frage ist:

**Reißt Clara die Latte, die die Arbeit verlangt — ohne Netz, ohne Aufsicht?**

Claude setzt die Latte und schreibt den Auftrag. Claude ist nicht der Gegner im
Vergleich, sondern das Werkzeug, das den Maßstab herstellt.

---

## Die drei Arme

Ein einzelner Vergleich „mit Claude / ohne Claude" wirft zwei verschiedene
Fähigkeiten in eine Zahl. Wenn Claude den Auftrag schreibt, hat Claude den
schwersten Teil schon erledigt — die Zerlegung. Der „ohne Claude"-Lauf ist dann
kein unbeaufsichtigter Lauf, sondern einer mit vorgedachtem Bauplan.

Deshalb drei Arme statt zwei:

| Arm | Clara bekommt | Netz | misst |
|---|---|---|---|
| **A** | Auftrag von Claude, Claude während der Arbeit erreichbar | offen | die Obergrenze |
| **B** | Auftrag von Claude | **gesperrt** | **Ausführung** |
| **C** | nur den Zielsatz, kein Auftrag | **gesperrt** | **Zerlegung** |

`A − B` ist der Wert lebender Hilfe. `B − C` ist der Wert der Zerlegung.

Der Zielsatz für Arm C ist ein Satz, nicht mehr. Beispiel:

> Bring den Datensatz unter `~/daten/wmh-roh` nach BIDS.

Arm B bekommt zur selben Aufgabe zwei Seiten: Ordnerstruktur, Namensschema,
welche Felder in `dataset_description.json` gehören, was der Validator prüft.

**Vermutung vor der Messung** (damit sie hinterher nicht nachgeschärft wird):
B geht überraschend gut, C fällt deutlich ab. Wenn B ebenfalls scheitert, liegt
es am Gerüst, nicht am Modell.

---

## Die Leiter

Nicht mit der WMH-Segmentierung anfangen. Das sind fünfzehn Aufgaben über
Stunden — scheitert es, weißt du nur *dass*, nicht *wo*.

| Stufe | Aufgabe | Dauer | Läufe je Arm |
|---|---|---|---|
| **1** | BIDS-Konvertierung · stratifizierter 5-fach-Split · Dice-Auswertung zweier Masken | Minuten | 10 |
| **2** | Training auf 20 Fällen gegen eine Untergrenze · QC-Bericht erzeugen | ~1 h | 3 |
| **3** | volles WMH-Training · Mikroblutungen · `recon-all` graue Substanz | Stunden–Tage | 1 |
| **4** | statistische Auswertung samt Deutung | | 3 |

Zehn Läufe auf Stufe 1, weil das Modell stochastisch ist — eine einzelne
Beobachtung bei `temp > 0` ist keine Messung. Ein Lauf auf Stufe 3, weil das
eine Demonstration ist und keine Statistik.

Stufe 4 zuletzt. Deutung ist das Einzige hier, das sich nicht hart prüfen lässt;
solange die unteren Stufen wackeln, misst man dort nur Rauschen.

---

## Abnahmekriterien

Jede Aufgabe braucht ihr `pruefe.py`, **geschrieben bevor die Aufgabe läuft**,
und selbst gegengerechnet. Der Grund steht in
[`codetest/LIESMICH.md`](codetest/LIESMICH.md): der erste Sollwert dort war von
Hand gerechnet und falsch, das Modell hatte recht. Ein Prüfwerkzeug, dessen
eigener Fehler wie ein Befund aussieht, verdirbt alles dahinter.

**Kein Modell urteilt.** Auch nicht Claude.

### 1a — BIDS-Konvertierung

| Prüfung | bestanden wenn |
|---|---|
| `bids-validator` | Rückgabewert 0, keine Meldung der Stufe `error` |
| Vollzähligkeit | jeder Proband aus der Rohablage hat `anat/sub-<id>_T1w.nii.gz` und `_FLAIR.nii.gz` |
| `dataset_description.json` | gültiges JSON, `Name` und `BIDSVersion` vorhanden |
| `participants.tsv` | Zeilenzahl gleich Zahl der `sub-*`-Ordner, Spalte `participant_id` deckungsgleich |
| Unversehrtheit | Prüfsumme der Bilddaten gleich der Rohablage — **umbenannt, nicht neu geschrieben** |

Die letzte Zeile ist die wichtigste. Eine Konvertierung, die nebenbei
Voxelwerte ändert, besteht sonst alle anderen Prüfungen.

### 1b — Stratifizierter 5-fach-Split

| Prüfung | bestanden wenn |
|---|---|
| Disjunkt | kein Proband in zwei Falten |
| Vollständig | Vereinigung aller Falten gleich der Gesamtmenge |
| Stratifiziert | Anteil der Zielklasse je Falte weicht höchstens 5 Prozentpunkte vom Gesamtanteil ab |
| Reproduzierbar | zweiter Lauf mit gleichem Seed erzeugt bitgleiche Aufteilung |
| Kein Leck | kein Proband mit mehreren Aufnahmen über Falten verteilt |

### 2 — Training gegen eine Untergrenze

Die Untergrenze kommt aus einem **Grundlinienlauf**, nicht aus der Literatur:
eine simple Schwellwertsegmentierung auf denselben Daten. Besteht, wer sie
schlägt. Dazu: Verlust ohne `NaN`, Prüfpunkt ladbar, Inferenz auf einem
ungesehenen Fall liefert eine Maske mit plausibler Volumenordnung.

### 3 — Mikroblutungen

**Nicht Dice.** Sensitivität und Falschpositive pro Fall — bei Läsionen von
wenigen Voxeln ist Dice fast nur Rauschen. Der `detektion`-Fall in
[`codetest/aufgaben.py`](codetest/aufgaben.py) prüft genau diese Unterscheidung
schon auf Modellebene.

### 3 — FreeSurfer, graue Substanz

`recon-all` Rückgabewert 0, `aseg.stats` maschinell lesbar, Volumina der grauen
Substanz gegen einen Referenzlauf: ICC über die Probanden, nicht Gleichheit im
Einzelfall.

---

## Der Engpass, der die Architektur bestimmt

**Clara kann nicht denken, während die GPU trainiert.**

`llama-server` hält 21.451 MiB der 24.564 MiB. Es bleiben 3.113 MiB. Ein echtes
Training passt da nicht daneben. Für jede Aufgabe der Stufen 2 und 3 gilt also
zwangsläufig eines von beiden:

- das Gerüst entlädt Clara vor dem Training und lädt sie danach — die
  Agentenschleife ist für Stunden tot
- oder das Training bleibt so klein, dass es in 3 GB passt — dann testest du
  nicht die Aufgabe, die du testen wolltest

Damit wird eine Fähigkeit prüfbar, die sonst niemand prüft:

**Kann der Agent Arbeit so strukturieren, dass sie ohne ihn weiterläuft?**

Auftrag wegschreiben, Zustand ablegen, sich selbst abschalten, nach dem
Neuladen den Faden wieder aufnehmen. Wer das kann, ist hier brauchbar. Wer nach
dem Neustart von vorn anfängt oder den halbfertigen Stand übersieht, nützt auch
mit gutem Dice nichts.

Das gehört als eigene Prüfung gemessen, nicht als Nebenbedingung:

| Prüfung | bestanden wenn |
|---|---|
| Übergabe | vor dem Entladen liegt ein Zustand auf Platte, aus dem sich weiterarbeiten lässt |
| Wiederaufnahme | nach dem Neuladen wird der Zustand gelesen und **nicht** neu begonnen |
| Erkennen | ein abgebrochener Trainingslauf wird als abgebrochen erkannt, nicht als fertig |

Die Zeit für Entladen und Laden wird mitgeschrieben. Bei 16 GB von SSD ist das
kein Rundungsfehler.

---

## Netzsperre ohne Root

Alita hat kein sudo. `nftables` und `iptables` fallen damit aus. Was bleibt, ist
ein unprivilegierter Namensraum:

```bash
alita/werkzeuge/netzsperre/netzsperre.sh -- ./mein-lauf.sh
```

Das Skript spannt einen Netz-, Mount- und Benutzer-Namensraum auf, in dem es
**nur Loopback** gibt. Kein Weg nach draußen, keine Regel, die man vergessen
kann — die Route existiert schlicht nicht.

Zwei Dinge, die daran wichtig sind:

**Clara muss innerhalb des Namensraums starten.** Ein Loopback im neuen
Namensraum ist nicht das Loopback des Rechners. Ein `llama-server`, der vorher
draußen läuft, ist von drinnen **nicht** erreichbar. Das Skript startet ihn
deshalb selbst mit hinein. Das ist der Grund, warum der Prüfstand den Server
stoppen und neu starten können muss.

**Jeder Netzversuch wird protokolliert.** Im Namensraum läuft eine winzige
DNS-Senke, die jede Namensauflösung mitschreibt und mit `NXDOMAIN` beantwortet.
Das ist kein Betriebsdetail, das ist ein **Messwert**:

> Clara hat 14-mal ins Netz gegriffen, davon 9-mal nach PyPI, 3-mal nach einer
> Doku-Seite, 2-mal nach einem Modell-Spiegel.

Das sagt dir, was das Modell stillschweigend voraussetzt — und was in den
Auftrag gehört, damit es das nicht mehr tut. Verbindungen auf nackte IPs
scheitern ohne Eintrag; die Senke sieht nur Namen. Das ist in der Praxis fast
alles.

### Vorher bereitlegen

Sonst stirbt der Lauf an `pip install nibabel` und du hast deinen Paketcache
gemessen statt des Agenten:

- Wheels lokal spiegeln (`pip download -r anforderungen.txt -d ~/raeder`),
  im Auftrag auf `--no-index --find-links` hinweisen
- FreeSurfer-Lizenz an ihrem Platz
- Modellgewichte und Datensatz auf Platte
- `~/.cache/torch`, `~/.cache/huggingface` vorgefüllt

---

## Schritt 0 — der Durchstich

**Nicht mit der WMH-Segmentierung anfangen.** Zuerst eine einzige Aufgabe der
Stufe 1 durch alle drei Arme, zehnmal je Arm: BIDS-Konvertierung, Richter ist
`bids-validator`. Ein Nachmittag statt einer Woche.

Danach weißt du, ob der Prüfstand selbst trägt:

1. Hält die Netzsperre? (Gegenprobe: `curl` auf eine bekannte Adresse **muss**
   scheitern, und der Versuch **muss** im Protokoll stehen)
2. Übersteht der Zustand einen Neustart von Clara?
3. Ist die Prüfung falsch-negativ? (Gegenprobe: einen von Hand korrekt
   konvertierten Datensatz durchschicken — er **muss** bestehen)
4. Ist die Prüfung falsch-positiv? (Gegenprobe: einen absichtlich kaputten
   Datensatz durchschicken — er **muss** durchfallen)

Punkt 3 und 4 sind nicht optional. Eine Prüfung, die nie jemand gegen ein
bekannt gutes und ein bekannt schlechtes Ergebnis gehalten hat, ist eine
Vermutung mit Rückgabewert.

Erst wenn dieser Durchstich sauber ist, lohnt Stufe 3.

---

## Was mitgeschrieben wird

Ein Lauf ist eine Zeile in `alita/laeufe.csv`:

```
datum,aufgabe,arm,seed,modell,schritte,token_ein,token_aus,sekunden,
neuladungen,netzversuche,pruefung,bemerkung
```

| Spalte | warum |
|---|---|
| `arm` | A, B oder C — ohne das ist die Zeile wertlos |
| `seed` | Läufe sind sonst nicht vergleichbar |
| `schritte` | wo das Budget ausging |
| `neuladungen` | wie oft Clara für die GPU weichen musste |
| `netzversuche` | der Befund aus der DNS-Senke |
| `pruefung` | `bestanden` / `durchgefallen` / `abgebrochen` — vom Skript, nicht vom Modell |

`abgebrochen` ist ein eigener Ausgang, nicht `durchgefallen`. Ein Lauf, der am
Zeitbudget endet, sagt etwas anderes als einer, der ein falsches Ergebnis
liefert — dieselbe Unterscheidung, die `urteil.py` mit `unentschieden` schon
für die Laufwache trifft.

---

## Was ich bewusst weglasse

**Clara gegen Claude auf Ergebnisqualität.** Das Ergebnis steht vorher fest,
kostet Rechenzeit und beantwortet keine Frage, die offen ist.

**Modell-als-Richter für die Abnahme.** Nicht weil es nicht ginge, sondern weil
der Prüfstand dann selbst die Eigenschaft hat, die er messen soll. Wo ein Urteil
unvermeidlich ist — Stufe 4 —, wird es von Hand gefällt und als solches
gekennzeichnet.

**Vergleiche zwischen Alita und Victus.** Andere Karte, anderes Modell, anderer
Engpass. Die Zahlen sehen vergleichbar aus und sind es nicht.
