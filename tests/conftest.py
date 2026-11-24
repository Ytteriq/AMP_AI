"""
tests/conftest.py
Global pytest fixtures and test configuration for AMP AI multi-tenant security test suite.
"""

from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app import app
from backend.config import settings
from backend.database.connection import (
    AI_OUTPUTS_COLLECTION,
    AGENCY_KEYS_COLLECTION,
    AGENCY_AI_METADATA_COLLECTION,
    CLIENTS_COLLECTION,
    REPORTS_COLLECTION,
    ensure_database_indexes,
    get_database,
)
from backend.security.key_manager import key_manager
from backend.security.tenant_context import create_tenant_token


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """Configures test settings and ensures required indexes."""
    settings.AUTH_ENFORCE = True
    db = get_database()
    ensure_database_indexes(db)
    yield


@pytest.fixture(autouse=True)
def clean_test_collections():
    """Resets test collections before each test to guarantee test isolation."""
    db = get_database()
    # Clean keys cache
    key_manager.invalidate_cache("agency_alpha")
    key_manager.invalidate_cache("agency_beta")
    key_manager.invalidate_cache("agency_gamma")
    yield


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture
def token_agency_a() -> str:
    return create_tenant_token(
        user_id="user_alpha",
        agency_id="agency_alpha",
        roles=["owner", "admin", "staff"],
        allowed_agencies=["agency_alpha"],
    )


@pytest.fixture
def token_agency_b() -> str:
    return create_tenant_token(
        user_id="user_beta",
        agency_id="agency_beta",
        roles=["owner", "admin", "staff"],
        allowed_agencies=["agency_beta"],
    )


@pytest.fixture
def token_agency_c() -> str:
    return create_tenant_token(
        user_id="user_gamma",
        agency_id="agency_gamma",
        roles=["owner", "admin", "staff"],
        allowed_agencies=["agency_gamma"],
    )


@pytest.fixture
def token_viewer_agency_a() -> str:
    return create_tenant_token(
        user_id="user_alpha_viewer",
        agency_id="agency_alpha",
        roles=["viewer"],
        allowed_agencies=["agency_alpha"],
    )
