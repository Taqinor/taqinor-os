# LANE_BRIEF.md — lane-agent contract

Distilled contract for each parallel worktree lane-agent in a plan run, so
agents don't re-read the full PLAN.md preamble every run.

## Ownership

Own exactly ONE `apps/<x>`. Read other apps ONLY via their `selectors.py`
(reads) or `services.py` (writes/orchestration), or string-FK references —
never import another app's `models`/`views` directly.

## Commits

One commit per task, building on the last. Migrations chain within your own
worktree.

## Tests

Write tests per `docs/TEST_AUTHORING_CONTRACT.md` (unique refs via
`itertools.count()`/factories, pinned time, no threads in `TestCase`,
`setUpTestData` for shared fixtures, `@tag('slow')`/`@tag('pdf')` on slow/IO
tests, warm caches before query-count assertions, use `core/factories.py`).

## Checks — lightweight only

Run `flake8` and `python -m compileall` (static checks only). Do NOT spawn
docker test runs and do NOT build a test DB — the ORCHESTRATOR owns the
single-writer test DB; parallel docker runs corrupt it.

## Hands off

Never edit `docs/CODEMAP.md` or the plan fingerprint — the orchestrator
re-stamps both once at the end via `scripts/land.ps1`.

## Blockers

A true blocker → mark `[BLOCKED: reason]` and SKIP that task; keep the lane
going.

## Reporting

Report a short conclusion when done, not file dumps.
