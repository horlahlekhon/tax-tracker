from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from models import Company, CompanyCreate, CompanyUpdate
from utils.storage import (
    get_companies,
    get_company,
    create_company,
    update_company,
    delete_company,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/", response_model=list[Company])
async def list_companies():
    """Get all companies."""
    return get_companies()


@router.post("/", response_model=Company)
async def create_new_company(company_data: CompanyCreate):
    """Create a new company."""
    company = Company(
        name=company_data.name,
        tin=company_data.tin,
        registration_date=company_data.registration_date,
    )
    return create_company(company)


@router.get("/manage", response_class=HTMLResponse)
async def manage_companies_page(request: Request):
    """Render the company management page."""
    companies = get_companies()
    return templates.TemplateResponse(
        "companies.html",
        {
            "request": request,
            "companies": companies,
            "company": None,
        },
    )


@router.get("/{company_id}", response_model=Company)
async def get_company_by_id(company_id: str):
    """Get a company by ID."""
    company = get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/{company_id}", response_model=Company)
async def update_company_by_id(company_id: str, company_data: CompanyUpdate):
    """Update a company by ID."""
    updates = company_data.model_dump(exclude_unset=True)
    company = update_company(company_id, updates)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.delete("/{company_id}")
async def delete_company_by_id(company_id: str):
    """Delete a company by ID."""
    if not delete_company(company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    return {"message": "Company deleted successfully"}
