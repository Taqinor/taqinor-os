# AR_RESYNC_BRIEF — Arabic pages to bring in line with the reworked French

Prepared for a **native Arabic reviewer**. We are deliberately NOT AI-generating
Arabic prose. This brief tells you, page by page, what changed on the French side
and exactly which Arabic line to touch. Quotes are copied verbatim from the files.

- FR source files: `apps/web/src/pages/<name>.astro`
- AR files to edit: `apps/web/src/pages/ar/<name>.astro` (and `ar/guides/…`)
- **Keep all numbers in Latin/Western digits** (the AR pages already do this — stay consistent).
- **Internal links**: AR pages already wrap hrefs in `L(...)` / `localizeNavHref` — do not touch the link plumbing, only the visible Arabic text.
- **Do not touch the FR files.**

Legend: 🔴 = LIVE factual error / must-fix before go-live · 🟠 = content the FR
gained and the AR is missing (needs real Arabic writing) · 🟡 = minor / polish.

---

## 🔴 URGENT — live factual errors / inconsistencies (fix first)

These are not stylistic; they are wrong or self-contradicting as published.

### 1. `ar/à-propos.astro` line 85 — "twenty years" should be "ten years"
The Arabic says the founder has been reading this kind of calculation **for twenty
years**, but the whole rest of the page (and the FR source) says **more than ten
years**. It contradicts the same page's own line 30 / 61 / 76 / 141 ("أكثر من عشر
سنوات" / "+10 سنوات") and the FR ("depuis plus de dix ans").

Current AR (line 85):
> «… وكل شيء يحسمه شخص مهنته، **منذ عشرين سنة**، قراءة هذا النوع من الحساب.»

FR equivalent (à-propos line 89):
> «… tranché par quelqu'un dont le métier, **depuis plus de dix ans**, est de lire ce genre de calcul.»

**Action:** change «منذ عشرين سنة» → the correct phrasing for *more than ten years*
(e.g. «منذ أكثر من عشر سنوات»). NB the noun must agree (سنوات, not سنة). I did NOT
edit this automatically because the digit change also changes the grammatical
agreement, which needs an Arabic eye.
*(Other pages — `professionnel` line 75, `résidentiel` line 138, `index` line 175
— also contain «عشرين سنة» / «خمس وعشرين سنة», but those are CORRECT translations
of "vingt ans" / "vingt-cinq ans" in their context. Only `à-propos` line 85 is wrong.)*

### 2. "الفصل 33" vs "المادة 33" — inconsistent legal term for Article 33
Moroccan legal usage for an article of a law is **المادة** (article). Most AR pages
correctly say **«المادة 33»** (regularization, loi-82-21, faq, nos-solutions,
pourquoi-taqinor, à-propos, contact). But **`ar/index.astro` uses «الفصل 33» twice**:
- line 44 (homepage FAQ answer): «يفتح **الفصل 33** من القانون 82-21 …»
- line 68 (solutions card): «تسوية وضعية التركيبات القائمة عبر **الفصل 33**.»

**Action:** harmonise the homepage to «المادة 33» to match every other AR page and
the legal term, unless you (the reviewer) judge «الفصل» preferable — in which case
change ALL pages, not just these. Pick one and make it consistent site-wide.

> Verified clean: no «رقم 04/26» / "ANRE 04/26" anywhere, and no «المادتين 25 و 27»
> mistake remains — the earlier fix on `ar/regularization-article-33.astro` held
> (it correctly shows «المادة 25» / «المادة 28» / «المادة 29» / «المادة 32»).

---

## Per-page change list

### `ar/index.astro` (homepage)
- Figures, FAQ (5 items), journey (6 steps), solutions (6) all match FR 1:1. ✅
- 🔴 «الفصل 33» → «المادة 33» (see urgent item 2, lines 44 & 68).
- 🟡 Otherwise faithful. No other action.

