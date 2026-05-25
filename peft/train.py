import os
import json
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

def train():
    # 1. Load config settings
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)

    print("Initializing tokenizers...")
    tokenizer = AutoTokenizer.from_pretrained(config["model_name_or_path"])
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # 2. Configure 4-bit Quantization (QLoRA)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16 if config["bf16"] else torch.float16
    )

    print(f"Loading base model {config['model_name_or_path']} in 4-bit...")
    model = AutoModelForCausalLM.from_pretrained(
        config["model_name_or_path"],
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
    
    # 3. Setup LoRA adapter configurations
    model = prepare_model_for_kbit_training(model)
    peft_config = LoraConfig(
        r=config["lora_r"],
        lora_alpha=config["lora_alpha"],
        target_modules=config["target_modules"],
        lora_dropout=config["lora_dropout"],
        bias=config["bias"],
        task_type=config["task_type"]
    )
    
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 4. Load dataset
    print("Loading training dataset...")
    dataset_path = "peft_dataset.jsonl"
    if not os.path.exists(dataset_path):
        dataset_path = os.path.join(os.path.dirname(__file__), "peft_dataset.jsonl")
    dataset = load_dataset("json", data_files=dataset_path, split="train")

    def formatting_prompts_func(example):
        output_texts = []
        for i in range(len(example['instruction'])):
            text = f"### System: You are an enterprise coder. Follow organization style rules.\n### Instruction: {example['instruction'][i]}\n### Input: {example['input'][i]}\n### Response: {example['output'][i]}"
            output_texts.append(text)
        return output_texts

    # 5. Set up Training Arguments
    training_args = TrainingArguments(
        output_dir=config["output_dir"],
        learning_rate=config["learning_rate"],
        num_train_epochs=config["num_train_epochs"],
        per_device_train_batch_size=config["per_device_train_batch_size"],
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        optim=config["optim"],
        fp16=config["fp16"],
        bf16=config["bf16"],
        logging_steps=10,
        save_strategy="epoch",
        report_to="tensorboard",
        overwrite_output_dir=True
    )

    # 6. Initialize Trainer and run fine-tuning
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        max_seq_length=config["max_seq_length"],
        tokenizer=tokenizer,
        formatting_func=formatting_prompts_func,
        args=training_args
    )

    print("Beginning training run...")
    trainer.train()

    # 7. Save Adapter weights
    print(f"Fine-tuning complete. Saving adapter to {config['output_dir']}...")
    model.save_pretrained(config["output_dir"])
    tokenizer.save_pretrained(config["output_dir"])
    print("PEFT pipeline completed successfully.")

if __name__ == "__main__":
    train()
