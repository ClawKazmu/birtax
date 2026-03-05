from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
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
# Format: (upper_limit, rate)
# Progressive: each bracket applies only to the portion within its range.
BRACKETS_EMPLOYEE = [
    (250_000, 0.00),    # Up to 250k: exempt
    (400_000, 0.15),    # Over 250k up to 400k: 15%
    (800_000, 0.20),    # Over 400k up to 800k: 20%
    (2_000_000, 0.25),  # Over 800k up to 2M: 25%
    (8_000_000, 0.30),  # Over 2M up to 8M: 30%
    (float('inf'), 0.35) # Over 8M: 35%
]

def compute_graduated_tax(taxable_income: float) -> float:
    """Compute tax using progressive brackets."""
    tax = 0.0
    prev_limit = 0
    for limit, rate in BRACKETS_EMPLOYEE:
        if taxable_income <= prev_limit:
            break
        upper = min(taxable_income, limit)
        amount = upper - prev_limit
        tax += amount * rate
        prev_limit = limit
    return tax

class TaxRequest(BaseModel):
    taxpayer_type: Literal["employee", "self-employed", "corporation"]
    gross_annual_income: float = Field(..., ge=0, description="Total annual gross income before any deductions")
    deductions: float = Field(0, ge=0, description="Other optional deductions (e.g., business expenses for self-employed, additional deductions)")
    use_flat_tax: bool = Field(False, description="For self-employed: True to use 8% flat tax on gross receipts")
    # Optional deduction components for employees:
    sss: float = Field(0, ge=0, description="SSS contributions (annual)")
    philhealth: float = Field(0, ge=0, description="PhilHealth premiums (annual)")
    pagibig: float = Field(0, ge=0, description="Pag-IBIG contributions (annual)")
    personal_exemption: float = Field(0, ge=0, description="Personal exemption amount (simulation). Under TRAIN, the basic exemption is PHP 250,000 already applied. Use this to simulate additional dependents or exemptions.")
    number_of_dependents: int = Field(0, ge=0, description="Number of dependents for personal exemption simulation (if using fixed amount per dependent, e.g., 50,000 per dependent)")

class TaxResponse(BaseModel):
    annual_tax_due: float
    monthly_tax: float
    taxable_income: float
    tax_rate_applied: str
    notes: str = ""

@app.post("/api/estimate", response_model=TaxResponse)
def estimate(req: TaxRequest):
    # Compute total deductions and exemptions
    total_deductions = req.deductions + req.sss + req.philhealth + req.pagibig
    # Personal exemption simulation: basic 250k is already baked into brackets; this adds extra
    dependent_exemption = req.number_of_dependents * 50000  # assumed PH 50k per dependent
    total_exemptions = req.personal_exemption + dependent_exemption

    # For employees and self-employed (graduated), we subtract deductions and exemptions to get taxable
    if req.taxpayer_type == "employee":
        taxable = max(0, req.gross_annual_income - total_deductions - total_exemptions)
        tax = compute_graduated_tax(taxable)
        rate_desc = "Graduated rates (TRAIN)"
        notes = f"Taxable income after deductions: PHP {taxable:,.2f}. Includes personal exemption simulation: PHP {total_exemptions:,.2f}."
    elif req.taxpayer_type == "self-employed":
        if req.use_flat_tax:
            # 8% flat tax on gross receipts exceeding 250,000 (no deductions)
            if req.gross_annual_income > 250_000:
                tax = (req.gross_annual_income - 250_000) * 0.08
            else:
                tax = 0
            taxable = req.gross_annual_income
            rate_desc = "Flat 8% (TRAIN)"
            notes = "Flat tax applied to gross receipts exceeding PHP 250,000."
        else:
            taxable = max(0, req.gross_annual_income - total_deductions - total_exemptions)
            tax = compute_graduated_tax(taxable)
            rate_desc = "Graduated rates (TRAIN)"
            notes = f"Taxable income after deductions: PHP {taxable:,.2f}. Includes personal exemption simulation: PHP {total_exemptions:,.2f}."
    else:  # corporation
        taxable = max(0, req.gross_annual_income - total_deductions)
        tax = taxable * 0.30
        rate_desc = "30% corporate (regular)"
        notes = "Corporate tax rate 30%. Deductions applied (exemptions not typical for corporations)."
        # There are incentives (PEZA, etc.) not implemented.

    monthly = tax / 12
    return TaxResponse(
        annual_tax_due=round(tax, 2),
        monthly_tax=round(monthly, 2),
        taxable_income=round(taxable, 2),
        tax_rate_applied=rate_desc,
        notes=notes + " This is an estimate. Consult a BIR-accredited tax consultant for filing."
    )

@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))

@app.get("/health")
def health():
    return {"status": "ok", "service": "birtax"}
