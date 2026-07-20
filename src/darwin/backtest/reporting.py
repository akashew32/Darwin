import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def write_outputs(output: Path, result: dict[str, Any], config_snapshot: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(result["summary"], indent=2, sort_keys=True))
    (output / "config_snapshot.yaml").write_text(yaml.safe_dump(config_snapshot, sort_keys=True))
    for key in [
        "trades",
        "orders",
        "fills",
        "signals",
        "equity_curve",
        "positions",
        "risk_decisions",
    ]:
        pd.DataFrame(result[key]).to_csv(output / f"{key}.csv", index=False)
    (output / "report.html").write_text(render_html_report(result["summary"]))


def render_html_report(summary: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<tr><th>{key}</th><td>{value}</td></tr>" for key, value in sorted(summary.items())
    )
    return f"""
<!doctype html>
<html>
<head><title>Darwin Backtest Report</title></head>
<body>
<h1>Darwin Backtest Report</h1>
<p>Results are historical simulation outputs, not a profitability guarantee.</p>
<table>{rows}</table>
</body>
</html>
"""
