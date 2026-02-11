from __future__ import annotations

import sys
from pathlib import Path

from streamlit.web import cli as stcli


if __name__ == "__main__":
    target = str((Path(__file__).parent / "web_app.py").resolve())
    sys.argv = ["streamlit", "run", target, "--server.headless", "true"]
    raise SystemExit(stcli.main())
