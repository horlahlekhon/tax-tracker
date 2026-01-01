"""Google Drive Integration Routes.

Handles OAuth flow and file uploads to Google Drive.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from utils.gdrive import (
    is_configured,
    is_authenticated,
    get_authorization_url,
    exchange_code_for_credentials,
    revoke_credentials,
    upload_balance_sheet,
    get_user_info,
    list_folders,
    GoogleDriveError,
)
from utils.storage import get_company, get_transactions, get_transactions_ytd, get_checklist
from utils.tax_calculator import calculate_tax_summary
from utils.pdf_generator import generate_balance_sheet_pdf

router = APIRouter()


class GDriveStatusResponse(BaseModel):
    """Response model for Google Drive status."""
    configured: bool
    authenticated: bool
    user_email: Optional[str] = None
    user_name: Optional[str] = None


class GDriveAuthUrlResponse(BaseModel):
    """Response model for authorization URL."""
    authorization_url: str
    state: str


class GDriveUploadResponse(BaseModel):
    """Response model for file upload."""
    success: bool
    file_id: Optional[str] = None
    file_name: Optional[str] = None
    web_view_link: Optional[str] = None
    error: Optional[str] = None


class GDriveFolderResponse(BaseModel):
    """Response model for folder list."""
    folders: list[dict]


@router.get("/status")
async def get_gdrive_status() -> GDriveStatusResponse:
    """Get Google Drive integration status."""
    configured = is_configured()
    authenticated = is_authenticated()

    user_email = None
    user_name = None

    if authenticated:
        user_info = get_user_info()
        if user_info:
            user_email = user_info.get("email")
            user_name = user_info.get("name")

    return GDriveStatusResponse(
        configured=configured,
        authenticated=authenticated,
        user_email=user_email,
        user_name=user_name,
    )


@router.get("/auth/url")
async def get_auth_url(
    state: Optional[str] = None,
) -> GDriveAuthUrlResponse:
    """Get OAuth authorization URL.

    Args:
        state: Optional state parameter for CSRF protection
    """
    try:
        auth_url, state = get_authorization_url(state)
        return GDriveAuthUrlResponse(
            authorization_url=auth_url,
            state=state,
        )
    except GoogleDriveError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback")
async def oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """Handle OAuth callback from Google.

    Redirects to dashboard with success or error message.
    """
    if error:
        # User denied access or other error
        return RedirectResponse(
            url=f"/?gdrive_error={error}",
            status_code=302,
        )

    if not code:
        return RedirectResponse(
            url="/?gdrive_error=no_code",
            status_code=302,
        )

    try:
        exchange_code_for_credentials(code)
        return RedirectResponse(
            url="/?gdrive_success=connected",
            status_code=302,
        )
    except GoogleDriveError as e:
        return RedirectResponse(
            url=f"/?gdrive_error={str(e)}",
            status_code=302,
        )


@router.post("/disconnect")
async def disconnect_gdrive() -> dict:
    """Disconnect Google Drive integration."""
    success = revoke_credentials()
    return {"success": success}


@router.get("/folders")
async def get_folders() -> GDriveFolderResponse:
    """Get list of folders in user's Google Drive."""
    if not is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Google Drive")

    folders = list_folders()
    return GDriveFolderResponse(folders=folders)


@router.post("/upload/balance-sheet")
async def upload_balance_sheet_to_drive(
    company_id: str,
    month: Optional[str] = None,
    folder_id: Optional[str] = None,
) -> GDriveUploadResponse:
    """Generate and upload balance sheet PDF to Google Drive.

    Args:
        company_id: The company ID
        month: Month in YYYY-MM format (defaults to current month)
        folder_id: Optional Google Drive folder ID

    Returns:
        Upload result with file link
    """
    if not is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Google Drive. Please connect first.",
        )

    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not month:
        month = datetime.now().strftime("%Y-%m")

    try:
        # Get transactions for the month
        transactions = get_transactions(company_id=company_id, month=month)

        # Get YTD revenue for threshold calculations
        year = int(month.split("-")[0])
        ytd_txns = get_transactions_ytd(company_id, year)
        ytd_summary = calculate_tax_summary(ytd_txns, period_type="ytd")
        annual_revenue = ytd_summary.total_revenue

        # Calculate tax summary for the month
        summary = calculate_tax_summary(
            transactions,
            period_type="month",
            annual_revenue_override=annual_revenue,
        )

        # Get filing checklist
        checklist = get_checklist(company_id, month)

        # Generate PDF
        pdf_bytes = generate_balance_sheet_pdf(
            company=company,
            month=month,
            summary=summary,
            checklist=checklist,
        )

        # Upload to Google Drive
        result = upload_balance_sheet(
            pdf_content=pdf_bytes,
            company_name=company.name,
            month=month,
            folder_id=folder_id,
        )

        return GDriveUploadResponse(
            success=True,
            file_id=result["id"],
            file_name=result["name"],
            web_view_link=result["web_view_link"],
        )

    except GoogleDriveError as e:
        return GDriveUploadResponse(
            success=False,
            error=str(e),
        )
    except Exception as e:
        return GDriveUploadResponse(
            success=False,
            error=f"Failed to upload: {str(e)}",
        )
