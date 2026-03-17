# Outreach Automator

A locally-hosted web dashboard that automates B2B email outreach for an architecture firm's business development workflow. It connects to the user's Microsoft OneDrive (to read/write a client tracking spreadsheet) and Outlook (to send emails via Microsoft Graph API), replacing an entirely manual copy-paste workflow.

---

## What It Does

- **Sends initial outreach emails** to a list of firms pulled from an Excel spreadsheet stored in OneDrive
- **Tracks status** per firm: not contacted → email sent → follow-up sent → in contact / no response
- **Automates follow-ups**: a background scheduler checks daily and sends follow-up emails to firms that haven't replied after 7 days
- **Monitors inbox**: polls Outlook every 30 minutes for replies and auto-transitions firms to "in contact"
- **Logs everything**: full activity log with dry-run support for safe testing

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 / FastAPI |
| Frontend | Single-file React (CDN, no Node.js required) |
| Auth | MSAL Python — device code flow |
| Email & Files | Microsoft Graph API (Outlook + OneDrive) |
| Scheduling | APScheduler |
| Database | SQLite (local activity log) |
| Excel | openpyxl |

---

## Project Structure

```
outreach-tool/
├── backend/
│   ├── main.py                 # FastAPI app + static file serving
│   ├── config.py               # Settings loaded from .env
│   ├── auth/
│   │   └── msal_auth.py        # Device code flow + token caching
│   ├── services/
│   │   ├── onedrive.py         # OneDrive download/upload
│   │   ├── spreadsheet.py      # Excel read/write (firms, templates, statuses)
│   │   ├── email_sender.py     # Outlook send via Graph API
│   │   ├── inbox_monitor.py    # Inbox reply detection
│   │   └── scheduler.py        # APScheduler background jobs
│   ├── models/
│   │   └── database.py         # SQLite activity log
│   ├── routes/
│   │   ├── auth_routes.py      # /api/auth
│   │   ├── dashboard.py        # /api/dashboard
│   │   ├── outreach.py         # /api/outreach
│   │   └── logs.py             # /api/logs
│   ├── static/
│   │   └── index.html          # Single-file React dashboard
│   └── requirements.txt
├── setup.bat                   # One-click Windows setup
├── start.bat                   # One-click Windows launcher
├── .env.example                # Config template
└── PROJECT_CONTEXT.md          # Full project context and design decisions
```

---

## Setup

### Prerequisites
- Python 3.11+
- A Microsoft 365 account with Exchange (for email) and OneDrive for Business (for spreadsheet access)
- An app registered in Azure Entra ID (see below)

### Azure App Registration
1. Go to [portal.azure.com](https://portal.azure.com) and register a new app in the same tenant as your Microsoft 365 account
2. Under **Authentication**, add a Mobile/Desktop redirect URI: `http://localhost` and enable "Allow public client flows"
3. Under **API Permissions**, add:
   - `Files.ReadWrite`
   - `Mail.Send`
   - `Mail.Read`
   - `User.Read`
4. Note your **Client ID** and **Tenant ID** for the `.env` file

### Installation

**Windows:**
```bat
setup.bat
```

**macOS / Linux:**
```bash
cd outreach-tool/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

```bash
cp outreach-tool/.env.example outreach-tool/.env
```

Edit `.env` with your Azure credentials and OneDrive file path:

```env
AZURE_CLIENT_ID=your-client-id
AZURE_TENANT_ID=your-tenant-id
ONEDRIVE_FILE_PATH=Sales Folder/Architecture Folder/client_tracking.xlsx

# Set to true to test with a local .xlsx file (no OneDrive needed)
USE_LOCAL_FILE=false
```

### Running

**Windows:**
```bat
start.bat
```

**macOS / Linux:**
```bash
cd outreach-tool/backend
source venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://localhost:8000` in your browser and sign in with your Microsoft account.

---

## Local File Testing Mode

To test without a Microsoft 365 Business account (no OneDrive access required):

1. Set `USE_LOCAL_FILE=true` in `.env`
2. Place your `.xlsx` file at `outreach-tool/backend/data/client_tracking.xlsx`
3. The dashboard will read directly from disk — all features (preview, send, follow-ups, logging) work in this mode

---

## Spreadsheet Format

The tool expects an Excel file with two tabs:

**Firms tab** (`Architekturbüros`) — one row per firm with columns:
`Firmenname`, `Standort`, `Website`, `E-Mail-Adresse - Alg.`, `Telefonnummer`, `Ansprechpartner`, `Position`, `E-Mail-AP`, `Telefonnummer-A`, `LinkedIn`, `Status`, `Anmerkungen`, `Datum gesendet`, `Letzte Kommunikation`

**Templates tab** (`Email Vorlagen`) — columns: `Vorlage` (name), `Betreff` (subject), `Email` (body)
- Row 2: initial outreach template
- Row 3: `followup_1`
- Row 4: `followup_2`

See `PROJECT_CONTEXT.md` for the full column mapping and status value reference.
