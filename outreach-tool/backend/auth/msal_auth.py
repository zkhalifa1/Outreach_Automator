"""Microsoft authentication via MSAL using device code flow.

Device code flow is ideal for this tool because:
- No web server callback needed for auth
- Works on any machine (Windows, Mac, Linux)
- User authenticates in their own browser
- Tokens are cached locally for seamless re-auth
"""

import json
import logging
from pathlib import Path

import msal

from config import settings

logger = logging.getLogger(__name__)


class MSALAuth:
    """Handles Microsoft authentication and token management."""

    def __init__(self):
        self._app: msal.PublicClientApplication | None = None
        self._token_cache = msal.SerializableTokenCache()
        self._load_token_cache()

    def _load_token_cache(self):
        """Load cached tokens from disk if available."""
        cache_path = Path(settings.token_cache_path)
        if cache_path.exists():
            try:
                self._token_cache.deserialize(cache_path.read_text())
                logger.info("Token cache loaded from disk.")
            except Exception as e:
                logger.warning(f"Failed to load token cache: {e}")

    def _save_token_cache(self):
        """Persist token cache to disk."""
        if self._token_cache.has_state_changed:
            cache_path = Path(settings.token_cache_path)
            cache_path.write_text(self._token_cache.serialize())
            logger.info("Token cache saved to disk.")

    @property
    def app(self) -> msal.PublicClientApplication:
        """Lazily initialise the MSAL public client application."""
        if self._app is None:
            if not settings.azure_client_id:
                raise ValueError(
                    "AZURE_CLIENT_ID is not set. Please configure it in your .env file."
                )
            self._app = msal.PublicClientApplication(
                client_id=settings.azure_client_id,
                authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
                token_cache=self._token_cache,
            )
        return self._app

    def get_accounts(self) -> list[dict]:
        """Return cached accounts."""
        return self.app.get_accounts()

    def acquire_token_silent(self) -> dict | None:
        """Attempt to acquire a token silently from cache.

        Returns the token result dict if successful, None otherwise.
        """
        accounts = self.get_accounts()
        if not accounts:
            return None

        result = self.app.acquire_token_silent(
            scopes=settings.graph_scopes,
            account=accounts[0],
        )
        if result and "access_token" in result:
            self._save_token_cache()
            return result
        return None

    def initiate_device_flow(self) -> dict:
        """Start a device code flow.

        Returns the flow dict containing 'user_code' and 'message'
        that the user needs to complete auth in their browser.
        """
        flow = self.app.initiate_device_flow(scopes=settings.graph_scopes)
        if "user_code" not in flow:
            raise RuntimeError(
                f"Failed to initiate device flow: {flow.get('error_description', 'Unknown error')}"
            )
        return flow

    def acquire_token_by_device_flow(self, flow: dict) -> dict:
        """Complete the device code flow after user has authenticated.

        Args:
            flow: The flow dict returned by initiate_device_flow().

        Returns:
            Token result dict with 'access_token' on success,
            or 'error' / 'error_description' on failure.
        """
        result = self.app.acquire_token_by_device_flow(flow)
        self._save_token_cache()
        return result

    def get_access_token(self) -> str | None:
        """Get a valid access token, trying cache first.

        Returns the access token string or None if not authenticated.
        """
        result = self.acquire_token_silent()
        if result:
            return result["access_token"]
        return None

    def is_authenticated(self) -> bool:
        """Check if we have a valid cached token."""
        return self.get_access_token() is not None

    def logout(self):
        """Clear token cache and force re-authentication."""
        accounts = self.get_accounts()
        for account in accounts:
            self.app.remove_account(account)
        self._save_token_cache()
        logger.info("Logged out — token cache cleared.")


# Singleton instance
auth = MSALAuth()
