# Tägliche Recherche: lokaler Arbeitsplatz mit lokalen Modellen

Dieser Text ist der Auftrag für den täglichen Lauf (`tag.sh`). Ändern erlaubt,
der nächste Lauf liest ihn neu.

## Rahmen
- Zwei Budgets: **8 GB VRAM** (Victus, RTX-Laptop, 32 GB RAM, Ubuntu) und **24 GB VRAM** (3090/4090-Klasse).
- Im Einsatz: qwen3.6-35B-A3B (64k) über Ollama, OpenCode und Hermes als Agenten,
  Laya 0.3.28 als Router vor dem Agenten (CPU), Unsloth für späteres Feintuning.
- Gesucht ist, was sich seit dem letzten Stand **geändert** hat. Bekanntes nicht wiederholen.

## Fragen
1. **Modelle:** Neue offene Modelle oder Quants, die für 8 GB oder 24 GB das Bisherige
   schlagen könnten (Allround, Coding/Agent, Reasoning, Deutsch). Je Modell: Name,
   Parameter gesamt/aktiv, Quant und passender Kontext, Lizenz, Datum, Quelle.
2. **Methoden:** Neues in llama.cpp, ik_llama.cpp, Ollama, vLLM, ExLlamaV3, LM Studio;
   Speculative Decoding/MTP, MoE-Offload, KV-Cache, Prefix-Cache, Quant-Formate,
   Agent-Harnesses (OpenCode, Hermes, Aider). Je Punkt: Flag oder Befehl, Messung, Quelle.
3. **Entscheidungsmodelle:** Router, Wächter für Shell-Befehle, Antwort-Prüfer,
   Unsicherheitsschätzer, Neues bei Jev/Laya. Größe, CPU/GPU, Lizenz, Quelle.
4. **Experimente:** Was davon lohnt sich auf dem Victus zu messen? Höchstens drei,
   konkret mit Befehl.

## Belegregeln
- Jede Zahl bekommt **[U]** (unabhängig gemessen: Artificial Analysis, localbench,
  Kaitchup, GitHub-PR mit Messung, Paper mit Fremdreplikation) oder **[V]** (Hersteller,
  Blogs, Aggregatoren).
- SEO- und Ranking-Seiten (bestllmfor, insiderllm, localaimaster, modelfit u. ä.) nur
  zum Finden, nie als Beleg. Widersprechen sie Modellkarten, gilt die Modellkarte.
- Datum jeder Meldung angeben. Ohne Datum: "Datum unklar".
- Nichts erfinden. Unsicheres als unsicher markieren.

## Ausgabe
- `stand/<JJJJ-MM-TT>.md`: vollständiger Stand (fortgeschrieben aus dem letzten Stand,
  Überholtes gestrichen oder als überholt markiert), gleiche Gliederung wie die Fragen.
- `NEU.md`: nur die Änderungen gegenüber dem letzten Stand, höchstens 15 Zeilen,
  wichtigste zuerst. Gab es nichts Neues, genau die Zeile `Nichts Neues.`
