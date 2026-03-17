# Outreach Automation Tool — Project Context & State

**Document Created:** February 16, 2026
**Status:** V1 feature-complete — all outreach features tested live, inbox monitoring built, status tracking unified
**Last Updated:** March 1, 2026
**Last Updated By:** Antigravity (AI assistant) in collaboration with Ziad

---

## 1. Project Overview

### What This Is
A locally-hosted web dashboard that automates email outreach for an architecture firm's business development workflow. The tool connects to the user's OneDrive (to read/write a client tracking spreadsheet) and Outlook (to send emails), providing a single interface to manage outreach campaigns.

### Who It's For
- **Primary user:** Business development / outreach professional at an architecture firm based in Germany
- **End users (future):** Other team members who will have the tool installed on their own machines
- **Language context:** German-language data in spreadsheets, German email templates, UI can be English

### Problem It Solves
The current workflow is entirely manual: the user opens OneDrive, navigates to an Excel file, checks statuses, switches to Outlook, copies/pastes email templates, formats them, sends them, then goes back to update the spreadsheet. This tool eliminates all of that repetitive work.

---

## 2. Current Manual Workflow (As-Is)

1. Open Chrome → navigate to OneDrive
2. Navigate to: My Files → Sales Folder → Architecture Folder
3. Open `.xlsx` file containing potential client data
4. Go to the **"architecture firms"** tab
5. Check the **Status** column (Column K)
6. For firms with status `noch nicht kontaktiert`:
   - Open Outlook in browser
   - Insert firm's contact email
   - Switch back to Excel → go to **"email templates"** tab
   - Copy subject line and email body
   - Paste into Outlook, format (capitalization, paragraphs)
   - Send the email
   - Return to Excel → update status to `email gesendet` and record the date
7. For firms where email was sent 7+ days ago → manually flag for follow-up

---

## 3. Target Automated Workflow (To-Be)

1. User opens browser to `localhost:8000`
2. Dashboard displays all firms grouped by status with counts
3. **Initial outreach:** User clicks "Send Outreach" → selects email column preference (general or contact person) → previews list → confirms → tool sends emails, updates spreadsheet
4. **Follow-ups:** Background job runs daily checking for `email gesendet` entries older than 7 days → auto-sends follow-up email → updates status
5. **Manual trigger:** User can trigger follow-up check on demand from dashboard
6. **Activity log:** All actions logged and visible on dashboard

---

## 4. Spreadsheet Structure

### File Details
- **Filename:** `Vertriebsliste_Architektur.xlsx` (copied to `client_tracking.xlsx` locally)
- **Format:** `.xlsx` (Excel file stored in OneDrive)
- **Location in OneDrive:** Configurable per user via `.env` file
- **Local file mode:** When `USE_LOCAL_FILE=true` in `.env`, the file is read from `backend/data/client_tracking.xlsx` directly (bypasses OneDrive API)
- **Tabs in real file:**
  - `Architekturbüros` — main architecture firms (54 rows, primary tab used by tool)
  - `Innenarchitekturbüros` — interior architecture firms (22 rows, not yet used)
  - `Projektentwickler` — project developers (28 rows, not yet used)
  - `Generalunternehmen` — general contractors (24 rows, not yet used)
  - `Projektsteuerer_Baumanagement` — project managers (25 rows, not yet used)
  - `Bauträger` — building developers (25 rows, not yet used)
  - `Email Vorlagen` — email templates (3 templates)

### Architecture Firms Tab — Column Mapping

