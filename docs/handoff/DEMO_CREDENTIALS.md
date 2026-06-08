# Demo Credentials

Three pre-seeded golden merchants with real pipeline-produced decisions.
Use these to demo LeaseFlow without waiting on the live pipeline.

All passwords: `demo123!`  (same for each)

| # | Persona | Email | Outcome | Amount | Monthly |
|---|---|---|---|---|---|
| qahwa | Qahwa Haneen Specialty Coffee | `ghazal.abdulrazzak@gmail.com` | **approved** | SAR 50,000 | SAR 4,792 |
| awful | Awful Coffee Corner | `gzrazak@gmail.com` | **denied** | — | — |
| iffy | Iffy Burger | `a-madoun@hotmail.com` | **manual_review** | — | — |

## Details

### Qahwa Haneen Specialty Coffee
- login: `ghazal.abdulrazzak@gmail.com` / `demo123!`
- CR: `1010000000`
- merchant_id: `6dae66f7-212a-4d8a-a903-fe14f4f94c14`
- loan_id: `13535ea2-47a2-46ba-90d7-b78377e73cf5`
- expected → actual: `approved` → `approved`

### Awful Coffee Corner
- login: `gzrazak@gmail.com` / `demo123!`
- CR: `1010000085`
- merchant_id: `9cb4e1e8-049b-46e5-a624-ccc61a188d59`
- loan_id: `db71e453-d67b-4baf-9544-1fc0f74d883b`
- expected → actual: `denied` → `denied`

### Iffy Burger
- login: `a-madoun@hotmail.com` / `demo123!`
- CR: `1010000010`
- merchant_id: `110d6922-dd31-4d38-8cbc-ae4727b41a9b`
- loan_id: `490e4f40-5446-48c4-b8a5-f4c36d655c03`
- expected → actual: `manual_review` → `manual_review`
