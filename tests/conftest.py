"""
Shared pytest fixtures.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

SAMPLE_DIR = Path(__file__).parent / "sample_files"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


@pytest.fixture
def sample_txt_path() -> str:
    return str(SAMPLE_DIR / "sample_regulation.txt")


@pytest.fixture
def sample_pdf_path() -> str:
    return str(SAMPLE_DIR / "sample_regulation.pdf")
