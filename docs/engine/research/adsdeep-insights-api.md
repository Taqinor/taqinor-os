# ADSDEEP dossier — Meta Insights API (Graph v21–v25, recherché 2026-07-16)

Source de vérité pour les tâches ADSDEEP de synchro/lecture des métriques. Champs
vérifiés contre `facebook-python-business-sdk/adsinsights.py` + docs Meta.

## 1. Edge `/insights` (campagne / adset / AD)

`GET /<ID>/insights?level=ad&fields=...` — `level` ∈ `ad|adset|campaign|account`
détermine la granularité des lignes (on peut interroger l'edge du COMPTE avec
`level=ad` : une ligne par ad).

Champs de diffusion : `spend`, `impressions`, `reach` (estimé), `frequency`
(estimé), `clicks`, `unique_clicks`, `ctr`, `unique_ctr`, `cpc`, `cpm`, `cpp`,
`inline_link_clicks`, `inline_link_click_ctr`, `outbound_clicks`,
`outbound_clicks_ctr`, `social_spend`.

Champs de conversion : `actions` (tableau AdsActionStats `{action_type, value,
<fenêtre>_click, <fenêtre>_view}`), `action_values`, `unique_actions`,
`cost_per_action_type`, `cost_per_conversion`, `cost_per_result`,
`conversions`, `results` (LA métrique alignée sur l'objectif — ce qu'Ads
Manager affiche comme « Résultats »).

### Action types CTWA (WhatsApp)
- `onsite_conversion.messaging_conversation_started_7d` — LA métrique
  « conversations démarrées » (1 conversation par fenêtre glissante de 7 j, pas
  1 par message). C'est le `results` habituel des campagnes CTWA.
- `onsite_conversion.messaging_first_reply` — nouvelles conversations
  (première réponse du business).
