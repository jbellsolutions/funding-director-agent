"""Narrow, location-scoped GoHighLevel client for funding operations."""

from __future__ import annotations

import json
import math
import os
from typing import Any
from urllib import error, parse, request

from .models import ValidationError


class GHLClient:
    BASE_URL = "https://services.leadconnectorhq.com"
    VERSION = "v3"
    WRITE_OPERATIONS = {"add_tags", "create_note", "update_opportunity"}

    @classmethod
    def validate_operation(cls, operation: str, payload: dict[str, Any]) -> None:
        if operation not in cls.WRITE_OPERATIONS:
            raise ValidationError(f"unsupported GoHighLevel operation: {operation}")
        if operation == "add_tags":
            tags = payload.get("tags")
            if set(payload) != {"tags"} or not isinstance(tags, list) or not tags or not all(
                isinstance(tag, str) and tag.strip() for tag in tags
            ):
                raise ValidationError("add_tags requires only a non-empty tags array")
        elif operation == "create_note":
            body = payload.get("body")
            if set(payload) != {"body"} or not isinstance(body, str) or not body.strip():
                raise ValidationError("create_note requires only a non-empty body")
        elif operation == "update_opportunity":
            allowed = {"pipelineStageId", "status", "monetaryValue", "name", "assignedTo"}
            if not payload or set(payload) - allowed:
                raise ValidationError("update_opportunity contains an unapproved field")
            if "status" in payload and payload["status"] not in {"open", "won", "lost", "abandoned"}:
                raise ValidationError("opportunity status is invalid")
            if "monetaryValue" in payload and (
                isinstance(payload["monetaryValue"], bool)
                or not isinstance(payload["monetaryValue"], (int, float))
                or not math.isfinite(payload["monetaryValue"])
                or payload["monetaryValue"] < 0
            ):
                raise ValidationError("opportunity monetaryValue must be a non-negative number")
            for key in ("pipelineStageId", "name", "assignedTo"):
                if key in payload and (not isinstance(payload[key], str) or not payload[key].strip()):
                    raise ValidationError(f"opportunity {key} must be non-empty text")

    def __init__(self, token: str | None = None, location_id: str | None = None):
        self.token = token or os.getenv("GHL_API_KEY", "")
        self.location_id = location_id or os.getenv("GHL_LOCATION_ID", "")
        if not self.token.startswith("pit-"):
            raise ValidationError("GHL_API_KEY must be a location-scoped private integration token")
        if not self.location_id.strip():
            raise ValidationError("GHL_LOCATION_ID is required")

    def _call(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = self.BASE_URL + path
        if query:
            url += "?" + parse.urlencode({key: value for key, value in query.items() if value not in (None, "")})
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "Version": self.VERSION,
            "User-Agent": "FundingDirector/1.0",
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, separators=(",", ":")).encode()
        outbound = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(outbound, timeout=30) as response:
                raw = response.read(1_000_000)
                status = response.status
        except error.HTTPError as exc:
            raise ValidationError(f"GoHighLevel returned HTTP {exc.code}") from exc
        except error.URLError as exc:
            raise ValidationError("GoHighLevel could not be reached") from exc
        if not 200 <= status < 300:
            raise ValidationError(f"GoHighLevel returned HTTP {status}")
        try:
            value = json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise ValidationError("GoHighLevel returned an invalid JSON response") from exc
        if not isinstance(value, dict):
            raise ValidationError("GoHighLevel returned an unexpected response shape")
        return value

    def search_contacts(self, query: str = "", limit: int = 20) -> dict[str, Any]:
        body: dict[str, Any] = {
            "locationId": self.location_id,
            "pageLimit": min(max(limit, 1), 100),
        }
        if query.strip():
            body["query"] = query.strip()[:75]
        return self._call("POST", "/contacts/search", body=body)

    def get_contact(self, contact_id: str) -> dict[str, Any]:
        return self._call("GET", f"/contacts/{parse.quote(contact_id, safe='')}")

    def search_opportunities(self, pipeline_id: str = "", status: str = "", limit: int = 20) -> dict[str, Any]:
        if status and status not in {"open", "won", "lost", "abandoned", "all"}:
            raise ValidationError("opportunity status is invalid")
        return self._call(
            "GET",
            "/opportunities/search",
            query={
                "locationId": self.location_id,
                "pipelineId": pipeline_id,
                "status": status,
                "limit": min(max(limit, 1), 100),
            },
        )

    def list_pipelines(self) -> dict[str, Any]:
        return self._call("GET", "/opportunities/pipelines", query={"locationId": self.location_id})

    def execute(self, operation: str, target_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.validate_operation(operation, payload)
        if operation == "add_tags":
            return self._call("POST", f"/contacts/{parse.quote(target_id, safe='')}/tags", body=payload)
        if operation == "create_note":
            return self._call("POST", f"/contacts/{parse.quote(target_id, safe='')}/notes", body=payload)
        if operation == "update_opportunity":
            return self._call("PUT", f"/opportunities/{parse.quote(target_id, safe='')}", body=payload)
        raise AssertionError("validated operation did not route")
