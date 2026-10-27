---
name: online-exposure-audit
description: Use when the user wants their own online presence scanned for security vulnerabilities, data-breach exposure, impersonation risk or exploitable flaws, and a ranked list of fixes to make themselves safer.
---

# Online Exposure Audit

Adapted from Nate B. Jones's "the prompt that scans you for vulnerabilities." The core idea: ask an AI to look at your online presence the way an attacker would, check it against established hacks and current zero-day vulnerabilities, and hand back a list of weak spots ranked by severity, with fixes.

This is a self-audit. Run it only on the user themselves, or on a business or person the user is responsible for and has permission to assess (their own company, a family member who asked). Do not use it to build a profile of someone else.

## 1. Collect the scope

Ask for what you need in one message, then start. Don't ask for anything you can find yourself.
- The name they go by publicly, and roughly where they're based (city or region, not an address).
- Usernames or profile links to cover (LinkedIn, Instagram, X, TikTok, Facebook, GitHub, personal site, etc.).
- Email addresses to include: work, personal, or both.
- Any domains they own or run (business website, company email domain).
- Optional: the main apps, devices and services they rely on (phone and laptop OS, browser, password manager, email provider, bank, work tools, smart-home devices, router). This is what makes the zero-day check specific.

Never ask for passwords, security answers, one-time codes, or account numbers, and tell the user not to share them.

## 2. Map the public footprint

Use web search. Look at what an attacker could find in an afternoon:
- Search results for their name with their location, employer and usernames.
- Each profile: what it reveals (employer, role, colleagues, city, travel, kids, pets, birthday, school, home or office photos, routine).
- Username reuse: the same handle across sites makes it easy to link accounts together.
- People-search and data-broker listings that show home address, phone, relatives or age.
- Old or forgotten accounts, posts, CVs, conference bios, and cached pages.
- Email and phone number exposure: where they're posted publicly.

Note what pieces combine into something useful to an attacker: answers to common security questions, enough detail for a convincing phishing email, or enough to impersonate them to a bank, phone carrier or colleague.

## 3. Check breach exposure

- Search for known data breaches at the services, employers and sites the user uses or has used.
- For each email, give the user exact steps to check it themselves on Have I Been Pwned (haveibeenpwned.com) and, if they have one, their password manager's breach monitor. You usually can't query these for them.
- Flag breaches that leaked passwords, password hashes, phone numbers or security answers as more serious than ones that leaked only email addresses.

## 4. Check domains (if they own any)

- Email spoofing protection: whether SPF, DKIM and DMARC are set, and whether DMARC is enforcing (`p=quarantine` or `p=reject`) or only monitoring (`p=none`). Look these up with DNS lookup tools or public DNS checkers.
- WHOIS privacy: whether personal details show up in the domain record.
- Website basics: HTTPS, an outdated CMS or plugins with known vulnerabilities, exposed admin pages, public files that shouldn't be.
- Look-alike domains that could be used to impersonate them.

## 5. Check current vulnerabilities in what they use

For each app, device and service they listed, search for:
- Actively exploited vulnerabilities and zero-days disclosed recently (check CISA's Known Exploited Vulnerabilities catalog, vendor security advisories and reputable security news).
- Whether a patch exists, and which version fixes it.
- Ongoing scams or phishing campaigns aimed at users of that service.

Use the current date in searches. Only report vulnerabilities that apply to the products and versions the user actually has; say so when you're assuming a version.

## 6. Report

Lead with a short summary: overall exposure (low / moderate / high) and the top three things to do today.

Then a list ranked by severity, most serious first. For each item:
- **Severity**: Critical, High, Medium or Low.
- **What we found**: the specific exposure, with a link to where it was found.
- **Why it matters**: the realistic attack it enables, in one or two plain sentences.
- **Fix**: concrete steps, with the setting or page to go to.

Rank by how likely an attacker is to use it and how much damage it would do. Typical ordering: passwords exposed in a breach or reused, no two-factor authentication on email or banking, unpatched actively exploited flaws, phone number exposure that enables SIM-swap, home address on data-broker sites, email spoofing on their domain, oversharing that answers security questions, then general hygiene.

End with standing habits: password manager with unique passwords, app-based or hardware-key two-factor (not SMS) on email, banking and phone carrier, a carrier account PIN, automatic updates, data-broker opt-outs, and re-running this audit every few months.

## Rules

- Report what you found, with sources. Don't guess at exposures you couldn't confirm; list them as "worth checking yourself" instead.
- Keep the findings private to the user. Don't publish or share the report anywhere unless they ask.
- Don't attempt to log in, test passwords, probe systems, or exploit anything. This is a review of public information and known vulnerabilities only.
