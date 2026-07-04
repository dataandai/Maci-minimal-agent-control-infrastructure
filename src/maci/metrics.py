from __future__ import annotations

import json
import os
import time
from typing import Any


def emit_metric(name: str, value: float, *, unit: str = "Count", dimensions: dict[str, str] | None = None, properties: dict[str, Any] | None = None) -> None:
    """Emit CloudWatch Embedded Metric Format JSON with local stdout fallback."""

    namespace = os.getenv("METRICS_NAMESPACE", "Maci")
    dims = dimensions or {}
    metric = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": namespace,
                    "Dimensions": [list(dims.keys())] if dims else [[]],
                    "Metrics": [{"Name": name, "Unit": unit}],
                }
            ],
        },
        name: value,
        **dims,
        **(properties or {}),
    }
    print(json.dumps(metric, sort_keys=True))
