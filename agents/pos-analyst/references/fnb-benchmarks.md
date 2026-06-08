# F&B Operational Benchmarks

These are typical ranges the agent can use as priors when judging whether a metric is normal, mild, or alarming. They are NOT ground truth — the data is. Benchmarks are loaded into the agent's context only as a sanity check, and any benchmark used in a finding must be cited as an external prior, not as a measured value.

## How to use this file

- The agent MAY reference these ranges to label an observed metric as "low", "typical", or "high".
- The agent MUST NOT use these numbers to overrule what the data shows.
- The agent MUST NOT report these numbers as if they came from the data.
- For a number-of-record claim ("your void rate is X% vs typical Y%"), X comes from `run_python`, Y comes from this file, and the comparison is the agent's reasoning.

## Counter-service café / quick-service restaurant (QSR)

| Metric | Typical range | Notes |
|---|---|---|
| Average ticket (single-store, urban) | $4 – $15 | Coffee shops cluster low; QSRs higher. Currency varies. |
| Items per ticket | 1.3 – 2.2 | <1.2 suggests single-item habit; >2.5 suggests strong attach. |
| Void rate | 0.3% – 1.5% of transactions | >2% is a red flag; investigate by staff and time-of-day. |
| Discount rate | 2% – 8% of gross revenue | Heavily promo-driven brands run 10–15%; sustained >20% suggests margin leakage. |
| Comp rate (free items) | 0.1% – 0.8% | Sustained >1.5% is unusual; investigate by staff. |
| Refund rate | <0.5% | >1% on a quick-service ticket is unusual. |
| Peak-hour share of daily volume | 35% – 55% in two peaks (AM rush + lunch) | Flat curves are unusual and worth a callout. |
| Weekend lift over weekday | +10% to +40% | Negative weekend lift suggests B2B/office-driven traffic. |
| Top-10 SKU share of revenue | 50% – 75% | <40% suggests bloated menu; >85% suggests over-reliance on a few items. |

## Full-service restaurant / casual dining

| Metric | Typical range | Notes |
|---|---|---|
| Average ticket | $20 – $80 per cover | Highly cuisine- and region-dependent. |
| Items per ticket | 2.5 – 4.5 | Includes drinks and sides. |
| Void rate | 0.5% – 2.0% | Higher than QSR because of order modifications. |
| Discount + comp rate combined | 3% – 10% | Includes loyalty, manager comps, marketing. |
| Tip share (where captured) | 10% – 20% of pre-tip ticket | Useful as a service-quality signal when it's in the data. |
| Peak-hour concentration | Lunch + dinner double peak; dinner ~55–70% of day | Lunch-only or dinner-only patterns are normal for many concepts. |
| Table turn (where derivable) | 1.5 – 3.0 turns per service | Requires table_id + open/close timestamps. |

## Cross-cutting operational signals

- **Cash-vs-card mix shift**: a multi-month drift toward cash without a stated reason can indicate skimming. A sudden card-mix jump usually means a new POS terminal or payment provider.
- **Time-of-day voids concentrated in last hour**: classic close-out adjustment pattern; investigate.
- **One staff member with >2× peer void rate**: not necessarily fraud, but always worth surfacing.
- **Single-item-only tickets dominating**: weak attach; pricing or upsell training opportunity.
- **Dead inventory**: SKUs with <1 sale/day for 30+ days in an active menu category — menu-rationalization signal.
- **Branch cannibalization**: same brand, same trade area, opposite-correlated daily revenue.

## Seasonal and calendar context

The agent should check the period covered by the data against known calendar effects in the operating region:

- **Public holidays** in the region can lift or suppress F&B revenue 20–80% depending on segment (retail-adjacent café up; office-adjacent café down on bank holidays).
- **Ramadan** — for businesses operating in Muslim-majority markets, daypart distribution shifts dramatically (suppressed daytime, surge after iftar). Comparing Ramadan to non-Ramadan months without flagging is a methodological error.
- **School calendar** — family-restaurant volumes track school holidays; summer +20–40% is typical in tourist areas.
- **Weather extremes** can collapse outdoor-seating-heavy concepts; if revenue craters on a single day, the agent should flag it as plausibly weather-related rather than label it an operational issue.

The agent's job is not to look these up exhaustively — it is to recognize when a date-range pattern in the data is plausibly explained by a calendar effect, and either confirm via `web_search` or flag the hypothesis in the report.
