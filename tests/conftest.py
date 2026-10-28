"""Pytest configuration and common fixtures."""

import os
import sys
import pytest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set test environment
os.environ["JARVIS_ENV"] = "test"
os.environ["JARVIS_SECRET_KEY"] = "test_secret_key_32_bytes_long_ok"
