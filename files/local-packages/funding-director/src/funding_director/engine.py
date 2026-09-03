"""Funding case, recommendation, approval, and submission engine."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
from typing import Any

from .catalog import ProductCatalog
from .destinations import DestinationCatalog, send_http_json
from .ghl import GHLClient
from .models import (
    ApplicantProfile,
    CaseStage,
    FundingOffer,
    ProductStatus,
    SubmissionState,
    TERMINAL_STAGES,
    ValidationError,
    reject_sensitive_keys,
)
from .store import FundingStore, now_iso


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode()).hexdigest()


class FundingEngine:
    def __init__(self, config_dir: Path | None = None, state_dir: Path | None = None):
        package_root = Path(__file__).resolve().parents[2]
        self.config_dir = config_dir or Path(os.getenv("FUNDING_DIRECTOR_CONFIG_DIR", package_root / "config"))
        self.state_dir = state_dir or Path(os.getenv("FUNDING_DIRECTOR_STATE_DIR", Path.home() / ".hermes" / "funding-director"))
        self.catalog = ProductCatalog(self.config_dir / "products.json")
        self.destinations = DestinationCatalog(self.config_dir / "destinations.json")
        self.store = FundingStore(self.state_dir / "funding-director.sqlite3")
        self.stop_file = self.state_dir / "EXTERNAL_WRITES_STOPPED"

    def external_write_status(self) -> dict[str, Any]:
        return {
            "stopped": self.stop_file.exists(),
            "reason": self.stop_file.read_text(encoding="utf-8").strip() if self.stop_file.exists() else "",
        }

    def stop_external_writes(self, reason: str, actor: str = "funding-director") -> dict[str, Any]:
        if not reason.strip():
            raise ValidationError("an emergency-stop reason is required")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.stop_file.with_suffix(".tmp")
        temporary.write_text(f"{now_iso()} | {actor} | {reason.strip()}\n", encoding="utf-8")
        temporary.replace(self.stop_file)
        self.store.audit(
            actor=actor,
            case_id="",
            action="external_writes.stop",
            resource="all",
            policy_decision="deny",
            result="stopped",
            verification="stop sentinel written",
            details={"reason": reason.strip()},
        )
        return self.external_write_status()

    def _require_external_writes_enabled(self) -> None:
        if self.stop_file.exists():
            raise ValidationError("external writes are emergency-stopped; owner resume is required")

    def create_case(self, applicant: dict[str, Any]) -> dict[str, Any]:
        return self.store.create_case(ApplicantProfile.from_dict(applicant))

    def get_case(self, case_id: str) -> dict[str, Any]:
        return self.store.get_case(case_id)

    def transition_case(self, case_id: str, target: str, reason: str) -> dict[str, Any]:
        return self.store.transition(case_id, CaseStage(target), reason)

    def recommend(self, case_id: str, include_inactive: bool = False) -> dict[str, Any]:
        case = self.store.get_case(case_id)
        applicant = ApplicantProfile.from_dict(case["applicant"])
        matches = [item.to_dict() for item in self.catalog.match(applicant, include_inactive)]
        recommendation = {
            "case_id": case_id,
            "generated_at": now_iso(),
            "catalog_path": str(self.catalog.path),
            "eligible_count": sum(1 for item in matches if item["eligible"]),
            "matches": matches[:10],
            "decision": (
                "eligible_routes_found"
                if any(item["eligible"] for item in matches)
                else "no_verified_active_route"
            ),
        }
        self.store.save_recommendation(case_id, recommendation)
        return recommendation

    def prepare_submission(
        self,
        *,
        case_id: str,
        product_id: str,
        destination: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        reject_sensitive_keys(payload, "submission")
        case = self.store.get_case(case_id)
        applicant = ApplicantProfile.from_dict(case["applicant"])
        if CaseStage(case["stage"]) is not CaseStage.SUBMISSION_READY:
            raise ValidationError("case must be submission_ready")
        product = self.catalog.get(product_id)
        if product.status is not ProductStatus.ACTIVE:
            raise ValidationError("only an active Product Card can be submitted")
        result = self.catalog._evaluate(applicant, product)
        if not result.eligible:
            raise ValidationError("applicant does not meet the active Product Card")
        if result.missing_documents:
            raise ValidationError("required documents are missing: " + ", ".join(result.missing_documents))
        if not applicant.client_authorization_ref:
            raise ValidationError("client authorization reference is required")
        if not applicant.permissible_purpose_ref:
            raise ValidationError("permissible-purpose reference is required")
        if not destination.strip():
            raise ValidationError("submission destination is required")
        destination_config = self.destinations.get_active(destination, product_id)
        if product.submission_adapter and product.submission_adapter != destination_config.adapter:
            raise ValidationError("Product Card and destination adapter do not match")

        payload_hash = digest(payload)
        submission_id = f"sub_{secrets.token_hex(8)}"
        timestamp = now_iso()
        with self.store.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM submissions WHERE case_id = ? AND destination = ? AND payload_hash = ?",
                (case_id, destination, payload_hash),
            ).fetchone()
            if existing:
                return self._submission_dict(dict(existing))
            connection.execute(
                """INSERT INTO submissions
                   (submission_id, case_id, product_id, destination, payload_json, payload_hash, state,
                    client_authorization_ref, permissible_purpose_ref, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    submission_id, case_id, product_id, destination, stable_json(payload), payload_hash,
                    SubmissionState.PREPARED.value, applicant.client_authorization_ref,
                    applicant.permissible_purpose_ref, timestamp, timestamp,
                ),
            )
            self.store._audit_tx(
                connection,
                actor="funding-director",
                case_id=case_id,
                action="submission.prepare",
                resource=submission_id,
                policy_decision="approval-required",
                result="prepared",
                verification="payload validated and de-duplicated",
                details={"destination": destination, "payload_hash": payload_hash, "product_id": product_id},
            )
        return self.get_submission(submission_id)

    def request_approval(self, submission_id: str) -> dict[str, Any]:
        submission = self.get_submission(submission_id)
        allowed = {SubmissionState.PREPARED.value, SubmissionState.APPROVAL_REQUESTED.value}
        if submission["state"] == SubmissionState.APPROVED.value:
            with self.store.connection() as connection:
                previous = connection.execute(
                    "SELECT * FROM approvals WHERE approval_id = ?", (submission["approval_id"],)
                ).fetchone()
            if previous and not previous["used_at"] and datetime.fromisoformat(previous["expires_at"]) > datetime.now(UTC):
                raise ValidationError("submission already has an active unused approval")
            allowed.add(SubmissionState.APPROVED.value)
        if submission["state"] not in allowed:
            raise ValidationError("submission is not waiting for approval")
        with self.store.connection() as connection:
            connection.execute(
                "UPDATE submissions SET state = ?, approval_id = '', updated_at = ? WHERE submission_id = ?",
                (SubmissionState.APPROVAL_REQUESTED.value, now_iso(), submission_id),
            )
            self.store._audit_tx(
                connection,
                actor="funding-director",
                case_id=submission["case_id"],
                action="submission.request_approval",
                resource=submission_id,
                policy_decision="approval-required",
                result="pending",
                verification="exact action digest generated from durable frozen fields",
            )
            case = connection.execute(
                "SELECT stage FROM cases WHERE case_id = ?", (submission["case_id"],)
            ).fetchone()
            if case and case["stage"] == CaseStage.SUBMISSION_READY.value:
                connection.execute(
                    "UPDATE cases SET stage = ?, updated_at = ? WHERE case_id = ?",
                    (CaseStage.APPROVAL_REQUESTED.value, now_iso(), submission["case_id"]),
                )
                self.store._audit_tx(
                    connection,
                    actor="funding-director",
                    case_id=submission["case_id"],
                    action="funding_case.transition",
                    resource=submission["case_id"],
                    policy_decision="allow",
                    result=CaseStage.APPROVAL_REQUESTED.value,
                    verification="submission approval request stored in the same transaction",
                    details={"from": CaseStage.SUBMISSION_READY.value, "submission_id": submission_id},
                )
        value = self.get_submission(submission_id)
        return {
            "submission_id": submission_id,
            "action_digest": self.action_digest(value),
            "destination": value["destination"],
            "product_id": value["product_id"],
            "payload": value["payload"],
            "approval_required": True,
        }

    def approve_submission(
        self,
        submission_id: str,
        action_digest: str,
        approver: str,
        expires_at: str,
    ) -> dict[str, Any]:
        submission = self.get_submission(submission_id)
        if submission["state"] != SubmissionState.APPROVAL_REQUESTED.value:
            raise ValidationError("submission is not waiting for approval")
        expected = self.action_digest(submission)
        if not secrets.compare_digest(action_digest, expected):
            raise ValidationError("action digest does not match the proposed submission")
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            raise ValidationError("approval expiry must include a timezone")
        if expiry <= datetime.now(UTC):
            raise ValidationError("approval is already expired")
        if not approver.strip():
            raise ValidationError("approver identity is required")
        approval_id = f"apr_{secrets.token_hex(8)}"
        with self.store.connection() as connection:
            cursor = connection.execute(
                """UPDATE submissions SET state = ?, approval_id = ?, updated_at = ?
                   WHERE submission_id = ? AND state = ?""",
                (
                    SubmissionState.APPROVED.value, approval_id, now_iso(), submission_id,
                    SubmissionState.APPROVAL_REQUESTED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValidationError("submission approval request is no longer pending")
            connection.execute(
                "INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, '')",
                (approval_id, submission_id, expected, approver, now_iso(), expiry.isoformat()),
            )
            self.store._audit_tx(
                connection,
                actor=approver,
                case_id=submission["case_id"],
                action="submission.approve",
                resource=submission_id,
                policy_decision="approved-once",
                result="approved",
                verification="action digest matched",
                approval_id=approval_id,
            )
        return self.get_submission(submission_id)

    def authorize_execution(self, submission_id: str) -> dict[str, Any]:
        self._require_external_writes_enabled()
        submission = self.get_submission(submission_id)
        if submission["state"] != SubmissionState.APPROVED.value:
            raise ValidationError("submission does not have an unused approval")
        with self.store.connection() as connection:
            approval = connection.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (submission["approval_id"],)
            ).fetchone()
        if not approval or approval["used_at"]:
            raise ValidationError("approval is missing or already used")
        expiry = datetime.fromisoformat(approval["expires_at"])
        if expiry <= datetime.now(UTC):
            raise ValidationError("approval has expired")
        if approval["action_digest"] != self.action_digest(submission):
            raise ValidationError("submission changed after approval")
        return {"authorized": True, "approval_id": approval["approval_id"], "submission": submission}

    def _claim_submission(self, submission_id: str) -> dict[str, Any]:
        authorization = self.authorize_execution(submission_id)
        submission = authorization["submission"]
        with self.store.connection() as connection:
            cursor = connection.execute(
                "UPDATE approvals SET used_at = ? WHERE approval_id = ? AND used_at = ''",
                (now_iso(), authorization["approval_id"]),
            )
            if cursor.rowcount != 1:
                raise ValidationError("approval was already consumed")
            cursor = connection.execute(
                "UPDATE submissions SET state = ?, updated_at = ? WHERE submission_id = ? AND state = ?",
                (SubmissionState.EXECUTING.value, now_iso(), submission_id, SubmissionState.APPROVED.value),
            )
            if cursor.rowcount != 1:
                raise ValidationError("submission is no longer approved")
            self.store._audit_tx(
                connection,
                actor="funding-director",
                case_id=submission["case_id"],
                action="submission.claim_execution",
                resource=submission_id,
                policy_decision="approved-once",
                result="executing",
                verification="approval consumed atomically before external write",
                approval_id=authorization["approval_id"],
            )
        return authorization

    def execute_submission(self, submission_id: str) -> dict[str, Any]:
        """Use a reviewed HTTP adapter; never retry an uncertain result automatically."""
        pending = self.get_submission(submission_id)
        destination = self.destinations.get_active(pending["destination"], pending["product_id"])
        if destination.adapter != "http_json":
            raise ValidationError("browser submissions must begin with funding_submission_begin_browser")
        authorization = self._claim_submission(submission_id)
        submission = authorization["submission"]
        try:
            receipt_id, verification = send_http_json(destination, submission["payload"], submission_id)
        except Exception as exc:
            self._fail_submission(submission, authorization["approval_id"], str(exc))
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("submission result is unknown; reconcile before retry") from exc
        return self._finish_submission(submission, authorization["approval_id"], receipt_id, verification)

    def begin_browser_submission(self, submission_id: str) -> dict[str, Any]:
        """Consume approval before a browser portal is allowed to change external state."""
        pending = self.get_submission(submission_id)
        destination = self.destinations.get_active(pending["destination"], pending["product_id"])
        if destination.adapter != "browser_playbook":
            raise ValidationError("this submission uses the reviewed HTTP adapter")
        authorization = self._claim_submission(submission_id)
        return {
            "authorized": True,
            "submission": self.get_submission(submission_id),
            "playbook_ref": destination.playbook_ref,
            "instruction": "Perform exactly the frozen portal action once, then record its receipt or mark it unknown.",
        }

    def record_receipt(self, submission_id: str, receipt_id: str, verification: str) -> dict[str, Any]:
        if not receipt_id.strip() or not verification.strip():
            raise ValidationError("receipt_id and verification are required")
        submission = self.get_submission(submission_id)
        if submission["state"] != SubmissionState.EXECUTING.value or not submission["approval_id"]:
            raise ValidationError("browser submission has not begun with a consumed approval")
        return self._finish_submission(
            submission, submission["approval_id"], receipt_id.strip(), verification.strip()
        )

    def mark_submission_unknown(self, submission_id: str, reason: str) -> dict[str, Any]:
        submission = self.get_submission(submission_id)
        if submission["state"] != SubmissionState.EXECUTING.value or not submission["approval_id"]:
            raise ValidationError("only an executing submission can be marked unknown")
        if not reason.strip():
            raise ValidationError("a reconciliation reason is required")
        self._fail_submission(submission, submission["approval_id"], reason.strip())
        return self.get_submission(submission_id)

    def _finish_submission(
        self,
        submission: dict[str, Any],
        approval_id: str,
        receipt_id: str,
        verification: str,
    ) -> dict[str, Any]:
        with self.store.connection() as connection:
            connection.execute(
                """UPDATE submissions SET state = ?, external_receipt_id = ?, updated_at = ?
                   WHERE submission_id = ?""",
                (SubmissionState.SUBMITTED.value, receipt_id, now_iso(), submission["submission_id"]),
            )
            self.store._audit_tx(
                connection,
                actor="funding-director",
                case_id=submission["case_id"],
                action="submission.record_receipt",
                resource=submission["submission_id"],
                policy_decision="approved-once",
                result="submitted",
                verification=verification,
                approval_id=approval_id,
                details={"receipt_id": receipt_id, "destination": submission["destination"]},
            )
            case = connection.execute(
                "SELECT stage FROM cases WHERE case_id = ?", (submission["case_id"],)
            ).fetchone()
            if case and case["stage"] in {
                CaseStage.SUBMISSION_READY.value,
                CaseStage.APPROVAL_REQUESTED.value,
            }:
                connection.execute(
                    "UPDATE cases SET stage = ?, updated_at = ? WHERE case_id = ?",
                    (CaseStage.SUBMITTED.value, now_iso(), submission["case_id"]),
                )
        return self.get_submission(submission["submission_id"])

    def _fail_submission(self, submission: dict[str, Any], approval_id: str, message: str) -> None:
        with self.store.connection() as connection:
            connection.execute(
                "UPDATE submissions SET state = ?, error = ?, updated_at = ? WHERE submission_id = ?",
                (SubmissionState.FAILED.value, message[:500], now_iso(), submission["submission_id"]),
            )
            self.store._audit_tx(
                connection,
                actor="funding-director",
                case_id=submission["case_id"],
                action="submission.execute",
                resource=submission["submission_id"],
                policy_decision="approved-once",
                result="failed-or-unknown",
                verification="manual reconciliation required; automatic retry disabled",
                approval_id=approval_id,
                details={"error": message[:500]},
            )
            case = connection.execute(
                "SELECT stage FROM cases WHERE case_id = ?", (submission["case_id"],)
            ).fetchone()
            if case and case["stage"] not in {stage.value for stage in TERMINAL_STAGES}:
                connection.execute(
                    "UPDATE cases SET stage = ?, updated_at = ? WHERE case_id = ?",
                    (CaseStage.ESCALATED.value, now_iso(), submission["case_id"]),
                )

    def ghl_search_contacts(self, query: str = "", limit: int = 20) -> dict[str, Any]:
        return GHLClient().search_contacts(query, limit)

    def ghl_get_contact(self, contact_id: str) -> dict[str, Any]:
        return GHLClient().get_contact(contact_id)

    def ghl_search_opportunities(self, pipeline_id: str = "", status: str = "", limit: int = 20) -> dict[str, Any]:
        return GHLClient().search_opportunities(pipeline_id, status, limit)

    def ghl_list_pipelines(self) -> dict[str, Any]:
        return GHLClient().list_pipelines()

    def record_offer(self, offer_value: dict[str, Any]) -> dict[str, Any]:
        offer = FundingOffer.from_dict(offer_value)
        case = self.store.get_case(offer.case_id)
        self.catalog.get(offer.product_id)
        timestamp = now_iso()
        with self.store.connection() as connection:
            connection.execute(
                """INSERT INTO offers (offer_id, case_id, product_id, offer_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(offer_id) DO UPDATE SET
                     offer_json = excluded.offer_json, updated_at = excluded.updated_at""",
                (offer.offer_id, offer.case_id, offer.product_id, stable_json(offer.to_dict()), timestamp, timestamp),
            )
            current = CaseStage(case["stage"])
            if current in {CaseStage.SUBMITTED, CaseStage.FUNDER_FOLLOW_UP}:
                connection.execute(
                    "UPDATE cases SET stage = ?, updated_at = ? WHERE case_id = ?",
                    (CaseStage.OFFERS_RECEIVED.value, timestamp, offer.case_id),
                )
            self.store._audit_tx(
                connection,
                actor="funding-director",
                case_id=offer.case_id,
                action="offer.record",
                resource=offer.offer_id,
                policy_decision="allow",
                result="recorded",
                verification="source receipt retained",
                details={"product_id": offer.product_id, "source_receipt": offer.source_receipt},
            )
        return offer.to_dict()

    def compare_offers(self, case_id: str) -> dict[str, Any]:
        self.store.get_case(case_id)
        with self.store.connection() as connection:
            rows = connection.execute(
                "SELECT offer_json FROM offers WHERE case_id = ? ORDER BY created_at, offer_id", (case_id,)
            ).fetchall()
        offers = [json.loads(row["offer_json"]) for row in rows]
        comparisons = [self._offer_comparison(offer) for offer in offers]
        comparisons.sort(
            key=lambda item: (
                item["known_cost_per_net_dollar"] is None,
                item["known_cost_per_net_dollar"] if item["known_cost_per_net_dollar"] is not None else 0,
            )
        )
        return {
            "case_id": case_id,
            "offer_count": len(comparisons),
            "offers": comparisons,
            "decision": "human-selection-required" if comparisons else "no-offers-recorded",
            "warning": "Do not compare factor rate with APR. Unknown terms remain unknown.",
        }

    @staticmethod
    def _offer_comparison(offer: dict[str, Any]) -> dict[str, Any]:
        total_payback = offer.get("total_payback")
        amount = offer["amount"]
        net_proceeds = offer.get("net_proceeds")
        if net_proceeds is None:
            net_proceeds = max(0, amount - offer.get("fees", 0))
        known_cost = None if total_payback is None else total_payback - amount
        cost_per_dollar = None
        if known_cost is not None and net_proceeds > 0:
            cost_per_dollar = round(known_cost / net_proceeds, 4)
        frequency_factor = {"daily": 260 / 12, "weekly": 52 / 12, "biweekly": 26 / 12, "monthly": 1}
        payment = offer.get("payment_amount")
        monthly_debt_service = None
        if payment is not None and offer.get("payment_frequency") in frequency_factor:
            monthly_debt_service = round(payment * frequency_factor[offer["payment_frequency"]], 2)
        missing = [
            label for field, label in (
                ("total_payback", "total payback"),
                ("payment_amount", "payment amount"),
                ("term_months", "term"),
                ("prepayment_terms", "prepayment terms"),
            ) if offer.get(field) in (None, "")
        ]
        return {
            **offer,
            "net_proceeds_calculated": round(net_proceeds, 2),
            "known_finance_cost": None if known_cost is None else round(known_cost, 2),
            "known_cost_per_net_dollar": cost_per_dollar,
            "estimated_monthly_debt_service": monthly_debt_service,
            "missing_for_decision": missing,
        }

    def prepare_ghl_action(
        self,
        *,
        operation: str,
        target_id: str,
        payload: dict[str, Any],
        case_id: str = "",
    ) -> dict[str, Any]:
        reject_sensitive_keys(payload, "ghl_action")
        if not target_id.strip():
            raise ValidationError("GoHighLevel target ID is required")
        if case_id:
            self.store.get_case(case_id)
        GHLClient.validate_operation(operation, payload)
        payload_hash = digest(payload)
        action_id = f"act_{secrets.token_hex(8)}"
        timestamp = now_iso()
        with self.store.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM external_actions WHERE provider = 'ghl' AND operation = ? AND target_id = ? AND payload_hash = ?",
                (operation, target_id, payload_hash),
            ).fetchone()
            if existing:
                return self._external_action_dict(dict(existing))
            connection.execute(
                """INSERT INTO external_actions
                   (action_id, case_id, provider, operation, target_id, payload_json, payload_hash,
                    state, created_at, updated_at)
                   VALUES (?, ?, 'ghl', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    action_id, case_id, operation, target_id, stable_json(payload), payload_hash,
                    SubmissionState.PREPARED.value, timestamp, timestamp,
                ),
            )
            self.store._audit_tx(
                connection,
                actor="funding-director",
                case_id=case_id,
                action="ghl_action.prepare",
                resource=action_id,
                policy_decision="approval-required",
                result="prepared",
                verification="operation allowlisted and payload de-duplicated",
                details={"operation": operation, "target_id": target_id, "payload_hash": payload_hash},
            )
        return self.get_external_action(action_id)

    def request_external_action_approval(self, action_id: str) -> dict[str, Any]:
        action = self.get_external_action(action_id)
        allowed = {SubmissionState.PREPARED.value, SubmissionState.APPROVAL_REQUESTED.value}
        if action["state"] == SubmissionState.APPROVED.value:
            with self.store.connection() as connection:
                previous = connection.execute(
                    "SELECT * FROM external_action_approvals WHERE approval_id = ?",
                    (action["approval_id"],),
                ).fetchone()
            if previous and not previous["used_at"] and datetime.fromisoformat(previous["expires_at"]) > datetime.now(UTC):
                raise ValidationError("external action already has an active unused approval")
            allowed.add(SubmissionState.APPROVED.value)
        if action["state"] not in allowed:
            raise ValidationError("external action is not waiting for approval")
        with self.store.connection() as connection:
            connection.execute(
                "UPDATE external_actions SET state = ?, approval_id = '', updated_at = ? WHERE action_id = ?",
                (SubmissionState.APPROVAL_REQUESTED.value, now_iso(), action_id),
            )
            self.store._audit_tx(
                connection,
                actor="funding-director",
                case_id=action["case_id"],
                action="ghl_action.request_approval",
                resource=action_id,
                policy_decision="approval-required",
                result="pending",
                verification="exact CRM action digest generated from durable frozen fields",
            )
        action = self.get_external_action(action_id)
        return {**action, "action_digest": self.external_action_digest(action), "approval_required": True}

    def approve_external_action(self, action_id: str, action_digest: str, approver: str, expires_at: str) -> dict[str, Any]:
        action = self.get_external_action(action_id)
        expected = self.external_action_digest(action)
        if action["state"] != SubmissionState.APPROVAL_REQUESTED.value:
            raise ValidationError("external action is not waiting for approval")
        if not secrets.compare_digest(action_digest, expected):
            raise ValidationError("action digest does not match the proposed external action")
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expiry.tzinfo is None or expiry <= datetime.now(UTC):
            raise ValidationError("approval expiry must be a future timezone-aware value")
        if not approver.strip():
            raise ValidationError("approver identity is required")
        approval_id = f"apr_{secrets.token_hex(8)}"
        with self.store.connection() as connection:
            cursor = connection.execute(
                """UPDATE external_actions SET state = ?, approval_id = ?, updated_at = ?
                   WHERE action_id = ? AND state = ?""",
                (
                    SubmissionState.APPROVED.value, approval_id, now_iso(), action_id,
                    SubmissionState.APPROVAL_REQUESTED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ValidationError("external action approval request is no longer pending")
            connection.execute(
                "INSERT INTO external_action_approvals VALUES (?, ?, ?, ?, ?, ?, '')",
                (approval_id, action_id, expected, approver, now_iso(), expiry.isoformat()),
            )
            self.store._audit_tx(
                connection,
                actor=approver,
                case_id=action["case_id"],
                action="ghl_action.approve",
                resource=action_id,
                policy_decision="approved-once",
                result="approved",
                verification="action digest matched",
                approval_id=approval_id,
            )
        return self.get_external_action(action_id)

    def execute_ghl_action(self, action_id: str) -> dict[str, Any]:
        self._require_external_writes_enabled()
        action = self.get_external_action(action_id)
        if action["provider"] != "ghl" or action["state"] != SubmissionState.APPROVED.value:
            raise ValidationError("GoHighLevel action does not have an unused approval")
        with self.store.connection() as connection:
            approval = connection.execute(
                "SELECT * FROM external_action_approvals WHERE approval_id = ?", (action["approval_id"],)
            ).fetchone()
            if not approval or approval["used_at"]:
                raise ValidationError("approval is missing or already used")
            if datetime.fromisoformat(approval["expires_at"]) <= datetime.now(UTC):
                raise ValidationError("approval has expired")
            if approval["action_digest"] != self.external_action_digest(action):
                raise ValidationError("external action changed after approval")
            cursor = connection.execute(
                "UPDATE external_action_approvals SET used_at = ? WHERE approval_id = ? AND used_at = ''",
                (now_iso(), approval["approval_id"]),
            )
            if cursor.rowcount != 1:
                raise ValidationError("approval was already consumed")
            connection.execute(
                "UPDATE external_actions SET state = ?, updated_at = ? WHERE action_id = ?",
                (SubmissionState.EXECUTING.value, now_iso(), action_id),
            )
        try:
            result = GHLClient().execute(action["operation"], action["target_id"], action["payload"])
            receipt_id = self._ghl_receipt(result, action_id)
        except Exception as exc:
            with self.store.connection() as connection:
                connection.execute(
                    "UPDATE external_actions SET state = ?, error = ?, updated_at = ? WHERE action_id = ?",
                    (SubmissionState.FAILED.value, str(exc)[:500], now_iso(), action_id),
                )
                self.store._audit_tx(
                    connection,
                    actor="funding-director",
                    case_id=action["case_id"],
                    action="ghl_action.execute",
                    resource=action_id,
                    policy_decision="approved-once",
                    result="failed-or-unknown",
                    verification="manual reconciliation required; automatic retry disabled",
                    approval_id=approval["approval_id"],
                    details={"operation": action["operation"], "error": str(exc)[:500]},
                )
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("GoHighLevel result is unknown; reconcile before retry") from exc
        with self.store.connection() as connection:
            connection.execute(
                "UPDATE external_actions SET state = ?, external_receipt_id = ?, updated_at = ? WHERE action_id = ?",
                (SubmissionState.SUBMITTED.value, receipt_id, now_iso(), action_id),
            )
            self.store._audit_tx(
                connection,
                actor="funding-director",
                case_id=action["case_id"],
                action="ghl_action.execute",
                resource=action_id,
                policy_decision="approved-once",
                result="completed",
                verification="GoHighLevel returned a successful JSON response",
                approval_id=approval["approval_id"],
                details={"operation": action["operation"], "receipt_id": receipt_id},
            )
        return self.get_external_action(action_id)

    def get_external_action(self, action_id: str) -> dict[str, Any]:
        with self.store.connection() as connection:
            row = connection.execute("SELECT * FROM external_actions WHERE action_id = ?", (action_id,)).fetchone()
        if not row:
            raise ValidationError(f"unknown external action: {action_id}")
        return self._external_action_dict(dict(row))

    @staticmethod
    def _external_action_dict(value: dict[str, Any]) -> dict[str, Any]:
        value["payload"] = json.loads(value.pop("payload_json"))
        return value

    @staticmethod
    def external_action_digest(action: dict[str, Any]) -> str:
        return digest({
            "action_id": action["action_id"],
            "case_id": action["case_id"],
            "provider": action["provider"],
            "operation": action["operation"],
            "target_id": action["target_id"],
            "payload_hash": action["payload_hash"],
        })

    @staticmethod
    def _ghl_receipt(result: dict[str, Any], fallback: str) -> str:
        for key in ("id", "traceId"):
            if result.get(key):
                return str(result[key])
        for container in ("contact", "opportunity", "note"):
            value = result.get(container)
            if isinstance(value, dict) and value.get("id"):
                return str(value["id"])
        return fallback

    def get_submission(self, submission_id: str) -> dict[str, Any]:
        with self.store.connection() as connection:
            row = connection.execute(
                "SELECT * FROM submissions WHERE submission_id = ?", (submission_id,)
            ).fetchone()
        if not row:
            raise ValidationError(f"unknown submission: {submission_id}")
        return self._submission_dict(dict(row))

    @staticmethod
    def _submission_dict(value: dict[str, Any]) -> dict[str, Any]:
        value["payload"] = json.loads(value.pop("payload_json"))
        return value

    @staticmethod
    def action_digest(submission: dict[str, Any]) -> str:
        return digest({
            "submission_id": submission["submission_id"],
            "case_id": submission["case_id"],
            "product_id": submission["product_id"],
            "destination": submission["destination"],
            "payload_hash": submission["payload_hash"],
            "client_authorization_ref": submission["client_authorization_ref"],
            "permissible_purpose_ref": submission["permissible_purpose_ref"],
        })
