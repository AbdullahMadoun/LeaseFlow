# Iffy Burger

- login: `a-madoun@hotmail.com` / `demo123!`
- CR: `1010000010`
- merchant_id: `110d6922-dd31-4d38-8cbc-ae4727b41a9b`
- loan_id: `490e4f40-5446-48c4-b8a5-f4c36d655c03`

## Decision

- status: **manual_review**
- synthesis_status: `done`
- approved_amount: None
- monthly_payment: None
- override_applied: `agreement`
- generated_at: 2026-04-16T14:29:20.226392+00:00

### Deterministic proposal
- overall_score: 64.7
- risk_level: `medium`
- rules_fired: ['overall_score_in_review_band', 'dscr_comfortable']
- per_dim: `{'pos': 65.0, 'simah': 50.0, 'industry': 63.0, 'financial_docs': 75.0}`

### Hard floors
- passed: **True**
- violations: `[]`

### LLM response
- decision: manual_review  confidence: 0.58
- reasoning: Iffy Burger presents a medium-risk profile with solid financial metrics (DSR 1.99, 10% net margin) that comfortably support the lease payment, but multiple flags warrant deeper scrutiny: SIMAH recommendation is 'caution' with 4 recent inquiries and 1 bounced payment, POS data is limited to a single report preventing operational validation, and the sentiment dimension errored leaving a data gap. The conservative market appetite and rising input costs in the QSR segment further support a cautious amount rather than the full SAR 60,000 request. Manual review should verify the recent credit activity and request additional POS documentation to confirm operational consistency with financials.

## Dimensions

| dim | status | score | conf | narrative |
|---|---|---|---|---|
| pos | done | 65.0 | 0.85 | Only 1 POS report with 1 source document; revenue, average ticket, void and refu |
| financial_docs | done | 75.0 | 0.85 | Merchant shows stable revenue (SAR 57,642/month), net profit SAR 11,466/month, 1 |
| simah | done | 50.0 | 0.95 | SIMAH score 639, 0 default(s), payment history fair. |
| sentiment | error | None | None |  |
| industry | done | 63.0 | 0.6 | In Dammam's quick-service restaurant sector, medium competition coexists with 9% |

## Documents (Supabase Storage)

- `bank_statement` → `110d6922-dd31-4d38-8cbc-ae4727b41a9b/490e4f40-5446-48c4-b8a5-f4c36d655c03/bank_statement/4f775aeb185d.pdf`  (done)
- `pos_data` → `110d6922-dd31-4d38-8cbc-ae4727b41a9b/490e4f40-5446-48c4-b8a5-f4c36d655c03/pos_data/48f19c98e2d9.csv`  (done)
- `financial_statement` → `110d6922-dd31-4d38-8cbc-ae4727b41a9b/490e4f40-5446-48c4-b8a5-f4c36d655c03/financial_statement/7aa82750c37d.pdf`  (done)
- `invoice` → `110d6922-dd31-4d38-8cbc-ae4727b41a9b/490e4f40-5446-48c4-b8a5-f4c36d655c03/invoice/34c736840e3f.pdf`  (done)

## Installments

| # | due | amount | status | pay_now_url | paid_at |
|---|---|---|---|---|---|

## Stream subscription

- _no Stream subscription (approval did not occur or Stream call failed)_
