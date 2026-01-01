"""Google Drive Integration for Tax Tracker.

Handles OAuth 2.0 authentication and file uploads to Google Drive.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

# Scopes required for Google Drive file upload
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Paths for credentials and tokens
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CREDENTIALS_FILE = DATA_DIR / "credentials.json"
TOKEN_FILE = DATA_DIR / "gdrive_token.json"

# Redirect URI for OAuth flow
REDIRECT_URI = "http://localhost:8000/gdrive/callback"


class GoogleDriveError(Exception):
    """Custom exception for Google Drive operations."""
    pass


def get_credentials_config() -> dict | None:
    """Load Google OAuth credentials configuration.

    Returns:
        Credentials config dict or None if not configured
    """
    if not CREDENTIALS_FILE.exists():
        return None

    try:
        with open(CREDENTIALS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def is_configured() -> bool:
    """Check if Google Drive integration is configured.

    Returns:
        True if credentials.json exists and is valid
    """
    config = get_credentials_config()
    return config is not None and "web" in config


def get_stored_credentials() -> Credentials | None:
    """Load stored OAuth tokens if they exist and are valid.

    Returns:
        Valid Credentials object or None
    """
    if not TOKEN_FILE.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        # Check if credentials are expired and can be refreshed
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save refreshed credentials
                save_credentials(creds)
            except Exception:
                # If refresh fails, return None to trigger re-auth
                return None

        return creds if creds and creds.valid else None
    except Exception:
        return None


def save_credentials(creds: Credentials) -> None:
    """Save OAuth credentials to token file.

    Args:
        creds: Credentials object to save
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())


def get_authorization_url(state: Optional[str] = None) -> tuple[str, str]:
    """Generate OAuth authorization URL.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Tuple of (authorization_url, state)

    Raises:
        GoogleDriveError: If credentials not configured
    """
    if not is_configured():
        raise GoogleDriveError(
            "Google Drive not configured. Please add credentials.json to the data directory."
        )

    flow = Flow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",  # Force consent to get refresh token
    )

    return authorization_url, state


def exchange_code_for_credentials(code: str) -> Credentials:
    """Exchange authorization code for credentials.

    Args:
        code: Authorization code from OAuth callback

    Returns:
        Credentials object

    Raises:
        GoogleDriveError: If exchange fails
    """
    if not is_configured():
        raise GoogleDriveError("Google Drive not configured.")

    try:
        flow = Flow.from_client_secrets_file(
            str(CREDENTIALS_FILE),
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )

        flow.fetch_token(code=code)
        creds = flow.credentials

        # Save credentials for future use
        save_credentials(creds)

        return creds
    except Exception as e:
        raise GoogleDriveError(f"Failed to exchange authorization code: {str(e)}")


def is_authenticated() -> bool:
    """Check if user is authenticated with Google Drive.

    Returns:
        True if valid credentials exist
    """
    creds = get_stored_credentials()
    return creds is not None and creds.valid


def revoke_credentials() -> bool:
    """Revoke stored credentials and delete token file.

    Returns:
        True if successful
    """
    try:
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
        return True
    except Exception:
        return False


def upload_file(
    file_content: bytes,
    filename: str,
    mime_type: str = "application/pdf",
    folder_id: Optional[str] = None,
) -> dict:
    """Upload a file to Google Drive.

    Args:
        file_content: File content as bytes
        filename: Name for the uploaded file
        mime_type: MIME type of the file
        folder_id: Optional Google Drive folder ID

    Returns:
        Dict with file id, name, and webViewLink

    Raises:
        GoogleDriveError: If upload fails or not authenticated
    """
    creds = get_stored_credentials()
    if not creds:
        raise GoogleDriveError("Not authenticated with Google Drive.")

    try:
        service = build("drive", "v3", credentials=creds)

        # File metadata
        file_metadata = {"name": filename}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        # Upload file
        media = MediaInMemoryUpload(file_content, mimetype=mime_type)

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink",
        ).execute()

        return {
            "id": file.get("id"),
            "name": file.get("name"),
            "web_view_link": file.get("webViewLink"),
        }
    except Exception as e:
        raise GoogleDriveError(f"Failed to upload file: {str(e)}")


def upload_balance_sheet(
    pdf_content: bytes,
    company_name: str,
    month: str,
    folder_id: Optional[str] = None,
) -> dict:
    """Upload a balance sheet PDF to Google Drive with standardized naming.

    Args:
        pdf_content: PDF file content as bytes
        company_name: Name of the company
        month: Month in YYYY-MM format
        folder_id: Optional Google Drive folder ID

    Returns:
        Dict with file id, name, and webViewLink
    """
    # Format month for filename
    try:
        date = datetime.strptime(month, "%Y-%m")
        formatted_month = date.strftime("%B %Y")
    except ValueError:
        formatted_month = month

    # Clean company name for filename
    clean_name = "".join(
        c for c in company_name if c.isalnum() or c in (' ', '-', '_')
    ).strip()

    filename = f"{clean_name} - Balance Sheet - {formatted_month}.pdf"

    return upload_file(
        file_content=pdf_content,
        filename=filename,
        mime_type="application/pdf",
        folder_id=folder_id,
    )


def get_user_info() -> dict | None:
    """Get authenticated user's information.

    Returns:
        Dict with user email and name, or None if not authenticated
    """
    creds = get_stored_credentials()
    if not creds:
        return None

    try:
        service = build("oauth2", "v2", credentials=creds)
        user_info = service.userinfo().get().execute()
        return {
            "email": user_info.get("email"),
            "name": user_info.get("name"),
        }
    except Exception:
        return None


def list_folders(page_size: int = 20) -> list[dict]:
    """List folders in user's Google Drive.

    Args:
        page_size: Number of folders to return

    Returns:
        List of folder dicts with id and name
    """
    creds = get_stored_credentials()
    if not creds:
        return []

    try:
        service = build("drive", "v3", credentials=creds)

        results = service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and trashed=false",
            pageSize=page_size,
            fields="files(id, name)",
            orderBy="name",
        ).execute()

        folders = results.get("files", [])
        return [{"id": f["id"], "name": f["name"]} for f in folders]
    except Exception:
        return []
