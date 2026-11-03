"""AI-Powered Customer Sales Analytics Platform.

Root Streamlit entry point. Delegates to the dashboard package so that
``streamlit run app.py`` launches the full application.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
_entry = str(PROJECT_ROOT)
if _entry in sys.path:
    sys.path.remove(_entry)
sys.path.insert(0, _entry)

from dashboard.app import main  # noqa: E402

if __name__ == "__main__":
    main()
