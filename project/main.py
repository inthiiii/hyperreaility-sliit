from pathlib import Path
import platform

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

st.set_page_config(page_title="RE:L!NK", page_icon="📡", layout="wide")
st.title("RE:L!NK")
st.caption("Restore connectivity. Coordinate recovery.")
st.success("Development environment is running.")
st.info("Environment setup only. Planning, agents, data loading and simulation are not implemented yet.")
st.subheader("Development environment")
st.write({"Python": platform.python_version(), "Project folder": str(ROOT), "Execution": "Local development"})
st.subheader("Next implementation steps")
st.markdown("""
1. Publish shared Pydantic schemas.
2. Connect Zahra's validated scenario loader.
3. Implement scheduling and independent validation.
4. Connect the dashboard and approval workflow.
5. Add hosted-model reasoning and agent coordination.
""")
