# Qahwa Haneen Specialty Coffee

- login: `ghazal.abdulrazzak@gmail.com` / `demo123!`
- CR: `1010000000`
- merchant_id: `6dae66f7-212a-4d8a-a903-fe14f4f94c14`
- loan_id: `13535ea2-47a2-46ba-90d7-b78377e73cf5`

## Decision

- status: **approved**
- synthesis_status: `done`
- approved_amount: 50000.0
- monthly_payment: 4791.67
- override_applied: `agreement`
- generated_at: 2026-04-16T14:21:23.664856+00:00

### Deterministic proposal
- overall_score: 76.3
- risk_level: `low`
- rules_fired: ['overall_score>=70', 'dscr_comfortable']
- per_dim: `{'pos': 70.0, 'simah': 85.0, 'industry': 68.0, 'financial_docs': 80.0}`

### Hard floors
- passed: **True**
- violations: `[]`

### LLM response
- decision: approve  confidence: 0.85
- reasoning: The deterministic proposal scores 76.3 overall with a comfortable DSCR of 6.61, well above risk thresholds, and SIMAH credit (787) shows zero defaults with excellent payment history. Financial docs confirm strong health with 27.5% net margin and current ratio 1.9, supporting the SAR 50,000 lease-to-own on a high-value La Marzocco GB5. The sentiment dimension errored, reducing confidence slightly, but all other dimensions are positive and the conservative market appetite is already factored into the proposal bounds.

## Dimensions

| dim | status | score | conf | narrative |
|---|---|---|---|---|
| pos | done | 70.0 | 0.85 | Daily revenue averages SAR 3,533 with monthly estimate SAR 105,991; average tick |
| financial_docs | done | 80.0 | 0.85 | Merchant generated SAR 1.13 M revenue, SAR 310,833 net profit (27.5% net margin) |
| simah | done | 85.0 | 0.95 | SIMAH score 787, 0 default(s), payment history excellent. |
| sentiment | error | None | None |  |
| industry | done | 68.0 | 0.6 | Riyadh's specialty coffee café sector is booming with 13% annual growth while fa |

## Documents (Supabase Storage)

- `bank_statement` → `6dae66f7-212a-4d8a-a903-fe14f4f94c14/13535ea2-47a2-46ba-90d7-b78377e73cf5/bank_statement/1012ffe31847.pdf`  (done)
- `pos_data` → `6dae66f7-212a-4d8a-a903-fe14f4f94c14/13535ea2-47a2-46ba-90d7-b78377e73cf5/pos_data/09fe026c5bda.csv`  (done)
- `financial_statement` → `6dae66f7-212a-4d8a-a903-fe14f4f94c14/13535ea2-47a2-46ba-90d7-b78377e73cf5/financial_statement/bdaeec4623d3.pdf`  (done)
- `invoice` → `6dae66f7-212a-4d8a-a903-fe14f4f94c14/13535ea2-47a2-46ba-90d7-b78377e73cf5/invoice/645172498984.pdf`  (done)

## Installments

| # | due | amount | status | pay_now_url | paid_at |
|---|---|---|---|---|---|
| 1 | 2026-05-16 | 4791.67 | pending | [link](https://streampay.sa/s/QVRuK) | — |
| 2 | 2026-06-15 | 4791.67 | pending | — | — |
| 3 | 2026-07-15 | 4791.67 | pending | — | — |
| 4 | 2026-08-14 | 4791.67 | pending | — | — |
| 5 | 2026-09-13 | 4791.67 | pending | — | — |
| 6 | 2026-10-13 | 4791.67 | pending | — | — |
| 7 | 2026-11-12 | 4791.67 | pending | — | — |
| 8 | 2026-12-12 | 4791.67 | pending | — | — |
| 9 | 2027-01-11 | 4791.67 | pending | — | — |
| 10 | 2027-02-10 | 4791.67 | pending | — | — |
| 11 | 2027-03-12 | 4791.67 | pending | — | — |
| 12 | 2027-04-11 | 4791.63 | pending | — | — |

## Stream subscription

- id: `e648e166-b1c6-4039-807c-dff75c8b8617`
- status: **INACTIVE**
- current_cycle: 1
- period_end: 2026-05-16T14:21:33Z
- dashboard: https://app.streampay.sa/subscriptions/e648e166-b1c6-4039-807c-dff75c8b8617
