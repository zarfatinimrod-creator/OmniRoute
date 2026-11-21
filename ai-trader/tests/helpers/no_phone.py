"""Keeps a test run off the owner's phone (supervisor spec 11.1). Every new test module imports this first.

The import drops the phone variables from this process, as tests/test_core.py does when it is loaded. clean_env() is the
explicit environment of every process a test or a drill starts: no AITRADER_* variable, no proxy variable, and
NO_PROXY=127.0.0.1 so that a local stub is reached directly.
"""

import os
from pathlib import Path

PHONE_VARS = ("AITRADER_NTFY_TOPIC", "AITRADER_TELEGRAM_TOKEN", "AITRADER_TELEGRAM_CHAT")
for _var in PHONE_VARS:
    os.environ.pop(_var, None)


def clean_env(**extra: str) -> dict[str, str]:
    """PATH and HOME of this process, PYTHONPATH = the ai-trader folder, NO_PROXY=127.0.0.1, then extra. Nothing else."""
    env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
    return {**env, "PYTHONPATH": str(Path(__file__).resolve().parents[2]), "NO_PROXY": "127.0.0.1", **extra}
