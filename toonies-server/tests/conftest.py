import asyncio
import pytest
from toonies_server.state.store import AppState


@pytest.fixture
def state():
    return AppState()


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
