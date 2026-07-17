# ADSDEEP dossier — Posts organiques, commentaires, Instagram (recherché 2026-07-16)

## 1. Éditer un post de Page (`POST /<page_post_id>`)

- Post PUBLIÉ : **seul `message` est éditable**. L'image/vidéo attachée d'un
  post publié N'EST PAS modifiable (aucun champ documenté) — changer le visuel
  = supprimer + recréer (perte de l'historique d'engagement).
- Post NON publié / programmé : `message`, `link`, `scheduled_publish_time`
  modifiables avant publication.
- **Contrainte clé : une app ne peut éditer QUE les posts créés PAR elle** —
  les posts faits via Business Suite/autres outils sont intouchables par l'ERP.
- Post adossé à une AD active (`effective_object_story_id`) : l'édition du
  `message` n'est pas bloquée par l'API mais = hors chemin supporté (le post a
  été reviewé comme ad ; risque re-review/désync). L'aide Meta officielle : un
  boosted post reviewé ne peut plus changer texte/image/vidéo. → l'UI doit
  marquer ces posts « adossé à une pub — édition à risque » via
  `GET /<page_id>/ads_posts` (liste TOUS les posts utilisés en ads, dark
  compris ; exige pages_manage_ads + pages_show_list + ads_management + tâche
  ADVERTISE).
- `DELETE /<page_post_id>` OK — mais supprimer un post adossé à une ad la CASSE
  définitivement (« Unsupported Ad Type or Removed Post »).
- Permissions : `pages_manage_posts` (write) + `pages_read_engagement` (read),
  token PAGE d'un porteur de tâche CREATE_CONTENT/MANAGE.

## 2. Créer des posts + booster un post existant

- Publié : `POST /<page_id>/feed` (message, link).
- **Dark post** : `published=false` sans scheduled_publish_time — objet post
  complet jamais affiché sur la Page, réutilisable en ad (`object_story_id`),
  avec SES propres commentaires/likes.
- Programmé : `published=false` + `scheduled_publish_time` (**10 min à 30 jours**).
- Photo : `POST /<page_id>/photos` ; multi-photos : photos `published=false`
  puis `/feed` avec `attached_media[n]={"media_fbid":...}`.
- Vidéo : `POST /<page_id>/videos` ; gros fichiers via Resumable Upload API
  (`/<APP_ID>/uploads` → session → handle) — max **1,75 Go / 45 min**.
- **Booster un post existant** (préserve la preuve sociale) :
  `POST /act_<ID>/adcreatives` avec `object_story_id=<page_post_id>` (PAS
  d'object_story_spec) → `POST /act_<ID>/ads` (status PAUSED — règle #3).
- IG : booster un média IG = `source_instagram_media_id` sur l'adcreative.

## 3. Commentaires (posts publiés ET dark posts — mêmes edges)

- Lire : `GET /<object_id>/comments?summary=true&filter=toplevel|stream` —
  champs `id,message,from,created_time,like_count,is_hidden,can_hide,
  can_remove,comment_count,attachment,permalink_url`.
- Masquer : `POST /<comment_id>` `is_hidden=true` (les 2 SEULS champs
  écrivables d'un Comment : `is_hidden`, `message`).
- Supprimer : `DELETE /<comment_id>` (la Page propriétaire de l'objet).
- Répondre : `POST /<comment_id>/comments` (message, attachment_url, @mention).
- **Réponses privées (DM)** : `POST /<comment_id>/private_replies` — UNE seule
  par commentaire, dans les **7 jours**, exige `pages_messaging`.
- Permissions : lecture `pages_read_engagement` ; write (hide/delete/reply)
  `pages_manage_engagement` + tâche MODERATE ; DM `pages_messaging`.
- Pièges : erreur **80001** (throttle Page, BUC ≈ 4800×utilisateurs engagés/24 h,
  token System User recommandé) ; `is_hidden` = éventuellement consistant
  (bugs connus : hidden côté API mais visible côté FB — re-GET pour vérifier ;
  unhide parfois refusé alors que hide passe).

## 4. Instagram (compte Business connecté)

- Lecture média : champs `id,caption(READ-ONLY),comments_count,like_count,
  media_type,media_url,permalink,timestamp,view_count`. Permissions
  `instagram_basic` (+`pages_read_engagement`).
- Commentaires IG : hide `POST /<ig_comment_id>` `hide=true` ; reply
  `POST /<ig_comment_id>/replies` ; delete ; couper les commentaires d'un média
  `POST /<ig_media_id>` `comment_enabled=false` (SEUL champ écrivable du média).
  Permission `instagram_manage_comments`.
- **Publication (container en 2 temps)** : `POST /<IG_USER_ID>/media`
  (image_url JPEG | video_url, media_type IMAGE|VIDEO|REELS|STORIES|CAROUSEL,
  caption, alt_text) → poll `status_code=FINISHED` → `POST /<IG_USER_ID>/
  media_publish` (creation_id). Quota `content_publishing_limit` :
  **50 publications/24 h** (vérifier par compte via l'endpoint).
- Specs REELS : MP4/MOV (moov devant), H.264/HEVC, AAC ≤48 kHz, ≤300 Mo,
  23-60 FPS, 9:16 recommandé, 5-90 s pour l'onglet Reels.
- **Caption IG non éditable après publication** (Reels compris). Endpoints IG
  legacy morts depuis 2025-04-21 — n'utiliser que IG User/Media/Comment.

## 5. App Review — réalité 2025-2026 (DÉCISIF)

- **Gérer SA PROPRE Page/IG : Standard Access SUFFIT — AUCUNE App Review, AUCUNE
  Business Verification** tant que les utilisateurs de l'intégration ont un
  rôle (admin/dev/testeur) sur l'app ET que le Business de l'app possède la
  Page/le compte IG. (Docs permissions + Instagram App Review : « apps serving
  only your own business ».)
- Advanced Access (nécessaire seulement si l'ERP gère un jour les Pages
  D'AUTRES entreprises) : Business Verification (48 h-14 j) + soumission par
  permission (screencast, privacy policy…), délais 2026 ~2-20 j + 3-5 j par
  rejet. → budget 1-4+ semaines, uniquement pour du multi-tenant social.

## 6. Impossible (à afficher honnêtement dans l'UI)

- Changer l'image/vidéo d'un post publié ; éditer une caption IG/Reel publiée ;
  éditer les posts créés par d'autres apps ; éditer texte/visuel d'un boosted
  post déjà reviewé (chemin supporté = pointer l'ad vers un AUTRE post) ;
  réutiliser un post supprimé dans une ad active ; unhide fiable à 100 %.
