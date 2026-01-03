"""PDF Converter Routes.

Handles PDF bank statement to CSV conversion.
"""

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from utils.pdf_statement_parser import parse_and_convert, SupportedBank

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter()

# List of supported banks for UI
SUPPORTED_BANKS = [
    {"value": SupportedBank.ZENITH.value, "label": "Zenith Bank"},
    {"value": SupportedBank.GTBANK.value, "label": "GTBank"},
    {"value": SupportedBank.KUDA.value, "label": "Kuda Bank"},
]


@router.get("/", response_class=HTMLResponse)
async def pdf_converter_page(request: Request):
    """Render the PDF converter page."""
    return templates.TemplateResponse(
        "pdf_converter.html",
        {
            "request": request,
            "supported_banks": SUPPORTED_BANKS,
        },
    )


@router.post("/convert")
async def convert_pdf_to_csv(
    file: UploadFile = File(...),
    bank: str = Form(default="zenith"),
    password: Optional[str] = Form(default=None),
) -> Response:
    """Convert uploaded PDF bank statement to CSV.

    Args:
        file: Uploaded PDF file
        bank: Bank type (zenith or gtbank)
        password: Optional password for encrypted PDFs

    Returns:
        CSV file as downloadable response
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="File must be a PDF"
        )

    # Validate bank type
    try:
        bank_enum = SupportedBank(bank.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported bank: {bank}. Supported banks: {', '.join([b.value for b in SupportedBank])}"
        )

    try:
        # Read file content
        content = await file.read()

        if len(content) == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty"
            )

        # Clean up password (empty string should be None)
        pdf_password = password if password and password.strip() else None

        # Parse and convert
        csv_content = parse_and_convert(content, bank_enum, pdf_password)

        # Generate output filename
        original_name = file.filename.rsplit('.', 1)[0]
        output_filename = f"{original_name}_transactions.csv"

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{output_filename}"',
            },
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        error_msg = str(e)
        # Provide clearer error for password-protected PDFs
        if "password" in error_msg.lower() or "encrypted" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="This PDF is password-protected. Please enter the correct password."
            )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process PDF: {error_msg}"
        )
