#!/usr/bin/env python3
"""Run the separate, pinned Experiment B setup after explicit preflight."""

import argparse
import json

import train_qlora as core
from preflight_experiment_b import CONFIG, OUTPUT, TRAIN, VALIDATION, check


DRY_RUN_REPORT = core.HERE / "dry_run_experiment_b.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-config", action="store_true", help="Check static B config and frozen hashes only")
    modes.add_argument("--dry-run", action="store_true", help="Format combined dataset with the pinned tokenizer; no model load")
    modes.add_argument("--train", action="store_true", help="Run Experiment B on Lightning after all checks pass")
    args = parser.parse_args()
    report = check(local=not args.train)
    if report["errors"]:
        parser.exit(2, "Experiment B preflight failed: " + "; ".join(report["errors"]) + "\n")
    if args.check_config:
        print(json.dumps(report, indent=2))
        return 0
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    train_messages = core.load_messages(TRAIN)
    validation_messages = core.load_messages(VALIDATION)
    if args.dry_run:
        return core.dry_run(config, train_messages, validation_messages,
                            train_path=TRAIN, validation_path=VALIDATION,
                            output_root=OUTPUT, report_path=DRY_RUN_REPORT)
    core.require_completed_dry_run(DRY_RUN_REPORT, TRAIN, VALIDATION)
    return core.train(config, train_messages, validation_messages, smoke=False,
                      train_path=TRAIN, validation_path=VALIDATION, output_root=OUTPUT)


if __name__ == "__main__":
    raise SystemExit(main())
