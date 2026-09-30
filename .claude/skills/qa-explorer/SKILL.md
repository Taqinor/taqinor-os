---
name: qa-explorer
description: >-
  Nightly "human tester" fleet for TAQINOR OS (QAH1). One sonnet explorer
  sub-agent per kept MVP module (crm, visites, calepinage, ventes, stock,
  chantiers, sav, ged, portail, parametres), each with a PERSONA and a plain-French
  MISSION, drives the LOCAL demo ERP (docker stack seeded by seed_demo, login
  demo_admin — or, with `dataset: anon`, an anonymised copy of production loaded
  by import_anonymise, login anon_admin) through Playwright MCP, while HARD
  ORACLES judge — any 4xx/5xx, console.error / pageerror / unhandled rejection,
  empty list right after a create, failing /proposal PDF, prix_achat visible,
  audit_coherence violations — and the LLM only judges
  ambiguous screens against an explicit per-module grid. Every candidate is
  replayed once in an independent Chrome DevTools MCP browser before it is
  filed as an ERR-QAH-<MODULE>-<SLUG> line in docs/ERROR_PLAN.md (error-autopilot
  format, deduped), then a docs-only self-merge. Never against production.
  Honour the kill switch in docs/qa-explorer.config.yml. Launched each night by
  scripts/nightly-qa.ps1 (docs/nightly-qa.md) or by hand: "run the qa-explorer skill".
---

# QA-Explorer — the agent explores, the oracles judge

You are running the qa-explorer. Your job is **not** to fix code. Your job is to
**use the demo ERP the way a real user would, module by module, catch every
real defect a user would hit, prove each one twice, and file it** as a correction
item in `docs/ERROR_PLAN.md`. Landing the fixes is done later by
`work on error plan`.

**The governing fact (research L2, 27/09/2026 — `docs/PLAN.md` GROUPE QAH):** an
LLM agent **explores well and judges badly**. GUI Testing Arena: the best model
≈16 % execution success, ≈14 % defect recall; GUITester: 49 % F1 with two named
failure modes — *goal-oriented masking* (the agent routes around the bug to
finish its mission) and *execution-bias attribution* (it blames a real bug on its
own click); Anthropic's long-running-harness write-up: Claude declared broken
features "done" until it had a browser tool AND an explicit order to verify, and
it does not see native `alert`/`confirm`. So in this skill the **hard oracles
(STEP 2) carry the verdict**, the agent carries the exploration, and the LLM
judges only against the explicit grid of STEP 4 — never "does it look good?".

Treat this file as your runbook — it is self-contained because you run
unattended. Obey every `CLAUDE.md` non-negotiable rule always. You are the
ORCHESTRATOR: you keep the judgment (triage, replay, dedupe, filing, merge) and
delegate the exploration volume to explorer sub-agents that ALWAYS carry an
explicit `model:` (never inherited — founder rule).

---

## STEP 0 — Preflight, kill switch, locks (every pass, before anything else)

You may be launched headless by `scripts/nightly-qa.ps1` (`claude -p`, Claude
subscription, `--permission-mode dontAsk` + an allowlist — any command outside it
is DENIED, so use the Bash tool with plain `git` / `gh` / `docker` / `python` /
`curl` / `powershell` commands) or by hand in a session. Behave identically.

**Preconditions (safe abort, make no change if any fails):** you are inside a git
checkout of `taqinor/taqinor-os`; the checkout has no *unrelated* uncommitted
tracked changes (if it does, stop and report — never fold a human's in-progress
edits into the pass); `git` and the shell are usable. If one fails, print one line
saying why and end without writing anything.

1. Read `docs/qa-explorer.config.yml`. If it is missing → print
   `QA_EXPLORER: NOT CONFIGURED (docs/qa-explorer.config.yml missing)` and end.
2. **If `enabled: false` → STOP immediately.** No file change, no commit, no
   merge, no browser. Print exactly `QA_EXPLORER: DISABLED (config flag off)`
   and end.
3. Load the knobs: `base_url`, `modules`, `max_minutes`, `max_agents`,
   `cross_check`, `max_findings_per_run`, `dataset` (`demo` | `anon`, default
   `demo` when absent) and `anon_snapshot` (default
   `var/anon/latest.anon.json.gz`). Note the start time: the whole pass
   (explore + confirm + file) must end within `max_minutes`.
4. **Target guard.** `base_url` host must be `localhost` or `127.0.0.1`. Anything
   else → print `QA_EXPLORER: REFUSED (base_url is not the local stack)` and end.
   Never production, never the server, never a staging URL.
5. **Previous pass still running?** The pass marker is
   `logs/nightly-qa/qa-explorer.running` (`logs/` is gitignored). If it exists and
   its timestamp is younger than `max_minutes + 30` minutes → print
   `QA_EXPLORER: SKIPPED (a previous pass is still running since <ts>)` and end.
   If it is older, it is a crashed leftover: delete it, note it in the report,
   continue.