### `ar/regularization-article-33.astro`
- 🟠 **Lead paragraph lost two facts the FR now states.**
  FR lead (lines 53–58) now says the decree was *published in the Bulletin Officiel
  on **9 March 2026*** and *entered into force on 9 June 2026*, **and** that the
  ANRE decision *sets the buy-back tariff for the surplus* ("fixe le tarif de rachat
  du surplus").
  Current AR (lines 57–61) only says:
  > «المرسوم 2-25-100 وقرار ANRE دخلا حيّز التنفيذ في 9 يونيو 2026. منذ ذلك التاريخ، يُطبَّق نظام القانون 82-21 …»
  **Action:** add the **9 March 2026 (9 مارس 2026)** BO-publication date, and that
  the ANRE decision **sets the surplus buy-back tariff** ("يحدّد تعريفة شراء الفائض"
  or similar). Keep "9 يونيو 2026" as the entry-into-force date. Do NOT invent a
  tariff figure — the FR doesn't give one here either.
- ✅ Steps, sanctions (articles 25/28/29/32), 18 months, all correct.

### `ar/loi-82-21.astro`
- 🟡 **Missing the two reference-link buttons** the FR has under "Les trois régimes
  en détail" (FR lines 73–76): «Régimes pour un site professionnel →» and «Loi 82-21
  expliquée simplement →». The AR ends that section without them (after line 74).
  **Action:** add the two link buttons (text: «الأنظمة لموقع مهني →» and «القانون
  82-21 ببساطة →», linking to `/professionnel` and `/guides/loi-82-21-expliquee`
  via `L(...)`). Low priority — purely an internal-linking parity gap.
- ✅ Hero, decree date, regime selector, Article-33 CTA all match.

### `ar/nos-solutions.astro`
- 🟠 **Missing the FR closing paragraph** (FR lines 115–119) under the "Pas sûr de
  la solution…" section: a sentence inviting EV-driver readers to see
  «recharger votre voiture au solaire» and «parcourez tous nos guides», with two
  inline links (`/recharge-voiture-electrique-solaire`, `/guides`).
  The AR section (lines 109–117) ends right after the CTA button, without this line.
  **Action:** translate and add that closing paragraph + its two links. (Note: the
  EV page and guides hub may only exist in FR — `L(...)` will fall back to FR, which
  is acceptable, never a dead link.)
- ✅ 6 solution cards + intro match.

### `ar/pourquoi-taqinor.astro`
- ✅ All four pillars, figures (43,48 kWc / 25 ans / 0 MAD / 11 kW / 10–25 ans /
  9 June 2026), proof section match FR.
- 🟡 Pillar 04 title softened: FR «Cinq marques tier-1, et rien d'anonyme sur le toit»
  → AR «لائحة قصيرة من علامات الصف الأول» ("a short list of tier-1 brands"). The
  "nothing anonymous on the roof" idea survives in the AR body, so this is optional.
  Reviewer may tighten the title to echo FR if desired. No factual issue.

### `ar/à-propos.astro`
- 🔴 Line 85 "twenty years" error — see urgent item 1.
- ✅ Founder pedigree (Huawei/Ericsson/STMicroelectronics, docteur-ingénieur,
  10+ ans R&D), 4 method steps, tier-1 brand list all match.

### `ar/équipement.astro`
- ✅ All 6 product cards, every spec/figure (705–720 Wc, 100 GW, IEC codes,
  5–30 kW, 6 000 cycles, 90 % DoD, 84,8 %, warranties 12/25/10/20/2) exact.
- 🟡 OND-1 (Deye hybride) body is reworded into a metaphor: FR opens «On retient le
  Deye hybride pour une raison concrète : quand le réseau saute, il bascule sur
  batterie en quelques millisecondes…»; AR opens «العاكس الهجين هو قائد الأوركسترا…»
  ("the orchestra conductor"). Content kept; the millisecond grid-failover detail is
  dropped from AR. Reviewer may restore the "few milliseconds on grid failure" point
  if matching FR closely matters. No factual error.

### `ar/maintenance-monitoring.astro`
- ✅ Faithful: 3 suivi cards, dongle WiFi/Ethernet, Deye Cloud, no invented SLA,
  closing link block all match FR. No action.

### `ar/marocains-du-monde.astro`
- 🟠 **MAJOR: the whole "deepened diaspora" section is missing.** The FR gained a
  full section «Trois craintes que personne ne formule à voix haute» (FR lines
  86–134) — three detailed worry-cards a buyer-from-abroad actually feels:
  1. **La confiance** — «Je ne serai pas là pour vérifier» (written quote, staged
     payment on progress, appoint a trusted relative to witness, pay the balance only
     once production reads on Deye Cloud).
  2. **Le paiement** — «Comment je paie depuis l'étranger ?» (quote in dirhams, no
     hidden conversion, we are not a bank, we never touch your forex).
  3. **La maison** — «C'est la maison de mes parents» (the family home, careful
     fixings, clean cabling, nothing that disfigures the façade).
  The AR jumps straight from the WhatsApp section (ends line 94) to the
  "Suivi à distance + conformité" section (line 96) — this whole 3-card block is absent.
  **Action:** translate and insert the three-craintes section between those two AR
  sections. This is the single biggest content gap in the AR set and is the heart of
  the diaspora pitch — it needs genuine, warm Arabic writing (not literal), so it is
  left entirely to you.
