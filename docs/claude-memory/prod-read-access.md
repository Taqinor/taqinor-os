---
name: prod-read-access
description: Reda granted standing approval to READ production (api.taqinor.ma / Hetzner) data for investigations
metadata:
  type: feedback
---

Reda (founder, taqinor-os) gave standing approval on 2026-09-29: Claude may always access and READ production data (SSH to root@178.105.192.116 with ~/.ssh/taqinor_hetzner, `docker exec` into the django container, read-only `manage.py shell` queries) when investigating a problem such as a wrong figure on a client quote.

**Why:** debugging quote PDFs needs the quote's real stored `etude_params`; the local DB has no production quotes, so without prod reads the investigation stalls.

**How to apply:** read-only queries only — never write, migrate, deploy or restart on prod through this approval (deploys stay governed by CLAUDE.md: Claude stops at the merge). Say in chat that you're reading prod.

**The key is per machine and never in git.** A machine without `~/.ssh/taqinor_hetzner` generates its own (`ssh-keygen -t ed25519 -f ~/.ssh/taqinor_hetzner`) and Reda adds its PUBLIC line to the server's `/root/.ssh/authorized_keys` from a machine that already has access. See [[setup-missing-tools]].
