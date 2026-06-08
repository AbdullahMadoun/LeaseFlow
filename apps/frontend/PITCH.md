# LeaseFlow — Hackathon Pitch Deck

3-minute pitch · 6 slides · Vision 2030 × Saudi F&B financing.
Live deck: `http://localhost:5174/slides`.

---

## Slide 01 — Hook / Title · ~15s

**Eyebrow**: `HACKATHON · RIYADH · 2026`

**Headline**:
> **LeaseFlow.**

**Subtitle**:
> 90-second lease-to-own financing for the Kingdom's cafés.

**Footer mark**: *Built for Vision 2030 · No loans · No collateral · No waiting.*

### Talking points
- Open with the name + tagline. Let it breathe.
- Optional one-liner: "We finance the machines that pour the Kingdom's coffee."

---

## Slide 02 — Ahmed (The Moment) · ~35s

**Eyebrow**: `01 · MEET AHMED`

**Headline**:
> **Ahmed runs a café in Olaya.**

**Body**:
> His specialty-coffee traffic is up **40%** this quarter. He needs a second espresso machine — **﷼ 50,000**.
>
> His bank said **[no]** in 14 days.

**Right column — three red-flag cards**:
1. **✕ No collateral** — Café equipment doesn't qualify as bank collateral.
2. **✕ No history** — 2 years of books; not enough for a traditional lender.
3. **✕ No time** — Competitor across the street opened last week.

### Talking points
- Name a real merchant. Judges remember Ahmed; they don't remember "micro-SMEs".
- The 40% traffic is the hook — this is a *growing* business, not a struggling one.
- End with: "This isn't one Ahmed. It's every café owner in the Kingdom."

---

## Slide 03 — The Gap · ~35s

**Eyebrow**: `02 · THE GAP`

**Headline**:
> Ahmed's problem is a **[SAR 300 billion]** problem.

**Side note (right rail)**: *Every rejected café is a dent in Vision 2030.*

**Four-cell grid**:
| Metric | Label | Caption |
|---|---|---|
| **﷼ 50B** | KSA F&B market by 2030 | Up from $35B in 2024 · 8–9% CAGR |
| **12%** | Cafés & bars CAGR | Fastest-growing segment in the Kingdom |
| **4×** | Cafés per capita target | Vision 2030: 258 → 1,000 per million |
| **﷼ 300B** + donut (22%) | Unfunded SME gap | SME GDP share: 22% today → 35% target |

### Talking points
- Lead with the punchline: "300 billion riyals of unmet demand."
- The 4× cafés number is *mandated* by Vision 2030. We're not guessing at a market; the Kingdom is pulling it in.
- The donut visualizes the gap: SMEs are 22% of GDP today; the target is 35%. That +13pp is where we live.

---

## Slide 04 — Solution · ~45s

**Eyebrow**: `03 · WHAT WE BUILT`

**Headline**:
> **Lease-to-own. Underwritten in 90 seconds.**

**Side note**: *The machine is the collateral. The merchant owns it at payoff.*

**Three-step protocol**:

**01 · UPLOAD**
> Bank statement · POS data · invoice · financial statement. No forms. Raw ingest.

**02 · WE SCORE**
> 5-dimension LLM pipeline. Rules-anchored. Every decision audit-traceable end-to-end.

**03 · YOU GET ﷼**
> Lease-to-own disbursement. Stream auto-debit. Sharia-compliant by construction.

### Talking points
- This is the wedge: lease-to-own, **not a loan**. Three consequences:
  1. **Sharia-compliant** by construction (not retrofit).
  2. **Zero-collateral** — the espresso machine IS the asset.
  3. **Aligned** — the merchant owns it at payoff, we're not rent-extractors.
- "We read raw docs. We don't ask merchants to fill forms they don't have time for."
- "Every decision has a trace. Admins can audit it line by line."

---

## Slide 05 — Live Ledger (Demo) · ~35s

**Eyebrow**: `04 · LIVE SYSTEM`

**Headline**:
> **Not a mockup. [A ledger.]**

**Body**:
> Backend runs end-to-end today. Every decision is a row, every installment a receipt.

