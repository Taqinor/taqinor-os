# Lead handling v4 — how TAQINOR deals with every lead, the cold list and the dormant files

Design document, 1 November 2026. Second L3 pass, built on the audit of the same day ("Cadence de suivi clients — audit L3") and on three new production reads (read-only), one repo map, four research lanes, an independent capacity model, fresh verifiers and a final critic (section 10). Every production figure gives its n; external figures are tagged **[M]** measured (n, year), **[V]** vendor, **[O]** opinion. Nothing in this document has been built; nothing on production was written.

---

## 0. The short version

**The system in twelve lines.**

1. Every lead is always in exactly one of six states: **Live** (a cadence with an open step), **Standby** (reached, dated, with a reason, owner keeps it), **Nurture** (never reached or "not now" without a date: no human touches, trigger-based re-entry, one seasonal message a year), **Archive** (terminal reason: never contacted again, history kept), **Perdu** (a human decision with a motive), **Opposé** (legal opt-out, permanent). The six funnel stages of `STAGES.py` do not change; the states live in fields, tags and steps.
2. No lead is ever parked without a reason, and never in Standby without a date. The park dialogue asks for both; the cockpit shows what is overdue.
3. First touch: within 5 minutes in office hours, within 30 minutes of opening for night arrivals, and never more than 24 hours for a weekend arrival (today: 24 h median, 52 % reached against 69 % for office arrivals).
4. The contact protocol becomes **5 calls and 3 WhatsApps over 7 days** instead of 6 and 5 over 14: on our own data, 94 % of Meryem's first reaches happen inside 7 days and touches 5 to 11 produced one call-back in 25 executions.
5. The call is the reach channel (27-29 % of Meryem's calls reach someone, 2-3 % of her WhatsApps get a reply); calls go in the windows that answer on our own data (10-14 h; Tuesday to Thursday rather than Monday, which carries the weekend pile-up), the dead 17:30-18:30 and Sunday rungs disappear.
6. After the quote, the weight moves to days 1-7 (the J2 call reaches 50 %), the four dead WhatsApps go, J14 becomes a decision call, and one reasoned touch a month follows to J90. Quote validity goes to 30 days from the send, independent of the cadence, and the extension call comes two days before expiry, because an expired quote cannot be extended.
7. Wake-ups depend on history: a lead that was never reached and never quoted gets no more individual J30/J60 steps (157 such messages in production: 0 conversations; the one conversation among all 178 wake-ups came from a lead that had been reached and quoted); it goes to the seasonal list. A lead that was reached or quoted gets a human call at J30 and a message at J60. Whether a human call would do better than the messages on never-reached leads is untested here: a small pilot on those who declared a bill above 2,000 MAD will say whether any conversation happens at all.
8. The segment decides the path after the first conversation, not before it: "later" leads are quoted as often as "now" leads, so they get the same first day, then a dated Standby. C&I leads get a quote-prerequisite workflow (bills, second contact, 8-12 weeks), not a residential script.
9. The cold list (721), together with the 317 dormant, never-placed and lost files that sit in the live stages, is 1,038 leads in ten buckets with a different action each: 36 reached-and-quoted leads worth a personal call now; 262 pre-engine Meta leads worth one personalised message and a call for the responders; 519 Odoo-era contacts of which 423 are an archive to label and 96 are files Odoo had advanced; 158 junk, opposed or terminally lost files to clean out (89, 40 and 29).
10. The dormant files are repaired once (125 bounced leads back to Froid with a reason, 124 lost or archived leads out of the live stages, 66 never-placed leads sorted by their Odoo stage, about 160 wake-up steps cancelled: 147 on the 111 leads never reached and never quoted, some of them junk files, plus the dozen left on other junk files), then a nightly rule keeps it clean: no active lead without a next step or a dated park.
11. Capacity is the binding constraint: Meryem delivers about 124 touches a week and the current design asks for about 270 at full execution. v4 removes 3 touches per silent lead and about 20 wake-up touches a week, routes the residential flow through one queue with a duty rep (C&I leads keep their named owner), and sizes the reactivation batch each week from the measured slack, never as a quota.
12. We will not know it worked from an A/B test (a half/half test over 6 weeks can only detect a jump from 37 % to 62 % reach). We will know it from the weekly cohort line, pre-registered, read with control limits, plus two fast metrics: median time to first touch and on-time %.

**What it changes for the people.** Meryem keeps her discipline (92 % on time) and loses about 40 % of her low-yield touches; she gains a day template with two protected call blocks and a Monday that is no longer a weekend pile-up. Asmaa runs the same cadence under the same rules, visible on the same cockpit (her leads: 49 % reached, 0.7 touches per lead, and 28 "reached" calls logged on one Friday). Reda stops owning cadence leads (8 % on time) and becomes the escalation tier and the Monday reviewer.

**What it asks the founder to decide (section 9).** Ten decisions, each with a default. Three of them (the contact protocol, the cadence part of the post-quote change, and the segment path, CAD52) reopen decisions of 21/09/2026 that were explicitly conditioned on « mesurer d'abord (CAD87) »; this document is that measurement. The others reopen decisions taken on other grounds (CAD25, B2B7, VALID1, CAD74 Q20, CAD57) and say so; CAD124 (no segment axis in the gabarit) stays closed. An eleventh decision is legal rather than commercial: whether to message the 155 old Meta leads at all.

---

## 1. What the design rests on (the evidence, one line each)

| # | Fact (production unless tagged) | n | Consequence in v4 |
|---|---|---|---|
| 1 | Of the leads reached since 06/09, 48 % were first reached within 24 h, 59 % within 48 h, 78 % within 7 d; for Meryem's own leads 68 of 72 within 7 d | 109 reached of 180 | A 7-day contact protocol; the first 48 h carry the weight |
| 2 | Contact touches 5-11 (J1 evening to J14): 1 call-back in 25 recorded executions in October; no first reach after touch 6 through a step, ever | 25 / 179 leads | Touches 5-11 replaced by three touches over J2-J7 |
| 3 | Meryem's calls reach 27-29 % (55 of 190-208, depending on whether steps or chatter lines are counted), her WhatsApps 2-3 % (9 of 351-387); the identity WhatsApp step reaches 3 % on Meryem's leads (1/37) and 8 % for everyone but Asmaa (3/39) | October chatter and steps | Calls are the reach channel; WhatsApp announces, confirms and keeps the thread |
| 4 | Call reach by window: 10-12 h 29 % (59), 12-14 h 33 % (24), 14-16 h 18 % (40), 16-18 h 26 % with 59 % any response (27); Monday 18 % (60) vs Thursday 38 % (32); about 2 % of her touches at 18 h or later; 0 touches on Sunday in 12 weeks. (Randomised survey data, IPA 2020, finds no universal best hour and contact highest on Monday, so the weekday pattern is local, probably the weekend pile-up, and is re-measured monthly) | steps + chatter | Default call windows 10-14 h and 16-18 h, Tuesday-Thursday preferred; the 17:30-18:30 and Sunday rungs are removed because they are not executed |
| 5 | First touch within 24 h: 68 % reached, 26 % cold; 24-72 h: 54 % reached, 46 % cold; office arrivals 69 % reached (median first touch 0.2 h), night 60 % (9.7 h), weekend 52 % (24.1 h) | 180 leads | A 24-hour ceiling for every arrival, a weekend sweep, a 5-minute rule in office hours |
| 6 | Post-quote: J1 WhatsApp 17 % reach (29), J2 call 50 % (24 recorded in October; 21 % on all 84 executions, many with blank September outcomes), J4 WhatsApp 0 (24), J6 WhatsApp 0 (22), J7 call 23 % (22), J9 WhatsApp 7 % (29), J11 call 19 % (31), J13 WhatsApp 4 % (28), J14 WhatsApp 7 % (29); acceptances at 2, 6, 6, 6, 6 and 21 days from the first quote; 38 % of quoted leads never reached after the send | 90 quotes, 79 leads | Weight on J1-J7, J14 as a decision call, dead WhatsApps removed, a touch a month to J90 |
| 7 | About four quotes in five opened within a day (71-75 of 90, median 22-25 min), 10-14 never; 33 of the 79 quoted leads had no recorded reach before the quote (the WhatsApp exchange that produced it is not logged as a reach) | 90 | "Opened" is not a signal to wait for; the J2 call is; the logging rule of 7.5 |
| 8 | Expired quotes: 63-70 leads (by definition of "expired"), about half still touched after expiry, 7 reached, 3 re-quoted; validity 13-14 d on about 50 of them | 63-70 | Validity 30 days; expiry becomes a touch |
| 9 | Wake-ups: 178 done (J30 and J60, both stored as WhatsApp in production), 1 conversation, 4 reaches within 30 d, 6 quotes; 232 open steps on 164 leads, 147 of them on the 111 leads never reached and never quoted | 178 / 232 | No individual wake-up for never-reached, never-quoted leads; a human J30 call for reached or quoted ones |
| 10 | Standby answers (27 matured leads): 96 % touched again, 56 % reached again, 30 % quoted, 59 % cold, 0 signed within 30 d; call-backs are punctual (14 of 17 within a day) | 27 | Standby is worth keeping but needs a date, a reason and a ceiling on cycles |
| 11 | Timeline answers: "3 months" leads were reached 65 % of the time against 61 % for "immediate" and 57 % for 6 months or later, and were quoted as often | 61 / 43 / 42 leads | Same first day for everyone; the timeline sets the Standby date after the first conversation |
| 12 | Capacity: Meryem median 22.5 done steps a day (p25 16, p75 31, max 46), 124 touches a week, 7.5 h span, every weekday worked; demand 20-27 new leads a week | 30 days | Plan 25 touches a day; every touch removed from the design is worth 23 touches a week |
| 13 | Asmaa: 63 leads since 06/09, 49 % reached, median 306 h to first reach, 0.6-0.7 done steps per lead, 38 done steps in total of which 32 on a single day, 30 of 33 October calls logged "reached", 28 of them on 30/10 | 63 | One queue, one cockpit, one rule set for both reps; a park refused before the minimum attempts |
| 14 | Commercial: 74 leads, 9 % reached, 38 never touched, 3 quotes, 0 accepted; cockpit median 10.2 days to first quote | 74 | A quote-prerequisite workflow, not a rhythm change |
| 15 | Cold list: 670 of 721 never had an ERP touch; 519 are Odoo-era contacts with no ERP history; 36 reached-and-quoted leads, 33 of whom opened their quote online, 25 with quotes above 60k MAD | 721 | Ten buckets, ten actions (section 5) |
| 16 | Power: 37 % to 45 % reach needs 592 leads per arm; 60 per arm detects only 37 % to 62 % | arithmetic | No A/B; cohort line with control limits, pre-registered |

---

## 2. The lead model: six states on six stages

**The rule.** The funnel stages stay exactly the six of `STAGES.py` (Nouveau, Contacté, Devis envoyé, Relance, Signé, Froid). What changes is that each prospect (every lead that is not Signé; signed clients follow 4.8) also carries a **follow-up state**, derived from fields the ERP already has or will get (an open step, a park reason, a standby date, the archive flag, the lost flag, the opposition flag). Opposé overrides every other state. A prospect with nothing open, no Standby date and no park reason is in no state: that is a defect, and the nightly rule of section 6.2 flags it (68 such leads today). The state answers one question the stage cannot: *what will happen to this lead next, and when?*

| State | Stage(s) it lives on | What defines it | What happens next | Who |
|---|---|---|---|---|
| **Live** | Nouveau, Contacté, Devis envoyé, Relance | An open step in a contact, post-quote, visit or engine chain cadence | The next step, at its date and window | Owner |
| **Standby** | Relance (or Devis envoyé) | Reached; the client gave a reason and a horizon; `parc_jusqu_au` set; the step is moved to that date | Nothing until the date, except a client-initiated trigger; at the date the owner calls; cockpit line "Standby échu" | Owner |
| **Nurture** | Froid | Never reached after the full protocol ("injoignable"), or reached and "not now" without a date, or post-quote silence after J90; `parc_raison` set | No human touch; re-entry only on a trigger (reply, quote link opened, inbound call, season, tariff news); one seasonal message a year (June), with opt-out | Nobody (list) |
| **Archive** | Froid | Terminal reason: wrong number, duplicate, test, not owner, no roof, bought elsewhere, already equipped, out of zone, consumption too low, Odoo archive 2025-26, 12 months of silence | Never contacted again; history kept; excluded from every count of prospects | Nobody |
| **Perdu** | any (flag) | A human decision with a `motif_perte` | By motive: price and "reporté" are not terminal (they return as Nurture triggers); competitor, equipped, not owner are terminal | Owner, founder |
| **Opposé** | any (flag) | `ne_plus_contacter` | Never contacted, never exported, never in an audience; permanent | System |

**Reason codes at park time** (the `parc_raison` the park dialogue requires; the answer models of the journey table already carry most of them):

| Code | Meaning | Cooling period | Re-entry |
|---|---|---|---|
| `injoignable` | Full protocol, no human contact | none (Nurture) | reply, opened link, inbound call, seasonal message |
| `pas_maintenant_sans_date` | Reached, "later", no horizon given | 90 d | seasonal message, then Standby if the client answers |
| `plus_tard_date` | Reached, horizon given → this is **Standby**, not Froid | until the date | the owner's call at the date |
| `budget` / `trop_cher` | Reached, price or financing | 90-120 d | financing offer, price change, seasonal message |
| `concurrent` / `achete_ailleurs` | Signed elsewhere | 12-18 months (Archive unless a second system is plausible) | none |
| `non_proprietaire` / `pas_de_toit` / `technique` | Cannot buy | Archive | none |
| `faux_numero` / `doublon` / `test` | Junk | Archive | none |
| `archive_odoo` | Odoo-era contact with no ERP history, Odoo stage cold or lost | Archive (one seasonal pilot, section 5) | none, unless the pilot says otherwise |
| `opposition` | Opt-out | permanent | none |

Cooling periods are practitioner conventions **[O]** (timing 30-90 d, budget 90-120 d, competitor 120-180 d, no response 60-90 d, from the CRM-vendor material of the first audit); nothing measured exists, so they are defaults to tune on our own re-entry data.

**Three invariants the cockpit enforces nightly.**

1. No active lead (not Froid, not Signé, not lost, not archived, not opposed) without an open step or a `parc_jusqu_au` in the future. Today 68 of 265 active live leads have no open step.
2. No Froid lead without a `parc_raison`. Today none has one.
3. No lead parked "injoignable" with fewer than the protocol's five calls recorded, and no lead parked at all with zero touches. Today 25 of Asmaa's October leads went cold with no touch.

---

## 3. Intake and speed: the first 24 hours

**What the data says.** Since 06/09 the median delay to the first touch is 8-10 h depending on how the first touch is defined (p75 20-24 h); five leads waited more than 72 hours, the longest 27 days. Office arrivals are touched in 0.2 h and reached 69 %; weekday-night arrivals 9.7 h and 60 %; weekend arrivals 24.1 h and 52 %, with no weekend lead reached inside an hour. First touch inside 24 h: 68 % reached, 26 % cold today; 24-72 h: 54 % reached, 46 % cold. 71 % of Meta leads arrive outside Monday-Friday 9-18 h. The published data agrees on the direction (Oldroyd 2007 **[M, vendor-run]**: odds of contact fall 100× between 5 and 30 minutes; our own cells show the big drop after 24 h rather than after 5 minutes).

**Rules.**

| Arrival | First touch target | How |
|---|---|---|
| Monday-Friday 9-18 h | ≤ 5 min: identity WhatsApp, then the call | The duty rep is pushed the lead; 5-minute interrupt rule inside any block |
| Weekday 18 h-9 h | ≤ 30 min after opening (09:00-09:30 WhatsApp batch, calls from 09:30) | The 09:00 queue triage; WhatsApp first because the person asked at night |
| Friday 18 h to Sunday | ≤ 24 h: two 60-minute WhatsApp-first sweeps, Saturday 10:00 and Sunday 17:00; calls only if the lead proposes one | Rota, one weekend in two; Monday 09:00 starts with a clear first-touch list (the Friday-to-Monday window brings about 10 leads, 15 at the 95th percentile at 23 leads a week) |
| Any time | Automatic acknowledgement within seconds | **Decision 5**: needs the WhatsApp Business Platform (utility template); without it, the sweeps above are the whole answer |

**Routing between two reps (design, not measured evidence).** One shared queue "À prendre" for every new residential lead whatever the source and whoever the Meta form would have assigned (commercial and industrial leads keep going to the named pro owner, D-CIQ-20, and enter the C&I path of 4.6); a named duty rep per half-day (alternating; Meryem takes the half-days when Asmaa is on visits); escalation ladder T+5 min unclaimed → push to both, first to claim; T+15 → Reda alert; T+30 → auto-assign to the rep with the fewest untouched leads and log a breach. After the first touch the claimer owns the lead for the whole journey. Re-assignment only on rule: a declared absence of more than a working day (the ERP already records absences for the time rules; the owner's open steps then move to the duty rep for the absence and come back after it), a step overdue more than 24 h, or the owner's request. Reda's own leads and Imane's few (5 active today) enter the same queue and cockpit. Measured on the median time to first touch, never the mean.

**Why not simply give the whole flow to Meryem.** Her seat is saturated (section 7): 20 Meta leads at 5.9 executed touches each are 118 of her 124 weekly touches. v4 lowers the touches per lead, but the post-quote work and the Standby calls it adds mean the second seat is structural, not optional. The queue makes the second seat accountable on the same cockpit instead of a separate pile.

**Meta dayparting** (lifetime budget, ad schedule) can shift arrivals into office hours; it also cuts volume and the research lane will say what Meta allows for lead forms. It is an option next to the sweeps, not a replacement: the people who fill the form at 22:40 are real buyers.

---

## 4. The cadences

### 4.1 Contact protocol v4 (residential, all sources)

Keep: identity WhatsApp first (founder rule; it opens the thread and carries the opt-out), one call and one message per day as the ceiling (CAD20) with the J0 exception the current protocol already uses, Moroccan calendar rules (Ramadan window, declared absences, working days), the reactive engine (a reply ends the protocol and starts the next one). Change: the tail.

| # | Day | Window | Channel | Purpose | If unanswered |
|---|---|---|---|---|---|
| 1 | J0 | ≤ 5 min (office) / 09:00 batch / weekend sweep | WhatsApp | Identity, "votre demande de ce matin", one question, opt-out line | → 2 |
| 2 | J0 | +3 min | Call | Opening call: who, where, bill, when, who decides | → 3; if voicemail or busy, no message (the WhatsApp of #1 is the shadow) |
| 3 | J0 | +2 h 30 (the engine re-slots it to the company call window when it lands in the 12:30-14:00 break; "the other window" is the template preference of 7.4) | Call | Second attempt | → 4 |
| 4 | J1 | 10:30-12:00 | Call | Third attempt | → 5 |
| 5 | J2 | Call 16:00-17:00 (the window with 59 % "any response"); WhatsApp rung the same day at 17:45, born only if the call stays unanswered | Call, then WhatsApp: "je n'arrive pas à vous joindre, quel créneau vous convient ?" with two proposed slots | Fourth attempt, offers the client control of the slot | → 6 |
| 6 | J4 | 10-14 h (a Tuesday-Thursday day when the calendar allows: a day-template rule, not a gabarit field) | Call | Fifth and last call | → 7 |
| 7 | J7 | 12:00 | WhatsApp "je classe votre demande ?" with the opt-out line | Explicit closing question; a reply re-opens the protocol | → park `injoignable` → Nurture |
| — | J30 | — | nothing individual | | Seasonal list (June message) + triggers |

Every rung above is expressible in the existing gabarit data (day, hour, channel per rung; the engine only creates the next rung from the outcome of the previous one, so "if unanswered" is its default behaviour; a same-day second rung has its own hour; a true two-minute shadow exists only on J0 rungs). What is not gabarit data and lives in the day template of 7.4 instead: "the other window" for the second J0 call, the Tuesday-Thursday preference, and Monday mornings kept for weekend arrivals. Leads flagged `whatsapp_only` keep the existing channel swap (CAD32). One gap the texts have today: the opt-out sentence exists only on the closing and wake-up templates (`je_classe_j7`, `cloture_j14`, `j13`, `j14_pause`, `reveil_*`), not on the identity message nor on the post-quote J1; task 2.14 puts it on every outbound template, as section 5.2 requires. Five calls, three WhatsApps, seven days (v3: six calls, five WhatsApps, fourteen days). What goes: the J1 "WhatsApp de valeur" (0 reaches in 21), the J3 voice note (0 in 11), the J5 Sunday call (0 reaches, 1 refusal in 7, and Meryem has never worked a Sunday), the J10 call (0 in 3), the J14 closing message (0 in 7; the closing question moves to J7), and the 17:30-18:30 default that carries one call in nine. Calls go from six to five: the sixth call of v3 (J10) never reached anyone. What the evidence says about the risk: the September chatter shows 6 of Meryem's 42 chatter reaches later than day 7 (4 around days 14-17, one at day 90), so a 7-day protocol forgoes a thin tail; the seasonal message and the trigger re-entry are what replace it, at zero human cost. The founder's 21/09 argument that "a client who answers never suffers the whole protocol" is true and is exactly why the tail is cheap to cut: it only ever runs on silent leads.

**Decision 1** (reopens "ni le nombre, ni l'ordre, ni le jour J+N" of 21/09): adopt this table. Default: yes.

### 4.2 After the first conversation: three questions, then the path

The call script already exists (each field is its own question, `help_text` rule of the CAD group). v4 adds three mandatory answers at the first conversation, one tap each, because they are what the path branches on:

1. **Who decides** (`decideur`: alone / couple / family / company) → triggers the "Dimanche famille" touch and the second-contact rule (the call panel already asks it, `panneau_appel.py:54`, yet 0 of 1,132 leads carry an answer: the question is skipped or the answer is not written back).
2. **When** (`project_timeline` confirmed by voice, not the form) → sets the Standby date: now → quote within 24 h; 3 months → Standby call at J60; 6 months → J150; later → June seasonal list; "waiting for X" → `attend_accord` with the date.
3. **What would make you decide / what holds you back** (`declencheur` / `frein_principal`; the call panel asks them, `panneau_appel.py:696`, the lead form has no input for them, `fieldLabels.js:342` "pending", and 0 of 1,132 leads carry an answer) → chooses the post-quote content (financing, proof, warranty, bill season).

| Path after the first conversation | Who | Next |
|---|---|---|
| Residential now | Owner | Quote within 24 h (median today 0.9 d), post-quote cadence 4.3 |
| Residential later, with a date | Owner | Standby to the date (4.4); a short "voici ce que ça donnerait chez vous" one-page estimate is allowed, not the full proposal |
| Residential later, no date | Owner | Froid `pas_maintenant_sans_date` → seasonal list |
| Website / referral / walk-in | Owner | Same first day, then visit or quote at once: these leads reach 90 % and quote 5 of 8 |
| C&I | Owner + Reda | 4.6 |
| Agricultural | Reda | 4.7 |
| Not interested, reason given | Owner | Perdu with motive (terminal or not), never Froid |
| Opposition | System | Flag, every open step closed |

### 4.3 After the quote

| # | Day | Channel | Purpose | Note |
|---|---|---|---|---|
| 0 | J0 | WhatsApp with the proposal link | Delivery; the link logs the opening | 83 % open within a day (median 22 min): the open is not a signal to wait for |
| 1 | J1 | WhatsApp | "Avez-vous pu le parcourir ? Une question ?" | 17 % reach (29); keep |
| 2 | J2 | **Call** | The decisive conversation: walk through the figures, "qui décide ?", objections, propose the technical visit | 50 % reach (24): the best touch in the whole system |
| 3 | J3 | WhatsApp (conditional) | "Dimanche famille" only if `decideur` ≠ alone | kept, now actually triggered by 4.2 |
| 4 | J7 | Call | "Où en êtes-vous ?", answer the objection captured at J2, offer the visit again | 23 % reach, 32 % any response (22) |
| 5 | J10 | WhatsApp | One content touch chosen by `frein_principal`: financing simulation, nearby installation, warranty sheet, summer-bill projection | replaces the four fixed WhatsApps J4/J6/J9/J13 that reached 0, 0, 7 % and 4 % |
| 6 | J14 | **Call** | Decision call: accept / Standby with a date / extend validity to J30 / Perdu with motive | replaces the J14 "mise en pause" message (7 % reach); acceptances came at days 2-6 and 21, so J14 is a decision point, not an ending |
| 7 | J28 | Call | "La validité se termine dans deux jours : on prolonge, on révise, ou on classe ?" plus one new element | two days before expiry, because an extension is only possible while the quote is still « envoyé »; the 21-day acceptance lives here, and BEACN's most common request-to-installation time (3 months) starts here |
| 8 | J60 | WhatsApp | Season or price element | |
| 9 | J90 | Call or seasonal | Last reasoned touch; then Froid `pas_maintenant_sans_date` or Standby if a date emerged | |

Six touches in the first 14 days (v3: ten), then three in the next 76. Validity **30 days for every quote, set from the send date and decoupled from the cadence** (today the validity is the date of the last post-quote step, VALID1 of 07/09: with a J90 step that rule would silently give 90 days; CAD57 gave 30 days to financed files and 14 to the others; about 50 of the 63-70 expired quotes had 13-14 days; expiry today neither closes nor converts: about half of those leads are still touched, 3 re-quoted). The J28 call is the extension point, because the nightly job flips a quote to « expiré » after its date and nothing brings it back: an extension is possible only while the quote is still « envoyé » (the existing service `prolonger_validite_devis`); an expired quote means a revision, not an extension. A revision resets nothing in the cadence: the clock runs from the first send. After an acceptance the file is not done: no chain follows the accepted quote to the signed contract and the deposit today (none found in `ventes` or `crm`); task 2.16 adds a short one (confirmation J+2, deposit reminder J+7, escalation to Reda at J+14).

**Decision 3** (reopens CAD57 and the 21/09 "touche entre J14 et J30 / troisième vague" rejections): adopt. Default: yes.

### 4.4 Standby

Standby is the state for a reached client who gave a horizon. It already exists mechanically ("Plus tard", "À rappeler le", "Mettre en veille", "En attente d'un accord" move the same step to a date; 44 step events and 104 chatter events since September; "attente accord" has never been used). v4 makes it visible and bounded:

- A Standby always has a date, a reason and an owner; the step moved to the date is a **call**, not a message (the standby cohort: 56 % reached again within 30 days, 30 % quoted).
- The date comes from the client; defaults by timeline when the client is vague: J60 / J150 / next June.
- A lead may cycle through Standby twice; the third "later" goes to Froid `pas_maintenant_sans_date` with the seasonal list, unless the client names a date in the current quarter.
- Cockpit line "Standby échus" (date passed, no call done), judged in working days like every other step.
- While in Standby a client trigger (reply, opened link, inbound call) pulls the lead back to Live at once.

### 4.5 Nurture and wake-ups, by history

| History of the lead | Individual steps | List |
|---|---|---|
| Never reached, never quoted (`injoignable`) | none: the 125 J30 steps and 32 J60 steps run on this group produced 0 conversations | June seasonal message (one a year, opt-out line), trigger re-entry |
| Never reached, bill ≥ 2,000 MAD declared | one human **call** at J30 as a pilot **[O]**: the 125 J30 messages to never-reached leads produced 0 conversations and the call was never tried on them; the pilot is about 2-3 calls a week (about 30 a quarter), enough to see whether any conversation happens, not to measure a rate | same |
| Reached, no quote (rare: 1 lead today) | call at J30 | same |
| Reached and quoted, no decision after J90 | call at J30 after the park, message at J60, then seasonal | June + financing/price triggers |
| Perdu, non-terminal motive (price, reported) | none | June + price/financing news (today the seasonal job excludes every lost lead: task 2.8 opens it for non-terminal motives only) |

One fact to hold in mind: in production both wake-up steps were executed as WhatsApp messages (178 done, 1 conversation). The J30 call decided on 21/09 (CAD74 Q20) exists in the code defaults but the company's gabarit rows predate it and were never updated (section 8), so the human J30 call has never actually been tried here; in our data a call reaches about ten times more often than a message (29 % against 3 %).

Triggers that re-open a Nurture lead into Live, owner notified. Automatic: the proposal link opened again after 30 days (wired today only on the third reopening, task 2.7), and a new form submission by a phone already in the base (today a duplicate lead is created instead: 31 duplicate pairs, 12 of them Meta × Odoo; task 2.15). Manual, because WhatsApp is manual and no inbound-call webhook exists: a WhatsApp reply or an inbound call is recorded by the rep as an outcome on the parked lead, and that gesture re-opens it (task 2.15).

**Decision 2** (reopens CAD74 Q20 "J30 = call" for part of the population and removes the J60 for it): adopt. Default: yes.

### 4.6 Commercial and industrial

74 leads, 7 reached (9 %), 38 never touched, 3 quotes, 0 accepted, median 10 days to a first quote. The blocker is upstream of any rhythm: a C&I quote needs 12 months of bills, the tariff, sometimes a visit (D-CIQ: only for MT or unknowns), and a second contact (finance or facilities). v4 gives C&I its own **path**, not its own rung count (a segment variant all the same, so it reopens the 21/09 "no segment axis" decision, CAD52/CAD124, and the eliminated B2B7 for its longer tail: decision 10):

1. Same first day (identity message, calls), but the opening call is a discovery call with Reda or the owner: activity, operating hours, bill level, decision circuit, timing.
2. Within 24 h: a WhatsApp checklist "ce qu'il nous faut pour chiffrer" (12 months of bills or the annual statement, a photo of the meter and the roof, the contact of the person who signs). The post-contact engine chain already poses "devis demain / rappel convenu / décider la suite": the C&I variant poses "pièces reçues ?" at J3 and J7.
3. Quote within 5 working days of the documents; validity 30 days; the post-quote cadence of 4.3 with calls at J2, J7, J14, J30 and a **second contact** named at J2.
4. Standby by budget cycle (the client's financial year, a board date), up to 12 months, with a quarterly call, never Froid at J14.
5. No individual wake-up messages (27 done on commercial leads, 0 conversations); the quarterly call is the wake-up.

### 4.7 Agricultural (pumping)

Two leads in the base, both pre-engine. The path follows the agricultural decisions already taken (D-AGR, 02/10): declared volume first, visit before quote when the borehole is unknown, FDA prior-approval cycle. Cadence: first day as residential, then Standby at the dates the farmer gives (FDA file, campaign, harvest cash), recorded at the first conversation; the system invents no agricultural season (AGR512). Nothing to measure yet.

### 4.8 Signed clients

22 signed; the "deuxième affaire" cadence has run on one lead (both steps cancelled). v4: at commissioning + 30 days a satisfaction call that asks for one referral and records it as a lead with source "parrainage"; at + 12 months a message (battery, EV charger, second site); referrals enter the website/referral path (90 % reach, 5 quotes of 8 in the base).

---

## 5. The cold list: ten buckets, ten actions

### 5.1 The inventory (production, 1 November 2026, 1,132 leads)

The 721 Froid leads, the 124 lost/archived/opposed leads still in live stages, the 66 active leads never placed in a cadence and the 127 dormant mis-staged leads (1,038 in all) were each assigned to exactly one bucket, in this order of precedence:

| Bucket | Rule | Leads | of which Froid | Bill ≥ 1,000 / ≥ 2,000 MAD | "now" or "3 months" | Last human touch |
|---|---|---|---|---|---|---|
| K0 | Opposed (`ne_plus_contacter`) | 40 | 3 | 31 / 6 | 19 | 36 within 30 d |
| K1 | Junk: no valid Moroccan mobile (54), duplicate of a more advanced lead (35) | 89 | 49 | 53 / 21 | 12 | 56 never |
| K2 | Lost with a terminal motive (competitor, already equipped, not owner, out of zone, spam, invalid number…) | 29 | 4 | 24 / 6 | 17 | 28 touched |
| **K3** | **Reached and quoted, no decision** | **36** | 13 | 34 / 15 | 26 | 31 within 30 d |
| K4 | Reached, never quoted | 1 | 1 | — | 1 | ≤ 14 d |
| **K5** | **Never reached, Meta lead of the engine era (since 06/09)** | **33** | 26 | 30 / 15 | 22 | 28 within 30 d |
| **K6** | **Never reached, Meta lead before 06/09 (May-August)** | **262** | 193 | 214 / 47 | 75 | 187 never, 63 at 15-30 d |
| K7 | Never reached, website or walk-in | 28 | 9 | 26 / 9 | 0 | 10 never, 11 at 61-90 d |
| **K8** | **Odoo-era contact, no ERP history at all** | **519** | 423 | 0 / 0 in the ERP field (Odoo tags: 109 mentions ≥ 1,000 DH) | 0 | 519 never |
| K9 | Other (one Odoo import with a quote, never touched) | 1 | 0 | | | |

Every lead in K3-K9 has a valid-looking phone. K8 splits further by the Odoo stage the sync wrote into each lead's note: among the 423 Froid ones, "Cold Lead" 181, "Devis Cold" 120 (quoted in Odoo), "lost" 113 (22 tagged "Déjà fait l'installation"), "not convinced" 9; 170 carry the Odoo tag NRP (no answer). The 96 K8 leads that sit in live ERP stages were advanced in Odoo: "Quote Discussed" 34, "Dernière chance" 20, "site visit scheduled" 13, "Lead Qualified" 10, "preliminary quote" 6, "waiting for bills" 4, "negotiation" 3, "no answer post-quote" 4. K6 too has an Odoo past: 90 "Devis Cold", 34 "Quote Discussed", 13 "Lead Qualified", 107 tagged NRP, so "never reached in the ERP" does not mean never called. The ERP holds no Odoo last-activity date, so the only check possible from the ERP is the stage at sync time.

Two corrections to K1 before anything is archived: 25 of the 54 "invalid" numbers are formatting only ("212" without "+", or a missing leading 0) and 18 are foreign numbers (likely Moroccans abroad); only 8 are empty. 19 of the 54 have a quote and 8 were reached. One 19-lead "duplicate group" shares a single phone (15 website leads, 4 of them Signé): an internal or test number, not real duplicates. After the formatting fix, 10 K1 leads stay duplicates, 8 move to K7, 3 to K6, 3 to K3.

### 5.2 The legal frame (what every bucket's action respects)

Primary texts read by the research lane and re-opened by an independent verifier (loi 09-08, loi 31-08, the CNDP information sheet « Prospection directe par SMS, emailing… Vos obligations », undated, produced in 2017 and hosted in the CNDP's 2025 upload folder, WhatsApp's Business Messaging Policy); open questions listed in section 10.

1. **Art. 10 of loi 09-08** forbids direct prospecting without prior consent when it uses an automatic calling machine, fax, e-mail "ou moyen employant une technologie de même nature". A human voice call is not named. The CNDP sheet reads it as SMS/e-mail-type prospecting: **prior consent and a prior declaration of the prospecting file** to the CNDP; the only exemption is for contacts collected at a prior sale of analogous products (the statute writes it for e-mail, the sheet extends it to SMS), which a form with no sale does not satisfy. The sheet mentions neither WhatsApp nor phone calls. Whether a hand-typed WhatsApp falls under art. 10 has no CNDP text and no case law; the 21/09 audit already recorded that manual sending protects nothing by itself (SD7): what protects is the traced consent (CAD90) and the exit door in every message (CAD110).
2. **Art. 4 al. 3-b**: consent is not required for pre-contractual measures taken at the request of the person. A Meta form or a website request is such a request; following it up is pre-contractual. That this basis fades with time, and is absent for the Odoo contacts whose request, if any, lives in Odoo, is this document's reading **[O]**, not a text.
3. **Art. 12-1-b**: using data for a purpose other than the one it was collected for needs an authorisation. Re-prospecting the 519 Odoo contacts for a new campaign is the bucket where this bites.
4. **Art. 9 / art. 59**: free right of opposition; processing despite opposition is punished by 3 months to 1 year and/or 20,000-200,000 MAD. 40 leads are opposed today; the 24 "refuse" answers on Meryem's quote tasks are the engine's opposition auto-close, not refusals, and the flag must never be set for "pas intéressé".
5. **Loi 31-08 art. 23-24, 31, 51, 176**: an advertisement must show that it is one and name the provider (art. 23); art. 24 is written for e-mail advertising and its last paragraph extends the opt-out information "quelle que soit la technique de télécommunication utilisée"; on the phone the caller states identity and commercial purpose at the start of the call (art. 31), sends the consumer a confirmation of the offer, and the consumer is bound only by signature (art. 51); breaches of 23-24 cost 10,000-50,000 DH (art. 176).
6. **WhatsApp**: the Business Messaging Policy requires an opt-in "confirming that they wish to receive subsequent messages"; Meta's opt-in guidance adds that the opt-in must name the business; the Policy covers the Business App and the Platform, and the Business App terms incorporate it by reference; opt-outs expressed "either on or off WhatsApp" must be honoured; blocks and reports reduce or remove a number's ability to send; broadcast lists only reach people who saved the number (useless on a cold list). No ban threshold is published.
7. **Regulator practice**: CNDP complaints in 2014 (n = 162) were 50 % SMS and 17 % spam; a fitness club with 151 complaints was referred to court (2018); at a CNDP-ANRT meeting on 23 May 2019 the three operators committed to require an opt-out indication in every prospecting SMS. No do-not-call register, no calling-hours rule, no frequency cap exists in either law.

**Design rules that follow.** Every message names TAQINOR, says where the contact comes from ("votre demande du 14 juin sur Facebook"), and ends with the opt-out line (today only the closing and wake-up templates carry it: task 2.14). Opposed, STOP and wrong-number leads are excluded by the system before any list is built. The prospecting file is declared (F211) before the first batch, if the receipt does not already exist. Messages are typed one by one from the ERP's prepared text (never a broadcast list), 15-25 a day per number, spaced; a batch stops when two or more blocks or hostile replies appear in twenty. The voice call is, on this reading **[O]**, the channel the texts constrain least (art. 10 does not name it), and the most effective in our data; it is also the most expensive in time.

### 5.3 Treatment per bucket

| Bucket | n | Action | Order and cap | What the first touch says | Exit |
|---|---|---|---|---|---|
| K0 opposed | 40 | Nothing. Audit with Meryem that each flag was a real opt-out, not a "pas intéressé"; lifting a flag is a per-lead gesture with a chatter line and a consent-registry entry, never a bulk change | — | — | Permanent |
| K1 junk | 89 | Fix the 25 formatting numbers (they re-enter their real bucket); mark the 19-lead test group; archive the 8 empty and the 10 true duplicates (merge history onto the surviving lead); decide the 18 foreign numbers (WhatsApp only, if they answered a form) | Week 1, system task + 1 h of review | — | Archive |
| K2 terminal lost | 29 | Archive label; keep history | Week 1 | — | Archive |
| **K3 reached + quoted** | **36** | **Meryem, personal call, now.** 33 opened the quote online, 31 have a sent quote (28 expired), 25 quotes above 60k MAD, 31 created in September: they are inside the 3-month decision window the longitudinal data describes (BEACN **[M, vendor-run]**: 3 months is the most common request-to-install gap) | about 3 leads (6 touches) a day over 3-4 weeks; ≤ 2 calls + 1 WhatsApp each | WhatsApp the day before ("je reviens vers vous avec un élément nouveau"), then the call: the new element (a revised quote with a 30-day validity, since an expired quote cannot be extended, financing, a nearby installation, the summer-bill projection), then the J14 decision question | Standby with a date / Perdu with motive / new quote; never Froid again without a reason |
| K4 reached, unquoted | 1 | Call | with K3 | | |
| **K5 never reached, engine era** | **33** | **Two calls in different windows and one message** (the tier-1 treatment below; a full re-run of the protocol would cost about 150 touches): 27 have zero done steps, 26 were parked by Asmaa in October without a cadence. Until task 2.12 exists there is no gesture for this ("Relancer la cadence" poses the wake-up cadence, and the contact cadence refuses a lead that is not Nouveau): worked from a list, calls and messages logged in the chatter | Weeks 5-7, once the second seat is measured (7.3) | Identity message naming their October request, then the calls | Reach → Live; none → Nurture |
| **K6 never reached, May-August Meta** | **262** | Two tiers. **Tier 1 (107: bill ≥ 2,000 MAD or "now/3 months", union of 47 and 75 with 15 in both): call first**, one attempt in a 10-14 h window and one in a 16-18 h window on another day; WhatsApp only after a reach ("je vous envoie le récapitulatif") or, if both calls fail, one hand-typed message citing their request. **Tier 2 (155): one hand-typed 1:1 WhatsApp** citing their request (month, platform), one question, opt-out line; a call only for those who reply. This tier is **decision 11**: a 3-6-month-old form request is a weakening basis and no Meta-conformant opt-in exists for these leads; the alternative is calls only, or nothing | 20-25 a day, weeks 3-10, sized each week by the capacity rule (7.3); hot tier first | Dean Jackson's nine-word form **[O, no measured rate]**: first name as subject, "Êtes-vous toujours à la recherche d'une solution solaire pour votre maison à <ville> ?", nothing else but the opt-out line | Reply → Live; no reply → Nurture (June list); block or STOP → Opposé |
| K7 never reached, web/walk-in | 28 | 19 are archived website leads from June-July (terminal unless a check says otherwise); the 9 Froid ones join K6 tier 1 | Week 3 | | |
| **K8 Odoo, advanced in Odoo** | **96** | These were "Quote Discussed / Dernière chance / site visit / qualified" in Odoo and sit in live ERP stages with no owner. **Pilot: 50 human calls** in office hours by Reda or Asmaa, one attempt plus one retry, no WhatsApp first; the thresholds are judgment, not statistics: fewer than 2 of 50 with any interest (the 2 % floor the reactivation research suggests) closes the Odoo list; 5 or more (10 %) extends the calls to the 120 "Devis Cold"; in between Reda decides on the conversations' content | Week 2-3, 10 a day | Identity, commercial purpose, "vous aviez échangé avec nous au printemps" | Reach → Live or Perdu with motive; no reach → Archive `archive_odoo` |
| **K8 Odoo, cold or lost in Odoo** | **423** | **Archive label `archive_odoo`, Odoo stage kept.** Exception decided by the pilot above: extend the calls to the 120 "Devis Cold" if it passes; otherwise nothing. No WhatsApp campaign on this bucket (no request on record in the ERP, art. 12-1-b, WhatsApp opt-in rule, 170 NRP tags) | Week 1 label; pilot decision week 4 | — | Archive |
| K9 | 1 | Call | with K3 | | |

**Decision 8** (the Odoo archive): label the 423 and run the 50-call pilot on the Odoo-advanced files. Default: yes. The alternative on the table, one WhatsApp broadcast to the whole Odoo list in June, is not recommended: it is the bucket with the weakest legal basis, the lowest information (phone and city), the highest block risk, and the research found no measured yield for lists of that age anywhere.

### 5.4 Calendar and volumes

| Weeks (from go) | What runs | Touches | Who, and where the capacity comes from |
|---|---|---|---|
| 1 | Hygiene: K0 audit, K1 fixes and merges, K2 and K8-cold labels, the one-time repair of section 6, cancellation of about 160 wake-up steps on never-reached, never-quoted leads and junk files, F211 check | system + 2 h | ERP task, Reda, Meryem |
| 2-5 | K3 (36 leads, 1 message + up to 2 calls each, about 108 touches): these calls REPLACE the 56 wake-up steps already due on those leads in Meryem's November, so they add about 50 touches, not 108 | about 6 a day | Meryem, inside her existing wake-up load; the only reactivation that does not wait for the second seat |
| 2-3 | K8 pilot: 50 calls (plus one retry) on the Odoo-advanced files | 10 a day | Reda's time, outside the reps' capacity |
| 4 | Pilot readout: extend to the 120 "Devis Cold" or close | | Reda |
| 5-7 | K5 (33 leads at 2.5 touches, about 83) | about 6 a day | the queue reps, only once the measured seat gives a positive slack (7.3 returns 0 until then; today the slack is negative) |
| 7-16 | K6 tier 1 (107 leads at 2.5 touches, about 270) and K7's 9 cold leads | 25-30 a week, the whole slack | queue reps; faster only if Asmaa reaches a full seat (+67 touches a week) |
| 12-19 | K6 tier 2 (155 messages, plus about 75 touches for the repliers at an assumed 8 % reply rate: about 230), subject to decision 11 | 25-30 a week | queue reps |
| June 2027 | Seasonal message to the Nurture list only (K6 non-responders, `injoignable`, `pas_maintenant_sans_date`; never the Archive, never "the whole database"), opt-out line | one message each, 25 a day over June, inside the daily cap | queue reps |

At the slack of section 7.2 (about 0-20 touches a week once the new-lead flow is served, and only with the second seat at 0.8) the Meta cold list takes until about April; with Asmaa at a full seat it takes until February; with today's recorded second seat it does not start, except K3 and the K8 pilot. The batch of a given week is set by the rule of 7.3, never by this table.

**Expected yield, honestly.** No public dataset gives reply, appointment or close rates by lead age for solar or home services; every "aged lead" table the lane traced was unsourced, and the one CRM audit found (5,000 real-estate leads, 12 % converted over 24 months, not all with the team that bought them) is not transferable. What transfers is the shape: the longitudinal solar data says 3 months is the most common time from request to installation and requesters of January 2016 were still installing at the end of 2020, nearly five years later; the lead-age data from other verticals says an old record rarely converts by itself, a new intent event does (Jornaya 2019 **[M, vendor, n unstated]**). So the plan expects K3 to produce a handful of signatures (the only bucket where a decision is in progress), K5-K6 to produce conversations in the low tens, and K8 to produce the measurement that decides whether the 519 Odoo contacts are worth anything. Every bucket gets a readout line in the Monday review: contacts, replies, conversations, quotes, signatures, STOPs and blocks.

**Stop rules.** A bucket's batch stops for the week when: two or more blocks or hostile replies in twenty messages; a new lead waited more than 15 working minutes unclaimed that day; or last week's on-time % on new-lead steps fell below 90 %. K6 tier 2 stops for good if the first 100 messages produce fewer than 2 replies.

### 5.5 What "archive" means

A label (`parc_raison` terminal, `is_archived`), never a deletion: the history stays, the lead is excluded from every count of prospects, from every list the reps work, from every audience export, and from the seasonal message. The 12-month-silence rule for Nurture leads is a practitioner convention (the e-mail "sunset" logic; Return Path 2014 **[M, e-mail]** found 85 % of the subscribers that teams cut were not actually inactive), so the archive step after 12 months (a nightly job that writes one chatter line per lead) is reversible: a trigger re-opens an archived lead like any other.

---

## 6. The dormant files, and never again

### 6.1 The one-time repair (dry-run first, founder's go, then one command)

| Population | n | What is wrong | Action | Effect on screens |
|---|---|---|---|---|
| Bounced by the Odoo alignment 17/09-08/10 | 125 (of 127 dormant: Relance 71, Nouveau 21, Contacté 20, Devis envoyé 15) | Parked Froid by Meryem, pushed back to their old stage 20 minutes later by the sync, nothing but a wake-up attached | Back to Froid with a `parc_raison` derived from history (quoted → `pas_maintenant_sans_date`, never reached → `injoignable`), tags kept, wake-ups per 4.5 | With the filter below: Relance 197 → about 92, Nouveau 69 → about 16, Contacté 70 → about 17, Devis envoyé 53 → about 15 (the 66 never-placed Odoo files included until their triage); Meryem's active files 118 → about 30, her 115 lost/archived files behind the toggle (her raw live-stage count 233 → 145) |
| Lost, archived or opposed in a live stage | 124 (Nouveau 32, Contacté 33, Devis envoyé 23, Relance 36) | Archiving or losing never changed the stage | No data write: every live-stage count, list and kanban excludes lost/archived/opposed by default (a selector rule), with a toggle to show them | The four live stages lose 124 phantom files |
| Active, never placed in any cadence | 66 | 61 are Odoo-era files Odoo had advanced, 5 recent arrivals | The 61 join the K8 pilot (5.3); the 5 are placed in v4 now | |
| Open wake-ups | 232 steps on 164 leads | 147 steps sit on the 111 leads never reached and never quoted (71 K6 leads, 35 K8 leads, the rest K1/K5/K7), 74 steps on ownerless files, 43 overdue | Cancel the 147 and the dozen left on other K1 files (about 160 in all); convert the 56 on K3 leads into the K3 calls of 5.3; keep the rest | Meryem's November: 118 wake-up steps (49 + 40 + 14 + 15 by week) become about 50 on leads reached or quoted, which are the K3 calls |
| Asmaa's October parks | 25 (in K5) | Parked Froid with zero touches | Re-placed in v4 (5.3) | |
| Test and internal records | the 19-lead phone group, 4 June website "Signé" with no quote, no activity, no step (10 of the 22 Signé have no quote at all) | Count as signed and as duplicates | Mark `test`, exclude from conversion figures | Signed 22 → about 18 real |

Method: a management command with `--dry-run` that prints, per population, the ids and the before/after; the dry-run diff goes to the founder; then the write, once, logged in the chatter of every lead touched ("réparation du 2026-11-xx, motif"). This follows the house rule for client-visible repairs (dry-run diff first, re-ask if anything a client received changes; here nothing client-facing changes).

### 6.2 The standing rules (so it cannot rebuild)

**Nightly invariants** (section 2), each with a cockpit line and a Monday list:

| Rule | Threshold | Today |
|---|---|---|
| Active lead without an open step and without a future Standby date | 0 tolerated | 68 of 265 (50 in Relance) |
| Froid lead without a reason | 0 tolerated | 721 of 721 |
| Lead parked `injoignable` with fewer than 5 calls recorded, or any lead parked with 0 touches | 0 tolerated | 25 of Asmaa's October leads; "Injoignable 6 appels" tag on 6 leads in the whole base |
| Standby date passed, no call done | ≤ 2 working days | not measurable (no field) |
| Lost or archived lead counted in a live stage | 0 | 124 |
| Wake-up step on a lead never reached and never quoted | 0 | 147 steps on 111 leads |

**Stage ceilings** (the "rotting" idea of Pipedrive and the Close views, adapted; a scheduled future task does not stop the clock, only a dated Standby with a reason does):

| Stage | Flag at | Decide at | What "decide" means |
|---|---|---|---|
| Nouveau | first touch > 5 working min (office) or > 24 h (any) | 10 days | reached → Contacté; not reached after the protocol → Froid `injoignable` |
| Contacté | 7 days without a quote or a dated Standby | 14 days | quote, Standby with a date, or Perdu with motive |
| Devis envoyé | 14 days (the J14 decision call) | 30 days (the J30 validity call) | accept, Standby, extend once, or Perdu with motive |
| Relance | any step overdue > 2 working days; no dated step | 90 days since the quote | Standby with a date, Nurture, or Perdu |
| Froid | reason missing | monthly review of re-entries | |

**Definition of "not contacted in a while", measured as days since the last human touch per stage and owner.** Today the touched part of the live base is fresh (no active, touched lead is older than 60 days; Meryem's 118 active files: 36 under 14 days, 69 at 15-30, 9 at 31-60). The stale population is the never-touched one: 110 of 265 active leads, 99 of them ownerless Odoo-era files. After the repair this number is near zero, and the rule above keeps it there.

---

## 7. The operating model: capacity, days, weeks

### 7.1 Where the capacity goes today

Meryem: 525 done steps in the last 30 days on 22 working days, median 22.5 a day (p25 16, p75 31, max 46), 124 touches a week, 7.5-hour span, every weekday worked since 7 September, 36 % calls / 64 % WhatsApp. At 20-27 new leads a week and 5.9 executed contact touches per lead (her average), the contact protocol alone is 118-160 touches a week; the post-quote cadence asks 10 touches on about 45 % of leads; the wake-up stock (232) costs about 29 touches a week to burn down over 12 weeks. The designed demand is about 270 touches a week against about 124 delivered: the system runs because execution is partial (5.9 of 11), and because the unscheduled touches are silently not done. Asmaa's recorded effort is 38 done steps since 06/09 (about 10 a week), 32 of them on a single day (chatter on 23 days), 0.6-0.7 steps per lead; Reda's 72 steps in 10 days.

### 7.2 What v4 removes and adds (per week, N = 23 new leads, assumptions labelled)

| Item | Today | v4 | Assumption |
|---|---|---|---|
| Contact protocol, executed touches per lead | 5.9 | about 4.6 | reached leads (61 %) still stop at touch 2-3 (2.5 touches); silent leads get 8 instead of 11 |
| → touches/week | 136 | 106 | 23 leads |
| Post-quote, touches/week | 83 | 75 | 45 % quoted; v3: 10 at 80 % execution; v4: 6 at 85 % + 3 at 70 % |
| Wake-ups | 29 | about 8 | the 66 steps that survive the cancellation, burned over 12 weeks (5.5), plus the bill ≥ 2,000 pilot calls (about 2); the J28/J60/J90 touches of reached-and-quoted leads are inside the post-quote line |
| Standby calls and call-backs | 9 | 9 | 15 % of leads, 2 touches; 10 % call-backs |
| Post-park wake-ups of quoted non-signers (J30 call + J60 message after the J90 park) | inside the 29 above | about 11 | 23 × 45 % quoted × 55 % undecided × 2 touches |
| Weekend sweeps | 0 | net 0 (about 20 touches shifted from Monday to the weekend, already inside the contact line) | 10 weekend leads × 2 first touches |
| **New-lead demand** | **257** | **about 209** | 106 + 75 + 8 + 9 + 11 |
| Capacity, Meryem | 112 (5 × 25 × 0.9) | 112 | plan 25 a day, 10 % buffer; her measured pace is 124 |
| Capacity, Asmaa | about 10 recorded steps a week (0.1 of a seat on recorded steps) | **90 required (0.8 seat)** | the design does not close without it |
| **Slack for reactivation** | negative (257 asked, about 122 delivered: execution about 50 %) | **about 0-20** (209 against 112 + 90, the seat at 0.8; at 0.9 the slack is about 20) | |

Reading: v4 removes about 60 touches a week of demonstrably unproductive work (3 per silent lead, 8 post-quote, about 20 wake-ups) and still needs the second seat at four days a week to carry the new-lead flow with a margin. The reactivation of section 5 runs on that margin and is paced by it (the calendar of 5.4): K3 (about 108 touches) mostly replaces wake-ups already due; K5 about 83; K6 tier 1 about 270; K6 tier 2 about 230 (155 messages plus the repliers). At 30 new leads a week the slack disappears and the reactivation pauses (section 5.4 stop rules). The three numbers that decide everything and that we do not have yet: Asmaa's real seat, the post-quote execution rate under v4, the reply rate of the first 100 K6 messages.

### 7.3 The weekly capacity rule

Strict priority, interrupt-driven: (1) a new lead's first touch, (2) a reply from any lead including cold-list repliers, (3) scheduled call-backs and Standby dates, (4) post-quote steps due, (5) contact protocol steps, (6) the remaining wake-ups, (7) the reactivation batch. The reactivation batch of next week = min(measured slack of last week, 40 contacts), and 0 whenever last week's median time to first touch missed its target or the on-time % on new-lead steps fell under 90 %. Daily guard: the reactivation block is cancelled if more than 3 new leads are waiting unclaimed or any new lead is older than 15 working minutes.

### 7.4 Meryem's day (template; Friday prayer window respected; Ramadan window per the existing calendar)

| Time | Block | Content |
|---|---|---|
| 09:00-09:30 | Queue + WhatsApp batch 1 | Overnight and weekend leads (identity WhatsApp), replies, today's call-backs |
| 09:30-10:00 | Quotes, admin | |
| 10:00-12:00 | **Call block A** (protected; the 10-12 h window reaches 29 %) | New-lead attempts 2-3, call-backs, J2 post-quote calls |
| 12:00-12:30 | Log, replies | |
| 12:30-14:00 | Break (Friday prayer window respected) | |
| 14:00-15:30 | Quotes, visit booking and preparation (the 14-16 h window reaches 18 %: no calls) | |
| 15:30-16:00 | WhatsApp batch 2 + reactivation messages (only if 7.3 is green) | |
| 16:00-17:30 | **Call block B** (protected; the 16-18 h window reaches 26 % and answers 59 % of the time) | J7/J14/J28 post-quote calls, Standby dates, K3 calls, cold-list repliers, the J2 evening attempt |
| 17:30-18:00 | Log, plan tomorrow, huddle numbers | |

The 16:00-17:30 block is the test the 21/09 default (CAD25, calls at 17:30-18:30) never got, since 2 % of touches happened after 18 h: one month of measurement decides its hours.

Standing rules: a new-lead notification is a first touch within 5 working minutes, then back to the block; a WhatsApp reply from an active lead is answered within 15 working minutes even inside a block; calls on Monday morning are reserved for weekend arrivals (Monday reach 18 %, the worst day; Tuesday-Thursday 22-38 %). Asmaa: the same template shifted by 30 minutes, duty half-days alternating, the same touches-per-lead band on the same cockpit. Reda: queue escalation, Monday review, C&I discovery calls, the K8 pilot; no cadence leads of his own.

### 7.5 Logging rules that make the numbers true

- "Joint" means a conversation happened. A WhatsApp that was delivered is "envoyé", a reply is "réponse"; the cockpit flags a rep whose WhatsApp "joint" rate exceeds 25 % or whose call "joint" rate exceeds 70 % as a data anomaly to look at (Asmaa, October: 22 of 24 identity WhatsApps "joint", 30 of 31 calls "joint", 28 of them on 30/10).
- WhatsApp chatter lines are written about twice per step today (1,392 lines for 708 done steps); the capacity figures use done steps; the double logging is a bug to fix so that the chatter can be trusted for time per touch.
- A Standby always records the agreed date in a field, not only in a note ("Rappel demandé le…" exists 53 times as free text and cannot be checked).
- Opposition is a separate gesture with a confirmation, never a shortcut for "pas intéressé".

### 7.6 Management rhythm

- **Daily, 10 minutes, standing**: yesterday's misses (overdue steps, leads unclaimed > 15 min), today's load and whose block is protected, the queue, one number (on-time % vs 90 %).
- **Monday 09:30, 30 minutes, Reda + both reps**: scoreboard 5 min (cohort line with control limits: leads in, median time to first touch, reach by attempt, on-time %, quotes sent, time to quote, J14/J30 decisions); stuck list 10 min (auto-generated, max 10 rows: no next step, step overdue, > 14 days since a meaningful contact, quote > 7 days without a reply; each row leaves with an action, a date, or a downgrade); quotes out 8 min (J7/J14/J30 decisions due, top 5 by value, who decides); Standby and reactivation 5 min (dates due, this week's batch from 7.3, last week's readout per bucket); decisions 2 min (what changes this week, written in the experiment register).
- **Monthly**: re-entries from Nurture and Archive, the hour-window test, the seat fractions, the capacity table of 7.2 recomputed with measured numbers.

### 7.7 How we will know it worked

- No half/half A/B on the new-lead reach rate: detecting 37 % → 45 % needs 592 leads per arm (59 weeks at 10 per arm per week); 60 per arm detects only a jump to 62 %. Peeking at a running test inflates false positives.
- Instead: the package is adopted at once; the weekly cohort line (reached within 14 days, quoted within 21 days) is pre-registered against the last 12 weeks' baseline (37 % step-recorded reach, 61-63 % total reach), read with a sequential test (SPRT) or a CUSUM at fixed checkpoints (weeks 4, 8, 12), with every campaign or creative change marked on the chart because it moves the baseline.
- Process changes are judged on the fast, high-count metrics: median time to first touch, on-time %, touches per lead per rep (hundreds of events a month).
- The cold list is the one place where numbers are not scarce: K6 tier 2 can be split by lead id into two message variants (about 75 vs 75 at first, growing with the June list); detecting a doubling of the reply rate from 8 % to 16 % needs about 260 per arm at 80 % power (345 at 90 %), and 75 per arm gives about one chance in three; so variants are compared cumulatively over the year, not decided in a month.
- An experiment register (date, change, metric, expected effect, readout date) lives next to the cockpit so that the Monday review attributes movements instead of guessing.

### 7.8 What can start on Monday without a build

Wave 1 is code (build, CI, merge, deploy); these are not:

1. **Paramètres → CRM**: set the wake-up rung ordre 1 to canal « appel » (this applies the 21/09 decision CAD74 Q20 that never reached the company's rows); optionally enter the v4 contact rungs in the same editor (the data of 4.1), knowing that plans in flight follow the new gabarit at once and that the closing tag will read "Injoignable 6 appels" until task 2.3 makes it dynamic.
2. **Team attribution**: route the Meta flow to Meryem alone until the queue of 2.11 exists, or keep Asmaa on it with the cockpit's team view open every morning; either way, the rule "no park with fewer than five recorded calls" is said out loud now and checked by hand on Friday.
3. **The K3 calls**: the 56 wake-up steps are already in Meryem's November queue; she takes them as calls with the new element (a revised quote at 30 days, financing, a nearby installation), and logs the decision answer.
4. **The K8 pilot**: 50 calls by Reda in office hours, a line per call in the chatter.
5. **Meryem's day template** (7.4) and the logging rule (7.5): "joint" means a conversation.
6. **The Monday review** (7.6) with the numbers the cockpit already gives (on-time %, first contact median, par_segment).

What breaks first if more is attempted by hand: the K3 "revised quote" hook means up to 28 revisions to produce (uncounted work for Meryem); Asmaa's execution does not change until the queue exposes it; the slack of 7.3 cannot be measured until task 1.7 exists.

---

## 8. What changes in the ERP (implementation map, from a read-only pass over the code at `ba577e26ad`)

**Four facts that shape the build.** (1) The rhythm is data: each company's rungs live in `parametres.CadenceRelanceEtape` (`apps/parametres/models_relance.py:436`), editable in Paramètres → CRM; `seed_cadence` never touches an existing rung, so v4 reaches production through an idempotent data migration or a Paramètres edit, not through code defaults. In-flight plans follow the new gabarit (the next touch is looked up by `ordre`, `apps/crm/cadence_plan.py:906`). (2) The engine is reactive: the next touch is born from the outcome of the previous one, so "only if unanswered" is the default semantics and needs no new mechanism; a same-day second rung with its own `heure_cible` is data; a true 2-minute shadow exists only for J0 rungs (anchored on the closing instant, `cadence_plan.py:~1010`). (3) Three code paths park a lead in Froid and none keeps a reason: the end of a gabarit (`cloturer_cadence`, `cadence_plan.py:1075`: COLD + a hard-coded tag + J30/J60 wake-ups posed at once), the nightly quote expiry (`apps/ventes/domain/recouvrement.py:989`: Devis envoyé → Relance → Froid after 30 days, no tag), and the bulk "→ Froid" (`apps/crm/fiche_bulk.py`). (4) The wake-ups decided on 21/09 (J30 = call, `reveil_a1`) exist as code defaults (`models_relance.py:275`) but the company's rows read ordre 1 WhatsApp J30 and ordre 2 WhatsApp J60 (verified on production): they were seeded before the decision and never updated, and `seed_cadence` never touches an existing row. The human J30 call has therefore never actually run in production.

No new stage, no SQL, company-scoped selectors, cross-app through `selectors.py`/`services.py`, WhatsApp stays manual (the engine poses touches, a human opens the `wa_url`), `/proposal` untouched, contract samples delivered first (PACT10) on every task that adds a served key (1.2, 1.7, 2.1, 2.7, 2.11, 2.12, 2.13). Owner plans per `docs/ownership.yml`: the cadence engine files (`cadence_*.py`, `parcours_suivi.json`) → `docs/plans/PLAN_AUDIT_LEAD.md`; `apps/crm/views.py`, `services.py`, `selectors.py` → `PLAN_AUDIT_CRM.md`; `models_relance.py` and `models_company.py` → parametres; `leads_meta.py` and `adsengine` → acquisition; coherence rules → `PLAN_AUDIT_MOTEUR.md`; `ventes/scheduled.py` and `recouvrement.py` → `PLAN_AUDIT_FACTURATION.md`; any task spanning several owners → `PLAN_AUDIT_TRANSVERSE.md`. No open task covers the park reason, the Standby/Nurture/Archive states, the repair of the bounced leads, the live-state filtering, the J1+ shadow, the frein/déclencheur inputs, an "extend validity" button or the opposition guard on the e-mail nudges; the related open tasks are CADM5, CADM7, CIQM25, AGRM32/34/37, CADM1 and the gated PUB107/PUB109 (WhatsApp Cloud).

### Wave 1 — clean, protect, measure (no cadence change; needs only the repair go)

| # | Task | Anchor | Size |
|---|---|---|---|
| 1.1 | Repair command for the bounced leads: dry-run by default, `--apply`, `--limite`, `--company` (never cross-tenant); the 125 leads (system "Froid → X" row, only a wake-up open) back to Froid with a derived reason, tags and wake-ups per 4.5, one chatter line each | pattern `apps/crm/management/commands/corriger_villes_leads.py`; data `LeadActivity(field='stage', user=None, old_value='Froid')` | M |
| 1.2 | Archiving stops the cadence; lost and opposed leads leave every live-stage count and list by default (the kanban already hides archived leads, `stages.js:248`, but shows lost and opted-out ones; the KPIs exclude them; the cockpit and the queue count differently); one selector rule, a "voir les perdus/archivés" toggle; contract sample first for the cockpit keys | `apps/crm/views.py:883`, `fiche_bulk.py:368` → `arreter_cadence` (`cadence_plan.py:1485`); `frontend/src/features/crm/.../stages.js:247`; `kpis.py:22`; `controle_suivi.py`; `cadence_selectors.py:1437` | M |
| 1.3 | One-off cancellation of the wake-up steps on never-reached, never-quoted leads and on junk files (about 160 steps: 147 on the 111 never-reached, never-quoted leads plus the K1 remainder), through `arreter_cadence(cadences=['reveil'])` in the same command as 1.1 | `cadence_plan.py:1485` | S |
| 1.4 | Hygiene: normalise the 25 "212"/missing-0 phones, flag the 19-lead internal number and the June test records with a managed `test` tag (the park reason after 2.1; `est_junk` belongs to the lost-reason list, not to the lead) and exclude them from the KPI selectors, merge the 10 true duplicates (history onto the survivor), decide the 18 foreign numbers | `Lead.telephone/whatsapp`; CAD11 `est_junk`; duplicate signal in `leads_meta.py:732-808` | S |
| 1.5 | Archive label on the 423 Odoo-cold contacts (`archive_odoo`, Odoo stage kept in the note), excluded from prospect counts, lists, audiences and the seasonal message | tag via `poser_tag_lead` until 2.1 gives the field; `cadence_reveil_saison.py:176` exclusion | S |
| 1.6 | Nightly data rules: active lead with no open step and no future Standby date; Froid without a reason (after 2.1); parked with 0 touches or "injoignable" with < 5 calls; wake-up on a never-reached, never-quoted lead; lost/archived counted live; rep whose WhatsApp "joint" rate > 25 % or call "joint" rate > 70 % over 7 days | registry `apps/ventes/coherence/registre.py` + `regles_crm.py` (beat `ventes-audit-coherence-nuit`) | M |
| 1.7 | Measurement: cumulative first-reach-by-rank curve per cadence and segment, weekly cohort line (created → first touch median → reached ≤ 14 d → quoted ≤ 21 d → accepted), touches per lead per owner; contract sample first, then cockpit lines | next to `apps/crm/mesure_cadence.py:401` (`par_segment`) and `:133`; `controle_suivi.py:805`; `contract_samples/controle_suivi.json` | M |
| 1.8 | The post-quote nudges (J2/J5/J10 at 08:15) go to the SELLER (in-app note or e-mail with a wa.me draft), never to the client, and are held while a cadence runs (MRY7); two gaps remain: when the cadence ends every unsent level fires at once, and the seller can receive a wa.me draft for an opted-out lead. Fix both; same `peut_contacter` filter on the CRM exports | `ventes/domain/recouvrement.py:656-837`; `apps/crm/portee_selectors.py:15`; `apps/crm/exports.py` | S |
| 1.9 | WhatsApp chatter lines logged twice per step (1,392 lines for 708 steps): one line per touch | `cadence_messages.py:545`, `cadence_views.py:1161` | S |
| 1.10 | Bulk "préparer WhatsApp" operation: `peut_contacter` guard, daily cap (15-25 per number), STOP line check, batch log | `fiche_bulk.py:436` | S |
| 1.11 | Structured call-back date: the "Rappel demandé le …" free text becomes a date field on the moved step (readable by the cockpit; contract sample first) | `cadence_reponses.py:706/805`; `models_cadence.py` | S |

### Wave 2 — cadence v4 and the park model (after decisions 1-4)

| # | Task | Anchor | Size |
|---|---|---|---|
| 2.1 | Contract first: `contract_samples/lead.json` with `parc_etat` (standby / nurture / archive), `parc_raison` (the codes of section 2), `parc_jusqu_au`; then the crm migration and the six places CAD149 lists (tracked fields, provenance exclusions, `draftCore.js`, `fieldLabels.js`, webhook cleaners, questionnaire sections); one write point `parquer_lead(lead, raison, jusqu_au, user)` used by `cloturer_cadence`, `_advance_lead_on_expiry`, the bulk "→ Froid", `mettre_en_veille`/`repondre_plus_tard`, `repondre_perdu` | `cadence_plan.py:1075`; `recouvrement.py:989`; `fiche_bulk.py`; `cadence_reponses.py:706/805/1628` | L |
| 2.2 | Park dialogue: reason mandatory, date mandatory for Standby, refusal of "injoignable" under 5 recorded calls and of any park at 0 touches (the engine's own count), third "later" → Nurture | `parcours_suivi.json` answer models; `cadence_reponses.py` | M |
| 2.3 | Contact gabarit v4 as an idempotent data migration that edits ordres 1-11 in place (rows 1-4 kept; 5-8 rewritten as J2 call, J2 message, J4 call, J7 message; 9-11 deactivated) so that plans already in flight continue at the right rank and never receive a rung whose day is past; dynamic closing tag ("Injoignable N appels" computed, not the hard-coded 6); the journey table, the GED guide and the frozen tests updated in the same change | `models_relance.py:149/436`; `cadence_reperes.py:170/176`; `parcours_suivi.json`; tests `tests_mry4_cadence_v2`, `tests_cad25_heures_cibles`, `tests_cad67_scripts_appels`, `tests_cad20_un_appel_un_message`, `tests_cad153_script_guide`, `tests_guide_suivi_a_jour` | L |
| 2.4 | Post-quote gabarit v4 (same in-place mechanics): J1 WA, J2 call, J3 conditional, J7 call, J10 content WA chosen by `frein_principal`, J14 call, J28 call, J60 WA, J90; validity decoupled from the last step (VALID1 ties it to the last post-quote step today, `cadence_plan.py:797-830`, `cadence_messages.py:886`) and set to 30 days from the send; the J28 call is the extension point because `prolonger_validite_devis` only acts on a quote still « envoyé » (`envoi.py:431`) and the nightly `expire_stale_devis` flips it to « expiré » after the date with no way back; a "Prolonger la validité" button on that service; the expiry path (`_advance_lead_on_expiry`) parks with a reason through 2.1 instead of silently; the proposal's validity line shows the 30-day date and « prix révisable au-delà » (a text fix in the one engine, rule #4) | `models_relance.py:224`; `recouvrement.py:859/989`; `envoi.py:409/431` | L |
| 2.5 | Conditional wake-ups: in the placement loop (pattern "dimanche famille", `calculer_echeances_cadence:243`) no individual wake-up for never-reached, never-quoted leads; J30 = call for reached or quoted leads; the bill ≥ 2,000 pilot; a rule for ownerless leads (default owner or team queue) | `cadence_plan.py:170/243/1122`; `cadence_placement.py:453` | M |
| 2.6 | The three questions: inputs for `frein_principal` and `declencheur` in the lead form (today "pending"), `decideur` asked in the residential script, each with its `help_text` question; the J10 content touch picks its template from `frein_principal` | `fieldLabels.js:342`; `panneau_appel.py:54`; `MessageTemplate` variants (CAD126) | M |
| 2.7 | Standby visible (contract sample first): cockpit line "Standby échus" from `parc_jusqu_au`, max 2 cycles, triggers re-open a parked lead on the first reopening of the proposal link after 30 days (today only the third reopening poses a touch) | `controle_suivi.py`; `ventes/scheduled.py:677` → `cadence_signaux.py:336` | M |
| 2.8 | Seasonal list: `poser_reveils_saisonniers` extended to every Nurture lead (K6 non-responders, `injoignable`, `pas_maintenant_sans_date`) and to lost leads with a non-terminal motive (the job excludes all lost leads today), Archive excluded (so the 423 Odoo-cold leads must carry the archive flag first), one per year, STOP line, and a daily cap of 25 instead of the job's 200 per company per day | `cadence_reveil_saison.py:176` | S |
| 2.9 | C&I path (decision 10; reopens CAD52/CAD124 and B2B7; keeps D-CIQ-20): post-contact engine chain variant ("pièces reçues ?" J3 and J7), second-contact field, quarterly Standby, no wake-up messages on commercial leads | engine chains in `cadence_plan.py`; CIQ tasks | M |
| 2.10 | Weekend sweep: `samedi_ok` on the identity WhatsApp rung only, Sunday window 17:00, company windows, a duty setting per weekend | CAD43 `samedi_ok`; `CompanyProfile` windows (`parametres/models_company.py:464-502`) | S |
| 2.11 | Duty-rep queue (contract sample first; C&I leads bypass it to the named pro owner, D-CIQ-20): evolution of `dispatch.py` (which already holds leads for a decision out of hours): shared "À prendre" list, claim, ladder T+5 both / T+15 Reda / T+30 auto-assign with a logged breach, median time-to-first-touch KPI, Reda's leads in the queue | `apps/crm/dispatch.py:70`; `leads_attribution.py:68`; `escalader_premier_contact` (beat */5) | M |
| 2.12 | Reactivation tooling (contract sample first): bucket selectors (K3/K5/K6 tiers), weekly batch from the capacity rule, prepared messages from `MessageTemplate` with the origin of the contact and the STOP line, per-bucket readout (contacts, replies, conversations, quotes, signatures, STOP, blocks), stop rules, consent-registry entries for the basis used | `cadence_selectors.py`; CAD90 `enregistrer_consentement_lead`; `fiche_bulk.py:436` | M |
| 2.13 | Experiment register and the pre-registered cohort chart (contract sample first) (baseline window, checkpoints, SPRT/CUSUM) in the cockpit | `mesure_cadence.py`; cockpit | S |
| 2.14 | The opt-out sentence on every outbound template (identity message, post-quote J1, the new J2 slot offer, J10 content, J60), not only the closing and wake-up texts CAD110 covered | `apps/parametres/models_messages.py` (`identite` l.60-63, STOP keys) | S |
| 2.15 | Re-entry gestures: a WhatsApp reply or inbound call recorded on a parked lead re-opens it (outcome gesture, owner notified); a new form submission by a phone already in the base re-opens the existing lead instead of creating a duplicate | `cadence_reponses.py`; `leads_meta.py:732-808` (duplicate signal) | M |
| 2.16 | After acceptance: a short chain to the signed contract and the deposit (confirmation J+2, deposit reminder J+7, escalation to Reda at J+14); none exists today | ventes → crm through `services.py` | M |

### Wave 3 — integrations (decisions 5-7)

| # | Task | Anchor | Size |
|---|---|---|---|
| 3.1 | Instant acknowledgement out of hours through the WhatsApp Business Platform (utility template, about 80 messages a month), with an opt-in box naming WhatsApp and phone on the Meta form, cross-border transfer question answered, number strategy (coexistence disables broadcast lists) | gated PUB107/PUB109; `adsengine/whatsapp_webhook.py` (inbound only today) | L |
| 3.2 | Meta form: consent checkbox, "higher intent" setting, dayparting on a lifetime budget (no code) | Meta Ads Manager | — |
| 3.3 | Click-to-WhatsApp ad test with a welcome message (the user's message opens the 24 h window; free entry point 7 days) | CTWA webhook exists | S |

---

## 9. The founder's decisions

**Decided on 2026-11-01 by the founder, in session, all eleven at their defaults** (answers given as four grouped choices: cadences 1/2/3/10, park model and repair 4/9, flow and coverage 5/6/7, cold list 8/11). Conditions that stay attached: the repair runs dry-run first with the id list validated before `--apply`; the K6 tier-2 messages wait for the F211 receipt and the Meta form disclaimer check; the automatic acknowledgement waits for the opt-in box on the form (3.2). Wave 2 and wave 3 tasks are therefore no longer gated on a decision, only ordered.

| # | Decision | Default | What it reopens | Evidence in one line | Cost if the default is wrong |
|---|---|---|---|---|---|
| 1 | Contact protocol v4: 5 calls + 3 WhatsApps over 7 days, windows 10-14 h / 16-18 h, Tue-Thu preferred, no Sunday rung, no 17:30-18:30 default | Yes | 21/09 "ni le nombre, ni l'ordre, ni le J+N" and "mesurer d'abord (CAD87)"; CAD25 (calls at 17:30-18:30 by default) | touches 5-11: 1 call-back in 25; 94 % of Meryem's first reaches inside 7 d; Sunday 0 touches in 12 weeks | a thin tail (6 of 42 chatter reaches after day 7) is handed to the seasonal list; reversible in Paramètres |
| 2 | Wake-ups by history: no individual steps for never-reached, never-quoted leads; human J30 call for reached or quoted; a small call pilot on never-reached leads with a bill ≥ 2,000 | Yes | CAD74 Q20 (J30 = call) for part of the population | 157 wake-up messages to never-reached, never-quoted leads → 0 conversations (the one conversation in 178 was a reached-and-quoted lead); the J30 call never ran in production, so dropping it for this group is a capacity choice, and the pilot is its only test | the pilot and the seasonal list catch what the blind steps did not |
| 3 | Post-quote v4, validity 30 days decoupled from the cadence, the J28 call as the extension point | Yes | CAD57 (J+14 unless financed); VALID1 of 07/09 (validity = date of the last post-quote step); 21/09 rejections of "a touch between J14 and J30" and "third wake-up wave" (the cadence part was conditioned on CAD87) | J4/J6 WhatsApps 0/46; J2 call 50 %; acceptances at days 2-6 and 21; about 50 of 63-70 expired at 13-14 d | a longer validity costs nothing in a falling-price market only if the quote says the price may be revised; one line in the proposal |
| 4 | The park model: reason and date mandatory, Standby/Nurture/Archive as fields (not tags), nightly invariants | Yes, fields | nothing decided before; CAD149 six-places discipline | 721 Froid without a reason; 68 active leads without a next step; 3 park paths | tags would be faster (no migration) but unqueryable and unenforceable |
| 5 | Automatic acknowledgement out of hours through the WhatsApp Business Platform (utility template; about 2 $ a month at Morocco's rate; needs an opt-in box on the Meta form), and whether to test click-to-WhatsApp ads (3.3) | Yes, utility only, after 3.2; the ad test is optional | RELANCE-WA (manual WhatsApp), D-WHATSAPP (no Cloud API), PUB107/109 gated | weekend arrivals wait 24 h and reach 52 %; Meta documents only a user message or call as opening the 24 h window, so a form submission does not (inference from Meta's pages); the Business-app away message only answers people who write in | the weekend sweeps alone (decision 6) are the fallback; the API also changes the number set-up |
| 6 | Weekend coverage: two 60-minute WhatsApp-first sweeps (Sat 10:00, Sun 17:00), one weekend in two, compensated | Yes | the 21/09 note that Sunday 16-19 h is "a free commercial choice" | 61 weekend leads, median first touch 24 h, 0 reached within an hour | Meta dayparting instead shifts arrivals but cuts volume |
| 7 | One shared queue with a duty rep and ownership after the first touch for residential leads; Reda's leads in the queue; C&I leads keep the named pro owner (D-CIQ-20 untouched); Asmaa at ≥ 0.8 seat on the same cockpit | Yes | the team-based attribution and the "responsable confirme" mode of 27-30/10 | Asmaa 0.7 touches per lead, 49 % reached, median 306 h to first reach, 28 "reached" calls logged on one Friday; Reda 8 % on time | if a second seat is not available, the Meta budget must follow Meryem's capacity: at v4's 9 touches per lead (209 for 23 leads) her 112 touches carry about 12-13 leads a week, not 20 |
| 8 | Odoo archive: label the 423, run a 50-call pilot on the 96 Odoo-advanced files, no WhatsApp campaign on the Odoo list | Yes | the audit's option "one broadcast in June" | weakest legal basis (art. 12-1-b), 170 NRP tags, phone-and-city only, no measured yield anywhere for lists of that age | if the pilot reaches ≥ 10 % with interest, extend to the 120 "Devis Cold" |
| 9 | The one-time repair of section 6.1 (dry-run diff, then one command) | Yes | nothing; applies the house rule for repairs | 125 bounced, 124 phantom, about 160 blind wake-up steps, 25 zero-touch parks | none: the dry-run is the safeguard |
| 10 | Segment paths: the C&I quote-prerequisite path with a quarterly Standby and no J14 park (4.6), the agricultural Standby at the client's own dates (4.7), wake-ups by history (2) | Yes | CAD52 (21/09: no rhythm variant "until CAD87": this is that measurement); B2B7 (longer post-quote tail for B2B, eliminated 21/09); CAD124 stays closed (no segment axis in the gabarit: the path is engine chains and Standby rules, which CAD124 allows); AGR512 kept (no invented season) | 74 commercial leads, 9 % reached, 3 quotes created of which 1 sent, 0 accepted; 27 wake-ups on commercial leads, 0 conversations | reversible: no second gabarit |
| 11 | Message the 155 K6 tier-2 leads at all (one hand-typed WhatsApp each, citing their May-August request, opt-out line, 20-25 a day), or calls only, or nothing | Yes to the messages, only after the F211 receipt exists and the Meta form's disclaimer has been read and names contact by WhatsApp or phone; otherwise calls only | nothing decided before; the audit's option of a June broadcast | the basis is a 3-6-month-old form request (art. 4 al. 3-b reading, **[O]**), no Meta-conformant opt-in exists for them, 107 NRP tags in Odoo; the yield is unknown (no measured data for lists of that age) | art. 59 exposure (3 months to 1 year, 20,000-200,000 MAD) if the CNDP reads a hand-typed WhatsApp as art. 10 prospecting without consent; a number block if replies turn hostile; the stop rules of 5.4 limit both |

Two conditions sit under decision 11 and under the tier-1 messages that follow a failed call: the prospecting file's declaration to the CNDP (F211 receipt) must exist, and the Meta form's current disclaimer wording must be read, because it decides whether a 2026-05 submission still carries a basis for a 2026-11 message.

---

## 10. Method, verification, limits

**Rounds.** R1 (understand) = the audit of 1 November (problem list, 11 findings). R2 (dig) = seven lanes: two production reads (cold inventory; cadence curves), one repo map (ERP hooks), four research lanes (reactivation evidence; segment cadences and pipeline rules; WhatsApp, Moroccan law and Meta; capacity and operations), plus the orchestrator's own power arithmetic. R3 (validate) = three fresh verifiers with different lenses (production numbers recomputed; sources and legal texts re-opened; feasibility against the code, the founder's decisions and the repo rules), findings triaged and folded. R4 (final review) = one completeness critic over the whole document, its findings folded. **10.1 Verification counts.** Production verifier: 87 figures recomputed with its own queries, 41 confirmed, 42 within 1-3 of the stated value (definition differences, kept as ranges where it matters), 4 refuted and corrected here (the 111 blind wake-ups are leads carrying 147 steps; five leads waited more than 72 h for a first touch; Asmaa's steps fall on 6 days; the after-repair Nouveau count), 1 misleading reading corrected (Meryem's screen after the repair). Sources verifier: 29 claims re-opened, 19 confirmed, 10 partly and reworded (the CNDP sheet's date, the 31-08 articles, the 2019 operators' commitment, WhatsApp's opt-in and opt-out wording, the 24-hour-window inference, Morocco's rates read on Meta's own page, BEACN's wording, the K6 test size), 0 refuted. Feasibility verifier: 18 findings against the code and the decisions, all folded (six calls counted as five; validity tied to the last step by VALID1; no extension of an expired quote; the quote nudges go to the seller; five reopened decisions added; the calendar re-paced to the capacity; the arithmetic of 7.2; the location of `est_junk`; the call panel already asks the three questions; in-flight plans and the migration; the seasonal job's cap and exclusions; the invented agricultural season; ownership routing; field naming; contract-first on five tasks). **10.2 Final critic.** One fresh completeness critic (Fable) read the whole document against its inputs, the code and the decisions: 5 blocking findings, 12 important, 7 optional, all folded. The blocking ones: the single wake-up conversation came from a reached-and-quoted lead, so the bill ≥ 2,000 pilot is a hypothesis, not a measured result; the opt-out sentence exists only on the closing and wake-up templates (task 2.14); the one-seat fallback is 12-13 leads a week, not 20; the K6 tier-2 messages are a founder decision with a legal cost (decision 11), not a condition; the reactivation calendar had to be gated on the measured second seat and the cancelled wake-up count corrected to about 160. The important ones added the manual/automatic split of the re-entry triggers (2.15), the post-acceptance chain (2.16), the post-park wake-up load in 7.2, the absence and Imane rules, the pilots' lack of statistical power, the [O] markers on two legal readings, and section 7.8 (what can start on Monday without a build). The critic's own client-view count under v4: a never-reached Meta lead receives 9-10 touches in 12 months (8 in the first week; v3: 14), a quoted-undecided lead 12-13 (six calls, each with a reason), a K6 tier-2 lead 2 messages a year.

**Production access.** Read-only under the founder's standing approval: eight probe scripts through `manage.py shell`, each grepped for write tokens before running; counts and ids only; nothing written, migrated or restarted. Base on 1 November: 1,132 leads (1,126 the day before: 7 new arrivals).

**Data cautions that apply to every production number above.** Outcomes were mostly blank in September and reliably recorded from 1 October; Asmaa's October "reached" records (30 of 31 calls, 28 on 30/10) are excluded wherever a reach rate is quoted for the team; WhatsApp chatter lines are logged twice per step, so volumes use done steps; the eight quote openings under 2 minutes may be team devices; 8 weeks of cadence, 25 clean observations of the contact tail, 27 matured Standby leads, 6 acceptances with a date; commercial and agricultural cells are 74 and 2 leads.

**Research cautions.** No controlled study compares segmented with uniform cadences, post-quote plans, validity lengths or routing rules; the measured persistence curves come from survey methodology (IPA 2020, 64,635 numbers; Pew 2012; BLS) and are an upper bound for people who asked to be called; aged-lead yield tables are unsourced everywhere they appear; the Moroccan law is silent on hand-typed WhatsApp, calling hours and frequency; several Meta Help Center pages returned empty bodies to the research lane and are tagged [SNIP] in its notes (the verifier later read the WhatsApp FAQ and Meta's rate page in a browser: Morocco list rates on 1 November 2026 are 0.0414 $ per marketing message and 0.0230 $ per utility message; Meta's own pages disagree on the free entry point, 7 days on the developer page, 72 hours on an older business page). The cooling periods of section 2 and the yields of section 5.4 are conventions and inferences, labelled as such.

**Open legal questions** (for counsel, not for the ERP): does art. 10 reach a hand-typed WhatsApp or a human call; is a Meta form submission a consent, for how long, and what did the form's disclaimer say; does the Odoo file need an art. 12-1-b authorisation, and does an F211 receipt exist; cross-border transfer for the WhatsApp Platform (arts. 43-44, 60); does loi 31-08 art. 24 apply to WhatsApp advertisements.

**Not opened.** Odoo itself (its last-activity dates would sharpen K8); the BEACN report (press release only); the Sunergia and Kantar reports (secondary summaries); the Jornaya and Return Path figures were confirmed through secondary sources only.
