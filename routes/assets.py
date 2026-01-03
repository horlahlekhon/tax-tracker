from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from models import Asset, AssetCreate, AssetUpdate
from routes.auth import get_current_company
from utils.storage import (
    get_assets,
    get_asset,
    create_asset,
    update_asset,
    delete_asset,
    get_total_assets_value,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

# Asset threshold constant
ASSET_THRESHOLD = Decimal("250000000")  # ₦250 million


@router.get("/", response_class=HTMLResponse)
async def assets_page(request: Request):
    """Render the assets management page."""
    # Get authenticated company
    company = get_current_company(request)

    # Get assets for the company
    assets = []
    total_value = Decimal("0")
    threshold_percent = 0

    if company:
        assets = get_assets(company_id=company.id)
        total_value = get_total_assets_value(company.id)
        threshold_percent = int(min((total_value / ASSET_THRESHOLD * 100), 100))

    return templates.TemplateResponse(
        "assets.html",
        {
            "request": request,
            "company": company,
            "assets": assets,
            "total_value": total_value,
            "threshold_percent": threshold_percent,
            "asset_threshold": ASSET_THRESHOLD,
        },
    )


@router.get("/api", response_model=list[Asset])
async def list_assets(company_id: Optional[str] = None):
    """Get assets, optionally filtered by company."""
    return get_assets(company_id=company_id)


@router.post("/api", response_model=Asset)
async def create_new_asset(asset_data: AssetCreate):
    """Create a new asset."""
    asset = Asset(
        company_id=asset_data.company_id,
        name=asset_data.name,
        purchase_date=asset_data.purchase_date,
        purchase_amount=asset_data.purchase_amount,
        description=asset_data.description,
        transaction_id=asset_data.transaction_id,
    )
    return create_asset(asset)


@router.get("/api/{asset_id}", response_model=Asset)
async def get_asset_by_id(asset_id: str):
    """Get an asset by ID."""
    asset = get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.put("/api/{asset_id}", response_model=Asset)
async def update_asset_by_id(asset_id: str, asset_data: AssetUpdate):
    """Update an asset by ID."""
    updates = asset_data.model_dump(exclude_unset=True)
    asset = update_asset(asset_id, updates)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.delete("/api/{asset_id}")
async def delete_asset_by_id(asset_id: str):
    """Delete an asset by ID."""
    if not delete_asset(asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"message": "Asset deleted successfully"}


@router.get("/total-value")
async def get_assets_total_value(request: Request):
    """Get total asset value for the authenticated company."""
    company = get_current_company(request)
    if not company:
        raise HTTPException(status_code=401, detail="Not authenticated")

    total = get_total_assets_value(company.id)
    threshold_percent = int(min((total / ASSET_THRESHOLD * 100), 100))

    return {
        "total_value": float(total),
        "threshold_percent": threshold_percent,
        "exceeds_threshold": total > ASSET_THRESHOLD,
    }
