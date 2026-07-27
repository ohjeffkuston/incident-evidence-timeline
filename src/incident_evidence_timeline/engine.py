"""Deterministic incident-event normalization and sequencing."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

SEVERITIES = {"info", "warning", "error", "critical"}
REQUIRED_EVENT_FIELDS = {"id", "source", "timestamp", "severity", "service", "type", "message"}


class TimelineInputError(ValueError):
    """Raised when evidence cannot be evaluated safely."""


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise TimelineInputError(f"{field} must be a non-empty ISO-8601 string")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise TimelineInputError(f"{field} is not valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise TimelineInputError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_offsets(payload: dict[str, Any]) -> dict[str, int]:
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise TimelineInputError("sources must be a non-empty list")
    offsets: dict[str, int] = {}
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise TimelineInputError(f"sources[{index}] must be an object")
        name = source.get("name")
        offset = source.get("clock_offset_seconds", 0)
        if not isinstance(name, str) or not name.strip():
            raise TimelineInputError(f"sources[{index}].name must be non-empty")
        if name in offsets:
            raise TimelineInputError(f"duplicate source name: {name}")
        if not isinstance(offset, int) or abs(offset) > 3600:
            raise TimelineInputError(f"sources[{index}].clock_offset_seconds must be within +/-3600")
        offsets[name] = offset
    return offsets


def _fingerprint(event: dict[str, Any]) -> str:
    stable = "|".join(str(event[key]) for key in sorted(REQUIRED_EVENT_FIELDS))
    return sha256(stable.encode("utf-8")).hexdigest()[:16]


def build_timeline(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic, read-only incident evidence report."""
    if not isinstance(payload, dict):
        raise TimelineInputError("input must be an object")
    data = deepcopy(payload)
    incident_id = data.get("incident_id")
    if not isinstance(incident_id, str) or not incident_id.strip():
        raise TimelineInputError("incident_id must be non-empty")

    gap_threshold = data.get("gap_threshold_seconds", 300)
    if not isinstance(gap_threshold, int) or gap_threshold < 1:
        raise TimelineInputError("gap_threshold_seconds must be a positive integer")

    offsets = _source_offsets(data)
    events = data.get("events")
    if not isinstance(events, list) or not events:
        raise TimelineInputError("events must be a non-empty list")

    seen: dict[tuple[str, str], str] = {}
    timeline: list[dict[str, Any]] = []
    duplicate_count = 0
    for index, raw in enumerate(events):
        if not isinstance(raw, dict):
            raise TimelineInputError(f"events[{index}] must be an object")
        missing = sorted(REQUIRED_EVENT_FIELDS - raw.keys())
        if missing:
            raise TimelineInputError(f"events[{index}] missing fields: {', '.join(missing)}")
        if raw["source"] not in offsets:
            raise TimelineInputError(f"events[{index}] references unknown source: {raw['source']}")
        if raw["severity"] not in SEVERITIES:
            raise TimelineInputError(f"events[{index}].severity must be one of {sorted(SEVERITIES)}")
        for field in ("id", "service", "type", "message"):
            if not isinstance(raw[field], str) or not raw[field].strip():
                raise TimelineInputError(f"events[{index}].{field} must be non-empty")

        identity = (raw["source"], raw["id"])
        fingerprint = _fingerprint(raw)
        if identity in seen:
            if seen[identity] != fingerprint:
                raise TimelineInputError(f"conflicting duplicate event: {raw['source']}/{raw['id']}")
            duplicate_count += 1
            continue
        seen[identity] = fingerprint

        observed = _parse_timestamp(raw["timestamp"], f"events[{index}].timestamp")
        corrected = observed - timedelta(seconds=offsets[raw["source"]])
        timeline.append(
            {
                "id": raw["id"],
                "source": raw["source"],
                "observed_at": _iso(observed),
                "normalized_at": _iso(corrected),
                "clock_correction_seconds": -offsets[raw["source"]],
                "severity": raw["severity"],
                "service": raw["service"],
                "type": raw["type"],
                "message": raw["message"],
                "evidence_fingerprint": fingerprint,
            }
        )

    timeline.sort(key=lambda event: (event["normalized_at"], event["source"], event["id"]))
    gaps: list[dict[str, Any]] = []
    for previous, current in zip(timeline, timeline[1:]):
        before = _parse_timestamp(previous["normalized_at"], "normalized_at")
        after = _parse_timestamp(current["normalized_at"], "normalized_at")
        gap_seconds = int((after - before).total_seconds())
        if gap_seconds > gap_threshold:
            gaps.append(
                {
                    "after_event": previous["id"],
                    "before_event": current["id"],
                    "gap_seconds": gap_seconds,
                }
            )

    severity_counts = Counter(event["severity"] for event in timeline)
    services = sorted({event["service"] for event in timeline})
    findings: list[dict[str, Any]] = []
    if duplicate_count:
        findings.append({"code": "DUPLICATES_REMOVED", "count": duplicate_count})
    if gaps:
        findings.append({"code": "EVIDENCE_GAPS_FOUND", "count": len(gaps)})
    corrected_sources = sorted(name for name, offset in offsets.items() if offset)
    if corrected_sources:
        findings.append({"code": "CLOCK_OFFSETS_APPLIED", "sources": corrected_sources})

    return {
        "incident_id": incident_id,
        "decision": "REVIEW" if gaps else "READY",
        "event_count": len(timeline),
        "duplicate_count": duplicate_count,
        "severity_counts": {key: severity_counts.get(key, 0) for key in sorted(SEVERITIES)},
        "services": services,
        "gaps": gaps,
        "findings": findings,
        "timeline": timeline,
        "safety": {
            "read_only": True,
            "external_calls": False,
            "changes_infrastructure": False,
            "requires_human_interpretation": True,
        },
    }

