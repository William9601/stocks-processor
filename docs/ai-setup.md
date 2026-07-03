# AI setup

How AI is wired into this repo, and what runs where.

## Claude Code (primary — all reasoning work)

`CLAUDE.md` is the operating manual every session loads. On top of it:

| Piece | Where | Job |
|---|---|---|
| strategy-designer | `.claude/agents/` | idea → rigorous SPEC.md; kills weak ideas early |
| quant-reviewer | `.claude/agents/` | hunts lookahead bias, overfitting, fake fills, risk gaps |
| backtest-analyst | `.claude/agents/` | interprets experiments/, compares strategies, issues verdicts |
| /new-strategy | `.claude/skills/` | scaffolds a strategy folder + drives spec creation |
| /compare-strategies | `.claude/skills/` | comparability-checked leaderboard from experiments/ |

The separation is deliberate: the agent that writes a strategy never grades its own
homework. Implementation happens in the main session; review and analysis go through
the specialized agents with fresh context.

Typical session commands:
- `/new-strategy vwap-reversion "fade extensions from VWAP on liquid large-caps"`
- "run the quant-reviewer on strategies/vwap-reversion"
- `/compare-strategies`

## Local models (optional, M5 / 48 GB)

Claude Code handles all design, coding, and review — a local model is **not** needed
for that and would be a downgrade. Where a local model earns its keep is high-volume,
low-stakes batch work where API costs would add up:

- bulk sentiment/relevance labeling of news headlines or filings for a data feature
- summarizing large log/backtest output during long unattended runs
- offline experimentation when rate limits or cost matter

Setup when the need actually arises (don't pre-install):
`brew install ollama`, then `ollama pull qwen3:32b` (~20 GB quantized — comfortable in
48 GB unified memory) or `qwen3:14b` for faster batch throughput. Expose to code via
Ollama's OpenAI-compatible endpoint at `http://localhost:11434/v1`.

Rule of thumb: reasoning about money → Claude. Labeling 50k headlines → local model.

## Guardrails that apply to every AI session

- AI never enables live trading; that is a human, per-session decision.
- AI-produced backtest conclusions are provisional until quant-reviewer has passed
  the underlying code.
- Secrets stay in `.env`; no AI writes credentials into tracked files.