6. **Single-writer test-DB lock held?** `scripts/test-backend.ps1` refuses to start
   while a container named `erp-agentique-django_core-run*` is alive; this skill
   stops on the same signal (a test run means someone is working on this box):
   `docker ps --filter "name=erp-agentique-django_core-run" --format "{{.Names}}"`.
   Non-empty → print `QA_EXPLORER: SKIPPED (test-backend.ps1 single-writer lock held: <name>)`
   and end. Docker not reachable → `QA_EXPLORER: SKIPPED (docker not running)` and end.
7. Write the marker `logs/nightly-qa/qa-explorer.running` (UTC ISO timestamp + a
   run id `qah-<YYYYMMDD-HHMM>`). **Delete it on EVERY exit path** from here on
   (done, skipped, blocked, error).
8. **Stack health.** `GET <base_url>/` must answer 200 and
   `GET <base_url>/api/django/token/` must answer something below 500 (405/401/400
   = Django is up; 502/503/504 = it is not). Down → print
   `QA_EXPLORER: BLOCKED (local stack down — docker compose up -d, or let scripts/nightly-qa.ps1 do it)`
   and end. The skill does not build or migrate the stack; the nightly runner does.
9. **Demo data.** The demo company is `slug='taqinor-demo'`, created by
   `backend/django_core/authentication/management/commands/seed_demo.py`, which is
   idempotent (it skips when the company already has products). If it is empty,
   run `docker compose exec -T django_core python manage.py seed_demo` — **never
   with `--force`** (NE PAS FAIRE of GROUPE QAH; its ERR88 guard refuses outside
   `DEBUG`: if it refuses, STOP with `QA_EXPLORER: BLOCKED (seed_demo refused — DJANGO_DEBUG is not True in the local .env)`).
   **Second tenant (for the cross-company grid line):** if the company
   `taqinor-demo-full` does not exist, run
   `docker compose exec -T django_core python manage.py seed_demo_company` (idempotent,
   DEBUG-only, never `--force`). Then read — READ-ONLY, via
   `docker compose exec -T django_core python manage.py shell -c "..."` — three
   client names of `taqinor-demo-full`: they are the **foreign markers** every
   explorer must never see (STEP 2, oracle 9).
   **Anonymised dataset (`dataset: anon`).** The ACTIVE company is then
   `taqinor-anon` (with `demo` it is `taqinor-demo`); the demo seeding above
   still runs (the demo company stays the fallback). Then:
   - `anon_snapshot` missing → print `QA_EXPLORER: NOTE (dataset anon demandé mais instantané absent — repli sur demo)`,
     continue with `dataset: demo` and say so in the report.
   - Otherwise import it when it is NEWER than the last import OR the company
     `taqinor-anon` does not exist (read-only check via `manage.py shell -c`).
     "Last import" = the mtime recorded in `logs/nightly-qa/anon-last-import.txt`
     (gitignored); compare with
     `python -c "import os,sys; s=os.path.getmtime(sys.argv[1]); m=sys.argv[2]; print('IMPORT' if not os.path.exists(m) or s > float(open(m).read().strip() or 0) else 'FRESH')" <anon_snapshot> logs/nightly-qa/anon-last-import.txt`.
     Import = three commands, never anything else:
     `docker compose cp <anon_snapshot> django_core:/tmp/latest.anon.json.gz`,
     `docker compose exec -T django_core python manage.py import_anonymise --in /tmp/latest.anon.json.gz`,
     `docker compose exec -T django_core rm -f /tmp/latest.anon.json.gz`
     (always run the `rm`, even after a failure). The command is DEBUG-only and
     only ever wipes/reloads `taqinor-anon`. If it refuses → STOP with
     `QA_EXPLORER: BLOCKED (import_anonymise refused — DJANGO_DEBUG is not True in the local .env)`.
     On success write the snapshot's mtime into the marker:
     `python -c "import os,sys; open(sys.argv[2],'w').write(str(os.path.getmtime(sys.argv[1])))" <anon_snapshot> logs/nightly-qa/anon-last-import.txt`.
   - **Confidentiality.** The snapshot and everything read from `taqinor-anon`
     is CONFIDENTIAL (real amounts, real purchase prices, real études — only the
     identities are fake). Never copy the file anywhere else, never open it,
     never paste its content or absolute amounts read from it into a report, an
     ERR entry, a commit or a capture name. The skill NEVER runs
     `export_anonymise` and never touches the server.
10. **Credentials — never invent them, never print them.** With `dataset: demo`
    the explorer login is `demo_admin`; its password is the literal passed to
    `admin.set_password(...)` in `seed_demo.py` (the same pair is `ADMIN` in
    `frontend/e2e/helpers.js`). With `dataset: anon` it is `anon_admin`, password
    = the `ANON_PASSWORD` literal of
    `backend/django_core/authentication/management/commands/import_anonymise.py`.
    Read it from there and hand it to the explorers in their brief only. It must
    never appear in the report, in an ERR entry, in a capture file name or in a
    commit. There is no seeded client-portal account: see the `portail` mission.