**Left column — status donut**: `12 mo` in center · 1 Paid (green) · 1 Due (yellow) · 10 Queued (gray).

**Left column — tech rows**:
- **Underwriting** — FastAPI · LLM + deterministic rules
- **Data** — Supabase · Mumbai region · RLS
- **Payments** — Stream.sa auto-debit subscriptions

**Right column — terminal card** (`AHMED.COFFEE · ACTIVE_LEASE.LEDGER`):
- Status: **APPROVED · 87s**
- Principal: **﷼ 50,000** · 12 mo · fixed · auto-debit · asset: espresso machine
- Repayment ledger: installments 01–05 visible, 7 more queued.

### Talking points
- "We didn't build a demo. We built the system." Name specific pieces.
- "Every installment you see is a real row in a real database. If you wanted to pay installment 02, we'd webhook-flip it green on this screen in under a second."
- This is the execution-quality slide. Judges reward what actually runs.

---

## Slide 06 — Close / Why We Win · ~15s

**Eyebrow**: `05 · WHY WE WIN`

**Headline**:
> The only automated, data-native, **[Sharia-compliant]** café lender in the room.

**Three-cell differentiator row**:
- **▶ Lease-to-own** — Asset-backed · not a loan · zero collateral
- **▶ F&B-native** — Built for cafés · not horizontal SME lending
- **▶ Live today** — Backend · DB · webhooks · frontend · running

**Yellow close banner**:
> **Fund the Kingdom's next 4× cafés.**
> *Vision 2030 · 258 → 1,000 per million.*
> CTA: **Let's ship it →**
> Footer: `leaseflow.sa · Riyadh node`

### Talking points
- Close on the positioning: sector-focused, structurally Sharia-compliant, already running.
- Tie back to the Vision 2030 number. "If we want 4× more cafés, someone has to fund them. We're the only team in this room that built the thing."
- Land the CTA and stop talking.

---

## Pacing sheet

| # | Slide | Target | Cumulative |
|---|---|---|---|
| 01 | Hook | 15s | 0:15 |
| 02 | Ahmed | 35s | 0:50 |
| 03 | Gap | 35s | 1:25 |
| 04 | Solution | 45s | 2:10 |
| 05 | Ledger | 35s | 2:45 |
| 06 | Close | 15s | 3:00 |

---

## Delivery rules

1. **Start on Ahmed by the 20s mark.** Don't linger on the title.
2. **No jargon on stage.** DSCR, dimension scores, override_applied — none of it is spoken. Merchants don't hear it; judges don't need it.
3. **Practice the 4× line.** It's your closer's payoff.
4. **Keyboard nav only**: `→` / `Space` / `PgDn` advance, `←` / `PgUp` go back, `Home` / `End` jump.
5. **If demo fails**, slide 05 still reads as a static proof — don't apologize, keep moving.

---

## Data sources

- Saudi Foodservice Market — [Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/saudi-arabia-foodservice-market)
- Saudi F&B Market Size & Forecast — [IMARC Group](https://www.imarcgroup.com/saudi-arabia-foodservice-market)
- Restaurant Statistics Saudi Arabia — [Restroworks](https://www.restroworks.com/blog/restaurant-statistics-saudi-arabia/)
- SME role in Vision 2030 — [Eye of Riyadh](https://www.eyeofriyadh.com/news/details/sme-s-role-in-vision-2030)
- Biban 2025 — Monsha'at SME surge — [Arab News](https://www.arabnews.com/node/2621496/business-economy)
- Saudi SME financing gap — [Arab News](https://www.arabnews.com/node/2124751)
- Vision 2030 — A Thriving Economy — [Vision 2030](https://www.vision2030.gov.sa/en/overview/pillars/a-thriving-economy)
- Saudi Riyal Symbol — [SAMA official guidelines](https://www.sama.gov.sa/en-US/Currency/SRS/Pages/Guidelines.aspx)
- Pitch craft — [Ink Narrates](https://www.inknarrates.com/post/hackathon-pitch-deck), [TAIKAI](https://taikai.network/en/blog/how-to-create-a-hackathon-pitch)
