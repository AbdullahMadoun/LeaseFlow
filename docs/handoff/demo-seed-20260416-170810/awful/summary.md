# Awful Coffee Corner

- login: `gzrazak@gmail.com` / `demo123!`
- CR: `1010000085`
- merchant_id: `9cb4e1e8-049b-46e5-a624-ccc61a188d59`
- loan_id: `db71e453-d67b-4baf-9544-1fc0f74d883b`

## Decision

- status: **denied**
- synthesis_status: `done`
- approved_amount: None
- monthly_payment: None
- override_applied: `hard_floor`
- generated_at: 2026-04-16T14:26:24.672389+00:00

### Deterministic proposal
- overall_score: 35.8
- risk_level: `high`
- rules_fired: ['overall_score<=40', 'dscr_tight', 'simah_defaults_present']
- per_dim: `{'pos': 65.0, 'simah': 25.0, 'industry': 53.0, 'financial_docs': 10.0}`

### Hard floors
- passed: **False**
- violations: `['dscr_below_1.0(0.08)', 'simah_defaults>0(1)']`

## Dimensions

| dim | status | score | conf | narrative |
|---|---|---|---|---|
| pos | done | 65.0 | 0.85 | The merchant has submitted 1 POS report and 1 source document; no revenue, avera |
| financial_docs | done | 10.0 | 0.75 | Merchant shows net loss SAR 28,943 (‑10.8 % net margin), average monthly net cas |
| simah | done | 25.0 | 0.95 | SIMAH score 470, 1 default(s), payment history poor. |
| sentiment | error | None | None |  |
| industry | done | 53.0 | 0.6 | Jeddah's high-competition specialty coffee market benefits from 10% growth, yet  |

## Documents (Supabase Storage)

- `bank_statement` → `9cb4e1e8-049b-46e5-a624-ccc61a188d59/db71e453-d67b-4baf-9544-1fc0f74d883b/bank_statement/3ba188aed1a6.pdf`  (done)
- `pos_data` → `9cb4e1e8-049b-46e5-a624-ccc61a188d59/db71e453-d67b-4baf-9544-1fc0f74d883b/pos_data/f9a4ef01aa0d.csv`  (done)
- `financial_statement` → `9cb4e1e8-049b-46e5-a624-ccc61a188d59/db71e453-d67b-4baf-9544-1fc0f74d883b/financial_statement/ef7c9d9c0d21.pdf`  (done)
- `invoice` → `9cb4e1e8-049b-46e5-a624-ccc61a188d59/db71e453-d67b-4baf-9544-1fc0f74d883b/invoice/f7f2a0a97cfc.pdf`  (done)

## Installments

| # | due | amount | status | pay_now_url | paid_at |
|---|---|---|---|---|---|

## Stream subscription

- _no Stream subscription (approval did not occur or Stream call failed)_
