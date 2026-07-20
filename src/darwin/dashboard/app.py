import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from darwin.config import load_config
from darwin.risk.kill_switch import KillSwitch


def main() -> None:
    st.set_page_config(page_title="Darwin", layout="wide")
    st.title("Darwin")
    st.caption("Read-only prediction-market research and paper-trading dashboard.")
    config = load_config()
    report_dir = Path(os.getenv("DARWIN_REPORT_DIR", "reports/paper/mock-smoke"))
    if not (report_dir / "summary.json").exists():
        report_dir = Path("reports/backtests/sample")
    summary = _load_json(report_dir / "summary.json")
    cols = st.columns(4)
    cols[0].metric("Trading mode", config.execution.mode.value)
    cols[1].metric(
        "Kill switch", "active" if KillSwitch(config.risk.kill_switch_path).active() else "clear"
    )
    cols[2].metric("Cash", f"${summary.get('final_cash', 0):,.2f}")
    cols[3].metric("Net P&L", f"${summary.get('net_pnl', 0):,.4f}")
    st.info("Live-order actions are intentionally unavailable.")

    tabs = st.tabs(["Overview", "Live", "Markets", "Positions", "Backtests", "Risk"])
    with tabs[0]:
        st.caption(f"Report directory: {report_dir}")
        st.json(summary)
    with tabs[1]:
        st.subheader("Connection And Health")
        _table(report_dir / "health.csv")
        st.subheader("Metrics")
        _table(report_dir / "metrics.csv")
    with tabs[2]:
        st.subheader("Current Books")
        _table(report_dir / "books.csv")
        st.subheader("Latest Signals")
        _table(report_dir / "signals.csv")
    with tabs[3]:
        _table(report_dir / "positions.csv")
    with tabs[4]:
        _table(report_dir / "equity_curve.csv")
        _table(report_dir / "fills.csv")
    with tabs[5]:
        _table(report_dir / "orders.csv")
        _table(report_dir / "risk_decisions.csv")


def _load_json(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    raw: Any = json.loads(path.read_text())
    if not isinstance(raw, dict):
        return {}
    return {str(key): float(value) for key, value in raw.items() if isinstance(value, int | float)}


def _table(path: Path) -> None:
    st.subheader(path.name)
    if path.exists():
        st.dataframe(pd.read_csv(path), use_container_width=True)
    else:
        st.caption(f"No data at {path}")


if __name__ == "__main__":
    main()
