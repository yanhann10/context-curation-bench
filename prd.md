**PRD: HR Living Docs Context Curation Experiment**

**Project ID:** hr-living-docs-context-curation  
**Version:** 1.1  
**Date:** April 2026  
**Goal:** 2-hour staged hackathon / learning project (lean Python codebase only — no Jupyter notebook)

#### 1. Objective & Thesis
Build a minimal **New Hire Onboarding Agent** that answers HR questions using a hybrid knowledge base:
- Static HR policy documents sourced from the public GitLab Employee Handbook (https://handbook.gitlab.com/handbook/)
- Fresh Slack-style HR threads (synthetic live answers not yet indexed)

**Core Thesis:**  
Compare context curation strategies on this realistic task. Start with **Stage 1**: Full context stuffing vs. Meta-Harness auto-optimized context.  
After a complete end-to-end run, optionally extend to embedding retrieval, agent-managed context, and hand-curated baseline.  
This tests whether “just stuff the full context window” holds when mixing static handbook content with noisy fresh chat data, and whether Meta-Harness can automatically discover better context handling.

**Meta-Harness Integration:**  
Use https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact (and refer to https://yoonholee.com/meta-harness/) to auto-optimize the harness for context management (retrieval, formatting, injection logic). Meta-Harness evolves the surrounding code using full execution traces and filesystem access.

**Data Source Update:**  
Use content from the public **GitLab Handbook** (https://handbook.gitlab.com/handbook/) as the static HR document set. Extract relevant sections on expenses, time off, onboarding, IT setup, and benefits. Include specific examples such as expense policies, reimbursement processes, budget limits, home office equipment, PTO, and IT onboarding.


#### 2. Success Criteria (Done = End-to-End Stage 1)
- Lean single-file or minimal multi-file Python codebase (`main.py` + small supporting modules)
- Stage 1 fully working: Full context baseline vs. Meta-Harness optimized harness
- At least 6 test questions with golden answers
- Automatic logging and evaluation (quality score, latency, token usage)
- Clear README with findings from Stage 1 run
- Total initial build ≤ 2 hours

#### 3. In Scope – Staged Implementation
**Stage 1 (Mandatory – Complete First):**
- Full context strategy: Stuff all extracted GitLab Handbook sections + all Slack threads into every prompt
- Meta-Harness integration: Use the artifact/repo to auto-optimize the harness (focus on context curation logic)
- Run end-to-end comparison on the test set
- Evaluation framework with metrics

**Stage 2 (Only After Stage 1 Completes):**
- Add embedding-based retrieval
- Add agent-managed context (simple tool-calling loop for “request what I need”)
- Add hand-curated baseline (manual best-context per question)

#### 4. Out of Scope
- Jupyter notebooks — pure lean Python scripts only
- Production UI or real Slack integration
- More than 6–8 test questions initially
- Scraping the full handbook automatically (manually copy/paste 8–12 relevant sections into data/ files)

#### 5. Technical Requirements

**Stack (Minimal)**
- Python 3.10+
- `openai` SDK (gpt-4o or gpt-4o-mini recommended)
- `sentence-transformers` or OpenAI embeddings (for later stages)
- `numpy`, `pandas`, `time`, `json`
- Meta-Harness artifact from https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact (clone or copy relevant harness optimization components; adapt for context evolution)
- Refer to https://yoonholee.com/meta-harness/ for usage patterns

**Data Layer (data/ folder)**
- Extract and save as plain text or markdown files from GitLab Handbook:
  - Expense-related: Global Travel and Expense Policy (or internal equivalent), home office equipment/supplies, reimbursement processes
  - Time off: Time Off Types, Flexible PTO policy, sick time
  - Onboarding/IT: GitLab IT Onboarding 101, remote onboarding guide
  - Other useful sections: Benefits overview, procurement policies (8–12 total files/chunks)
- Keep total stuffed tokens < 12k when combined
- Slack threads (4–6 synthetic): short Q&A with some noise/irrelevant replies (e.g., recent expense approval questions answered in Slack)
- Each item as dict: `{"id": str, "type": "static"|"slack", "content": str, "metadata": {"title": str, "source": "gitlab-handbook" or "slack"}}`

**Core Scripts**
- `main.py` — entry point with Stage 1 logic
- `strategies.py` — full_context() and meta_harness_optimized() functions
- `evaluator.py` — quality scoring (LLM-as-judge or simple overlap vs golden), logging to CSV
- `data_loader.py` — load GitLab Handbook excerpts and test questions
- `harness_optimizer.py` — integration point for Meta-Harness (adapt proposer to evolve context logic using traces)

**Evaluation**
- 6 test questions focused on new hire HR topics, e.g.:
  - “What is the expense budget limit or reimbursement process for new hires?”
  - “How does the Flexible PTO policy work for new team members?”
  - “What do I need to do for IT/laptop setup as a new hire?”
- Golden answers based on handbook content
- Metrics per run:
  - Quality score (0–1 via LLM judge prompt)
  - Latency (wall-clock seconds)
  - Prompt + completion tokens
  - Failure notes (e.g., “expense limit buried in full context”)
- Output: `output/results_stage1.csv` + simple console summary
and a master doc in eval/eval_runs.md

#### 6. Stage 1 Implementation Guidelines
1. Manually extract and place relevant GitLab Handbook sections (expense policy, PTO, IT onboarding, etc.) into `data/` as text files
2. Implement `full_context(question)`: concatenate all handbook content + Slack threads + system prompt for onboarding agent
3. Integrate Meta-Harness: Set up filesystem for harness candidates, traces, and scores. Let the optimizer evolve context management code (what to include, order, compression, etc.)
4. Run both strategies on the 6 questions
5. Log and compare results
6. Only after successful Stage 1 run: extend to other strategies in the same codebase
7. Dont spend too much energy on token cost estimation

#### 7. Deliverables
 Stage 1
- `main.py` (lean entry point)
- Supporting `.py` files (keep total code minimal)
- `data/` folder with extracted GitLab Handbook sections (include expense portal/budget examples) and `test_questions.json`
- `results/` folder with CSV logs
- `README.md` containing:
  - Thesis summary
  - How to run Stage 1
  - Key findings from the run
  - Link to Meta-Harness resources and GitLab Handbook source
  Stage 2
  - test out at least another method (e.g embedding (openai, qwen, cohere etc)), each context strategy has a cleaner delineaated .py without over engineering
  - update output and eval 
  Stage 3 
  - generate synthetic data (as if from slack api read format) where the info is slightly different from the original data but there are supposed to be the truth / more recent info validated by hr 
  - udpate agents to be able to consolidate info. set all original doc datatime to 2026-01-01.
  - make sure u benchmark token usage and accuracy across different context curation strategy
  Stage 4
  - use ai4research to generate for curation strategy (and try etc https://github.com/MaxGfeller/open-harness)


