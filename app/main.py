from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal, Optional
import os
import json
from dotenv import load_dotenv
import logging
from datetime import datetime, timezone

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("birtax")

app = FastAPI(title="BIR Tax Calculator", version="0.1.0")

# Rate Limiter Implementation (100 calls/month)
class RateLimiter:
    def __init__(self):
        self.usage = {}  # {user_key: {month_key: count}}
        self.last_reset = {}  # {user_key: month_key}
    
    def get_current_month_key(self) -> str:
        now = datetime.now(timezone.utc)
        return f"{now.year}-{now.month:02d}"
    
    def check_and_increment(self, user_key: str) -> bool:
        month_key = self.get_current_month_key()
        
        if user_key not in self.usage:
            self.usage[user_key] = {}
            self.last_reset[user_key] = month_key
        
        if self.last_reset[user_key] != month_key:
            # New month, reset counter
            self.usage[user_key] = {}
            self.last_reset[user_key] = month_key
        
        current = self.usage[user_key].get(month_key, 0)
        if current >= 100:
            return False
        
        self.usage[user_key][month_key] = current + 1
        return True
    
    def get_remaining(self, user_key: str) -> int:
        month_key = self.get_current_month_key()
        count = self.usage.get(user_key, {}).get(month_key, 0)
        return max(0, 100 - count)

rate_limiter = RateLimiter()

# Rate limiting middleware to add headers
@app.middleware("http")
async def add_rate_limit_headers(request: Request, call_next):
    response = await call_next(request)
    if hasattr(request.state, "rate_limit_remaining"):
        remaining = request.state.rate_limit_remaining
        response.headers["X-RateLimit-Limit"] = "100"
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response

# Rate limiting dependency
async def rate_limit_dependency(request: Request):
    user_email = request.headers.get("X-User-Email")
    api_key = request.headers.get("X-API-Key")
    
    if user_email:
        user_key = f"email:{user_email}"
    elif api_key:
        user_key = f"apikey:{api_key}"
    else:
        client = request.client
        host = client.host if client else "unknown"
        user_key = f"ip:{host}"
    
    if not rate_limiter.check_and_increment(user_key):
        remaining = rate_limiter.get_remaining(user_key)
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Free tier limit of 100 API calls per month exceeded. Please upgrade for higher limits.",
                "limit": 100,
                "remaining": remaining,
                "upgrade_info": "Contact administrator for paid plans."
            }
        )
    
    request.state.rate_limit_remaining = rate_limiter.get_remaining(user_key)
    return user_key

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
def estimate(req: TaxRequest, user_key: str = Depends(rate_limit_dependency)):
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
