# ADSDEEP dossier — Audiences, ciblage, planification (recherché 2026-07-16)

## 1. Custom Audiences depuis le CRM

- `POST /act_<ID>/customaudiences` `subtype=CUSTOM` + `customer_file_source`
  (USER_PROVIDED_ONLY…). Max 500 audiences/compte.
- Peupler : `POST /<AUD_ID>/users` (add) / `DELETE .../users` /
  `POST /<AUD_ID>/usersreplace` (remplacement atomique, ne reset PAS le
  learning). Payload `{schema: ["EMAIL","PHONE",...], data: [[sha256,...]]}` —
  clés : EMAIL, PHONE (E.164 chiffres seuls), FN/LN/GEN/DOB*/CT/ST/ZIP/COUNTRY,
  MADID/EXTERN_ID (non hashés), LOOKALIKE_VALUE (valeur client).
- **SHA-256 uniquement**, normaliser avant hash. Upload par session
  (`session_id`, `batch_seq`, `last_batch_flag`) — **10 000 lignes max/appel**,
  fenêtre ~90 min ; réponse `num_received/num_invalid_entries`.
- **≥100 personnes matchées** pour être utilisable/seeder un lookalike.
- **Conditions d'utilisation** : 1er appel → 400 « Custom Audience Terms not
  yet accepted » tant qu'un HUMAIN n'a pas accepté sur
  business.facebook.com/ads/manage/customaudiences/tos/ — étape fondateur.
  + certification consentement des données 1st-party (RGPD-like).
  ⚠ GATE XMKT36 (consentement) : les tâches d'export d'audiences restent
  GATED décision fondateur — le dossier documente le COMMENT, pas le GO.

## 2. Lookalikes

- `subtype=LOOKALIKE`, `lookalike_spec {origin_audience_id, type:
  similarity|reach, country:"MA", ratio: 0.01-0.20, starting_ratio?}`.
- Seed ≥100 matchés (200+ conseillé). Prêt en ~1-6 h — poll `delivery_status`.
- Value-based : seed `is_value_based=1` + colonne LOOKALIKE_VALUE ;
  `lookalike_spec.type="custom_ratio"`.

## 3. Audiences site/engagement

- Site (pixel) : `rule` JSON (event_sources pixel, retention_seconds,
  filter url/event/category), rétention 1-180 j (730 j Purchase), `prefill`.
- ENGAGEMENT : event_sources type `page|ig_business|lead|canvas|...` —
  events utiles : `lead_generation_submitted/dropoff/opened` (formulaires !),
  `page_engaged`, `ig_business_profile_engaged`… Rétention : lead forms 90 j,
  Page/IG 730 j.

## 4. Targeting spec (adset)

- `geo_locations {countries:["MA"], cities:[{key,radius,distance_unit}]}`,
  `age_min/max`, `genders:[1,2]`, `custom_audiences`/`excluded_custom_audiences`,
  `flexible_spec` (OR intra-bloc, AND inter-blocs ; ids via /search).
- **v23 BREAKING : `targeting_automation.advantage_audience` DÉFAUT = 1 à la
  création** → TOUJOURS le poser explicitement (0|1) dans toute création ERP.
- `targeting_optimization: expansion_all|none` (Advantage detailed targeting —
  forcé ON pour link-clicks/LPV, ON-par-défaut pour Leads).
- `special_ad_categories` (campagne) : élargi jan-2025 aux services financiers
  (banque/assurance/crédit) — pertinent si TAQINOR pub du FINANCEMENT solaire
  (perd genre/zip/lookalikes). Sinon ["NONE"].

## 5. Estimations & recherche de ciblage

- `GET /<ADSET_ID>/delivery_estimate` (ou pré-création côté compte avec
  targeting_spec) → estimate_ready, estimate_dau, estimate_mau_*.
- **Audience Overlap : UI Ads Manager UNIQUEMENT — aucun endpoint public** ;
  ne pas le promettre dans l'ERP.
- Résolution d'intérêts : `GET /search?type=adinterest|adinterestsuggestion|
  adgeolocation|...&q=...`.

## 6. Dayparting

- `adset_schedule [{start_minute, end_minute, days[0-6], timezone_type
  USER|ADVERTISER}]` — heures PLEINES, ≥1 h ; **exige lifetime_budget** +
  start/end_time + `pacing_type` incluant "day_parting".
- Alternative budget QUOTIDIEN : règle native `adrules_library` avec
  schedule_spec (pause la nuit / reprise 8 h) — MAIS s'exécute côté Meta sans
  approbation (cf. dossier write-surface §6) → chez nous : proposer l'action
  planifiée via notre moteur de règles interne, approbation à l'armement.

## 7. Dépréciations/contraintes 2024-2026

- 2024-01 : purge des intérêts sensibles. **2025-03-31 : les EXCLUSIONS de
  detailed targeting sont SUPPRIMÉES** (plus d'exclusion d'intérêts).
- 2025-10→2026-01 (à re-vérifier sur la source officielle) : les ids
  d'intérêts pré-2025-10-08 cessent d'être servis.
- 2025-09-02 : interdiction des audiences impliquant état de santé/situation
  financière. 2024-10-30 : >100 métriques insights retirées (unique_*).
- 2025-05 : Offline Conversions API morte → CAPI datasets.
