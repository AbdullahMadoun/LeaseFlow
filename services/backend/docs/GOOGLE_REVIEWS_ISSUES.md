# Google Reviews Agent Issues

Date: 2026-04-16
Branch: `google-reviews-agent`
Scope: company name or Google Maps URL -> matched place -> Google review report summary

## Current behavior

The Google reviews agent does the following:
- accepts a merchant company name
- optionally accepts a direct Google Maps URL
- resolves a Google Maps place
- scrapes Google-origin reviews through Apify
- generates a structured review summary

The implementation lives in:
- `leaseflow/app/google_reviews_agent.py`
- `leaseflow/app/dims/sentiment.py`

## Confirmed issues and limitations

### 1. Company-name-only matching is not branch-safe

If a brand has multiple branches with very similar names, the agent cannot safely infer which branch is intended from the company name alone.

Observed example:
- `Namq Cafe`

Live lookup returned multiple strong matches, including:
- Riyadh, Al Manar
- Riyadh, Al Malqa
- Jubail

Because the top candidates were too close in score, the resolver now fails closed and returns an ambiguous-match result instead of picking one.

Impact:
- branch-level certainty requires a direct Google Maps URL, or future support for city/district disambiguation

Status:
- partially mitigated by persisting exact branch identity after a successful
  match, so future runs can reuse `google_place_id` / `google_place_url`
  instead of repeating fuzzy matching

### 2. Direct Google Maps URL path is trusted

If `google_maps_url` is provided, the resolver currently trusts it and skips place-search ranking.

Impact:
- if the supplied URL points to the wrong branch or wrong business, the agent will scrape that place

Recommended fix:
- fetch place metadata for the provided URL and verify the place title against the company name before accepting it

Status:
- not fixed yet

### 3. Name matching is heuristic only

Current place matching uses:
- normalized full-name equality
- substring containment
- token overlap after removing generic words like `cafe` and `restaurant`
- small boost for review count
- penalty for closed places

What it does not yet use:
- merchant city
- district
- phone number
- CR number
- website domain

Impact:
- common brand names remain ambiguous unless a URL is supplied

### 4. Apify usage has been reduced, but is still external and paid

Current cost-control behavior:
- company-name-only flow uses one Apify actor call
- direct-URL flow still uses a dedicated reviews actor call
- in-process cache keeps reports for 12 hours to avoid repeated hits for the same business/query pair
- default limits were reduced to `max_places=3` and `max_reviews=20`

Impact:
- repeat requests in the same running process are cheap
- cold starts or multiple app instances still cause new Apify runs

### 5. Review sample can differ from place aggregate

Apify can return a small recent review sample while the place has thousands of total reviews.

Mitigation already added:
- deterministic fallback now anchors to the place aggregate rating when the sampled reviews are too few or clearly unrepresentative

Remaining issue:
- a recent-review sample can still make trend analysis noisy

### 6. LLM summary generation can fail

If MiniMax fails or returns invalid JSON during review summarization, the agent falls back to deterministic scoring and summary logic.

Impact:
- the pipeline still completes
- summary quality becomes more rigid and less nuanced

Observed during live tests:
- `google reviews llm summary failed`

### 7. Audit logging is best-effort

The agent writes audit rows via `ai_traces`, but tracing failures are intentionally non-fatal.

Impact:
- a review report can succeed even if trace rows fail to insert
- debugging may be less complete when Supabase logging is unavailable

Observed during live tests:
- `ai_traces insert failed`

## Operational rule right now

Use these inputs in this order:

1. Best: direct Google Maps URL for the exact branch
2. Acceptable: company name plus future city support
3. Weakest: company name only

If only company name is available and the resolver returns ambiguity:
- do not auto-pick a branch
- require the merchant to provide the exact Maps URL

## Recommended next improvements

### High priority

- add city and district to the resolver score
- verify provided Google Maps URLs against returned place metadata
- store top 3 candidates in the output when ambiguous

### Medium priority

- add persistent cache outside process memory
- include website-domain matching when present
- expose an admin review step for ambiguous brand matches

### Low priority

- calibrate score thresholds using a labeled place-match set
- expand review red-flag taxonomy for food safety and service incidents
