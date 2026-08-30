# 06 — Vorhaben: was als Nächstes gemessen und geändert wird

Stand 29.08.2026. Abgeleitet aus einer Recherche über acht Perspektiven mit
Faktenprüfung (51 geprüfte Ansätze) und einer Prüfung des eigenen Codes
(32 bestätigte Befunde).

Dieses Blatt ist eine **Arbeitsschlange**, kein Bericht. Jeder Punkt hat einen
ersten Befehl und ein Abbruchkriterium. Was erledigt ist, wandert nach Teil C.

## Wie das zu lesen ist

| Marke | Bedeutung |
|---|---|
| **[belegt]** | Primärquelle gelesen und genannt, oder auf einer der Maschinen gemessen |
| **[plausibel]** | folgt aus Belegtem, aber nicht direkt belegt |
| **[ungeprüft]** | Annahme. Noch hat niemand nachgesehen |

Die Trennung ist der Punkt. Ein Vorhaben mit der Marke **[ungeprüft]** darf
nicht als Grundlage für ein zweites dienen.

---

## Teil A — auf Victus: Werkzeuge bauen, nicht messen

Die Rollenverteilung steht in [`maschinen/ROLLEN.md`](../maschinen/ROLLEN.md).
Kurz: **Victus ist für Recherche und Strategie da.** Messen und Testen gehört
auf Alita, Laden auf PC_1 über [`alita/ZU-LADEN.md`](../alita/ZU-LADEN.md).

Die Faustregel dazu: ist das Ergebnis eine **Zahl**, gehört es auf Alita — ist
es ein **Werkzeug oder ein Gedanke**, darf es hier entstehen. Ein Durchsatzwert
vom Laptop sagt über die Workstation nichts; wertvoll ist das Werkzeug, das die
Messung durchführt, nicht die Zahl, die es auf Victus liefert.

Alles in Teil A ist deshalb maschinenunabhängig: es kommt per `git pull` auf
Alita an und läuft dort unverändert, ohne GPU, ohne Daten, ohne Leitung.

Zwei Tage sind rund 16 Arbeitsstunden. Die geprüften Vorhaben summieren sich auf
etwa zehn Arbeitstage — es werden also **zwei Werkzeuge fertig, nicht acht**.

### A1 — `vorflug`: das Auftragsformat und seine mechanische Vorprüfung **[belegt]**

Der teuerste gemessene Fehlschlag des Projekts war kein Modellfehler. `BLACKBOARD [2]`:
die Abnahme verlangte 62 SWI- und 150 T2*-Dateien, beide Verzeichnisse waren leer,
die Quelldaten lagen woanders. Zwei Anläufe, rund 2 h 50 min, null Dateien.

Ein zeilenweises `.auftrag`-Format mit sieben Wörtern — `auftrag`, `arbeit`,
`ziel`, `frage`, `quelle`, `soll`, `bleibt` — und ein Werkzeug, das es **vor dem
Start** prüft: sind alle Quellen auflösbar, ist jede `soll`-Zeile jetzt noch
falsch (Nullmessung), ist jede `bleibt`-Zeile jetzt wahr, sind die Zielverweise
zyklenfrei, liegen alle Pfade unter `{arbeit}`.

Aus demselben Auftrag erzeugt `vorflug --liste N` die schlichte Abnahmeliste je
Teilziel, die `abnahme` und `laufwache` heute schon lesen. Nichts Bestehendes
wird geändert.

**Die einzigen zwei Belegstellen im Repo** — erst lesen, dann bauen:

```bash
grep -n -B4 -A6 "genau /path" docs/05-scaffolding.md
sed -n '77,108p' alita/werkzeuge/laufwache
```

Daraus steht fest, was `vorflug` über `abnahme` wissen darf: drei Verben
(`genau <glob> <n>`, `datei <pfad>`, `enthaelt <pfad> <text>`) und eine
Ausgabezeile, `Abnahme: N erfuellt`. Mehr ist auf Victus nicht belegbar.

Die Wahrheitswerte kommen über **eine** einspeisbare Quelle: `--pruefer <kommando>`,
Vorgabe eine mitgelieferte Referenzfassung der drei Verben. Auf Alita wird
`--pruefer` auf das echte `abnahme` umgestellt — und der erste Befehl dort ist
nicht der Einsatz, sondern der Abgleich: dieselbe Liste durch beide Prüfer, auf
Gleichheit prüfen. Weichen sie ab, gilt `abnahme`.

