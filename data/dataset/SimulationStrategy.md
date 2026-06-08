# Simulation Strategy for Restaurant/Cafe POS Financial Data

## Bottom line

For this schema, the best usable strategy is **not** direct table sampling and **not** a pure GAN/LLM-style generator.

It should be a **causal, layered simulation**:

1. Simulate the restaurant's hidden operational reality.
2. Roll that reality into daily financial facts.
3. Reconcile sales, collections, bank movement, and obligations with hard accounting rules.
4. Validate utility, not just realism.

Because your exported schema is only:

- `merchants`
- `sales_daily`
- `payments_daily`
- `bank_daily`
- `obligations`

you need a richer **internal latent layer** even if you never export it.

## Why naive generation will fail

If you generate each daily table independently, the data will look plausible at a glance but break under analysis:

- sales spikes will not line up with bank inflows
- payment mix will not match local market behavior
- refunds will not follow service failures, promotions, or delivery-heavy days
- obligations will not create realistic liquidity stress
- bank balances will drift or jump without operational causes
- seasonality will be too smooth and too generic

That makes the dataset bad for underwriting, operations analytics, fraud checks, forecasting, or scenario testing.

## Recommended architecture

Use a **two-layer architecture**.

### Layer 1: hidden simulation layer

Generate hidden objects that are not necessarily exported:

- merchant profile
- city and market context
- daypart demand
- order arrivals
- queue/capacity pressure
- basket and discount behavior
- payment tender behavior
- settlement lags
- cash deposit behavior
- supplier, payroll, rent, tax, and loan events
- service failures, outages, promotions, and special events

### Layer 2: exported schema layer

Aggregate hidden events into:

- `sales_daily`
- `payments_daily`
- `bank_daily`
- `obligations`

This gives you both realism and explainability.

## Core design principle

Generate data from **causes to effects**, not from columns to columns.

Use a causal chain like this:

`merchant archetype + city + calendar + weather + event + promotion + staffing/capacity -> orders -> sales -> collections -> bank settlement -> cash coverage of obligations`

That is much closer to how restaurant finance actually behaves.

## Merchant archetypes

Start by assigning each merchant to an archetype. Do not use one generic merchant model.

Recommended archetypes:

- specialty coffee kiosk
- neighborhood cafe
- bakery/pastry shop
- quick service restaurant
- casual dining restaurant
- delivery-first kitchen

Each archetype should have different priors for:

- operating hours
- daypart intensity
- seating capacity
- service rate
- average ticket
- item margin structure
- delivery dependence
- discount behavior
- refund rate
- card/wallet/cash mix
- supplier cadence
- payroll burden
- rent burden

Example logic:

- specialty coffee should concentrate demand in morning and afternoon
- bakery should spike around mornings, weekends, and special days
- quick service should show sharper lunch and dinner peaks
- casual dining should have higher tickets, lower order counts, and stronger weekend effects
- delivery-first kitchens should have later peaks, higher platform fees, and more refund volatility

## Geography and localization

The merchant city should materially affect scale and behavior.

Use city-level priors for:

- baseline demand
- wallet adoption
- rent burden
- seasonality amplitude
- weather sensitivity
- tourism/event sensitivity

If you are simulating Saudi data, treat localization as first-class:

- Ramadan
- Eid al-Fitr
- Eid al-Adha
- Hajj period where relevant
- National Day
- school breaks
- local weekend pattern
- month-end and salary-day demand effects
- high digital payment adoption
- VAT and e-invoice consistency

Do not bolt these on as afterthought multipliers. They should be part of the core calendar engine.

## Calendar engine

Your calendar model should have multiple overlapping effects:

- day of week
- week of month
- month of year
- holiday type
- holiday proximity
- payday proximity
- school in/out session
- major event flag
- weather regime

Special days should be modeled separately, not as a normal seasonal point.

The right mental model is:

- normal weekdays
- normal weekends
- holiday-like weekdays
- pre-holiday pull-forward days
- post-holiday normalization days
- event shock days

This matters because restaurant demand often changes regime, not just magnitude.

## Demand generation

Daily sales should emerge from **orders count x ticket behavior**, not from one direct revenue draw.

Generate demand in stages:

1. Potential customer arrivals by daypart.
2. Fulfilled orders after capacity constraints.
3. Basket value and discount behavior per fulfilled order.

Recommended dayparts:

- breakfast
- lunch
- afternoon
- dinner
- late night

Not all archetypes should use all dayparts equally.

### Count model

Use a count process such as:

- Poisson-lognormal
- Negative Binomial

The count mean should depend on:

- merchant baseline
- day of week
- month/season
- holiday state
- weather state
- promotion state
- local event state
- latent merchant health

Conceptually:

`lambda(m, d, p) = base(m, p) x weekday(d) x season(d) x holiday(d) x weather(d) x promo(m, d) x event(city, d) x health(m, d)`

