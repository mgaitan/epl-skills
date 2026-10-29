#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["pytest"]
# ///
"""Aislar todos los tests de credenciales reales heredadas del proceso."""

import pytest


@pytest.fixture(autouse=True)
def isolate_account_environment(monkeypatch):
    for name in ("EPL_USER", "EPL_PASS", "EPL_USERNAME", "EPL_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
