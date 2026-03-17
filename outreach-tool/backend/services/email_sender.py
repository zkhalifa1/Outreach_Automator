"""Email sending service via Microsoft Graph API (Outlook).

Sends emails through the authenticated user's Outlook account using
the /me/sendMail endpoint.
"""

import asyncio
import logging

import httpx

from config import settings
from auth.msal_auth import auth

logger = logging.getLogger(__name__)


class EmailSenderService:
    """Send emails via Microsoft Graph API."""

    def __init__(self):
        self.base_url = settings.graph_base_url
        self.rate_limit_delay = settings.send_rate_limit_delay

    def _get_headers(self) -> dict:
        """Build auth headers with current access token."""
        token = auth.get_access_token()
        if not token:
            raise RuntimeError("Not authenticated. Complete device code flow first.")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _build_message(
        self,
        to_email: str,
        subject: str,
        body: str,
        content_type: str = "HTML",
    ) -> dict:
        """Build the Graph API sendMail payload.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            body: Email body content.
            content_type: 'HTML' or 'Text'. Defaults to 'HTML'.
        """
        return {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": content_type,
                    "content": body,
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email,
                        }
                    }
                ],
            },
            "saveToSentItems": True,
        }

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        dry_run: bool = False,
    ) -> dict:
        """Send a single email via Graph API.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            body: Email body (HTML).
            dry_run: If True, log but don't actually send.

        Returns:
            Dict with 'success', 'to', and optionally 'error'.
        """
        if not to_email or not to_email.strip():
            return {
                "success": False,
                "to": to_email,
                "error": "Empty email address",
            }

        if dry_run:
            logger.info(f"[DRY RUN] Would send to {to_email}: {subject}")
            return {
                "success": True,
                "to": to_email,
                "dry_run": True,
            }

        url = f"{self.base_url}/me/sendMail"
        headers = self._get_headers()
        payload = self._build_message(to_email, subject, body)

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 202:
                logger.info(f"Email sent to {to_email}: {subject}")
                return {"success": True, "to": to_email}
            else:
                # Log full response details for debugging
                logger.error(f"Failed to send to {to_email}: {response.status_code}")
                logger.error(f"Response headers: {dict(response.headers)}")
                logger.error(f"Response body: {response.text}")
                error_msg = f"Failed to send to {to_email}: {response.status_code} — {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "to": to_email,
                    "error": error_msg,
                }

    async def send_batch(
        self,
        recipients: list[dict],
        subject: str,
        body: str,
        email_column: str = "email_general",
        dry_run: bool = False,
    ) -> list[dict]:
        """Send emails to a batch of firms with rate limiting.

        Args:
            recipients: List of firm dicts from the spreadsheet service.
            subject: Email subject line.
            body: Email body (HTML).
            email_column: Which email field to use ('email_general' or 'email_contact').
            dry_run: If True, simulate without sending.

        Returns:
            List of result dicts, one per recipient.
        """
        results = []

        for i, firm in enumerate(recipients):
            to_email = firm.get(email_column, "").strip()
            firm_name = firm.get("firmenname", "Unknown")

            if not to_email:
                results.append({
                    "success": False,
                    "firm": firm_name,
                    "to": "",
                    "error": f"No email in '{email_column}' column",
                })
                continue

            result = await self.send_email(to_email, subject, body, dry_run=dry_run)
            result["firm"] = firm_name
            result["row"] = firm.get("row")
            results.append(result)

            # Rate limiting — wait between sends (skip delay for last email)
            if not dry_run and i < len(recipients) - 1:
                await asyncio.sleep(self.rate_limit_delay)

        sent = sum(1 for r in results if r.get("success"))
        failed = len(results) - sent
        logger.info(
            f"Batch complete: {sent} sent, {failed} failed "
            f"({'DRY RUN' if dry_run else 'LIVE'})"
        )

        return results


# Singleton instance
email_sender = EmailSenderService()
