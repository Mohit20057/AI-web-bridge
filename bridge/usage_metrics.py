"""Optional local comparison of token counts reported by a coding CLI."""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


TOKEN_FIELDS = (
    "baseline_input_tokens",
    "baseline_output_tokens",
    "bridge_input_tokens",
    "bridge_output_tokens",
)


def record_usage_sample(path: Path, task_label: str, counts: dict[str, int]) -> dict:
    label = " ".join(task_label.split())
    if not label:
        raise ValueError("A short task label is required for a usage sample.")
    clean = {}
    for field in TOKEN_FIELDS:
        value = counts.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field} must be a non-negative integer reported by your CLI.")
        clean[field] = value
    baseline = clean["baseline_input_tokens"] + clean["baseline_output_tokens"]
    bridge = clean["bridge_input_tokens"] + clean["bridge_output_tokens"]
    if baseline == 0:
        raise ValueError("Baseline token total must be greater than zero.")
    record = {
        "version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_label": label[:80],
        **clean,
        "baseline_total_tokens": baseline,
        "bridge_total_tokens": bridge,
        "tokens_saved": baseline - bridge,
        "reduction_percent": round((baseline - bridge) * 100 / baseline, 2),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def summarize_usage(path: Path) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid usage record on line {line_number} in {path}.") from exc
        if not isinstance(row, dict) or any(not isinstance(row.get(field), int) for field in TOKEN_FIELDS):
            raise ValueError(f"Invalid usage record on line {line_number} in {path}.")
        grouped[str(row.get("task_label") or "(unlabelled)")].append(row)
    summaries = []
    for label, rows in sorted(grouped.items()):
        baseline = sum(row["baseline_input_tokens"] + row["baseline_output_tokens"] for row in rows)
        bridge = sum(row["bridge_input_tokens"] + row["bridge_output_tokens"] for row in rows)
        summaries.append({
            "task_label": label,
            "samples": len(rows),
            "baseline_total_tokens": baseline,
            "bridge_total_tokens": bridge,
            "tokens_saved": baseline - bridge,
            "reduction_percent": round((baseline - bridge) * 100 / baseline, 2) if baseline else 0.0,
        })
    return summaries
