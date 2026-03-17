"""OneDrive service — download and upload the client tracking spreadsheet.

Uses Microsoft Graph API to:
- Download the .xlsx file from OneDrive to a local temp copy
- Upload the modified .xlsx back to OneDrive after updates
"""

import logging
from pathlib import Path

import httpx

from config import settings
from auth.msal_auth import auth

logger = logging.getLogger(__name__)

LOCAL_XLSX_PATH = Path("./data/client_tracking.xlsx")


class OneDriveService:
    """Handles OneDrive file operations via Microsoft Graph API."""

    def __init__(self):
        self.base_url = settings.graph_base_url

    def _get_headers(self) -> dict:
        """Build auth headers with current access token."""
        token = auth.get_access_token()
        if not token:
            raise RuntimeError(
                "Not authenticated. Please complete the device code flow first."
            )
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _file_url(self) -> str:
        """Build the Graph API URL for the OneDrive file."""
        # Encode the file path for the API
        file_path = settings.onedrive_file_path.strip("/")
        return f"{self.base_url}/me/drive/root:/{file_path}"

    async def download_spreadsheet(self) -> Path:
        """Download the xlsx file from OneDrive to local storage.

        Returns:
            Path to the downloaded local file.

        Raises:
            RuntimeError: If download fails.
        """
        LOCAL_XLSX_PATH.parent.mkdir(parents=True, exist_ok=True)

        url = f"{self._file_url()}:/content"
        headers = self._get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, follow_redirects=True)

            if response.status_code == 200:
                LOCAL_XLSX_PATH.write_bytes(response.content)
                logger.info(f"Downloaded spreadsheet to {LOCAL_XLSX_PATH}")
                return LOCAL_XLSX_PATH
            else:
                error_msg = f"Failed to download file: {response.status_code} — {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

    async def upload_spreadsheet(self, local_path: Path | None = None) -> dict:
        """Upload the (modified) xlsx file back to OneDrive.

        Args:
            local_path: Path to the local file to upload. Defaults to LOCAL_XLSX_PATH.

        Returns:
            Graph API response dict with file metadata.

        Raises:
            RuntimeError: If upload fails.
        """
        path = local_path or LOCAL_XLSX_PATH
        if not path.exists():
            raise FileNotFoundError(f"Local file not found: {path}")

        url = f"{self._file_url()}:/content"
        headers = self._get_headers()
        headers["Content-Type"] = "application/octet-stream"

        file_bytes = path.read_bytes()

        async with httpx.AsyncClient() as client:
            response = await client.put(
                url, headers=headers, content=file_bytes
            )

            if response.status_code in (200, 201):
                logger.info(f"Uploaded spreadsheet from {path}")
                return response.json()
            else:
                error_msg = f"Failed to upload file: {response.status_code} — {response.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

    async def get_file_metadata(self) -> dict:
        """Get metadata for the OneDrive file (size, modified date, etc.)."""
        headers = self._get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.get(self._file_url(), headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                raise RuntimeError(
                    f"Failed to get file metadata: {response.status_code} — {response.text}"
                )


# Singleton instance
onedrive_service = OneDriveService()
