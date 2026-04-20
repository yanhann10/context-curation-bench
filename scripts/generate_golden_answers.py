"""Generate golden answers for ConflictQA questions using Bedrock Claude.

For each question, feeds all yes/no source texts to Claude and asks for a
nuanced synthesis answer with key_facts. Tracks timing and saves progress
incrementally.

Usage:
    python3 scripts/generate_golden_answers.py
"""
import json
import time
import boto3
from pathlib import Path
from datetime import datetime, timezone

MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
REGION = "us-east-1"
MAX_TOKENS = 600

SYSTEM = """You are writing golden answers for a benchmark that tests whether AI systems can synthesize conflicting evidence.

Given a debatable question and multiple source texts that disagree (some say yes, some say no), write:
1. A golden_answer (150-250 words): A nuanced synthesis that acknowledges both sides, identifies where evidence converges and diverges, and states the current consensus or why there isn't one. Do NOT just pick a side. Cite specific evidence patterns (e.g., "meta-analyses show X but critics argue Y").
2. key_facts (5 items): Five concrete, verifiable claims that a good answer must contain. These should be specific enough to grade against (e.g., "effect size is modest at SMD ~0.3") not vague (e.g., "the evidence is mixed").

Return JSON only:
{"golden_answer": "...", "key_facts": ["...", "...", "...", "...", "..."]}"""


def generate_one(client, question: str, sources: list[dict]) -> dict:
    """Generate golden answer for one question."""
    # Build source summary — trim to 500 chars/source to stay under token limits
    source_text = ""
    max_chars = min(500, 6000 // max(len(sources), 1))  # budget ~6k chars total
    for s in sources:
        stance = s.get("extra", {}).get("stance", "?")
        title = s.get("title", "Unknown")
        content = s.get("content", "")[:max_chars]
        source_text += f"\n[{stance.upper()}] {title}\n{content}\n"

    user_msg = f"QUESTION: {question}\n\nSOURCES ({len(sources)} total):\n{source_text}\n\nReturn JSON only."

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": user_msg}],
    })

    # Retry with exponential backoff for throttling
    t0 = time.time()
    for attempt in range(6):
        try:
            resp = client.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                body=body,
            )
            break
        except Exception as e:
            if "ThrottlingException" in str(type(e).__name__) or "Too many requests" in str(e):
                wait = 2 ** attempt + 1
                print(f"    throttled, waiting {wait}s (attempt {attempt+1}/6)")
                time.sleep(wait)
            else:
                raise
    latency = time.time() - t0

    result = json.loads(resp["body"].read())
    text = result["content"][0]["text"]
    usage = result.get("usage", {})

    # Parse JSON from response
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{[\s\S]*\}", text)
        data = json.loads(m.group(0)) if m else {"golden_answer": text, "key_facts": []}

    return {
        "golden_answer": data.get("golden_answer", ""),
        "key_facts": data.get("key_facts", []),
        "latency_s": round(latency, 2),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
    }


def main():
    start_time = datetime.now(timezone.utc)
    print(f"[{start_time.isoformat()}] Starting golden answer generation")

    client = boto3.client("bedrock-runtime", region_name=REGION)

    # Load questions and corpus
    with open("data/conflictqa/questions_raw.json") as f:
        questions = json.load(f)

    with open("data/conflictqa/corpus.jsonl") as f:
        docs = [json.loads(l) for l in f]
    docs_by_id = {d["id"]: d for d in docs}

    # Check for existing progress
    progress_path = Path("data/conflictqa/golden_progress.json")
    done = {}
    if progress_path.exists():
        with open(progress_path) as f:
            done = json.load(f)
        print(f"Resuming: {len(done)}/{len(questions)} already done")

    total_tokens_in = 0
    total_tokens_out = 0
    total_latency = 0.0

    for i, q in enumerate(questions):
        qid = q["id"]
        if qid in done:
            continue

        sources = [docs_by_id[sid] for sid in q["relevant_source_ids"] if sid in docs_by_id]

        try:
            result = generate_one(client, q["question"], sources)
            q["golden_answer"] = result["golden_answer"]
            q["key_facts"] = result["key_facts"]
            done[qid] = result

            total_tokens_in += result["input_tokens"]
            total_tokens_out += result["output_tokens"]
            total_latency += result["latency_s"]

            print(f"  [{i+1:3d}/{len(questions)}] {qid} — {result['latency_s']:.1f}s "
                  f"({result['input_tokens']}+{result['output_tokens']} tok) "
                  f"— {q['question'][:50]}")

            # Save progress every 5 questions
            if (i + 1) % 5 == 0:
                with open(progress_path, "w") as f:
                    json.dump(done, f, indent=2)

        except Exception as e:
            print(f"  [{i+1:3d}/{len(questions)}] {qid} — ERROR: {e}")
            time.sleep(5)
            continue

        # Throttle: 1.5s between calls to avoid Bedrock rate limits
        time.sleep(1.5)

    # Save final progress
    with open(progress_path, "w") as f:
        json.dump(done, f, indent=2)

    # Build final questions with golden answers
    for q in questions:
        if q["id"] in done:
            q["golden_answer"] = done[q["id"]]["golden_answer"]
            q["key_facts"] = done[q["id"]]["key_facts"]

    # Write final files
    with open("data/conflictqa/test_questions.json", "w") as f:
        json.dump(questions, f, indent=2)

    with open("data/conflictqa/questions.jsonl", "w") as f:
        for q in questions:
            f.write(json.dumps(q) + "\n")

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    # Write run metadata
    meta = {
        "task": "generate_golden_answers",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_s": round(duration, 1),
        "model": MODEL_ID,
        "questions_total": len(questions),
        "questions_generated": len(done),
        "total_input_tokens": total_tokens_in,
        "total_output_tokens": total_tokens_out,
        "total_latency_s": round(total_latency, 1),
        "avg_latency_s": round(total_latency / max(len(done), 1), 2),
    }
    with open("data/conflictqa/generation_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Done: {len(done)}/{len(questions)} golden answers")
    print(f"Duration: {duration:.0f}s ({duration/60:.1f}min)")
    print(f"Tokens: {total_tokens_in} in + {total_tokens_out} out")
    print(f"Avg latency: {total_latency/max(len(done),1):.1f}s per question")
    print(f"Files: data/conflictqa/test_questions.json, questions.jsonl")


if __name__ == "__main__":
    main()
