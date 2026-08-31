# Codetest — vier Aufgaben aus echten Fehlern

    python lauf.py http://127.0.0.1:8000 "Modellname"

Stellt jede Aufgabe, fuehrt die Antwort aus, prueft sie gegen einen Sollwert.
**Kein Modell urteilt.** Entweder der Code rechnet das Richtige oder nicht.

## Die Aufgaben

| | stammt von |
|---|---|
| `dice_label` | Label 2 zaehlt nicht als Laesion — Clara fand den Unterschied am 28.08. selbst |
| `zurueck_dann_schwellen` | erst hochskalieren, DANN schwellen — der Geometriefehler vom 25.08. |
| `detektion` | Trefferzaehlung statt Dice — was der microbleed-Auftrag verlangt |
| `stapel` | zehn verschiedene Bildgroessen der WMH-Challenge auf eine Kante |

Sie sind nicht ausgedacht, sondern aus Fehlern gewaehlt, die auf dieser
Maschine Geld gekostet haben. Deshalb misst der Test etwas: ein Modell, das
sie loest, kann hier arbeiten.

## Ergebnisse

    2026-08-28   Qwen3.8-27B UD-Q4_K_M    4 von 4   2602 Token

## Eine Warnung an den, der Aufgaben ergaenzt

Beim ersten Lauf meldete der Test `dice_label` als falsch: erwartet 0.8,
bekommen 0.666667. Der Sollwert war von Hand gerechnet — **und falsch**.
0.666667 ist richtig, das Modell hatte recht.

Ein Pruefwerkzeug, dessen eigener Fehler wie ein Befund am Geprueften
aussieht, ist die gefaehrlichste Sorte. Jeder neue Sollwert gehoert
nachgerechnet, bevor er eingetragen wird -- am besten mit einem kleinen
Skript, nicht im Kopf.

---

## Dasselbe gegen ein fernes Modell

    export OPENROUTER_API_KEY=...
    python lauf-fern.py                       # Router waehlt ein freies Modell
    python lauf-fern.py z-ai/glm-5.2:free     # feste Kennung
    python lauf-fern.py --art denken          # andere Neigung

`lauf-fern.py` stellt **dieselben Aufgaben mit denselben Parametern** und
benutzt **dieselbe Pruefung** wie `lauf.py`. Der einzige Unterschied ist das
Protokoll: llama.cpp spricht `/completion`, OpenRouter spricht
`/chat/completions`. Waeren die Parameter verschieden, wuerde man die
Einstellung messen statt das Modell.

`router.py` waehlt aus dem **zur Laufzeit gelesenen** Katalog. Eine feste
Liste waere nach zwei Wochen falsch, und zwar stumm -- freie Modelle
verschwinden und wechseln ihre Kennung.

    python router.py code 8000      # zeigt die Kette, laedt nichts

Geliefert wird nie ein einzelnes Modell, sondern eine **Ausweichkette**: freie
Modelle sind ratenbegrenzt, und bei 429 geht es mit dem naechsten weiter statt
den Lauf abzubrechen. Welches Modell tatsaechlich geantwortet hat, steht in
jeder Ergebniszeile -- sonst vergleicht man am Ende gegen etwas anderes, als
man glaubt.

## Was dabei das Haus verlaesst

Die vier Aufgabentexte aus `aufgaben.py`. Keine Daten, keine Pfade, kein
Fallbezug -- in derselben Datei nachlesbar.

Bei kostenlosen Modellen duerfen die Anbieter Eingaben in aller Regel zum
Training verwenden; wer nichts zahlt, zahlt mit dem, was er schickt. Fuer vier
Programmieraufgaben ist das in Ordnung. **Fuer alles mit Patientenbezug ist
dieses Skript der falsche Weg** -- dafuer gibt es Alita ohne Netz.

## Warum Clara trotzdem lokal bleibt

Nicht aus Vorsicht allein, sondern weil es rechnerisch nicht geht: Alita hat
gemessene 36 Byte/s. Claras microbleed-Auftrag verbrauchte in einer Runde
966 500 Token. Ueber diese Leitung waere das keine langsame Runde, sondern
gar keine.
