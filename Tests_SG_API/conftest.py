import os

import pytest


@pytest.fixture(autouse=True)
def _prevent_hard_exit(monkeypatch):
    """SG_main.exit() calls os._exit(0) on Windows; allow pytest to run the full suite."""
    monkeypatch.setattr(os, "_exit", lambda code=0: None)
