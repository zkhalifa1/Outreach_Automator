"""Inbox monitoring service — detect client replies via Microsoft Graph API.

Polls the authenticated user's inbox for messages from contacted firms
and auto-updates their status to 'in Kontakt' when a reply is detected.
"""

import logging
from datetime import datetime

import httpx

from config import settings
from auth.msal_auth import auth

logger = logging.getLogger(__name__)


class InboxMonitorService:
    """Monitor inbox for replies from contacted firms."""

    def __init__(self):
        self.base_url = settings.graph_base_url

    def _get_headers(self) -> dict:
        """Build auth headers with current access token."""
        token = auth.get_access_token()
        if not token:
            raise RuntimeError("Not authenticated. Complete device code flow first.")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def check_for_replies(
        self,
        firms: list[dict],
        dry_run: bool = False,
    ) -> list[dict]:
        """Check inbox for replies from a list of contacted firms.

        Args:
            firms: List of firm dicts (must have 'email_general', 'email_contact',
                   'letzte_kommunikation', 'datum_gesendet', 'firmenname', 'row').
            dry_run: If True, detect replies but don't update the spreadsheet.

        Returns:
            List of result dicts with detected replies and actions taken.
        """
        from services.spreadsheet import spreadsheet_service

        # Collect unique email addresses → firms mapping
        email_to_firms: dict[str, list[dict]] = {}
        for firm in firms:
            email = (firm.get("email_general") or firm.get("email_contact") or "").strip().lower()
            if not email:
                continue
            email_to_firms.setdefault(email, []).append(firm)

        results = []
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=15.0) as client:
            for email, firm_group in email_to_firms.items():
                try:
                    # Query inbox for messages FROM this email address
                    # Use $search instead of $filter — $filter + $orderby
                    # causes InefficientFilter on consumer accounts
                    url = (
                        f"{self.base_url}/me/messages"
                        f"?$search=\"from:{email}\""
                        f"&$top=5"
                        f"&$select=receivedDateTime,subject,from"
                    )

                    response = await client.get(url, headers=headers)

                    if response.status_code != 200:
                        logger.warning(
                            f"Failed to query inbox for {email}: "
                            f"{response.status_code} — {response.text}"
                        )
                        results.append({
                            "email": email,
                            "action": "error",
                            "error": f"Graph API {response.status_code}",
                        })
                        continue

                    data = response.json()
                    messages = data.get("value", [])

                    if not messages:
                        continue  # No messages from this sender

                    # Sort locally by receivedDateTime (desc) since
                    # $orderby can't be combined with $search
                    messages.sort(
                        key=lambda m: m.get("receivedDateTime", ""),
                        reverse=True,
                    )
                    latest_msg = messages[0]
                    received_str = latest_msg["receivedDateTime"]
                    # Graph returns ISO 8601: "2026-02-28T14:30:00Z"
                    received_dt = datetime.fromisoformat(
                        received_str.replace("Z", "+00:00")
                    ).replace(tzinfo=None)  # naive for comparison

                    # Check each firm associated with this email
                    for firm in firm_group:
                        last_comm = firm.get("letzte_kommunikation") or firm.get("datum_gesendet")
                        if not last_comm:
                            continue

                        # Parse the firm's last communication date
                        try:
                            if isinstance(last_comm, datetime):
                                last_dt = last_comm
                            else:
                                last_dt = datetime.strptime(
                                    str(last_comm).strip(), "%d.%m.%Y"
                                )
                        except ValueError:
                            continue

                        # Reply is newer than our last outreach?
                        if received_dt > last_dt:
                            reply_date = received_dt.strftime("%d.%m.%Y")
                            subject = latest_msg.get("subject", "(no subject)")

                            if not dry_run:
                                spreadsheet_service.mark_reply_received(
                                    firm["row"], reply_date
                                )

                            results.append({
                                "firm": firm["firmenname"],
                                "email": email,
                                "action": "reply_detected",
                                "reply_date": reply_date,
                                "reply_subject": subject,
                                "status_from": firm["status"],
                                "status_to": "in Kontakt",
                                "dry_run": dry_run,
                            })

                            logger.info(
                                f"{'[DRY RUN] ' if dry_run else ''}"
                                f"Reply detected from {email} for "
                                f"{firm['firmenname']} — subject: {subject}"
                            )

                    # Rate limit: 1 second between API calls
                    import asyncio
                    await asyncio.sleep(1.0)

                except Exception as e:
                    logger.error(f"Error checking inbox for {email}: {e}")
                    results.append({
                        "email": email,
                        "action": "error",
                        "error": str(e),
                    })

        detected = sum(1 for r in results if r.get("action") == "reply_detected")
        logger.info(
            f"Inbox check complete: {detected} replies detected "
            f"({'DRY RUN' if dry_run else 'LIVE'})"
        )

        return results


# Singleton instance
inbox_monitor = InboxMonitorService()
