# HR — Failure-Mode Forensics

Deep dive into the three cells where any strategy dropped below 0.95 on HR corpus. Quotes are excerpts from `output/results_hr.csv`.

---

## q-v2-009 — the honest refusal (meta_harness = 0.00)

**Question:** *"What's the maximum duration of short-term disability coverage at GitLab, and what percentage of my salary does it replace?"*

**Golden:** 26 weeks, 66.7% of base salary, provided at no cost, apply via `leaves@gitlab.com`, NYLife responds in 3 business days.

**meta_harness answer (quality 0.00):**
> "The sources provided to me don't contain specific details about GitLab's short-term disability (STD) coverage — including the maximum duration or salary replacement percentage. **What I'd Recommend:** Check the GitLab Handbook directly at `/handbook/total-rewards/benefits/general-and-entity-benefits/`..."

**Mechanism:** the optimizer's final `CurationSpec` excluded `handbook/us-benefits-overview` (verified in `output/final_spec_hr.json` — `include_static_ids` list). The strategy literally cannot see the STD policy doc, so the agent honestly refuses. **This is correct behaviour under the spec; the spec is wrong.**

**Architectural lesson:** proposer-based optimization trades breadth for train-set fit. Every doc-exclusion mutation creates a latent failure on any question that needs that doc. At small train sizes this is unavoidable — the proposer can't see the excluded topic's relevance until it gets graded on a question that needs it.

**Cascade recovery:** cascade_router got 1.00 here by escalating — tier 1 hier presumably hedged, verifier said `confident: 0`, tier 2 agent_managed fetched `us-benefits-overview` with `get_handbook` and answered correctly. Cascade's verifier actually worked *on this case*.

---

## q-v2-010 — the cascade failure in flagrante (hier=0.10, rag=0.30, cascade=0.30)

**Question:** *"I was called up for a 9-month military deployment. After service ends, how long do I have to apply for reinstatement at GitLab?"*

**Golden:** 90 days from end of service (for service >180 days). Escalator principle applies. Healthcare may be retained up to 2 years at own expense.

**hierarchical answer (quality 0.10):**
> "Since your deployment is 9 months, which exceeds the 6-month threshold, here's what you should know: **Leaves longer than 6 months** mean you would be **offboarded**..."

Note: hier hallucinated or misread the 2-year healthcare retention number and never surfaced the 90-day reinstatement window. The router picked `parental-and-other-leave.md` (correct doc) but the model focused on the offboarding clause, not the reinstatement clause.

**rag_embedding answer (quality 0.30):**
> "Based on your deployment length of 9 months (which falls in the 181 days to 5 years range of service), here is what applies to your reinstatement timeline: ⚠️ **The source document appears to be cut off mid-sentence at the reinstatement application deadlines section**, so I cannot provide the specific deadline..."

Note: RAG correctly identified the service category but its top-6 chunks truncated the answer — the 90-day number fell outside the retrieved chunks. This is the **chunking boundary problem** — policy-like docs have dense micro-sections that get split across chunk boundaries.

**cascade_router answer (quality 0.30) — IDENTICAL to hier:**
> "Since your deployment is 9 months, which exceeds the 6-month threshold, here's what you should know: **Leaves longer than 6 months** result in you being..."

**Mechanism:** cascade took hier's tier-1 output. The self-verifier then read hier's answer:
- ✅ cites a handbook source by title
- ✅ specific numbers (9 months, 6 months)
- ✅ no hedging language
- → verifier scored `confident: 1`
- → cascade returned hier's answer without escalating to tier 2

**The verifier never re-checked the source.** It only pattern-matched surface features of the answer. Confident-sounding + wrong = verifier blind spot.

**This reproduces a documented LLM self-consistency failure:** a single model grading its own output is miscalibrated when the error is **specific wrong fact**, not **general hedging**. Cross-model or retrieval-score verification would catch this — same-model self-scoring can't.

**agent_managed recovered to 1.00** on this question because it issued a second `get_handbook` call after an incomplete first fetch, giving it a different slice of the doc that included the reinstatement table.

---

## q-v2-007 — the needs_both partial (agent_managed = 0.90)

**Question:** *"I'm starting as a staff-augmentation contractor next week. Who handles my onboarding and where can I ask contractor-specific questions in Slack?"*

**Golden:** Procurement team (not People Ops) + `#contractor-hub` (created 2026-03-28) + `@contractor-ops` during 9–6 ET + `@procurement_team` for paperwork + three contingent-worker categories.

**agent_managed answer (quality 0.90):**
> "...the People team is not involved — your onboarding is handled by the Procurement team, not People Ops. Refer to the Temporary Service Provider internal handbook page for templates and guidance. **Contractor Slac**..." [truncated in CSV at 500 chars]

**Judge note:** "Covers all key facts accurately: Procurement team, #contractor-hub, @contractor-ops, @procurement_team."

