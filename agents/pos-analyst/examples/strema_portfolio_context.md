# Context

You are analyzing a synthetic Saudi restaurant and cafe merchant portfolio for underwriting, liquidity monitoring, and operational-risk analysis.

This is not one brand and not one branch network. The unit of analysis is primarily `merchant_id`, with city and merchant archetype differences likely to matter.

The uploaded files are expected to represent this schema:

- `merchants.csv`: merchant master data
- `sales_daily.csv`: daily gross sales, discounts, refunds, net sales, VAT, order count, average ticket
- `payments_daily.csv`: daily customer collections split by cash, card, wallet
- `bank_daily.csv`: daily opening balance, inflows, outflows, closing balance
- `obligations.csv`: rent, payroll, supplier, tax, and loan obligations with amount due and paid

The data is synthetic but was intentionally generated from a causal simulation with calendar effects, merchant scenarios, payment-settlement lag, cash deposits, refunds, and obligations stress. Treat it as analytically coherent unless the data itself proves otherwise.

# What I need from you

Answer these questions directly:

1. Which merchant segments look healthiest, and why?
2. Which merchant segments look riskiest from a liquidity and repayment perspective, and why?
3. What are the strongest early-warning indicators of merchant stress in this dataset?
4. Which metrics best separate stable merchants from stressed merchants?
5. How do city and merchant-type differences affect risk and performance?
6. Are there signs of settlement mismatch, weak cash conversion, refund pressure, or obligation undercoverage?
7. If you were building a lender or BNPL risk policy on top of this data, which metrics would you prioritize first?

# Constraints

- Focus on merchant-level and cohort-level insights, not branch-level commentary.
- If menu or item-level analysis is not possible from these files, say that explicitly and move on.
- Quantify every major claim.
- Distinguish clearly between operating performance, collection behavior, and bank liquidity.
- Prioritize insights that would be useful for credit underwriting, fraud/risk triage, and portfolio monitoring.