- 🟡 Étapes were localised nicely (AR step 1 says «من على أريكتك في باريس أو مونتريال
  أو دبي»). Fine — keep.
- ✅ Hero, WhatsApp CTA, monitoring/admin/cities cards match.

### `ar/faq.astro`
- 🟠 **AR has only 12 of the FR's 20 questions.** The FR (`faq.astro`) lists 20 Q&A;
  the AR carries a trimmed 12. Missing from AR (all present in FR):
  1. «Comment est calculé le prix d'une installation ?» (the 6 kWc / 60 000–75 000 MAD example)
  2. «Les panneaux fonctionnent-ils la nuit ou par temps nuageux ?» (300+ jours de soleil)
  3. «L'ombre réduit-elle beaucoup la production ?» (20–30 %, optimiseurs/micro-onduleurs)
  4. «Faut-il nettoyer les panneaux, et à quelle fréquence ?»
  5. «Que se passe-t-il si le réseau tombe en panne ?» (anti-îlotage, hybride+batterie)
  6. «Combien de temps dure une batterie LFP ?» (6 000 cycles, 10 ans/70 %, 12–15 ans)
  7. «Puis-je recharger ma voiture électrique avec mes panneaux ?» (15 kWh/100 km, Zappi/Wallbox, ~93 MAD/100 km essence)
  8. «Faut-il une batterie pour recharger la voiture la nuit ?»
  **Decision needed from the reviewer / founder:** either (a) translate the 8 missing
  questions so AR reaches parity with FR, or (b) deliberately keep AR shorter. The AR
  meta description does NOT claim "20 questions", so there is **no live error** — but
  the AR FAQ is materially thinner than FR. Recommend translating at least the
  high-value ones (price calc, night/cloud, shade, battery lifetime, EV) for SEO and
  honesty parity. Each carries figures — keep them exact in Latin digits.
- ✅ The 12 present answers match their FR counterparts exactly (figures included).

### `ar/pompage-solaire.astro`
- ✅ Faithful: 4 étapes, 4 variables (Débit/HMT/forage/besoins), the **VAT-exemption =
  agricultural pumping ONLY, never residential rooftop PV** point is preserved exactly.
  No action.

### `ar/batteries-stockage.astro`
- 🟠 **MAJOR: the AR is missing two whole blocks the FR (W130) gained.**
  1. **A 5-item visual FAQ** (FR `faqItems`, lines 52–73), including the
     store-vs-sell answer that carries NEW live figures: injection capped at
     **20 % of annual production**, ANRE buy-back **0,18–0,21 DH/kWh**, grid purchase
     **0,90–1,66 DH/kWh**, "stored kWh worth **4–9×** an exported one", plus EPS mode /
     **≈ 4 ms** failover, and the **5–10 / 10–20 / 20+ kWh** sizing tiers.
  2. **A "Guides batteries & stockage" 3-card section** (FR lines 189–214) linking
     `/guides/batterie-lithium-ou-gel`, `/guides/quelle-taille-de-batterie`,
     `/guides/electricite-pendant-les-coupures`.
  The AR jumps from the install-cards block (ends line 149) straight to the closing
  links (line 151) — both blocks are absent.
  **Action:** translate and add (1) the 5-item FAQ and (2) the 3 guide cards.
  Keep every figure exact. ⚠️ Those three guide slugs may have **no AR version** —
  `L(...)` will fall back to FR, which is acceptable. Also note one AR detail to fix
  while you're in here: the warranty spec row (line 28) shows the value as `'10 ans'`
  (French) whereas the FR adds «capacité conservée ≥ 70 %» — consider `'10 سنوات،
  السعة المحفوظة ≥ 70 %'` to match FR (`équipement` already uses «10 سنوات»).
