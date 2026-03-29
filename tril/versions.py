from __future__ import annotations

from datetime import date, datetime
from typing import Dict

from .config import DataVersions
from .models import SourceVersionSummary


def data_staleness_warning(versions: DataVersions, today: date | None = None, stale_after_days: int = 60) -> str | None:
    today = today or date.today()
    osm_date = datetime.strptime(versions.osm_extract_date, "%Y-%m-%d").date()
    age_days = (today - osm_date).days
    if age_days > stale_after_days:
        return f"Map data is {age_days} days old. Consider updating for most current restrictions."
    return None



def summarize_staleness(version_summaries: Dict[str, SourceVersionSummary]) -> Dict[str, dict]:
    return {
        key: {
            "version": summary.version,
            "status": summary.status,
            "published_at": summary.published_at,
            "age_days": summary.age_days,
            "stale_after_days": summary.stale_after_days,
            "is_stale": bool(
                summary.stale_after_days is not None
                and summary.age_days is not None
                and summary.age_days > summary.stale_after_days
            ),
            "record_count": summary.record_count,
            "coverage": summary.coverage,
        }
        for key, summary in version_summaries.items()
    }
