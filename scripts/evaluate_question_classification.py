#!/usr/bin/env python3
"""Evaluate independently labelled Math 9 chapter-6 questions from JSON."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.classification_evaluation import evaluate


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('labels', help='JSON array of labelled rows')
    parser.add_argument('--output', help='Write the JSON report to this path')
    parser.add_argument('--min-labeled-rows', type=int, default=240)
    parser.add_argument('--min-pair-accuracy', type=float, default=.95)
    args = parser.parse_args()
    rows = json.loads(Path(args.labels).read_text(encoding='utf-8'))
    if not isinstance(rows, list):
        raise SystemExit('File nhãn phải là một mảng JSON.')
    report = evaluate(rows, dict(min_labeled_rows=args.min_labeled_rows, min_pair_accuracy=args.min_pair_accuracy))
    output = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(output + '\n', encoding='utf-8')
    print(output)
