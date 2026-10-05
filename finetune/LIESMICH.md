# finetune: eigenes Wissen in ein lokales Modell

Ziel: Ein Modell soll Mendels Wissensstand von sich aus vertreten, ohne dass er
jedes Mal per Prefill in den Prompt muss. Beispiel: Ein Standardmodell nennt
SK Hynix einen zyklischen Konsum-Speicherwert. Nach Mendels Wiki darf der
Standardzyklus aber erst nach der Absorptionsprüfung (HBM je Package gegen
GB je Wafer) als Argument stehen.

Hier liegt die **Infrastruktur**, kein trainiertes Modell. Trainiert wird
später auf einem HPC oder einer Workstation.

## Ablauf

```
Quellen ──> Fakten ──> Trainingsbeispiele ──> LoRA (später) ──> GGUF/Ollama
              │                                                    │
              └──> Sonden ──> ausfragen.py (Basis) ───────────────> ausfragen.py (neu) ──> --vergleich
```

```bash
# 1. Quellen lesen: Wiki-Einträge mit Typ und Status, Use-Case-Karten, Begriffe
python3 erzeugen.py fakten --wiki ~/Projects/blackbeard_wikki --usecases <ai_use_cases_overview>/index.html

# 2. Trainingsbeispiele
python3 erzeugen.py vorlagen                                    # feste Vorlagen, offline
python3 erzeugen.py umschreiben --modell qwen3.6-64k --bereich memory_supply   # Umschreibungen per LLM (Entwurf)
python3 erzeugen.py sonden --modell qwen3.6-64k --bereich memory_supply        # MC-Sonden per LLM (Entwurf)

# 3. Basismodell ausfragen, heute
python3 ausfragen.py --modell qwen3.6-64k --runden 2 --mischen

# 4. Später, nach dem Training: dasselbe gegen das neue Modell und vergleichen
python3 ausfragen.py --url http://<hpc>:8000/v1 --modell mein-lora --runden 2 --mischen
python3 ausfragen.py --vergleich laeufe/<basis>.jsonl laeufe/<neu>.jsonl

# 5. Training (Gerüst, noch nie gelaufen)
python3 training/unsloth_sft.py --trocken        # Daten prüfen, läuft überall
sbatch training/slurm.sbatch                     # HPC; Platzhalter in der Datei ausfüllen
```

## Was gemessen wird (Sonden, `sonden/`)

| Art | Frage | Warum |
|---|---|---|
| wirkung | Sitzt das Gelernte? | der eigentliche Zweck |
| umschreibung | Dieselbe Aussage anders gefragt, nie im Training | auswendig gelernt oder verstanden? |
| nachbarschaft | Verwandtes Wissen, das sich NICHT ändern soll (Schweinezyklus allgemein) | kein Überschreiben über das Ziel hinaus |
| erhalt | Allgemeinwissen | Finetuning darf das Modell nicht dümmer machen |
| unsicherheit | Offene Punkte | das Modell soll "offen" sagen, nicht raten |
| begriff | Eigene Terminologie (Trägt nicht, Axiom, Bruchindikator) | |

`sonden/hand/` ist von Hand geschrieben und gegengelesen. `sonden/erzeugt/`
sind LLM-Entwürfe mit `geprueft: false`; `ausfragen.py --nur-geprueft`
lässt sie weg.

## Grundsätze

- **Status bestimmt die Antwort.** `vorschlag` wird als unbestätigt gelernt,
  `offen` als offen, ein Axiom als Setzung von Mendel. Sonst lernt das Modell
  Vermutungen als Fakten.
- **"Trägt nicht" ist Trainingsmaterial.** Dort stehen die Fehlschlüsse, die
  weg sollen, und das Gegen-Extrem (Zyklus *ausgeschlossen*) ebenso.
- **Sonde nie im Training.** `erzeugen.py` prüft nach jedem Schritt, dass keine
  Sonden-Frage wörtlich in `daten/train/` steht, und endet sonst mit Exit 1.
- **Viele Formulierungen.** Ein Faktum, einmal trainiert, ist danach meist
  nicht abrufbar; Umschreibungen helfen (Allen-Zhu & Li 2023).
- **Vorsicht bei neuem Wissen.** Finetuning auf Fakten, die das Modell nicht
  kennt, kann Halluzinationen fördern (Gekhman et al. 2024). Deshalb
  `nachbarschaft` und `erhalt` immer mitmessen.

## Ablage

| Pfad | Inhalt | erzeugt von |
|---|---|---|
| `quellen/` | Leser für Wiki und Use-Case-Seite | Hand |
| `daten/fakten.jsonl`, `daten/begriffe.jsonl` | ein Faktum je Zeile | `erzeugen.py fakten` |
| `daten/train/*.jsonl` | Chatformat für TRL/Unsloth | `erzeugen.py vorlagen/umschreiben` |
| `sonden/hand/`, `sonden/erzeugt/` | Prüffragen | Hand / LLM |
| `laeufe/` | Ergebnisse je Ausfragen | `ausfragen.py` |
| `training/` | Unsloth-Skript, Konfiguration, Slurm-Vorlage | Hand |

Daten, Sonden und Läufe sind versioniert, damit sie ohne Wiki-Zugang auf den
HPC mitgehen.

## Quellen

- Meng et al. 2022, ROME (Wirksamkeit, Verallgemeinerung, Spezifität als Messgrößen), DOI 10.48550/arXiv.2202.05262
- Allen-Zhu & Li 2023, Physics of Language Models 3.1 (Wissen braucht Umschreibungen), DOI 10.48550/arXiv.2309.14316
- Gekhman et al. 2024, Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations?, DOI 10.48550/arXiv.2405.05904
