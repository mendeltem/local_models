# 03 — Modell-Wiki: wofür taugt das Ding, und wie stellt man es ein

Betriebswissen zu **Qwen3.6-35B-A3B** (GGUF `UD-IQ4_XS`) auf dem Referenzsystem.
Alles hier ist gemessen; wo etwas ungeprüft übernommen ist, steht es dabei.

## Was für ein Modell das ist

Aus den GGUF-Metadaten, nicht aus der Modellkarte:

| | |
|---|---|
| Architektur | `qwen35moe`, 40 Layer |
| Experten | 256, davon 8 pro Token aktiv |
| Embedding | 2048, Expert-FFN-Breite 512 |
| Attention | 16 Heads, 2 KV-Heads → GQA 8:1 |
| Kontext nativ | 262 144 Token |
| Aktive Parameter | ~3 B von ~35 B |

Die GQA 8:1 ist der Grund, warum großer Kontext hier billig ist: 40 KB KV-Cache pro
Token, 640 MiB bei 16k.

## Tempo

| | |
|---|---|
| Decode | 19–30 t/s (kurze Antworten schneller) |
| Prefill, warm | ~306 t/s |
| Prefill, kalt (Paging) | ~6 t/s ← das ist ein RAM-Problem, kein Modellproblem |

Ein 16k-Prompt kostet warm rund 54 Sekunden. Kontext ist auf lokaler Hardware
teuer — nicht im VRAM, sondern in Wartezeit.

## Was es kann

Gemessen mit einer Batterie fester Aufgaben, je mit maschineller Prüfung:

| Aufgabe | Ergebnis |
|---|---|
| Übersetzen DE↔EN, Fachbegriffe erhalten | zuverlässig |
| JSON-Extraktion inkl. deutscher Zahlformate (`1.249,90` → `1249.9`) | zuverlässig |
| Fehlende Werte als `null` statt erfunden | zuverlässig |
| Klassifikation gegen vorgegebene Labels | zuverlässig |
| Formattreue (exakt N Stichpunkte, nur das Label, kein Codefence) | zuverlässig |
| Kurze Funktionen (< 30 Zeilen) | zuverlässig |
| Commit-Messages aus Diff | zuverlässig |
| Verweigern, wenn Fakten fehlen | zuverlässig, **wenn** der Prompt stimmt |

## Wo es scheitert

**Zählen.** Eine Regex für deutsche IBANs war in drei Anläufen dreimal falsch — mit
26, dann 29, dann gar keiner Länderkennung. Jedes Mal *plausibel aussehend*. Das ist
der teure Fehlermodus: nicht offensichtlicher Unsinn, sondern etwas, das man
nachprüfen muss.

Mit aktiviertem Thinking war dieselbe Aufgabe korrekt:

```
DE\d{2}(?:\s?\d{4}){4}\s?\d{2}
```

Kosten: 116 s statt 5 s, 3098 statt 64 Token.

**Regel: alles, was Längen, Anzahlen oder Positionen betrifft, braucht Thinking oder
eine Gegenprobe im Code.**

## Die wichtigste Lektion: der System-Prompt

Dasselbe Modell ging bei zwei Aufgabentypen **von 0 % auf 100 %** — nur weil ein
Absatz aus dem System-Prompt entfernt wurde.

