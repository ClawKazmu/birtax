# BIR Tax Calculator (2024 TRAIN)

Estimates Philippine income tax dues for employees, self-employed professionals, and corporations based on the 2024 TRAIN law (Tax Reform for Acceleration and Inclusion). This is an educational tool to help understand tax liabilities.

## Features
- **Employee compensation tax** with mandatory deductions (SSS, PhilHealth, Pag-IBIG) and optional personal exemption simulation.
- **Self-employed / Professionals**: choose between graduated rates (with deductions) or the 8% flat tax on gross receipts (exceeding PHP 250,000).
- **Corporations**: flat 30% tax on taxable income (after deductions).
- Simple HTML/JS frontend with a responsive form.
- REST API (`/api/estimate`) for integration.

## Tax Brackets (2024 TRAIN - Individual)

| Annual Taxable Income (PHP) | Rate | Computation |
|----------------------------|------|-------------|
| Not over 250,000 | 0% | Exempt |
| Over 250,000 up to 400,000 | 15% | 15% on excess over 250,000 |
| Over 400,000 up to 800,000 | 20% | 22,500 + 20% on excess over 400,000 |
| Over 800,000 up to 2,000,000 | 25% | 102,500 + 25% on excess over 800,000 |
| Over 2,000,000 up to 8,000,000 | 30% | 402,500 + 30% on excess over 2,000,000 |
| Over 8,000,000 | 35% | 2,202,500 + 35% on excess over 8,000,000 |

**Note**: The basic personal exemption of PHP 250,000 is already built into the brackets. Additional personal exemptions can be simulated (e.g., for dependents).
For self-employed using the 8% flat tax: tax = 8% on the portion of gross receipts exceeding PHP 250,000 (no deductions allowed).

## Quickstart

```bash
# Clone the repo (if on GitHub) or navigate to the project folder
cd business/projects/birtax

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload
```

Open your browser:
- **Frontend**: http://localhost:8000/
- **API docs (Swagger)**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health

## API Usage

### POST /api/estimate

Compute tax based on input parameters.

**Request body (JSON)**

```json
{
  "taxpayer_type": "employee" | "self-employed" | "corporation",
  "gross_annual_income": 600000,
  "deductions": 0,
  "use_flat_tax": false,
  "sss": 0,
  "philhealth": 0,
  "pagibig": 0,
  "personal_exemption": 0,
  "number_of_dependents": 0
}
```

**Field descriptions**:

- `taxpayer_type`: Type of taxpayer.
- `gross_annual_income`: Total annual gross income before any deductions (PHP).
- `deductions`: Other deductions (e.g., business expenses for self-employed, additional employee deductions).
- `use_flat_tax`: Only for `self-employed`. If `true`, applies 8% flat tax on gross receipts exceeding 250,000 (ignores all deduction fields).
- `sss`: Annual SSS contributions (employee only).
- `philhealth`: Annual PhilHealth premiums (employee only).
- `pagibig`: Annual Pag-IBIG contributions (employee only).
- `personal_exemption`: Additional personal exemption amount for simulation (PHP). Added to the basic 250k exemption.
- `number_of_dependents`: Number of dependents; each adds PHP 50,000 to exemption (simulation).

**Response**

```json
{
  "annual_tax_due": 12500.00,
  "monthly_tax": 1041.67,
  "taxable_income": 550000.00,
  "tax_rate_applied": "Graduated rates (TRAIN)",
  "notes": "Detailed breakdown..."
}
```

## Examples

### Example 1: Employee with no deductions, PHP 600,000 gross

```json
{
  "taxpayer_type": "employee",
  "gross_annual_income": 600000
}
```

Tax calculation:
- Taxable = 600,000 - 250,000 = 350,000
- Tax = (150,000 × 15%) + (100,000 × 20%)? Actually progressive: first 250k=0, next 150k (250-400) = 150k*15% = 22,500, next 0? Wait, 350k is within second bracket (250-400). So tax = 150,000 * 0.15 = 22,500.
- Annual tax = 22,500; Monthly = 1,875.

Result: `annual_tax_due: 22500.00`

