"""Activity log API endpoints."""

from fastapi import APIRouter

from models.database import get_activity_log

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/")
async def get_logs(
    limit: int = 100,
    offset: int = 0,
    action_type: str | None = None,
    firm_name: str | None = None,
):
    """Get activity log entries with optional filters.

    Query params:
        limit: Max entries to return (default 100).
        offset: Pagination offset.
        action_type: Filter by type (e.g., 'initial_email_sent', 'followup_sent').
        firm_name: Filter by firm name (partial match).
    """
    entries = get_activity_log(
        limit=limit,
        offset=offset,
        action_type=action_type,
        firm_name=firm_name,
    )
    return {"entries": entries, "count": len(entries)}