Ursprünglich stand dort eine Liste von Abbruchgründen („eskaliere bei Websuche,
aktuellen Fakten, mehr als 30 Zeilen Code, mehreren Dateien …"). Das Modell hat
daraufhin eine Commit-Message für einen Vier-Zeilen-Diff abgelehnt — mit der
Begründung „mehr als 30 Zeilen Code" — und eine Fünf-Zeilen-Funktion mit
„Keine Websuche oder aktuelle Fakten".

Ein Versuch, die Regel zu präzisieren, machte es schlimmer. Erst das **Entfernen**
half.

**Regel: kleine Modelle mit abgeschaltetem Thinking mustern Regellisten ab, statt
sie anzuwenden.** Bedingungen gehören nur zu den Aufgabentypen, die sie brauchen,
nicht in einen gemeinsamen Prompt. Und je kürzer der System-Prompt, desto besser —
auf CPU-seitigem Prefill zahlt man ihn ohnehin bei jedem Aufruf.

## Sampling-Parameter

Die Qwen-Modellkarte empfiehlt:

| Modus | Parameter |
|---|---|
| Instruct / non-thinking, allgemein | `temp=0.7, top_p=0.8, top_k=20, min_p=0, presence_penalty=1.5` |
| Instruct / non-thinking, Reasoning | `temp=1.0, top_p=0.95, top_k=20, min_p=0, presence_penalty=1.5` |
| Thinking, allgemein | `temp=1.0, top_p=0.95, top_k=20, min_p=0, presence_penalty=1.5` |
| Thinking, präzises Coding | `temp=0.6, top_p=0.95, top_k=20, min_p=0, presence_penalty=0.0` |

Die Karte weist darauf hin, dass `presence_penalty` zwischen 0 und 2 gegen endlose
Wiederholungen hilft, hohe Werte aber Sprachmischung verursachen können.

**Gegengetestet** auf fünf mechanischen Aufgaben, je drei Läufe, gegen strenges
Sampling (`temp=0`, keine Penalties):

| | Treffer | Reproduzierbarkeit |
|---|---|---|
| streng (`temp=0`) | 15/15 | dreimal identische Ausgabe |
| Karte (`temp=0.7 …`) | 15/15 | 2–3 verschiedene Varianten je Aufgabe |

**Kein Qualitätsunterschied bei kurzen, formatgebundenen Aufgaben — aber
Determinismus nur bei `temp=0`.** Für Extraktion, Klassifikation, Übersetzung also
streng fahren.

Einschränkung dieser Messung: sie prüft kurze Ausgaben. Die `presence_penalty=1.5`
der Karte zielt auf **endlose Wiederholungen in langen Generierungen** — ein
Fehlermodus, den dieser Test nicht auslöst. Für lange, freie Texte ist die
Empfehlung der Karte weiter plausibel und ungetestet.

## Betriebsregeln nach Aufgabentyp

| Aufgabe | Thinking | Temperatur | Anmerkung |
|---|---|---|---|
| Übersetzen | aus | 0.2 | Fachbegriffe explizit schützen |
| Kürzen, Umformulieren | aus | 0.3–0.4 | |
| Rechtschreibung | aus | 0.1 | |
| JSON-Extraktion | aus | 0.0 | Schema im Prompt, „erfinde nichts" |
| Klassifikation | aus | 0.0 | Labels vorgeben, nur Label zurück |
| Stichpunkte | aus | 0.3 | Anzahl hart vorgeben |
| Commit-Message | aus | 0.2 | |
| Kurzer Code | aus | 0.4 | unter 30 Zeilen |
| Docstrings | aus | 0.2 | |
| **Regex, Längen, Anzahlen** | **an** | 0.1 | sonst plausibel falsch |
| Offene Fragen | an | 0.6 | oder gar nicht lokal |

## Wofür man es **nicht** nehmen sollte

- Über mehrere Dateien hinweg denken
- Fehler debuggen, deren Ursache nicht im gelieferten Text steht
- Architekturentscheidungen, Bewertungen mit offenem Ausgang
- Alles, was als Instanz urteilen soll

Die unangenehme Asymmetrie: die Aufgaben, die es gut kann, sind auch die billigsten
bei einem Cloud-Modell. Was dort wirklich Tokens kostet — ein Repo durchsuchen, zehn
Dateien lesen, eine Fehlerkette verfolgen — ist genau das, woran ein 35-B-MoE
scheitert.

**Wo lokal wirklich gewinnt: Mengenarbeit.** 500 Texte klassifizieren, 80 Dateien
mit Docstrings versehen, einen Ordner übersetzen. Bei ~3,5 s pro Eintrag sind 500
Tickets eine halbe Stunde unbeaufsichtigt, ohne Kosten und ohne Rate Limit. Dafür
gibt es `lok.py batch`.

## Tool-Calling

Funktioniert sauber über die OpenAI-kompatible API. Getestet mit zwei Werkzeugen:

```
finish_reason: tool_calls
run_bash({"cmd": "wc -l \"C:\\Users\\Mendel\\Projects\\lok\\lok.py\""})
```

Valides JSON in den Argumenten, sinnvolle Werkzeugwahl, kein Geschwätz im `content`.
Damit ist ein Agent-Harness grundsätzlich machbar — die Grenze ist nicht die
Fähigkeit, sondern das Tempo: rund 5 s pro Agent-Schritt bei append-only Verlauf.

Die Modellkarte nennt zusätzlich `chat_template_kwargs: {"preserve_thinking": true}`,
um Reasoning aus früheren Nachrichten zu erhalten — laut Karte senkt das den
Token-Verbrauch in Agent-Szenarien und verbessert die KV-Cache-Nutzung.
`llama-server` bietet dafür `--reasoning-preserve`. Ungetestet.
