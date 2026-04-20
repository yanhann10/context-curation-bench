"""Redirect shim. The entry point is now the `xcbench` package.

  python -m xcbench demo      # run the bundled sample suite end-to-end
  python -m xcbench run SUITE # run a specific suite YAML
  python -m xcbench --help

Earlier versions of this file held an inline driver; that history is in
git. All current runs go through the `xcbench` CLI + a suite YAML.
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