**Abbruchkriterium:** braucht die Referenzfassung mehr als 60 Zeilen, ist die
Kriteriensyntax reicher als `docs/05` zeigt. Dann nicht weiterraten — `vorflug`
ohne Wahrheitswerte bauen (nur Quellen-, Pfad- und Zyklenprüfung) und die
Nullmessung auf Alita nachrüsten.

**Zeitbedarf:** ein bis anderthalb Tage.

### A2 — Obduktion: der Linter gegen die vier echten Aufträge **[belegt]**

Die vier gemessenen Aufträge im neuen Format rekonstruieren und als
Regressionstest festschreiben. Jede Datei mit Kopfzeile *„rekonstruiert aus
BLACKBOARD [n], nicht der Originaltext"*. Sollvorgabe:

| Auftrag | muss |
|---|---|
| `unet-qc` | durchgehen |
| `mb1` (Symlinkstufe) | durchgehen |
| `microbleed` 27.08. | **abgelehnt werden** — Quelle des ersten Ziels ist leer |
| `microbleed` 28.08. | **durchgehen und trotzdem scheitern** |
| `mb2` | **durchgehen und trotzdem scheitern** — 50 min Quelltext vor der ersten Datei |

`mb2` fehlte in der ersten Fassung dieser Tabelle. `docs/05-scaffolding.md`
misst vier Aufträge — `unet-qc`, `mb1`, `microbleed-gesamt`, `mb2` —, und
`microbleed-gesamt` lief an zwei Tagen. Wer die zwei Tage einzeln zählt und
`mb2` weglässt, kommt auf vier und merkt die Vertauschung nicht. `mb2` gehört
dazu, gerade weil `vorflug` auch ihn nicht fängt: zu langes Lesen ist kein
Erfüllbarkeitsproblem.

**Belege nicht an Zeilennummern hängen.** `docs/06` ist zwischen zwei Commits
um zehn Zeilen gewachsen und die A2-Tabelle mit ihr. Ein Regressionstest, der
seine Belege über Zeilennummern in einer bewegten Datei verankert, verankert
nichts — Eintragsnummern (`BLACKBOARD [2]`) und wörtliche Zitate halten,
Zeilennummern nicht.

Der vierte Fall ist der wichtigste und gehört als **Negativbefund wörtlich in
den Kopf des Werkzeugs**:

> `vorflug` prüft Erfüllbarkeit, nicht Größe. Der teuerste gemessene Lauf des
> Projekts — 173 Aufrufe, 966 500 Token, 0 Dateien — hätte diese Prüfung
> bestanden.

`BLACKBOARD [26]` verlangt genau das von jedem, der einen neuen Indikator baut:
vorher sagen können, welchen Fall er **nicht** erkennt.

**Abbruchkriterium:** lässt sich `unet-qc` oder `mb1` nicht aus dem Repo
rekonstruieren, nur die zwei negativen Fälle festschreiben. Ein Linter, dessen
Zustimmung auf einer erfundenen Rekonstruktion beruht, ist schädlicher als
einer, der nur ablehnt.

**Zeitbedarf:** halber Tag.

### A3 — Bruchfall-Katalog und `bestand.py` **[belegt]**

`vorflug` prüft, ob ein Pfad auflösbar ist. `bestand.py` sagt, ob das, was dort
liegt, brauchbar ist. Zusammen hätten sie den Fall vom 27.08. vollständig
abgefangen.

Erst 12 bis 20 absichtlich kaputte NIfTI-Dateien mit erwartetem Urteil in einer
JSON-Tabelle — synthetisch, wenige hundert Kilobyte, darf ins öffentliche Repo.
Beim Orientierungsfall gegen **LPS** kippen, nicht gegen RAS/LAS: LPS ist der
echte Fall auf Alita.

Vier Pflichtfälle, falls die Zeit knapp wird — sie entsprechen `LEKTIONEN` 9
und 12 direkt: Dublette `.nii`/`.nii.gz`, leere Maske, Form-Ungleichheit,
nicht-binäre Maske.

