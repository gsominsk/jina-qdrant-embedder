import asyncio
import time
import sys
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from fastapi import FastAPI

# Add app path to allow imports
sys.path.insert(0, "embeddings/app")

# Import the function and objects to be tested
from app import periodic_memory_cleanup, lifespan

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_app():
    """Fixture to create a mock FastAPI app with a state object."""
    app = FastAPI()
    app.state = MagicMock()
    app.state.last_activity_time = time.monotonic()
    return app

@patch('app.threading.Thread')
@patch('app.log_stats_periodically', new_callable=AsyncMock)
@patch('app.periodic_memory_cleanup', new_callable=AsyncMock) # Mock cleanup during startup
@patch('app.ctypes')
@patch('app.gc')
@patch('app.torch')
async def test_cleanup_not_triggered_when_active(mock_torch, mock_gc, mock_ctypes, mock_startup_cleanup, mock_log_stats, mock_thread):
    """
    Tests that aggressive cleanup is NOT triggered when the app is active.
    """
    # Setup mocks
    mock_libc = MagicMock()
    mock_ctypes.CDLL.return_value = mock_libc
    
    test_app = FastAPI()

    # Run startup via lifespan to initialize state
    async with lifespan(test_app):
        pass # Startup logic runs here

    # Run the REAL cleanup task for a short duration
    cleanup_task = asyncio.create_task(
        periodic_memory_cleanup(test_app, idle_threshold=10, check_interval=2)
    )
    
    # Simulate activity
    for i in range(5):
        await asyncio.sleep(1.5)
        test_app.state.last_activity_time = time.monotonic()
        print(f"Simulating activity at {test_app.state.last_activity_time}")

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Assert that malloc_trim was never called
    mock_libc.malloc_trim.assert_not_called()
    print("Test passed: malloc_trim was not called during active use.")


@patch('app.threading.Thread')
@patch('app.log_stats_periodically', new_callable=AsyncMock)
@patch('app.periodic_memory_cleanup', new_callable=AsyncMock) # Mock cleanup during startup
@patch('app.ctypes')
@patch('app.gc')
@patch('app.torch')
async def test_cleanup_triggered_when_idle(mock_torch, mock_gc, mock_ctypes, mock_startup_cleanup, mock_log_stats, mock_thread):
    """
    Tests that aggressive cleanup IS triggered when the app becomes idle.
    """
    # Setup mocks
    mock_libc = MagicMock()
    mock_ctypes.CDLL.return_value = mock_libc

    test_app = FastAPI()

    # Run startup via lifespan to initialize state
    async with lifespan(test_app):
       # Set activity time in the past AFTER state is initialized
       idle_threshold = 5
       test_app.state.last_activity_time = time.monotonic() - (idle_threshold + 1)

    # Run the REAL cleanup task once
    cleanup_task = asyncio.create_task(
        periodic_memory_cleanup(test_app, idle_threshold=idle_threshold, check_interval=1)
    )

    # Allow the task to run and perform the check
    await asyncio.sleep(1.5)

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Assert that malloc_trim was called
    mock_libc.malloc_trim.assert_called_once_with(0)
    print("Test passed: malloc_trim was called after idle period.")
