# Prompt for the next session (written 24/11/2026, after the L5 of 23/11)

Paste everything between the two lines into a new session opened on `main`.

---

go L5 — finish the calepinage and quote work of 23/11, then test the whole thing as a user.

Read first, in this order: `docs/audits/l5-calepinage/etat.md` (block « POINT FINAL du 23/11 »),
`docs/audits/l5-calepinage/RAPPORT-FINAL-2026-11-23.md` section 11,
`docs/audits/l5-calepinage/controles/C4-un-seul-moteur.md` and `C4-consolidation.md`,
`docs/audits/decisions.yml` (D-ACAL-75 to 101), `docs/claude-memory/calepinage-decisions-fondateur.md`.

PART 1 — BUILD, in this order (one merge per step, contract first, stop at each merge: I deploy)

1. « One engine in the whole ERP » (my decision D-ACAL-97). Build the 55 tasks of the group « un seul moteur dans
   l'ERP (D-ACAL-97, 2026-11-23) » in `docs/plans/PLAN_AUDIT_DEVIS.md`, `PLAN_AUDIT_LEAD.md`,
   `PLAN_AUDIT_CALEPINAGE.md`, `PLAN_AUDIT_GENERATEUR.md`, `PLAN_AUDIT_DEPLOY.md` and `PLAN_AUDIT_TRANSVERSE.md`, in
   the nine steps of `C4-consolidation.md`. The rule: one engine calculates every number; its result is stored once
   (on the lead, or on the calepinage when there is no lead) and read everywhere; it is recalculated only when an
   input changes, and the screen says why; a quote already sent is never changed — a revision is proposed. A parity
   test before every switch. Before any switch that changes numbers, show me the list of quotes whose numbers would
   change (tasks ADEV154 and ADEV155) and wait for my answer.
2. The 15 leftover tasks of wave D: ACAL2030 to ACAL2038, ACAL2040, ACAL2041, ADEV156 to ADEV158, ADEP109.
3. The screens still far from the v2 mockups: Documents, Quick start, Tablet, Phone survey, Phone client view,
   Presentation, and the picture on the map (panel tint — ACAL1984, gold roof outline, strings drawn). Put each real
   screen beside its mockup, same size, before saying « built ».

PART 2 — FULL USER TEST (after part 1 is merged)

Where: on a COPY of production on this PC — the anonymised copy of my real data (`qa_import_anonymise`, login
`anon_admin`; see `docs/claude-memory/qa-coherence-auditor.md` and the `qa-explorer` skill). Never on production:
production stays read only. Never my real `.env` in the test stack.

Before testing, prefill everything so that every result is REAL and COMPLETE — no « incomplete » result, no
« price to fill », no empty setting:
- company settings: Calepinage → Settings → Quick start → « Fill the empty settings », weather mode and years, tariffs,
  consumption profiles, C&I flat rates;
- every product used by a scenario: price, and its technical sheet completed from the maker's public datasheet with
  the source written down (electrical values, power tolerance, NOCT, temperature coefficients, battery cycles, pump
  curves);
- the map key.
Give me the list of what you filled and where each value comes from. What you cannot source: say it, do not invent.

Who tests: fresh reviewers who built nothing, by clicks in a real browser (Chromium and WebKit; desktop 1440 × 900,
tablet, phone; light and dark), with the real roles (commercial, commercial responsable, technicien, admin), not only
admin.

Scenarios: each one is a test lead created the way a user creates it and followed to the end —
lead → automatic quote → quote edited by hand → PDF from `/proposal` in every format → sent → calepinage (roof,
panels, electrical, results, documents) → study report → revised quote V2 → accepted → chantier → invoice → SAV.
At least:
- Residential: (a) only a bill in dirhams, city typed « casa », no GPS; (b) kWh, summer different from winter, GPS,
  pitched roof with two faces, a chimney and a neighbour's shade; (c) with battery, both options shown; (d) flat roof
  with east-west frames.
- Commercial: (e) a shop with only a bill, a city and a category — everything else assumed and said; (f) everything
  declared (contract, phase, opening hours, hourly curve), ballasted flat roof, with and without battery.
- Industrial: (g) two shifts with no start hour and no declared voltage; (h) medium voltage declared.
- Agricultural: (i) new pump on a borehole, head and flow given; (j) existing pump kept; (k) phase unknown — the quote
  must stay blocked and say why.
- Edge cases: (l) typed kWh that contradict the bills; (m) city « maroc »; (n) quote sent, then the design changed in
  the calepinage → « Revise the quote »; (o) a calepinage with no lead; (p) ground field and carport; (q) phone survey
  done offline, then synced; (r) two users saving the same calepinage.

For every scenario check: each value shows ONE number, the same on every screen and in every PDF; every assumption is
said with the field to fill; nothing a client reads is invented; no purchase price anywhere; no 4xx or 5xx, no console
error; the journey never dead-ends.

Coverage: keep a table « screen × scenario × viewport ». No screen, button, option or setting of the calepinage module,
the quote generator, the quote tab of the lead card and the PDF dialog stays untested. Say plainly what was NOT covered.

Every defect: reproduce it, fix it (failing test first), have it replayed by a fresh reviewer. Loop until two rounds in
a row find nothing new.

At the end: one report in simple English — what works, what was fixed, what remains, what I must decide — and the
acceptance records under `docs/audits/acceptation/`.

Rules: stop at each merge (I deploy); one CI at a time; Auto-fix on every PR; decisions come to me as interactive
questions; nothing a client reads is decided without me; quality before quota.

---

Notes for Reda:
- « go L5 » is your call: it is the long campaign (several sessions, state kept in `etat.md`). Write « go L4 » for a
  shorter loop on the same contract.
- Part 1, step 1 alone is large (55 tasks). If you want to see the user test sooner, cut the prompt after step 2 and
  run part 2 on what is merged today; the « one engine » work then starts from a tested base.
- The four confirmations of 23/11 night are answered and recorded (D-ACAL-98 to 101); the new session has nothing to
  ask about them.
