#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maci.redteam import OfficialDatasetName  # noqa: E402


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _read_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("data", "rows", "examples", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"Could not find a list of records in {path}")


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_local(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _read_jsonl(path)
    if suffix == ".json":
        return _read_json(path)
    if suffix == ".csv":
        return _read_csv(path)
    raise ValueError(f"Unsupported local format: {path}")


def _load_url(url: str, cache_path: Path) -> list[dict[str, Any]]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - operator-provided dataset URL
        cache_path.write_bytes(response.read())
    return _load_local(cache_path)


def _load_hf(dataset: str, split: str | None, config: str | None, max_cases: int | None) -> list[dict[str, Any]]:
    try:
        from datasets import load_dataset  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise SystemExit("Hugging Face export requires: pip install -e '.[evals]'") from exc
    kwargs: dict[str, Any] = {}
    if split:
        kwargs["split"] = split
    if config:
        ds = load_dataset(dataset, config, **kwargs)
    else:
        ds = load_dataset(dataset, **kwargs)
    if not split and isinstance(ds, dict):
        first_key = "train" if "train" in ds else next(iter(ds.keys()))
        ds = ds[first_key]
    if max_cases:
        ds = ds.select(range(min(max_cases, len(ds))))
    return [dict(row) for row in ds]


def _first(row: dict[str, Any], fields: Iterable[str]) -> Any | None:
    for field in fields:
        if field and field in row and row[field] not in (None, ""):
            return row[field]
    return None


def _expected_action(row: dict[str, Any], label_field: str | None, benign_values: set[str], attack_values: set[str], default: str) -> str:
    value = row.get("expected_action")
    if value in {"intervene", "allow"}:
        return value
    if label_field:
        value = row.get(label_field)
        if isinstance(value, bool):
            return "intervene" if value else "allow"
        if isinstance(value, (int, float)):
            return "intervene" if int(value) == 1 else "allow"
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in benign_values:
                return "allow"
            if normalized in attack_values:
                return "intervene"
    return default


def main() -> int:
    parser = argparse.ArgumentParser(description="Export public red-team/eval datasets into Maci normalized JSONL.")
    parser.add_argument("--source", choices=("hf", "local", "url"), required=True)
    parser.add_argument("--input", help="Local JSONL/JSON/CSV path for --source local")
    parser.add_argument("--url", help="JSONL/JSON/CSV URL for --source url")
    parser.add_argument("--hf-dataset", help="Hugging Face dataset name, e.g. JailbreakBench/JBB-Behaviors")
    parser.add_argument("--hf-config", default="")
    parser.add_argument("--split", default="")
    parser.add_argument("--text-field", default="payload,text,prompt,attack,goal,behavior,instruction,input,query,content")
    parser.add_argument("--label-field", default="label")
    parser.add_argument("--id-field", default="id,idx,sample_id,behavior_id")
    parser.add_argument("--dataset-name", choices=[item.value for item in OfficialDatasetName], default="generic_jsonl")
    parser.add_argument("--channel", default="user_input")
    parser.add_argument("--category", default="direct_prompt_injection")
    parser.add_argument("--default-action", choices=("intervene", "allow"), default="intervene")
    parser.add_argument("--benign-values", default="benign,safe,clean,0,false")
    parser.add_argument("--attack-values", default="jailbreak,attack,injection,malicious,unsafe,1,true")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    max_cases = args.max_cases or None
    if args.source == "hf":
        if not args.hf_dataset:
            parser.error("--hf-dataset is required for --source hf")
        rows = _load_hf(args.hf_dataset, args.split or None, args.hf_config or None, max_cases)
    elif args.source == "url":
        if not args.url:
            parser.error("--url is required for --source url")
        rows = _load_url(args.url, ROOT / "evals/redteam/.cache/downloaded_dataset")
    else:
        if not args.input:
            parser.error("--input is required for --source local")
        rows = _load_local(Path(args.input))

    text_fields = tuple(item.strip() for item in args.text_field.split(",") if item.strip())
    id_fields = tuple(item.strip() for item in args.id_field.split(",") if item.strip())
    benign_values = {item.strip().lower() for item in args.benign_values.split(",") if item.strip()}
    attack_values = {item.strip().lower() for item in args.attack_values.split(",") if item.strip()}

    out_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        payload = row.get("payload") if isinstance(row.get("payload"), (str, dict)) else _first(row, text_fields)
        if payload is None:
            continue
        case_id = str(_first(row, id_fields) or f"{args.dataset_name}-{idx:05d}")
        out_rows.append({
            "case_id": case_id,
            "source_record_id": case_id,
            "source_dataset": args.dataset_name,
            "payload": payload,
            "channel": row.get("channel", args.channel),
            "category": row.get("category", args.category),
            "expected_action": _expected_action(row, args.label_field or None, benign_values, attack_values, args.default_action),
            "description": row.get("description", f"Exported from {args.dataset_name}"),
        })
        if max_cases and len(out_rows) >= max_cases:
            break

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in out_rows) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "records": len(out_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
