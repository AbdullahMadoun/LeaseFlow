-- LeaseFlow 0004: seed F&B segments with KSA-contextualized benchmarks.
-- Numbers are priors, not ground truth. Tune post-demo with real data.
-- All monetary values in SAR.

BEGIN;

INSERT INTO public.segments (name, label, benchmarks) VALUES
(
  'specialty_coffee',
  'Specialty coffee / counter-service café',
  jsonb_build_object(
    'avg_ticket_sar',          jsonb_build_array(18, 45),
    'items_per_ticket',        jsonb_build_array(1.3, 2.2),
    'void_rate',               jsonb_build_array(0.003, 0.015),
    'discount_rate',           jsonb_build_array(0.02, 0.08),
    'refund_rate_max',         0.005,
    'avg_monthly_revenue_sar', 85000,
    'avg_net_margin',          0.14,
    'failure_rate_3y',         0.35,
    'peak_hour_share',         jsonb_build_array(0.35, 0.55),
    'weekend_lift',            jsonb_build_array(0.10, 0.40),
    'top10_sku_share',         jsonb_build_array(0.50, 0.75)
  )
),
(
  'qsr',
  'Quick-service restaurant',
  jsonb_build_object(
    'avg_ticket_sar',          jsonb_build_array(25, 75),
    'items_per_ticket',        jsonb_build_array(1.5, 2.5),
    'void_rate',               jsonb_build_array(0.003, 0.015),
    'discount_rate',           jsonb_build_array(0.02, 0.10),
    'refund_rate_max',         0.005,
    'avg_monthly_revenue_sar', 160000,
    'avg_net_margin',          0.12,
    'failure_rate_3y',         0.30,
    'peak_hour_share',         jsonb_build_array(0.40, 0.60),
    'weekend_lift',            jsonb_build_array(0.15, 0.45),
    'top10_sku_share',         jsonb_build_array(0.55, 0.80)
  )
),
(
  'casual_dining',
  'Casual / full-service restaurant',
  jsonb_build_object(
    'avg_ticket_sar',          jsonb_build_array(80, 300),
    'items_per_ticket',        jsonb_build_array(2.5, 4.5),
    'void_rate',               jsonb_build_array(0.005, 0.020),
    'discount_comp_rate',      jsonb_build_array(0.03, 0.10),
    'tip_share',               jsonb_build_array(0.10, 0.20),
    'avg_monthly_revenue_sar', 260000,
    'avg_net_margin',          0.10,
    'failure_rate_3y',         0.40,
    'dinner_share_of_day',     jsonb_build_array(0.55, 0.70),
    'table_turns_per_service', jsonb_build_array(1.5, 3.0)
  )
),
(
  'fine_dining',
  'Fine dining',
  jsonb_build_object(
    'avg_ticket_sar',          jsonb_build_array(300, 900),
    'items_per_ticket',        jsonb_build_array(3.5, 6.0),
    'void_rate',               jsonb_build_array(0.005, 0.020),
    'discount_comp_rate',      jsonb_build_array(0.02, 0.08),
    'tip_share',               jsonb_build_array(0.12, 0.22),
    'avg_monthly_revenue_sar', 480000,
    'avg_net_margin',          0.08,
    'failure_rate_3y',         0.45,
    'dinner_share_of_day',     jsonb_build_array(0.70, 0.85),
    'table_turns_per_service', jsonb_build_array(1.0, 2.0)
  )
),
(
  'bakery',
  'Bakery / patisserie',
  jsonb_build_object(
    'avg_ticket_sar',          jsonb_build_array(15, 60),
    'items_per_ticket',        jsonb_build_array(1.5, 3.0),
    'void_rate',               jsonb_build_array(0.002, 0.012),
    'discount_rate',           jsonb_build_array(0.02, 0.07),
    'avg_monthly_revenue_sar', 110000,
    'avg_net_margin',          0.13,
    'failure_rate_3y',         0.32,
    'peak_hour_share',         jsonb_build_array(0.30, 0.50),
    'weekend_lift',            jsonb_build_array(0.20, 0.60)
  )
),
(
  'juice_bar',
  'Juice bar / healthy grab-and-go',
  jsonb_build_object(
    'avg_ticket_sar',          jsonb_build_array(20, 55),
    'items_per_ticket',        jsonb_build_array(1.0, 1.8),
    'void_rate',               jsonb_build_array(0.003, 0.015),
    'discount_rate',           jsonb_build_array(0.02, 0.09),
    'avg_monthly_revenue_sar', 70000,
    'avg_net_margin',          0.15,
    'failure_rate_3y',         0.40
  )
),
(
  'dessert_parlor',
  'Dessert parlor / ice cream',
  jsonb_build_object(
    'avg_ticket_sar',          jsonb_build_array(25, 80),
    'items_per_ticket',        jsonb_build_array(1.8, 3.2),
    'void_rate',               jsonb_build_array(0.003, 0.015),
    'discount_rate',           jsonb_build_array(0.03, 0.10),
    'avg_monthly_revenue_sar', 95000,
    'avg_net_margin',          0.14,
    'failure_rate_3y',         0.38,
    'weekend_lift',            jsonb_build_array(0.30, 0.80)
  )
),
(
  'cloud_kitchen',
  'Cloud / delivery-only kitchen',
  jsonb_build_object(
    'avg_ticket_sar',          jsonb_build_array(45, 120),
    'items_per_ticket',        jsonb_build_array(1.5, 2.8),
    'void_rate',               jsonb_build_array(0.005, 0.025),
    'refund_rate',             jsonb_build_array(0.01, 0.04),
    'avg_monthly_revenue_sar', 130000,
    'avg_net_margin',          0.08,
    'failure_rate_3y',         0.50,
    'aggregator_commission',   jsonb_build_array(0.18, 0.30)
  )
),
(
  'food_truck',
  'Food truck / mobile',
  jsonb_build_object(
    'avg_ticket_sar',          jsonb_build_array(25, 75),
    'items_per_ticket',        jsonb_build_array(1.3, 2.2),
    'avg_monthly_revenue_sar', 55000,
    'avg_net_margin',          0.15,
    'failure_rate_3y',         0.45
  )
),
(
  'other_fnb',
  'Other F&B',
  jsonb_build_object(
    'avg_ticket_sar',          jsonb_build_array(20, 200),
    'avg_monthly_revenue_sar', 120000,
    'avg_net_margin',          0.11,
    'failure_rate_3y',         0.38
  )
)
ON CONFLICT (name) DO UPDATE
SET label      = EXCLUDED.label,
    benchmarks = EXCLUDED.benchmarks,
    updated_at = now();

-- ============================================================
-- Seed initial risk policy (versioned scorer config)
-- ============================================================

INSERT INTO public.risk_policies (rules, created_by, effective_from) VALUES (
  jsonb_build_object(
    'version', 'v1',
    'dimension_weights', jsonb_build_object(
      'pos',            0.25,
      'financial_docs', 0.30,
      'simah',          0.20,
      'sentiment',      0.10,
      'industry',       0.15
    ),
    'hard_floors', jsonb_build_array(
      jsonb_build_object('rule', 'dscr_minimum',     'threshold', 1.0),
      jsonb_build_object('rule', 'simah_defaults_max','threshold', 0)
    ),
    'thresholds', jsonb_build_object(
      'approve_overall_score_min', 70,
      'deny_overall_score_max',    40,
      'manual_review_band',        jsonb_build_array(40, 70)
    ),
    'dscr_bands', jsonb_build_object(
      'comfortable_min', 1.5,
      'marginal_min',    1.2
    ),
    'decision_mode', 'guardrail'
  ),
  NULL,
  now()
)
ON CONFLICT DO NOTHING;

COMMIT;
