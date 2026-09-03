"""Allowlisted submission destinations and the small HTTP execution adapter."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib import error, parse, request

from .models import ValidationError


@dataclass(slots=True)
class Destination:
    destination_id: str
    name: str
    status: str
    adapter: str
    product_ids: list[str]
    url: str = ""
    method: str = "POST"
    auth_env: str = ""
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    receipt_field: str = "id"
    playbook_ref: str = ""


class NoRedirect(request.HTTPRedirectHandler):
    """Treat redirects as an ambiguous provider result instead of following them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


def _validate_public_https_url(value: str) -> None:
    parsed = parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValidationError("active HTTP destination must be a credential-free HTTPS URL")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".local"):
        raise ValidationError("submission destination cannot target a local host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if not address.is_global:
        raise ValidationError("submission destination cannot target a private or reserved address")


class DestinationCatalog:
    def __init__(self, path: Path):
        self.path = path
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValidationError("unsupported destination catalog schema")
        self.destinations = [Destination(**item) for item in payload.get("destinations", [])]
        ids = [item.destination_id for item in self.destinations]
        if len(ids) != len(set(ids)):
            raise ValidationError("destination IDs must be unique")
        for destination in self.destinations:
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", destination.destination_id):
                raise ValidationError("destination IDs must be safe lowercase identifiers")
            if not isinstance(destination.name, str) or not destination.name.strip():
                raise ValidationError("destination name is required")
            if destination.status not in {"draft", "active", "paused", "blocked"}:
                raise ValidationError("destination status is invalid")
            if destination.adapter not in {"http_json", "browser_playbook"}:
                raise ValidationError("destination adapter is not allowlisted")
            if not isinstance(destination.product_ids, list) or not all(
                isinstance(product_id, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", product_id)
                for product_id in destination.product_ids
            ):
                raise ValidationError("destination product_ids must contain safe product identifiers")
            if len(destination.product_ids) != len(set(destination.product_ids)):
                raise ValidationError("destination product IDs must be unique")
            if destination.auth_env and not re.fullmatch(r"[A-Z][A-Z0-9_]{2,79}", destination.auth_env):
                raise ValidationError("destination auth_env must name a dedicated environment variable")
            if destination.status != "active":
                continue
            if not destination.product_ids:
                raise ValidationError("active destination requires at least one Product Card")
            if destination.adapter == "http_json":
                _validate_public_https_url(destination.url)
                if destination.method.upper() != "POST" or not destination.receipt_field.strip():
                    raise ValidationError("active HTTP destination requires POST and a receipt field")
            elif not destination.playbook_ref.startswith("private://"):
                raise ValidationError("active browser destination requires a private reviewed playbook reference")

    def get_active(self, destination_id: str, product_id: str) -> Destination:
        for destination in self.destinations:
            if destination.destination_id != destination_id:
                continue
            if destination.status != "active":
                raise ValidationError("submission destination is not active")
            if product_id not in destination.product_ids:
                raise ValidationError("product is not approved for this destination")
            return destination
        raise ValidationError(f"unknown submission destination: {destination_id}")


def _nested(value: Any, dotted_path: str) -> Any:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def send_http_json(destination: Destination, payload: dict[str, Any], idempotency_key: str) -> tuple[str, str]:
    """Transmit to one reviewed HTTPS endpoint and return receipt plus proof."""
    if destination.adapter != "http_json":
        raise ValidationError("this destination requires a reviewed browser playbook")
    _validate_public_https_url(destination.url)
    if destination.method.upper() != "POST":
        raise ValidationError("only POST submission endpoints are supported")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
        "User-Agent": "FundingDirector/1.0",
    }
    if destination.auth_env:
        secret = os.getenv(destination.auth_env, "")
        if not secret:
            raise ValidationError(f"missing destination credential: {destination.auth_env}")
        prefix = f"{destination.auth_scheme} " if destination.auth_scheme else ""
        headers[destination.auth_header] = prefix + secret
    outbound = request.Request(
        destination.url,
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with request.build_opener(NoRedirect).open(outbound, timeout=30) as response:
            raw = response.read(1_000_000)
            status = response.status
    except error.HTTPError as exc:
        raise ValidationError(f"destination returned HTTP {exc.code}; reconcile before retry") from exc
    except error.URLError as exc:
        raise ValidationError("destination result is unknown; reconcile before retry") from exc
    if not 200 <= status < 300:
        raise ValidationError(f"destination returned HTTP {status}; reconcile before retry")
    try:
        body = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise ValidationError("destination response was not valid JSON; reconcile before retry") from exc
    receipt = _nested(body, destination.receipt_field)
    if receipt is None or not str(receipt).strip():
        raise ValidationError("destination response did not contain the configured receipt")
    return str(receipt), f"HTTP {status}; receipt field {destination.receipt_field}"
