"""Pytest configuration and fixtures for AP Workflow Agent tests."""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Set up environment variables for testing
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/ap_workflow_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "true")
