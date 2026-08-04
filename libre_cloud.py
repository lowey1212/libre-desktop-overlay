"""Gluroo/Nightscout data access for the Libre desktop overlay.

The Gluroo Global Connect URL contains a health-data access token. It is held
only in memory while the app runs and is never included in displayed errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class CloudLoginError(RuntimeError):
    pass


class CloudSetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class CloudReading:
    time: datetime
    mgdl: float
    trend: str = ""


def _local_naive(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is not None:
        return timestamp.astimezone().replace(tzinfo=None)
    return timestamp


class GlurooSession:
    """Read Gluroo's intentionally exposed Nightscout-compatible feed."""

    patient_name = "Gluroo"

    def __init__(self, global_connect_url: str):
        self._feed_url, self._headers = self._normalise_connection(global_connect_url)

    @classmethod
    def connect(cls, global_connect_url: str) -> "GlurooSession":
        return cls(global_connect_url)

    @staticmethod
    def _normalise_connection(value: str) -> tuple[str, dict[str, str]]:
        text = value.strip()
        if not text:
            raise CloudSetupError("Paste the Gluroo Global Connect details.")

        details = {}
        json_text = text
        if not json_text.startswith("{") and '"apiSecretToken"' in json_text:
            json_text = "{" + json_text + "}"
        try:
            decoded = json.loads(json_text)
            if isinstance(decoded, dict):
                details = decoded
        except json.JSONDecodeError:
            pass

        url_match = re.search(r"https://[^\"'\s,}]+", text)
        base_url = details.get("url") or details.get("baseUrl") or (url_match.group(0) if url_match else text)
        token = details.get("apiSecretToken") or details.get("token")
        secret_header = details.get("apiSecretHeader") or details.get("api-secret")
        token_match = re.search(r'"apiSecretToken"\s*:\s*"([A-Za-z0-9_-]+)', text)
        header_match = re.search(r'"apiSecretHeader"\s*:\s*"([0-9A-Fa-f]+)', text)
        token = token or (token_match.group(1) if token_match else None)
        secret_header = secret_header or (header_match.group(1) if header_match else None)

        parsed = urlsplit(str(base_url).strip())
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise CloudSetupError("The Gluroo details must contain a complete HTTPS address.")
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        token = token or query.get("token")
        secret_header = secret_header or query.get("api-secret")
        if not token:
            raise CloudSetupError(
                "No Gluroo API token was found. Paste the complete Gluroo Global Connect details."
            )
        query["token"] = str(token)
        query["count"] = "288"
        path = parsed.path.rstrip("/")
        if not path:
            path = "/api/v1/entries/sgv.json"
        elif not path.endswith("/pebble") and "/api/v1/entries" not in path:
            path = f"{path}/pebble" if path else "/pebble"
        headers = {"api-secret": str(secret_header)} if secret_header else {}
        return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(query), "")), headers

    def fetch(self) -> list[CloudReading]:
        try:
            import requests
            response = requests.get(self._feed_url, headers=self._headers, timeout=(5, 20))
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            raise CloudLoginError(_friendly_network_error(error)) from None

        if isinstance(payload, dict):
            items = payload.get("bgs") or payload.get("entries") or []
        elif isinstance(payload, list):
            items = payload
        else:
            items = []

        readings_by_time = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                mgdl = float(item.get("sgv", item.get("mbg", item.get("value"))))
            except (TypeError, ValueError):
                continue
            if not 20 <= mgdl <= 600:
                continue
            timestamp = _parse_nightscout_time(item)
            if not timestamp:
                continue
            trend = _nightscout_trend(item.get("direction", item.get("trend")))
            readings_by_time[timestamp] = CloudReading(time=timestamp, mgdl=mgdl, trend=trend)
        if not readings_by_time:
            raise CloudSetupError(
                "Gluroo returned no glucose readings. Confirm that Libre is connected in Gluroo and try again."
            )
        return sorted(readings_by_time.values(), key=lambda item: item.time)


def _parse_nightscout_time(item: dict) -> datetime | None:
    milliseconds = item.get("datetime", item.get("date"))
    if milliseconds is not None:
        try:
            number = float(milliseconds)
            if number > 10_000_000_000:
                number /= 1000
            return datetime.fromtimestamp(number)
        except (OSError, OverflowError, TypeError, ValueError):
            pass
    date_string = item.get("dateString") or item.get("timestamp")
    if date_string:
        try:
            parsed = datetime.fromisoformat(str(date_string).replace("Z", "+00:00"))
            return _local_naive(parsed)
        except ValueError:
            pass
    return None


def _nightscout_trend(value: Any) -> str:
    arrows = {
        "doubleup": "↑↑",
        "singleup": "↑",
        "fortyfiveup": "↗",
        "flat": "→",
        "fortyfivedown": "↘",
        "singledown": "↓",
        "doubledown": "↓↓",
        "notcomputable": "?",
        "rateoutofrange": "?",
    }
    if value is None:
        return ""
    return arrows.get(str(value).replace("_", "").replace(" ", "").lower(), "")


def _friendly_network_error(error: Exception) -> str:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code in (401, 403):
        return "Gluroo rejected the access URL. Copy a fresh Global Connect URL and reconnect."
    if status_code == 429:
        return "Gluroo is temporarily limiting requests. The app will retry shortly."
    if status_code:
        return f"The Gluroo feed returned HTTP {status_code}."
    return "Could not reach Gluroo. Check the internet connection."