- `onsite_conversion.messaging_block`, `onsite_conversion.messaging_user_subscribed`.
- Les issues POST-conversation (devis envoyé…) ne passent PAS par /insights —
  c'est la Conversions API for Business Messaging (`action_source:
  business_messaging`, `ctwa_clid`).

### Action types Lead forms
- `lead` — TOUS les leads (Instant Forms + pixel/CAPI confondus) ; `results`
  habituel quand `optimization_goal=LEAD_GENERATION`.
- `onsite_conversion.lead_grouped` — leads on-Facebook dédupliqués.
- `leadgen_grouped` — Instant Forms + Messenger.
- `offsite_conversion.fb_pixel_lead` — leads pixel site web.

Sources : developers.facebook.com/docs/marketing-api/reference/ads-action-stats/ ;
…/reference/ad-account/insights/

## 2. Breakdowns

Param `breakdowns` : `age`, `gender`, `country`, `region`, `dma`,
`device_platform`, `impression_device`, `publisher_platform`,
`platform_position`, `product_id`, `frequency_value`,
`hourly_stats_aggregated_by_advertiser_time_zone`,
`hourly_stats_aggregated_by_audience_time_zone`, breakdowns d'assets
(`ad_format_asset`, `body_asset`, `image_asset`, `video_asset`, `title_asset`,
`call_to_action_asset`, `link_url_asset`, `description_asset`).

Param séparé `action_breakdowns` (segmente les tableaux `actions`) :
`action_type` (défaut), `action_device`, `action_destination`,
`action_target_id`, `action_video_sound`, `action_video_type`,
`action_carousel_card_id/name`, `conversion_destination`…

Combos autorisés (liste NON exhaustive, seules certaines permutations passent) :
- `age`+`gender` ensemble ; chacun avec `action_type`/`action_target_id`.
- `country`, `region`, `publisher_platform` chacun avec `action_type`.
- `action_device` + `impression_device`/`publisher_platform`/`platform_position`.
- Horaires (`hourly_stats_*`) seuls (+`action_type`) — PAS combinables large.

Champs qui DISPARAISSENT sous breakdown :
- Horaires : perdent tous les `unique_*`, `reach`, `frequency`.
- `dma` incompatible `video_thruplay_watched_actions` ; `region` incompatible
  `video_p*_watched_actions`.
- Breakdowns Dynamic-Creative : champs restreints à `impressions,clicks,spend,
  reach,actions,action_values`.

Source : developers.facebook.com/docs/marketing-api/insights/breakdowns/

## 3. Métriques vidéo (toutes en forme AdsActionStats, PAS scalaires)

`video_play_actions` (flag « in development »), `video_6/15/30_sec_watched_actions`,
`video_avg_time_watched_actions` (secondes, replays inclus),
`video_p25/50/75/95/100_watched_actions` (skip-to-point inclus),
`video_thruplay_watched_actions` (complet si <15 s sinon ≥15 s — métrique
facturable ThruPlay).

Formules « creative analytics » dérivées (référentiel concurrents) :
hook rate = video_3s (ou 6s)/impressions ; hold rate = thruplay/plays.

## 4. Fenêtres temporelles, attribution, jobs async

- `time_increment=1` → une ligne par JOUR (ignoré si `time_ranges` pluriel).
- `date_preset=maximum` (remplace `lifetime` depuis v10) — plafond 37 mois.
- `action_attribution_windows` : défaut `["7d_click","1d_view"]` ; valeurs
  vivantes `1d_click,7d_click,28d_click,1d_view,1d_ev`.
  **DEPRECATED 2026-01-12 : `7d_view` et `28d_view`** — les demander renvoie
  silencieusement AUCUNE donnée (pas d'erreur). NE JAMAIS les coder.
- Rétention (depuis 2026-01-12) : champs `unique_*` + breakdowns horaires →
  13 mois ; `frequency_value` → 6 mois ; agrégats simples → 37 mois.
- Async (obligatoire pour les gros pulls) : `POST /<id>/insights` → `report_run_id`
  → poll `GET /<report_run_id>` (`async_status`: Job Not Started→Started→Running→
  Completed/Failed/Skipped, `async_percent_completion`) → `GET /<report_run_id>/insights`.
  Jusqu'à 60 min ; `report_run_id` expire après 30 j ; en cas de Job Failed
  sans détail → réduire la plage/cardinalité.

Source : developers.facebook.com/docs/marketing-api/insights/ ;
ppc.land/meta-restricts-attribution-windows-and-data-retention-in-ads-insights-api/

## 5. Rate limits & erreurs

- Tiers : Limited (Dev) vs Full Access (≥500 appels Marketing API/15 j, <15 % erreurs).
- BUC par compte, fenêtre 1 h : `ads_insights` = (190 000 Full | 600 Dev)
  + 400×ads actives − 0,001×user_errors ; `ads_management` = (100 000 | 300)
  + 40×ads actives. Budgets CPU/wall time séparés.
- En-têtes à LIRE sur chaque réponse : `X-Business-Use-Case-Usage`
  (call_count, total_cputime, total_time, estimated_time_to_regain_access),
  `X-Ad-Account-Usage`, `X-FB-Ads-Insights-Throttle`
  (app_id_util_pct, acc_id_util_pct, ads_api_access_tier).
- Erreurs : `4` (app), `17` (user), `32` (page), `613` (BUC compte) → backoff
  exponentiel ; coder sur le CODE numérique, jamais le message.
- `filtering=[{field,operator,value}]` (GREATER_THAN, IN_RANGE, CONTAIN…),
  `sort` (`actions:link_click_descending`), `summary` pour les totaux.

## 6. Dépréciations 2025-2026 à éviter

- `7d_view`/`28d_view` (cf. §4). `date_preset=lifetime` (mort depuis v10).
- `breakdowns=mmm` → async-only. `instagram_story_id` (v22) →
  `source_instagram_media_id`. `promotions` → `promotion_details`.
- Épingler une version récente (v24/v25 mi-2026) et suivre
  developers.facebook.com/docs/graph-api/changelog.