Dann `bestand.py <wurzel> [--muster "**/*.nii.gz"]`, läuft einen Kohortenbaum ab
und schreibt `bestand.csv` und `FEHLT.md`. Zwingend **layoutfrei** — Fall-ID über
einen regulären Ausdruck als Argument, keine fest verdrahteten Ordnernamen.
Jede nicht ermittelbare Kennzahl wird `unbekannt`, nie ein plausibler
Ersatzwert.

**Fertig, wenn:** gegen den Bruchfall-Katalog mindestens drei Viertel der Fälle
richtig gemeldet werden, und ein Lauf über rund 70 Fälle unter einer Minute
bleibt. Dauert er länger, liest das Skript Bilddaten statt Kopfdaten — dann auf
`img.header` ohne `get_fdata` zurückschneiden.

**Zeitbedarf:** ein Tag für beides zusammen.

### Messungen — gehören auf Alita, nicht hierher

Diese Punkte standen in der ersten Fassung dieses Blatts unter „auf Victus".
Das war falsch: **jede Zahl gälte für den Laptop**, und Alitas Zahlen müssen
dort ohnehin neu gemessen werden. Beim MoE-Modell auf Victus kann das Ergebnis
sogar in die Gegenrichtung zeigen.

Was hier steht, ist deshalb die **Messvorschrift**, nicht der Messauftrag — sie
gehört nach Teil B und wird dort ausgeführt. Auf Victus lohnt allenfalls, das
Skript zu schreiben, das die Messung später auf Alita fährt.

**Der `-ncmoe`-Sweep.** `llama-bench` kann `-ncmoe` als Testparameter, was die
Handanleitung aus `docs/02-tuning.md` ersetzt. Zwei Korrekturen gegenüber der
ersten Fassung dieses Blatts, beide auf Victus geprüft: `sqlite3` liegt **nicht**
im PATH, und `-o` nimmt genau **einen** Wert aus `csv|json|jsonl|md|sql`. Richtig
ist `-o jsonl` — eine echte Obermenge von `sql`, zusätzlich mit `samples_ts`:

```bash
for n in 30 32 34 36 38; do
  llama-bench -m ~/models/Qwen3.6-35B-A3B-UD-IQ4_XS.gguf \
    -ngl 99 -ncmoe $n -p 4096 -n 128 --delay 20 -o jsonl >> messwerte.jsonl
done
```

Ein Prozess je Punkt: ein OOM beendet sonst den ganzen Lauf. `--delay 20` gegen
thermische Drosselung — auf einem Laptop kein Detail, sondern der Unterschied
zwischen Messung und Zufall. Die Zeile trägt `build_commit` mit, also ist nach
jedem llama.cpp-Update zuordenbar, welche Version eine Zahl verändert hat.

**`-ub` gegen `-ncmoe`.** Auf `-ub` wurde nie gedreht, obwohl es mit `-ncmoe` um
dasselbe VRAM konkurriert. Erwartung: 2 bis 3 Expert-Layer, also 6 bis 9 %
Decode.

**`ngram-mod` auf Victus.** Der Build kennt es, geprüft. Aber Victus trägt ein
MoE mit 8 von 256 aktiven Experten — genau der Fall, in dem der einzige
veröffentlichte Zahlensatz *negativ* ausfiel. Ein negatives Ergebnis hier sagt
deshalb **nichts** über Alita, wo ein dichtes Modell läuft.

**Die Aufgabenbatterie.** `docs/03-model-wiki.md` sagt „gemessen mit einer
Batterie fester Aufgaben" — diese Batterie liegt nicht im Repo. Vorbild:
`alita/codetest/lauf.py`. Zwei Reparaturen vorher: Zeile 6 zeigt auf ein
flüchtiges Scratchpad-Verzeichnis, und das Skript liefert immer Exit-Code 0.

**`detect.py` gegen ein dichtes Modell.** Der `key_length`-Fix ist noch nicht
gegen ein Nicht-Qwen-Modell geprüft. Zu prüfen: meldet es verständlich, dass
`-ncmoe` dort wirkungslos ist, statt still „0 von N Expert-Layern"?

## Teil B — vorbereitet für Alita

