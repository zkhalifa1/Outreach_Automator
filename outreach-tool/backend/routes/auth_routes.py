"""Authentication API endpoints for Microsoft login flow."""

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from auth.msal_auth import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Persist the device flow to disk so it survives server restarts (--reload)
FLOW_CACHE_PATH = Path("./.active_flow.json")


def _save_flow(flow: dict | None):
    """Save device flow to disk."""
    if flow is None:
        FLOW_CACHE_PATH.unlink(missing_ok=True)
    else:
        FLOW_CACHE_PATH.write_text(json.dumps(flow))


def _load_flow() -> dict | None:
    """Load device flow from disk."""
    if FLOW_CACHE_PATH.exists():
        try:
            return json.loads(FLOW_CACHE_PATH.read_text())
        except Exception:
            return None
    return None


@router.get("/status")
async def auth_status():
    """Check if the user is currently authenticated."""
    is_auth = auth.is_authenticated()
    accounts = auth.get_accounts() if is_auth else []
    return {
        "authenticated": is_auth,
        "accounts": [
            {"username": a.get("username", "")} for a in accounts
        ],
    }


@router.post("/login")
async def start_login():
    """Initiate the device code login flow.

    Returns the user code and verification URL. The user opens
    the URL in their browser, enters the code, and authenticates.
    """
    # Check if already authenticated
    if auth.is_authenticated():
        return {
            "authenticated": True,
            "message": "Already authenticated.",
        }

    try:
        flow = auth.initiate_device_flow()
        _save_flow(flow)
        return {
            "authenticated": False,
            "user_code": flow.get("user_code"),
            "verification_uri": flow.get("verification_uri"),
            "message": flow.get("message"),
            "expires_in": flow.get("expires_in"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complete")
async def complete_login():
    """Complete the device code flow after user has authenticated in browser.

    Runs the blocking MSAL call in a thread to avoid freezing the event loop.
    """
    active_flow = _load_flow()

    if active_flow is None:
        raise HTTPException(
            status_code=400,
            detail="No active login flow. Call /api/auth/login first.",
        )

    try:
        # Run the blocking MSAL call in a thread to avoid freezing the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, auth.acquire_token_by_device_flow, active_flow
        )
        _save_flow(None)  # Clear the flow file

        if "access_token" in result:
            return {
                "authenticated": True,
                "message": "Login successful.",
            }
        else:
            return {
                "authenticated": False,
                "error": result.get("error"),
                "error_description": result.get("error_description"),
            }
    except Exception as e:
        _save_flow(None)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def logout():
    """Clear cached tokens and log out."""
    auth.logout()
    _save_flow(None)
    return {"authenticated": False, "message": "Logged out."}