| Column | Header              | Description                    | Used By Tool        |
|--------|---------------------|--------------------------------|---------------------|
| A      | Firmenname          | Company name                   | Display, logging    |
| B      | Standort            | Location / city                | Display             |
| C      | Website             | Company website                | Display             |
| D      | E-Mail-Adresse - Alg. | General company email        | **Email target (option 1)** |
| E      | Telefonnummer       | Company phone number           | Display             |
| F      | Ansprechpartner     | Contact person name            | Display, logging    |
| G      | Position            | Contact person's role          | Display             |
| H      | E-Mail-AP           | Contact person's email         | **Email target (option 2)** |
| I      | Telefonnummer-A     | Contact person's phone         | Display             |
| J      | LinkedIn            | LinkedIn profile URL           | Display             |
| K      | Status              | Outreach status                | **Core logic field** |
| L      | Anmerkungen         | Notes / remarks                | Display             |
| **M**  | **Datum gesendet**  | **Date initial email sent**    | **Auto-populated by tool** |
| **N**  | **Letzte Kommunikation** | **Date of last communication** | **Auto-updated on every outgoing email + reply detection** |

> **Note:** Column N was originally "Follow-up Datum" — repurposed on March 1, 2026 to track the date of the most recent communication (initial send, follow-up, or detected reply). Column M is the original send date and never changes.

### Email Templates Tab — Column Mapping

| Column | Header   | Description         |
|--------|----------|---------------------|
| A      | Vorlage  | Template name       |
| B      | Betreff  | Email subject line  |
| C      | Email    | Email body content  |

| Row | Template Name                          | Purpose              |
|-----|----------------------------------------|----------------------|
| 2   | Architekturbüros - Standard Email      | Initial outreach     |
| 3   | followup_1                             | First follow-up      |
| 4   | followup_2                             | Second follow-up     |

> The tool normalises template names: the first non-followup row is treated as `initial`, and `followup_1`/`followup_2` are matched by name.

### Status Values (Column K)

> **Note:** All status values were unified on March 1, 2026 to consistent German lowercase. Empty statuses were set to `noch nicht kontaktiert`. The tool lowercases all status values when reading. The frontend displays English translations.

| Status (in code, lowercase) | Meaning | Set By |
|-----------------------------|---------|--------|
| `noch nicht kontaktiert` | Not contacted yet — ready for outreach | Manual / default |
| `email gesendet` | Initial email sent, awaiting response | Tool |
| `follow-up fällig` | Follow-up is due (7+ days elapsed) | Tool |
| `follow up gesendet` | Follow-up email has been sent | Tool |
| `in kontakt` | Conversation started / reply detected | Tool (inbox monitor) or Manual |
| `keine rückmeldung` | No response after all follow-ups | Tool |

### Email Target Selection Logic
- User chooses **per batch** which email column to use:
  - Column D (`E-Mail-Adresse - Alg.`) — general company email
  - Column H (`E-Mail-AP`) — contact person's email
- This selection is made in the dashboard UI before confirming a send batch

---

## 5. Business Rules

### Follow-Up Rules
- **Trigger:** 7 days after last communication (based on `Letzte Kommunikation` in Column N, falling back to `Datum gesendet` in Column M)
- **Number of follow-ups:** 2 follow-ups before marking `keine Rückmeldung`
- **Follow-up email templates:** Created by owner — `followup_1` and `followup_2` in the "email templates" tab
- **After final follow-up:** Status changes to `keine Antwort`

### Date Format
- **DD.MM.YYYY** — German standard (e.g., `16.02.2026`)

### Duplicate Prevention
- Tool must check the activity log before sending to ensure no duplicate emails are sent to the same firm

### Safety Features
- Preview + confirmation dialog before any batch send
- Dry run mode available
- Rate limiting: small delay between sends (Microsoft Graph limit: ~30 messages/minute)
- Full activity log with audit trail
- Will not send to firms that already have an active status (`email gesendet`, `in kontakt`, etc.)

---

## 6. Tech Stack

| Component      | Technology                          | Notes                                    |
|----------------|-------------------------------------|------------------------------------------|
| Backend        | **Python 3.11+ / FastAPI**          | Async-friendly, lightweight              |
| Frontend       | **Single-file React (CDN)**         | Served by FastAPI, no Node.js required   |
| File Access    | **Microsoft Graph API (OneDrive)**  | Read/download/upload .xlsx               |
| Email Sending  | **Microsoft Graph API (Outlook)**   | Send from user's work Outlook account    |
| Auth           | **MSAL Python (device code flow)**  | Public client, tokens cached locally     |
| Scheduling     | **APScheduler**                     | Background jobs for follow-up checks     |
| Database       | **SQLite**                          | Local storage for config, logs, state    |
| Excel Parsing  | **openpyxl**                        | Read/write .xlsx files                   |
| OS             | **Windows** (target) / **macOS** (dev) | Cross-platform Python backend        |

