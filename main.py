"""Redirect shim. The entry point is now the `xcbench` package.

  python -m xcbench demo      # run the bundled sample suite end-to-end
  python -m xcbench run SUITE # run a specific suite YAML
  python -m xcbench --help

The original Stage-1 driver lives in git history (this file was the
Stage-1 hard-coded pipeline before the xcbench CLI). Stage-2 and Stage-3
drivers live under legacy/ and still work with --skip-optimize etc.
"""
import sys

MSG = (
    "\nThis script has been superseded by the `xcbench` CLI.\n\n"
    "  python -m xcbench demo                                  # bundled sample suite\n"
    "  python -m xcbench run suites/sample_data_hr_policy.yaml # same, explicit\n"
    "  python -m xcbench run examples/toy/suite.yaml           # minimal 3-doc example\n"
    "  python -m xcbench --help\n"
)

if __name__ == "__main__":
    print(MSG, file=sys.stderr)
    sys.exit(2)
