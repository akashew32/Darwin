import streamlit as st


def main() -> None:
    st.set_page_config(page_title="Darwin", layout="wide")
    st.title("Darwin")
    st.caption("Read-only prediction-market research and paper-trading dashboard.")
    cols = st.columns(4)
    cols[0].metric("Trading mode", "paper")
    cols[1].metric("Kill switch", "clear")
    cols[2].metric("Cash", "$0.00")
    cols[3].metric("Daily P&L", "$0.00")
    st.info("Live-order actions are intentionally unavailable in this initial dashboard.")


if __name__ == "__main__":
    main()
