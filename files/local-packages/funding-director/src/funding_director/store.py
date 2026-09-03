"""Crash-safe workflow, approval, and audit state separate from chat history."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from .models import ALLOWED_TRANSITIONS, ApplicantProfile, CaseStage, ValidationError


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class FundingStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    stage TEXT NOT NULL,
                    applicant_json TEXT NOT NULL,
                    recommendation_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS submissions (
                    submission_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(case_id),
                    product_id TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    client_authorization_ref TEXT NOT NULL,
                    permissible_purpose_ref TEXT NOT NULL,
                    approval_id TEXT NOT NULL DEFAULT '',
                    external_receipt_id TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(case_id, destination, payload_hash)
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
                    action_digest TEXT NOT NULL,
                    approver TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS standing_playbooks (
                    playbook_id TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    UNIQUE(product_id, destination, version)
                );
                CREATE TABLE IF NOT EXISTS external_actions (
                    action_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    approval_id TEXT NOT NULL DEFAULT '',
                    external_receipt_id TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(provider, operation, target_id, payload_hash)
                );
                CREATE TABLE IF NOT EXISTS external_action_approvals (
                    approval_id TEXT PRIMARY KEY,
                    action_id TEXT NOT NULL REFERENCES external_actions(action_id),
                    action_digest TEXT NOT NULL,
                    approver TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS offers (
                    offer_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(case_id),
                    product_id TEXT NOT NULL,
                    offer_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    case_id TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    policy_decision TEXT NOT NULL,
                    approval_id TEXT NOT NULL DEFAULT '',
                    result TEXT NOT NULL,
                    verification TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS approvals_submission_idx
                    ON approvals(submission_id, approved_at);
                CREATE INDEX IF NOT EXISTS external_approvals_action_idx
                    ON external_action_approvals(action_id, approved_at);
                """
            )
            self._migrate_repeatable_approvals(connection)

    @staticmethod
    def _migrate_repeatable_approvals(connection: sqlite3.Connection) -> None:
        """Drop legacy one-row constraints while retaining every approval record."""
        migrations = (
            (
                "approvals",
                "submission_id",
                "submissions(submission_id)",
                "approval_id, submission_id, action_digest, approver, approved_at, expires_at, used_at",
            ),
            (
                "external_action_approvals",
                "action_id",
                "external_actions(action_id)",
                "approval_id, action_id, action_digest, approver, approved_at, expires_at, used_at",
            ),
        )
        for table, foreign_key, reference, columns in migrations:
            row = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
            ).fetchone()
            sql = row["sql"] if row else ""
            if f"{foreign_key} TEXT NOT NULL UNIQUE" not in sql:
                continue
            legacy = f"{table}_legacy_unique"
            connection.execute(f"ALTER TABLE {table} RENAME TO {legacy}")
            connection.execute(
                f"""CREATE TABLE {table} (
                    approval_id TEXT PRIMARY KEY,
                    {foreign_key} TEXT NOT NULL REFERENCES {reference},
                    action_digest TEXT NOT NULL,
                    approver TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT NOT NULL DEFAULT ''
                )"""
            )
            connection.execute(f"INSERT INTO {table} ({columns}) SELECT {columns} FROM {legacy}")
            connection.execute(f"DROP TABLE {legacy}")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS approvals_submission_idx ON approvals(submission_id, approved_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS external_approvals_action_idx ON external_action_approvals(action_id, approved_at)"
        )

    def create_case(self, applicant: ApplicantProfile, actor: str = "funding-director") -> dict[str, Any]:
        timestamp = now_iso()
        with self.connection() as connection:
            try:
                connection.execute(
                    "INSERT INTO cases VALUES (?, ?, ?, '{}', ?, ?)",
                    (applicant.case_id, CaseStage.RECEIVED.value, json.dumps(applicant.to_dict()), timestamp, timestamp),
                )
            except sqlite3.IntegrityError as exc:
                raise ValidationError(f"case already exists: {applicant.case_id}") from exc
            self._audit_tx(
                connection,
                actor=actor,
                case_id=applicant.case_id,
                action="funding_case.create",
                resource=applicant.case_id,
                policy_decision="allow",
                result="created",
                verification="case row committed",
            )
        return self.get_case(applicant.case_id)

    def get_case(self, case_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not row:
            raise ValidationError(f"unknown case: {case_id}")
        value = dict(row)
        value["applicant"] = json.loads(value.pop("applicant_json"))
        value["recommendation"] = json.loads(value.pop("recommendation_json"))
        return value

    def save_recommendation(self, case_id: str, recommendation: dict[str, Any]) -> None:
        timestamp = now_iso()
        with self.connection() as connection:
            cursor = connection.execute(
                "UPDATE cases SET recommendation_json = ?, updated_at = ? WHERE case_id = ?",
                (json.dumps(recommendation), timestamp, case_id),
            )
            if cursor.rowcount != 1:
                raise ValidationError(f"unknown case: {case_id}")
            self._audit_tx(
                connection,
                actor="funding-director",
                case_id=case_id,
                action="funding_strategy.save",
                resource=case_id,
                policy_decision="allow",
                result="saved",
                verification="recommendation row updated",
            )

    def transition(self, case_id: str, target: CaseStage, reason: str, actor: str = "funding-director") -> dict[str, Any]:
        if not reason.strip():
            raise ValidationError("a transition reason is required")
        with self.connection() as connection:
            row = connection.execute("SELECT stage FROM cases WHERE case_id = ?", (case_id,)).fetchone()
            if not row:
                raise ValidationError(f"unknown case: {case_id}")
            current = CaseStage(row["stage"])
            if target not in ALLOWED_TRANSITIONS.get(current, set()):
                raise ValidationError(f"invalid transition: {current.value} -> {target.value}")
            connection.execute(
                "UPDATE cases SET stage = ?, updated_at = ? WHERE case_id = ?",
                (target.value, now_iso(), case_id),
            )
            self._audit_tx(
                connection,
                actor=actor,
                case_id=case_id,
                action="funding_case.transition",
                resource=case_id,
                policy_decision="allow",
                result=target.value,
                verification="stage read back from durable case state",
                details={"from": current.value, "to": target.value, "reason": reason},
            )
        return self.get_case(case_id)

    def audit(
        self,
        *,
        actor: str,
        case_id: str,
        action: str,
        resource: str,
        policy_decision: str,
        result: str,
        verification: str,
        approval_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.connection() as connection:
            self._audit_tx(
                connection,
                actor=actor,
                case_id=case_id,
                action=action,
                resource=resource,
                policy_decision=policy_decision,
                result=result,
                verification=verification,
                approval_id=approval_id,
                details=details,
            )

    @staticmethod
    def _audit_tx(
        connection: sqlite3.Connection,
        *,
        actor: str,
        case_id: str,
        action: str,
        resource: str,
        policy_decision: str,
        result: str,
        verification: str,
        approval_id: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """INSERT INTO audit_events
               (timestamp, actor, case_id, action, resource, policy_decision, approval_id, result, verification, details_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                now_iso(), actor, case_id, action, resource, policy_decision,
                approval_id, result, verification, json.dumps(details or {}),
            ),
        )
