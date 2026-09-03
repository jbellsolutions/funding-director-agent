from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "files" / "local-packages" / "funding-director" / "src"
sys.path.insert(0, str(CORE_SRC))

from funding_director.catalog import ProductCatalog
from funding_director.engine import FundingEngine
from funding_director.ghl import GHLClient
from funding_director.models import ValidationError


class FundingCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.config = root / "config"
        self.state = root / "state"
        self.config.mkdir()
        products = {
            "schema_version": 1,
            "products": [
                {
                    "product_id": "test-browser-product",
                    "name": "Verified Browser Product",
                    "family": "test",
                    "status": "active",
                    "business_purpose_only": True,
                    "requirements": {"min_monthly_revenue": 10000, "min_time_in_business_months": 6},
                    "required_documents": ["business_application", "bank_statements"],
                    "exclusions": ["gambling"],
                    "sources": [{"type": "provider-evidence", "url": "private://provider/test", "note": "fixture"}],
                    "effective_date": "2026-01-01",
                    "expires_at": "2099-12-31",
                    "provider_id": "test-provider",
                    "submission_adapter": "browser_playbook"
                },
                {
                    "product_id": "test-http-product",
                    "name": "Verified HTTP Product",
                    "family": "test",
                    "status": "active",
                    "business_purpose_only": True,
                    "requirements": {},
                    "required_documents": ["business_application", "bank_statements"],
                    "exclusions": [],
                    "sources": [{"type": "provider-evidence", "url": "private://provider/http", "note": "fixture"}],
                    "effective_date": "2026-01-01",
                    "expires_at": "2099-12-31",
                    "provider_id": "http-provider",
                    "submission_adapter": "http_json"
                }
            ]
        }
        destinations = {
            "schema_version": 1,
            "destinations": [
                {
                    "destination_id": "test-browser",
                    "name": "Test Browser Portal",
                    "status": "active",
                    "adapter": "browser_playbook",
                    "product_ids": ["test-browser-product"],
                    "playbook_ref": "private://provider/test-browser-playbook"
                },
                {
                    "destination_id": "test-http",
                    "name": "Test HTTPS API",
                    "status": "active",
                    "adapter": "http_json",
                    "product_ids": ["test-http-product"],
                    "url": "https://provider.example.test/submissions",
                    "receipt_field": "submission.id"
                }
            ]
        }
        (self.config / "products.json").write_text(json.dumps(products), encoding="utf-8")
        (self.config / "destinations.json").write_text(json.dumps(destinations), encoding="utf-8")
        self.engine = FundingEngine(self.config, self.state)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def applicant(self, case_id: str = "case-001") -> dict:
        return {
            "case_id": case_id,
            "requested_amount": 50000,
            "purpose": "business working capital",
            "state": "FL",
            "industry": "consulting",
            "monthly_revenue": 25000,
            "time_in_business_months": 24,
            "credit_score": 700,
            "documents": ["business_application", "bank_statements"],
            "client_authorization_ref": "consent-001",
            "permissible_purpose_ref": "purpose-001"
        }

    def ready_case(self, case_id: str = "case-001") -> None:
        self.engine.create_case(self.applicant(case_id))
        for stage in ("completeness_review", "underwriting_review", "strategy_ready", "submission_ready"):
            self.engine.transition_case(case_id, stage, "synthetic test")

    @staticmethod
    def future() -> str:
        return (datetime.now(UTC) + timedelta(minutes=10)).isoformat()

    def approve_submission(self, submission_id: str) -> None:
        request = self.engine.request_approval(submission_id)
        self.engine.approve_submission(submission_id, request["action_digest"], "owner-test", self.future())

    def test_case_state_and_product_routing_are_deterministic(self) -> None:
        self.engine.create_case(self.applicant())
        with self.assertRaisesRegex(ValidationError, "invalid transition"):
            self.engine.transition_case("case-001", "funded", "skip everything")
        self.engine.transition_case("case-001", "completeness_review", "file received")
        result = self.engine.recommend("case-001")
        self.assertEqual(2, result["eligible_count"])
        self.assertTrue(all(match["eligible"] for match in result["matches"]))

    def test_sensitive_fields_and_incomplete_submission_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValidationError, "prohibited"):
            self.engine.create_case({**self.applicant(), "ssn": "000-00-0000"})
        self.ready_case()
        with self.assertRaisesRegex(ValidationError, "prohibited"):
            self.engine.prepare_submission(
                case_id="case-001",
                product_id="test-browser-product",
                destination="test-browser",
                payload={"applicant": {"bank_account": "123"}},
            )
        with self.assertRaisesRegex(ValidationError, "approved for this destination"):
            self.engine.prepare_submission(
                case_id="case-001",
                product_id="test-browser-product",
                destination="test-http",
                payload={"contact_ref": "contact-1"},
            )

    def test_submission_is_deduplicated_exactly_approved_and_consumed_once(self) -> None:
        self.ready_case()
        first = self.engine.prepare_submission(
            case_id="case-001",
            product_id="test-browser-product",
            destination="test-browser",
            payload={"contact_ref": "contact-1", "file_refs": ["doc-1"]},
        )
        duplicate = self.engine.prepare_submission(
            case_id="case-001",
            product_id="test-browser-product",
            destination="test-browser",
            payload={"file_refs": ["doc-1"], "contact_ref": "contact-1"},
        )
        self.assertEqual(first["submission_id"], duplicate["submission_id"])
        approval = self.engine.request_approval(first["submission_id"])
        with self.assertRaisesRegex(ValidationError, "digest"):
            self.engine.approve_submission(first["submission_id"], "wrong", "owner", self.future())
        self.engine.approve_submission(first["submission_id"], approval["action_digest"], "owner", self.future())
        with self.assertRaisesRegex(ValidationError, "begun"):
            self.engine.record_receipt(first["submission_id"], "too-early", "not actually submitted")
        begun = self.engine.begin_browser_submission(first["submission_id"])
        self.assertEqual("executing", begun["submission"]["state"])
        result = self.engine.record_receipt(first["submission_id"], "portal-receipt-1", "portal confirmation read back")
        self.assertEqual("submitted", result["state"])
        self.assertEqual("portal-receipt-1", result["external_receipt_id"])
        self.assertEqual("submitted", self.engine.get_case("case-001")["stage"])
        with self.assertRaisesRegex(ValidationError, "unused approval"):
            self.engine.begin_browser_submission(first["submission_id"])

    def test_expired_submission_approval_can_be_reissued_without_deleting_history(self) -> None:
        self.ready_case()
        submission = self.engine.prepare_submission(
            case_id="case-001",
            product_id="test-browser-product",
            destination="test-browser",
            payload={"contact_ref": "contact-reapproval"},
        )
        request = self.engine.request_approval(submission["submission_id"])
        approved = self.engine.approve_submission(
            submission["submission_id"], request["action_digest"], "owner-one", self.future()
        )
        with self.engine.store.connection() as connection:
            connection.execute(
                "UPDATE approvals SET expires_at = ? WHERE approval_id = ?",
                ((datetime.now(UTC) - timedelta(minutes=1)).isoformat(), approved["approval_id"]),
            )
        renewed = self.engine.request_approval(submission["submission_id"])
        final = self.engine.approve_submission(
            submission["submission_id"], renewed["action_digest"], "owner-two", self.future()
        )
        self.assertNotEqual(approved["approval_id"], final["approval_id"])
        with self.engine.store.connection() as connection:
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM approvals WHERE submission_id = ?",
                (submission["submission_id"],),
            ).fetchone()["count"]
        self.assertEqual(2, count)

    def test_ambiguous_browser_result_fails_closed_and_escalates_case(self) -> None:
        self.ready_case()
        submission = self.engine.prepare_submission(
            case_id="case-001",
            product_id="test-browser-product",
            destination="test-browser",
            payload={"contact_ref": "contact-unknown"},
        )
        self.approve_submission(submission["submission_id"])
        self.engine.begin_browser_submission(submission["submission_id"])
        result = self.engine.mark_submission_unknown(submission["submission_id"], "portal timed out")
        self.assertEqual("failed", result["state"])
        self.assertEqual("escalated", self.engine.get_case("case-001")["stage"])

    def test_reviewed_http_adapter_executes_once(self) -> None:
        self.ready_case()
        submission = self.engine.prepare_submission(
            case_id="case-001",
            product_id="test-http-product",
            destination="test-http",
            payload={"contact_ref": "contact-1"},
        )
        self.approve_submission(submission["submission_id"])
        with patch("funding_director.engine.send_http_json", return_value=("api-receipt-1", "HTTP 201")) as send:
            result = self.engine.execute_submission(submission["submission_id"])
        self.assertEqual("submitted", result["state"])
        self.assertEqual("api-receipt-1", result["external_receipt_id"])
        send.assert_called_once()
        with self.assertRaisesRegex(ValidationError, "unused approval"):
            self.engine.execute_submission(submission["submission_id"])

    def test_emergency_stop_blocks_submission_and_ghl_execution(self) -> None:
        self.ready_case()
        submission = self.engine.prepare_submission(
            case_id="case-001",
            product_id="test-browser-product",
            destination="test-browser",
            payload={"contact_ref": "contact-stop"},
        )
        self.approve_submission(submission["submission_id"])
        action = self.engine.prepare_ghl_action(
            operation="create_note", target_id="contact-1", payload={"body": "Internal synthetic note"}, case_id="case-001"
        )
        request = self.engine.request_external_action_approval(action["action_id"])
        self.engine.approve_external_action(action["action_id"], request["action_digest"], "owner", self.future())
        self.engine.stop_external_writes("synthetic stop test", "owner")
        with self.assertRaisesRegex(ValidationError, "emergency-stopped"):
            self.engine.authorize_execution(submission["submission_id"])
        with self.assertRaisesRegex(ValidationError, "emergency-stopped"):
            self.engine.execute_ghl_action(action["action_id"])

    def test_ghl_write_allowlist_and_one_time_approval(self) -> None:
        self.ready_case()
        with self.assertRaisesRegex(ValidationError, "unsupported"):
            self.engine.prepare_ghl_action(operation="delete_contact", target_id="contact-1", payload={})
        with self.assertRaisesRegex(ValidationError, "unapproved field"):
            self.engine.prepare_ghl_action(
                operation="update_opportunity", target_id="opp-1", payload={"pipelineStageId": "stage-2", "delete": True}
            )
        action = self.engine.prepare_ghl_action(
            operation="add_tags", target_id="contact-1", payload={"tags": ["funding-review"]}, case_id="case-001"
        )
        approval = self.engine.request_external_action_approval(action["action_id"])
        self.engine.approve_external_action(action["action_id"], approval["action_digest"], "owner", self.future())
        with patch("funding_director.engine.GHLClient") as client_class:
            client_class.return_value.execute.return_value = {"contact": {"id": "contact-1"}}
            result = self.engine.execute_ghl_action(action["action_id"])
        self.assertEqual("submitted", result["state"])
        with self.assertRaisesRegex(ValidationError, "unused approval"):
            self.engine.execute_ghl_action(action["action_id"])

    def test_offer_comparison_preserves_unknowns_and_requires_human_choice(self) -> None:
        self.ready_case()
        for stage in ("approval_requested", "submitted"):
            self.engine.transition_case("case-001", stage, "synthetic lifecycle")
        self.engine.record_offer({
            "offer_id": "offer-a",
            "case_id": "case-001",
            "product_id": "test-browser-product",
            "provider_name": "Provider A",
            "amount": 50000,
            "total_payback": 65000,
            "payment_amount": 1250,
            "payment_frequency": "weekly",
            "term_months": 12,
            "fees": 1000,
            "source_receipt": "offer-document-a"
        })
        self.engine.record_offer({
            "offer_id": "offer-b",
            "case_id": "case-001",
            "product_id": "test-http-product",
            "provider_name": "Provider B",
            "amount": 50000,
            "total_payback": None,
            "payment_amount": None,
            "payment_frequency": "unknown",
            "term_months": None,
            "source_receipt": "offer-document-b"
        })
        result = self.engine.compare_offers("case-001")
        self.assertEqual("human-selection-required", result["decision"])
        self.assertEqual("offer-a", result["offers"][0]["offer_id"])
        self.assertEqual(5416.67, result["offers"][0]["estimated_monthly_debt_service"])
        self.assertIsNone(result["offers"][1]["known_cost_per_net_dollar"])

    def test_active_product_requires_provider_evidence(self) -> None:
        invalid = {
            "schema_version": 1,
            "products": [{
                "product_id": "invalid-active",
                "name": "Invalid",
                "family": "test",
                "status": "active",
                "business_purpose_only": True,
                "requirements": {},
                "required_documents": [],
                "exclusions": [],
                "sources": [{"type": "marketing", "url": "https://example.test", "note": "not enough"}],
                "effective_date": "2026-01-01",
                "expires_at": "2099-01-01",
                "provider_id": "provider",
                "submission_adapter": "http_json"
            }]
        }
        path = self.config / "invalid-products.json"
        path.write_text(json.dumps(invalid), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "provider evidence"):
            ProductCatalog(path)

    def test_ghl_rejects_broad_or_session_credentials(self) -> None:
        with self.assertRaisesRegex(ValidationError, "location-scoped"):
            GHLClient(token="firebase-refresh-token", location_id="location-1")

    def test_ghl_uses_current_v3_contract_and_camel_case_filters(self) -> None:
        client = GHLClient(token="pit-synthetic-test", location_id="location-1")
        self.assertEqual("v3", client.VERSION)
        with patch.object(client, "_call", return_value={}) as call:
            client.search_contacts("Jane", 999)
        call.assert_called_once_with(
            "POST",
            "/contacts/search",
            body={"locationId": "location-1", "pageLimit": 100, "query": "Jane"},
        )
        with patch.object(client, "_call", return_value={}) as call:
            client.search_opportunities("pipeline-1", "open", 20)
        call.assert_called_once_with(
            "GET",
            "/opportunities/search",
            query={
                "locationId": "location-1",
                "pipelineId": "pipeline-1",
                "status": "open",
                "limit": 20,
            },
        )


if __name__ == "__main__":
    unittest.main()
