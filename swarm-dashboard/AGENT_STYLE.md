# Agent Style Guide (Yamai)

## Goal
Help the coding agent reliably translate how I describe work into concrete, safe, and shippable implementation steps.

## My Communication Pattern
- I usually describe desired outcomes before implementation details.
- I prefer direct, concise execution over long explanations.
- I often ask for cleanup, review, and practical fixes in the same flow.
- I expect the agent to proceed unless a decision is truly blocking.

## Interpretation Rules
- Convert broad requests into specific deliverables with file-level actions.
- If wording is ambiguous, choose the least destructive default and state assumptions briefly.
- Ask questions only when blocked; otherwise implement and verify.
- Prioritize visible user impact first, then technical debt cleanup.

## Phrase-to-Action Mapping
- "check the repository for redundant or missing files"
  - inventory files, detect artifacts, detect referenced-but-missing routes/files, propose cleanup list
- "add placeholders"
  - scaffold missing routes/pages with consistent layout and minimal stub copy
- "it just shows empty cards"
  - diagnose data flow first (source path, payload validity, loading/error states), then patch UI fallbacks
- "quick fix"
  - minimal patch, low regression risk, no broad refactor
- "properly"
  - include robust error handling, sane defaults, and validation steps
- "review my changes"
  - prioritize concrete defects (security/runtime/tooling regressions), not style nits

## Default Engineering Priorities
1. Correctness and runtime behavior
2. Security and input safety
3. Build/lint/test integrity
4. Maintainability and cleanup
5. Cosmetic polish

## Execution Contract (Per Task)
1. Restate interpreted intent in 3-6 bullets.
2. Apply code/file changes directly.
3. Validate with relevant checks (`build`, `lint`, targeted tests if present).
4. Report:
   - what changed
   - why it changed
   - what still remains or is blocked
5. End with short numbered next options only when useful.

## Safety Constraints
- Do not run destructive operations without explicit confirmation.
- Do not revert unrelated user changes.
- Avoid broad refactors unless explicitly requested.
- Keep edits localized and traceable.

## Preferred Output Style
- Concise, technical, no fluff.
- Action-first summary.
- Explicit file references for important changes.
- Clear statement when a check fails and why.

## Code Review Severity Policy (P0-P3)
- `P0` (drop everything)
  - Use only for universal, release-blocking failures (data loss, critical security exploit, complete outage, build cannot produce runnable artifact).
  - Must be reproducible without special assumptions.
- `P1` (urgent, next cycle)
  - Security exposure with realistic exploit path, major runtime breakage in core flows, or high-impact regression likely to affect normal users.
- `P2` (normal)
  - Correctness/tooling/maintainability issue that should be fixed but has workaround or limited blast radius.
- `P3` (low)
  - Nice-to-have robustness, minor inefficiency, or low-risk cleanup that does not meaningfully block delivery.

### Review Reporting Rules
- Report issues the author would likely fix immediately if aware.
- Prefer concrete, actionable defects over speculative risks.
- Include:
  - why it is a bug
  - when it happens
  - shortest precise file/line location
- Avoid:
  - style-only nits
  - broad architecture opinions without a direct defect
  - pre-existing issues unless explicitly requested

## Repo-Specific Notes
- This project uses Next.js App Router.
- Route placeholders are acceptable to prevent sidebar 404s.
- Telemetry/data-path issues should be resolved end-to-end (writer path + reader path + fallback UI).
- Keep an eye on local artifact files (`*.swp`, logs, local caches) and suggest cleanup when relevant.
