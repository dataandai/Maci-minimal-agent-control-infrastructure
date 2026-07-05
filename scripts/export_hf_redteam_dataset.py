#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export an allowed subset of a Hugging Face dataset to JSONL for Maci red-team tests. "
            "Requires optional dependency: pip install datasets."
        )
    )
    parser.add_argument("--dataset", required=True, help="HF dataset name, e.g. rogue-security/prompt-injections-benchmark")
    parser.add_argument("--split", default="train")
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--text-field", default="text")
    parser.add_argument("--label-field", default="label")
    args = parser.parse_args()

    try:
        from datasets import load_dataset  # type: ignore
    except Exception as exc:  # pragma: no cover - optional external dependency
        raise SystemExit("Install optional dependency first: pip install datasets") from exc

    dataset = load_dataset(args.dataset, split=args.split)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for idx, row in enumerate(dataset):
            if idx >= args.limit:
                break
            text = row.get(args.text_field)
            label = row.get(args.label_field)
            if text is None:
                continue
            handle.write(json.dumps({"id": f"{args.dataset}:{args.split}:{idx}", "text": text, "label": label}, ensure_ascii=False) + "\n")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
