"""Run the offline LOKI evaluation from the command line."""

import sys

from switchboard.loki.eval.harness import format_report, run_evaluation


def main() -> None:
    report = run_evaluation()
    sys.stdout.write(format_report(report))
    sys.exit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
