"""Spreadsheet service — parse and update the client tracking xlsx.

Column mapping (architecture firms tab):
  A: Firmenname          B: Standort           C: Website
  D: E-Mail-Adresse-Alg  E: Telefonnummer      F: Ansprechpartner
  G: Position            H: E-Mail-AP          I: Telefonnummer-A
  J: LinkedIn            K: Status             L: Anmerkungen
  M: Datum gesendet      N: Letzte Kommunikation

Status values:
  noch nicht kontaktiert  → ready for outreach
  email gesendet          → initial email sent
  follow up fällig        → follow-up due (7+ days)
  follow up gesendet      → follow-up sent
  in kontakt              → conversation started (manual)
  keine Antwort           → no response after all follow-ups
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from config import settings

logger = logging.getLogger(__name__)

# Column indices (1-based for openpyxl)
COL = {
    "firmenname": 1,       # A
    "standort": 2,         # B
    "website": 3,          # C
    "email_general": 4,    # D
    "telefon": 5,          # E
    "ansprechpartner": 6,  # F
    "position": 7,         # G
    "email_contact": 8,    # H
    "telefon_contact": 9,  # I
    "linkedin": 10,        # J
    "status": 11,          # K
    "anmerkungen": 12,     # L
    "datum_gesendet": 13,  # M
    "letzte_kommunikation": 14,  # N
}

DATE_FORMAT = "%d.%m.%Y"

SHEET_NAME = "Architekturbüros"
TEMPLATES_SHEET = "Email Vorlagen"

# Status constants (lowercased — the code lowercases cell values on read)
STATUS_NOT_CONTACTED = "noch nicht kontaktiert"
STATUS_EMAIL_SENT = "email gesendet"
STATUS_FOLLOWUP_DUE = "follow-up fällig"
STATUS_FOLLOWUP_SENT = "follow up gesendet"
STATUS_IN_CONTACT = "in kontakt"
STATUS_NO_RESPONSE = "keine rückmeldung"

# Statuses that should NOT receive new emails
ACTIVE_STATUSES = {
    STATUS_EMAIL_SENT,
    STATUS_IN_CONTACT,
    STATUS_FOLLOWUP_SENT,
}


class SpreadsheetService:
    """Read and write the client tracking spreadsheet."""

    def __init__(self, file_path: Path | None = None):
        self.file_path = file_path or Path("./data/client_tracking.xlsx")

    def _open_workbook(self):
        """Open the workbook, ensuring columns M and N exist."""
        wb = load_workbook(self.file_path)
        ws = wb[SHEET_NAME]
        self._ensure_tracking_columns(ws)
        return wb, ws

    def _ensure_tracking_columns(self, ws: Worksheet):
        """Add Datum gesendet (M) and Letzte Kommunikation (N) headers if missing."""
        header_m = ws.cell(row=1, column=COL["datum_gesendet"]).value
        header_n = ws.cell(row=1, column=COL["letzte_kommunikation"]).value

        if not header_m:
            ws.cell(row=1, column=COL["datum_gesendet"], value="Datum gesendet")
            logger.info("Added 'Datum gesendet' header in column M.")
        if not header_n:
            ws.cell(row=1, column=COL["letzte_kommunikation"], value="Letzte Kommunikation")
            logger.info("Added 'Letzte Kommunikation' header in column N.")

    def _row_to_firm(self, ws: Worksheet, row: int) -> dict:
        """Convert a spreadsheet row to a firm dict."""
        def cell(col_key):
            return ws.cell(row=row, column=COL[col_key]).value

        return {
            "row": row,
            "firmenname": cell("firmenname") or "",
            "standort": cell("standort") or "",
            "website": cell("website") or "",
            "email_general": cell("email_general") or "",
            "telefon": cell("telefon") or "",
            "ansprechpartner": cell("ansprechpartner") or "",
            "position": cell("position") or "",
            "email_contact": cell("email_contact") or "",
            "telefon_contact": cell("telefon_contact") or "",
            "linkedin": cell("linkedin") or "",
            "status": (cell("status") or "").strip().lower(),
            "anmerkungen": cell("anmerkungen") or "",
            "datum_gesendet": cell("datum_gesendet") or "",
            "letzte_kommunikation": cell("letzte_kommunikation") or "",
        }

    def get_all_firms(self) -> list[dict]:
        """Read all firms from the spreadsheet (skipping header row)."""
        wb, ws = self._open_workbook()
        firms = []
        for row in range(2, ws.max_row + 1):
            name = ws.cell(row=row, column=COL["firmenname"]).value
            if not name:
                continue  # skip empty rows
            firms.append(self._row_to_firm(ws, row))
        wb.close()
        return firms

    def get_firms_by_status(self, status: str) -> list[dict]:
        """Get all firms matching a specific status."""
        return [f for f in self.get_all_firms() if f["status"] == status.lower()]

    def get_status_summary(self) -> dict[str, int]:
        """Get a count of firms per status for the dashboard."""
        firms = self.get_all_firms()
        summary: dict[str, int] = {}
        for firm in firms:
            s = firm["status"] or "unknown"
            summary[s] = summary.get(s, 0) + 1
        return summary

    def get_ready_for_outreach(self) -> list[dict]:
        """Get firms ready for initial outreach."""
        return self.get_firms_by_status(STATUS_NOT_CONTACTED)

    def get_followup_due(self) -> list[dict]:
        """Get firms where follow-up is due.

        Includes:
        - Firms already marked as 'follow-up fällig' (pre-flagged as due)
        - Firms with status 'email gesendet' or 'follow up gesendet'
          where 7+ days have elapsed since the last email
        """
        firms = self.get_all_firms()
        due = []
        now = datetime.now()
        threshold = timedelta(days=settings.follow_up_days)

        for firm in firms:
            # Already flagged as due — include directly
            if firm["status"] == STATUS_FOLLOWUP_DUE:
                due.append(firm)
                continue

            # Check date-based eligibility for sent statuses
            if firm["status"] not in (STATUS_EMAIL_SENT, STATUS_FOLLOWUP_SENT):
                continue

            date_str = firm["letzte_kommunikation"] or firm["datum_gesendet"]
            if not date_str:
                continue

            try:
                if isinstance(date_str, datetime):
                    last_date = date_str
                else:
                    last_date = datetime.strptime(str(date_str).strip(), DATE_FORMAT)

                if now - last_date >= threshold:
                    due.append(firm)
            except ValueError as e:
                logger.warning(
                    f"Invalid date for {firm['firmenname']}: {date_str} — {e}"
                )

        return due

    def count_followups_sent(self, firm: dict) -> int:
        """Count how many follow-ups have been sent for a firm.

        Checks if follow-up datum has been populated. In V1, we track
        the count by checking both datum_gesendet and letzte_kommunikation fields
        plus the status progression.
        """
        # If status is 'follow up gesendet', at least one follow-up was sent
        if firm["status"] == STATUS_FOLLOWUP_SENT:
            # If both dates exist, at least 1 follow-up happened
            # For more granular tracking, the activity log should be consulted
            return 1  # Placeholder — will be enhanced with activity log count
        return 0

    def update_status(
        self,
        row: int,
        new_status: str,
        date_column: str = "datum_gesendet",
        date_value: str | None = None,
    ):
        """Update a firm's status and optionally set a date.

        Args:
            row: The spreadsheet row number.
            new_status: The new status value.
            date_column: Which date column to update ('datum_gesendet' or 'letzte_kommunikation').
            date_value: The date string to set. Defaults to today.
        """
        wb, ws = self._open_workbook()

        ws.cell(row=row, column=COL["status"], value=new_status)

        if date_value is None:
            date_value = datetime.now().strftime(DATE_FORMAT)

        if date_column in COL:
            ws.cell(row=row, column=COL[date_column], value=date_value)

        wb.save(self.file_path)
        wb.close()

        firm_name = ws.cell(row=row, column=COL["firmenname"]).value
        logger.info(f"Updated row {row} ({firm_name}): status='{new_status}', {date_column}='{date_value}'")

    def mark_email_sent(self, row: int):
        """Mark a firm as having received the initial outreach email.

        Sets both Datum gesendet (M) and Letzte Kommunikation (N) to today.
        """
        today = datetime.now().strftime(DATE_FORMAT)
        wb, ws = self._open_workbook()
        ws.cell(row=row, column=COL["status"], value=STATUS_EMAIL_SENT)
        ws.cell(row=row, column=COL["datum_gesendet"], value=today)
        ws.cell(row=row, column=COL["letzte_kommunikation"], value=today)
        wb.save(self.file_path)
        wb.close()
        firm_name = ws.cell(row=row, column=COL["firmenname"]).value
        logger.info(f"Updated row {row} ({firm_name}): status='{STATUS_EMAIL_SENT}', datum_gesendet='{today}', letzte_kommunikation='{today}'")

    def mark_followup_sent(self, row: int):
        """Mark a firm as having received a follow-up email."""
        self.update_status(row, STATUS_FOLLOWUP_SENT, "letzte_kommunikation")

    def mark_no_response(self, row: int):
        """Mark a firm as no response after all follow-ups exhausted."""
        self.update_status(row, STATUS_NO_RESPONSE, "letzte_kommunikation")

    def mark_reply_received(self, row: int, reply_date: str):
        """Mark a firm as having received a reply (transition to 'in Kontakt').

        Args:
            row: The spreadsheet row number.
            reply_date: Date string (DD.MM.YYYY) when the reply was received.
        """
        self.update_status(row, STATUS_IN_CONTACT, "letzte_kommunikation", date_value=reply_date)

    def get_contacted_firms(self) -> list[dict]:
        """Get firms that have been contacted and are awaiting replies.

        Returns firms with status: email gesendet, follow up gesendet,
        or follow-up fällig — these are the ones we should monitor for replies.
        """
        contacted_statuses = {
            STATUS_EMAIL_SENT,
            STATUS_FOLLOWUP_SENT,
            STATUS_FOLLOWUP_DUE,
        }
        return [f for f in self.get_all_firms() if f["status"] in contacted_statuses]

    def get_email_templates(self) -> dict:
        """Read email templates from the email templates tab.

        Spreadsheet layout (confirmed):
            Column A: Vorlage (template name)
            Column B: Betreff (subject)
            Column C: Email (body)

        Row 2: initial template (name varies, e.g. "Architekturbüros - Standard Email")
        Row 3: followup_1
        Row 4: followup_2

        Returns a dict with normalised keys: 'initial', 'followup_1', 'followup_2'.
        The first non-followup template is treated as 'initial'.
        """
        wb = load_workbook(self.file_path)
        try:
            ws = wb[TEMPLATES_SHEET]
        except KeyError:
            logger.warning(f"Sheet '{TEMPLATES_SHEET}' not found in spreadsheet.")
            return {}

        templates = {}
        initial_found = False

        for row in range(2, ws.max_row + 1):
            name = ws.cell(row=row, column=1).value  # Vorlage
            subject = ws.cell(row=row, column=2).value  # Betreff
            body = ws.cell(row=row, column=3).value  # Email
            if not name:
                continue

            key = str(name).strip().lower()
            template_data = {
                "subject": subject or "",
                "body": body or "",
                "original_name": str(name).strip(),
            }

            # Normalise: if the name starts with "followup", keep as-is
            # Otherwise treat as the initial outreach template
            if key.startswith("followup"):
                templates[key] = template_data
            else:
                templates["initial"] = template_data
                initial_found = True

        if not initial_found:
            logger.warning("No initial email template found in the templates tab.")

        wb.close()
        return templates


# Singleton instance
spreadsheet_service = SpreadsheetService()