Then sample:

`arrivals ~ NegBin(mean=lambda, dispersion=k)`

Negative Binomial is preferable to pure Poisson because real restaurant traffic is overdispersed.

## Capacity and queueing layer

This is where most synthetic restaurant datasets stay too shallow.

A restaurant cannot fulfill unlimited demand just because demand is high.

For each merchant-day-daypart, simulate:

- staffed service capacity
- service time distribution
- order prep bottlenecks
- queue pressure
- abandonment or lost demand

Useful capacity drivers:

- seat count or service points
- staffed labor hours
- throughput per labor hour
- service-time distribution
- delivery prep load

Then derive:

- `fulfilled_orders = min(arrivals, effective_capacity)`
- lost demand
- service-failure probability

This matters because capacity stress should affect:

- refunds
- discounts used for recovery
- next-day reputation drag
- bank strength through missed revenue

## Basket, ticket, and menu logic

Do not simulate `avg_ticket` directly as an isolated number.

Instead, simulate hidden basket behavior and derive ticket size.

Recommended hidden basket components:

- order channel: dine-in, takeaway, delivery
- basket size
- add-on probability
- premium item probability
- dessert/drink attachment
- promotion type
- discount depth

Use a distribution like lognormal or gamma for basket value, with modifiers by:

- archetype
- daypart
- channel
- weather
- event
- promotion

Then derive:

- `gross_sales`
- `discounts`
- `orders_count`
- `avg_ticket`

### Hidden menu categories

Even if the exported schema is daily financial only, the simulator should maintain hidden menu categories such as:

- coffee/tea
- bakery
- main meals
- desserts
- cold beverages
- seasonal specials

Why this matters:

- weather impacts categories differently
- promotions create substitution and cannibalization
- margin changes do not hit all products equally
- cafes and restaurants differ materially in attachment behavior

## Promotion logic

Promotions should not be a simple discount percentage on sales.

Model promotions as interventions that change:

- traffic
- basket composition
- discount spend
- margin
- cannibalization across items
- return/refund risk if execution fails

Recommended promotion types:

- traffic-driving percentage off
- bundle meal
- coffee + pastry combo
- loyalty redemption
- free delivery
- end-of-day clearance

Each promotion should have:

- eligibility
- uplift effect
- cannibalization effect
- margin effect
- duration
- decay or fatigue

For realism, store the promotion as a hidden event and let its effects flow into the exported tables.

## Refunds and service-failure logic

Refunds should not be random noise.

Refund probability should rise with:

- delivery share
- high queue pressure
- outages
- payment reversal events
- quality or stock-out failures
- aggressive promotions

Recommended rule:

`refund_rate = base_refund + a*delivery_share + b*queue_stress + c*outage_flag + d*promo_complexity`

Then cap it to archetype-appropriate ranges.

This makes refund spikes explainable.

## Semantics for `sales_daily`

Before generation, freeze exact accounting semantics. Otherwise the dataset will become inconsistent later.

Recommended definitions:

- `gross_sales`: pre-discount, tax-exclusive merchandise value of fulfilled orders
- `discounts`: promotional and manual discounts granted on those orders
- `refunds_amount`: value refunded or credited for prior or same-day orders
- `net_sales`: `gross_sales - discounts - refunds_amount`
- `orders_count`: fulfilled order count
- `avg_ticket`: `(gross_sales - discounts) / orders_count`
- `vat_amount`: VAT computed from taxable net sales according to the active tax regime

If you prefer a different semantic for `net_sales`, lock it once and keep it consistent everywhere.

## VAT and invoice consistency

If this is Saudi-oriented, keep VAT and invoice-note behavior aligned with ZATCA rules.

That means:

- VAT should follow the chosen taxable base consistently
- refunds should conceptually map to credit-note behavior
- invoice sequencing and e-invoicing constraints should be respected in the hidden layer if you ever extend to receipt-level data

Even in a daily dataset, VAT cannot behave like free noise.

## Payment tender generation

`payments_daily` should represent how customers paid on the payment date, not how the bank settled the money.

Simulate tender at order level or basket level:

- cash
- card
- wallet

Tender shares should depend on:

- city
- archetype
- channel
- ticket size
- promotion type

For Saudi-specific simulations, use a strongly digital prior and let merchants vary around it.
Keep smaller merchants somewhat more cash-heavy than large operators when you want realism at the micro-business level.

## Semantics for `payments_daily`

Recommended definitions:

- `cash_amount`: customer cash collected that day
- `card_amount`: customer card collections recorded that day
- `wallet_amount`: customer wallet collections recorded that day
- `total_collected`: `cash_amount + card_amount + wallet_amount`

In a clean operational model:

