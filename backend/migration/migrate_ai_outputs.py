"""
backend/migration/migrate_ai_outputs.py
Production-grade, resumable migration CLI for converting legacy plaintext AI outputs
into AES-256-GCM envelope-encrypted records in the shared 'ai_outputs' collection.

Supports:
- Dry-run mode (--dry-run)
- Live migration (--migrate)
- Decryption verification (--verify)
- Migration status reporting (--status)
- Safe rollback (--rollback)
"""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Any, Dict, List, Optional, Tuple

from backend.database.connection import (
    AI_OUTPUTS_COLLECTION,
    AGENCY_AI_METADATA_COLLECTION,
    AGENCY_KEYS_COLLECTION,
    CLIENTS_COLLECTION,
    REPORTS_COLLECTION,
    get_database,
)
from backend.security.audit_logger import audit_logger
from backend.security.encryption_service import encryption_service
from backend.security.key_manager import key_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ai_reel.migration")

BACKUP_COLLECTION = "_migration_backup_reports"


class AIMigrationRunner:
    """Orchestrates safe, verifiable migration of legacy plaintext AI reports."""

    def __init__(self, db: Optional[Any] = None) -> None:
        self.db = db or get_database()

    def resolve_agency_id(self, doc: Dict[str, Any]) -> Optional[str]:
        """
        Determines authoritative owning agency for a document.
        Never guesses: returns None if ambiguous.
        """
        # 1. Direct agency_id or agencyId on document
        agency_id = doc.get("agency_id") or doc.get("agencyId")
        if agency_id and str(agency_id).strip() and str(agency_id).strip() != "undefined":
            return str(agency_id).strip()

        # 2. In nested client_info
        client_info = doc.get("client_info")
        if isinstance(client_info, dict):
            c_agency = client_info.get("agency_id") or client_info.get("agencyId")
            if c_agency and str(c_agency).strip():
                return str(c_agency).strip()

        # 3. Lookup client in clients collection
        client_id = doc.get("client_id")
        if not client_id and isinstance(client_info, dict):
            client_id = client_info.get("client_id")

        if client_id:
            client_doc = self.db[CLIENTS_COLLECTION].find_one({"client_id": str(client_id).strip()})
            if client_doc and client_doc.get("agency_id"):
                return str(client_doc["agency_id"]).strip()

        return None

    def get_status(self) -> Dict[str, Any]:
        """Calculates current migration metrics across collections."""
        total_reports = self.db[REPORTS_COLLECTION].count_documents({})
        migrated_reports = self.db[REPORTS_COLLECTION].count_documents({"migrated": True})
        total_encrypted_outputs = self.db[AI_OUTPUTS_COLLECTION].count_documents({})
        total_keys = self.db[AGENCY_KEYS_COLLECTION].count_documents({})

        unmigrated = total_reports - migrated_reports
        return {
            "total_legacy_reports": total_reports,
            "migrated_legacy_reports": migrated_reports,
            "unmigrated_legacy_reports": unmigrated,
            "total_encrypted_ai_outputs": total_encrypted_outputs,
            "total_agency_keys": total_keys,
            "migration_completed": (unmigrated == 0 and total_reports > 0),
        }

    def run_dry_run(self) -> Dict[str, Any]:
        """
        Analyzes existing records and prints a comprehensive plan without modifying any data.
        """
        logger.info("Executing Migration DRY-RUN...")
        docs = list(self.db[REPORTS_COLLECTION].find({}))
        plan: List[Dict[str, Any]] = []
        ambiguous: List[str] = []
        already_migrated: int = 0
        ready_to_migrate: int = 0

        for doc in docs:
            doc_id = str(doc.get("report_id") or doc.get("_id"))
            if doc.get("migrated") is True:
                already_migrated += 1
                continue

            agency_id = self.resolve_agency_id(doc)
            if not agency_id:
                ambiguous.append(doc_id)
                plan.append({
                    "record_id": doc_id,
                    "action": "SKIP",
                    "reason": "Ambiguous agency ownership - manual review required",
                })
            else:
                ready_to_migrate += 1
                plan.append({
                    "record_id": doc_id,
                    "agency_id": agency_id,
                    "action": "ENCRYPT_AND_PERSIST",
                    "reason": "Valid agency identified",
                })

        summary = {
            "mode": "DRY_RUN",
            "total_records": len(docs),
            "already_migrated": already_migrated,
            "ready_to_migrate": ready_to_migrate,
            "ambiguous_records_skipped": len(ambiguous),
            "ambiguous_record_ids": ambiguous,
        }
        logger.info("DRY-RUN Complete: Ready=%d, Skipped=%d, AlreadyMigrated=%d", ready_to_migrate, len(ambiguous), already_migrated)
        return summary

    def run_migration(self) -> Dict[str, Any]:
        """
        Executes actual resumable migration:
        1. Backs up records before encryption.
        2. Generates missing agency keys.
        3. Encrypts outputs with AES-256-GCM.
        4. Verifies round-trip decryption.
        5. Saves to ai_outputs and marks original record as migrated.
        """
        logger.info("Starting Live AI Output Migration...")
        cursor = self.db[REPORTS_COLLECTION].find({"migrated": {"$ne": True}})
        migrated_count = 0
        failed_count = 0
        skipped_ambiguous = 0
        details: List[Dict[str, Any]] = []

        now_iso = datetime.now(timezone.utc).isoformat()

        for doc in cursor:
            doc_id = str(doc.get("report_id") or doc.get("_id"))
            agency_id = self.resolve_agency_id(doc)

            if not agency_id:
                skipped_ambiguous += 1
                details.append({
                    "record_id": doc_id,
                    "status": "SKIPPED",
                    "error": "Ambiguous agency ID; cannot guarantee isolated ownership.",
                })
                continue

            try:
                # 1. Backup original document for rollback safety
                backup_copy = dict(doc)
                backup_copy["_backup_timestamp"] = now_iso
                self.db[BACKUP_COLLECTION].replace_one({"_id": doc["_id"]}, backup_copy, upsert=True)

                # 2. Ensure agency has an encryption key
                key_manager.get_or_create_agency_key(agency_id)

                # 3. Clean payload of internal MongoDB ObjectIds
                clean_payload = dict(doc)
                clean_payload["_id"] = doc_id
                clean_payload["report_id"] = doc_id
                clean_payload["agency_id"] = agency_id

                # 4. Encrypt document
                user_id = str(doc.get("user_id") or "migration_admin")
                encrypted_doc = encryption_service.encrypt_agency_data(
                    agency_id=agency_id,
                    record_id=doc_id,
                    data=clean_payload,
                    user_id=user_id,
                    feature="marketing_report",
                )

                # 5. VERIFICATION: Decrypt immediately to guarantee data integrity
                verified_data = encryption_service.decrypt_agency_data(
                    agency_id=agency_id,
                    record_id=doc_id,
                    encrypted_data=encrypted_doc,
                )
                if not verified_data or verified_data.get("report_id") != doc_id:
                    raise ValueError("Decryption verification failed: payload corrupted.")

                # 6. Save encrypted document to ai_outputs
                self.db[AI_OUTPUTS_COLLECTION].replace_one({"_id": doc_id}, encrypted_doc, upsert=True)

                # 7. Write non-sensitive metadata to agency_ai_metadata
                meta_doc = {
                    "_id": doc_id,
                    "agencyId": agency_id,
                    "userId": user_id,
                    "feature": "marketing_report",
                    "report_title": doc.get("report_title", "Marketing Report"),
                    "client_id": doc.get("client_info", {}).get("client_id") if isinstance(doc.get("client_info"), dict) else doc.get("client_id"),
                    "createdAt": encrypted_doc["createdAt"],
                    "migrated": True,
                }
                self.db[AGENCY_AI_METADATA_COLLECTION].replace_one({"_id": doc_id}, meta_doc, upsert=True)

                # 8. Mark original record as migrated (preserving original for backup)
                self.db[REPORTS_COLLECTION].update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "migrated": True,
                            "migratedAt": now_iso,
                            "encryptedOutputId": doc_id,
                        }
                    },
                )

                migrated_count += 1
                details.append({"record_id": doc_id, "agency_id": agency_id, "status": "MIGRATED_AND_VERIFIED"})

                audit_logger.log_event(
                    event_type="MIGRATION_RECORD_ENCRYPTED",
                    agency_id=agency_id,
                    user_id="migration_runner",
                    resource_id=doc_id,
                    status="SUCCESS",
                )

            except Exception as exc:
                failed_count += 1
                logger.error("Migration failed for report '%s': %s", doc_id, exc)
                details.append({"record_id": doc_id, "agency_id": agency_id, "status": "FAILED", "error": str(exc)})
                audit_logger.log_event(
                    event_type="MIGRATION_RECORD_FAILED",
                    agency_id=agency_id or "UNKNOWN",
                    user_id="migration_runner",
                    resource_id=doc_id,
                    status="FAILED",
                    details={"error": str(exc)},
                )

        report = {
            "mode": "LIVE_MIGRATION",
            "timestamp": now_iso,
            "migrated_successfully": migrated_count,
            "failures": failed_count,
            "skipped_ambiguous": skipped_ambiguous,
            "details": details,
        }
        logger.info(
            "Migration execution finished: %d succeeded, %d failed, %d skipped.",
            migrated_count,
            failed_count,
            skipped_ambiguous,
        )
        return report

    def verify_all_migrated(self) -> Dict[str, Any]:
        """
        Scans all documents in 'ai_outputs', retrieves each agency key,
        and verifies that each record decrypts without error.
        """
        logger.info("Verifying all encrypted ai_outputs...")
        cursor = self.db[AI_OUTPUTS_COLLECTION].find({})
        verified = 0
        corrupted = 0
        details = []

        for doc in cursor:
            doc_id = doc["_id"]
            agency_id = doc.get("agencyId")
            try:
                decrypted = encryption_service.decrypt_agency_data(agency_id, doc_id, doc)
                if not decrypted:
                    raise ValueError("Decrypted output is empty.")
                verified += 1
            except Exception as exc:
                corrupted += 1
                details.append({"record_id": doc_id, "agency_id": agency_id, "error": str(exc)})
                logger.error("Verification failed for '%s' (agency '%s'): %s", doc_id, agency_id, exc)

        summary = {
            "total_checked": verified + corrupted,
            "verified_valid": verified,
            "corrupted_or_failed": corrupted,
            "details": details,
            "all_valid": (corrupted == 0),
        }
        logger.info("Verification Complete: %d valid, %d corrupted.", verified, corrupted)
        return summary

    def run_rollback(self) -> Dict[str, Any]:
        """
        Restores reports from _migration_backup_reports and removes newly encrypted records.
        """
        logger.info("Executing Migration Rollback from backup collection...")
        backups = list(self.db[BACKUP_COLLECTION].find({}))
        restored = 0

        for b in backups:
            original_id = b["_id"]
            clean_b = {k: v for k, v in b.items() if k not in ("_backup_timestamp",)}
            clean_b["migrated"] = False

            # Restore original in reports collection
            self.db[REPORTS_COLLECTION].replace_one({"_id": original_id}, clean_b, upsert=True)

            # Delete from ai_outputs
            out_id = str(b.get("report_id") or original_id)
            self.db[AI_OUTPUTS_COLLECTION].delete_one({"_id": out_id})
            self.db[AGENCY_AI_METADATA_COLLECTION].delete_one({"_id": out_id})
            restored += 1

        logger.info("Rollback complete: %d records restored.", restored)
        return {"status": "SUCCESS", "records_restored": restored}


def main():
    parser = argparse.ArgumentParser(description="AMP AI Outputs Multi-Tenant Encryption Migration CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Analyze records and display migration plan without writing.")
    group.add_argument("--migrate", action="store_true", help="Execute live migration and verification.")
    group.add_argument("--verify", action="store_true", help="Verify all encrypted ai_outputs can be decrypted.")
    group.add_argument("--status", action="store_true", help="Display current migration status counts.")
    group.add_argument("--rollback", action="store_true", help="Roll back migrated records from backup.")

    args = parser.parse_args()
    runner = AIMigrationRunner()

    if args.dry_run:
        result = runner.run_dry_run()
        print(json.dumps(result, indent=2))
    elif args.migrate:
        result = runner.run_migration()
        print(json.dumps(result, indent=2))
    elif args.verify:
        result = runner.verify_all_migrated()
        print(json.dumps(result, indent=2))
    elif args.status:
        result = runner.get_status()
        print(json.dumps(result, indent=2))
    elif args.rollback:
        result = runner.run_rollback()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