11. Read `docs/ERROR_PLAN.md` (the dedupe base — every `ERR*` line, open, done or
    gated, plus the AUTOPILOT INTAKE LOG), `CLAUDE.md`, `docs/CODEMAP.md` §4 (to
    attribute `Files:`), and `STAGES.py` (the 6 French stage labels the CRM grid
    checks against).
12. **Browser tools.** Load the MCP tools (ToolSearch `+playwright`,
    `+chrome-devtools`). Playwright MCP (`mcp__playwright__*`) is mandatory: absent
    → print `QA_EXPLORER: BLOCKED (Playwright MCP not connected — approve it in /mcp, see docs/qa-explorer.md)`
    and end. Chrome DevTools MCP (`mcp__chrome-devtools__*`) absent → continue in
    DEGRADED mode (the STEP 1 replay uses a fresh Playwright session after
    `browser_close` instead of an independent Chrome) and say so in the report.
    Both servers are declared in `.mcp.json` with pinned versions.

---

## STEP 1 — The pipeline (explore → replay → cross-check → dedupe → file)

### Phase A — EXPLORE (one sonnet explorer per module)
For each key of `modules`, in order, dispatch ONE explorer with the `Agent` tool:
`model: "sonnet"` (explicit — never inherited), `run_in_background: false`, **no
worktree** (explorers never edit the repo; they only write capture files and
return a report). Run at most `max_agents` explorers at the same time — default
**1**, because every sub-agent of this session shares this session's ONE
Playwright MCP browser (one browser, one "current tab"): two explorers at once
would drive each other's page. Only raise it after adding isolated Playwright
slots (docs/qa-explorer.md, "Parallélisme") and giving each concurrent explorer
its own slot name.

Each explorer's brief is self-contained: its PERSONA and MISSION (STEP 4), the
entry routes, `base_url`, the login (STEP 0.10), the run id, the foreign markers
(STEP 0.9), the explorer rules (STEP 3), the hard-oracle checklist (STEP 2), its
module grid (STEP 4), its time budget (`max_minutes` × 0.6 / number of modules,
rounded down — the rest of the pass is replay + filing) and the return format
below. Paste this grounding block verbatim into every brief:

> Before reporting progress, audit each claim against a tool result from this
> session. Only report work you can point to evidence for; if something is not
> yet verified, say so explicitly. If tests fail, say so with the output.

**Explorer return format (short, structured — never page dumps):**
- `CANDIDATES` — one block each: `module`, proposed `SLUG`, one-line title,
  `oracle` (`hard:<n>` from STEP 2, or `grid:<line>` from STEP 4), URL, numbered
  repro steps **from the login screen**, expected vs observed, evidence (method +
  endpoint + status, the console text, the dialog text, the numbers read on
  screen), `retried_once: yes/no` + the retry's outcome, capture path, suspected
  severity.
- `CREATED` — every record created: object type (devis, lead, facture…), id
  read from the URL or the API response, reference, marker. Oracle 10 uses it
  to attribute coherence violations to this pass.
- `COVERAGE` — mission steps done / blocked (and by what), screens visited.
- `ENV NOTES` — third-party failures (map tiles, fonts, external APIs without
  keys), module not activated for the demo company (`/app-non-activee`), anything
  environmental. These are never filed.
- `COST` — tool calls made; tokens if your harness reports them.