Fertige Befehle für die erste Sitzung zurück an der Maschine. Reihenfolge ist
bindend: B0 und B1 beantworten Fragen, von denen der Rest abhängt.

### B0 — Das Maschinenblatt erneuern **[belegt]**

`maschinen/erfassen.sh` schreibt seit dem 29.08. auch die Laufzeit mit: die
Build-Nummer von llama.cpp, die vollständige `--spec-type`-Liste dieses Builds,
und die Aufrufzeile jedes laufenden Servers aus `/proc/<pid>/cmdline`.

```bash
./maschinen/erfassen.sh --zeigen     # erst ansehen
./maschinen/erfassen.sh              # dann schreiben
```

**Beantwortet zwei offene Fragen auf einmal:** kennt Alitas Build `ngram-mod`
überhaupt, und mit welchen Flags läuft der Server wirklich (nicht: welche
stehen in `start.sh`).

### B1 — Was liegt in `modelle/embedding/`? **[ungeprüft]**

Der bestverzinste Vorschlag der ganzen Recherche lautet, einen Reranker zu
benutzen, der angeblich schon dort liegt. **Das steht nirgends im Repo.**
`maschinen/Alita-MS-7D91.md` listet nur Ordnernamen und Größen:
`encoder 1.1G`, `waechter 1.1G`, `embedding 1.8G`.

```bash
ls -la /home/uchralt/local_agentic_system/modelle/embedding/
ls -la /home/uchralt/local_agentic_system/modelle/encoder/
```

Ein Reranker adressiert direkt den teuersten gemessenen Fehlermodus — bei `mb2`
50 Minuten Quelltextlesen vor der ersten Datei. Er kostet kein VRAM (CPU) und
keinen Download. Aber ohne diesen `ls` ist der Vorschlag eine Vermutung.

**Der Weg dahinter ist kurz, falls der `ls` etwas findet** — auf Victus an
`llama-server --help` geprüft: llama.cpp kann Reranking nativ, über
`--rerank, --reranking` (per Vorgabe aus) zusammen mit `--pooling rank`. Es
braucht also keine zusätzliche Bibliothek, nur einen zweiten Server auf einem
eigenen Port.

Eine Größenordnung zur Erwartung, gemessen auf CPU: rund **3,2 s je 50
Kandidaten**. Das ändert den Entwurf — 3 Sekunden sind zu teuer für jeden
Aufruf. Der Reranker gehört hinter eine Option oder eine Unsicherheitsschwelle,
nicht in den Standardpfad.

### B2 — Trägt der Prefix-Cache? **[belegt, wie man es misst]**

Fünf unabhängige Perspektiven kamen auf diesen Hebel. Diese eine Zahl ordnet
alle übrigen Tempoarbeiten: trägt der Cache, ist Kontext ein VRAM- und
Qualitätsproblem; trägt er nicht, kostet jede Agentenrunde einen vollen
80k-Prefill und alles andere ist zweitrangig.

```bash
journalctl --user -u llama-server --since "24 hours ago" \
  | grep "prompt eval time" | tail -40
```

Genauer und ohne Logauswertung geht es über den **`/slots`-Endpunkt**, nicht
über `timings`. Zwei Dinge dazu, auf Victus an `llama-server --help` geprüft:

- `--slots` ist **per Vorgabe an** (`--slots, --no-slots … default: enabled`).
  Es braucht **kein** `--metrics` — das ist ein separater Prometheus-Endpunkt
  und per Vorgabe *aus*.
- `/slots` misst Claras echten Verkehr, statt dass man eine Testanfrage
  einschleust, die den Cache selbst verändert.

Die Feldnamen unterscheiden sich zwischen den beiden Orten — im `timings`-Objekt
heißen sie anders als unter `/slots`. Welche genau, ist auf Victus **nicht**
prüfbar, weil dafür ein laufender Server nötig wäre. Also am ersten Tag zurück
zuerst einmal `curl -s localhost:8000/slots | head -60` ansehen und die
tatsächlichen Namen hier eintragen, statt sie aus einer Anleitung zu übernehmen.

- unter 0,1 neu gerechnet → der Cache trägt. Ergebnis nach `docs/02` notieren,
  damit die Frage nicht wiederkommt.
