// Prospect tag detector. Paste into the browser's JavaScript console/tool on the prospect's page.
// Returns a JSON summary of ad, retargeting, analytics, affiliate, email and consent tags.
// Run before accepting the cookie banner, then after accepting and reloading, on home, product and cart pages.
(() => {
  const SIGS = [
    // [vendor, category, regex on hostname+path]
    ["Google Ads / remarketing", "retargeting", /googleadservices\.com|googleads\.g\.doubleclick\.net|google\.com\/pagead|google\.com\.au\/pagead/],
    ["Google DV360 / Floodlight", "retargeting", /fls\.doubleclick\.net|ad\.doubleclick\.net|\.g\.doubleclick\.net/],
    ["Google Tag Manager", "tag-manager", /googletagmanager\.com\/gtm\.js/],
    ["Google tag (gtag)", "tag-manager", /googletagmanager\.com\/gtag\/js/],
    ["Google Analytics", "analytics", /google-analytics\.com|analytics\.google\.com|\/g\/collect/],
    ["Meta Pixel", "retargeting", /connect\.facebook\.net|facebook\.com\/tr/],
    ["TikTok Pixel", "retargeting", /analytics\.tiktok\.com/],
    ["Pinterest Tag", "retargeting", /s\.pinimg\.com\/ct|ct\.pinterest\.com/],
    ["Snap Pixel", "retargeting", /sc-static\.net|tr\.snapchat\.com/],
    ["Microsoft Ads (UET)", "retargeting", /bat\.bing\.com/],
    ["LinkedIn Insight", "retargeting", /snap\.licdn\.com|px\.ads\.linkedin\.com/],
    ["Reddit Pixel", "retargeting", /redditstatic\.com\/ads|alb\.reddit\.com/],
    ["Criteo", "retargeting-specialist", /criteo\.(net|com)/],
    ["RTB House", "retargeting-specialist", /creativecdn\.com|rtbhouse/],
    ["AdRoll", "retargeting-specialist", /adroll\.com/],
    ["StackAdapt", "retargeting-specialist", /stackadapt\.com/],
    ["The Trade Desk", "dsp", /adsrvr\.org/],
    ["Amazon DSP", "dsp", /amazon-adsystem\.com/],
    ["Yahoo DSP", "dsp", /s\.yimg\.com\/wi|ads\.yahoo\.com|yahoo\.com\/sync/],
    ["Xandr / Microsoft Invest", "dsp", /adnxs\.com/],
    ["Adform", "dsp", /adform\.net/],
    ["Quantcast", "dsp", /quantserve\.com|quantcount\.com/],
    ["Taboola", "native", /taboola\.com/],
    ["Outbrain", "native", /outbrain\.com/],
    ["Commission Factory", "affiliate", /cfjump\.com|commissionfactory/],
    ["Partnerize", "affiliate", /prf\.hn|partnerize/],
    ["Impact", "affiliate", /impactradius|impact\.com|ojrq\.net/],
    ["Awin", "affiliate", /dwin1\.com|awin1\.com/],
    ["Rakuten Advertising", "affiliate", /linksynergy\.com/],
    ["CJ", "affiliate", /emjcd\.com|cj\.com/],
    ["Klaviyo", "email-sms", /klaviyo\.com/],
    ["Omnisend", "email-sms", /omnisend|omnisrc/],
    ["Attentive", "email-sms", /attentivemobile|attn\.tv/],
    ["Mailchimp", "email-sms", /chimpstatic\.com|list-manage\.com/],
    ["Braze", "email-sms", /braze\.com|appboycdn/],
    ["Salesforce Marketing Cloud", "email-sms", /igodigital\.com|exacttarget|marketingcloudapps/],
    ["Dotdigital", "email-sms", /dotdigital|trackedlink\.net|r1-t\.trackedlink/],
    ["OneTrust", "consent", /cookielaw\.org|onetrust/],
    ["Cookiebot", "consent", /cookiebot\.com/],
    ["Usercentrics", "consent", /usercentrics\.eu/],
    ["Didomi", "consent", /didomi\.io/],
    ["Shopify", "platform", /cdn\.shopify\.com|shopify\.com\/shopifycloud/],
    ["Salesforce Commerce Cloud", "platform", /demandware\.(net|static)/],
    ["BigCommerce", "platform", /bigcommerce\.com/],
    ["Hotjar", "analytics", /hotjar\.com/],
    ["Microsoft Clarity", "analytics", /clarity\.ms/],
    ["Segment", "analytics", /segment\.(com|io)/],
    ["Tealium", "tag-manager", /tiqcdn\.com|tealium/],
    ["Adobe Launch / Analytics", "tag-manager", /adobedtm\.com|omtrdc\.net|2o7\.net/],
  ];
  const GLOBALS = {
    fbq: "Meta Pixel", ttq: "TikTok Pixel", pintrk: "Pinterest Tag", snaptr: "Snap Pixel", uetq: "Microsoft Ads (UET)",
    criteo_q: "Criteo", adroll_adv_id: "AdRoll", __adroll: "AdRoll", rtbhEvents: "RTB House", saq: "StackAdapt",
    ttd_dom_ready: "The Trade Desk", _tfa: "Taboola", obApi: "Outbrain", klaviyo: "Klaviyo", _learnq: "Klaviyo",
    OneTrust: "OneTrust", Cookiebot: "Cookiebot", UC_UI: "Usercentrics", Didomi: "Didomi", Shopify: "Shopify",
    gtag: "Google tag (gtag)", google_tag_manager: "Google Tag Manager", utag: "Tealium", _satellite: "Adobe Launch / Analytics",
  };
  const urls = new Set();
  try { performance.getEntriesByType("resource").forEach(e => urls.add(e.name)); } catch (e) {}
  document.querySelectorAll("script[src],img[src],iframe[src],link[href]").forEach(el => urls.add(el.src || el.href));
  const inline = Array.from(document.scripts).filter(s => !s.src).map(s => s.textContent).join("\n").slice(0, 2_000_000);

  const found = {};
  const add = (vendor, category, evidence) => {
    found[vendor] = found[vendor] || { category, evidence: new Set() };
    if (found[vendor].evidence.size < 3) found[vendor].evidence.add(evidence);
  };
  urls.forEach(u => {
    let key;
    try { const p = new URL(u, location.href); key = p.hostname + p.pathname; } catch (e) { return; }
    for (const [v, c, re] of SIGS) if (re.test(key)) add(v, c, key.slice(0, 120));
  });
  for (const [g, v] of Object.entries(GLOBALS)) {
    try { if (typeof window[g] !== "undefined") add(v, (SIGS.find(s => s[0] === v) || [, "other"])[1], "window." + g); } catch (e) {}
  }

  const blob = inline + "\n" + Array.from(urls).join("\n");
  const ids = {
    google_ads: [...new Set((blob.match(/AW-\d{6,12}/g) || []))],
    ga4: [...new Set((blob.match(/G-[A-Z0-9]{6,12}/g) || []))],
    gtm: [...new Set((blob.match(/GTM-[A-Z0-9]{4,10}/g) || []))],
    meta_pixel: [...new Set((blob.match(/fbq\(\s*['"]init['"]\s*,\s*['"](\d{10,20})/g) || []).map(m => m.match(/(\d{10,20})/)[1]))],
  };

  let dlEvents = [];
  try {
    dlEvents = [...new Set((window.dataLayer || []).map(x => (x && (x.event || (x[0] === "event" && x[1]))) || null).filter(Boolean))].slice(0, 40);
  } catch (e) {}

  // Server-side tagging hints: GTM/gtag served from the site's own domain or a first-party subdomain
  // Registrable domain, e.g. shop.brand.com.au -> brand.com.au ; www.brand.com -> brand.com
  const labels = location.hostname.split(".");
  const twoPartTld = /^(com|net|org|edu|gov|asn|id|co)$/.test(labels[labels.length - 2] || "") && (labels[labels.length - 1] || "").length === 2;
  const base = labels.slice(twoPartTld ? -3 : -2).join(".");
  const knownThirdParty = /googletagmanager\.com|google-analytics\.com|doubleclick\.net|googleadservices\.com/;
  const serverSide = Array.from(urls).filter(u => {
    try {
      const p = new URL(u, location.href);
      return p.hostname.endsWith(base) && !knownThirdParty.test(p.hostname) &&
        /gtm\.js|gtag\/js|\/g\/collect|\/collect\b|sgtm|^ss\.|^sst\.|^metrics\.|^data\.|^tag\.|^tags\./i.test(p.hostname + p.pathname);
    } catch (e) { return false; }
  }).slice(0, 5);

  const ld = Array.from(document.querySelectorAll('script[type="application/ld+json"]')).map(s => s.textContent);
  const productSchema = ld.some(t => /"@type"\s*:\s*"Product"/i.test(t));
  const offerSchema = ld.some(t => /"offers"|"price"/i.test(t));

  const cats = {};
  for (const [v, o] of Object.entries(found)) (cats[o.category] = cats[o.category] || []).push(v);
  const summary = {
    page: location.href,
    checked_at: new Date().toISOString(),
    by_category: cats,
    retargeting_specialists: cats["retargeting-specialist"] || [],
    ids,
    dataLayer_events: dlEvents,
    server_side_tagging_hints: serverSide,
    product_schema: productSchema,
    price_in_schema: offerSchema,
    evidence: Object.fromEntries(Object.entries(found).map(([v, o]) => [v, [...o.evidence]])),
    notes: [
      "Absence of a vendor is weak evidence: tags may load later, only after consent, only on some pages, or server-side.",
      "Run on home (before and after consent), product and cart pages.",
    ],
  };
  return JSON.stringify(summary, null, 2);
})();
