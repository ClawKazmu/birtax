from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional
import os
import json
from dotenv import load_dotenv
import logging

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("birtax")

app = FastAPI(title="BIR Tax Calculator", version="0.1.0")

# TRAIN 2024 individual income tax brackets (for compensation)
# Brackets: (upper_limit, base_tax, rate)
# upper_limit is inclusive? We'll use (min, max, base, rate) but easier: sequence of thresholds.
BRACKETS = [
    (250_000, 0, 0.00),
    (400_000, 0, 0.20),
    (800_000, 30_000, 0.25),
    (2_000_000, 130_000, 0.30),
    (8_000_000, 490_000, 0.32),
    (float('inf'), 2_410_000, 0.35),
]

def compute_graduated_tax(taxable_income: float) -> float:
    # Find the bracket where income <= upper limit
    for limit, base, rate in BRACKETS:
        if taxable_income <= limit:
            # base tax for previous bracket is the base of this bracket?
            # Actually base is the tax on the lower bound. We need to compute from previous threshold.
            # Simpler: iterate thresholds
            break
    # Alternative: compute by segments
    tax = 0
    prev = 0
    for i, (limit, base, rate) in enumerate(BRACKETS):
        if taxable_income <= prev:
            break
        upper = min(taxable_income, limit)
        amount = upper - prev
        tax += amount * rate
        prev = limit
    return tax

class TaxRequest(BaseModel):
    taxpayer_type: Literal["employee", "self-employed", "corporation"]
    gross_annual_income: float = Field(..., ge=0)
    deductions: float = Field(0, ge=0)  # optional deductions (if any)
    use_flat_tax: bool = False  # only for self-employed
    # other fields: number of dependents not implemented

class TaxResponse(BaseModel):
    annual_tax_due: float
    monthly_tax: float
    taxable_income: float
    tax_rate_applied: str
    notes: str = ""

@app.post("/api/estimate", response_model=TaxResponse)
def estimate(req: TaxRequest):
    # Basic logic:
    if req.taxpayer_type == "employee":
        # Compensation income: taxable = gross - deductions (if allowed, e.g., personal exemption? Not considering)
        taxable = max(0, req.gross_annual_income - req.deductions)
        tax = compute_graduated_tax(taxable)
        rate_desc = "Graduated rates (TRAIN)"
    elif req.taxpayer_type == "self-employed":
        if req.use_flat_tax:
            # 8% of gross receipts (no deductions)
            tax = req.gross_annual_income * 0.08
            rate_desc = "Flat 8% (TRAIN)"
            taxable = req.gross_annual_income
        else:
            taxable = max(0, req.gross_annual_income - req.deductions)
            tax = compute_graduated_tax(taxable)
            rate_desc = "Graduated rates (TRAIN)"
    else:  # corporation
        # Corporate income tax: regular rate 30% (or 20% for domestic? But we'll use 30% as placeholder)
        taxable = max(0, req.gross_annual_income - req.deductions)
        tax = taxable * 0.30
        rate_desc = "30% corporate (regular)"
        # There are incentives (PEZA, etc.) not implemented.

    monthly = tax / 12
    return TaxResponse(
        annual_tax_due=round(tax, 2),
        monthly_tax=round(monthly, 2),
        taxable_income=round(taxable, 2),
        tax_rate_applied=rate_desc,
        notes="This is an estimate. Consult a BIR-accredited tax consultant for filing."
    )

@app.get("/")
def health():
    return {"status": "ok", "service": "birtax"}
