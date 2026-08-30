"""
Where insaight keeps its local state (SQLite DB, memory files, .env, config).

Resolution order for the home directory:
  1. INSAIGHT_HOME env var
  2. <repo>/data if it exists (developer checkout — keeps old layouts working)
  3. ~/.insaight (default for packaged / uvx installs)
"""

import os
from pathlib import Path

_REPO_DATA = Path(__file__).parent.parent / "data"


def home() -> Path:
    env = os.environ.get("INSAIGHT_HOME", "")
    if env:
        return Path(env).expanduser()
    if _REPO_DATA.is_dir():
        return _REPO_DATA
    return Path.home() / ".insaight"


def ensure_home() -> Path:
    h = home()
    h.mkdir(parents=True, exist_ok=True)
    return h
