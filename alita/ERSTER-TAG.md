# Erster Tag zurück an Alita

Abzuarbeiten in dieser Reihenfolge. Die ersten drei Schritte beantworten Fragen,
von denen alles Weitere abhängt — sie kosten zusammen unter zwanzig Minuten.

Jeder Schritt nennt: den Befehl, was herauskommen soll, und was zu tun ist, wenn
etwas anderes herauskommt. Wo eine Antwort festzuhalten ist, steht wohin.

> Alles hier ist auf Victus geschrieben und dort nur auf **Lesbarkeit** geprüft.
> Die Pfade sind Alita-Pfade; kein Urteil in diesem Blatt ist auf einer anderen
> Maschine nachvollzogen worden.

---

## 0 — Stand holen

```bash
cd ~/local_models && git pull
```

Es arbeiten mehrere Sitzungen an diesem Repo. Ohne `git pull` fehlen `vorflug`,
`abgleich` und die historischen Aufträge.

---

## 1 — Das Maschinenblatt erneuern

```bash
./maschinen/erfassen.sh --zeigen
```

`--zeigen` schreibt nichts, gibt nur aus. Sieht es brauchbar aus, ohne den
Schalter noch einmal laufen lassen — dann landet es in `maschinen/<rechner>.md`.

**Beantwortet zwei offene Fragen auf einmal:**

| Zeile im Blatt | wofür |
|---|---|
| `llama-server` … build … | die Build-Nummer stand bisher nirgends |
| `Spekulation / speculative` | steht dort `ngram-mod`? Davon hängt Schritt 7 ab |
| `kennt / knows` | fehlt `--cache-ram` oder `--cache-reuse`, ist die Doku älter als das Binary |
| Aufrufzeile aus `/proc` | mit welchen Flags der Server **wirklich** läuft, nicht was `start.sh` vorhat |

**Wenn `--spec-type` die Liste nicht ausgibt:** Build ist älter als b10603. Dann
Schritt 7 streichen und im Blatt vermerken, statt zu raten.

---

## 2 — Was liegt in `modelle/embedding/` und `modelle/encoder/`?

```bash
ls -la ~/local_agentic_system/modelle/embedding/ ~/local_agentic_system/modelle/encoder/
```

Der bestverzinste Vorschlag der ganzen Recherche lautet, einen **Reranker** zu
benutzen, der angeblich schon dort liegt. **Das steht nirgends im Repo** —
`maschinen/Alita-MS-7D91.md` listet nur Ordnernamen und Größen (`embedding 1.8G`,
`encoder 1.1G`). Dieser eine Befehl entscheidet, ob der Vorschlag eine Grundlage
hat.

**Liegt dort ein Reranker** (Dateiname enthält typisch `rerank`): der Weg dahinter
ist kurz — llama.cpp kann Reranking nativ, geprüft an `llama-server --help`:
`--rerank`/`--reranking` zusammen mit `--pooling rank`. Zweiter Server auf
eigenem Port, kein VRAM (CPU).

**Liegt keiner dort:** in `docs/06-vorhaben.md` bei B1 von *[ungeprüft]* auf
*widerlegt* ändern und den Punkt streichen. Das spart einen Tag.

Ergebnis in beiden Fällen nach `maschinen/Alita-MS-7D91.md` eintragen — der
Ordnerinhalt gehört ins Maschinenblatt, nicht in den Kopf.

---

## 3 — `abnahme-referenz` gegen das echte `abnahme`

**Das ist der Schritt, ohne den `vorflug` auf dieser Maschine nichts entscheiden
darf.** `vorflug` wurde ohne das echte `abnahme` gebaut; daneben liegt eine
Nachbildung der drei Verben aus `docs/05-scaffolding.md`. Ob beide dasselbe
sagen, ist ungeprüft.

Erst eine Liste besorgen, die alle drei Verben benutzt — entweder eine echte aus
einem laufenden Auftrag, oder diese hier:

```bash
cat > /tmp/probe.abnahme <<'EOF'
datei /home/uchralt/local_agentic_system/modelle/HERKUNFTS-PRUEFSUMMEN.txt
datei /home/uchralt/gibt-es-nicht.md
enthaelt /home/uchralt/local_agentic_system/modelle/HERKUNFTS-PRUEFSUMMEN.txt sha256
genau /home/uchralt/local_agentic_system/modelle/*.gguf 3
EOF
```