### Example 2: Self-employed with business expenses, PHP 1,000,000 gross, using graduated rates

```json
{
  "taxpayer_type": "self-employed",
  "gross_annual_income": 1000000,
  "deductions": 300000,
  "use_flat_tax": false
}
```

Taxable = 1,000,000 - 300,000 = 700,000.
- 250k at 0% = 0
- 150k (250-400) @15% = 22,500
- 300k (400-700) @20% = 60,000 (but careful: the portion from 400 to 700 is 300k? Actually 700k - 400k = 300k, yes)
Total = 82,500.

Annual tax = 82,500.

### Example 3: Self-employed with 8% flat tax, PHP 800,000 gross

```json
{
  "taxpayer_type": "self-employed",
  "gross_annual_income": 800000,
  "use_flat_tax": true
}
```

Taxable base = 800,000 - 250,000 = 550,000.
Tax = 550,000 × 0.08 = 44,000.

### Example 4: Employee with SSS, PhilHealth, Pag-IBIG, PHP 600,000 gross

Approximate contributions (annual):
- SSS: ~ 4,000 (monthly ~ 333)
- PhilHealth: ~ 4,500 (monthly ~ 375)
- Pag-IBIG: ~ 2,400 (monthly ~ 200)
Total = 10,900.

```json
{
  "taxpayer_type": "employee",
  "gross_annual_income": 600000,
  "sss": 4000,
  "philhealth": 4500,
  "pagibig": 2400
}
```

Taxable = 600,000 - 10,900 - 250,000 = 339,100.
Tax ≈ (339,100 - 250,000) * 0.15 = 89,100 * 0.15 = 13,365 (since still within second bracket).

Annual tax ~ 13,365.

## Limitations & Caveats

- **Estimates only**: This tool does not constitute official tax advice. Consult a BIR-accredited tax consultant or the BIR directly for filing.
- **Tax law updates**: Tax rates and thresholds may change. Verify against the latest BIR circulars and the TRAIN law.
- **Deductions**: The list of allowed deductions is simplified. Actual allowable deductions may vary (e.g., health insurance, life insurance, etc.). For self-employed, business expenses must be ordinary and necessary.
- **Personal exemptions**: The TRAIN law eliminated most personal exemptions. The only basic exemption is PHP 250,000. The `personal_exemption` and `number_of_dependents` fields are simulation only and not recognized by BIR for tax filings (as of 2024).
- **Corporations**: Corporate tax rate is simplified at 30%. Various incentives (e.g., PEZA, CREATE Act reduced rates for domestic corporations, minimum corporate income tax) are not implemented.
- **Withholding**: For employees, actual withholding by employer may differ due to payroll timing, other benefits, etc.
- **No tax credits**: This calculator does not account for tax credits, carry-over losses, or other offsets.
- **Currency**: All amounts are in Philippine Pesos (PHP).

## Tech Stack
- **Backend**: FastAPI (Python 3.10+)
- **Frontend**: HTML5 + Vanilla JavaScript (no build step)
- **Validation**: Pydantic models
- **Packaging**: `requirements.txt`

## Development

Run in development mode with auto-reload:

```bash
uvicorn app.main:app --reload
```

Validate Python syntax:

```bash
python -m py_compile app/main.py
```

Test API directly via Swagger UI at `/docs`.

## Future Enhancements
- Support for mixed compensation (multiple employers).
- Tax credit simulation.
- More detailed deduction categories.
- Local government unit (LGU) business tax estimates.
- Saved scenarios and PDF reports.

## Rate Limiting

- Free tier: **100 API calls per month** per user.
- Users are identified via HTTP headers:
  - `X-User-Email`: Your email address (preferred)
  - `X-API-Key`: Your API key
  - If neither is provided, the requester's IP address is used.
- Rate limited responses return **HTTP 429** with a JSON body containing `error`, `message`, `limit`, `remaining`, and `upgrade_info`.
- Response headers `X-RateLimit-Limit` and `X-RateLimit-Remaining` indicate your current quota status.
- To upgrade or increase limits, contact the administrator.

## License
MIT (or specify your license)

