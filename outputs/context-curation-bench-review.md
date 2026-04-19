# Peer Review: xcbench — Context Curation Benchmark

**Artifact:** https://github.com/yanhann10/context-curation-bench  
**Reviewer:** Feynman (automated peer review)  
**Date:** 2026-04-19  
**Verdict:** Not publishable in current form. Contains valuable architectural intuitions and honest self-critique, but the statistical foundation cannot support any of the headline claims. Several design choices systematically bias results.

---

## Loopholes (Biggest → Smallest)

### 1. [FATAL] N=10 × 1 seed × 1 model renders all strategy comparisons statistically meaningless

**Evidence:** Both Stage 3 (HR) and Stage 4 (Polars) evaluate exactly 10 questions each, with a single random seed (temperature=0 for answers, 0.4 for proposer), using a single model (Claude Sonnet 4.6) for all roles.

**Impact:** At N=10, each cell has resolution of 0.10. The headline claim that ensemble (0.995) beats agent_managed (0.990) rests on a difference of 0.005 — **1/20th of the minimum detectable effect**. The Stage 4 finding that "thin > medium > thick" (0.955 vs 0.905 vs 0.810) is driven by 1-2 individual question failures, not systematic quality differences. No confidence intervals, no significance tests, no bootstrap. The artifact's own `eval_runs.md` acknowledges "N=10 resolution is 0.1; ±0.05 per cell is noise" — yet the README presents the numbers as findings, not hypotheses.

**What would fix it:** N≥200, ≥3 seeds, bootstrap CIs, paired significance tests (McNemar or permutation). The eval_runs.md checklist correctly identifies all of this.

---

### 2. [~~FATAL~~ FIXED] Judge prompt leaked question category, creating circular evaluation

**Status:** ✅ Fixed. `JUDGE_SYSTEM` no longer references `category` or `slack_contradicts`. The `category` field was removed from the judge payload in `evaluator_async.py`. The judge now scores purely on factual correctness against the golden answer.

**Original issue:** The `JUDGE_SYSTEM` prompt explicitly told the judge to penalize stale answers on `slack_contradicts` questions, and the judge payload included the `category` field. This made the quality metric a proxy for "did you include Slack data?" rather than "did you answer correctly?"

