"""LoRA fine-tuning helper."""

from __future__ import annotations

from pathlib import Path
import os

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from sklearn.model_selection import train_test_split
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    EarlyStoppingCallback,
    TrainingArguments,
)
from trl import SFTTrainer
from huggingface_hub import login

BASE_MODEL = "mistralai/Mistral-7B-Instruct-v0.2"
# dataset built by ``vgj_chat.data.dataset.build_auto_dataset``
# combines manual and automatically generated Q&A pairs
COMBINED_QA_JL = "vgj_combined.jsonl"
CHECKPOINT_DIR = "lora-vgj-checkpoint"

LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
BATCH_PER_GPU = 4
GRAD_ACC_STEPS = 4
LOG_STEPS = 1
EVAL_STEPS = 1
PATIENCE = 3
EPOCHS = 10
LR = 2e-4


def run_finetune() -> None:
    hf_token = os.getenv("VGJ_HF_TOKEN")
    if hf_token:
        login(token=hf_token)
    tok = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True, token=hf_token)
    tok.pad_token = tok.eos_token
    if torch.cuda.is_available():
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        base = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            quantization_config=bnb_cfg,
            device_map={"": 0},
            torch_dtype=torch.float16,
            token=hf_token,
        )
    else:
        base = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            torch_dtype=torch.float32,
            token=hf_token,
        )
    base = prepare_model_for_kbit_training(base)
    lora_cfg = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(base, lora_cfg)

    def to_chat(ex):
        user = ex["instruction"].strip()
        if ex["input"]:
            user += "\n" + ex["input"].strip()
        return {"text": f"<s>[INST] {user} [/INST] {ex['output'].strip()} </s>"}

    dataset = load_dataset("json", data_files=COMBINED_QA_JL, split="train").map(
        to_chat, remove_columns=["instruction", "input", "output"]
    )
    train_idx, eval_idx = train_test_split(
        list(range(len(dataset))), test_size=0.1, random_state=42
    )
    train_set = dataset.select(train_idx)
    eval_set = dataset.select(eval_idx)
    train_args = TrainingArguments(
        output_dir=CHECKPOINT_DIR,
        per_device_train_batch_size=BATCH_PER_GPU,
        gradient_accumulation_steps=GRAD_ACC_STEPS,
        num_train_epochs=EPOCHS,
        learning_rate=LR,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=LOG_STEPS,
        eval_strategy="steps",
        eval_steps=EVAL_STEPS,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        save_strategy="steps",
        fp16=True,
        report_to=[],
    )
    trainer = SFTTrainer(
        model=model,
        args=train_args,
        train_dataset=train_set,
        eval_dataset=eval_set,
        callbacks=[
            EarlyStoppingCallback(
                early_stopping_patience=PATIENCE, early_stopping_threshold=0.0
            )
        ],
    )
    trainer.train()
    model.save_pretrained(CHECKPOINT_DIR)
    tok.save_pretrained(CHECKPOINT_DIR)
    print(f"LoRA adapter + tokenizer saved to → {CHECKPOINT_DIR}")
