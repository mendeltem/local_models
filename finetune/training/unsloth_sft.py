#!/usr/bin/env python3
"""unsloth_sft - LoRA-Finetuning auf daten/train/*.jsonl, danach GGUF fuer Ollama.

    python3 unsloth_sft.py --config config.json --trocken    Daten pruefen, nichts laden (laeuft ueberall)
    python3 unsloth_sft.py --config config.json              trainieren (GPU, Unsloth installiert)

GERUEST: noch nie gelaufen. Abgleichen mit dem aktuellen Unsloth-Notebook der
gewaehlten Modellfamilie, bevor Rechenzeit verbraucht wird (TRL benennt
Parameter zwischen Versionen um, z. B. tokenizer -> processing_class).

Ablauf nach dem Training: gguf/Modelfile -> `ollama create <name> -f Modelfile`
(oder vLLM auf dem HPC mit dem LoRA-Adapter), dann ../ausfragen.py gegen
Basis- und neues Modell und `ausfragen.py --vergleich`.
"""

import argparse
import glob
import json
import random
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent


def lade_daten(cfg):
    beispiele = []
    for muster in cfg["daten"]["dateien"]:
        for p in sorted(glob.glob(str((HIER / muster).resolve()))):
            for z in Path(p).read_text(encoding="utf-8").splitlines():
                if z.strip():
                    beispiele.append(json.loads(z))
    if cfg["daten"].get("nur_geprueft"):
        beispiele = [b for b in beispiele if b.get("geprueft")]
    if cfg["daten"].get("bereiche"):
        beispiele = [b for b in beispiele if any(f"/{x}/" in b["fakt"] or b["fakt"].startswith(x) for x in cfg["daten"]["bereiche"])]
    for b in beispiele:
        rollen = [m["role"] for m in b["messages"]]
        if rollen[-1] != "assistant" or "user" not in rollen:
            raise ValueError(f"Beispiel ohne user/assistant: {b.get('fakt')}")
    random.Random(cfg["training"]["seed"]).shuffle(beispiele)
    return beispiele


def trainieren(cfg, beispiele):
    from unsloth import FastLanguageModel           # erst hier: --trocken laeuft ohne GPU
    from unsloth.chat_templates import train_on_responses_only
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=cfg["modell"], max_seq_length=cfg["max_seq_length"], load_in_4bit=cfg["load_in_4bit"])
    lo = cfg["lora"]
    model = FastLanguageModel.get_peft_model(
        model, r=lo["r"], lora_alpha=lo["alpha"], lora_dropout=lo["dropout"], target_modules=lo["ziele"],
        use_gradient_checkpointing="unsloth", random_state=cfg["training"]["seed"])
    texte = [tokenizer.apply_chat_template(b["messages"], tokenize=False) for b in beispiele]
    ds = Dataset.from_dict({"text": texte})
    t = cfg["training"]
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=ds,
        args=SFTConfig(dataset_text_field="text", per_device_train_batch_size=t["batch"],
                       gradient_accumulation_steps=t["grad_akkumulation"], learning_rate=t["lernrate"],
                       num_train_epochs=t["epochen"], max_steps=t["max_schritte"], warmup_ratio=t["warmup_anteil"],
                       logging_steps=5, seed=t["seed"], output_dir=str(HIER / cfg["ausgabe"]), report_to="none"))
    # Verlust nur auf den Antworten, nicht auf Frage und System-Prompt.
    # Die Marker haengen am Chat-Template der Modellfamilie - im Notebook nachsehen.
    trainer = train_on_responses_only(trainer, instruction_part="<|im_start|>user\n",
                                      response_part="<|im_start|>assistant\n")
    stats = trainer.train()
    aus = HIER / cfg["ausgabe"]
    model.save_pretrained(str(aus / "lora"))
    tokenizer.save_pretrained(str(aus / "lora"))
    model.save_pretrained_gguf(str(aus / "gguf"), tokenizer, quantization_method=cfg["gguf"]["quantisierung"])
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HIER / "config.json"))
    ap.add_argument("--trocken", action="store_true", help="nur Daten laden und pruefen")
    a = ap.parse_args(argv)
    cfg = json.loads(Path(a.config).read_text())
    b = lade_daten(cfg)
    zeichen = sum(len(m["content"]) for x in b for m in x["messages"])
    print(f"{len(b)} Beispiele, ~{zeichen // 4:,} Token (grob Zeichen/4), {sum(x['geprueft'] for x in b)} aus Vorlagen oder gegengelesen, Rest LLM-Entwurf")
    if a.trocken:
        return 0
    print(trainieren(cfg, b))
    return 0


if __name__ == "__main__":
    sys.exit(main())