- `total_collected` should usually track `gross_sales - discounts - same-day voids`
- same-day refunds reduce same-day collections only if the refund happens immediately
- many refunds should instead surface later through bank settlement reversals

## Settlement and bank conversion

This is the most important bridge between POS data and real cash health.

Do not map `payments_daily.total_collected` straight into `bank_daily.inflows`.

Instead simulate settlement mechanics:

- cash deposited same day, next day, or batched
- card settled at T+1 or T+2
- wallet settled on its own lag
- merchant discount rate and fees deducted
- refund reversals and chargebacks delayed
- occasional settlement holds or disputes

Then bank inflows become operationally believable.

## Bank movement model

`bank_daily` should be ledger-consistent.

Use the hard identity:

`closing_balance = opening_balance + inflows - outflows`

Bank inflows may include:

- cash deposits
- card settlements net of fees
- wallet settlements
- owner cash injections
- loans or financing draws

Bank outflows may include:

- rent
- payroll
- supplier payments
- utilities
- taxes
- loan repayments
- POS/platform fees
- petty cash withdrawals

Keep hidden transaction tags even if the exported table only stores totals.

That lets you explain stress cases later.

## Obligations engine

`obligations` should not be generated independently from `bank_daily`.

Generate them from merchant economics:

- rent: fixed, due monthly
- payroll: semi-monthly or monthly, partly linked to staffing
- supplier: variable, tied to sales volume and COGS with payment terms
- tax: tied to VAT accumulation and filing cadence
- loan: fixed amortization schedule when relevant

Then simulate actual payments and set:

- `amount_due`
- `amount_paid`
- `status`

Recommended statuses:

- unpaid
- partial
- paid
- overdue

This creates realistic cash stress and repayment-risk signals.

## Strong scenario library

Do not generate one generic population. Use scenario families.

Recommended core scenarios:

1. Stable healthy operator
2. Fast-growing store
3. Seasonal cafe
4. Promotion-dependent merchant
5. Capacity-constrained lunch business
6. Delivery-heavy operator
7. Margin-squeezed merchant
8. Liquidity-stressed merchant
9. Cash-leakage or settlement-mismatch merchant
10. Recovery merchant after an outage or weak quarter

Each scenario should change multiple drivers at once:

- demand
- margin
- discounting
- payment mix
- refund behavior
- settlement lag
- obligations coverage

That creates datasets useful for ranking, anomaly detection, and underwriting.

## Recommended hidden state variables

Per merchant:

- archetype
- city
- capacity index
- service quality score
- digital payment propensity
- delivery share
- baseline margin profile
- rent burden
- payroll intensity
- supplier credit terms

Per merchant-day:

- holiday regime
- weather regime
- event intensity
- promotion regime
- staffing level
- queue stress
- outage flag
- reputation momentum
- cash stress level

These hidden states are what make the exported daily tables coherent.

## Use structural logic first, ML second

If you already have real anchor data later, the best stack is:

1. structural causal simulator
2. parameter calibration on real data
3. optional residual learner for realism

Good residual tools later can include:

- copulas for dependency correction
- hierarchical Bayesian fitting
- diffusion/tabular models on merchant-level parameter vectors
- SCM-based relational generators for cross-table refinement

Do **not** start by training a black-box model directly on final daily rows unless you also enforce accounting and inter-table constraints.

For this use case, explainability and controllability matter more than surface realism.

## Calibration strategy

Use a top-down plus bottom-up calibration.

### Top-down anchors

Use external benchmarks for:

- city-level scale
- category-level seasonality
- payment-digitization priors
- holiday shock patterns

### Bottom-up merchant generation

For each merchant, sample:

- relative market share inside city x archetype
- price level
- capacity
- operating efficiency
- payment behavior
- cost burden

Then check that the merchant population aggregates back to realistic market-level totals.

## Practical generation workflow

Recommended workflow:

1. Generate merchant master data.
2. Build yearly calendar and exogenous features by city.
3. Simulate daily hidden demand by daypart.
4. Apply capacity constraints and service stress.
5. Simulate basket values, discounts, and refunds.
6. Roll up into `sales_daily`.
7. Assign tenders and collection timing.
8. Roll up into `payments_daily`.
9. Simulate settlement lags, deposits, fees, and non-sales cash flows.
10. Roll up into `bank_daily`.
11. Generate obligations and payment outcomes.
12. Validate accounting identities, temporal realism, and utility.

## Validation framework

Validation must be multi-layered.

### Hard accounting rules

Every dataset should satisfy:

- no negative balances unless overdraft is explicitly allowed
- `closing_balance = opening_balance + inflows - outflows`
- `total_collected = cash_amount + card_amount + wallet_amount`
- `avg_ticket x orders_count` should be close to sales before refunds within defined tolerance
- VAT must be mathematically consistent
- obligation status must match due/paid logic

### Cross-table realism

Check whether:

