"""Versioned funding-product catalog and deterministic eligibility checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import math
from pathlib import Path
import re
from typing import Any

from .models import ApplicantProfile, ProductCard, ProductStatus, ValidationError


@dataclass(slots=True)
class ProductMatch:
    product: ProductCard
    eligible: bool
    score: int
    reasons: list[str]
    blockers: list[str]
    missing_documents: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "product": self.product.to_dict(),
            "eligible": self.eligible,
            "score": self.score,
            "reasons": self.reasons,
            "blockers": self.blockers,
            "missing_documents": self.missing_documents,
        }


class ProductCatalog:
    REQUIREMENT_KEYS = {
        "allowed_states",
        "max_amount",
        "max_existing_mca_count",
        "max_negative_days_last_3_months",
        "max_nsf_count_last_3_months",
        "max_recent_derogatories",
        "max_recent_inquiries",
        "max_revolving_utilization_percent",
        "min_amount",
        "min_annual_revenue",
        "min_average_daily_balance",
        "min_credit_score",
        "min_monthly_revenue",
        "min_ownership_percent",
        "min_time_in_business_months",
        "requires_collateral",
        "requires_invoices",
        "requires_real_estate",
    }
    BOOLEAN_REQUIREMENTS = {"requires_collateral", "requires_invoices", "requires_real_estate"}

    def __init__(self, path: Path):
        self.path = path
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValidationError("unsupported product catalog schema")
        self.products = [ProductCard.from_dict(item) for item in payload.get("products", [])]
        ids = [item.product_id for item in self.products]
        if len(ids) != len(set(ids)):
            raise ValidationError("product IDs must be unique")
        for product in self.products:
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", product.product_id):
                raise ValidationError("product IDs must be safe lowercase identifiers")
            if not product.name.strip() or not product.family.strip():
                raise ValidationError("product name and family are required")
            if not isinstance(product.requirements, dict):
                raise ValidationError(f"{product.product_id}.requirements must be an object")
            unknown_rules = sorted(set(product.requirements) - self.REQUIREMENT_KEYS)
            if unknown_rules:
                raise ValidationError(
                    f"{product.product_id} has unsupported requirement keys: {', '.join(unknown_rules)}"
                )
            for key, value in product.requirements.items():
                if key in self.BOOLEAN_REQUIREMENTS:
                    if not isinstance(value, bool):
                        raise ValidationError(f"{product.product_id}.{key} must be true or false")
                elif key == "allowed_states":
                    if not isinstance(value, list) or not value or not all(
                        isinstance(state, str) and re.fullmatch(r"[A-Z]{2}", state)
                        for state in value
                    ):
                        raise ValidationError(f"{product.product_id}.allowed_states must contain uppercase state codes")
                elif (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < 0
                ):
                    raise ValidationError(f"{product.product_id}.{key} must be a non-negative number")
            for field_name, values in (
                ("required_documents", product.required_documents),
                ("exclusions", product.exclusions),
            ):
                if not isinstance(values, list) or not all(isinstance(item, str) and item.strip() for item in values):
                    raise ValidationError(f"{product.product_id}.{field_name} must contain non-empty strings")
                if len(values) != len(set(values)):
                    raise ValidationError(f"{product.product_id}.{field_name} must not contain duplicates")
            if not isinstance(product.sources, list) or not product.sources or not all(
                isinstance(source, dict)
                and isinstance(source.get("type"), str)
                and isinstance(source.get("url"), str)
                and source.get("type", "").strip()
                and source.get("url", "").strip()
                for source in product.sources
            ):
                raise ValidationError(f"{product.product_id} requires at least one structured source")
            if product.expires_at:
                date.fromisoformat(product.expires_at)
            if product.effective_date:
                date.fromisoformat(product.effective_date)
            if product.effective_date and product.expires_at:
                if date.fromisoformat(product.effective_date) > date.fromisoformat(product.expires_at):
                    raise ValidationError(f"{product.product_id} effective date is after its expiry")
            if product.status is ProductStatus.ACTIVE:
                if not product.business_purpose_only:
                    raise ValidationError("active Product Cards must be business-purpose only")
                if not product.provider_id or not product.submission_adapter:
                    raise ValidationError("active Product Cards require provider_id and submission_adapter")
                if not any(source.get("type") == "provider-evidence" for source in product.sources):
                    raise ValidationError("active Product Cards require current provider evidence")

    def get(self, product_id: str) -> ProductCard:
        for product in self.products:
            if product.product_id == product_id:
                return product
        raise ValidationError(f"unknown product_id: {product_id}")

    def match(self, applicant: ApplicantProfile, include_inactive: bool = False) -> list[ProductMatch]:
        matches = []
        for product in self.products:
            if not include_inactive and product.status is not ProductStatus.ACTIVE:
                continue
            matches.append(self._evaluate(applicant, product))
        return sorted(matches, key=lambda item: (item.eligible, item.score), reverse=True)

    def _evaluate(self, applicant: ApplicantProfile, product: ProductCard) -> ProductMatch:
        blockers: list[str] = []
        reasons: list[str] = []
        requirements = product.requirements

        if product.status is not ProductStatus.ACTIVE:
            blockers.append(f"product status is {product.status.value}, not active")
        if product.effective_date and date.fromisoformat(product.effective_date) > date.today():
            blockers.append("product card is not effective yet")
        if product.expires_at and date.fromisoformat(product.expires_at) < date.today():
            blockers.append("product card is expired")
        if requirements.get("allowed_states") and applicant.state.upper() not in requirements["allowed_states"]:
            blockers.append("applicant state is not eligible")
        if applicant.industry and applicant.industry.lower() in {item.lower() for item in product.exclusions}:
            blockers.append("industry is excluded")

        numeric_checks = (
            ("credit_score", "min_credit_score", "credit score"),
            ("monthly_revenue", "min_monthly_revenue", "monthly revenue"),
            ("annual_revenue", "min_annual_revenue", "annual revenue"),
            ("time_in_business_months", "min_time_in_business_months", "time in business"),
            ("ownership_percent", "min_ownership_percent", "ownership percentage"),
            ("average_daily_balance", "min_average_daily_balance", "average daily balance"),
        )
        for applicant_field, rule_field, label in numeric_checks:
            minimum = requirements.get(rule_field)
            if minimum is None:
                continue
            actual = getattr(applicant, applicant_field)
            if actual is None:
                blockers.append(f"{label} is missing")
            elif actual < minimum:
                blockers.append(f"{label} is below the verified minimum")
            else:
                reasons.append(f"{label} meets the verified minimum")

        maximum_checks = (
            ("revolving_utilization_percent", "max_revolving_utilization_percent", "revolving utilization"),
            ("recent_inquiries", "max_recent_inquiries", "recent inquiries"),
            ("recent_derogatories", "max_recent_derogatories", "recent derogatories"),
            ("negative_days_last_3_months", "max_negative_days_last_3_months", "negative-balance days"),
            ("nsf_count_last_3_months", "max_nsf_count_last_3_months", "NSF count"),
            ("existing_mca_count", "max_existing_mca_count", "existing MCA count"),
        )
        for applicant_field, rule_field, label in maximum_checks:
            maximum_value = requirements.get(rule_field)
            if maximum_value is None:
                continue
            actual = getattr(applicant, applicant_field)
            if actual is None:
                blockers.append(f"{label} is missing")
            elif actual > maximum_value:
                blockers.append(f"{label} exceeds the verified maximum")
            else:
                reasons.append(f"{label} is within the verified maximum")

        boolean_checks = (
            ("requires_collateral", applicant.has_collateral, "eligible collateral"),
            ("requires_invoices", applicant.has_invoices, "eligible invoices"),
            ("requires_real_estate", applicant.owns_real_estate, "eligible real estate"),
        )
        for rule, actual, label in boolean_checks:
            if requirements.get(rule) and not actual:
                blockers.append(f"{label} is required")
            elif requirements.get(rule):
                reasons.append(f"applicant has {label}")

        maximum = requirements.get("max_amount")
        minimum = requirements.get("min_amount")
        if maximum is not None and applicant.requested_amount > maximum:
            blockers.append("requested amount exceeds the verified maximum")
        elif minimum is not None and applicant.requested_amount < minimum:
            blockers.append("requested amount is below the verified minimum")
        else:
            reasons.append("requested amount is within the documented range")

        missing_documents = sorted(set(product.required_documents) - set(applicant.documents))
        score = max(0, 100 - 20 * len(blockers) - 5 * len(missing_documents))
        return ProductMatch(
            product=product,
            eligible=not blockers,
            score=score,
            reasons=reasons,
            blockers=blockers,
            missing_documents=missing_documents,
        )
