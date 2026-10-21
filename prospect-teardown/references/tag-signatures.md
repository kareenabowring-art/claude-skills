# Tag signatures: what each vendor means for a retargeting pitch

`scripts/detect_tags.js` groups vendors into categories. How to read them:

## Dedicated retargeting specialists (direct competitors)
| Vendor | Hostnames / globals | What it means |
|---|---|---|
| Criteo | `*.criteo.net`, `*.criteo.com`, `criteo_q` | Incumbent dynamic product retargeting. Usually CPC/CPA billed on last-click or post-view attribution. Pitch: incrementality and pay-on-sales; ask how they measure Criteo's real contribution. |
| RTB House | `creativecdn.com`, `rtbhEvents` | Deep-learning retargeting competitor, similar pitch to Criteo. |
| AdRoll | `*.adroll.com`, `adroll_adv_id`, `__adroll` | Common with mid-size Shopify brands; self-serve. Often under-managed. |
| StackAdapt | `*.stackadapt.com`, `saq` | Programmatic, often run by an agency. |
| The Trade Desk / Amazon DSP / Yahoo DSP / Xandr / Adform / Quantcast | `adsrvr.org`, `amazon-adsystem.com`, `s.yimg.com/wi`, `adnxs.com`, `adform.net`, `quantserve.com` | Programmatic buying, usually via an agency; may include retargeting. Presence alone doesn't prove retargeting. |
| Taboola / Outbrain | `taboola.com`, `outbrain.com` | Native ads; pixels enable retargeting but are often used for prospecting. |

Two or more specialists firing on the same pages → likely bidding against themselves for the same visitors and double-counting conversions. Strong lead finding.

## Platform pixels (retargeting-capable, not specialists)
Google Ads remarketing (`googleadservices.com`, `googleads.g.doubleclick.net`, `AW-` IDs), Meta (`connect.facebook.net`, `fbq`), TikTok, Pinterest, Snap, Microsoft UET, LinkedIn, Reddit.
- These enable retargeting inside each platform, but the brand may only use them for conversion tracking.
- Google + Meta pixels but **no specialist** → "you're retargeting only inside walled gardens" opportunity; the agency covers the open web.
- Confirm actual retargeting by looking for dynamic/catalogue ads in the Meta Ad Library and display/remarketing-style ads in the Google Ads Transparency Center.

## Tag managers and server-side tagging
GTM (`gtm.js`, `GTM-` IDs), gtag, Tealium (`tiqcdn.com`, `utag`), Adobe Launch (`adobedtm.com`, `_satellite`).
- Tags behind a tag manager may load only after consent or specific triggers (e.g. product view). Check on every page type.
- First-party hostnames serving `gtm.js` / `gtag/js` / `/g/collect` (e.g. `sst.brand.com.au`, `metrics.brand.com.au`) → **server-side tagging**. Vendors may be invisible in the browser. Lower confidence in any "not found" claim; this is also a sign of a sophisticated team.

## Affiliate networks
Commission Factory (`cfjump.com`), Partnerize (`prf.hn`), Impact (`impactradius`, `ojrq.net`), Awin (`dwin1.com`), Rakuten (`linksynergy.com`), CJ (`emjcd.com`).
- Big affiliate programs (especially cashback and coupon sites) often claim the same returning customers retargeting would. Context, and a reason to talk about incrementality.

## Email / SMS
Klaviyo (`klaviyo.com`, `_learnq`), Omnisend, Attentive, Mailchimp, Braze, Salesforce Marketing Cloud, Dotdigital.
- Abandoned-cart email exists → retargeting should complement it (e.g. exclude people in the email flow for 24h, or target non-subscribers). Overlap is a finding only if you can show it.

## Consent platforms
OneTrust (`cookielaw.org`), Cookiebot, Usercentrics, Didomi.
- Australia has no GDPR-style cookie consent requirement today, but Privacy Act reforms in progress (the 2026 exposure draft proposed to bring targeted/behavioural advertising into direct-marketing rules). Frame consent observations as "worth getting ahead of", never as a breach.
- Tags firing before consent on a site that shows a consent banner → their banner may not be doing what they think. Mention carefully, as a question.

## Platform
Shopify (`cdn.shopify.com`, `Shopify`), Salesforce Commerce Cloud (`demandware`), BigCommerce. Helps plan feed and pixel integration effort.
