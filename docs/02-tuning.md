# 02 — Tuning: was passt auf meine GPU?

Die zentrale Frage bei einem MoE-Modell, das nicht ins VRAM passt: **wo verläuft
die Grenze zwischen GPU und RAM?** Dieses Dokument beschreibt die Methode und
zeigt, was sie auf dem Referenzsystem gebracht hat.

## Warum MoE das überhaupt erlaubt

Ein dichtes Modell muss für jedes Token alle Gewichte lesen. Ein Mixture-of-Experts
liest nur die aktiven. Bei Qwen3.6-35B-A3B sind das 3 von 35 Milliarden Parametern
— und genau deshalb ist es auf einer 8-GB-Karte benutzbar, während ein dichtes
27-B-Modell auf derselben Karte bei ~4 Token/s festhängt.

Die Aufteilung:

- **`-ngl 99`** legt von allen Layern die Nicht-Experten-Teile (Attention,
  Embeddings, Norms) plus den KV-Cache ins VRAM
- **`-ncmoe N`** lässt die **Expert**-Gewichte der ersten N Layer im RAM, gerechnet
  von der CPU

Beides arbeitet gleichzeitig. Pro Token wandern die Aktivierungen zwischen GPU und
CPU hin und her.

## Die Rechnung

`detect.py` macht das automatisch, aber die Logik sollte man kennen:

```
freies VRAM
  − Nicht-Experten-Gewichte
  − KV-Cache (ctx × Layer × 2 × KV-Heads × head_dim × 2 Byte)
  − Reserve für Compute-Puffer
  ────────────────────────────
  ÷ Bytes pro Expert-Layer      =  Layer, die auf die GPU passen
```

### Die Falle: nominelle Bitbreiten

Der naheliegende Weg — `expert_count × 3 × embedding × ffn_length × Bits/8` — geht
bei modernen Quantisierungen daneben. Dynamische Quants (unsloth „UD", i-Quants)
geben verschiedenen Tensoren **verschiedene** Bitbreiten: Experten weniger,
Attention und Embeddings mehr. Auf dem Referenzsystem lag diese Rechnung um Faktor
zwei daneben.

Richtig ist, die **Tensor-Tabelle** im GGUF-Header auszuwerten. Dort steht jeder
Tensor mit Name, Typ und Datei-Offset. Die Differenz zweier aufeinanderfolgender
Offsets ist die exakte Größe — unabhängig vom Quant-Typ, auch für Typen, die es
beim Schreiben dieses Textes noch nicht gab. `detect.py` summiert alle Tensoren,
deren Name auf `_exps` endet, gruppiert nach Layer.

Gegenprobe auf dem Referenzsystem: Summe aller Tensoren 17,72 GB gegen 17,73 GB
Dateigröße.

## Gemessen auf dem Referenzsystem

Modell `Qwen3.6-35B-A3B-UD-IQ4_XS`, 40 Layer, 256 Experten, 8 aktiv, GQA 16:2.

| | |
|---|---|
| Experten gesamt | 14,12 GiB |
| Nicht-Experten | 2,38 GiB |
| pro Expert-Layer | 361,6 MiB |
| KV-Cache bei 16k Kontext | 640 MiB |

Der KV-Cache ist dank GQA 8:1 winzig — 40 KB pro Token. Kontext ist bei diesem
Modell also billig; das Verdoppeln auf 32k kostet nur 640 MiB.

### Der Effekt

| | `-ncmoe 99` (alles CPU) | `-ncmoe 34` (6 Layer GPU) |
|---|---|---|
| VRAM belegt | 5132 MiB | 6733 MiB |
| Decode | 15,9 t/s | **19,4 t/s** |
| Prefill (warm) | 160 t/s | **306 t/s** |

Sechs von vierzig Layern auf der GPU bringen 22 % beim Decoding und knapp das
Doppelte beim Prefill. Der Grund für den überproportionalen Prefill-Gewinn: der ist
compute-bound, und die GPU rechnet Matrixmultiplikationen um Größenordnungen
schneller als acht CPU-Kerne.

## Vorgehen von Hand

Falls `detect.py` nicht passt, geht es auch empirisch:

1. Mit `-ncmoe 99` starten — läuft garantiert, alles auf der CPU
2. `nvidia-smi` ansehen, wie viel VRAM frei bleibt
3. Zahl schrittweise senken: 99 → 40 → 34 → 30
4. Sobald der Start an „out of memory" scheitert: eine Stufe zurück

**Wichtig:** vor dem Messen alle anderen GPU-Verbraucher schließen. Ein Browser
belegt schnell 2 GB VRAM, und dann misst man dessen Schwankungen statt des Modells.

## Die anderen Stellschrauben

### `-np 1` — ein Slot

`llama-server` legt standardmäßig mehrere Slots an. Jeder hat einen **eigenen**
Prefix-Cache. Für einen sequenziellen Client bedeutet das: jeder Aufruf landet in
einem anderen Slot und der System-Prompt wird jedes Mal neu prefillt.

Mit `-np 1` bleibt alles in einem Cache. Für interaktive Nutzung ist das die
wichtigste einzelne Einstellung. Für **Batch**-Durchsatz ist das Gegenteil richtig:
mehrere parallele Anfragen lasten die Expert-Matmuls besser aus. Zwei Profile
anlegen, eines je Zweck.

### `-lm` — Lademodus und SSD-Verschleiß

SSD-Verschleiß entsteht durch **Schreiben**, nicht durch Lesen. Ein Modell zu laden
ist reines Lesen und kostet keine Lebensdauer.

| Modus | Verhalten |
|---|---|
| `mmap` (Default) | Modellseiten sind dateigebunden und sauber. Unter Speicherdruck werden sie verworfen und neu **gelesen**. Kein Verschleiß, aber langsamer Prefill bei RAM-Mangel. |
| `mmap+mlock` | wie mmap, zusätzlich resident gepinnt. Keine Verdrängung, keine Re-Reads. Das Optimum — **wenn** genug RAM frei ist. |
| `none` | anonymer Speicher. Bei RAM-Mangel landet das Modell im **Pagefile** — echte Schreibvorgänge. Nur bei viel freiem RAM. |

Auf dem Referenzsystem war der erste gemessene Prefill 6 t/s statt 306. Ursache
war nicht die CPU, sondern Paging: die mmap-Seiten wurden unter Speicherdruck
laufend verdrängt und neu von SSD gelesen. Der Fix ist nicht `-lm none`, sondern
**RAM freimachen**.

### Kontext

`-c` kostet KV-Cache im VRAM, und der geht direkt von den Expert-Layern ab. Bei
GQA-Modellen ist er klein genug, dass man großzügig sein kann. Bei Modellen ohne
GQA (KV-Heads = Attention-Heads) ist er 8-fach größer und die Rechnung fällt anders
aus — `detect.py` zeigt den Wert an.

## Was man **nicht** tunen sollte

**Prompt-Kompaktierung in Agent-Schleifen.** Bei append-only Verlauf und einem Slot
trägt der Prefix-Cache den gesamten Kontext; pro Schritt werden nur die neuen Tokens
prefillt. Jede Operation, die die Historie *umschreibt* — Compaction, Timestamps im
System-Prompt, nachträgliches Trimmen — wirft den Cache weg und erzwingt vollen
Re-Prefill. Bei 8k Kontext sind das rund 50 Sekunden pro Schritt statt 5.
