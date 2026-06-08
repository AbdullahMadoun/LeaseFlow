Yes — for your BNPL-style F&B risk project, I’d cut it down to just the financial tables that show sales, collections, refunds, and bank cash movement.
For underwriting, the strongest externally grounded fields are invoice totals and VAT fields from Saudi invoice requirements plus bank transaction amounts, dates, debit/credit direction, and balances from open-banking style transaction models. [openbankinguk.github](https://openbankinguk.github.io/read-write-api-site3/v3.1.5/resources-and-data-models/aisp/Transactions.html)

## Minimal schema

Use only these 5 tables:

```sql
merchants (
  merchant_id UUID PRIMARY KEY,
  legal_name VARCHAR(150),
  vat_number VARCHAR(30),
  city VARCHAR(80)
);

sales_daily (
  merchant_id UUID,
  sales_date DATE,
  gross_sales DECIMAL(12,2),
  discounts DECIMAL(12,2),
  net_sales DECIMAL(12,2),
  vat_amount DECIMAL(12,2),
  refunds_amount DECIMAL(12,2),
  orders_count INT,
  avg_ticket DECIMAL(12,2),
  PRIMARY KEY (merchant_id, sales_date)
);

payments_daily (
  merchant_id UUID,
  payment_date DATE,
  cash_amount DECIMAL(12,2),
  card_amount DECIMAL(12,2),
  wallet_amount DECIMAL(12,2),
  total_collected DECIMAL(12,2),
  PRIMARY KEY (merchant_id, payment_date)
);

bank_daily (
  merchant_id UUID,
  balance_date DATE,
  opening_balance DECIMAL(14,2),
  inflows DECIMAL(14,2),
  outflows DECIMAL(14,2),
  closing_balance DECIMAL(14,2),
  PRIMARY KEY (merchant_id, balance_date)
);

obligations (
  merchant_id UUID,
  due_date DATE,
  obligation_type VARCHAR(30),   -- rent, payroll, supplier, tax, loan
  amount_due DECIMAL(12,2),
  amount_paid DECIMAL(12,2),
  status VARCHAR(20)
);
```

## Why this is enough

`sales_daily` captures revenue quality, VAT, refunds, order count, and ticket size, which are the main POS-side signals you need for risk. [halsimplify](https://www.halsimplify.com/knowledge-center/vat-invoice-saudi-arabia)
`payments_daily` separates cash from card and wallet collections, which helps you estimate collection quality and channel mix.
`bank_daily` is critical because bank data gives the real cash movement, including credits, debits, and balances, so you can verify whether reported sales are turning into cash. [openbankinguk.github](https://openbankinguk.github.io/read-write-api-site3/v3.1.5/resources-and-data-models/aisp/Transactions.html)
`obligations` lets you compare incoming cash against rent, supplier, payroll, tax, and loan commitments, which is central to repayment analysis.

## Key features

From this simplified model, compute:

- Revenue trend = 30-day sales growth.
- Volatility = standard deviation of daily net sales.
- Refund ratio = refunds_amount / gross_sales.
- Card share = card_amount / total_collected.
- Cash conversion = inflows / net_sales.
- Balance buffer = closing_balance / average daily outflows.
- Obligation coverage = monthly net inflows / monthly obligations due.

For a hackathon, this is usually enough to produce a solid risk score without getting stuck in full POS complexity.
If you want, I can make it even simpler as a single flat CSV schema.
