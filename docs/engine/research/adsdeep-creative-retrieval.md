# ADSDEEP dossier — Récupérer le contenu créatif COMPLET des ads (recherché 2026-07-16)

Version Graph vivante au moment de la recherche : v25.0 (2026-02-18). Champs
stables v21→v25 sauf mention.

## 1. Ad → creative

`GET /<AD_ID>?fields=creative{object_story_spec,asset_feed_spec,
effective_object_story_id,thumbnail_url,body,title,image_url,
instagram_permalink_url,call_to_action_type}`

- `object_story_spec` (créatifs standards) : `page_id` (requis) ;
  `link_data` : `message` (texte principal), `link`, `name` (titre),
  `description`, `call_to_action {type, value:{link,…}}`, `image_hash`,
  `child_attachments` (cartes carrousel : name/description/link/image_hash/video_id) ;
  `video_data` : `video_id`, `message`, `title`, `image_url` (miniature),
  `call_to_action` ; `photo_data` : `image_hash`.
- `asset_feed_spec` (créatifs dynamiques/Advantage+) : `bodies[].text`,
  `titles[].text`, `descriptions[].text`, `images[].hash`, `videos[].video_id`
  + `thumbnail_url/hash`, `link_urls[].website_url`, `call_to_action_types[]`,
  `ad_formats[]`, `asset_customization_rules[]`.
- `effective_object_story_id` — l'ID du post de Page réellement diffusé
  (publié OU dark post) → chaîner §4.
- `body`/`title`/`image_url` directs : `body` N'EST PAS peuplé pour les vidéos.

Source : developers.facebook.com/docs/marketing-api/reference/ad-creative/ ;
…/ad-creative/asset-feed-spec/

## 2. La VIDÉO elle-même

`GET /<VIDEO_ID>?fields=source,picture,length,permalink_url`
(+ edge `GET /<VIDEO_ID>/thumbnails` → uri/height/width/is_preferred, exige
`pages_read_engagement`+`pages_show_list`).

- `source` = URL mp4 CDN **directement jouable** — TOUJOURS d'actualité v25.
- **Les URLs CDN EXPIRENT (~1 h pour `source`)** — AUCUNE URL Graph n'est
  permanente. Patron obligatoire : stocker `video_id` (permanent), fetcher un
  `source` FRAIS à l'affichage, cache Redis quelques minutes max, ne JAMAIS
  persister l'URL. (Télécharger une copie serveur = décision fondateur ToS,
  pas un défaut silencieux.)
- Permissions : token Page/User avec `pages_read_engagement` / `ads_read`.

Source : developers.facebook.com/docs/graph-api/reference/video/

## 3. Les IMAGES

`GET /act_<ID>/adimages?hashes=["<hash>"]&fields=hash,url,url_128,permalink_url,name,width,height`

- `hash` = identifiant PERMANENT (à stocker) ; `url`/`url_128` = temporaires
  (doc officielle : « do not use this URL in ad creative creation ») ;
  `permalink_url` = **URL permanente** utilisable pour l'affichage durable.

Source : developers.facebook.com/docs/marketing-api/reference/ad-image/

## 4. Post de Page derrière l'ad (`effective_object_story_id`)

`GET /<POST_ID>?fields=message,attachments{media,url,type,description,title}`

- Exige un **token Page** (pas un simple user token) issu d'un porteur de la
  tâche ADVERTISE sur la Page, scopes `ads_management`(/`ads_read`),
  `pages_read_engagement`, `pages_manage_ads`, `pages_show_list`.
- **PIÈGE n°1 (vécu supports/forums)** : un token System User échoue
  (`(#200)`, ou `attachments` vide) si le System User n'a pas reçu l'ACCÈS À
  L'ASSET PAGE dans Business Settings → Assign Assets → Pages — avoir le scope
  dans le token NE SUFFIT PAS. Correctif = assignation d'asset Page au System
  User (très fréquent sur les ads CTWA créées via le flux WhatsApp).
- CTWA : creative = `object_story_spec` standard + bloc `page_welcome_message` ;
  aucune permission spéciale WhatsApp pour la LECTURE.

## 5. Previews (aperçus rendus par Meta)

`GET /<AD_ID>/previews?ad_format=<FORMAT>` (aussi sur un creative id) →
`body` = snippet `<iframe>` à injecter tel quel.

- Formats utiles : `MOBILE_FEED_STANDARD`, `DESKTOP_FEED_STANDARD`,
  `INSTAGRAM_STANDARD`, `INSTAGRAM_STORY`, `INSTAGRAM_REELS`,
  `FACEBOOK_REELS_MOBILE`, `FACEBOOK_STORY_MOBILE`, `MARKETPLACE_MOBILE`…
- **L'iframe n'est valide que 24 h** (doc officielle) → régénérer à chaque
  affichage, ne jamais persister le HTML.

Source : developers.facebook.com/docs/marketing-api/reference/adgroup/previews/

## 6. Irrécupérable / dépréciations

- Variations générées Advantage+ (fonds IA, expansion d'image, variations de
  texte IA, musique par impression) : NON énumérables via l'API — seuls les
  flags opt-in/out (`degrees_of_freedom_spec`) + un échantillon de previews.
- `asset_feed_spec` + `asset_customization_rules` : le round-trip GET peut
  revenir INCOMPLET (bug forum connu) — tolérer les champs manquants.
- v24/v25 : création/màj des campagnes Advantage+ Shopping/App fermée via API.
- Rien de déprécié sur `object_story_spec`/`thumbnail_url`/`image_url` à v25.
