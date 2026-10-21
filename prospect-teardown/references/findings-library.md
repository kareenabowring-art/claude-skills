# Findings library

Each finding: how to verify, why it costs them, how to phrase the opener. Phrase in plain words, specific to what you saw, one sentence. Never overstate.

## A. No dedicated retargeting (biggest opportunity)
- **Verify:** no retargeting specialist on home, product or cart pages after consent; no dynamic/catalogue ads in Meta Ad Library; Google Transparency shows search/Shopping only.
- **Why it matters:** most visitors leave without buying; nothing brings them back outside Google/Meta.
- **Opener:** "I went through [brand]'s site and product pages and couldn't find anything bringing cart abandoners back outside Google and Meta. For AU brands at your traffic level, that channel usually ends up at [proof point] of total sales."
- **Confidence:** medium if server-side tagging hints were found.

## B. Two or more retargeting vendors at once
- **Verify:** two specialists firing on the same page (e.g. Criteo + RTB House, or AdRoll + Criteo).
- **Why:** they bid against each other for the same visitor and both claim the same sale.
- **Opener:** "Your product pages are feeding two retargeting platforms at once, [A] and [B], so you're likely paying both to chase the same shoppers, and both are counting the same sales."

## C. Retargeting tags only on some pages
- **Verify:** vendor fires on home but not on product or cart pages; or no product/cart events in dataLayer.
- **Why:** without product views and add-to-carts, ads can't show the product someone looked at; audiences are just "visited the site".
- **Opener:** "Your [vendor] tag loads on the home page but not on product or cart pages, so it can't show people the products they actually looked at."

## D. Stale or mismatched creative
- **Verify:** Meta Ad Library / Google Transparency shows an ended promotion still running, wrong season, out-of-stock products, or prices different from the site today. Screenshot both.
- **Why:** wasted spend and broken trust at the moment of return.
- **Opener:** "Your catalogue ads on Meta are still showing [product] at [price], but it's [price/sold out] on the site today."

## E. Catalogue/dynamic ads missing
- **Verify:** Meta pixel present but no catalogue/carousel product ads in the Ad Library; only static brand creative.
- **Why:** static ads to past visitors convert worse than showing the exact products they viewed.
- **Opener:** "All [n] of your active Meta ads are brand creative; none show shoppers the products they viewed."

## F. Product pages missing structured data
- **Verify:** `product_schema: false` or no price in schema on product pages.
- **Why:** harder to build accurate product feeds for dynamic ads and Shopping; weaker rich results.
- **Use as:** supporting finding only; rarely a lead.

## G. Tags firing before consent
- **Verify:** banner shown, and marketing tags already loaded in the first run (before clicking anything).
- **Why:** reputational and regulatory risk is rising (Privacy Act reform); also a sign the data setup isn't controlled.
- **Opener (careful, as a question):** "Noticed your ad tags load before anyone answers the cookie banner. With the Privacy Act changes coming for targeted advertising, is that something your team is looking at?"
- Supporting finding only, unless the user wants to lead with compliance.

## H. Heavy affiliate/cashback overlap
- **Verify:** cashback/coupon affiliate tags plus retargeting, and brand terms crowded by affiliates in search.
- **Why:** multiple channels paid for the same returning customer.
- **Use as:** context for an incrementality conversation.

## I. Comparison / lead sites (price and product comparison sites)
- **Verify:** click-outs to partners or lead-form starts not tracked as dataLayer events; no retargeting of people who compared but didn't click out.
- **Opener:** "People who compare [category] on your site and leave without clicking through don't seem to be followed up anywhere, and that's usually the biggest pool of revenue a comparison site isn't earning from."

## J. Nothing wrong found
Say so. Use an observation opener tied to the offer, e.g. "You're already running [vendor]. We only get paid when someone clicks our ad and buys, so running us alongside for a month costs nothing unless it sells." Never invent a problem.

## Ranking
Lead with A, B, D or I when present (specific, verifiable, money). Use C, E as leads when strongly evidenced. F, G, H are supporting.
