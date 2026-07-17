# ADSDEEP dossier — Surface d'ÉCRITURE Meta (agir sur les ads) (recherché 2026-07-16)

Tout write ci-dessous = un simple `POST /<object_id>` → tout passe par la boîte
d'approbation (propose→approve→apply). RÈGLE #3 CLAUDE.md inchangée : les
campagnes NAISSENT PAUSED ; le client n'expose AUCUNE méthode d'activation.

## 1. Budgets

- AdSet : `daily_budget` / `lifetime_budget` (unités MINEURES — cents),
  `lifetime_budget` exige `end_time` ; sous-contrôles `daily_min_spend_target`,
  `daily_spend_cap`.
- Campagne (Advantage campaign budget, ex-CBO) : mêmes champs sur la campagne ;
  budget campagne non-nul = CBO ON. Tous les adsets enfants : même type de
  budget + même `bid_strategy`. ≥70 adsets → bid_strategy/CBO verrouillés.
- Minimums : PAS de table codée en dur — `GET /act_<ID>/minimum_budgets`.
- Pacing : dépassement quotidien documenté jusqu'à 25 % (des sources 2026
  parlent de 75 % côté UI — coder contre les 25 % documentés).
- `spend_cap` : existe au niveau CAMPAGNE (plafond total campagne) ET au niveau
  COMPTE (`POST /act_<ID>` — 0 = sans plafond ; atteint = TOUT le compte
  s'arrête ; `spend_cap_action=reset|delete`).

## 2. Learning phase / « significant edits »

- `GET /<ADSET_ID>?fields=learning_stage_info` → `{status: LEARNING|SUCCESS|
  FAIL, conversions, last_sig_edit_ts, attribution_windows}`.
- Éditions qui RÉINITIALISENT l'apprentissage (documenté) : budget >20 %,
  bid/bid_strategy, ciblage, création/édition de créatif. (2026 « Andromeda » :
  seuils resserrés — avertir large.)
- → la boîte d'approbation DOIT afficher un avertissement « cette action
  réinitialise l'apprentissage » quand le seuil est franchi.

## 3. Statuts

- Écriture `status` : `ACTIVE|PAUSED|ARCHIVED|DELETED` (création : seuls
  ACTIVE/PAUSED). ARCHIVED → seuls name/status éditables, retour interdit ;
  DELETED → seul name ; stats des supprimés lisibles 28 j ; max 100 000
  archivés par type.
- `effective_status` (lecture) : + `CAMPAIGN_PAUSED`, `PENDING_REVIEW`,
  `WITH_ISSUES`, `DISABLED`… (hérite du parent).
- INVARIANT REPO : pas de méthode unpause/activate dans meta_client — la mise
  en ligne reste un geste humain dans Ads Manager. Les ADSDEEP ne changent pas ça.

## 4. Éditer le créatif/texte d'une ad EXISTANTE

- **AdCreative = write-once** pour le contenu (`POST /<CREATIVE_ID>` ne change
  que name/status/adlabels). Le SEUL chemin d'édition de texte :
  1. `POST /act_<ID>/adcreatives` → NOUVEAU creative avec le nouveau texte ;
  2. `POST /<AD_ID>` avec `{"creative": {"creative_id": "<NOUVEAU>"}}`.
  → même ad_id, historique insights conservé ; MAIS = significant edit
  (re-review + reset learning).
- Preuve sociale : `object_story_id` (post existant) la CONSERVE ;
  `object_story_spec` crée un post NEUF (compteurs à zéro). Changer le texte ⇒
  nouveau post ⇒ perte des likes/commentaires : l'UI doit l'annoncer.

## 5. Param maps création (CTWA / Lead Ads) — objectifs ODAX v21+

- CTWA : campagne `objective` ∈ {OUTCOME_ENGAGEMENT, OUTCOME_LEADS,
  OUTCOME_SALES, OUTCOME_TRAFFIC} ; adset `destination_type: "WHATSAPP"`,
  `optimization_goal: "CONVERSATIONS"`, `promoted_object: {page_id,
  whatsapp_phone_number}` ; creative `link_data.link:
  "https://api.whatsapp.com/send"`, `call_to_action: {type: "WHATSAPP_MESSAGE",
  value: {app_destination: "WHATSAPP"}}`, `page_welcome_message` optionnel.
- Lead Ads : campagne `OUTCOME_LEADS` + `special_ad_categories: ["NONE"]` ;
  adset `destination_type: "ON_AD"`, `optimization_goal: LEAD_GENERATION|
  QUALITY_LEAD` (+`pixel_id` dans promoted_object pour QUALITY_LEAD),
  `billing_event: "IMPRESSIONS"` ; creative CTA `{type: SIGN_UP|GET_QUOTE|…,
  value: {lead_gen_form_id}}` ; formulaires gérés via `/<PAGE>/leadgen_forms`.
- Passage ACTIVE ⇒ review Meta (`PENDING_REVIEW`) — chokepoint humain naturel.

## 6. Automated Rules NATIVES Meta (`/act_<ID>/adrules_library`)

- `evaluation_spec` : `evaluation_type SCHEDULE|TRIGGER`, `filters[{field,
  value,operator}]` (GREATER_THAN, IN_RANGE, CONTAIN, ANY/ALL/NONE…),
  `trigger` (STATS_CHANGE, STATS_MILESTONE…).
- `execution_spec.execution_type` : `PAUSE`, `UNPAUSE`, `NOTIFICATION`,
  `CHANGE_BUDGET`, `CHANGE_CAMPAIGN_BUDGET`, `CHANGE_BID`, `ROTATE`,
  `REBALANCE_BUDGET`, `PING_ENDPOINT`.
- `schedule_spec` : DAILY/HOURLY/SEMI_HOURLY/CUSTOM (fenêtres minutes/jours).
- ⚠ Ces règles s'exécutent CÔTÉ META, SANS boîte d'approbation → dans notre
  modèle sûreté, ne créer que des règles `NOTIFICATION` (le geste réel reste
  chez nous), sauf le homme-mort ADSENG19 (gated fondateur).

## 7. A/B tests

- `POST /act_<ID>/ad_studies` — vivant en 2026, types `SPLIT_TEST` et
  `SPLIT_TEST_V2` (créatif, 2-5 cellules via `creative_test_config`).
- `cells[]` : name, `treatment_percentage` (≥10 %, somme 100), ids campagne/
  adset/ad (≤100 entités/cellule, ≤150 cellules, ≤100 études actives).
- `treatment_percentage`/`start_time` IMMUABLES après lancement ; `end_time`
  éditable.

## 8. Batch + erreurs + idempotence

- `POST graph.facebook.com/?batch=[...]` — **50 opérations max**, chaînage par
  `name` + `{result=<name>:$.path}`, PAS transactionnel (inspecter chaque
  sous-réponse).
- Erreurs : `{error: {message, type, code, error_subcode, error_user_title,
  error_user_msg, fbtrace_id}}` — `error_user_msg` est FAIT pour être montré à
  l'approbateur ; la logique se code sur code/subcode.
- **AUCUNE clé d'idempotence** sur les writes Graph — un retry peut dupliquer.
  Le journal EngineAction (ids écrits AVANT retry) est l'unique dédup sûr.
