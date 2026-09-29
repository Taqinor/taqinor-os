---
name: memory-shared-via-repo
description: Durable taqinor-os memory is mirrored in the repo (docs/claude-memory/, imported by CLAUDE.md) so other machines/accounts get it
metadata:
  type: feedback
---

Since 2026-09-30 the founder wants Claude memory available on his other computer and other Claude account. Durable project facts are versioned in taqinor-os `docs/claude-memory/` (index imported from CLAUDE.md with `@docs/claude-memory/MEMORY.md`).

**Why:** local memory under ~/.claude is per machine; git is the only channel shared by all his machines and accounts.

**How to apply:** when saving a durable taqinor-os fact (founder decision, standing approval, open incident), write it BOTH here and in docs/claude-memory/ (via a PR, never secrets). Machine-specific notes stay local only. Related: [[couv-hor-donut-incident]].
