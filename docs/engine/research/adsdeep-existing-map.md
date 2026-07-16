# ADSDEEP dossier — Carte de l'EXISTANT adsengine vs cibles (scout 2026-07-16)

À lire AVANT toute tâche ADSDEEP : ce qui existe déjà, ce qui est affamé de
données, ce qui est réellement neuf. (Code lu, pas déduit des docs.)

## Réponses aux 6 questions clés

1. **InsightSnapshot par AD ?** Le modèle OUI (FK générique campagne/adset/ad ;
   champs date/spend/results/frequency/cpl, unique (company, ct, object, date)),
   la prod NON : l'unique writer est `tasks._sync_company` → boucle CAMPAGNES
   seulement. Conséquence : `attribution.py` (échelle lead→ad à 5 niveaux,
   coût/signature PAR AD — déjà codée !), `rules_engine._eval_frequency_high`,
   `budget_applier.has_consistent_spend` lisent des snapshots ad/adset
   STRUCTURELLEMENT VIDES. Un seul fix de sync débloque tous ces consommateurs.
2. **Contenu créatif stocké ?** `CreativeAsset` = NOTRE bibliothèque (hook_id/
   hook_text/primary_text/cta/file_key MinIO) — PAS un miroir du créatif LIVE
   Meta (AdMirror n'a que meta_id/name/status). Et le serializer n'expose pas
   de `preview_url` résolvable depuis file_key alors que CreativeLibraryScreen
   attend `a.preview_url || a.file_url` → previews cassés aujourd'hui.
3. **Ingestion de leads Meta ?** DÉJÀ CONSTRUITE dans `apps/crm/webhooks.py`
   (`meta_lead_ads_webhook`, XMKT32 + ADSENG1 : capture ad_id/form_id/
   leadgen_id), gated par META_LEAD_ADS_VERIFY_TOKEN/ACCESS_TOKEN. NE PAS
   reconstruire. `capi_crm.py` (ADSENG32) = OUTBOUND stages CRM ; QJ9 = CAPI
   devis accepté. `backfill_meta_lead_attribution` (commande crm) backfille
   l'attribution des leads DÉJÀ capturés (pas l'historique insights).
4. **EngineAction kinds** : CREATE_CAMPAIGN/CREATE_ADSET/CREATE_AD/
   ROTATE_CREATIVE/REBALANCE_BUDGET/PAUSE + treasury (pause_for_month,
   increase_pace, rebalance_adset_budget, enable_cbo propose-only).
   `services.py` : propose (reason_fr obligatoire, policy créa) → approve
   (select_for_update) → apply (CAS atomique, garde-fous : plafond quotidien,
   ±15 %/j budget, PAUSED-only, baseline 7 j treasury) → dispatch meta_client ;
   échec ⇒ ECHOUEE. `execute_auto_action` (ENG8) : ROTATE/REBALANCE si toggles
   GuardrailConfig, toujours journalisé.
5. **FlightRunner** : 3 gabarits fixes (resid_ctwa, agri_pompage, b2b_leadform),
   crée campagne+adsets PAUSED idempotents ; ne crée PAS d'ads au launch ; le
   go-live est humain par principe.
6. **reporting.variant_table** = reshape d'`attribution.variant_attribution`
   (spend par ad depuis les snapshots AD — vides, cf. 1 ; leads via
   `crm.selectors.attribution_lead_rows` ; échelle meta_ad_id → utm_content
   'ad-<id>' → nom → non-résolu ; coût/lead qualifié + coût/signature par ad
   avec lead_ids traçables).

## Modèles existants (clé)
MetaConnection (+currency), GuardrailConfig (plafonds, bandes, toggles auto),
AdCampaignMirror/AdSetMirror/AdMirror (meta_id/name/status/budget/objective),
InsightSnapshot (4 métriques), EngineAction, WeeklyBrief, EngineAlert,
CreativeAsset/CreativePolicy, Experiment/ExperimentArm/ArmDailyStat/DecisionLog,
RulePolicy (dry_run défaut), AnomalyEvent, PacingState, CreativeGenerationBatch/
CreativeBacklogItem, FlightPlan/FlightPhase, ReconciliationSnapshot.

## Endpoints/écrans : voir urls.py — console 13 écrans déjà en place
(Dashboard hero coût/signature + drill Odoo, Campagnes+sync, Approbations,
Créathèque, Expérimentations, Plan de vol, Backlog, Règles, Simulation,
Reporting, Brief, Journal, Connexion). ADSENGINT1/2 : cases PLAN.md périmées —
DÉJÀ implémentés (vérifié). ADSENGINT3 (e2e Playwright) : réellement manquant.

## GAPS réels (cibles ADSDEEP)
- (a) Sync insights niveau ad/adset (débloque per-ad reporting + règles + CBO).
- (b) Attribution Odoo par AD (aujourd'hui campagne max, match téléphone).
- (c) Miroir du créatif LIVE Meta (copy/vidéo/image) + résolution médias.
- (d) Breakdowns démo/placement/horaire (AUCUNE colonne aujourd'hui).
- (e) Métrique conversations WhatsApp dédiée (ArmDailyStat.conversations n'est
  peuplé que par tests/seed).
- (f) Édition texte/créatif d'une ad existante (aucun update_ad dans
  meta_client — ROTATE crée une ad neuve, il n'édite pas).
- (g) Push CAPI « deal signé Odoo » (rien ne pousse quand odoo_signed_deals
  trouve une signature).
- (h) Backfill HISTORIQUE des insights ad-level (la commande crm ne couvre que
  l'attribution des leads).

## GATED à respecter (verbatim PLAN.md)
- ENG : alertes WhatsApp BSP ; commentaire LLM brief ; adaptateur Higgsfield ;
  export d'audiences Meta (XMKT36, consentement) ; facturation tenants (NTSUB) ;
  fusion SCA/ARC white-label.
- ADSENG19 (règle Meta homme-mort — décision fondateur), ADSENG34 (boucle
  ctwa_clid — exige WhatsApp Cloud API/BSP, coût), ADSENG50/51/52 (Google/
  Snapchat/TikTok), publication organique `pages_manage_posts` (App Review) —
  **partiellement LEVÉ par instruction fondateur du 2026-07-16 : « real post
  editing capabilities » demandé explicitement → les tâches ADSDEEP d'édition
  de posts sont autorisées, l'App Review reste un préalable opérationnel
  documenté**, export audiences reste gated consentement.
