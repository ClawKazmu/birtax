# BIR Tax Calculator

Estimates Philippine tax dues for employees, freelancers, and businesses based on BIR rules (TRAIN, CREATE).

## MVP Scope
- Employee withholding tax computation
- Self‑employed: 8% flat vs graduated rates toggle
- Output: annual tax, monthly remittance, due forms

## Tech
- FastAPI backend
- Plain HTML/JS frontend or Next.js (future)
- Tax tables in JSON (`bir_tables.json`)

## Quickstart
```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs to test.

## API
- `GET /` – health
- `POST /api/estimate` – compute tax

Request:
```json
{
  "taxpayer_type": "employee" | "self-employed",
  "gross_annual_income": 600000,
  "deductions": 0,
  "use_flat_tax": true/false (only for self-employed)
}
```

Response:
```json
{
  "annual_tax_due": 0,
  "monthly_tax": 0,
  "taxable_income": 0,
  "notes": "Below exemption threshold."
}
```

## Caveats
- Estimator only, not official tax advice.
- Must update tables when BIR issues new circulars.

## Project status
Scaffold created. Tax tables TBD.
