---
name: prospect-teardown
description: Qualify an Australian ecommerce or comparison-site prospect (80k+ visits/month) and tear down their live retargeting and ads setup to find the one specific problem to lead outreach with. Use for "teardown [brand]", "qualify these prospects", "audit [domain] for outreach", or before writing a cold email.
---

# Prospect teardown

The agency sells **retargeting** to Australian ecommerce brands and sites that sell or refer products online (comparison and referral sites count). It's paid on performance (a share of revenue or per result), so the client only pays for sales it drives. A teardown has one job: find **one specific, verifiable thing** about this prospect's setup that costs them sales, so the first line of outreach proves the agency has already looked. Generic praise or generic "we can help" is a failed teardown.

## Hard rules
- **Never name or hint at current clients** in anything written (teardowns, emails, decks). Describe proof as "AU apparel and footwear brands at your traffic level", never by brand. Proof points that are allowed are in `references/proof-points.md`.
- **Only state what you observed.** Every finding carries its evidence (URL, screenshot, tag hostname, ad library date). If you inferred something, say "suggests" or "likely". Never guess at a prospect's ROAS, spend or revenue as if it were fact.
- **Don't buy anything, submit real personal details, or sign up as the prospect's customer.** Adding to cart and browsing is fine; no checkout.
- **Privacy:** consent observations are framed as questions or opportunities, never as legal accusations. We're not lawyers.
- OpenSEO calls cost credits (~100–300 each). For batches over ~20 domains, say the estimated cost before running.

## Files
Get these from https://github.com/kareenabowring-art/claude-skills/tree/main/prospect-teardown if they aren't available locally (`git clone --depth 1 https://github.com/kareenabowring-art/claude-skills`). If that fails, the essentials are repeated in this file.
- `references/tag-signatures.md` maps tag hostnames and globals to vendors (Google, Meta, Criteo, RTB House, AdRoll, etc.).
- `references/findings-library.md` lists the problems worth leading with, how to verify each, and how to phrase them.
- `references/proof-points.md` lists approved, anonymised proof points and the pricing hook. Edit it as results change.
- `scripts/detect_tags.js` is a browser snippet: run it on the prospect's pages to list ad, retargeting, analytics, affiliate and consent tags.
- `scripts/teardown_template.md` is the output format.

## Workflow

### Mode: single prospect ("teardown X")
Run stages 1–6 below. Use a task list.

### Mode: batch ("qualify these", or a list of domains)
Run stage 1 for every domain first (cheap), produce the qualification table, then run stages 2–6 only for qualified prospects, best first. For more than ~10 full teardowns, ask how many to do now. Deliver the batch as a Sheets artifact (one row per prospect: domain, category, traffic estimate, qualified Y/N/borderline, retargeting vendors found, lead finding, confidence, status) so it doubles as the outreach tracker.

