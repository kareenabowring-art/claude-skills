---
name: llm-council
description: Pressure-test a decision, plan or idea with a council of 5 independent advisors, anonymous peer review and a Chairman's final verdict. Use when the user says 'council this', or wants honest, non-sycophantic advice.
---

# LLM Council

A single assistant tends to agree with whoever is asking. The council counters that: five advisors with deliberately different lenses answer independently, critique each other blind, and a Chairman makes the final call.

## When to use
- The user says "council", "council this", "run the council", or asks for brutally honest / non-sycophantic feedback.
- A real decision with tradeoffs: a business move, launch, hire, pricing, strategy, career choice, or a plan or draft they want stress-tested.
- Skip it for simple factual questions; just answer those.

## Step 0: Frame the question
Restate the decision in 1–2 sentences, plus the key context (goals, constraints, budget, timeline, what has already been tried). If something critical is missing and the user is present, ask at most 2 quick questions; otherwise state your assumptions and proceed. Do not reveal what answer the user seems to hope for to the advisors.

## Step 1: Five advisors answer independently
Each advisor sees only the framed question, never each other's answers. When subagents are available, run all five in parallel (one subagent each) so they truly can't influence one another. Otherwise write each one in turn, fully committing to that role.

1. **The Contrarian**: "What will break?" Assumes the plan fails and finds the fatal flaws, hidden risks, weak assumptions and failure modes. No softening.
2. **The First Principles Thinker**: "What's actually true?" Strips away assumptions and conventions, rebuilds the problem from fundamentals, and questions whether this is even the right problem.
3. **The Expansionist**: "What's the upside?" Looks for the bigger opportunity, the asymmetric bet, the 10x version, and what's being left on the table by thinking too small.
4. **The Outsider**: "Why do you do it that way?" Has no industry background. Asks naive questions, borrows from other fields, and calls out jargon and "that's just how it's done" thinking.
5. **The Executor**: "What do you do Monday morning?" Turns it into concrete next steps: first actions, owners, sequence, cost, and the fastest cheap test.

Each advisor gives: a verdict in one line, their reasoning (about 150–250 words), and the single thing they'd most want the user to hear. Advisors must not hedge or agree just to be agreeable.

## Step 2: Anonymous peer review
Shuffle the five answers and relabel them Response A–E so no one knows who wrote which. Each advisor (again in parallel if possible) reviews the anonymized set and gives:
- Which response is strongest, and why
- The biggest blind spot across all responses
- What everyone missed

Keep the A–E to advisor mapping for the Chairman.

## Step 3: The Chairman's final call
The Chairman reads everything (the original answers, the mapping, and the peer reviews) and delivers:

- **Verdict**: a clear decision or recommendation. Not "it depends".
- **Where the council agreed**: points of consensus (high confidence).
- **Where it clashed**: the real disagreements and how the Chairman resolved each one.
- **Blind spots caught**: what peer review surfaced.
- **Biggest risk + mitigation**
- **Next 3 actions**: concrete and doable this week.
- **Confidence**: low / medium / high, plus what would change the call.

The Chairman may disagree with the user's preferred option. Honesty beats agreeableness.

## Output to the user
Lead with the Chairman's verdict and next actions. Then give a short section with one line per advisor (their verdict and key point), then the peer-review highlights. Offer the full advisor transcripts if they want them, rather than dumping everything by default. If the user wants it kept or shared, save the full council report as a document.
