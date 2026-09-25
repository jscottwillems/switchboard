"""Local commands for the synthetic dataset and the scoring pipeline."""

import argparse
from pathlib import Path

from watson.dataset import default_dataset_path, default_report_path, load_dataset, prepare
from watson.evaluate import evaluate_dataset, render_markdown
from watson.pipeline import AssociationPipeline
from watson.synthetic import export_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="watson")
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="Score the synthetic dataset and write the evaluation report",
    )
    evaluate_parser.add_argument("--dataset", type=Path, default=None)
    evaluate_parser.add_argument("--report", type=Path, default=None)

    run_parser = subparsers.add_parser(
        "run",
        help="Ingest the synthetic dataset and print each association",
    )
    run_parser.add_argument("--dataset", type=Path, default=None)

    export_parser = subparsers.add_parser(
        "export-dataset",
        help="Write the synthetic dataset JSON from the builder",
    )
    export_parser.add_argument("--output", type=Path, default=None)

    args = parser.parse_args(argv)
    if args.command == "evaluate":
        return _evaluate(args.dataset, args.report)
    if args.command == "run":
        return _run(args.dataset)
    if args.command == "export-dataset":
        dataset = export_dataset(args.output)
        target = args.output or default_dataset_path()
        print(f"Wrote {len(dataset.calls)} calls to {target}")
        return 0
    parser.error(f"unknown command {args.command}")
    return 2


def _evaluate(dataset_path: Path | None, report_path: Path | None) -> int:
    dataset = load_dataset(dataset_path)
    report = evaluate_dataset(dataset)
    rendered = render_markdown(report)
    target = report_path or default_report_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    print(rendered)
    print(f"Wrote {target}")
    return 0


def _run(dataset_path: Path | None) -> int:
    runnable = prepare(load_dataset(dataset_path))
    pipeline = AssociationPipeline(intelligence=runnable.provider())
    truth = runnable.ground_truth()
    for call in runnable.calls():
        association = pipeline.ingest(call)
        print(
            f"{association.call_id} truth={truth[association.call_id]} "
            f"decision={association.decision.value} campaign={association.campaign_id} "
            f"score={association.association_score:.4f} "
            f"closest={association.matched_call_id or '-'}"
        )
        for reason in association.reasons:
            print(f"  - {reason}")
    return 0
