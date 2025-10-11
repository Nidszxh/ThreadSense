"""
Automatic Fine-Tuning Dataset Builder (Flan-T5 Large, Fast Mode)
----------------------------------------------------------------
Uses a lightweight, instruction-tuned model for rapid dataset generation.

- Reads: data/llm_inputs/llm_inputs_2.json
- Generates 4 prompt-style summaries per root comment
- Saves to: data/fine_tune/reddit_summarization_dataset.jsonl

⚡ Much faster than Falcon (3–6 sec per generation on GPU)
"""

import re
import json
import logging
from pathlib import Path
from time import time
from tqdm import tqdm
from typing import Dict, List
from transformers import pipeline

# ==============================
# CONFIG / PATHS
# ==============================
INPUT_FILE = Path(r"C:\Users\Sriman Rakshan N\Documents\Amrita\Project_Sem_V\new\ThreadSense\data\llm_inputs\llm_input_2.json")
OUTPUT_PATH = Path("data/fine_tune/reddit_summarization_dataset.jsonl")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

MODEL_NAME = "google/flan-t5-large"   # ⚡ Fast + Instruction-tuned

# ==============================
# LOGGING
# ==============================
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

# ==============================
# PROMPT VARIANTS
# ==============================
PROMPT_VARIANTS = ["zero_shot", "few_shot", "chain_of_thought", "role_play"]

def few_shot_examples() -> str:
    return (
        "### Example 1\n"
        "Root: 'The devs delayed the update again.'\n"
        "Replies:\n- Some users agree stability matters.\n- Others are frustrated by delays.\n"
        "Good Summary: 'Users debate the delay: some prefer stability, others express frustration.'\n\n"
        "### Example 2\n"
        "Root: 'Is this feature worth it?'\n"
        "Replies:\n- Opinions vary; performance differs by setup.\n"
        "Good Summary: 'Users share mixed opinions depending on their setup and needs.'\n\n"
    )

def build_prompt(variant: str, root: str, replies: str) -> str:
    base = f"Root Comment: {root}\nReplies:\n{replies}\n\n"
    if variant == "zero_shot":
        return base + "Summarize this Reddit thread in 2–3 sentences.\nSummary:"
    elif variant == "few_shot":
        return few_shot_examples() + base + "Now summarize the above thread in the same style.\nSummary:"
    elif variant == "chain_of_thought":
        return (
            base
            + "Think step by step:\n"
              "1. Identify key discussion points.\n"
              "2. Rank them by importance.\n"
              "3. Write a short summary.\nSummary:"
        )
    elif variant == "role_play":
        return (
            "You are a Reddit moderator summarizing this discussion neutrally.\n"
            + base
            + "Write a balanced 2–3 sentence summary.\nSummary:"
        )
    else:
        raise ValueError(f"Unknown variant: {variant}")

def clean_summary(text: str) -> str:
    text = re.sub(r"(?is)summary:\s*", "", text).strip()
    text = text.replace("\n", " ").strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:5]).strip()

# ==============================
# GENERATOR SETUP
# ==============================
logging.info(f"⚡ Loading model: {MODEL_NAME}")
generator = pipeline(
    "text2text-generation",
    model=MODEL_NAME,
    device=0,  # GPU
)
logging.info("✅ Model ready and running on GPU.")

# ==============================
# MAIN PIPELINE
# ==============================
def generate_summary(prompt: str) -> str:
    """Fast generation using Flan-T5."""
    result = generator(
        prompt,
        max_new_tokens=150,
        temperature=0.4,
        top_p=0.9,
        do_sample=True
    )[0]["generated_text"]
    return clean_summary(result)

def build_instruction_sample(variant: str, root: str, replies: str, summary: str) -> Dict:
    style = variant.replace("_", " ")
    return {
        "instruction": f"Summarize this Reddit thread in {style} style.",
        "input": f"Root Comment: {root}\nReplies:\n{replies}",
        "output": summary
    }

def process_thread(path: Path) -> List[Dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    comments = data["comments"]
    root_comments = [c for c in comments if c.get("depth", 0) == 0][:10]  # limit to first 10

    total_tasks = len(root_comments) * len(PROMPT_VARIANTS)
    samples = []
    start_time = time()

    logging.info(f"🚀 Starting summarization for {len(root_comments)} root comments × {len(PROMPT_VARIANTS)} variants = {total_tasks} generations.")

    for i, root in enumerate(root_comments, start=1):
        replies = [c["text"] for c in comments if c.get("parent_id") == root["author"]]
        replies_text = "\n".join(f"- {r}" for r in replies) if replies else "(no replies)"

        for j, variant in enumerate(PROMPT_VARIANTS, start=1):
            step = (i - 1) * len(PROMPT_VARIANTS) + j
            logging.info(f"[{step}/{total_tasks}] Generating ({variant}) for author: {root.get('author')}")

            try:
                gen_start = time()
                summary = generate_summary(build_prompt(variant, root["text"], replies_text))
                gen_time = time() - gen_start
                samples.append(build_instruction_sample(variant, root["text"], replies_text, summary))

                elapsed = time() - start_time
                avg_time = elapsed / step
                eta = avg_time * (total_tasks - step)
                logging.info(f"✅ Done in {gen_time:.2f}s | ETA: {eta/60:.1f} min remaining.")
            except Exception as e:
                logging.warning(f"⚠️ Error generating for {variant}: {e}")
                continue

    logging.info(f"🎯 Completed all {total_tasks} generations.")
    return samples

def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    logging.info(f"Processing single thread file: {INPUT_FILE.name}")
    total_samples = process_thread(INPUT_FILE)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for s in total_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    logging.info(f"✅ Total samples generated: {len(total_samples)}")
    logging.info(f"✅ Dataset saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
