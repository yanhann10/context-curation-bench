# readme_staging.md — Phase A plan for faithful Meta-Harness comparison

**Status:** design review, not yet executed. This document exists so the user can sign off on scope, cost, and timeline before any AWS spend.

Promotion rule: once Phases A → C are complete and results exist, this document is either merged into `README.md` (successful comparison) or deleted with a one-paragraph postmortem in `notes/` (null result or blocker).

---

## 1. What we're comparing, precisely

**Goal:** run the real [stanford-iris-lab/meta-harness](https://github.com/stanford-iris-lab/meta-harness) framework against an xcbench-defined context-curation task, and put its final numbers in the same trade-off table as the 9 existing strategies (`full_context`, `rag_embedding`, `hierarchical`, `agent_managed`, `cascade_router`, `ensemble`, `meta_harness_optimized` (the in-house simplification), `compressed`, `curation_difficulty`).

**Not the goal:**
- Reproducing Meta-Harness's Terminal-Bench 2.0 76.4% headline. That's a different domain (agentic coding shell tasks), different base model, and out of scope.
- Claiming we "ported" Meta-Harness. We'd be running *their* code against *our* task adapter.

**The comparison we want to land on:**

| strategy | quality | latency (× hier) | cost (× hier) |
|---|---|---|---|
| … 9 existing xcbench strategies … | | | |
| **meta_harness_faithful** (new) | ? | ? | ? |

If faithful Meta-Harness beats our typed-CurationSpec simplification at comparable or better cost, the `## Simplification` section of README.md needs a direct caveat. If it ties or loses, the simplification is vindicated and the README can say so.

---

## 2. What "faithful" requires us to build (the unavoidable ~8–16 hr integration)

From `notes/meta_harness_analysis.md` §3 and the h_wiki [Meta-Harness page](../Documents/h_wiki/wiki/topics/meta-harness-stanford-iris-2026.md). Non-negotiable coupling points we'd have to adapt:

| Coupling point | What it assumes | What we'd need to build |
|---|---|---|
| **Proposer transport** | `claude` CLI + subscription auth + MCP skills dir; loop strips `ANTHROPIC_API_KEY` before invoking CLI | Install `claude` CLI on the VM, log in with subscription auth, mount `.claude/skills/meta-harness/SKILL.md` |
| **Harness interface** | `MemorySystem` ABC: `predict(input) → (answer, meta)`, `learn_from_batch`, `get_state/set_state`, offline/online mode switch | Write a `CurationHarness(MemorySystem)` shim that wraps xcbench's `(question, corpus) → answer` into their ABC. Online mode is irrelevant for our task — run offline only. |
| **Dataset loader** | HuggingFace-style splits under `data/`, names hardcoded in `config.yaml` | Adapter that serves xcbench questions (HR-policy, Polars, Flask, or ConflictQA) as a faux HF dataset with `train/val/test` splits. Pick **one suite** for the first run — ConflictQA (N=120) is the best fit because it has enough questions for a real train/val/test split. |
| **Scorer** | Classification accuracy over multiple datasets, Pareto over (accuracy, context_length) | Replace with LLM-as-judge (already in xcbench as `judge.py`). Wire into `benchmark.py`'s scoring hook. Preserve their Pareto frontier bookkeeping — it's useful. |
| **Filesystem layout** | `logs/<run>/{pending_eval,frontier_val,evolution_summary,claude_sessions,reports}`; `SKILL.md` hardcodes these paths | Either match their layout exactly or rewrite `SKILL.md` — easier to match layout. |
| **Proposer prior** | `.claude/skills/meta-harness/SKILL.md` — hundreds of lines of domain-specific guidance for the text-classification example | Re-author for context-curation. This is the single most domain-specific piece of work. |
| **Leakage discipline** | test split only touched once at the end | Enforce in our adapter. The proposer must never see held-out questions. |

**Honest hour estimate** (copied from the existing analysis; tracks the h_wiki note):
- uv project + `claude` CLI auth + xcbench dataset adapter: 1.5 hr
- `CurationHarness(MemorySystem)` shim: 1 hr
- LLM-as-judge scorer wired into `benchmark.py`: 1.5 hr
- Re-authored `SKILL.md` for context-curation mutations: 2 hr
- Debug first end-to-end iteration (their README: "has not been tested beyond verifying that it runs"): 2+ hr
- **Subtotal: 8–12 hrs minimum, realistically 16.**

This is not an overnight unattended run. It's a two-to-three-day human-in-the-loop integration followed by an overnight search run.

---

## 3. VM sizing and compute cost

**VM:** t3.large minimum (2 vCPU, 8 GB). Meta-Harness holds Python environments, runs `claude` subprocesses, keeps filesystem logs. The existing `~/.ssh` micro-VM entry in memory is a t2.micro/t3.micro and will not fit.

Estimates (on-demand, us-east-1):
- t3.large: ~$0.083/hr → **~$0.67 for an 8 hr overnight run**
- t3.xlarge (safer headroom): ~$0.166/hr → **~$1.33 overnight**

Do NOT use spot — the search loop writes stateful JSONL history and a preempt would lose it.

**API cost (the dominant term):**
- Paper's text-classification run: ~20 iterations × 2 candidates/iter = 40 candidates
- Per candidate: eval on val split (~50 items × 1 answer call + 1 judge call) ≈ 100 API calls
- Per iteration proposer call: 1 call on Claude Opus CLI (subscription auth, not billed per-token if account is active)
- Total per-token API calls: ~40 × 100 = 4,000 eval calls

At Claude Sonnet 4.6 agent + Opus 4.7 judge pricing, with ConflictQA context sizes (~5k prompt tokens average):
- 4,000 × (5k prompt @ $3/MTok + 0.2k completion @ $15/MTok) ≈ 4,000 × $0.018 ≈ **$72**
- Judge adds ~$40
- **Total API: ~$110, plausibly up to $200 if iterations run longer or contexts are larger**

Proposer calls via `claude` CLI with subscription auth: metered against Max plan usage, not pay-per-token. If proposer hits the plan's cap mid-run the search stalls — worth checking the plan's current headroom before kickoff.

**Total Phase B overnight cost: ~$1 VM + ~$100–200 API ≈ $100–$200.**

---

## 4. Success criteria

**Primary:** produce one new row in the xcbench trade-off table — `meta_harness_faithful` with quality, latency, cost on the chosen suite (ConflictQA preferred). Held-out test split, never seen by proposer.

**Interpretation gate:**
- If faithful ≥ simplification by > 0.05 quality → update `## Simplification` to say "the simplification costs ~X quality points vs the faithful loop"
- If faithful ≈ simplification (|Δ| ≤ 0.05) → the simplification section stays; add one sentence confirming the loop's core value is the idea, not the Python-code-mutation freedom
- If faithful < simplification → interesting. Likely means the proposer over-mutates on small N; document as a Meta-Harness failure mode for context curation specifically.

**Anti-goals (things we will NOT claim):**
- No "faithful reproduction of Terminal-Bench 2.0 numbers"
- No Pareto claim unless we measure at ≥ 3 iterations and see a front actually move
- No significance claim (single-seed — same caveat as rest of xcbench)

---

## 5. Phase breakdown

### Phase A (this document — no compute)
- [x] Scope spec (this file)
- [ ] User sign-off on scope, cost, chosen suite
- [ ] Confirm `claude` CLI subscription auth availability (Max plan headroom check)

### Phase B — integration on a branch
All work on a new branch `faithful-metaharness`, never touches main until Phase C.
- [ ] `git checkout -b faithful-metaharness`
- [ ] Clone `stanford-iris-lab/meta-harness` into `external/meta-harness/` (gitignored, fetched locally)
- [ ] Build `xcbench_adapter/` with:
  - `dataset.py` — serve chosen xcbench suite as HF-style splits with explicit train/val/test
  - `curation_harness.py` — `MemorySystem` subclass wrapping xcbench's answer path
  - `scorer.py` — hook xcbench's LLM-as-judge into `benchmark.py`
  - `skill/SKILL.md` — re-authored proposer prior for context-curation mutations
- [ ] Local sanity check: 1 iteration × 1 candidate on laptop, 5 val items, verify a candidate gets written, scored, logged
- [ ] Commit the adapter, push to `faithful-metaharness`

### Phase B.5 — overnight run
- [ ] Spin up t3.large EC2 (on-demand, not spot)
- [ ] Clone repo, install deps, install `claude` CLI, log in
- [ ] Run `python meta_harness.py --n-iter 15 --config xcbench_conflictqa.yaml` inside `tmux` or `nohup`
- [ ] Morning: pull `logs/<run>/` back to laptop, run xcbench evaluation harness on the final frontier candidates against held-out test split
- [ ] **Stop the VM before doing analysis.** (cost-discipline per memory)

### Phase C — promote or postmortem
- [ ] If comparison clean: merge branch → add `meta_harness_faithful` row to `## Historical N=108 results` (or create a new `## Faithful Meta-Harness comparison` H2 section), update `## Simplification` to reference the delta
- [ ] If comparison null/blocked: write `notes/meta_harness_faithful_postmortem.md`, delete `readme_staging.md`, do not touch main README claims

---

## 6. Decisions needed from user before Phase B starts

1. **Which suite?** ConflictQA (N=120, synthesis-heavy, explicit conflicts — best fit for a proposer-driven search). Alternative: HR-policy (N=10, too small for a real train/val/test split; not recommended).
2. **Max plan headroom for the proposer.** If the Claude Max plan is already near cap this month, we either wait until reset or swap the proposer to `anthropic.Anthropic()` SDK calls (departs from faithful at one coupling point — document as a deviation).
3. **Go / no-go on ~$100–$200 API spend plus 8–16 hrs integration time.**
4. **Who drives Phase B integration?** If Claude (me), it'll need several turns with test execution. If user does it solo, this doc is the handoff.

---

## 7. Teardown checklist (end of Phase B.5)

- [ ] `aws ec2 stop-instances --instance-ids <id>` (stop, not terminate — keep EBS for logs)
- [ ] Pull `logs/<run>/`, `frontier_val.json`, final candidate `.py` files to laptop
- [ ] After analysis: `aws ec2 terminate-instances --instance-ids <id>`, verify EBS released
- [ ] Log cost totals in `eval/eval_runs.md`
- [ ] Commit artifacts under `external/meta-harness-runs/<date>/` (gitignored heavy files, committed summary)