**Residual risk:** Existing Stage 3/4 results were produced with the old leaked prompt. A rerun is needed to produce clean scores. The key_facts list still reaches the judge — this is appropriate (it's ground-truth), but a future audit should confirm key_facts don't encode category signal.

---

### 3. [~~MAJOR~~ FIXED] Pareto frontier in README omitted a non-dominated strategy

**Status:** ✅ Fixed. README key-numbers table and Pareto frontier listing now include `rag_embedding` as non-dominated. All 7 strategies shown with frontier status column. Illustrative output block updated.

**Original issue:** README listed only `hierarchical`, `agent_managed`, `ensemble` as non-dominated. `rag_embedding` (quality 0.925, cost $0.141, tokens 2161) was also non-dominated — no strategy beat it on all three axes. Verified by running `xcbench/frontier.py` on `summary_stage3.json`.

**Residual note:** On Stage 4 Polars, `rag_embedding` dominates 7 of 8 strategies. The README should eventually add a Stage 4 Pareto table or note the cross-domain divergence more prominently.

---

### 4. [~~MAJOR~~ FIXED] Train ⊂ eval contamination for meta_harness

**Status:** ✅ Fixed. Suite spec now supports `optimize.dev_size` (default 3). The optimizer trains on `questions[:4]`, monitors overfit on `questions[4:7]` (dev), and final eval runs on all 10 (with the dev split giving a clean overfit signal). The optimizer already supported `dev_questions` internally — it just wasn't wired through the CLI/spec.

**Changes:**
- `xcbench/spec.py`: `OptimizeCfg` gained `dev_size: int = 3`
- `xcbench/optimizer.py`: `fit()` now accepts and passes `dev_questions`
- `xcbench/cli.py`: slices questions into train/dev/held-out and passes dev to optimizer
- `suites/sample_data_hr_policy.yaml`: `dev_size: 3` added

**Residual note:** Existing Stage 3/4 results were produced without a dev split — a rerun is needed. The dev split is still small (3 questions); at N=10 total this is the best possible split without more questions.

---

### 5. [~~MAJOR~~ MITIGATED] Same model judges its own outputs — self-preference bias

**Status:** ⚠️ Mitigated with guardrails. The runner now warns at runtime when `agent_model == judge_model`. Spec validation prints a stderr warning. README documents that the judge model MUST differ from the agent model.

**Changes:**
- `xcbench/cli.py`: warns when agent == judge at runtime
- `xcbench/spec.py`: `validate()` prints stderr warning when models match
- `README.md`: "Reproducing these numbers" section documents cross-model requirement
- Suite YAML already defaults to `agent: claude-sonnet-4-6`, `judge: claude-opus-4-7` (different models)

**Residual risk:** The warning is non-blocking — users can still run with the same model. Historical Stage 4 results (eval_runs.md says "all roles = claude-sonnet-4-6") used the same model. A rerun with the cross-model default is needed. Human calibration on 50+ questions remains absent.

---

### 6. [MAJOR] Synthetic corpus eliminates real-world difficulty, inflating all quality scores

**Evidence:** Both corpora are author-constructed:
- HR corpus: 11 handbook docs "styled after GitLab" + 10 synthetic Slack threads with `validated_by_hr=true`
- Polars corpus: curated docs + synthetic deprecation threads

All contradictions are clean binary flips ($100→$125, 16 weeks→20 weeks, `groupby`→`group_by`). All questions have exactly one correct answer derivable from the provided sources.

**Impact:** Real enterprise knowledge bases have ambiguous policies, partial contradictions, multi-step reasoning chains, and questions where the "right" answer depends on unstated context. The clean binary-flip design means any strategy that sees both sources will trivially resolve the contradiction. This explains why 6 of 9 strategies hit 1.000 on Stage 4 Polars — the task is too easy for modern LLMs when the relevant source is in context. The benchmark measures retrieval success, not reasoning quality.

---

### 7. [MAJOR] Prompt portability bug contaminates Stage 4 results but is reported as a finding

**Evidence:** `stage4_polars_results.md` documents that `agent_managed` hardcodes "New Hire Onboarding assistant" in its system prompt. On Polars, the agent refuses questions it considers off-topic (q-polars-009 = 0.20). The same bug affects thin_harness.

**Impact:** The artifact reports this as "Failure Mode 1 — THE benchmark-portability bug" and draws architectural conclusions from it ("tool-use harnesses that embed domain assumptions in their system prompt are not benchmark-portable"). But this is a trivial implementation bug, not an architectural insight. The Stage 4 agent_managed quality (0.905) and the "thin > medium > thick" ordering are artifacts of the bug, not of strategy architecture. Reporting buggy results as findings without a corrected rerun is methodologically unsound.

---

### 8. [MAJOR] Category distribution (40% slack_contradicts) doesn't match real query distributions

**Evidence:** `test_questions_v2.json` contains 4 `slack_contradicts`, 2 `slack_only`, 2 `needs_both`, 2 `portal_only`. The `eval_runs.md` acknowledges: "Current set is 40% slack_contradicts; real ops queries are 5–15% staleness."

**Impact:** The overweight on contradiction questions inflates the importance of recency handling. Strategies that excel at contradiction detection (ensemble, full_context) get a structural advantage in the aggregate quality number. With a realistic 10% staleness rate, hierarchical and RAG would likely close the quality gap with complex strategies, since they perform well on non-contradiction questions.

---

### 9. [MINOR] Oracle router headline is misleading — compares theoretical vs. deployed

**Evidence:** README headline: "an oracle router over the 7 strategies hits 1.000 quality at ~5× cheaper than stuffing the full context." The oracle is computed post-hoc by picking the cheapest perfect-scoring strategy per question from Stage 3 results.

**Impact:** Comparing a non-deployable theoretical construct against real strategies without qualification is misleading. The "~5× cheaper" framing implies this is achievable, but the oracle's picks depend on knowing the correct answer first. The README does note "(theoretical)" in the table, but the headline omits this qualifier.

---

### 10. [MINOR] key_facts_recall metric is structurally broken for long answers

**Evidence:** `metrics.py` implements `key_facts_recall` as substring match: `normalize(fact) in normalize(pred)`. Key facts are phrases like "New individual HSA contribution is $125/month effective April 1, 2026". A verbose answer that repeats source text gets high recall; a correct concise answer may miss the exact substring.

**Impact:** This metric reads 0.00–0.10 across nearly all strategies (Stage 3: 0.00–0.08; Stage 4: 0.02–0.10). It's not discriminative — effectively dead weight in the metric battery. The artifact doesn't use it for any claim, but reporting it suggests it's informative when it isn't.

---

### 11. [MINOR] F1 against long golden answers is structurally uninformative

**Evidence:** Golden answers are 50–100 word paragraphs. Model answers are 200+ words. Token-level F1 between these is dominated by shared function words and generic policy language, not factual accuracy. All strategies cluster at F1 0.30–0.55.

**Impact:** Same as above — reported but not discriminative. The LLM-judge quality score carries all the weight, making the other metrics decorative.

---

### 12. [MINOR] No out-of-distribution questions test refusal behavior

**Evidence:** All 20 questions (10 HR + 10 Polars) have relevant sources in the corpus. No questions test whether strategies appropriately refuse when no source exists.

**Impact:** Agent-based strategies (agent_managed, cascade, thick_harness) have different refusal profiles. Without OOD questions, the benchmark cannot assess whether high quality comes at the cost of hallucinating on unanswerable questions.

---

### 13. [MINOR] README numbers mix Stage 3 and Stage 4 without clear delineation

**Evidence:** The README's "Key numbers" table uses Stage 3 HR data (7 strategies). The "Charts" section shows Stage 4 data (9 strategies). The Pareto frontier image (`frontier_stage3.png`) is Stage 3. The demo output mock-up uses Stage 3 numbers. A reader unfamiliar with the stage numbering could conflate results from different domains.

**Impact:** Minor confusion risk. The eval docs are well-organized internally, but the README mixes stages.

---

### 14. [MINOR] Cost accounting excludes judge costs in some comparisons

**Evidence:** `evaluator_async.py` sums `agent_cost + judge_cost` in `RunResult.cost_usd`. But the README's cost comparisons ("ensemble at 64% of full-context cost") use total cost including judge overhead, which is roughly constant across strategies. This means the token-efficiency differences between strategies are diluted by a fixed judge cost floor.

**Impact:** The actual context-curation cost savings of cheaper strategies are understated. If judge cost were stripped, the ratios would be more dramatic (hierarchical would be even cheaper relative to ensemble).

---

## Strengths

Despite the statistical limitations, this artifact has genuine qualities rare in evaluation-focused work:

1. **Pre-registered predictions with honest falsification.** The Stage 3 forensics doc makes 8 specific, falsifiable predictions about Stage 4 outcomes. 6 were falsified, and the artifact reports this openly rather than post-hoc rationalizing. This is exemplary scientific practice.

2. **Forensic failure-mode analysis.** The per-question failure breakdowns (e.g., cascade's self-verifier blind spot on q-v2-010, meta_harness's doc exclusion) are genuinely informative and well-documented with mechanism + evidence + architectural lesson.

3. **Honest framing section.** The README explicitly states what the artifact is NOT (a faithful Meta-Harness port, a production benchmark, a significance claim). The `eval_runs.md` "From Stage 3 to a real benchmark" checklist is a thorough roadmap.

4. **The most important finding is actually correct.** "Strategy ordering does not transfer across corpus structure" — this IS supported by the two-domain comparison, even at N=10. The specific orderings are noisy, but the instability of rankings across domains is robust.

5. **Clean code architecture.** Registry pattern, YAML-driven suites, async runners, strategy adapters. The codebase is well-organized for extensibility.

6. **Two-domain comparison.** Most evaluation papers test one domain. Testing HR + Polars and finding that rankings flip is a valuable methodological contribution, even as a pilot.

---

## Recommendation

**Major revision required.** The core idea — Pareto-frontier evaluation of context-curation strategies — is sound and fills a gap in the RAG evaluation literature. But the current execution cannot support the headline claims. Priority fixes:

1. Scale to N≥100 with ≥3 seeds and significance tests
2. Remove category leakage from the judge prompt
3. Fix the prompt portability bug and rerun Stage 4
4. Add human calibration for 50+ judge calls
5. Correct the Pareto frontier to include rag_embedding
6. Add a held-out test split for meta_harness

The forensic analysis and prediction-falsification methodology should be preserved — they're the artifact's best contribution.

---

## Sources

- Repository: https://github.com/yanhann10/context-curation-bench
- Judge prompt: `src/evaluator.py` lines 18–24 (`JUDGE_SYSTEM`)
- Stage 3 forensics: `eval/stage3_forensics.md`
- Stage 4 results: `eval/stage4_polars_results.md`
- Eval methodology: `eval/eval_runs.md`
- Metrics: `src/metrics.py`
- Questions: `data/test_questions_v2.json`
- Stage 4 summary data: `output/summary_stage4.json`
- Meta-Harness (Stanford IRIS Lab, 2025): https://yoonholee.com/meta-harness/
- Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" (2023): arXiv:2306.05685
