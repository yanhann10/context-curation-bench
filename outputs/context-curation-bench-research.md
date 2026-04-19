# Research Notes: context-curation-bench

## Artifact Summary
xcbench is a YAML-driven benchmark comparing 9 LLM context-curation strategies (full_context, RAG, hierarchical, agent_managed, cascade, ensemble, meta_harness, thin_harness, thick_harness) on a contradiction-aware corpus. Two domains: HR policy (Stage 3) and Polars docs (Stage 4), 10 questions each. Uses LLM-as-judge (Claude Sonnet 4.6 for agent, same model for judge in most runs). Reports Pareto frontiers over (quality, cost, tokens).

## Key Claims to Verify
1. "Ensemble matches full_context quality (0.995) at 64% cost" — Stage 3 HR
2. "Strategy ordering does not transfer across corpus structure" — cross-domain finding
3. "Oracle router hits 1.000 at ~5× cheaper than full_context"
4. "Cascade self-verification is broken" — same-model verifier blind spot
5. "Thicker scaffolding hurts on Polars" — thin > medium > thick
6. Pre-registered predictions: 1/8 confirmed, 6 falsified, 1 partial

## Data Collected

### Stage 3 (HR) — summary_stage3.json (via eval_runs.md)
| strategy | quality | cost_usd |
|---|---|---|
| full_context | 0.995 | 0.670 |
| ensemble | 0.995 | 0.428 |
| agent_managed | 0.990 | 0.320 |
| rag_embedding | 0.925 | 0.141 |
| hierarchical | 0.910 | 0.118 |
| cascade_router | 0.925 | 0.904 |
| meta_harness | 0.890 | 0.431 |

### Stage 4 (Polars) — summary_stage4.json
| strategy | quality | cost_usd |
|---|---|---|
| full_context | 0.995 | 0.559 |
| meta_harness | 1.000 | 0.541 |
| rag_embedding | 1.000 | 0.165 |
| hierarchical | 0.995 | 0.138 |
| thin_harness | 0.955 | 0.305 |
| agent_managed | 0.905 | 0.290 |
| thick_harness | 0.810 | 0.772 |
| cascade_router | 1.000 | 0.291 |
| ensemble | 1.000 | 0.427 |

### Critical Design Issues Found

1. **N=10 per domain, 1 seed, 1 model** — cell resolution is 0.1; differences of 0.05 are within noise. No significance tests.

2. **Train ⊂ eval contamination** — meta_harness optimizer trains on questions[:4], evals on all 10. 4/10 cells are in-sample. Acknowledged in eval_runs.md but not corrected.

3. **Single LLM judge = agent model** — Claude Sonnet 4.6 judges its own outputs. Self-preference bias documented in literature. No human calibration, no inter-judge agreement.

4. **Synthetic corpus** — both domains are author-constructed. HR handbook is styled after GitLab but with synthetic Slack contradictions. Polars docs are real-ish but curated. No real-world messiness.

5. **Category distribution skew** — 40% slack_contradicts, 20% slack_only, 20% needs_both, 20% portal_only. Real queries would be 5-15% staleness. This inflates any strategy that handles contradictions well.

6. **Judge prompt leaks category** — `JUDGE_SYSTEM` says "For recency-sensitive questions (category == 'slack_contradicts' or key_facts mention a recent update), an answer that uses the stale handbook value instead of the recent Slack value should score <= 0.5." The judge sees the category label and is told how to score it. This is circular — it tests whether strategies surface Slack data, with a judge explicitly told to penalize not surfacing Slack data.

7. **Cost normalization inconsistency** — README table says cost in "× hier" but absolute numbers vary between stages and between README and eval docs. The Stage 4 README table shows "1.2×" for oracle but Stage 3 numbers.

8. **Prompt portability bug** — agent_managed system prompt hardcodes "New Hire Onboarding assistant". On Polars domain, agent refuses questions. This is a known bug (documented in stage4_polars_results.md) but is NOT fixed — it contaminates the Stage 4 agent_managed results.

9. **key_facts_recall is substring match** — `normalize(fact) in normalize(pred)` counts hits. Long verbose answers score higher by accident. F1 against long golden answers is structurally low (all strategies get 0.30-0.55 F1 because golden answers are 50-100 word paragraphs, model answers are 200+ words).

10. **No out-of-distribution questions** — every question has a relevant source. No test of refusal behavior on unanswerable questions.

11. **Meta-Harness positioning is misleading** — README says "not a faithful Meta-Harness port" in honest framing section, but the strategy is still named `meta_harness_optimized` in results tables, inviting comparison.

12. **Oracle router is not a real strategy** — it's a theoretical upper bound computed post-hoc. The README's headline claim "oracle router at 1.000 quality at ~5× cheaper" is comparing a non-deployable theoretical construct against actual strategies.

13. **Pareto frontier claims** — need to verify dominance relationships are correct given the data.

### Strengths Found
- Pre-registered predictions with honest falsification reporting (6/8 falsified)
- Extensive self-critique in eval_runs.md ("From Stage 3 to a real benchmark" checklist)
- Forensic failure-mode analysis is genuinely useful
- Two-domain comparison is the right instinct
- Clean code architecture with registry pattern
- YAML-driven suite spec is well-designed for extensibility