### Microsoft Graph API Scopes Required
- `Files.ReadWrite` — access OneDrive files
- `Mail.Send` — send emails via Outlook
- `Mail.Read` — read inbox for reply detection (inbox monitor)
- `User.Read` — basic user profile (for auth confirmation)

### Azure Entra ID Configuration
- **App type:** Public client (Allow public client flows = Yes)
- **Redirect URI:** `http://localhost` (Mobile/Desktop)
- **Auth flow:** Device code flow
- **App registered in:** Organizational tenant (single-tenant)
  - App ID: `<configured in .env>`
  - Tenant ID: `<configured in .env>`

> **Important:** A previous app registration existed under a personal Microsoft (Hotmail) tenant but was abandoned because:
> 1. Personal accounts lack SharePoint Online (SPO) license → OneDrive Graph API calls fail with "Tenant does not have a SPO license"
> 2. When registered in the personal tenant and used with UBC's organizational account, Azure AD required admin consent (UBC blocks third-party apps)
>
> The solution was registering the app **inside UBC's tenant** via [portal.azure.com](https://portal.azure.com). The UBC student tenant still lacks SPO, which is why **local file mode** was implemented as a workaround for testing.

### Local File Testing Mode
- **Config:** `USE_LOCAL_FILE=true` in `.env`
- **Behavior:** When enabled, the "Sync Spreadsheet" button checks for the local file at `backend/data/client_tracking.xlsx` instead of calling OneDrive Graph API
- **Purpose:** Allows full testing of all dashboard features (preview, send, follow-ups, logging) without requiring a Microsoft 365 Business account with SPO
- **Production use:** Set `USE_LOCAL_FILE=false` (or remove) and use the architecture firm's Microsoft 365 work account which will have proper OneDrive for Business/SPO licensing

---

## 7. Architecture & Project Structure

```
outreach-tool/
├── backend/
│   ├── main.py                 # FastAPI app entry point + serves frontend
│   ├── config.py               # App configuration from .env
│   ├── auth/
│   │   └── msal_auth.py        # MSAL device code flow + token caching
│   ├── services/
│   │   ├── onedrive.py         # OneDrive download/upload via Graph API
│   │   ├── email_sender.py     # Outlook email sending via Graph API
│   │   ├── inbox_monitor.py    # Inbox reply detection via Graph API ($search)
│   │   ├── spreadsheet.py      # openpyxl read/write (firms, templates, statuses)
│   │   └── scheduler.py        # APScheduler: daily follow-up (9 AM) + inbox check (30 min)
│   ├── models/
│   │   └── database.py         # SQLite activity log + config store
│   ├── routes/
│   │   ├── auth_routes.py      # Login/logout/status endpoints
│   │   ├── dashboard.py        # Summary, firms, sync endpoints
│   │   ├── outreach.py         # Preview, send, follow-up endpoints
│   │   └── logs.py             # Activity log endpoints
│   ├── static/
│   │   └── index.html          # Single-file React dashboard (CDN-loaded)
│   └── requirements.txt
├── setup.bat                   # One-click Windows setup script
├── start.bat                   # One-click app launcher
├── .env                        # Active config (with real Azure credentials)
├── .env.example                # Template for distribution
└── PROJECT_CONTEXT.md          # This file
```

> **Design principle:** Keep clean separation between auth, services, and routes so that future scaling (multi-user, cloud hosting, Docker) requires minimal refactoring.

---

## 8. Deployment & Distribution Strategy

### Current Phase: Single Machine (Local)
- App runs locally on user's machine
- Accessed via browser at `localhost:8000`
- Setup via `setup.bat` script (Windows) or manual pip install (macOS)