### Phase B — REPLAY (orchestrator, sequential, independent browser)
The explorer's word is not enough (execution-bias attribution cuts both ways).
(Oracle 10 candidates are the exception: they come from the orchestrator's own
deterministic command and are replayed by re-running it — STEP 2, oracle 10.)
For each candidate, **after dedupe (Phase D) drops the known ones**, replay the
repro yourself in the **Chrome DevTools MCP** browser — a different, clean Chrome
with no shared state: open a new page, log in at `<base_url>/login`, follow the
numbered steps exactly, then read the failing request (`list_network_requests` /
`get_network_request`: status + response body), the console
(`list_console_messages`) and take the capture (`take_screenshot`, JPEG, saved to
the candidate's capture path). Tool names are those of chrome-devtools-mcp 1.x;
if `/mcp` lists different names, use the equivalent tool.
- The same hard signal reproduces → **CONFIRMED, confidence high**.
- A `grid:` candidate is confirmed only if the violated grid line is quoted with
  the numbers read on screen (e.g. `Total HT 10 000,00 + TVA 2 000,00 ≠ Total TTC 12 000,01`)
  and the replay reads the same numbers → **CONFIRMED, confidence high**.
- Not reproduced → **DROP** (listed in the report as `non reproduit`, with the
  explorer's evidence, for a human to look at if it recurs). Never file it.

### Phase C — CROSS-CHECK (optional, `cross_check: true`)
One fresh agent, `model: "opus"`, receives ONLY the evidence of every confirmed
`grid:` candidate (not the explorer's reasoning) and answers per candidate:
"is the quoted grid line objectively violated by the quoted numbers/text — yes/no,
one sentence why". A `no` → DROP. Hard-oracle candidates skip this phase.

### Phase D — DEDUPE (before replay, and again before filing)
Match every candidate against every `ERR*` line in `docs/ERROR_PLAN.md` (open,
`[x]` done, `[BLOCKED…]` gated) and the intake log, on **endpoint + symptom +
screen**. A known defect is dropped (`déjà connu: <ID>`). Two explorers reporting
the same root cause (same endpoint 500 from two screens) → ONE item, both repro
paths listed. With more than ~15 candidates, delegate the mechanical matching to
one `model: "haiku"` agent that returns `{candidate → matching ID | none}`; you
still decide.

### Budget & stop
Cap the pass at `max_findings_per_run` filed items (highest severity first; the
rest carry to the next night). Stop exploring when `max_minutes` × 0.6 is spent;
stop replaying when `max_minutes` × 0.9 is spent and file what is confirmed.

---

## STEP 2 — Hard oracles (NO LLM judgment — any hit is a candidate)

Scope: requests and pages of `base_url` (same origin). A third-party failure is
an ENV NOTE, never a finding.

1. **Server error** — any same-origin response ≥ 500 (`browser_network_requests`,
   filter `/api/`). Always a candidate.
2. **Client error on a legitimate action** — any same-origin 4xx after login,
   EXCEPT: the 401 of the session probe/refresh before login; a 404 on a URL the
   explorer typed on purpose to test it; a 400/422 on a form the explorer filled
   wrongly on purpose **and** whose message is shown under the faulty field
   (founder rule "erreurs → le champ fautif"). A 400 with no visible field error,
   or a 403/404 on a screen the admin reaches from the menu, IS a candidate.
3. **console.error / pageerror / unhandled rejection** —
   `browser_console_messages` with `level: "error"` and `all: true` (page errors
   and unhandled rejections surface there as errors in Chromium). Any same-origin
   entry is a candidate.
4. **Native dialogs** — `alert` / `confirm` / `prompt` never appear in the
   accessibility snapshot; they show up as a modal state that blocks the next
   action. After every click that can raise one (delete, leave a dirty form,
   accept, convert), check for it and resolve it with `browser_handle_dialog`,
   recording its exact text. A dialog carrying an error message, or a raw
   technical message (`[object Object]`, a stack trace, JSON), is a candidate.
5. **Empty list right after a create** — every record an explorer creates
   carries its unique marker (STEP 3.7); right after the create, open the list /
   board / search of that object and look for the marker. Absent → candidate.
6. **`/proposal` PDF fails** — for every devis the explorer creates or opens, read
   `GET <base_url>/api/django/ventes/devis/<id>/proposal/` from the logged-in page
   (`browser_evaluate` running `fetch(url, {credentials: 'include'})` and returning
   ONLY `{status, contentType, size, head}` where `head` is the first 5 bytes as
   text). Candidate if status ≠ 200, content type is not `application/pdf`, `head`
   is not `%PDF-`, or size < 10 000 bytes. **READ-ONLY**: `/proposal` is the only
   client quote-PDF path (CLAUDE.md rule #4) — never call, build or suggest any
   other PDF route to "work around" a failure.
7. **`prix_achat` visible in client-facing output** — the purchase price and the
   margin are GENERATOR-ONLY. Candidate (Critical) if a label `prix d'achat`,
   `prix_achat`, `coût d'achat` or `marge` appears in: the `/proposal` PDF text, a
   client-portal page (`/portail/client*`), a public token page (`/rdv/`, `/e/`,
   `/suivi/`, `/intervention/`, `/salle-vente/`), or a key `prix_achat` in a JSON
   body served to those pages. For the PDF text, the orchestrator downloads the
   PDF once per devis with `curl` (cookie login at `<base_url>/api/django/token/`)
   into `logs/nightly-qa/` (never committed) and extracts the text inside the
   Django container, which ships PyMuPDF:
   `docker compose exec -T django_core python -c "import sys,fitz; d=fitz.open(stream=sys.stdin.buffer.read(), filetype='pdf'); print(''.join(p.get_text() for p in d))" < logs/nightly-qa/<file>.pdf`.
   The internal quote generator's margin indicator is allowed — it is not client-facing.
8. **Broken screen** — the route error boundary ("Une erreur est survenue"), a
   blank main area, or a spinner / "Chargement…" still there after 30 s.
9. **Foreign data** — any of the foreign markers (the `taqinor-demo-full` client
   names, STEP 0.9) visible anywhere while logged in as the explorer account
   (`demo_admin` / `anon_admin`) → candidate, Critical (cross-tenant leak).
10. **Document coherence (deterministic, run by the ORCHESTRATOR, no browser, no
    LLM)** — right after the `ventes` explorer returns and right after the `crm`
    explorer returns, run
    `docker compose exec -T django_core python manage.py audit_coherence --company <active slug> --json --no-persist`
    (`taqinor-demo` or `taqinor-anon`, STEP 0.9). Its stdout is ONE JSON object
    `{"companies":[...], "checked":{...}, "violations":[{rule, severity, object_type, object_id, reference, company, message, values}], "new":[...], "rule_errors":[...], "duration_s": n}`.
    - Candidate = every violation whose (`object_type`, `object_id`) or
      `reference` is in an explorer's `CREATED` list or carries the pass marker
      (`QAH<YYYYMMDD>`) — and, with `dataset: anon`, EVERY violation (real-shaped
      documents computed by the current code are exactly what this oracle is
      for).
    - Replay (Phase B for this oracle) = re-run the same command; **CONFIRMED,
      confidence high** only if the same (`rule`, `object_type`, `object_id`)
      reappears. No browser replay is needed — the signal is deterministic.
    - Severity = the violation's `severity` (critical/high/medium/low → STEP 5
      levels; missing → High). `rule_errors` entries are ENV NOTES (an auditor
      rule crashed), never filed as product defects.
    - With `dataset: anon`, the ERR line quotes the rule, the object type, the
      reference and the GAP (e.g. `écart 0,01`, `28 % ≠ 37 %`) — never the
      absolute amounts of the snapshot (confidential). One ERR item per rule
      (all its objects listed by reference), not one per object.
    - **Command absent** (`manage.py help audit_coherence` → "Unknown command",
      or the run exits with that message) → skip oracle 10, write
      `oracle 10 ignoré : audit_coherence pas encore disponible` in the report.
      Never fail the pass for it. A non-zero exit WITH valid JSON on stdout is
      still read (violations may set the exit code).

---

## STEP 3 — Explorer rules (the research failure modes, as orders)

Put these in every explorer brief, verbatim in substance:

1. **Never route around a bug to finish the mission.** The moment an oracle fires,
   STOP that path, record the candidate with its evidence, then continue the
   mission from a fresh starting point if one exists. Finding a second way that
   "works" never cancels the first failure, and never write "mission accomplie"
   over a failure.
2. **Do not blame your own click — retry once.** When a step fails, take a fresh
   `browser_snapshot`, re-identify the target, redo the exact step once. Fails
   again → candidate with `retried_once: yes`. Succeeds on the retry → still a
   candidate if an oracle fired the first time (a 500 is a 500); otherwise note
   it under COVERAGE as "réussi au 2e essai" and move on.
3. **Native `alert` / `confirm` are invisible.** Check for a pending dialog after
   every click that can raise one and resolve it with `browser_handle_dialog`
   (dismiss destructive confirms unless the mission needs accept); record the text.
4. **No step is done without evidence.** After each mission step, verify the
   result ON SCREEN (the record is in the list, the status changed, the total
   updated) AND read the network + console for that step. "Done" = evidence.
5. **Read network and console BEFORE leaving a page.** `browser_network_requests`
   lists only the requests since the current page loaded; call it (filter
   `/api/`) before every navigation. Call `browser_console_messages`
   (`level: "error"`, `all: true`) at the end of each mission step.
6. **Judge only against your grid.** No opinion on colours, wording or layout
   unless a grid line says so. Ambiguous and not in the grid → COVERAGE note, not
   a candidate.
7. **Test data hygiene.** Every record you create carries the marker
   `QAH<YYYYMMDD>-<MODULE>-<n>` in its name / reference field / notes. Never
   delete or edit seed data you did not create (read it, use it as a parent).
   Never send an e-mail, WhatsApp or SMS to anyone, never click a link leaving
   `base_url`, never create or activate a Meta campaign, never run a scraper,
   never change a company-wide setting without restoring it in the same mission.
8. **Stay on `base_url`.** Never another host, never production.
9. **Mind the budget.** Stop cleanly when your time budget is spent and report
   what you covered; an unfinished mission is reported, never faked.
10. **Captures only for candidates.** `browser_take_screenshot` with
    `type: "jpeg"` and `filename:
    docs/qa-explorer/captures/<YYYY-MM-DD>/<MODULE>-<SLUG>.jpg` (the path is
    relative to the repo root). Crop nothing sensitive in: the login password is
    never on screen after login; if any secret is visible, do not capture.
11. **You are a user, not a code reviewer.** Do not read source code to decide
    whether a behaviour is "intended"; report what a user sees. The orchestrator
    attributes `Files:`.
12. **Log in through the UI** at `<base_url>/login` with the credentials of your
    brief. If you are redirected to `/app-non-activee`, the module is not
    activated for the demo company: ENV NOTE, stop that mission.

---

## STEP 4 — Missions, personas, entry routes, grids (one explorer per module)

Entry routes verified against `frontend/src/features/<x>/module.config.jsx` and
`frontend/src/router/index.jsx` on 28/09/2026. **Grid lines common to every
module:** (G1) a form never snaps or rejects a typed number (founder rule, ventes
and parametres); (G2) an error names the faulty field under the field; (G3) no
record of another company is ever visible (oracle 9); (G4) a list shows a record
created a second ago (oracle 5); (G5) a reference is unique — no two rows of the
same list share one.

| Module (key) | Persona | Entry routes | Mission (français courant) | Module grid |
|---|---|---|---|---|
| `crm` | commercial pressé, sur ordinateur | `/crm/cockpit`, `/crm/leads`, `/crm/leads/:id`, `/crm/relances` | « Crée un lead (nom avec ton marqueur, téléphone, ville), retrouve-le dans la liste puis dans le tableau, fais-le passer d'étape en étape, ajoute une note, planifie une relance, et vérifie chaque écran. » | Stage names shown = exactly the 6 French labels of `STAGES.py` (orchestrator passes them); the chatter logs each old→new change; the relance appears in `/crm/relances`. |
| `visites` | technicien sur mobile (`browser_resize` 390×844) | `/visites`, `/visites/planifier`, `/visites/toutes`, `/visites/:id` | « Planifie une visite technique pour ton lead ou un client démo, ouvre-la, remplis le relevé, enregistre, et vérifie qu'elle apparaît dans toutes les visites. » | Date/heure shown = date/heure entered; the visit is listed in `/visites/toutes`; usable at 390 px (no action hidden off-screen). |
| `calepinage` | technicien bureau d'études | `/calepinage`, `/calepinage/nouveau`, `/calepinage/:id/plan`, `/calepinage/:id/production` | « Crée une étude de calepinage, pose des panneaux, vérifie la puissance et la production, parcours les onglets principaux. » | kWc = nombre de panneaux × puissance unitaire (to the displayed precision); typed numbers never snapped (G1); map-tile failures are ENV NOTES. |
| `ventes` | comptable méfiante | `/ventes/devis/nouveau`, `/ventes/devis`, `/ventes/bons-commande`, `/ventes/factures`, `/ventes/avoirs` | « Prends un lead qui a ses factures d'électricité renseignées (facture hiver/été ; en jeu `anon`, choisis-en un parmi les leads existants ; en jeu `demo`, aucun n'en a : crée un lead avec ton marqueur et renseigne ses factures), crée un devis Résidentiel À PARTIR de ce lead (pas d'un client nu), vérifie que l'étude reprend ses factures, vérifie chaque total au centime, ouvre le PDF, accepte-le, convertis-le en bon de commande puis en facture, et vérifie chaque écran. » (The orchestrator then runs oracle 10.) | Sous-total HT → Remise → Total HT → TVA → Total TTC consistent **to the centime** on the form, the list, the BC and the facture (Total HT = Sous-total − Remise; TTC = HT + TVA); status chain brouillon → envoyé → accepté → BC → facture preserved 1:1 (no facture from a non-accepted devis through the UI); reference unique (G5); `/proposal` PDF OK (oracle 6) and free of `prix_achat` (oracle 7); the screen is 100 % TTC. |
| `stock` | magasinier | `/stock`, `/stock/mouvements`, `/stock/categories` | « Crée un produit avec ton marqueur et un prix, fais une entrée de stock puis une sortie, et vérifie la quantité restante et l'historique des mouvements. » | Resulting quantity = initial + entrée − sortie; both movements listed; an under-threshold product is flagged. |
| `chantiers` | chef de chantier sur mobile (390×844) | `/chantiers`, `/interventions`, `/planification`, `/ma-journee` | « Ouvre un chantier (depuis un devis accepté s'il en existe un), planifie une intervention, fais-la avancer d'état, et vérifie le planning et ta journée. » | State changes visible in the list and the detail; the planned intervention appears in `/planification` and `/ma-journee` on its date. |
| `sav` | technicien SAV | `/sav/cockpit`, `/sav`, `/equipements`, `/sav/contrats` | « Crée un ticket SAV pour un client démo, qualifie-le, fais-le avancer jusqu'à la clôture, et vérifie le cockpit. » | Status transitions shown in order; the ticket appears in the cockpit counts; closing requires what the wizard says it requires. |
| `ged` | assistante administrative | `/ged` | « Téléverse un petit document de test (un fichier texte que tu crées sous `logs/nightly-qa/`), classe-le et tague-le, retrouve-le par la recherche, mets-le à la corbeille puis restaure-le. » | The document is listed and found by search right after upload; the restore brings it back with its tags. |
| `portail` | client final, puis administrateur | `/portail/administration`; client side `/portail/client`, `/portail/client/devis`, `/portail/client/factures` | « Côté administration, ouvre l'administration du portail et vérifie qui a accès ; côté client, consulte tes devis et factures et ouvre un PDF. » No portal account is seeded and none may be invented: if the admin screen can create a portal test access on this LOCAL stack without sending anything outside, use it; otherwise cover the admin side + verify that `demo_admin` opening `/portail/client` is sent back to its own space, and report the client side as a coverage gap. | A client sees only his own devis/factures; `prix_achat` never visible (oracle 7); the portal PDF is the `/proposal` PDF (oracle 6). |
| `parametres` | administrateur prudent | `/parametres`, `/parametres/notifications`, `/parametres/messages-accueil`, `/parametres/historique-statut` | « Change un réglage anodin, enregistre, recharge la page, vérifie qu'il est conservé, puis remets la valeur d'origine. » | The value persists across a reload; the restore leaves it exactly as found; errors point at the field (G2). |

---

## STEP 5 — Severity & confidence

**Severity** (BUILD-QUEUE placement, same rubric as error-autopilot Appendix B):
- **Critical** — money miscalculation, cross-tenant visibility, `prix_achat` in a
  client output, data loss, a core workflow impossible (devis → facture blocked).
- **High** — 5xx on a core action, broken status chain, `/proposal` PDF failing,
  a record vanishing from its list after create.
- **Medium** — recoverable wrong behaviour, a 4xx without a field message, a
  console error with visible impact, a raw technical message shown to the user.
- **Low** — console error without visible impact, minor wrong display.

**Confidence** — file ONLY `high`: reproduced by the explorer AND by the
independent replay (Phase B) on an objective signal (a hard oracle, or a grid line
quoted with numbers), and — for `grid:` items when `cross_check: true` — agreed
by the cross-check. Anything else is DROPPED and listed in the report as "à
regarder par un humain". Never pad the backlog.

---

## STEP 6 — File the confirmed items

**Id**: `ERR-QAH-<MODULE>-<SLUG>` — `MODULE` ∈ `CRM VISITES CALEPINAGE VENTES
STOCK CHANTIERS SAV GED PORTAIL PARAMETRES`; `SLUG` = 2 to 5 UPPERCASE ASCII words
joined by `-` (no accents, e.g. `DEVIS-TTC-ARRONDI`). Unique across the file: if
taken, append `-2`. This shape matches `scripts/plan_lanes.py`'s task-id pattern.

**One physical line per item** (`plan_lanes.py` reads tags only on the first
line), inserted in `docs/ERROR_PLAN.md` under `## BUILD QUEUE` (replace the
`_(vide — …)_` placeholder line if it is still there), ordered Critical → Low:

```
- [ ] ERR-QAH-VENTES-DEVIS-TTC-ARRONDI — [ventes] <titre> : <symptôme / impact>. REPRO : 1) se connecter (demo_admin, stack locale seed_demo — ou anon_admin, jeu anonymisé import_anonymise) ; 2) … ; 3) …. ATTENDU : … ; OBSERVÉ : … (preuve : `POST /api/django/ventes/devis/ → 500`, console « … »). CAPTURE : `docs/qa-explorer/captures/<YYYY-MM-DD>/VENTES-DEVIS-TTC-ARRONDI.jpg`. SÉVÉRITÉ : High. CONFIANCE : high (oracle dur n°1, rejoué dans un navigateur indépendant). found via: qa-explorer <YYYY-MM-DD>, persona comptable méfiante. Files: <owning files from CODEMAP §4 — the endpoint's app views/serializers/services + the screen's `frontend/src/features/<x>/` file>. (ROUTINE, @model:sonnet)
```

- An item whose fix obviously needs a founder decision (new paid dependency,
  auth/cost policy, destructive migration, a CLAUDE.md non-negotiable) goes to
  `## GATED` with `[BLOCKED: <reason>]` instead.
- Append ONE dated line to the **AUTOPILOT INTAKE LOG** of `docs/ERROR_PLAN.md`:
  `- YYYY-MM-DD — qa-explorer : N constats vérifiés déposés (ERR-QAH-…, …) ; modules couverts : … ; M candidats écartés (non reproduits / déjà connus).`
- Append ONE row to the **Passes** table of `docs/qa-explorer.md` (date, modules
  covered, findings filed, dropped, cost). The FIRST real pass replaces the
  placeholder row even when it files nothing.
- A pass that confirms nothing (and is not the first real pass) files nothing and
  makes **no commit / no merge**; its report lives in the nightly log only.

---

## STEP 7 — CODEMAP fingerprint (same commit as the ERROR_PLAN edit)

`docs/ERROR_PLAN.md` is in the plan-fingerprint surface. In the SAME commit:
refresh §10 "Plan status" of `docs/CODEMAP.md` (paste
`PYTHONIOENCODING=utf-8 python scripts/codemap_fingerprint.py --print-plan-status`,
update the `Generated from commit` stamp), run
`python scripts/codemap_fingerprint.py --write`, then confirm
`python scripts/codemap_fingerprint.py --check` and `python scripts/check_stages.py`
are green. Note (verified 28/09/2026): the fingerprint's task regex counts ids of
the shape `[A-Z]+\d+`, so dashed ids like `ERR-QAH-…` (and the existing
`ERR-NTCON35-LEVER-RESERVE`) are not counted — `--write` may then be a no-op;
run the steps anyway and require `--check` green. You change no model, endpoint
or route, so the structure fingerprint does not move.

---

## STEP 8 — Land it (one docs-only self-merge to main)

Never commit in the checkout the nightly runs in (it must stay on a clean `main`
for the next night). File in a temporary worktree:

1. `git fetch origin` then
   `git worktree add .claude/worktrees/qa-explorer-<YYYYMMDD> -b dev-qa-<YYYYMMDD> origin/main`
   (`.claude/worktrees/` is gitignored). This is the pass's `dev` branch.
2. Apply the STEP 6 edits + the STEP 7 refresh there; copy the capture files of
   the FILED items from the main checkout's `docs/qa-explorer/captures/<date>/`
   into the worktree, then delete every capture of that date from the main
   checkout (untracked there). Captures of dropped candidates are not committed.
   **With `dataset: anon`, NO capture is committed** (screens show real amounts
   and purchase prices): the ERR line says `CAPTURE : locale seulement (jeu anonymisé)`
   and the captures are deleted from the main checkout at the end of the pass.
3. Commit once: `QA-explorer <YYYY-MM-DD> — N constats (ERR-QAH-…)`. The changed
   files must be ONLY `docs/ERROR_PLAN.md`, `docs/CODEMAP.md`,
   `docs/qa-explorer.md` and `docs/qa-explorer/captures/**` — anything else →
   stop, do not push.
4. Push the branch, open ONE PR to `main` (`gh pr create`; body = the pass
   summary, ending with the attribution line the session requires), wait with
   `powershell -File scripts/watch-ci.ps1 -Pr <n>` (docs-only → only the fast
   gates run, ~2 min), then `gh pr merge <n> --merge` (merge commit, never squash,
   never `--admin`). Red CI → do NOT merge: leave the PR open and report it.
   `main` moved / conflict → `git merge origin/main` into the branch (never
   rebase, never force-push), redo STEP 7, push, watch again.
5. After the merge: `git worktree remove` the temporary worktree and delete the
   local branch. **No deploy** (Deploys rule — the ERP auto-deploy fires by
   itself; a docs-only merge changes nothing it serves).

---

## STEP 9 — Report & status

Report once, in plain language (it lands in the nightly log): the dataset used
(`demo` / `anon`, imported this pass or already fresh, or fallback to demo) and
the oracle-10 outcome (violations seen / attributed / confirmed, or "ignoré");
the modules explored and how far each mission got; candidates found → replayed → confirmed →
filed → dropped (one-line reason tally: non reproduit / déjà connu /
cross-check / hors budget); the exact ids filed; ENV NOTES; the cost (tool calls
and tokens per explorer when known; the nightly log also holds the run's
`total_cost_usd` estimate from `--output-format json`). No diffs, no passwords.
Delete the pass marker. Then print, each on its own line:
- `QA_EXPLORER: DONE filed=<N> dropped=<M>` (or the STEP 0 status line that ended the pass)
- `ERROR_PLAN_STATUS: EMPTY` / `MORE` (from the `[ ]` count of `docs/ERROR_PLAN.md`)

---

## STANDING SAFETY RULES (always)

- Obey every `CLAUDE.md` non-negotiable: Odoo JSON-2 only; stage names from
  `STAGES.py`; Meta Ads campaigns born PAUSED (the explorer never creates one);
  **`/proposal` is the only client quote-PDF path — the explorer only READS it**;
  scraper policy (the explorer never scrapes).
- **Never against production** (`base_url` = local stack only). **Never
  `seed_demo --force`** (nor `seed_demo_company --force`).
- `prix_achat` / margins never appear in any output of this skill; seeing one in a
  client-facing output is a Critical finding, not something to copy.
- Credentials are read from the seed file, used in the browser only, never written
  anywhere.
- The anonymised snapshot (`var/anon/`, `*.anon.json.gz`) is CONFIDENTIAL: never
  committed, never copied outside the local docker stack, never opened or quoted;
  no absolute amount from `taqinor-anon` in any committed text or capture. The
  skill never runs `export_anonymise` and never touches the server.
- No outbound message to a real person (e-mail, WhatsApp, SMS), no Meta action,
  no external link followed.
- Never align a test or an oracle with the current behaviour to make it green;
  a divergence becomes an ERR item.
- The skill only writes `docs/ERROR_PLAN.md`, `docs/CODEMAP.md` §10 (+ plan
  fingerprint), `docs/qa-explorer.md` (Passes table), `docs/qa-explorer/captures/**`
  and its own marker/log files under `logs/`. It lands no code fix.
- Never weaken branch protection, never force-push, never overwrite another run's
  commits. Every sub-agent carries an explicit `model:`.
