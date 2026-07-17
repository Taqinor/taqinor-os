# ADSDEEP dossier — Leads Meta + boucle CAPI signatures (recherché 2026-07-16)

## 1. Lire les leads

`GET /<FORM_ID>/leads` et `GET /<AD_ID>/leads` — champs : `id` (lead 15-17
chiffres), `created_time`, `ad_id` (alias historique `adgroup_id`), `form_id`,
`field_data[]` (`{name, values[]}` par question). `adset_id`/`campaign_id` ne
sont PAS sur le lead → résoudre via `GET /<ad_id>?fields=adset_id,campaign_id`.

- Pagination curseurs standard ; filtrage date :
  `filtering=[{"field":"time_created","operator":"GREATER_THAN","value":<unix>}]`.
- Quota : 200 × 24 × (leads créés sur 90 j pour la Page) par 24 h.
- **RÉTENTION CONFIRMÉE : 90 JOURS après soumission** — ensuite le lead est
  supprimé et « ne peut plus jamais être téléchargé » (UI ET API). Conséquence
  TAQINOR (au 2026-07-16) : les leads d'avant ~2026-04-17 (mars + début avril)
  sont IRRÉCUPÉRABLES côté Meta — Odoo est la seule source historique. Le
  webhook temps réel est donc OBLIGATOIRE pour ne plus jamais perdre un lead.
  Source : facebook.com/business/help/1526849577619206 (« About expired leads »).

## 2. Permissions

- `leads_retrieval` requis (+ `pages_manage_metadata`, `pages_show_list`,
  `pages_read_engagement`, `ads_management` pour résoudre ad→campagne).
- Token PAGE requis pour lire les leads (un user token → vide/erreur) ; pattern
  serveur recommandé : token **System User** avec la Page assignée en asset.
- Advanced Access (App Review + Business Verification) requis pour la prod sur
  ads réelles ; le mode dev suffit pour SA propre Page avec des utilisateurs
  admin/dev/testeur de l'app.
- Pièges « data vide » : Page non abonnée à l'app (`subscribed_apps`), user
  token au lieu de Page token, System User sans asset Page.

## 3. Webhook leadgen (temps réel)

- Objet `page`, champ `leadgen`. Setup : callback URL app + subscribe +
  `POST /<page_id>/subscribed_apps?subscribed_fields=leadgen` (token Page).
- Payload MINIMAL (ids seulement, pas les réponses) :
  `entry[].changes[].value = {leadgen_id, page_id, form_id, adgroup_id, ad_id,
  created_time}` → follow-up `GET /<leadgen_id>?fields=...` avec
  `leads_retrieval`.
- NOTE repo : le récepteur EXISTE déjà (`apps/crm/webhooks.py`
  `meta_lead_ads_webhook`, XMKT32/ADSENG1) — gated par
  `META_LEAD_ADS_VERIFY_TOKEN`/`META_LEAD_ADS_ACCESS_TOKEN`. Ne PAS reconstruire.

## 4. Boucle retour CRM → Meta (Conversion Leads)

- **L'ancienne Offline Conversions API est MORTE** (~2025-05-14, dernière
  version v16) → tout passe par la **Conversions API sur un CRM Dataset**.
- Événements CRM : `action_source: "system_generated"` (OBLIGATOIRE pour les
  Conversion Leads), `custom_data.event_source: "crm"`,
  `custom_data.lead_event_source: "Odoo"` (ou "ERP"), `event_name` = étape
  pipeline LIBRE (minimum DEUX événements par lead : réception + issue, ex.
  `signed_contract`), `event_time` ≤ 7 j avant l'envoi.
- `user_data` par priorité de matching : **`lead_id` (leadgen Meta, JAMAIS
  hashé)** > click id / email SHA-256 > téléphone SHA-256 (E.164 sans
  symboles). Valeur du deal : `custom_data.value` + `custom_data.currency`
  (permet l'optimisation par la valeur).
- Un CRM Dataset ≠ le Pixel site web — dataset séparé, à créer avant l'envoi.
- Source : developers.facebook.com/docs/marketing-api/conversions-api/conversion-leads-integration/payload-specification/

## 5. Attribution WhatsApp (CTWA)

- /insights ne donne QUE l'agrégat (`messaging_conversation_started_7d`) —
  AUCUN export par téléphone/utilisateur (frontière vie privée, confirmée).
- **L'objet `referral` d'un message WhatsApp entrant** (Cloud API webhook
  `messages`) EST l'attribution par ad : `source_id` (**= AD ID**),
  `source_type` (`ad`|`post`), `source_url`, `headline`, `body`, `media_type`,
  `image_url`/`video_url`/`thumbnail_url`, **`ctwa_clid`** (click id).
  Présent uniquement si la conversation vient d'une pub CTWA. Nécessite le
  webhook WhatsApp Business Cloud API (topic `messages`) — PAS disponible via
  la simple app WhatsApp Business téléphone (gate ADSENG34 : coût/BSP).
- CAPI Business Messaging (issues post-conversation) :
  `action_source: "business_messaging"`, `messaging_channel: "whatsapp"`,
  `ctwa_clid` dans user_data (non hashé), dataset lié au WABA, permissions
  `whatsapp_business_management` + `whatsapp_business_manage_events`
  (Advanced), palier 1 500 appels/15 j <10 % erreurs.

## 6. UTM / url_tags

- Champ `url_tags` sur l'AD ; macros dynamiques `{{ad.id}}`, `{{adset.id}}`,
  `{{campaign.id}}`, `{{ad.name}}`, `{{site_source_name}}`, `{{placement}}`.
- **Les macros par NOM sont figées à la première publication** (un rename ne
  se propage pas) → toujours joindre par `{{ad.id}}` (stable), jamais par nom.
- Gabarit conseillé : `utm_source=facebook&utm_medium=paid_social&
  utm_campaign={{campaign.id}}&utm_term={{ad.id}}&utm_content={{adset.id}}`.
