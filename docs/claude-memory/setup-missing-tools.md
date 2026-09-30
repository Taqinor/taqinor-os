---
name: setup-missing-tools
description: Founder rule — when a tool or prerequisite is missing (docker, SSH key, node_modules, a CLI), set it up instead of reporting a blocker
metadata:
  type: feedback
---

When something a task needs is missing on the machine (Docker, an SSH key, `node_modules`, a CLI such as import-linter), Claude sets it up and carries on. It does not stop at "not available here" and hand the work back. Reda, 30/09/2026: « this is the behaviour you should have for the future installing docker and getting all what you need to do nice work ».

**Why:** on 30/09 a session on Reda's second PC reported "no docker, no SSH key → can't run the local tests / the prod check" and stopped. Reda wants the environment fixed, not the limitation reported.

**How to apply:** check prerequisites at the start of a task. Install from official sources (winget, `npm ci` from the lockfile, pip inside a venv). Generate per-machine SSH keys: never move a private key or any secret through git or chat, only public keys travel. Some steps physically need Reda (UAC prompt, BIOS virtualization switch, adding a public key on the server, reboot): do everything else first, then ask for exactly that one step. Related: [[prod-read-access]], [[memory-shared-via-repo]].
