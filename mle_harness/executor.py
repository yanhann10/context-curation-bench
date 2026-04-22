"""Docker sandbox + agent orchestration for mle-bench harness ablation.

One entry per (competition, harness) cell:
  1. harness_fn produces Python code (single-shot) OR drives a tool-use loop
  2. Python code runs in `mlebench-env` Docker container with data mounted RO
  3. On success we look for /workspace/submission.csv; grade it via `mlebench
     grade-sample`
  4. Emit a CellResult dict

Kept deliberately minimal: no multi-iteration revise loop for v1, no GPU.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path


CACHE = Path(os.path.expanduser("~/.cache/mle-bench/data"))
VENV_PY = Path(os.path.expanduser("~/mle-bench-run/.venv/bin/python"))
MLEBENCH = Path(os.path.expanduser("~/mle-bench-run/.venv/bin/mlebench"))


@dataclass
class CellResult:
    competition: str
    harness: str
    submitted: bool
    score: float | None
    medal: str | None           # none | bronze | silver | gold
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    wall_time_s: float
    code_chars: int
    docker_exit: int
    docker_timeout: bool
    error: str


def _public_dir(comp_id: str) -> Path:
    return CACHE / comp_id / "prepared" / "public"


def _private_test(comp_id: str) -> Path:
    return CACHE / comp_id / "prepared" / "private" / "test.csv"


def run_code_in_docker(code: str, public_dir: Path, timeout_s: int = 600) -> dict:
    """Run code in mlebench-env with read-only public/ mount.

    Returns {exit_code, stdout, stderr, submission_path_or_none, timed_out}.
    """
    work = Path(tempfile.mkdtemp(prefix="xcmle_"))
    try:
        (work / "solution.py").write_text(code, encoding="utf-8")
        cmd = [
            "sudo", "docker", "run", "--rm",
            "--network=none",
            "-v", f"{public_dir}:/data/public:ro",
            "-v", f"{work}:/workspace",
            "-w", "/workspace",
            "--memory=3g",
            "--entrypoint", "/opt/conda/envs/mleb/bin/python",
            "mlebench-env",
            "solution.py",
        ]
        t0 = time.time()
        try:
            p = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
            )
            timed_out = False
            exit_code = p.returncode
            stdout, stderr = p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            subprocess.run(["sudo", "docker", "ps", "-q", "--filter", "ancestor=mlebench-env"],
                           capture_output=True)
            timed_out = True
            exit_code = -1
            stdout = e.stdout.decode() if e.stdout else ""
            stderr = (e.stderr.decode() if e.stderr else "") + "\n[TIMEOUT]"
        elapsed = time.time() - t0

        sub = work / "submission.csv"
        sub_saved = None
        if sub.exists():
            final = work.parent / f"submission_{work.name}.csv"
            shutil.copy(sub, final)
            sub_saved = str(final)

        return {
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
            "submission_path": sub_saved,
            "wall_s": elapsed,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def grade_submission(submission_path: str, comp_id: str) -> tuple[float | None, str | None, str]:
    """Return (score, medal, raw_grader_json_or_err)."""
    try:
        p = subprocess.run(
            [str(MLEBENCH), "grade-sample", submission_path, comp_id],
            capture_output=True, text=True, timeout=120,
        )
        raw = (p.stdout + "\n" + p.stderr).strip()
    except Exception as e:
        return None, None, f"grader-error: {e}"

    try:
        m = re.search(r"\{[\s\S]*?\n\}", raw)
        if m:
            data = json.loads(m.group(0))
            score = data.get("score")
            if score is not None:
                score = float(score)
            medal = None
            for k in ("gold_medal", "silver_medal", "bronze_medal"):
                if data.get(k):
                    medal = k.split("_")[0]
                    break
            return score, medal, raw[-1500:]
    except Exception:
        pass
    return None, None, raw[-1500:]


async def _revise_on_error(ctx, comp_id, public_dir, prior_code, stderr):
    """One-shot revise: show Claude the broken code + traceback, ask for fix."""
    from mle_harness.harnesses import _client, _generate, SYSTEM, _cost
    user = (
        f"# Competition: {comp_id}\n"
        f"Your previous code failed in the mlebench-env container (sklearn 1.8, pandas 3.0). "
        f"Return the FIXED Python code in a ```python fenced block. No prose.\n\n"
        f"## Previous code\n```python\n{prior_code[:3000]}\n```\n\n"
        f"## stderr (last 1500 chars)\n```\n{stderr[-1500:]}\n```\n\n"
        f"Common fixes: sklearn 1.8 removed `multi_class` param from LogisticRegression "
        f"(use default), changed some imports. Use modern API only."
    )
    client = _client()
    return await _generate(client, SYSTEM, user)


def run_cell(
    comp_id: str,
    harness_name: str,
    harness_fn,
    *,
    timeout_s: int = 600,
    ctx: dict | None = None,
) -> CellResult:
    """Execute one (competition, harness) cell end-to-end.

    harness_fn signature: async fn(ctx, competition_id, public_dir) -> {code, prompt_tokens, completion_tokens, cost_usd}
    """
    import asyncio

    ctx = ctx or {}
    public_dir = _public_dir(comp_id)
    if not public_dir.exists():
        return CellResult(
            competition=comp_id, harness=harness_name,
            submitted=False, score=None, medal=None,
            prompt_tokens=0, completion_tokens=0, cost_usd=0,
            wall_time_s=0, code_chars=0, docker_exit=0,
            docker_timeout=False, error=f"public_dir missing: {public_dir}",
        )

    t0 = time.time()
    try:
        gen = asyncio.run(harness_fn(ctx, comp_id, public_dir))
    except Exception as e:
        return CellResult(
            competition=comp_id, harness=harness_name,
            submitted=False, score=None, medal=None,
            prompt_tokens=0, completion_tokens=0, cost_usd=0,
            wall_time_s=time.time() - t0, code_chars=0,
            docker_exit=0, docker_timeout=False,
            error=f"harness-error: {e}",
        )

    code = gen.get("code", "")
    if not code:
        return CellResult(
            competition=comp_id, harness=harness_name,
            submitted=False, score=None, medal=None,
            prompt_tokens=gen.get("prompt_tokens", 0),
            completion_tokens=gen.get("completion_tokens", 0),
            cost_usd=gen.get("cost_usd", 0.0),
            wall_time_s=time.time() - t0, code_chars=0,
            docker_exit=0, docker_timeout=False,
            error="harness produced empty code",
        )

    exec_result = run_code_in_docker(code, public_dir, timeout_s=timeout_s)

    # One revise-on-error round: if code failed or no submission, feed traceback back.
    if not exec_result["submission_path"] and ctx.get("revise_on_error", True):
        revise_gen = asyncio.run(_revise_on_error(
            ctx, comp_id, public_dir, code, exec_result["stderr"],
        ))
        gen["prompt_tokens"] += revise_gen.get("prompt_tokens", 0)
        gen["completion_tokens"] += revise_gen.get("completion_tokens", 0)
        gen["cost_usd"] += revise_gen.get("cost_usd", 0.0)
        revised_code = revise_gen.get("code", "")
        if revised_code:
            code = revised_code
            exec_result = run_code_in_docker(code, public_dir, timeout_s=timeout_s)

    score, medal, raw = (None, None, "")
    if exec_result["submission_path"]:
        score, medal, raw = grade_submission(exec_result["submission_path"], comp_id)

    return CellResult(
        competition=comp_id, harness=harness_name,
        submitted=exec_result["submission_path"] is not None,
        score=score, medal=medal,
        prompt_tokens=gen.get("prompt_tokens", 0),
        completion_tokens=gen.get("completion_tokens", 0),
        cost_usd=gen.get("cost_usd", 0.0),
        wall_time_s=time.time() - t0,
        code_chars=len(code),
        docker_exit=exec_result["exit_code"],
        docker_timeout=exec_result["timed_out"],
        error=(exec_result["stderr"][-400:] if exec_result["exit_code"] != 0 else raw[:400]),
    )
