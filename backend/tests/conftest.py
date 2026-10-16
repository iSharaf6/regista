"""Shared fixtures. The app (and its MCP session manager) can start only once per process, so tests share one client."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from regista.api.app import app

    with TestClient(app) as c:
        yield c
