"""Dashboard API endpoints — status overview and firm data."""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from config import settings
from services.spreadsheet import spreadsheet_service
from services.onedrive import onedrive_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

LOCAL_XLSX_PATH = Path("./data/client_tracking.xlsx")


@router.get("/summary")
async def get_summary():
    """Get status summary counts for the dashboard overview."""
    try:
        summary = spreadsheet_service.get_status_summary()
        total = sum(summary.values())
        return {
            "total_firms": total,
            "by_status": summary,
        }
    except FileNotFoundError:
        return {"total_firms": 0, "by_status": {}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/firms")
async def get_all_firms(status: str | None = None):
    """Get all firms, optionally filtered by status.

    Query params:
        status: Filter by status value (e.g., 'noch nicht kontaktiert')
    """
    try:
        if status:
            firms = spreadsheet_service.get_firms_by_status(status)
        else:
            firms = spreadsheet_service.get_all_firms()
        return {"firms": firms, "count": len(firms)}
    except FileNotFoundError:
        return {"firms": [], "count": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/firms/ready")
async def get_ready_firms():
    """Get firms ready for initial outreach."""
    try:
        firms = spreadsheet_service.get_ready_for_outreach()
        return {"firms": firms, "count": len(firms)}
    except FileNotFoundError:
        return {"firms": [], "count": 0}


@router.get("/firms/followup-due")
async def get_followup_due_firms():
    """Get firms where follow-up is due."""
    try:
        firms = spreadsheet_service.get_followup_due()
        return {"firms": firms, "count": len(firms)}
    except FileNotFoundError:
        return {"firms": [], "count": 0}


@router.post("/sync")
async def sync_spreadsheet():
    """Re-download the spreadsheet from OneDrive (or confirm local file in local mode).

    Use this to refresh data if someone edited the file externally.
    """
    if settings.use_local_file:
        # Local file mode — skip OneDrive, just verify the file exists
        if LOCAL_XLSX_PATH.exists():
            return {
                "message": "Local file mode: spreadsheet loaded from disk.",
                "path": str(LOCAL_XLSX_PATH),
                "local_mode": True,
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Local file mode is enabled but no spreadsheet found at "
                    f"'{LOCAL_XLSX_PATH}'. Place your .xlsx file there and try again."
                ),
            )

    try:
        path = await onedrive_service.download_spreadsheet()
        return {"message": "Spreadsheet synced successfully.", "path": str(path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