### 1. Qualify (5 min)
Check, in this order, and stop early on a clear "no":
- **Sells or refers online in Australia?** Ecommerce store shipping in AU, or a site that earns from online referrals/leads (comparison, marketplace, subscriptions). Not: local services, B2B-only, no online purchase or lead path.
- **Traffic ≥ 80k visits/month** (the product doesn't work below this). Use OpenSEO `get_domain_overview` (project with locationCode 2036, Australia). It returns **organic search traffic only**, so it's a floor, not total traffic. Total visits for AU ecommerce is typically ~2–3× organic (organic is usually 35–50% of visits; much lower for brands with heavy paid, email or direct traffic). Rule of thumb:
  - organic ≥ 40k → qualified
  - organic 15k–40k → borderline: look for other signals (large paid program in Ads Transparency, big social following, physical retail brand) and mark "borderline"
  - organic < 15k → not qualified unless strong evidence otherwise
  If the user gives better data (Similarweb, their own estimate), use that and say so. For a non-AU domain selling in AU (e.g. a .com), use AU-market data and note the domain may have traffic elsewhere.
- **A brand the agency would want** ("nice clients"): an established, reputable brand; no adult, gambling, payday lending, crypto-promo or obvious policy-risk categories unless the user says otherwise.
Output per prospect: verdict, the numbers, and why.

### 2. Map their tag stack
Open the site in a browser (use the preferred browser; read its skill first if one is listed). Visit, in order: home page → a category page → a product page (add one item to cart) → cart page. Don't check out.
- On the home page, **before** touching the cookie banner, run `scripts/detect_tags.js` (paste its contents into the browser's JavaScript tool). Note what fires before consent.
- Accept the banner (if any), reload, run it again on each page type.
- The snippet returns vendors found by hostname and by global variable, plus Google Ads IDs (AW-…), GA4 IDs (G-…), GTM containers, and Meta pixel IDs where readable.
If the script isn't available, run this in the browser instead and read the hostnames yourself: `[...new Set(performance.getEntriesByType('resource').map(e=>new URL(e.name).hostname))].sort().join('\n')`. Key hostnames: Criteo `criteo.net/.com`, RTB House `creativecdn.com`, AdRoll `adroll.com`, StackAdapt `stackadapt.com`, The Trade Desk `adsrvr.org`, Google Ads `googleadservices.com` / `googleads.g.doubleclick.net`, Meta `connect.facebook.net`, TikTok `analytics.tiktok.com`, Klaviyo `klaviyo.com`, Commission Factory `cfjump.com`, OneTrust `cookielaw.org`.

Read `references/tag-signatures.md` to interpret the result. Record:
- **Retargeting in place?** Which vendors (Criteo, RTB House, AdRoll, Google remarketing, Meta, TikTok, Pinterest, StackAdapt, The Trade Desk, Taboola/Outbrain, etc.).
- **Overlap**: two or more dedicated retargeting vendors usually means paying twice for the same visitors.
- **Gaps**: e.g. Meta pixel and Google tag present but no dedicated retargeting vendor; or tags firing on home but not on product/cart pages (no product-level events, so no dynamic product ads).
- **Server-side tagging** (first-party subdomain for GTM, like `sst.brand.com.au` or `/gtm/`): fewer visible tags. Note it and lower confidence on "no vendor found".
- **Affiliate networks** (Commission Factory, Partnerize, Impact, Awin) and **email/SMS** platforms (Klaviyo etc.): context for who else claims the same sales.

### 3. Look at their live ads
- **Google Ads Transparency Center** (adstransparency.google.com): search the brand or domain, region Australia. Note: approx. number of ads, formats (text, image, video, Shopping), last shown dates, whether any display/image creatives look like retargeting (dynamic product, "still thinking about it?").
- **Meta Ad Library** (facebook.com/ads/library, country Australia, all ads): number of active ads, formats, catalogue/dynamic ads (carousel of products with prices), oldest active ad date, stale promos (ended sale still running).
- Optional, if time: search 2–3 of their category terms on Google (AU) and note whether they appear in Shopping and paid results versus competitors.
Screenshot anything you'll cite. Note the date checked.

### 4. Walk the shopper journey
On the product and cart pages, check what a retargeting provider cares about:
- Product page has structured data (price, availability, image) and clean product URLs (needed for dynamic ads and feeds).
- Add-to-cart, view-content and purchase-intent events appear in `dataLayer` / pixel calls (the snippet reports dataLayer event names).
- Email capture / abandon-cart prompts (pop-up, exit intent).
- Out-of-stock handling, price consistency between ad creative and site.
For comparison/lead sites: the money step is the redirect or lead form. Check whether click-outs or form starts are tracked as events.

### 5. Pick the ONE finding
Go through `references/findings-library.md` and rank what you found by:
1. **Specific and verifiable** (they can check it in 30 seconds)
2. **Tied to lost sales or wasted money**
3. **Something the agency's retargeting fixes**
Pick one lead finding and up to two supporting findings. If nothing meaningful turned up, say so honestly and give the best "observation" opener (e.g. "you're running X with no dedicated retargeting partner; brands at your traffic level typically see 2–9% of total sales from it"), rather than inventing a problem.

### 6. Write the teardown
Use `scripts/teardown_template.md`. Keep it to one screen. It ends with:
- **Opening line** for outreach: one sentence, specific to them, in plain words (no jargon like "pixel stack").
- **Who to contact**: the role (Head of Ecommerce, Digital/Performance Marketing Manager, Head of Growth; for smaller brands the founder). Find names with Apollo or Lusha only if the user asks or an email is next; those cost credits.
- **Confidence**: high / medium / low, with why.
If the user wants an email, draft it from the opening line. If the user wants the teardown kept, save it as a doc; for batches, update the tracker sheet.

## Quality bar (check before sending)
- Could the prospect verify the lead finding in under a minute? If not, it's not the lead.
- Is every claim backed by evidence you captured today?
- No client names, no invented numbers about the prospect.
- Would the prospect learn something they likely don't know? "You use Google Ads" fails; "your Meta catalogue ads are still showing the September sale price" passes.
