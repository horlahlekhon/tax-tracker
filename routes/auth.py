"""Authentication routes for TIN-based company login."""

import datetime
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from models import Company
from utils.storage import get_companies, get_company_by_tin, create_company

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

# Cookie name for storing the authenticated company ID
AUTH_COOKIE_NAME = "company_id"


def get_current_company(request: Request) -> Optional[Company]:
    """Get the currently authenticated company from the session cookie."""
    company_id = request.cookies.get(AUTH_COOKIE_NAME)
    if not company_id:
        return None

    from utils.storage import get_company
    return get_company(company_id)


@router.get("/signin", response_class=HTMLResponse)
async def signin_page(request: Request, error: Optional[str] = None):
    """Render the sign-in page."""
    # If already logged in, redirect to dashboard
    if get_current_company(request):
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse(
        "signin.html",
        {
            "request": request,
            "error": error,
            "tin": "",
            "year": datetime.datetime.now().year,
        },
    )


@router.post("/signin")
async def signin(request: Request, tin: str = Form(...)):
    """Handle sign-in form submission."""
    tin = tin.strip()

    if not tin:
        return templates.TemplateResponse(
            "signin.html",
            {
                "request": request,
                "error": "Please enter a TIN",
                "tin": tin,
                "year": datetime.datetime.now().year,
            },
        )

    # Look up company by TIN
    company = get_company_by_tin(tin)

    if not company:
        return templates.TemplateResponse(
            "signin.html",
            {
                "request": request,
                "error": "No company found with this TIN. Please register first.",
                "tin": tin,
                "year": datetime.datetime.now().year,
            },
        )

    # Create response with redirect
    response = RedirectResponse(url="/", status_code=302)

    # Set the auth cookie (httponly for security)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=company.id,
        httponly=True,
        max_age=60 * 60 * 24 * 30,  # 30 days
        samesite="lax",
    )

    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: Optional[str] = None):
    """Render the company registration page."""
    # If already logged in, redirect to dashboard
    if get_current_company(request):
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "error": error,
            "year": datetime.datetime.now().year,
        },
    )


@router.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    tin: str = Form(...),
    registration_date: str = Form(...),
):
    """Handle company registration form submission."""
    name = name.strip()
    tin = tin.strip()

    # Validate inputs
    if not name:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Company name is required",
                "year": datetime.datetime.now().year,
            },
        )

    if not tin:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "TIN is required",
                "year": datetime.datetime.now().year,
            },
        )

    # Check if TIN already exists
    existing = get_company_by_tin(tin)
    if existing:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "A company with this TIN already exists. Please sign in instead.",
                "year": datetime.datetime.now().year,
            },
        )

    # Parse registration date
    try:
        reg_date = datetime.datetime.strptime(registration_date, "%Y-%m-%d").date()
    except ValueError:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Invalid registration date",
                "year": datetime.datetime.now().year,
            },
        )

    # Create the company
    company = Company(
        name=name,
        tin=tin,
        registration_date=reg_date,
    )
    created_company = create_company(company)

    # Create response with redirect and set auth cookie
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=created_company.id,
        httponly=True,
        max_age=60 * 60 * 24 * 30,  # 30 days
        samesite="lax",
    )

    return response


@router.get("/signout")
async def signout():
    """Sign out the current user."""
    response = RedirectResponse(url="/auth/signin", status_code=302)
    response.delete_cookie(key=AUTH_COOKIE_NAME)
    return response