- über 0,5 → Ursache suchen, bevor irgendein Flag gesetzt wird. Häufigster
  Grund ist ein wechselnder Kopf ganz vorn im Prompt (Zeitstempel,
  Rundennummer, neu sortierter Dateibaum). Zwei aufeinanderfolgende Anfragen an
  ihren ersten 200 Zeichen vergleichen.

### B3 — Die Speichergrenze prüfen **[plausibel]**

`alita/konfiguration/llama-server.service` setzt `MemoryMax=26G` mit dem
Kommentar „Gemessen 17,7 GiB RSS". Der Host-RAM-Prompt-Cache ist per Vorgabe
**an** und darf bis 8192 MiB wachsen. 17,7 + 8 = 25,7 GiB — das sind 0,3 GiB
unter der Grenze. Bei 62,6 GiB Gesamt-RAM ist die Grenze künstlich und stammt
aus einer Zeit vor dem Cache.

```bash
systemctl --user show llama-server -p MemoryHigh -p MemoryMax -p MemoryCurrent
```

Steht dort `infinity`, entfällt der Punkt. Steht dort 26G und `MemoryCurrent`
nahe 22G, ist das ein latenter Selbstabschuss — und muss **zusammen** mit
`--cache-ram` angehoben werden, nie das eine ohne das andere.

### B4 — `ngram-mod` einschalten **[belegt]**

Der einzige Tempohebel auf Alita, der an der VRAM-Wand nicht scheitert: kein
zweites Modell, kein zweiter KV-Cache, kein rs-Cache.

```bash
systemctl --user stop llama-server && sleep 20
LLAMA_ARG_SPEC_TYPE=ngram-mod ~/local_agentic_system/system/start.sh
```

Die 20 Sekunden sind nicht Vorsicht, sondern die Lektion vom 28.08.: systemd
startete alle 14 s neu, während das VRAM des abgestürzten Vorgängers noch nicht
frei war — dadurch sah ein Konfigurationsfehler nach Platzmangel aus.

Trägt es, dauerhaft als Drop-in ohne sudo:

```bash
systemctl --user edit llama-server
# [Service]
# Environment=LLAMA_ARG_SPEC_TYPE=ngram-mod
```

**Vergleichsgröße:** 33,55 tok/s bei 81920 Kontext.
**Abbruchkriterium:** unter +10 % auf echter Arbeit → Flag entfernen und eine
Zeile ins Modell-Wiki, damit es niemand nochmal probiert.

### B5 — Die Vorflug-Abnahme **[belegt]**

Jedes Abnahmekriterium bekommt eine `quelle`-Zeile: den Eingang, aus dem es
erfüllbar wäre. Der Lauf startet nur, wenn zu mindestens einem offenen
Kriterium die Quelle existiert.

`BLACKBOARD [2]` beschreibt den Fall wörtlich: die Abnahme verlangte 62 SWI-
und 150 T2*-Dateien, beide Verzeichnisse waren leer, die Quelldaten lagen
woanders. *Dem Auftrag fehlte die erste Stufe.* Prüfzeit: Sekunden. Kosten des
Nichtprüfens: rund 2 h 50 min über zwei Anläufe, ohne eine einzige Datei.

Erst das Ausgabeformat von `abnahme` feststellen, dann darauf filtern — nicht
raten.

---

## Teil C — erledigt oder geschlossen, nicht nochmal anfassen

### Bereits vermessen und verworfen

**MTP auf Alita.** `BLACKBOARD [19]`, 28.08.2026. Bei 81920 Kontext verlangt der
rs-Cache 3591 MiB zusätzlich, bei 65536 fehlen 774,71 MiB, bei 49152 läuft es
mit 703 MiB frei. Zwei unabhängige Gründe dagegen: Hermes verlangt ≥ 64000
Kontext, und Claras U-Net braucht 1,844 GiB Spitze.

Die Rettungsidee „KV-Quantisierung als VRAM-Kredit" wurde durchgerechnet:

| Konfiguration | KV-Cache | frei danach | MTP-Aufschlag | Rest |
|---|---|---|---|---|
| 81920 · f16/f16 (heute) | 5120 MiB | 2892 MiB | — | — |
| 81920 · q8_0/q8_0 | 2720 MiB | ~5290 MiB | ~4690 MiB | ~600 MiB |
| 81920 · q8_0/q4_0 | 2080 MiB | ~5930 MiB | ~4690 MiB | ~1240 MiB |
| 65536 · q8_0/q4_0 | 1664 MiB | ~6350 MiB | ~4690 MiB | ~1660 MiB |