### Distribution to Other Users (Next Phase)
- **Recommended approach:** Installer/setup script (`setup.bat`)
  - Installs Python dependencies into a virtual environment
  - Creates local SQLite database
  - Walks user through Microsoft login
  - User receives a folder/zip, runs `setup.bat`, follows prompts
  - **No Node.js required** — frontend is a single HTML file served by FastAPI
- **Designed for future migration to:**
  - **Docker container** (medium-term) — containerized app, user installs Docker Desktop + runs one command
  - **Cloud-hosted on Azure** (long-term) — no local install, users access via URL + Microsoft SSO

### Authentication Model
- Each user authenticates with their **own Microsoft 365 account**
- The tool accesses **their** OneDrive and sends from **their** Outlook
- No hardcoded credentials — fully delegated auth via MSAL
- Token caching for seamless re-authentication
- Device flow persisted to disk to survive server restarts

---

## 9. One-Time Setup Requirements

1. **Register an app in Azure Entra ID** (Microsoft admin portal) ✅ Done
   - Obtain: Client ID, Tenant ID
   - Enable "Allow public client flows" under Authentication → Advanced settings
   - Grant API permissions: `Files.ReadWrite`, `Mail.Send`, `User.Read`
   - **Important:** Register the app in the **same tenant** as the user's Microsoft 365 account to avoid admin consent issues

2. **Install on user's machine:**
   - Python 3.11+
   - Run `setup.bat` (Windows) or `pip install -r requirements.txt` (macOS)

3. **First-run configuration:**
   - Copy `.env.example` to `.env` and fill in Azure credentials + OneDrive path
   - For testing without OneDrive: set `USE_LOCAL_FILE=true` and place `.xlsx` in `backend/data/client_tracking.xlsx`
   - Run `start.bat` (Windows) or `uvicorn main:app` (macOS)
   - Authenticate with Microsoft account via device code flow
   - Set follow-up time window (default: 7 days)

---

## 10. Open Items & Decisions

| Item | Status | Notes |
|------|--------|-------|
| Exact OneDrive file path | ✅ Decided | Mock: `Documents/Arnold_project_trial` — configurable per user via `.env` |
| Email templates tab structure | ✅ Decided | Cols: A=Vorlage, B=Betreff, C=Email. Row 2=initial, Row 3=followup_1, Row 4=followup_2 |
| Follow-up email template | ✅ Created | Owner created followup_1 and followup_2 in the spreadsheet |
| Number of follow-ups before `keine Antwort` | ✅ Decided | **2 follow-ups**, then mark `keine Antwort` |
| Azure Entra ID access | ✅ Done | App registered, public client flow enabled, credentials in `.env` |
| IT restrictions on installing software | ❓ Unknown | Owner researching (not blocking mock/dev testing) |
| Personalization in templates | ✅ Decided | No personalization — same email to all firms |
| Follow-up trigger window | ✅ Decided | 7 days |
| Email target selection | ✅ Decided | User chooses per batch (Column D or H) |
| Date format | ✅ Decided | DD.MM.YYYY (German standard) |
| UI language | ✅ Decided | English UI, handles German data correctly |

---

## 11. Development Progress

