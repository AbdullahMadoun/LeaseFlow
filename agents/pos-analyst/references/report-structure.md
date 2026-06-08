# Report Structure

The final deliverable is a single markdown document written for a non-technical business owner. Treat it like a 15-minute meeting where the analyst presents — direct, specific, no jargon, no hedging without a reason.

## Required sections (in order)

### 1. Headline finding

The single most important thing this business should know, in two to four sentences. Lead with the number, then the implication, then the recommended next move. If the finding is bad news, say so plainly. If the finding is good news that the owner should double down on, say that.

Bad: "Sales appear to be trending in a generally positive direction over the period analyzed."
Good: "Branch B's lunch revenue dropped 38% (from 412 SAR/day average in Jan–Feb to 256 SAR/day in March), driven entirely by a collapse in the 12:00–14:00 window. Everything else at Branch B is normal. The likely cause is something specific that changed in March at that branch — staff, menu, neighbouring foot traffic — and it should be investigated this week."

### 2. Revenue and transaction performance

What the top line did. Cover, with specific numbers from the analysis:

- Total gross revenue, total transactions, average ticket — for the full period.
- Trend across the period: is it growing, flat, declining, and at what rate.
- Composition: dine-in vs takeaway vs delivery (if present), cash vs card (if present).
- Anything notable about the distribution: long tail of high-value tickets, bimodal day patterns, etc.

If the data is a daily financial schema rather than receipt-level transactions, translate this section into the closest valid metrics:

- gross sales, net sales, refunds, discounts, collections, bank inflows
- merchant- or branch-level dispersion in those metrics
- cash conversion and settlement timing where the data supports it

### 3. Operational patterns

What the data reveals about how the business actually runs.

- Hourly and daily distribution. Where are the peaks. How peaked or flat is the curve.
- Day-of-week pattern. Weekend behavior.
- Staff or shift patterns if the data supports it (cashier IDs).
- Period-over-period changes in operating rhythm (opening earlier, closing earlier, dropping a daypart).

### 4. Product and menu intelligence

What is selling, what is not, and what basket data implies.

- Top items by revenue and by volume (often different — call out when they are).
- Bottom of the menu: items with negligible sales that occupy menu real estate.
- Categories: which is growing, which is shrinking.
- Basket signals: items frequently bought together, items that drag up average ticket when added.
- New items in the period (if identifiable) — did they take off or stall.

If there is no item-, category-, or basket-level data, do not invent this section. Replace it with the closest supported commercial-mix section, for example:

- discount intensity and promo dependence
- refund pressure and service-failure signals
- tender mix and payment behavior
- merchant segment or archetype differences

State clearly in the first sentence that menu-level detail was unavailable.

### 5. Branch-level intelligence

If and only if multiple branches are present. Skip the section entirely (and say so under analyst notes) if single-branch.

- Revenue rank, ticket rank, transaction rank by branch.
- Branches that are outliers in either direction — and why, if the data supports a hypothesis.
- Cannibalization signals (same-brand branches in the same trade area moving inversely).
- Branch-specific operational anomalies (e.g. one branch's voids 4× the network average).

If the dataset is a merchant portfolio rather than a single brand, reinterpret this as merchant-level intelligence:

- top and bottom merchants by sales, collections, and liquidity resilience
- city, archetype, or cohort concentration
- merchants whose bank conversion, refund rate, or obligation coverage is materially worse than peers
- portfolio segments that drive most downside risk

### 6. Risk signals

Anything that looks like revenue leakage, operational waste, fraud, or a structural anomaly worth investigating. Each item gets:

- **What** — the pattern in plain language.
- **Where** — branch / time-of-day / staff / item, as specific as the data allows.
- **How big** — quantified (revenue at risk, frequency).
- **What to look at** — the next step the owner should take to confirm or rule it out.

If there are no genuine risk signals, say so explicitly. Do not invent risk for the sake of having a section.

### 7. Specific recommendations

Concrete, actionable, each tied to a specific finding from earlier sections. Number them. For each recommendation:

- The action (one sentence, imperative).
- The finding it responds to (cite the section).
- What success looks like (a measurable change to look for in next month's data).

Aim for 3–7 recommendations. More than that becomes noise.

### 8. Analyst notes

Honest disclosure of what limited the analysis and what would help next time.

- What the data did not contain that would have improved the analysis (e.g. no cost data, so margin analysis impossible).
- If the dataset was daily rollups rather than raw transactions, say so explicitly and name the analyses that were therefore not possible.
- What assumptions were made (e.g. "negative quantities were treated as voids because the data did not include an explicit void column").
- What was checked but found nothing notable (so the owner doesn't worry the agent skipped it).
- What additional data, if collected next month, would unlock the next layer of analysis.

## Tone and language rules

- Use the second person where natural ("your busiest day is Friday"). Drop it when it gets repetitive.
- Numbers go in the prose, not in footnotes. The owner should not have to look anywhere else.
- Currency: use the symbol or code from the data. Don't convert.
- Percentages: one decimal place at most. "23%" not "22.7%".
- Dates: month + day at minimum ("March 14"), with year if the period crosses a year boundary.
- No bullet-point lists where prose flows naturally. Use bullets when listing parallel items (top SKUs, branches, recommendations).
- No section is required to be long. A two-line section is fine if there's nothing more to say.

## What never appears in the report

- Code snippets.
- Column names from the raw data ("the `txn_total` column"). Translate to business language ("ticket total").
- Library names ("we ran a pandas groupby"). The owner doesn't care.
- Hedging without a reason. Never say "this may suggest" unless the next clause explains the specific reason it's only a suggestion.
- Generic F&B advice not anchored to a finding from THIS data.
- Apologies for limits of the data — those go in section 8 once, not repeatedly.

## Length

Target 1,200 – 2,500 words. Shorter if the dataset is small; longer only when there are genuinely many findings. A 4,000-word report is almost always a sign the agent is padding.
