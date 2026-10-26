# Codex model routing

Current project routing after the user's 2026-10-26 decision to stop using
Nemotron. All project coordination, implementation and review use Codex through
Orca, with distinct worker contexts for implementation and independent review.

| Role / work | Model | Effort |
| --- | --- | --- |
| Coordinator: queue, evidence and workflow | `gpt-6.1-sol` | medium |
| Bounded, repetitive implementation or mechanical checks | `gpt-6-luna` | medium |
| Cross-module implementation from an approved design | `gpt-6.1-sol` | medium |
| Routine independent R1 review | `gpt-6.1-sol` | medium |
| R2/R3 review, architecture or difficult authorized diagnosis | `gpt-6-astra` | high |

Use explicit `--agent codex --model <id> --effort <level>` at every worker
launch. Verify both requested and effective launch settings and actual provider
metadata. Do not silently inherit an `ultra` effort setting. Keep one active
writer per TASK and use a separate context for its reviewer.

Budgets, risk classes, retries and evidence follow
`autonomous-development/references/routing-and-budget.md` and
`autonomous-development/references/review-policy.md`. Counts and input usage
belong to the logical TASK and never reset on retry, model change or new Run.
Record real rollout usage, including cached input; do not equate subscription
window usage with one TASK's token cost. On provider exhaustion, stop the
dependent chain pending an explicit user decision.

Do not use Nemotron for this project. Do not change global model settings,
accounts or plans; do not reset or purchase credits.