- bank inflows lag collections realistically
- cash-heavy merchants deposit cash in believable patterns
- refund spikes later affect settlements
- supplier payments follow sales with terms-based lag
- tax obligations accumulate and release on filing cadence

### Temporal realism

Check:

- weekly seasonality
- holiday regime changes
- autocorrelation
- volatility clustering
- mean reversion after shocks
- scenario-specific stress persistence

### Utility validation

If you later compare against real data, use:

- marginal distribution checks
- pairwise and joint distribution checks
- downstream ML utility
- logical rule violation rate

For downstream ML utility, use TRTR vs TSTR style evaluation:

- train on real, test on real
- train on synthetic, test on the same real holdout

If model performance stays close, the synthetic data is useful, not just pretty.

## What the final exported tables should be good for

With this design, the five-table schema should support:

- restaurant underwriting
- liquidity stress scoring
- cash conversion analysis
- refund and discount abuse detection
- city and segment benchmarking
- promotion sensitivity analysis
- obligation coverage tracking
- scenario testing for lenders or operators

## Recommended realism checks by feature

High-signal checks:

- `refunds_amount / gross_sales`
- `card_amount / total_collected`
- `wallet_amount / total_collected`
- `inflows / net_sales`
- `closing_balance / avg_daily_outflows`
- monthly obligations coverage
- weekend uplift by archetype
- Ramadan or holiday regime change by archetype
- delay between collection and bank inflow

If these are wrong, the dataset is not analytically trustworthy.

## Most important implementation decision

If you only keep one principle, keep this one:

**simulate hidden restaurant operations first, then aggregate into finance**

That is the difference between a demo dataset and a dataset that can support deep insight.

## Research signals used for this strategy

- Restaurant demand forecasting works better when day-of-week, trend/seasonality, weather, and special-day effects are treated explicitly rather than as generic noise.
- Retail and bakery demand literature shows special days and neighboring days behave differently enough to deserve their own regime logic.
- Restaurant weather studies show weather changes affect categories differently, which supports a hidden menu/category layer.
- Queueing studies show peak-hour capacity and service-time distributions materially change fulfilled demand and waiting behavior.
- Recent synthetic-data research keeps pointing to the same issue: matching marginals is not enough; logical and inter-table consistency must be preserved.
- Recent relational synthetic-data work favors causal or structural approaches when multiple connected tables need to remain coherent.

## Source links

- ZATCA e-invoice specifications: https://www.zatca.gov.sa/en/E-Invoicing/SystemsDevelopers/Pages/E-Invoice-specifications.aspx
- SAMA: e-payments were 85% of retail payments in 2025: https://www.sama.gov.sa/en-US/News/Pages/news-1139.aspx
- SAMA payments usage study, useful for business-level cash vs non-cash priors: https://www.sama.gov.sa/en-US/Documents/Report_on_Payments_Usage_Study_2023_en.pdf
- SAMA weekly POS report, including `Restaurants & Cafes` and city breakdowns: https://www.sama.gov.sa/ar-sa/Indices/POS/Weekly_Points_of_Sale_Transactions_Report_28th-Feb-2026.pdf
- SAMA weekly POS report showing strong week-to-week restaurant movement in early March 2026: https://www.sama.gov.sa/en-US/Indices/POS_EN/Weekly_Points_of_Sale_Transactions_Report_07_Mar_2026.pdf
- Open Banking transactions model: https://openbankinguk.github.io/read-write-api-site3/v3.1.7/resources-and-data-models/aisp/Transactions.html
- Open Banking balances model: https://openbankinguk.github.io/read-write-api-site3/v3.1.11/resources-and-data-models/aisp/Balances.html
- Restaurant sales forecasting with weather and special days: https://dergipark.org.tr/en/pub/jda/issue/86230/1450459
- Daily retail demand forecasting with emphasis on calendric special days: https://www.sciencedirect.com/science/article/pii/S0169207020300224
- Weather effects on restaurant sales: https://www.tandfonline.com/doi/full/10.1080/15378020.2016.1209723
- Menu engineering with substitution effects: https://www.sciencedirect.com/science/article/pii/S0278431920300566
- Queueing simulation in fast food restaurants: https://www.researchgate.net/publication/341765787_Analysis_Of_Queuing_Models_Of_Fast_Food_Restaurant_with_Simulation_Approach
- NIST synthetic-data utility evaluation methods: https://pages.nist.gov/HLG-MOS_Synthetic_Data_Test_Drive/
- Utility evaluation with TSTR vs TRTR framing: https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2025.1576290/full
- Logical relationship preservation in synthetic tabular data: https://openreview.net/forum?id=9FIOO09boS
- Relational synthetic data via structural causal models: https://aclanthology.org/2025.trl-1.2/
- TabSCM and causal tabular generation: https://openreview.net/forum?id=dW2ToB9u89
