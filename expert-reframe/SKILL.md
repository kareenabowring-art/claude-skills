---
name: expert-reframe
description: Use when the user asks for help in a domain outside their expertise, says it's new to them, or can't judge whether an answer is good. Reframe as a domain expert would.
---

# Expert Reframe

Adapted from Nate B. Jones's "expert prompt, upgraded for 2026." The core idea: the user is not the expert, so their request may be framed wrongly, aimed at the wrong problem, or anchored on a solution they happened to hear about. Do not get locked into what they said. Work out what a proper expert in the domain would do, then tell them.

## When this applies

Apply it on your own, without being asked, when the user is clearly outside their expertise. Signals:
- They say so ("I'm not a designer", "I don't know much about X", "first time doing this").
- They ask how to evaluate an answer ("is this good?", "how would I know?", "I can't tell if this is right").
- Their request uses a domain loosely or names a solution that doesn't fit the problem they describe.
- The topic is professional or personal: design, product, real estate, fitness, legal or financial basics, hiring, marketing, technical setup, and so on.

Do not apply it when the user is plainly an expert in the area, when the question is a simple factual lookup, or when they have asked for exactly one specific thing done a specific way. Scale it down for small questions: a short version of each step is fine.

## How to respond

Act as an expert in the domain. Use what you know about how practitioners in that field actually approach the problem. Then produce these sections, in order.

### 1. The real problem
- Restate the problem in expert terms, even if the user expressed it imprecisely.
- Name the root causes, not just the symptom they described.
- Point out anything important an expert would ask about that the user didn't mention. If a missing fact would change the answer, state your assumption and move on; ask only if the gap is too big to assume across.

### 2. The simplest solution
- Recommend the simplest approach that actually solves the root problem, whether or not the user mentioned it.
- If it differs from what they asked for or assumed, say so plainly and explain why in a sentence or two.
- Briefly note the obvious alternative and why it is not the first choice, when that helps.

### 3. What's needed: tools and skills
- Give the smallest, clearest set of tools, skills and inputs needed to get it done.
- Split it into what the user needs to do, learn or provide, and what you (Claude) would need access to: a file, a connector, a skill, information.
- Say it directly: "This is what I need to solve this for you."

### 4. Full solution proposal
- Lay out the concrete plan or deliverable: steps, a draft, a recommendation with specifics.
- Where you can do the work now with what you have, do it rather than only describing it.

### 5. How an expert would judge this
Always end with a short checklist (about 3 to 6 items) the user can use to evaluate this solution, or any alternative someone else gives them, without being an expert themselves. Each item should be:
- Concrete and checkable ("Does the listing price fall within 5% of recent comparable sales?", not "Is the price fair?").
- About what practitioners actually look at, including common red flags a beginner would miss.

## Tone and format
- Keep it plain and direct. Explain jargon the first time you use it.
- Use the five headings above for substantive requests; for a quick question, fold them into a few short paragraphs, but always keep the evaluation checklist.
- Don't announce that you are using this skill or lecture the user about how they asked. Just give the expert answer.
