"""APScheduler service for automated follow-up checks.

Runs a daily job that:
1. Downloads the latest spreadsheet from OneDrive
2. Checks for firms needing follow-up
3. Sends follow-up emails
4. Updates the spreadsheet and uploads back
"""

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _run_followup_check():
    """Synchronous wrapper to run the async follow-up check."""
    from services.onedrive import onedrive_service
    from services.spreadsheet import spreadsheet_service, STATUS_FOLLOWUP_SENT, STATUS_NO_RESPONSE
    from services.email_sender import email_sender
    from models.database import log_activity, count_followups_for_firm

    logger.info("Scheduled follow-up check started.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Download latest spreadsheet
        loop.run_until_complete(onedrive_service.download_spreadsheet())

        # Check for due follow-ups
        due_firms = spreadsheet_service.get_followup_due()
        if not due_firms:
            logger.info("No follow-ups due.")
            return

        templates = spreadsheet_service.get_email_templates()
        sent = 0
        no_response = 0

        for firm in due_firms:
            followup_count = count_followups_for_firm(firm["firmenname"])

            if followup_count >= settings.max_follow_ups:
                spreadsheet_service.mark_no_response(firm["row"])
                log_activity(
                    action_type="marked_no_response",
                    firm_name=firm["firmenname"],
                    firm_row=firm["row"],
                    status_from=firm["status"],
                    status_to=STATUS_NO_RESPONSE,
                    details=f"Scheduled: max follow-ups ({settings.max_follow_ups}) reached.",
                )
                no_response += 1
                continue

            template_key = f"followup_{followup_count + 1}"
            template = templates.get(template_key) or templates.get("followup", {})
            if not template:
                continue

            to_email = firm.get("email_general") or firm.get("email_contact")
            if not to_email:
                continue

            result = loop.run_until_complete(
                email_sender.send_email(to_email.strip(), template["subject"], template["body"])
            )

            if result.get("success"):
                spreadsheet_service.mark_followup_sent(firm["row"])
                log_activity(
                    action_type="followup_sent",
                    firm_name=firm["firmenname"],
                    firm_row=firm["row"],
                    email_to=to_email,
                    email_subject=template["subject"],
                    status_from=firm["status"],
                    status_to=STATUS_FOLLOWUP_SENT,
                    details="Scheduled follow-up.",
                )
                sent += 1

        # Upload updated spreadsheet
        if sent > 0 or no_response > 0:
            loop.run_until_complete(onedrive_service.upload_spreadsheet())

        logger.info(
            f"Scheduled follow-up complete: {sent} sent, {no_response} marked no response."
        )

    except Exception as e:
        logger.error(f"Scheduled follow-up check failed: {e}")
        log_activity(
            action_type="scheduler_error",
            details=str(e),
        )
    finally:
        loop.close()


def _run_inbox_check():
    """Synchronous wrapper to run the async inbox check."""
    from services.spreadsheet import spreadsheet_service
    from services.inbox_monitor import inbox_monitor
    from models.database import log_activity

    logger.info("Scheduled inbox check started.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        contacted = spreadsheet_service.get_contacted_firms()
        if not contacted:
            logger.info("No contacted firms to monitor.")
            return

        results = loop.run_until_complete(
            inbox_monitor.check_for_replies(contacted, dry_run=False)
        )

        for r in results:
            if r.get("action") == "reply_detected":
                log_activity(
                    action_type="reply_detected",
                    firm_name=r["firm"],
                    email_to=r["email"],
                    status_from=r["status_from"],
                    status_to=r["status_to"],
                    details=f"Scheduled: Reply subject: {r.get('reply_subject', '')}",
                )

        detected = sum(1 for r in results if r.get("action") == "reply_detected")
        logger.info(f"Scheduled inbox check complete: {detected} replies detected.")

    except Exception as e:
        logger.error(f"Scheduled inbox check failed: {e}")
        log_activity(
            action_type="scheduler_error",
            details=f"Inbox check error: {e}",
        )
    finally:
        loop.close()


def start_scheduler():
    """Start the background scheduler with daily follow-up and periodic inbox checks."""
    scheduler.add_job(
        _run_followup_check,
        trigger=CronTrigger(hour=9, minute=0),  # Run daily at 9:00 AM
        id="daily_followup_check",
        name="Daily follow-up check",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_inbox_check,
        trigger=CronTrigger(minute=f"*/{settings.inbox_check_interval_minutes}"),
        id="periodic_inbox_check",
        name="Periodic inbox check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"Scheduler started — daily follow-up at 09:00, "
        f"inbox check every {settings.inbox_check_interval_minutes} min."
    )


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