Alle drei Zeilen liegen unter der U-Net-Spitze von 1,844 GiB. **Die Rechnung
geht nicht auf.**

*Eine Einschränkung dazu in Teil D.*

### Geprüft und geschlossen

- **ktransformers.** PyPI liefert für `kt-kernel` nur `cp312 + manylinux` —
  kein Windows-Rad. Das AMX-Backend läuft weder auf Zen 4 (7840HS) noch auf
  Alder Lake (12900K); es bliebe der LLAMAFILE-CPU-Pfad, und dessen
  GGUF-Unterstützung nennt IQ4_XS nicht. **[belegt]**
- **vLLM auf Alita.** Die A5000 ist Compute 8.6. Die kleinen Zahlen im
  vLLM-Rezept setzen Blackwell voraus. Der auf Ampere gangbare 4-Bit-Weg wiegt
  27,8 GB und passt nicht in 24,5 GiB, weil die Gated-DeltaNet-Schichten in
  BF16 bleiben müssen. **[belegt]**
- **Eigene imatrix.** Die vorhandenen unsloth-UD-Quants sind bereits
  imatrix-basiert. Man tauscht keine fehlende Kalibrierung gegen eine, sondern
  eine fremde gegen eine eigene — und die einschlägige Quelle heißt
  „Importance matrix calculations work best on near-random data", widerspricht
  der Idee also. Preis wäre ein 54-GB-Download. **[belegt]**
- **Ein VLM als Befunder auf NIfTI-Schnitten.** Ein Audit über 4102
  Hirn-MRT-Bilder findet für sechs Modelle 0,514 bis 0,670 Genauigkeit auf
  *trivialen* Fragen, bei 0,819 bis 0,968 Selbstsicherheit in den **falschen**
  Antworten. 33 bis 46 % aller Punkte waren gleichzeitig falsch und hochsicher.
  Als Leser der eigenen QC-Bilder dagegen sinnvoll — abgeleitete Bilder ja,
  Rohschnitte als Entscheidungsgrundlage nein. **[belegt]**
- **Ein anderes Modell auf Alita.** Qwen3.8-27B ist bereits das Beste, was Ende
  August 2026 in 24 GB passt. Der Hebel ist, vorhandene Fähigkeiten
  einzuschalten, nicht das Modell zu wechseln. **[belegt]**
- **Feintuning gegen den Zuschnitt.** „Guter Ausführer, schlechter
  Zuschneider" ist eine Eigenschaft des Auftrags, nicht der Gewichte — der
  Zuschnitt fällt vor dem ersten Token, ein LoRA sitzt dahinter. Dazu ein
  handfester Blocker: llama.cpp-Issue 21125 ist offen,
  `convert_lora_to_gguf.py` scheitert für diese Architekturlinie an
  `_reorder_v_heads`. Wer erst trainiert und dann konvertiert, kann das
  Ergebnis nicht ausliefern. **[belegt]**

### Im Code repariert, 29.08.2026

- `detect.py` liest die Kopfdimension aus `attention.key_length`, statt sie zu
  raten, und meldet Hybrid-Architekturen als Obergrenze statt als Messung
- `lok.py` vermerkt fehlgeschlagene Batch-Einträge nicht mehr als erledigt —
  ein Serverausfall mitten im Lauf verbrannte sie vorher dauerhaft
- Vier tote `Projects\lok`-Pfade in `tools/README.md` und `start-llm.ps1`
- MIT-Lizenz ergänzt
- `erfassen.sh` schreibt Build-Nummer, `--spec-type`-Liste und die echte
  Aufrufzeile des Servers mit

---

## Teil D — offen, noch von niemandem beantwortet