Die Zahl `3` in der letzten Zeile ist geraten — sie soll ruhig falsch sein.
Wichtig ist nicht, ob ein Kriterium zutrifft, sondern ob **beide Fassungen
dasselbe** darüber sagen.

```bash
python alita/werkzeuge/abgleich /tmp/probe.abnahme
```

Der Pfad zum echten `abnahme` ist voreingestellt auf
`/home/uchralt/local_agentic_system/system/werkzeuge/abnahme` — das ist der Pfad,
den `laufwache` benutzt. Stimmt er nicht, mit `--b <pfad>` überschreiben.

| Ausgang | was tun |
|---|---|
| **EINIG** (Exit 0) | `vorflug` darf ab jetzt mit `--pruefer <abnahme>` benutzt werden |
| **UNEINIG** (Exit 1) | Es gilt `abnahme`. `abnahme-referenz` nachziehen, erneut abgleichen. Bis dahin kein `vorflug`-Urteil für bare Münze nehmen |
| **Exit 64, „Seite B lässt sich nicht ausführen"** | falscher Pfad, mit `--b` korrigieren |
| **„B hat N Zeilen nicht verstanden"** | die Kriteriensyntax ist **reicher** als `docs/05` zeigt — dann `abnahme --hilfe` lesen und die zusätzlichen Verben in `docs/05-scaffolding.md` und in `abnahme-referenz` nachtragen |

Der letzte Fall ist der wahrscheinlichste und der wertvollste: `docs/05` behauptet,
`abnahme` prüfe auch **Exit-Codes**, aber dafür ist nirgends ein Verb dokumentiert.

---

## 4 — `vorflug` gegen den historischen Fall

Erst sinnvoll, wenn Schritt 3 „EINIG" ergab.

```bash
python alita/werkzeuge/vorflug alita/auftrag/historisch/microbleed-27-08.auftrag \
  --pruefer /home/uchralt/local_agentic_system/system/werkzeuge/abnahme
```

**Erwartet: Exit 1, abgelehnt**, mit der Begründung, dass die Quelle nicht
auflösbar ist.

