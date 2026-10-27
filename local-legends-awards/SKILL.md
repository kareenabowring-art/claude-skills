---
name: local-legends-awards
description: Run a "Local Legends" awards outreach campaign — scrape public Google reviews for one business type in one city, tag and count them in code, and make branded award cards plus outreach drafts for each winner.
---

# Local Legends Awards

Turn public Google reviews into data-backed, "Wrapped"-style award cards for
local businesses, then draft outreach that offers each winner their card.
The cards are the hook: the business gets something shareable, and you get a
warm reason to start a conversation.

## Inputs to collect first

Ask for anything missing before starting:

- **Business type** — e.g. med spas
- **City** — e.g. Chattanooga, Tennessee
- **Award categories** — e.g. speed of service, return visits, most-mentioned staff
- **Branding** — colors, fonts, logo or a brand-kit link
- **Review date window** — e.g. last 12 months
- **Sender** — name, business and what they offer (for the outreach drafts)

Work in two phases and **stop for the user's review between them**.

## Phase 1 — Collect the public data

1. Build a list of every [business type] in [city] from public data.
   Deduplicate each business by its source place ID.
2. Using connected data tools (e.g. the Apify Google Maps Reviews Scraper,
   `compass/google-maps-reviews-scraper`), collect each review's text, date,
   business ID and source URL. Record the fetch date and anything you could
   not access.
3. Save `businesses.csv` and `reviews.csv` with stable `business_id` and
   `review_id` fields. Keep the original review text. Never invent missing rows.
4. Report how much you collected, any gaps, and any tool access you still
   need. Do not rank winners yet.

If no scraping tool is connected, say so and ask the user to connect one or
supply exported CSVs. Do not fabricate reviews.

## Phase 2 — Tag, calculate, make awards

1. Using `businesses.csv` and `reviews.csv`, tag every review for explicit
   mentions of each award category. Keep the evidence quote and row ID next
   to each tag. Tag only on explicit wording ("right at your appointment
   time" = yes for speed; "left my skin glowing" = no).
2. Mark uncertain rows as `unknown`. Check a sample by hand and fix
   inconsistent tags before calculating.
3. Count matching reviews per business **in code, not by hand**, over the same
   date window. Show totals and shares. A business needs at least 30 usable
   reviews to be ranked; list the ones below that as unranked.
4. Name winners only within the sample you collected. Report ties,
   exclusions and source links. Make no claims about what caused the results.
5. For each winner, create a bold vertical (9:16) award card in the user's
   branding. Each card shows:
   - the business name and city
   - "Local Legends [year]"
   - the headline stat (e.g. "34 reviews mentioned speed of service")
   - a short punchy title (e.g. "RIGHT ON TIME.")
   - a small "Based on public reviews" footnote
6. Draft a short, friendly outreach message to each winner that attaches
   their card and suggests they share it on their story. Leave the drafts
   for the user's review. **Do not send anything.**

## Output checklist

- `businesses.csv`, `reviews.csv`, `tags.csv` (review_id, category, tag, evidence quote)
- A results table per category: business, matching count, usable reviews, share, rank
- One award card per winner
- One outreach draft per winner, unsent

## Guardrails

- Every number on a card must trace back to tagged rows in `tags.csv`.
- No citywide or "best in town" claims beyond the collected sample.
- Do not use business photos you lack the rights to; use the user's own
  assets or neutral design elements.
- Do not send messages or post anything without explicit approval.
