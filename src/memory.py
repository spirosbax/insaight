"""
Persistent outreach memory — two distilled Markdown files that the
draft-outreach skill reads instead of re-deriving style from raw history
every session.

  data/memory/style.md    — the user's voice: hooks, tone, length, tics
  data/memory/playbook.md — what gets replies: strategies with evidence counts

Both files are rewritten by the insaight-reflect skill (with user approval),
never silently. They live under data/ so they stay local and gitignored.
"""

import os
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "data" / "memory"


def _default_memory_dir() -> Path:
    """INSAIGHT_MEMORY_DIR env var overrides the default data/memory location."""
    env = os.environ.get("INSAIGHT_MEMORY_DIR", "")
    return Path(env) if env else MEMORY_DIR

_KINDS = ("style", "playbook")

DEFAULT_STYLE = """\
# Outreach style guide

*Not learned yet. Log a few outreach messages (insaight-track-outreach),
then run insaight-reflect to distill your voice from real sends.*
"""

DEFAULT_PLAYBOOK = """\
# Outreach playbook — what gets replies

*No evidence yet. Every entry in this file must carry its evidence
(e.g. "question hooks: 4/9 replied vs statement hooks: 1/8 — small n,
keep testing"). Low-n patterns are hypotheses, not rules.*
"""

_DEFAULTS = {"style": DEFAULT_STYLE, "playbook": DEFAULT_PLAYBOOK}


def _path(kind: str, memory_dir: Path | None = None) -> Path:
    if kind not in _KINDS:
        raise ValueError(f"Unknown memory kind '{kind}'. Expected one of {_KINDS}.")
    return (memory_dir or _default_memory_dir()) / f"{kind}.md"


def read_memory(kind: str, memory_dir: Path | None = None) -> str:
    """Return the memory file content, or the default scaffold if not written yet."""
    path = _path(kind, memory_dir)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return _DEFAULTS[kind]


def write_memory(kind: str, content: str, memory_dir: Path | None = None) -> Path:
    """Write a memory file, creating the directory if needed. Returns the path."""
    path = _path(kind, memory_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def is_learned(kind: str, memory_dir: Path | None = None) -> bool:
    """True once the file has actually been written (vs default scaffold)."""
    return _path(kind, memory_dir).exists()
