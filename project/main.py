"""Required application entry point: python -m streamlit run project/main.py"""
import sys
from pathlib import Path

# Allow `streamlit run project/main.py` as well as `python -m streamlit run ...`.
ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from project.ui.app import render_app  # noqa: E402

render_app()
