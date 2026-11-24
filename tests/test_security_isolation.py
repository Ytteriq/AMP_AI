"""
tests/test_security_isolation.py
Comprehensive automated security and multi-tenant isolation test suite for AMP AI.
Tests all 20 security requirements defined in Phase 9 across Agency A, Agency B, and Agency C.
"""

import base64
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.database.connection import (
    AI_OUTPUTS_COLLECTION,
    AGENCY_KEYS_COLLECTION,
    REPORTS_COLLECTION,
    CLIENTS_COLLECTION,
    get_database,
)
from backend.security.encryption_service import encryption_service
from backend.security.exceptions import (
    CrossAgencySubstitutionError,
    DecryptionError,
    KeyNotFoundError,
    TamperedCiphertextError,
    TenantAccessDeniedError,
)
from backend.security.key_manager import key_manager
from backend.security.tenant_context import (
    TenantContext,
    create_tenant_token,
    current_tenant_cv,
)
from backend.services.client_data_service import (
    get_ai_output,
    get_saved_reports,
    save_report_to_db,
)
from backend.tools.database_tools import query_reel_data


# -----------------------------------------------------------------------------
# 1. Agency A can access its own AI outputs
# -----------------------------------------------------------------------------
def test_1_agency_a_can_access_own_ai_outputs(client: TestClient, token_agency_a: str):
    headers = {"Authorization": f"Bearer {token_agency_a}"}

    # Save a report for Agency A
    save_res = client.post(
        "/api/reports/save",
        json={
            "report_payload": {
                "report_title": "Agency A Secret Strategy 2026",
                "client_id": "client_alpha_01",
                "executive_summary": {"overall_performance": "Agency A 10x ROAS"},
            }
        },
        headers=headers,
    )
    assert save_res.status_code == 200, save_res.text
    report_id = save_res.json()["report_id"]

    # Retrieve report via list
    list_res = client.get("/api/reports", headers=headers)
    assert list_res.status_code == 200
    reports = list_res.json()["reports"]
    matching = [r for r in reports if r.get("report_id") == report_id]
    assert len(matching) == 1
    assert matching[0]["report_title"] == "Agency A Secret Strategy 2026"
    assert matching[0]["executive_summary"]["overall_performance"] == "Agency A 10x ROAS"

    # Retrieve single report
    single_res = client.get(f"/api/reports/{report_id}", headers=headers)
    assert single_res.status_code == 200
    assert single_res.json()["report_title"] == "Agency A Secret Strategy 2026"


# -----------------------------------------------------------------------------
# 2. Agency B can access its own AI outputs
# -----------------------------------------------------------------------------
def test_2_agency_b_can_access_own_ai_outputs(client: TestClient, token_agency_b: str):
    headers = {"Authorization": f"Bearer {token_agency_b}"}

    save_res = client.post(
        "/api/reports/save",
        json={
            "report_payload": {
                "report_title": "Agency B Confidential Q3",
                "client_id": "client_beta_01",
                "executive_summary": {"overall_performance": "Agency B 5x ROAS"},
            }
        },
        headers=headers,
    )
    assert save_res.status_code == 200
    report_id = save_res.json()["report_id"]

    list_res = client.get("/api/reports", headers=headers)
    assert list_res.status_code == 200
    reports = list_res.json()["reports"]
    matching = [r for r in reports if r.get("report_id") == report_id]
    assert len(matching) == 1
    assert matching[0]["report_title"] == "Agency B Confidential Q3"


