"""Funding-domain models and fail-closed input validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import math
import re
from typing import Any


class CaseStage(StrEnum):
    RECEIVED = "received"
    COMPLETENESS_REVIEW = "completeness_review"
    UNDERWRITING_REVIEW = "underwriting_review"
    STRATEGY_READY = "strategy_ready"
    DOCUMENTS_NEEDED = "documents_needed"
    SUBMISSION_READY = "submission_ready"
    APPROVAL_REQUESTED = "approval_requested"
    SUBMITTED = "submitted"
    FUNDER_FOLLOW_UP = "funder_follow_up"
    OFFERS_RECEIVED = "offers_received"
    CLIENT_DECISION = "client_decision"
    APPROVED = "approved"
    FUNDED = "funded"
    NURTURE = "nurture"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    BLOCKED = "blocked"
    ESCALATED = "escalated"


TERMINAL_STAGES = {
    CaseStage.FUNDED,
    CaseStage.DECLINED,
    CaseStage.WITHDRAWN,
}


ALLOWED_TRANSITIONS: dict[CaseStage, set[CaseStage]] = {
    CaseStage.RECEIVED: {CaseStage.COMPLETENESS_REVIEW, CaseStage.BLOCKED, CaseStage.WITHDRAWN},
    CaseStage.COMPLETENESS_REVIEW: {
        CaseStage.UNDERWRITING_REVIEW,
        CaseStage.DOCUMENTS_NEEDED,
        CaseStage.BLOCKED,
        CaseStage.WITHDRAWN,
    },
    CaseStage.UNDERWRITING_REVIEW: {
        CaseStage.STRATEGY_READY,
        CaseStage.DOCUMENTS_NEEDED,
        CaseStage.NURTURE,
        CaseStage.DECLINED,
        CaseStage.ESCALATED,
    },
    CaseStage.STRATEGY_READY: {
        CaseStage.DOCUMENTS_NEEDED,
        CaseStage.SUBMISSION_READY,
        CaseStage.NURTURE,
        CaseStage.ESCALATED,
    },
    CaseStage.DOCUMENTS_NEEDED: {
        CaseStage.COMPLETENESS_REVIEW,
        CaseStage.SUBMISSION_READY,
        CaseStage.BLOCKED,
        CaseStage.WITHDRAWN,
    },
    CaseStage.SUBMISSION_READY: {
        CaseStage.APPROVAL_REQUESTED,
        CaseStage.SUBMITTED,
        CaseStage.ESCALATED,
    },
    CaseStage.APPROVAL_REQUESTED: {
        CaseStage.SUBMITTED,
        CaseStage.SUBMISSION_READY,
        CaseStage.ESCALATED,
    },
    CaseStage.SUBMITTED: {CaseStage.FUNDER_FOLLOW_UP, CaseStage.OFFERS_RECEIVED, CaseStage.DECLINED},
    CaseStage.FUNDER_FOLLOW_UP: {CaseStage.OFFERS_RECEIVED, CaseStage.DECLINED, CaseStage.ESCALATED},
    CaseStage.OFFERS_RECEIVED: {CaseStage.CLIENT_DECISION, CaseStage.DECLINED},
    CaseStage.CLIENT_DECISION: {CaseStage.APPROVED, CaseStage.NURTURE, CaseStage.WITHDRAWN},
    CaseStage.APPROVED: {CaseStage.FUNDED, CaseStage.FUNDER_FOLLOW_UP, CaseStage.ESCALATED},
    CaseStage.NURTURE: {CaseStage.COMPLETENESS_REVIEW, CaseStage.WITHDRAWN},
    CaseStage.BLOCKED: {CaseStage.COMPLETENESS_REVIEW, CaseStage.ESCALATED, CaseStage.WITHDRAWN},
    CaseStage.ESCALATED: {
        CaseStage.COMPLETENESS_REVIEW,
        CaseStage.UNDERWRITING_REVIEW,
        CaseStage.SUBMISSION_READY,
        CaseStage.WITHDRAWN,
    },
}


class ProductStatus(StrEnum):
    DRAFT = "draft"
    VERIFIED = "verified"
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"
    BLOCKED = "blocked"


class SubmissionState(StrEnum):
    PREPARED = "prepared"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVED = "approved"
    EXECUTING = "executing"
    SUBMITTED = "submitted"
    FAILED = "failed"
    CANCELLED = "cancelled"


SENSITIVE_KEY = re.compile(
    r"(^|_)(ssn|social_security|bank_account|routing_number|password|passcode|credential|"
    r"identityiq|credit_monitoring_login|api_key|access_token|refresh_token|secret)($|_)",
    re.IGNORECASE,
)


class ValidationError(ValueError):
    """Raised when a funding action is unsafe or incomplete."""


def is_finite_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def reject_sensitive_keys(value: Any, path: str = "payload") -> None:
    """Reject secrets and unnecessary high-risk identifiers recursively."""
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if SENSITIVE_KEY.search(key_text):
                raise ValidationError(f"{path}.{key_text} is prohibited")
            reject_sensitive_keys(item, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_sensitive_keys(item, f"{path}[{index}]")


@dataclass(slots=True)
class ApplicantProfile:
    case_id: str
    requested_amount: int
    purpose: str
    state: str
    industry: str = ""
    business_name: str = ""
    entity_type: str = ""
    ownership_percent: float | None = None
    monthly_revenue: int | None = None
    annual_revenue: int | None = None
    time_in_business_months: int | None = None
    credit_score: int | None = None
    revolving_utilization_percent: float | None = None
    recent_inquiries: int | None = None
    recent_derogatories: int | None = None
    average_daily_balance: int | None = None
    negative_days_last_3_months: int | None = None
    nsf_count_last_3_months: int | None = None
    existing_debt_balance: int | None = None
    existing_debt_monthly_payment: int | None = None
    existing_mca_count: int | None = None
    has_collateral: bool = False
    has_invoices: bool = False
    owns_real_estate: bool = False
    documents: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    ghl_contact_id: str = ""
    funding_machine_contact_id: str = ""
    client_authorization_ref: str = ""
    permissible_purpose_ref: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ApplicantProfile":
        reject_sensitive_keys(value, "applicant")
        profile = cls(**value)
        profile.validate()
        return profile

    def validate(self) -> None:
        if not isinstance(self.case_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,63}", self.case_id):
            raise ValidationError("case_id must be a safe 3-64 character identifier")
        if not is_finite_number(self.requested_amount) or self.requested_amount <= 0:
            raise ValidationError("requested_amount must be positive")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ValidationError("purpose is required")
        if not isinstance(self.state, str) or not re.fullmatch(r"[A-Za-z]{2}", self.state):
            raise ValidationError("state must be a two-letter code")
        if self.credit_score is not None and (
            not is_finite_number(self.credit_score) or not 300 <= self.credit_score <= 850
        ):
            raise ValidationError("credit_score must be between 300 and 850")
        if self.ownership_percent is not None and (
            not is_finite_number(self.ownership_percent) or not 0 < self.ownership_percent <= 100
        ):
            raise ValidationError("ownership_percent must be greater than 0 and at most 100")
        if self.revolving_utilization_percent is not None and (
            not is_finite_number(self.revolving_utilization_percent)
            or not 0 <= self.revolving_utilization_percent <= 200
        ):
            raise ValidationError("revolving_utilization_percent must be between 0 and 200")
        for name in (
            "monthly_revenue",
            "annual_revenue",
            "time_in_business_months",
            "recent_inquiries",
            "recent_derogatories",
            "average_daily_balance",
            "negative_days_last_3_months",
            "nsf_count_last_3_months",
            "existing_debt_balance",
            "existing_debt_monthly_payment",
            "existing_mca_count",
        ):
            number = getattr(self, name)
            if number is not None and (not is_finite_number(number) or number < 0):
                raise ValidationError(f"{name} cannot be negative")
        for name in ("has_collateral", "has_invoices", "owns_real_estate"):
            if not isinstance(getattr(self, name), bool):
                raise ValidationError(f"{name} must be true or false")
        for name in ("documents", "flags"):
            values = getattr(self, name)
            if not isinstance(values, list) or not all(isinstance(item, str) and item.strip() for item in values):
                raise ValidationError(f"{name} must contain non-empty strings")
        for name in (
            "industry", "business_name", "entity_type", "ghl_contact_id",
            "funding_machine_contact_id", "client_authorization_ref", "permissible_purpose_ref",
        ):
            if not isinstance(getattr(self, name), str):
                raise ValidationError(f"{name} must be text")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProductCard:
    product_id: str
    name: str
    family: str
    status: ProductStatus
    business_purpose_only: bool
    requirements: dict[str, Any]
    required_documents: list[str]
    exclusions: list[str]
    sources: list[dict[str, str]]
    effective_date: str
    expires_at: str
    provider_id: str = ""
    submission_adapter: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ProductCard":
        item = dict(value)
        item["status"] = ProductStatus(item["status"])
        return cls(**item)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        return value


@dataclass(slots=True)
class FundingOffer:
    offer_id: str
    case_id: str
    product_id: str
    provider_name: str
    amount: float
    total_payback: float | None
    payment_amount: float | None
    payment_frequency: str
    term_months: float | None
    fees: float = 0
    net_proceeds: float | None = None
    apr_percent: float | None = None
    interest_rate_percent: float | None = None
    factor_rate: float | None = None
    collateral: str = ""
    personal_guarantee: str = "unknown"
    prepayment_terms: str = ""
    expires_at: str = ""
    source_receipt: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FundingOffer":
        reject_sensitive_keys(value, "offer")
        offer = cls(**value)
        offer.validate()
        return offer

    def validate(self) -> None:
        for name in ("offer_id", "case_id", "product_id", "provider_name"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValidationError(f"{name} is required")
        if not is_finite_number(self.amount) or self.amount <= 0:
            raise ValidationError("offer amount must be positive")
        if self.total_payback is not None and (
            not is_finite_number(self.total_payback) or self.total_payback < self.amount
        ):
            raise ValidationError("total_payback cannot be less than offer amount")
        if self.factor_rate is not None and (
            not is_finite_number(self.factor_rate) or self.factor_rate < 1
        ):
            raise ValidationError("factor_rate cannot be less than 1")
        for name in (
            "total_payback", "payment_amount", "term_months", "fees", "net_proceeds",
            "apr_percent", "interest_rate_percent", "factor_rate",
        ):
            value = getattr(self, name)
            if value is not None and (not is_finite_number(value) or value < 0):
                raise ValidationError(f"{name} cannot be negative")
        if not isinstance(self.payment_frequency, str) or self.payment_frequency not in {
            "daily", "weekly", "biweekly", "monthly", "irregular", "unknown"
        }:
            raise ValidationError("payment_frequency is invalid")
        if not isinstance(self.personal_guarantee, str) or self.personal_guarantee not in {"yes", "no", "unknown"}:
            raise ValidationError("personal_guarantee must be yes, no, or unknown")
        if not isinstance(self.source_receipt, str) or not self.source_receipt.strip():
            raise ValidationError("source_receipt is required")
        for name in ("collateral", "prepayment_terms", "expires_at", "notes"):
            if not isinstance(getattr(self, name), str):
                raise ValidationError(f"{name} must be text")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
