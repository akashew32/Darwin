import json
from pathlib import Path

import pandas as pd
import streamlit as st

from darwin.config import load_config
from darwin.risk.kill_switch import KillSwitch


def main() -> None:
    st.set_page_config(page_title="Darwin", layout="wide")
    st.title("Darwin")
    st.caption("Read-only prediction-market research and paper-trading dashboard.")
    config = load_config()
    report_dir = Path("reports/backtests/sample")
    summary = _load_json(report_dir / "summary.json")
    cols = st.columns(4)
    cols[0].metric("Trading mode", config.execution.mode.value)
    cols[1].metric("Kill switch", "active" if KillSwitch(config.risk.kill_switch_path).active() else "clear")
    cols[2].metric("Cash", f"${summary.get('final_cash', 0):,.2f}")
    cols[3].metric("Net P&L", f"${summary.get('net_pnl', 0):,.4f}")
    st.info("Live-order actions are intentionally unavailable.")

    tabs = st.tabs(["Overview", "Markets", "Positions", "Backtests", "Risk"])
    with tabs[0]:
        st.json(summary)
    with tabs[1]:
        _table(report_dir / "signals.csv")
    with tabs[2]:
        _table(report_dir / "positions.csv")
    with tabs[3]:
        _table(report_dir / "equity_curve.csv")
        _table(report_dir / "fills.csv")
    with tabs[4]:
        _table(report_dir / "risk_decisions.csv")


def _load_json(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _table(path: Path) -> None:
    st.subheader(path.name)
    if path.exists():
        st.dataframe(pd.read_csv(path), use_container_width=True)
    else:
        st.caption(f"No data at {path}")


if __name__ == "__main__":
    main()
