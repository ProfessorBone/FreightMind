from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import Segment, SourceVersionSummary


class ReferenceDataError(RuntimeError):
    pass


class ReferenceDataCatalog:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._nbi = self._load_json("nbi_bridges.json")
        self._state = self._load_json("state_overlays.json")

    def _load_json(self, filename: str) -> Dict[str, Any]:
        path = self.data_dir / filename
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ReferenceDataError(f"Missing reference dataset: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ReferenceDataError(f"Invalid JSON in reference dataset: {path}") from exc

    @property
    def nbi_payload(self) -> Dict[str, Any]:
        return self._nbi

    @property
    def state_payload(self) -> Dict[str, Any]:
        return self._state

    def build_version_summary(self, today: date | None = None) -> Dict[str, SourceVersionSummary]:
        today = today or date.today()
        return {
            "nbi": self._summary_from_dataset("NBI", self._nbi, today),
            "state_overlays": self._summary_from_dataset("STATE_OVERLAYS", self._state, today),
        }

    def _summary_from_dataset(self, source_name: str, payload: Dict[str, Any], today: date) -> SourceVersionSummary:
        published_at = payload.get("published_at")
        age_days = None
        if published_at:
            published_date = datetime.strptime(published_at, "%Y-%m-%d").date()
            age_days = (today - published_date).days
        return SourceVersionSummary(
            source_name=source_name,
            version=payload.get("version", "unknown"),
            published_at=published_at,
            effective_from=payload.get("effective_from"),
            stale_after_days=payload.get("stale_after_days"),
            age_days=age_days,
            status=payload.get("status", "unknown"),
            record_count=self._record_count(payload),
            coverage=payload.get("coverage", {}),
        )

    def _record_count(self, payload: Dict[str, Any]) -> int:
        if isinstance(payload.get("records"), list):
            return len(payload["records"])
        states = payload.get("states")
        if isinstance(states, dict):
            return sum(len(items) for items in states.values() if isinstance(items, list))
        return 0

    def apply_reference_overlays(self, segments: Iterable[Segment]) -> List[dict]:
        annotations: List[dict] = []
        nbi_index = {record["segment_id"]: record for record in self._nbi.get("records", [])}
        state_index = {
            record["segment_id"]: record
            for records in self._state.get("states", {}).values()
            if isinstance(records, list)
            for record in records
        }

        for segment in segments:
            applied_sources: list[str] = []
            nbi_record = nbi_index.get(segment.segment_id)
            if nbi_record:
                applied_sources.append("nbi")
                self._apply_limit_if_lower(segment, "maxheight_ft", nbi_record.get("clearance_ft"))
                self._apply_limit_if_lower(segment, "maxweight_lb", nbi_record.get("posted_weight_lb"))
                self._apply_limit_if_lower(segment, "max_axle_weight_lb", nbi_record.get("posted_axle_weight_lb"))
                segment.source_tags.setdefault("nbi", {}).update({
                    "structure_id": nbi_record.get("structure_id"),
                    "feature_name": nbi_record.get("feature_name"),
                    "inspection_date": nbi_record.get("inspection_date"),
                })
                if "nbi" not in segment.source_flags:
                    segment.source_flags.append("nbi")

            state_record = state_index.get(segment.segment_id)
            if state_record:
                state_code = state_record.get("state")
                applied_sources.append(f"overlay:{state_code.lower()}")
                self._apply_limit_if_lower(segment, "maxheight_ft", state_record.get("maxheight_ft"))
                self._apply_limit_if_lower(segment, "maxweight_lb", state_record.get("maxweight_lb"))
                self._apply_limit_if_lower(segment, "maxlength_ft", state_record.get("maxlength_ft"))
                self._apply_limit_if_lower(segment, "max_axle_weight_lb", state_record.get("max_axle_weight_lb"))
                if state_record.get("hazmat_allowed") is not None:
                    segment.hazmat_allowed = state_record["hazmat_allowed"]
                if state_record.get("hgv_allowed") is not None:
                    segment.hgv_allowed = state_record["hgv_allowed"]
                segment.source_tags.setdefault("state_overlay", {}).update({
                    "state": state_code,
                    "restriction_type": state_record.get("restriction_type"),
                    "corridor_id": state_record.get("corridor_id"),
                    "updated_at": state_record.get("updated_at"),
                })
                overlay_flag = f"overlay:{state_code.lower()}dot"
                if overlay_flag not in segment.source_flags:
                    segment.source_flags.append(overlay_flag)

            if applied_sources:
                annotations.append({
                    "segment_id": segment.segment_id,
                    "applied_sources": applied_sources,
                    "source_tags": asdict_safe(segment.source_tags),
                })
        return annotations

    def _apply_limit_if_lower(self, segment: Segment, field_name: str, candidate: Any) -> None:
        if candidate is None:
            return
        current = getattr(segment, field_name)
        if current is None or candidate < current:
            setattr(segment, field_name, candidate)



def asdict_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, default=str))
    except TypeError:
        return str(value)
