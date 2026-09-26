#!/usr/bin/env python3
"""Explicit Experiment D entry point; no training unless --train is supplied."""

import argparse
import json

import train_qlora as core
from preflight_experiment_d import CONFIG, DRY_RUN_REPORT, OUTPUT, TRAIN, VALIDATION, check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-config",action="store_true",help="Static D input validation; no model")
    modes.add_argument("--dry-run",action="store_true",help="Tokenizer/chat only; no full model or training")
    modes.add_argument("--train",action="store_true",help="Train D after GPU and dry-run checks")
    args = parser.parse_args()
    report = check(local=not args.train)
    if report["errors"]:
        parser.exit(2,"Experiment D preflight failed: " + "; ".join(report["errors"]) + "\n")
    if args.check_config:
        print(json.dumps(report,indent=2))
        return 0
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    train_messages = core.load_messages(TRAIN)
    validation_messages = core.load_messages(VALIDATION)
    if args.dry_run:
        return core.dry_run(config,train_messages,validation_messages,
                            train_path=TRAIN,validation_path=VALIDATION,
                            output_root=OUTPUT,report_path=DRY_RUN_REPORT)
    core.require_completed_dry_run(DRY_RUN_REPORT,TRAIN,VALIDATION)
    return core.train(config,train_messages,validation_messages,smoke=False,
                      train_path=TRAIN,validation_path=VALIDATION,output_root=OUTPUT)


if __name__ == "__main__":
    raise SystemExit(main())
