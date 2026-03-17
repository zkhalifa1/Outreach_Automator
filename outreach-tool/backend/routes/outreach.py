"""Outreach API endpoints — sending emails and managing campaigns."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.spreadsheet import (
    spreadsheet_service,
    STATUS_NOT_CONTACTED,
    STATUS_EMAIL_SENT,
    STATUS_FOLLOWUP_SENT,
    STATUS_NO_RESPONSE,
    STATUS_IN_CONTACT,
)
from services.email_sender import email_sender
from services.inbox_monitor import inbox_monitor
from services.onedrive import onedrive_service
from models.database import (
    log_activity,
    count_followups_for_firm,
    has_been_emailed,
)
from config import settings

router = APIRouter(prefix="/api/outreach", tags=["outreach"])


class SendRequest(BaseModel):
    """Request body for sending outreach emails."""
    email_column: str = "email_general"  # or "email_contact"
    dry_run: bool = False


class FollowUpRequest(BaseModel):
    """Request body for triggering follow-up checks."""
    dry_run: bool = False


class InboxCheckRequest(BaseModel):
    """Request body for triggering inbox check."""
    dry_run: bool = False


@router.post("/preview")
async def preview_outreach(request: SendRequest):
    """Preview which firms will receive emails without sending.

    Returns the list of firms and the email template that would be used.
    """
    firms = spreadsheet_service.get_ready_for_outreach()
    templates = spreadsheet_service.get_email_templates()
    initial_template = templates.get("initial", {})

    # Filter out firms without a valid email in the chosen column
    eligible = []
    skipped = []
    for firm in firms:
        email = firm.get(request.email_column, "").strip()
        if email:
            # Check for duplicates
            if has_been_emailed(firm["firmenname"]):
                skipped.append({**firm, "skip_reason": "Already emailed (duplicate check)"})
            else:
                eligible.append(firm)
        else:
            skipped.append({**firm, "skip_reason": f"No email in '{request.email_column}'"})

    return {
        "eligible": eligible,
        "eligible_count": len(eligible),
        "skipped": skipped,
        "skipped_count": len(skipped),
        "email_column": request.email_column,
        "template": initial_template,
    }


@router.post("/send")
async def send_outreach(request: SendRequest):
    """Send initial outreach emails to all eligible firms.

    Flow:
    1. Get firms with status 'noch nicht kontaktiert'
    2. Load the initial email template
    3. Send emails with rate limiting
    4. Update spreadsheet statuses
    5. Upload modified spreadsheet to OneDrive
    6. Log all actions
    """
    firms = spreadsheet_service.get_ready_for_outreach()
    templates = spreadsheet_service.get_email_templates()
    initial_template = templates.get("initial", {})

    if not initial_template:
        raise HTTPException(
            status_code=400,
            detail="No 'initial' email template found in the spreadsheet.",
        )

    # Filter duplicates
    eligible = [
        f for f in firms
        if f.get(request.email_column, "").strip()
        and not has_been_emailed(f["firmenname"])
    ]

    if not eligible:
        return {"message": "No eligible firms to contact.", "sent": 0, "failed": 0}

    # Send emails
    results = await email_sender.send_batch(
        recipients=eligible,
        subject=initial_template["subject"],
        body=initial_template["body"],
        email_column=request.email_column,
        dry_run=request.dry_run,
    )

    # Update spreadsheet and log for successful sends
    for result in results:
        if result.get("success"):
            row = result.get("row")
            if row and not request.dry_run:
                spreadsheet_service.mark_email_sent(row)

            log_activity(
                action_type="initial_email_sent",
                firm_name=result.get("firm", ""),
                firm_row=row,
                email_to=result.get("to", ""),
                email_subject=initial_template["subject"],
                status_from=STATUS_NOT_CONTACTED,
                status_to=STATUS_EMAIL_SENT,
                dry_run=request.dry_run,
            )
        else:
            log_activity(
                action_type="email_failed",
                firm_name=result.get("firm", ""),
                firm_row=result.get("row"),
                email_to=result.get("to", ""),
                details=result.get("error", "Unknown error"),
                dry_run=request.dry_run,
            )

    # Upload updated spreadsheet back to OneDrive
    if not request.dry_run:
        try:
            await onedrive_service.upload_spreadsheet()
        except Exception as e:
            log_activity(
                action_type="upload_failed",
                details=f"Failed to upload spreadsheet after outreach: {e}",
            )

    sent = sum(1 for r in results if r.get("success"))
    failed = len(results) - sent

    return {
        "message": f"Outreach complete: {sent} sent, {failed} failed.",
        "sent": sent,
        "failed": failed,
        "dry_run": request.dry_run,
        "results": results,
    }


@router.post("/followup")
async def trigger_followup(request: FollowUpRequest):
    """Manually trigger a follow-up check.

    Checks all firms where follow-up is due and sends follow-up emails.
    Respects the max follow-up limit (2) before marking as 'keine Antwort'.
    """
    due_firms = spreadsheet_service.get_followup_due()
    templates = spreadsheet_service.get_email_templates()

    if not due_firms:
        return {"message": "No follow-ups due.", "sent": 0, "marked_no_response": 0}

    sent_count = 0
    no_response_count = 0
    results = []

    for firm in due_firms:
        followup_count = count_followups_for_firm(firm["firmenname"])

        if followup_count >= settings.max_follow_ups:
            # Max follow-ups reached — mark as keine Antwort
            if not request.dry_run:
                spreadsheet_service.mark_no_response(firm["row"])

            log_activity(
                action_type="marked_no_response",
                firm_name=firm["firmenname"],
                firm_row=firm["row"],
                status_from=firm["status"],
                status_to=STATUS_NO_RESPONSE,
                details=f"Max follow-ups ({settings.max_follow_ups}) reached.",
                dry_run=request.dry_run,
            )
            no_response_count += 1
            results.append({
                "firm": firm["firmenname"],
                "action": "marked_no_response",
            })
            continue

        # Determine which follow-up template to use
        template_key = f"followup_{followup_count + 1}"
        template = templates.get(template_key) or templates.get("followup", {})

        if not template:
            results.append({
                "firm": firm["firmenname"],
                "action": "skipped",
                "reason": f"No '{template_key}' template found.",
            })
            continue

        # Send follow-up
        to_email = firm.get("email_general") or firm.get("email_contact")
        if not to_email:
            continue

        send_result = await email_sender.send_email(
            to_email=to_email.strip(),
            subject=template["subject"],
            body=template["body"],
            dry_run=request.dry_run,
        )

        if send_result.get("success"):
            if not request.dry_run:
                spreadsheet_service.mark_followup_sent(firm["row"])

            log_activity(
                action_type="followup_sent",
                firm_name=firm["firmenname"],
                firm_row=firm["row"],
                email_to=to_email,
                email_subject=template["subject"],
                status_from=firm["status"],
                status_to=STATUS_FOLLOWUP_SENT,
                dry_run=request.dry_run,
            )
            sent_count += 1
            results.append({
                "firm": firm["firmenname"],
                "action": "followup_sent",
                "followup_number": followup_count + 1,
            })

    # Upload updated spreadsheet
    if not request.dry_run and (sent_count > 0 or no_response_count > 0):
        try:
            await onedrive_service.upload_spreadsheet()
        except Exception as e:
            log_activity(
                action_type="upload_failed",
                details=f"Failed to upload after follow-ups: {e}",
            )

    return {
        "message": f"Follow-up check complete.",
        "sent": sent_count,
        "marked_no_response": no_response_count,
        "dry_run": request.dry_run,
        "results": results,
    }


@router.post("/check-inbox")
async def check_inbox(request: InboxCheckRequest):
    """Check inbox for replies from contacted firms.

    Scans the authenticated user's inbox for messages from firms that
    have been emailed. If a reply is detected, updates the firm's status
    to 'in Kontakt' and sets the last communication date.
    """
    contacted = spreadsheet_service.get_contacted_firms()

    if not contacted:
        return {
            "message": "No contacted firms to monitor.",
            "replies_detected": 0,
            "firms_checked": 0,
        }

    results = await inbox_monitor.check_for_replies(contacted, dry_run=request.dry_run)

    # Log each detected reply
    for r in results:
        if r.get("action") == "reply_detected":
            log_activity(
                action_type="reply_detected",
                firm_name=r["firm"],
                email_to=r["email"],
                status_from=r["status_from"],
                status_to=r["status_to"],
                details=f"Reply subject: {r.get('reply_subject', '')}",
                dry_run=request.dry_run,
            )

    # Upload updated spreadsheet
    replies = [r for r in results if r.get("action") == "reply_detected"]
    if not request.dry_run and replies:
        try:
            await onedrive_service.upload_spreadsheet()
        except Exception as e:
            log_activity(
                action_type="upload_failed",
                details=f"Failed to upload after inbox check: {e}",
            )

    return {
        "message": f"Inbox check complete.",
        "replies_detected": len(replies),
        "firms_checked": len(contacted),
        "dry_run": request.dry_run,
        "results": results,
    }