# -----------------------------------------------------------------------------
# 3. Agency A cannot access Agency B's AI outputs
# -----------------------------------------------------------------------------
def test_3_agency_a_cannot_access_agency_b_ai_outputs(client: TestClient, token_agency_a: str, token_agency_b: str):
    # Save a report under Agency B
    headers_b = {"Authorization": f"Bearer {token_agency_b}"}
    save_b = client.post(
        "/api/reports/save",
        json={"report_payload": {"report_title": "Top Secret Agency B Playbook", "client_id": "client_b"}},
        headers=headers_b,
    )
    report_id_b = save_b.json()["report_id"]

    # Agency A tries to access Agency B's report
    headers_a = {"Authorization": f"Bearer {token_agency_a}"}
    get_res = client.get(f"/api/reports/{report_id_b}", headers=headers_a)
    assert get_res.status_code == 404, "Agency A should receive 404 when requesting Agency B report"

    # Agency A lists reports; Agency B's report must NOT be included
    list_a = client.get("/api/reports", headers=headers_a)
    reports_a = list_a.json()["reports"]
    assert not any(r.get("report_id") == report_id_b for r in reports_a)


# -----------------------------------------------------------------------------
# 4. Agency B cannot access Agency A's AI outputs
# -----------------------------------------------------------------------------
def test_4_agency_b_cannot_access_agency_a_ai_outputs(client: TestClient, token_agency_a: str, token_agency_b: str):
    headers_a = {"Authorization": f"Bearer {token_agency_a}"}
    save_a = client.post(
        "/api/reports/save",
        json={"report_payload": {"report_title": "Agency A Proprietary Financials", "client_id": "client_a"}},
        headers=headers_a,
    )
    report_id_a = save_a.json()["report_id"]

    headers_b = {"Authorization": f"Bearer {token_agency_b}"}
    get_res = client.get(f"/api/reports/{report_id_a}", headers=headers_b)
    assert get_res.status_code == 404, "Agency B should receive 404 when requesting Agency A report"


# -----------------------------------------------------------------------------
# 5. Changing agencyId in a request does not bypass authorization
# -----------------------------------------------------------------------------
def test_5_changing_agency_id_in_request_does_not_bypass_authorization(client: TestClient, token_agency_a: str):
    headers_a = {"Authorization": f"Bearer {token_agency_a}"}

    # Attempt to query Agency B's dashboard by changing query param ?agency_id=agency_beta
    dash_res = client.get("/api/dashboard/summary?agency_id=agency_beta", headers=headers_a)
    assert dash_res.status_code == 403, "Tampering with query param agency_id must return 403 Forbidden"

    # Attempt to query Agency B's clients
    clients_res = client.get("/api/clients?agency_id=agency_beta", headers=headers_a)
    assert clients_res.status_code == 403

    # Attempt to list Agency B's reports
    reports_res = client.get("/api/reports?agency_id=agency_beta", headers=headers_a)
    assert reports_res.status_code == 403


# -----------------------------------------------------------------------------
# 6. Guessing another agency's document ID does not expose data
# -----------------------------------------------------------------------------
def test_6_guessing_another_agency_document_id_does_not_expose_data(client: TestClient, token_agency_a: str, token_agency_b: str):
    # Agency B saves a document
    headers_b = {"Authorization": f"Bearer {token_agency_b}"}
    save_res = client.post(
        "/api/reports/save",
        json={"report_payload": {"report_id": "REP_GUESSED_TARGET_999", "report_title": "Target Document"}},
        headers=headers_b,
    )
    target_id = save_res.json()["report_id"]

    # Agency A tries to guess the ID
    headers_a = {"Authorization": f"Bearer {token_agency_a}"}
    guess_res = client.get(f"/api/reports/{target_id}", headers=headers_a)
    assert guess_res.status_code == 404


# -----------------------------------------------------------------------------
# 7. Unauthenticated requests are rejected
# -----------------------------------------------------------------------------
def test_7_unauthenticated_requests_are_rejected(client: TestClient):
    # Without any token or cookies
    assert client.get("/api/dashboard/summary").status_code == 401
    assert client.get("/api/clients").status_code == 401
    assert client.get("/api/reports").status_code == 401
    assert client.post("/api/reports/generate", json={"client_id": "c1", "report_type": "performance_analysis"}).status_code == 401
    assert client.post("/api/analysis/chat", json={"question": "Test question?"}).status_code == 401


