# StreamFlow Demo - Open Product Questions

Date: 2026-04-15
Scope: Frontend-only hackathon demo (no backend, simulated integrations)

## Unresolved Decisions

1. Hybrid repayment formula
- Exact split between fixed monthly amount and sales-based daily stream is not finalized.
- Need a default recommended formula for onboarding (e.g., 60% monthly fixed + 40% sales stream).

2. Stream service mapping
- Confirm exact Stream APIs to represent:
  - daily sales-based collection
  - monthly fixed plan collection
- Need fallback behavior in demo if one rail fails.

3. Investor return model
- Return type is not finalized:
  - fixed interest
  - variable profit share
  - non-financial reward model
- Demo currently uses simulated fixed annual return for visualization only.

4. Investor disclosure content
- Risk disclosures and investor warnings are not finalized.
- Need agreed language for:
  - default risk
  - liquidity/lockup assumptions
  - delayed repayments and loss scenarios

5. Collections policy for weak sales months
- Current direction: collect remaining amount at month-end.
- Still need detailed policy:
  - grace period
  - retries
  - partial collection handling

6. Partial approval governance
- AI-driven offer amount is accepted as direction, but policy limits are not finalized:
  - minimum/maximum financed amount
  - sector caps
  - exposure per merchant

## Confirmed Demo Assumptions (From Team Input)

- AI model determines eligible approved amount from financial docs.
- Counter-offer UI is required (requested vs approved).
- Merchant can pay the uncovered difference now; approved amount follows financing flow.
- Merchant can choose repayment mode: sales-based, fixed monthly, or hybrid.
- If sales are weak, remaining due is collected at end of month.
- Investor funding feature is demo-only and simulated.
- All three features are in scope for demo.

## Implementation Notes

- This demo intentionally uses mocked data and simulated status updates.
- No real money movement, KYC, lending, or securities operations are performed.
