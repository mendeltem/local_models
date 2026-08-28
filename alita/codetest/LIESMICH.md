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