**Mechanism:** this is a **judge/golden-specificity mismatch**, not a real model failure. The agent got the critical facts right but the judge deducted 0.05 likely for (a) missing business-hours window, (b) slightly imprecise framing, or (c) CSV-truncation confusion in the judge's own reading. Recency: 1.0 (correctly surfaced the new Slack channel).

**Why this matters:** even when quality reads `0.90`, inspect the answer before calling it a "failure". Judge granularity is 0.05 on a 4-level rubric; one-step deductions are within noise.

---

## Summary of failure modes (HR corpus)

| mode | affected strategies | root cause | fix direction |
|---|---|---|---|
| **Spec exclusion** | meta_harness_optimized | proposer mutates `include_static_ids` to a subset, excluding a doc needed by an unseen question | larger train set; held-out dev set before Pareto-select; multi-objective proposer that penalizes doc removal |
| **Chunking boundary** | rag_embedding | top-k chunks miss the specific answer span; policy docs have dense micro-sections | smaller chunks + reranker; or semantic chunking; or hybrid retrieval + expand-to-section |
| **Router miss** | hierarchical | LLM router picks the correct doc but the summarizer's summary didn't surface the relevant subtopic | full-doc summaries; multi-granularity summaries (doc + section); or hybrid (router + RAG fallback) |
| **Self-verifier blind spot** | cascade_router | same-model verifier says `confident: 1` on specific-wrong-fact answers | cross-model verifier (Haiku checks Sonnet); retrieval-score verifier; or fine-tuned classifier |
| **Judge granularity** | all (0.90/0.95 cells) | judge rubric is 4-level; partial answers deduct ±0.05 on any missed sub-fact | higher-resolution judge rubric (0.01 or continuous); multi-judge agreement |

---

## Pre-registered predictions for the Polars domain

Before the Polars run happened (blocked on credits), here are the predictions from the HR findings. When that run completed, we tested these directly — pre-registration makes the comparison falsifiable.

**Prediction A — Ranking generalizes (strong):** ensemble ≈ full_context > agent_managed ≫ meta_harness > hierarchical ≈ rag > cascade. If this holds on Polars too, the architectural ordering is robust across domains.

**Prediction B — Agent_managed wins cost-adjusted (strong):** agent_managed gets within 0.5pp of full_context at 40–60% the cost. If true, "best deployable strategy" generalizes.

**Prediction C — meta_harness catastrophic fail on a portal_only question (medium):** the optimizer will exclude a Polars doc that matters for the 2 `docs_only` questions (`q-polars-007` or `q-polars-010`). Expected quality: 0.00 or 0.30 on one of them.

**Prediction D — rag_embedding fails a slack_contradicts question that needs exact API name (medium):** if a deprecation question's old API appears in multiple docs as a keyword, RAG may retrieve a doc that describes the OLD syntax rather than the changelog thread with the NEW syntax. Expected failure: one of `q-polars-001` to `q-polars-004` at ≤0.30.

**Prediction E — cascade fails on the same self-verifier mechanism (strong):** on any Polars question where hier returns a confidently-wrong API name (e.g. says `apply` instead of `map_elements` based on stale docs), the verifier will say `confident: 1` and cascade will return the wrong answer. Expected: cascade quality ≤ hier quality on at least 1 of 4 `slack_contradicts` questions.

**Prediction F — thin_harness ≈ medium harness on easy questions, fails on `needs_both` (medium):** with max_iter=3 and no corpus-split preamble, thin_harness should handle `docs_only` and `slack_only` questions at 0.90+ but drop on `needs_both` (which requires multiple get_* calls). Expected: thin_harness quality ≥ 0.9 on 6 of 10, <0.5 on at least 1 `needs_both`.

**Prediction G — thick_harness quality = medium, cost 1.5–2× (medium):** planning + verifying overhead costs ~$0.08–0.12 per question extra. Quality gain vs medium is probably 0–2pp unless plan + verify catch a specific failure mode. Predicted: thick ≥ agent_managed by 0–0.02; cost 1.5–2× agent_managed.

**Prediction H — Polars `slack_contradicts` are EASIER than HR `slack_contradicts` (weak):** API renames are more lexically distinct than dollar-amount changes, so any strategy that fetches *either* source will spot the contradiction. HR: needed agent to prefer 2026-04 over 2026-01. Polars: needed agent to notice `group_by` vs `groupby` syntax difference. Predicted: all 7 main strategies ≥ 0.95 on all 4 `slack_contradicts` (but not cascade on at least 1 per Prediction E).

**What would falsify the findings:**
- If agent_managed drops below 0.90 on Polars → the tool-use win was HR-specific
- If cascade ≥ agent_managed → self-verifier bias was a fluke on q-v2-010
- If ensemble ≪ full_context in cost → judge-pick overhead scales non-linearly with technical content

**What gets us to a real benchmark after this:** see `eval/eval_runs.md` "From the HR run to a real benchmark" checklist. Nothing in this forensic document is statistically significant at N=10 × 1 seed × 1 model × 2 domains. It's a set of falsifiable hypotheses, not a result.
