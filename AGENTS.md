# Universal Orca development workflow

## Instructions to read

- Before designing, implementing or resuming a project, read
  `C:/Users/user/.agents/skills/autonomous-development/SKILL.md`.
- Before Orca commands, read
  `C:/Users/user/.agents/skills/orchestration/SKILL.md` and the installed
  version-matched Orca guide. Never guess commands.
- Before risk classification, dispatch or review, read
  `autonomous-development/references/routing-and-budget.md`.
- Before acceptance, FAIL corrections or a changed approach, read
  `autonomous-development/references/review-policy.md`.

## Roles and permissions

- The user approves requirements, architecture and the overall ROADMAP.
- Codex is the active Orca coordinator for this project. It owns the queue,
  frozen checklists, evidence and workflow records. Use separate Orca Codex
  workers for implementation and independent review as required by risk.
- Select a Codex model and effort for each role using
  `docs/workflow/MODEL-ROUTING.md`. Use lower-cost models for bounded routine
  work and reserve Astra for difficult or high-risk review.
- Nemotron and the abandoned TASK-WF-01 coordinator experiment are not part of
  the project workflow. Do not start or route project work to Nemotron.
- A routed PASS is required before advancing a TASK. Worker completion alone
  is not acceptance. Preserve failed attempts and actual token/call usage.
- The approved sequential ROADMAP authorizes its agreed TASKs unless the user
  narrows the scope. The latest user instruction controls any exception.
- Do not reset provider credits, buy credits, switch accounts/plans or recreate
  sessions to evade limits. Provider exhaustion blocks the dependent chain
  until the user explicitly decides to resume, even after an automatic reset.
- Work on `main` and preserve unrelated changes. Local commits are allowed
  after routed PASS. Push, merge and deployment require explicit user approval.
  Never delete important data without explicit approval.

## Project constraints

- Repository: `D:/Antigravity/EquipmentDocumentationRegistry`.
- Backend and tests run in WSL Ubuntu using `.venv/bin/python`; PostgreSQL 18
  must be online. Frontend runs in WSL using nvm Node.js v24.22.0.
- Do not alter or commit `.env`, `.venv/`, `storage/`, `node_modules/` or
  `dist/` unless a TASK explicitly requires it.
- Product code changes must stay inside the active TASK allowlist. Workflow
  records link actual checks and evidence; never fabricate results.
- Current progress and blockers are in `docs/workflow/STATE.md`; history is
  append-only in `docs/workflow/HISTORY.md`.

## Check commands

See the project verification table in `docs/PROJECT_STATUS.md` and the current
TASK evidence. Do not rerun checks already supported by complete evidence unless
the review policy permits it or the user requests it.
