# ConflictQA Track

## What this tests

ConflictQA is an **experimental synthesis-heavy sidecar track**. It stress-tests what happens when sources genuinely disagree and there is no simple authority or timestamp signal to resolve the question.

Each question has 7–15 real web sources that take opposing stances (yes/no) on a debatable topic. The curation challenge: aggregate conflicting evidence, weigh source quality, and produce a **nuanced synthesis** — not just pick a side.

This stresses a narrower mechanism than the main benchmark mix:
- main benchmark: direct lookup, source-specific updates, multi-source synthesis, resolved conflicts, and abstention-capable items
- ConflictQA: evidence-quality-based synthesis when sources disagree and no simple resolution signal exists

## Data attribution

Source data: [kortukov/ConflictingQA](https://huggingface.co/datasets/kortukov/ConflictingQA) on HuggingFace.

Paper: Kortukov et al., *"Studying Large Language Model Behaviors Under Context-Memory Conflicts With Real-World Knowledge"*

The corpus documents are real web page excerpts from the ConflictingQA dataset, preserved with original text, titles, and URLs. Questions and golden answers were written for this benchmark.

## Corpus structure

- **93 documents** across 10 topics (7–15 sources per topic)
- All documents have `kind: static` — no freshness signal
- All documents have empty timestamps — recency-based strategies cannot cheat
- Each document carries a `stance` field in extras (yes/no) for analysis, but this is NOT exposed to the agent

## Question categories

All 10 questions are synthesis-heavy. This track should be treated as one task family, not as the benchmark's whole purpose.

## Topics

| # | Domain | Question |
|---|---|---|
| 1 | Pharmacology | Are antidepressants more effective than placebo? |
| 2 | Neuroscience | Does fish oil improve brain function? |
| 3 | Cardiology | Do saturated fats increase the risk of heart disease? |
| 4 | Virology | Can HIV be cured? |
| 5 | Sustainability | Are electric cars really green? |
| 6 | Renewable Energy | Can renewables provide stable power? |
| 7 | Nuclear Energy | Can nuclear power solve climate change? |
| 8 | Climate Change | Are electric cars a solution to climate change? |
| 9 | Robotics | Can robots be programmed to feel pain? |
| 10 | Quantum Physics | Do virtual particles truly exist? |

## What strategies should do differently here

- **Full context:** All 93 docs in prompt. Model must identify which topic is relevant and synthesize opposing views.
- **RAG:** Embedding similarity may cluster same-stance sources. Top-k=6 might return only one side.
- **Hierarchical:** Router must select sources from BOTH sides. Summaries may lose the stance signal.
- **Agent-managed:** Can iteratively fetch sources, but needs to actively seek opposing views.
- **Ensemble:** Judge picks between two strategies' answers — both may be biased toward one side.

The prediction: **RAG will be biased toward the majority stance** (if 7/10 sources say "yes," top-k retrieval likely over-represents "yes"). Agent-managed should be more balanced if it explicitly seeks both sides. Full context should be most balanced but at highest cost.