**Trägt `grossauftrag` die MTP-Entscheidung neu?** Die 1,844-GiB-Reserve ist
nur nötig, wenn Training *neben* dem Modellserver läuft. `grossauftrag --vram 20`
hält llama-server an, rechnet, stellt ihn wieder her; `--einreihen` hängt den
Lauf an eine Warteschlange. Geht jeder Trainingslauf zwingend darüber, entfällt
der zweite Ablehnungsgrund aus `BLACKBOARD [19]` — und genau eine Kombination
wird wieder diskutabel: **65536 Kontext plus `-ctk q8_0 -ctv q8_0` plus MTP.**
Erst als vierter oder fünfter Schritt, und nur mit der Stop-vor-Start-Regel.

**Was kostet die Kompaktierung?** `docs/02-tuning.md` warnt, dass jede Operation,
die die Historie umschreibt, den Prefix-Cache wegwirft.
`alita/konfiguration/hermes-kompression.yaml` schaltet genau das ein
(`proactive_prune_tokens: 20000`) — und zwar zu Recht, denn ohne den Block starb
das Profil reproduzierbar an „Context length exceeded". Beide Entscheidungen
sind einzeln richtig. Die Wechselwirkung hat niemand bepreist: jedes
Kompaktieren kostet einen vollen Re-Prefill über 80k Kontext.

**Stimmt die Perplexitätszahl?** `doku/MASCHINE.md` nennt Q4 6,9651 gegen Q5
6,9622, also 0,042 % Unterschied. llama.cpps eigene Tabelle hat für dieselbe
Quant-Paarung rund 1,9 Prozentpunkte — ein Faktor von etwa 45. Gemessen wurde
bei 512 Token. Nachzumessen mit KL-Divergenz und „Same top p", nicht mit zwei
Perplexitäten nebeneinander.

**Gilt `temp=0` ist deterministisch?** Im Betrieb nicht. `cache_prompt` ist per
Vorgabe an und macht Ergebnisse nichtdeterministisch, weil Logits über
Batchgrößen nicht bitgleich sind. `alita/codetest/lauf.py` setzt
`cache_prompt: false` — richtig. Der laufende Agent auf `:8000` tut es nicht.
Solange das offen ist, misst jeder Qualitätsvergleich auch das eigene Rauschen.

**Wie groß ist der Reststrom an Laufwache Stufe 2?** Bevor ein Encoder das
27B-Urteil ersetzt, muss gezählt werden, wie oft Stufe 2 überhaupt gerufen
wird. Und der Klassifikator braucht **fünf** Ausgänge, nicht vier:
`unentschieden` ist in `urteil.py` bewusst eingeführt, weil die Vorlage bei
jedem Ausfall fälschlich `ok_weiter` zurückgab.

---

## Offene Codebefunde aus der Prüfung

Nicht dringend, aber belegt. Reihenfolge nach Nutzen je Aufwand:

| Datei | Befund | Aufwand |
|---|---|---|
| `lok.py` | `startswith("ESKALIEREN")` greift bei allen Aufgabentypen und ohne Doppelpunkt | klein |
| `lok.py` | Datei-Ein-/Ausgabe im Batch liegt außerhalb des `try`; nach `KeyboardInterrupt` Exit 0 statt 130 | klein |
| `lok.py` | Wiederaufsetz-Schlüssel kennt den Dateiinhalt nicht — eine geänderte Eingabedatei setzt still falsch auf | mittel |
| `detect.py` | `--reserve 3200` ist die einzige Zahl im Repo ohne Herkunftsangabe; gemessener Overhead liegt bei ~1500–2050 MiB | mittel, braucht Messlauf |
| `detect.py` | dichtes Modell ohne `_exps`: `layer_mib` wird 0 und das Profil ist still sinnlos | klein |
| `docker-compose.yml` | `- "8080:8080"` veröffentlicht einen Server ohne Auth im ganzen Netz; `- "127.0.0.1:8080:8080"` | klein |
| `tools/README.md` | private Notiz über Setup-Zips in einem öffentlichen Repo | klein |

**Das Muster hinter mehreren davon:** wo eine Messung fehlt, schreibt der Code
einen plausiblen Ersatzwert hin, statt zu sagen, dass er es nicht weiß —
`else 128`, `if layer_mib > 0 else 0`, `ram_gb or 0`, `"ngl": 99` neben
`"gpu": "keine"`. Die Ausgabe sieht dann wie eine Messung aus. Eine Regel räumt
das ab: **kein Rückfallwert ohne eine Zeile auf stderr, die ihn als solchen
benennt.**
