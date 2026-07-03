---
name: new-strategy
description: Scaffold a new trading strategy from the template. Creates strategies/<name>/ with a SPEC.md and guides the user through filling it in via the strategy-designer agent. Use when the user says "new strategy", "add a strategy", or brings a fresh trading idea.
---

# New strategy scaffold

Given a strategy name (kebab-case) and a one-line idea:

1. Refuse to proceed if `strategies/<name>/` already exists — suggest a different name.
2. Copy `strategies/_template/` to `strategies/<name>/`.
3. Fill in the SPEC.md header: name, date (absolute), one-line idea, status `draft`.
4. Launch the `strategy-designer` agent with the user's idea to draft the full spec.
   Relay its open questions back to the user — the spec is not done until every
   section is concrete and the user has approved it.
5. Set spec status to `approved` only after explicit user approval.
6. Remind the user: per CLAUDE.md, no implementation happens before the spec is approved,
   and success criteria are locked once backtesting starts.

Do not write any strategy code as part of this skill.
