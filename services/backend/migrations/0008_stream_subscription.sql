-- LeaseFlow 0008: Stream subscription model.
-- Moves from per-installment payment links (0007) to one recurring subscription
-- per approved loan. Old per-installment stream_* columns stay in place as
-- a legacy fallback (used only when a merchant's loan is pre-0008 or when
-- subscription creation fails and we want to fall back to ad-hoc links).
--
-- Stream's model: Consumer (= our merchant) owns Subscriptions; each
-- Subscription references one Product (recurring, price = single installment
-- amount); cycles create Invoices + Payments that webhook back to us.

BEGIN;

-- Stream consumer ID lives on merchants (one-to-one with Stream's Consumer).
ALTER TABLE public.merchants
  ADD COLUMN IF NOT EXISTS stream_consumer_id text;

-- Stream product + subscription IDs live on the loan.
ALTER TABLE public.loans
  ADD COLUMN IF NOT EXISTS stream_product_id      text,
  ADD COLUMN IF NOT EXISTS stream_subscription_id text,
  ADD COLUMN IF NOT EXISTS stream_subscription_status text;

-- Track which Stream invoice/payment closed each installment.
ALTER TABLE public.installments
  ADD COLUMN IF NOT EXISTS stream_invoice_id text,
  ADD COLUMN IF NOT EXISTS stream_payment_id text;

CREATE INDEX IF NOT EXISTS idx_loans_stream_subscription
  ON public.loans(stream_subscription_id)
  WHERE stream_subscription_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_installments_stream_invoice
  ON public.installments(stream_invoice_id)
  WHERE stream_invoice_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_installments_stream_payment
  ON public.installments(stream_payment_id)
  WHERE stream_payment_id IS NOT NULL;

COMMIT;