**Achtung, das kann heute anders ausgehen:** die Verzeichnisse unter
`data/work/microbleed/` sind seit dem 28.08. gefüllt (`BLACKBOARD [20]`: „62 SWI-
und 150 T2*-Fälle da"). Dann urteilt `vorflug` korrekt *startklar* — der
historische Zustand ist weg, nicht das Werkzeug kaputt. Der maschinenunabhängige
Ersatz dafür läuft ohnehin überall:

```bash
python alita/werkzeuge/pruefe-vorflug.py
```

Elf Fälle, die sich ihre Verzeichnisse selbst bauen. Muss „bestanden" sagen.

Dann der zweite historische Fall:

```bash
python alita/werkzeuge/vorflug alita/auftrag/historisch/microbleed-28-08.auftrag \
  --pruefer /home/uchralt/local_agentic_system/system/werkzeuge/abnahme
```

**Erwartet: Exit 0, startklar — und dieser Lauf ist trotzdem gescheitert**
(173 Aufrufe, 966 500 Token, null Dateien). Das ist kein Fehler, das ist der
Beleg: `vorflug` prüft Erfüllbarkeit, nicht Größe.

---

## 5 — Trägt der Prefix-Cache?

Diese eine Zahl ordnet alle Tempoarbeiten. Trägt der Cache, ist Kontext ein
VRAM- und Qualitätsproblem; trägt er nicht, kostet jede Agentenrunde einen vollen
80k-Prefill und alles andere ist zweitrangig.

```bash
curl -s http://127.0.0.1:8000/slots | head -60
```

`--slots` ist per Vorgabe **an** und braucht kein `--metrics` (das ist ein
separater Prometheus-Endpunkt, per Vorgabe aus) — geprüft an
`llama-server --help`.

Die Feldnamen habe ich **nicht** eingetragen, weil sie ohne laufenden Server
nicht prüfbar waren. Gesucht sind die zwei Zahlen „wie viele Prompt-Token
insgesamt" und „wie viele davon neu gerechnet". Ihr Verhältnis ist die
Trefferquote. **Die tatsächlichen Namen bitte in `docs/06-vorhaben.md` bei B2
eintragen**, statt sie aus einer Anleitung zu übernehmen.

Ersatzweise aus dem Log:

```bash
journalctl --user -u llama-server --since "24 hours ago" | grep "prompt eval time" | tail -40
```

| Anteil neu gerechnet | Bedeutung |
|---|---|
| unter 0,1 | Cache trägt. Nach `docs/02-tuning.md` notieren, damit die Frage nicht wiederkommt |
| über 0,5 | jede Runde wird voll neu gerechnet. **Ursache suchen, bevor ein Flag gesetzt wird** — meist ein wechselnder Kopf vorn im Prompt (Zeitstempel, Rundennummer). Zwei aufeinanderfolgende Anfragen an ihren ersten 200 Zeichen vergleichen |

---

## 6 — Die Speichergrenze

```bash
systemctl --user show llama-server -p MemoryHigh -p MemoryMax -p MemoryCurrent
```

`llama-server.service` setzt `MemoryMax=26G` mit dem Kommentar „Gemessen 17,7 GiB
RSS". Der Host-RAM-Prompt-Cache ist per Vorgabe an und darf bis 8192 MiB wachsen:
17,7 + 8 = 25,7 GiB, also 0,3 GiB unter der Grenze. Bei 62,6 GiB Gesamt-RAM ist
die Grenze künstlich und stammt aus einer Zeit vor dem Cache.

- Steht dort `infinity`: Punkt entfällt.
- Steht dort `26G` und `MemoryCurrent` nahe 22G: **latenter Selbstabschuss.**
  Zusammen mit `--cache-ram` anheben — nie das eine ohne das andere.

---

## 7 — `ngram-mod`

Nur wenn Schritt 1 ergeben hat, dass der Build es kennt.

Spekulatives Dekodieren **ohne Entwurfsmodell**: kein zweites Modell, kein
zweiter KV-Cache, kein rs-Cache, laut Doku rund 16 MB. Der einzige Tempohebel,
der an der VRAM-Wand nicht scheitert — MTP ist an genau dieser Wand gescheitert
(`BLACKBOARD [19]`, 3591 MiB rs-Cache bei 80k).

```bash
systemctl --user stop llama-server && sleep 20
LLAMA_ARG_SPEC_TYPE=ngram-mod ~/local_agentic_system/system/start.sh
```

Die 20 Sekunden sind nicht Vorsicht, sondern die Lektion vom 28.08.: systemd
startete alle 14 s neu, während das VRAM des abgestürzten Vorgängers noch nicht
frei war — dadurch sah ein Konfigurationsfehler nach Platzmangel aus.

**Vergleichsgröße:** 33,55 tok/s bei 81920 Kontext.

**Messfalle, die den Versuch wertlos macht:** der n-Gramm-Hashpool überlebt die
Anfrage. Derselbe Prompt zweimal hintereinander lässt das Verfahren um ein
Vielfaches besser aussehen, als es ist. Also Server zwischen den Läufen neu
starten, oder vier verschiedene echte Aufträge nehmen. Und die selbstgedruckte
Statistikzeile lesen: liegt `#acc/#gen` unter etwa 0,5, zahlt man mehr
Verifikation, als man spart.

**Abbruchkriterium:** unter +10 % auf echter Arbeit → Flag entfernen und eine
Zeile ins Modell-Wiki, damit es niemand nochmal probiert.

Trägt es, dauerhaft ohne sudo:

```bash
systemctl --user edit llama-server
# [Service]
# Environment=LLAMA_ARG_SPEC_TYPE=ngram-mod
```

---

## Was danach ansteht

`docs/06-vorhaben.md` ist die vollständige Arbeitsschlange. Teil C hält fest, was
bereits vermessen und **geschlossen** ist — MTP, ktransformers, vLLM, eigene
imatrix, ein VLM als Befunder, ein Modellwechsel. Diese Liste ist beim nächsten
Einfall zuerst zu lesen; sie ist da, damit kein Weg zweimal einen Abend kostet.

Und `alita/BLACKBOARD.md` bekommt einen Eintrag mit dem, was heute
herausgekommen ist — besonders die Antworten aus den Schritten 1, 2 und 3. Ohne
den weiß morgen niemand mehr, ob der Abgleich stattgefunden hat.
