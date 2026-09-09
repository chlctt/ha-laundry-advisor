"""Shared fixtures for the Home Assistant dependent tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Enable loading of the laundry_advisor custom integration in every test."""
    yield