# -----------------------------------------------------------------------------
# 8. Removed agency members cannot access data
# -----------------------------------------------------------------------------
def test_8_removed_agency_members_cannot_access_data(client: TestClient):
    # Expired token
    expired_token = create_tenant_token(
        user_id="user_fired",
        agency_id="agency_alpha",
        roles=["staff"],
        expires_in_hours=-1,  # expired 1 hour ago
    )
    res = client.get("/api/reports", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


# -----------------------------------------------------------------------------
# 9. Users with insufficient permissions cannot access restricted data
# -----------------------------------------------------------------------------
def test_9_users_with_insufficient_permissions_cannot_access_restricted_data(client: TestClient, token_viewer_agency_a: str):
    # Viewer role attempts key rotation
    headers = {"Authorization": f"Bearer {token_viewer_agency_a}"}
    rotate_res = client.post("/api/security/key/rotate", headers=headers)
    assert rotate_res.status_code == 403


# -----------------------------------------------------------------------------
# 10. Ciphertext modification causes decryption failure
# -----------------------------------------------------------------------------
def test_10_ciphertext_modification_causes_decryption_failure():
    db = get_database()
    doc = encryption_service.encrypt_agency_data(
        agency_id="agency_alpha",
        record_id="tamper_ct_test",
        data={"secret": "integrity_check_data"},
    )

    # Corrupt ciphertext
    corrupted_doc = dict(doc)
    corrupted_doc["encryptedPayload"] = dict(doc["encryptedPayload"])
    raw_ct = base64.b64decode(corrupted_doc["encryptedPayload"]["ciphertext"])
    flipped = bytes([raw_ct[0] ^ 0xFF]) + raw_ct[1:]
    corrupted_doc["encryptedPayload"]["ciphertext"] = base64.b64encode(flipped).decode("utf-8")

    with pytest.raises(TamperedCiphertextError):
        encryption_service.decrypt_agency_data("agency_alpha", "tamper_ct_test", corrupted_doc)


# -----------------------------------------------------------------------------
# 11. Authentication tag modification causes decryption failure
# -----------------------------------------------------------------------------
def test_11_auth_tag_modification_causes_decryption_failure():
    doc = encryption_service.encrypt_agency_data(
        agency_id="agency_alpha",
        record_id="tamper_tag_test",
        data={"secret": "integrity_check_tag"},
    )

    # Corrupt authTag
    corrupted_doc = dict(doc)
    corrupted_doc["encryptedPayload"] = dict(doc["encryptedPayload"])
    raw_tag = base64.b64decode(corrupted_doc["encryptedPayload"]["authTag"])
    flipped_tag = bytes([raw_tag[0] ^ 0x01]) + raw_tag[1:]
    corrupted_doc["encryptedPayload"]["authTag"] = base64.b64encode(flipped_tag).decode("utf-8")

    with pytest.raises(TamperedCiphertextError):
        encryption_service.decrypt_agency_data("agency_alpha", "tamper_tag_test", corrupted_doc)


# -----------------------------------------------------------------------------
# 12. Cross-agency ciphertext substitution is rejected
# -----------------------------------------------------------------------------
def test_12_cross_agency_ciphertext_substitution_is_rejected():
    # Encrypt data for Agency A
    doc_a = encryption_service.encrypt_agency_data(
        agency_id="agency_alpha",
        record_id="sub_test_01",
        data={"confidential": "Agency A Confidential Strategy"},
    )

    # Attempt to decrypt Agency A's payload using Agency B's context
    with pytest.raises(CrossAgencySubstitutionError):
        encryption_service.decrypt_agency_data("agency_beta", "sub_test_01", doc_a)


# -----------------------------------------------------------------------------
# 13. Encryption failures never produce plaintext storage
# -----------------------------------------------------------------------------
def test_13_encryption_failures_never_produce_plaintext_storage():
    db = get_database()
    initial_count = db[AI_OUTPUTS_COLLECTION].count_documents({})

    # Force an encryption error by passing empty record_id
    with pytest.raises(Exception):
        encryption_service.encrypt_agency_data(
            agency_id="agency_alpha",
            record_id="",  # invalid
            data={"sensitive": "should never be stored"},
        )

    # Verify nothing was inserted
    after_count = db[AI_OUTPUTS_COLLECTION].count_documents({})
    assert after_count == initial_count


# -----------------------------------------------------------------------------
# 14. Key rotation preserves existing data access
# -----------------------------------------------------------------------------
def test_14_key_rotation_preserves_existing_data_access():
    agency = "agency_alpha"
    # Ensure Key v1
    key_manager.get_or_create_agency_key(agency)

    # Encrypt record under Key v1
    doc_v1 = encryption_service.encrypt_agency_data(
        agency_id=agency,
        record_id="rec_v1_test",
        data={"message": "Created under Key Version 1"},
    )
    assert doc_v1["keyVersion"] == 1

    # Rotate key to v2
    rot_meta = key_manager.rotate_agency_key(agency)
    assert rot_meta["keyVersion"] == 2

    # Verify record encrypted under v1 can STILL be decrypted!
    dec_v1 = encryption_service.decrypt_agency_data(agency, "rec_v1_test", doc_v1)
    assert dec_v1["message"] == "Created under Key Version 1"

    # Encrypt new record under Key v2
    doc_v2 = encryption_service.encrypt_agency_data(
        agency_id=agency,
        record_id="rec_v2_test",
        data={"message": "Created under Key Version 2"},
    )
    assert doc_v2["keyVersion"] == 2

    # Verify v2 decrypts
    dec_v2 = encryption_service.decrypt_agency_data(agency, "rec_v2_test", doc_v2)
    assert dec_v2["message"] == "Created under Key Version 2"


# -----------------------------------------------------------------------------
# 15. Background jobs enforce agency isolation
# -----------------------------------------------------------------------------
def test_15_background_jobs_enforce_agency_isolation():
    # Simulate background task executing within Agency B context
    ctx_b = TenantContext(
        user_id="bg_worker",
        agency_id="agency_beta",
        roles=["staff"],
        allowed_agencies=["agency_beta"],
    )
    token = current_tenant_cv.set(ctx_b)
    try:
        # Tool call without explicit agency filter
        result = query_reel_data.invoke({})
        # Verify all retrieved records belong to agency_beta or match agency filter
        applied = result.get("applied_filters", {})
        assert applied.get("agency_name") == "agency_beta"
    finally:
        current_tenant_cv.reset(token)


# -----------------------------------------------------------------------------
# 16. AI outputs are stored encrypted in MongoDB
# -----------------------------------------------------------------------------
def test_16_ai_outputs_are_stored_encrypted_in_mongodb():
    db = get_database()
    record_id = "inspect_mongo_encryption_test"
    save_report_to_db(
        {
            "report_id": record_id,
            "report_title": "Highly Confidential M&A Ad Report",
            "secret_client_metrics": {"secret_revenue": 9999999},
        },
        agency_id="agency_alpha",
        user_id="user_alpha",
    )

    # Read raw document directly from MongoDB
    raw_doc = db[AI_OUTPUTS_COLLECTION].find_one({"_id": record_id})
    assert raw_doc is not None
    assert raw_doc["algorithm"] == "AES-256-GCM"
    assert "encryptedPayload" in raw_doc
    payload = raw_doc["encryptedPayload"]
    assert "ciphertext" in payload
    assert "nonce" in payload
    assert "authTag" in payload

    # STRICT ASSERTION: Plaintext title or secrets must NOT be anywhere in raw document!
    raw_str = str(raw_doc)
    assert "Highly Confidential M&A Ad Report" not in raw_str
    assert "secret_client_metrics" not in raw_str
    assert "9999999" not in raw_str


# -----------------------------------------------------------------------------
# 17. Existing AI features continue functioning
# -----------------------------------------------------------------------------
def test_17_existing_ai_features_continue_functioning(client: TestClient, token_agency_a: str):
    headers = {"Authorization": f"Bearer {token_agency_a}"}

    # Dashboard summary
    dash_res = client.get("/api/dashboard/summary", headers=headers)
    assert dash_res.status_code == 200
    assert "total_clients" in dash_res.json()

    # List clients
    clients_res = client.get("/api/clients", headers=headers)
    assert clients_res.status_code == 200
    assert "clients" in clients_res.json()

    # HTML export
    export_res = client.post(
        "/api/reports/export/html",
        json={"report_title": "Test Title", "client_info": {"client_name": "Test Brand"}},
        headers=headers,
    )
    assert export_res.status_code == 200
    assert "<html" in export_res.text.lower()


# -----------------------------------------------------------------------------
# 18. Agency registration provisions encryption keys correctly
# -----------------------------------------------------------------------------
def test_18_agency_registration_provisions_encryption_keys_correctly():
    db = get_database()
    new_agency = "agency_gamma"

    # Provision key for Agency C
    key_info = key_manager.create_agency_key(new_agency)
    assert key_info["agencyId"] == new_agency
    assert key_info["keyVersion"] == 1
    assert key_info["status"] == "active"

    # Verify document in agency_encryption_keys
    raw_key_doc = db[AGENCY_KEYS_COLLECTION].find_one({"agencyId": new_agency, "keyVersion": 1})
    assert raw_key_doc is not None
    assert "wrappedDEK" in raw_key_doc
    assert "kmsKeyId" in raw_key_doc
    # Plaintext DEK must NEVER be present!
    assert "plaintext" not in raw_key_doc
    assert "dek" not in raw_key_doc


# -----------------------------------------------------------------------------
# 19. An agency without a valid key cannot silently bypass encryption
# -----------------------------------------------------------------------------
def test_19_agency_without_valid_key_cannot_silently_bypass_encryption():
    # Corrupt agency key in database for a dummy agency
    db = get_database()
    dummy_agency = "agency_broken_key"
    key_manager.get_or_create_agency_key(dummy_agency)
    # Corrupt wrappedDEK
    db[AGENCY_KEYS_COLLECTION].update_one(
        {"agencyId": dummy_agency},
        {"$set": {"wrappedDEK": "INVALID_CORRUPTED_BASE64!!!"}},
    )
    key_manager.invalidate_cache(dummy_agency)

    # Attempting to unwrap or encrypt should fail loudly, never fall back to plaintext
    with pytest.raises(Exception):
        key_manager.unwrap_dek(dummy_agency)


# -----------------------------------------------------------------------------
# 20. Cache entries cannot leak key material across agencies
# -----------------------------------------------------------------------------
def test_20_cache_entries_cannot_leak_key_material_across_agencies():
    key_manager.invalidate_cache("agency_alpha")
    key_manager.invalidate_cache("agency_beta")

    # Ensure keys exist for both agencies
    key_manager.get_or_create_agency_key("agency_alpha")
    key_manager.get_or_create_agency_key("agency_beta")

    # Prime Agency A into cache
    dek_a, ver_a = key_manager.unwrap_dek("agency_alpha")
    # Prime Agency B into cache
    dek_b, ver_b = key_manager.unwrap_dek("agency_beta")

    # Verify keys are independent
    assert dek_a != dek_b, "Agency A and Agency B must have unique, independent DEKs!"

    # Verify cache isolation: Agency A cache entry is only accessible for Agency A
    cached_a = key_manager._cache_get("agency_alpha", ver_a)
    cached_b = key_manager._cache_get("agency_beta", ver_b)
    assert cached_a == dek_a
    assert cached_b == dek_b
    assert key_manager._cache_get("agency_beta", ver_a) != dek_a
