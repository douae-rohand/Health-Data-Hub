from fastapi import APIRouter, HTTPException
from quality.config import REGIONS
from quality.db import get_connection
from quality.report import build_report
from quality.stats import build_stats

router = APIRouter(tags=["quality"])


@router.get("/quality/reports")
def quality_reports(region: str | None = None):
    if region is not None and region not in REGIONS:
        raise HTTPException(status_code=404, detail="Région inconnue")
    with get_connection() as conn:
        return build_report(conn, [region] if region else None)


@router.get("/stats")
def stats():
    with get_connection() as conn:
        return build_stats(conn)
