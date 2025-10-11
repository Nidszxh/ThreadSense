import os, time, math
from pathlib import Path
from typing import Dict

import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    DataCollatorForSeq2Seq,
    TrainingArguments,
    Trainer,
)
from peft import LoraConfig, get_peft_model

# ==============================
# CONFIG
# ==============================
DATA_PATH  = Path("data/fine_tune/reddit_summarization_dataset.jsonl")
OUT_DIR    = Path("data/fine_tune/models/flan_t5_large_lora")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_MODEL = "google/flan-t5-large"

# Keep these modest to finish < 30 min on a 3070 Ti (8 GB)
MAX_SOURCE_LEN = 768      # reduce to 512 if VRAM is tight
MAX_TARGET_LEN = 256
NUM_EPOCHS     = 1
BATCH_SIZE     = 2         # set to 1 if OOM
GRAD_ACCUM     = 8         # effective batch size = BATCH_SIZE * GRAD_ACCUM

print("🚀 Starting FLAN-T5-Large LoRA fine-tuning...")
print(f"[INFO] CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"[INFO] Device: {torch.cuda.get_device_name(0)}")

# ==============================
# TOKENIZER & MODEL
# ==============================
print("[INFO] Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)

print("[INFO] Loading base model...")
model = AutoModelForSeq2SeqLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto" if torch.cuda.is_available() else None,
)

# Enable gradient checkpointing directly (Trainer args changed in newer versions)
try:
    model.gradient_checkpointing_enable()
    print("[INFO] Gradient checkpointing enabled on model.")
except Exception as _:
    print("[WARN] Gradient checkpointing not enabled (method unavailable).")

# LoRA config (T5: typically target q, v)
print("[INFO] Injecting LoRA adapters...")
lora_cfg = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q", "v"],
    task_type="SEQ_2_SEQ_LM",
)
model = get_peft_model(model, lora_cfg)
model.print_trainable_parameters()

# ==============================
# DATASET
# ==============================
if not DATA_PATH.exists():
    raise FileNotFoundError(f"Dataset file not found: {DATA_PATH}")

print(f"[INFO] Loading dataset from {DATA_PATH} ...")
ds = load_dataset("json", data_files=str(DATA_PATH), split="train")
print(f"[INFO] Raw samples: {len(ds)}")

def build_prompt(ex: Dict) -> str:
    instr = (ex.get("instruction") or "").strip()
    inp   = (ex.get("input") or "").strip()
    # Simple, robust instruction template
    if inp and inp != "(no replies)":
        return f"{instr}\n\n{inp}"
    return instr

def preprocess(ex: Dict):
    source = build_prompt(ex)
    target = (ex.get("output") or "").strip()

    model_in = tokenizer(
        source,
        max_length=MAX_SOURCE_LEN,
        truncation=True,
        padding=False,
    )
    # target
    with tokenizer.as_target_tokenizer():
        labels = tokenizer(
            target,
            max_length=MAX_TARGET_LEN,
            truncation=True,
            padding=False,
        )
    model_in["labels"] = labels["input_ids"]
    return model_in

print("[INFO] Tokenizing dataset (may take a minute)...")
tokenized = ds.map(preprocess, remove_columns=ds.column_names)
print(f"[INFO] Tokenized samples: {len(tokenized)}")

# Rough step estimate (no packing):
total_steps = math.ceil(len(tokenized) * NUM_EPOCHS / (BATCH_SIZE * GRAD_ACCUM))
print(f"[INFO] Estimated total steps: ~{total_steps}")

# ==============================
# COLLATOR & ARGS
# ==============================
collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)

# NOTE: This TrainingArguments block avoids deprecated fields (v5-friendly).
args = TrainingArguments(
    output_dir=str(OUT_DIR),
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    logging_steps=20,             # prints progress every 20 steps
    save_strategy="epoch",        # simpler than old save_strategy/ evaluation_strategy
    save_total_limit=2,
    do_eval=False,                # no mid-train evaluation/metrics
    fp16=torch.cuda.is_available(),
    bf16=False,
    report_to=[],                 # no wandb/etc
)

# ==============================
# TRAINER
# ==============================
print("[INFO] Initializing Trainer...")
trainer = Trainer(
    model=model,
    args=args,
    train_dataset=tokenized,
    tokenizer=tokenizer,
    data_collator=collator,
)

print("[INFO] Starting training...")
t0 = time.time()
trainer.train()
elapsed = time.time() - t0
print(f"✅ Training finished in {elapsed/60:.1f} min")

print("[INFO] Saving adapter and tokenizer...")
trainer.save_model(str(OUT_DIR))
tokenizer.save_pretrained(str(OUT_DIR))
print(f"✅ Model saved to: {OUT_DIR}")

# ============== Optional sanity generation ==============
try:
    prompt = (
        "Summarize this Reddit thread in 2–3 sentences.\n\n"
        "Root Comment: The devs delayed the update again.\n"
        "Replies:\n- Some users agree stability matters.\n- Others are frustrated by delays."
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    gen = model.generate(**inputs, max_new_tokens=128)
    print("\n[Sample output]")
    print(tokenizer.decode(gen[0], skip_special_tokens=True))
except Exception as e:
    print(f"[WARN] Sample generation skipped: {e}")