| Milestone | Status | Notes |
|-----------|--------|-------|
| Backend scaffolding | ✅ Done | FastAPI + all services + routes |
| MSAL authentication | ✅ Working | Device code flow, token caching, persisted flow state |
| OneDrive service | ✅ Built | Download/upload via Graph API — blocked by SPO license (see Azure section) |
| Spreadsheet parser | ✅ Tested | Full column mapping, status transitions — working with real data (47 firms) |
| Email sender | ✅ Tested | Graph API + rate limiting + dry run — live-tested with real emails |
| SQLite activity log | ✅ Working | Logging, duplicate prevention, follow-up counting |
| APScheduler | ✅ Working | Daily 9 AM follow-up + 30-min inbox check |
| React dashboard | ✅ Tested | Sync, status cards, firm table, activity log — all working |
| Local file mode | ✅ Working | Bypass OneDrive API, read xlsx from `backend/data/` |
| Windows scripts | ✅ Built | `setup.bat` and `start.bat` |
| Microsoft sign-in | ✅ Tested | Working with personal Hotmail account on macOS |
| Dashboard overview | ✅ Tested | 47 firms displayed with correct status groupings |
| Preview/Send outreach | ✅ Tested | Preview batch, dry run, and live send — all working |
| Follow-up triggers | ✅ Tested | Manual trigger (dry run + live) — working |
| Status unification | ✅ Done | All statuses unified to lowercase German, empty → `noch nicht kontaktiert` |
| Letzte Kommunikation | ✅ Done | Column N repurposed to track last communication date |
| Inbox monitoring | ✅ Built | Polls Graph API via `$search`, detects replies, auto-transitions to `in kontakt` |

### Known Issues
- **OneDrive Graph API blocked:** Both personal (Hotmail) and UBC student tenants lack SPO license. The `/me/drive/root:/{path}:/content` endpoint returns `BadRequest: Tenant does not have a SPO license`. **Workaround:** local file mode. **Fix:** use the architecture firm's Microsoft 365 Business account (production)
- **Multi-tab support:** Only the `Architekturbüros` tab is currently parsed. The other 5 industry tabs have slightly different column structures and are not yet supported
- **Date format edge cases:** Some dates in the spreadsheet use 2-digit years (`09.02.26`) which don't parse with `%d.%m.%Y` — these firms are skipped during follow-up checks

---

## 12. GDPR Considerations (Germany)

Since this tool processes contact data of individuals/firms in Germany, GDPR applies. Items to address before production use:

- **Lawful basis for processing:** Legitimate interest (B2B outreach) — should be documented
- **Data minimization:** Only process data necessary for outreach
- **Audit trail:** Activity log serves as a record of processing
- **Data retention:** Consider auto-archiving or flagging old `keine Rückmeldung` entries
- **Right to erasure:** Should be able to delete a firm's data if requested
- **Data stays local:** In the single-machine version, no data leaves the user's machine (aside from emails sent)

> *This is not legal advice. The project owner should consult with their firm's data protection officer or legal counsel.*

---

## 13. Future Enhancements (Out of Scope for V1)

- Multi-tab support (Innenarchitekturbüros, Projektentwickler, etc.)
- Multi-user support with centralized cloud hosting
- Email personalization (firm name, contact person name in template)
- LinkedIn outreach automation
- Multiple outreach campaigns
- Analytics dashboard (response rates, conversion metrics)
- Integration with a proper CRM
- Docker containerization for easier distribution
- Bilingual UI (EN/DE toggle)

---

## 14. Summary for Next Session / Developer

**All core outreach features are built and tested live.** The tool can send initial emails, follow-ups, detect inbox replies, and auto-update statuses. Inbox monitoring runs automatically every 30 minutes.

The next steps are:
1. **End-to-end inbox monitor test:** Send a test email from the tool to your own address, reply to it, then run "Check Inbox" to verify auto-detection and status transition to `in kontakt`
2. **Production deployment:** Connect to the architecture firm's Microsoft 365 Business account for production OneDrive access
3. **Fix 2-digit year dates** in the spreadsheet (`09.02.26` → `09.02.2026`) so all firms are covered by follow-up checks
4. **Multi-tab support** — extend to Innenarchitekturbüros and other tabs

**To resume development:**
1. `cd outreach-tool/backend`
2. `source venv/bin/activate` (macOS) or `venv\Scripts\activate` (Windows)
3. `python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
4. Open `http://localhost:8000`
5. Sign in with Microsoft account (has `Mail.Read`, `Mail.Send`, `Files.ReadWrite`, `User.Read` scopes)
6. Click "Sync Spreadsheet" to load the local file
7. Use **Send Outreach** tab: Preview Batch → Send → Follow-Ups → Check Inbox