- ✅ Hero, 2 cas cards, 6 specs, 3 real installs (15/10/5 kWh) match.

### `ar/guides/faut-il-des-batteries.astro`
- 🟠 **Missing the two new figure-bearing sections the FR added.** The AR has 4
  sections (intro, "diurne", "nocturne", "ce que dit la courbe"). The FR now has 6,
  adding:
  - «Ce qu'une batterie coûte, et ce qu'un kWh stocké vaut» — LFP **3 000–4 000 DH/kWh**;
    10 kWh ≈ **30 000–40 000 DH**; rachat **0,18–0,21 DH/kWh** vs achat **0,90–1,66 DH/kWh**;
    a stored kWh worth **4–9×** an exported one.
  - «Combien de temps avant qu'elle se rembourse» — payback **5–7 ans** without storage,
    **+1–3 ans** with a battery; **6 000 cycles**, 10-year / ≥ 70 % warranty.
  Note the AR file's own header comment still says "no figure, no price, no payback" —
  that policy is now superseded by the reworked FR; the comment can be updated too.
  **Action:** translate and add the two missing sections (with figures, Latin digits).

### `ar/guides/onduleur-hybride-ou-reseau.astro`
- 🟠 **Missing the new law-82-21 section.** The FR added «Pourquoi la loi 82-21 pèse
  dans la balance» (FR lines 73–83): injection capped at **20 %** of annual production,
  surplus bought at **0,18–0,21 DH/kWh** vs grid purchase **0,90–1,66 DH/kWh**, and
  how that reinforces the day-profile→grid / evening-profile→hybrid logic. The AR has
  only hybrid / réseau / "comment on choisit" (no 82-21 section).
  **Action:** translate and insert this section before "كيف نختار" (the AR
  "comment on choisit", line 71).
- 🟡 The AR hybrid (Deye) paragraph is also a touch shorter than FR — FR adds the
  nuance «cette polyvalence a un prix — il faut ajouter la batterie… une étape de
  conversion de plus». Optional to restore for full parity.

### `ar/guides/loi-82-21-expliquee.astro`
- 🟡 **Missing the named grid operators.** FR régime 02 «Accord de raccordement»
  (FR line 40) now names them: «l'ONEE dans la plupart des régions, ou la régie
  locale… (**Lydec** à Casablanca, **Redal** à Rabat, **Amendis** à Tanger)». The AR
  régime 02 (line 43) just says «اتفاق ربط من المدبّر» without ONEE/Lydec/Redal/Amendis.
  **Action:** add the operator names to the AR régime-02 body for parity. Low priority.
- ✅ 3 regimes, thresholds (11 kW / 5 MW), 9 June 2026, Article-33 18-month window
  all match.

---

## Summary for the reviewer

- **Must-fix before go-live (🔴):** `à-propos` line 85 (twenty → ten years), and the
  «الفصل 33» vs «المادة 33» term unification on `index`.
- **Biggest content gaps (🟠), in priority order:**
  1. `marocains-du-monde` — add the 3-card "Trois craintes" diaspora section.
  2. `batteries-stockage` — add the 5-item FAQ + 3 guide cards (new 82-21/tariff figures).
  3. `guides/faut-il-des-batteries` — add the 2 new figure sections.
  4. `guides/onduleur-hybride-ou-reseau` — add the 82-21 section.
  5. `faq` — decide on the 8 missing questions (parity vs intentional trim).
  6. `regularization-article-33` lead — add 9 Mar 2026 BO date + ANRE surplus-tariff point.
  7. `nos-solutions` — add the EV/guides closing paragraph.
- **Polish (🟡):** `loi-82-21` ref-link buttons; `loi-82-21-expliquee` operator names;
  `batteries-stockage` warranty "≥ 70 %"; `équipement` OND-1 wording; `pourquoi`
  pillar-04 title.
- **All numeric figures in the AR pages were checked against FR and are exact**
  (kWc, kWh, %, MAD, years, dates, fines, article numbers). The only numeric problem
  is the `à-propos` "twenty years" slip above.
