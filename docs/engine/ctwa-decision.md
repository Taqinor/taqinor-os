# ADSENG34 — Boucle `ctwa_clid` complète : dossier de DÉCISION

> **Statut (maj 2026-07-17) : RÉCEPTION CONSTRUITE (env-gated) ; boucle RETOUR
> CAPI encore GATED (décision fondateur, coût + architecture).**
> La moitié **ALLER** (recevoir un message CTWA entrant → capter `ctwa_clid` +
> `source_id`) est désormais implémentée côté `apps/adsengine` (ADSDEEP24), mais
> reste un **NO-OP TOTAL** tant que les jetons Cloud API ne sont pas provisionnés
> (voir §0). La moitié **RETOUR** (renvoyer les signatures via la Conversions API
> for Business Messaging) reste **non construite et gated ADSENG34**. Ce document
> reste la **spec de décision** de la boucle COMPLÈTE. Source :
> `docs/engine/research/dd-attribution.md` §2.4–2.5 et
> `docs/engine/research/adsdeep-leads-capi.md` §5 (vérifié contre la doc primaire
> Meta, 16 juil. 2026).

## 0. État réel du code (2026-07-17)

**CONSTRUIT — réception CTWA, entièrement env-gated (ADSDEEP24) :**

- Récepteur webhook **WhatsApp Cloud API** (topic `messages`) dans
  `apps/adsengine/whatsapp_webhook.py`, monté à
  `GET/POST /api/django/adsengine/whatsapp/webhook/` :
  - **GET** — poignée de main Meta (`hub.mode`/`hub.verify_token`/`hub.challenge`)
    contre `WHATSAPP_CLOUD_VERIFY_TOKEN`.
  - **POST** — signature `X-Hub-Signature-256` vérifiée contre
    `WHATSAPP_CLOUD_APP_SECRET` ; l'objet `referral` des messages entrants est
    extrait vers le modèle **`CtwaReferral`** (`ad_id` = `source_id`, `ctwa_clid`,
    `source_type`, `headline`, `ts`, `phone_key` normalisé QW10, `crm_lead_id`
    rattaché par téléphone via `crm.selectors` — jamais un import de `crm.models`).
    Idempotent par `(company, wa_message_id)`.
- **NO-OP TOTAL sans configuration** : tant que `WHATSAPP_CLOUD_VERIFY_TOKEN` **et**
  `WHATSAPP_CLOUD_APP_SECRET` ne sont pas tous deux posés, tout appel (GET/POST)
  répond **404** sans le moindre effet de bord — le webhook « n'existe pas » tant
  que le fondateur n'a pas pris la décision Cloud API/BSP ci-dessous.
- **Métrique conséquente (ADSDEEP25)** : `conversations_per_ad()` compte les
  `CtwaReferral` par ad et joint les signatures par téléphone
  (`GET /api/django/adsengine/metrics/conversations-per-ad/`) — « cette ad a
  produit N conversations, M signées ». Elle ne remonte des chiffres réels
  QUE lorsque le webhook est configuré et reçoit du trafic ; sinon elle est vide.

**PAS ENCORE CONSTRUIT — reste gated ADSENG34 :**

- La **boucle RETOUR** : aucune émission vers la **Conversions API for Business
  Messaging** (`action_source='business_messaging'`, `messaging_channel='whatsapp'`,
  `user_data.ctwa_clid`). Le `ctwa_clid` est capté et stocké mais rien ne le
  renvoie encore à Meta — c'est la moitié « feedback » de la boucle, qui exige
  un dataset lié au WABA + permissions `whatsapp_business_manage_events`
  (Advanced Access) et reste une décision coût/architecture séparée (§5–§6).

## 1. Ce que la boucle apporterait

L'**attribution exacte clic → conversation** pour le canal WhatsApp :

- **Aller (clic → lead)** : à la **première** entrée d'une nouvelle conversation
  WhatsApp, capter `referral.ctwa_clid` (l'identifiant de clic Click-to-WhatsApp)
  **et** `referral.source_id` (= `ad_id`, la **vraie granularité par variante**),
  puis les stocker sur le `Lead` (`ctwa_clid` + `meta_ad_id`). Le bandit (ENG8) et
  la réconciliation (ENG31) gagnent alors, pour WhatsApp, la même qualité
  d'attribution par-ad que les Lead Ads — au lieu du tag manuel
  `canal='whatsapp_ctwa'` (une supposition humaine, jamais une attribution).
- **Retour (signature → Meta)** : renvoyer les événements qualifiés via la
  **Conversions API for Business Messaging** (`action_source='business_messaging'`,
  `messaging_channel='whatsapp'`, `user_data.ctwa_clid` — documenté « ne pas
  hacher », contrairement à email/téléphone). C'est la moitié « feedback » qui
  ferme la boucle d'optimisation.

C'est une capacité Meta **propre, documentée et pleinement supportée** — le
blocage est **opérationnel/coût**, pas technique.

## 2. La contrainte vérifiée : impossible avec `wa.me` aujourd'hui

**VÉRIFIÉ — zéro chemin `ctwa_clid` possible dans la configuration actuelle :**

- Le `ctwa_clid` est injecté par Meta dans un objet `referral` livré **uniquement**
  dans le payload webhook d'un message entrant reçu **via la WhatsApp Business
  Platform (Cloud API)** — ou un BSP bâti dessus (360dialog, Twilio, Sinch…).
- L'app **WhatsApp Business gratuite** n'a **aucune** surface webhook/API : il n'y
  a **rien** pour recevoir l'objet `referral`, même en principe.
- Un lien `wa.me/<numéro>?text=…` **ne porte aucun paramètre de click-id** visible
  côté appareil/app : l'identifiant n'existe que côté serveur, sur l'infra Meta,
  livré au propriétaire de l'abonnement Cloud API du numéro.

**Conséquence :** aujourd'hui, le **seul** signal CTWA possible est le tag manuel
`canal='whatsapp_ctwa'`. L'attribution réelle par-ad/par-clic WhatsApp est
**catégoriquement indisponible** sans adopter la Cloud API.

### 2.1 Palliatif intérimaire (process, PAS du code)
Les pubs CTWA supportent un **message pré-rempli « personnalisé » par ad**. En
posant une phrase distincte par campagne/créatif (ex. « Bonjour, offre Toit A »),
un agent peut **inférer manuellement** quelle pub a lancé un fil WhatsApp et
taguer `canal`/`utm_campaign` à la main. C'est de la discipline de process, pas de
l'attribution : ne jamais l'afficher dans la console avec le même niveau de
confiance qu'un vrai match `meta_ad_id`.

## 3. Ce que la boucle exige (changement d'architecture)

1. Enregistrer le numéro WhatsApp sur la **Cloud API** (directement Meta ou via BSP).
2. ~~Monter un récepteur webhook~~ — **FAIT (ADSDEEP24)** : le récepteur vit dans
   `apps/adsengine/whatsapp_webhook.py` (et non `apps/crm/webhooks.py` comme
   anticipé — le CTWA appartient au domaine du moteur publicitaire, pas au CRM ;
   il lit le CRM uniquement via `crm.selectors`). Env-gated (§0).
3. ~~Capter `referral.ctwa_clid` + `referral.source_id`~~ — **FAIT** : stockés sur
   `CtwaReferral` (adsengine), pas sur `crm.Lead`. Le rattachement au lead se fait
   par `phone_key` (référence `crm_lead_id`), jamais une FK cross-app dure.
4. Émettre la **CAPI Business Messaging** au moment de la qualification — **RESTE À
   FAIRE, gated ADSENG34** (moitié RETOUR de la boucle).
5. **Renoncer** au workflow WhatsApp personnel/Business-App gratuit (le vrai coût
   caché : c'est un changement de flux de travail, pas seulement une facture).

> **Ce que la réception construite implique — et n'implique PAS :** le webhook
> ADSDEEP24 est un scaffold **inerte tant que non configuré** (404 sans jetons) :
> il ne présuppose donc aucune décision Cloud API. Il n'y a **aucune plomberie
> pointant vers une infra inexistante** — le code est simplement prêt à recevoir
> le jour où le fondateur provisionne les jetons. La décision coût/architecture
> (§4–§6) reste entière ; construire la réception ne l'a pas prise.

## 4. Coûts BSP connus (dossiers antérieurs)

La structure de coût (les **montants exacts en MAD restent à confirmer par le
fondateur** au moment de la décision — ne pas les figer ici) :

- **Tarif par conversation Meta** : facturé par catégorie (marketing / utility /
  service / authentication), par pays. Les conversations **initiées par
  l'utilisateur** (le cas CTWA : c'est le prospect qui écrit) tombent dans les
  catégories les moins chères, voire dans la fenêtre de service gratuite selon la
  politique en vigueur.
- **Frais de plateforme BSP** : soit un **abonnement mensuel forfaitaire** (modèle
  360dialog — pas de marge par message), soit une **marge par message** au-dessus
  du tarif Meta (modèle Twilio/Sinch). Pour un volume solaire (dizaines de
  conversations/semaine), le forfait mensuel est généralement le moins cher.
- **Coût d'intégration** : ponctuel (vérification du numéro + branchement du
  webhook). Côté ERP il est déjà **payé** — le récepteur ADSDEEP24 est prêt ; il
  ne reste que la config Meta et le collage des jetons.

**Cloud API DIRECT (Meta) vs BSP :** deux voies pour recevoir l'objet `referral`.
- **Direct Meta (Cloud API self-serve)** : pas de marge BSP par message ; on paie
  seulement le tarif conversation Meta. Exige de **gérer soi-même** l'App Meta, le
  numéro, les jetons et la fiabilité webhook — mais la surface webhook côté ERP
  existe déjà (ADSDEEP24), donc le surcoût est surtout opérationnel.
- **BSP (360dialog / Twilio / Sinch…)** : ajoute un abonnement forfaitaire OU une
  marge par message (cf. ci-dessus) en échange d'un onboarding géré et d'outils.
  Pertinent surtout si un opérateur humain veut une boîte de réception partagée.

Le poste dominant à ce volume n'est pas la facture Meta/BSP (faible) mais le
**changement de workflow** (perte de l'app WhatsApp gratuite).

## 5. Déclencheur de décision

Ouvrir la décision « adopter la WhatsApp Cloud API » devient pertinent quand **au
moins l'une** de ces conditions est atteinte :

- **Volume** : le canal WhatsApp génère **≥ 15–25 leads/semaine** — assez pour que
  l'attribution par-variante change les allocations du bandit (en-dessous, le MDE
  est trop large, l'attribution manuelle suffit).
- **Deuxième répondeur** : un **2ᵉ agent** répond sur WhatsApp — le tag manuel ne
  scale plus de façon cohérente entre plusieurs personnes, la capture automatique
  devient le seul moyen fiable.

Tant qu'aucune condition n'est remplie, la boucle est **superflue** : le tag
manuel + le message pré-rempli distinct par ad couvrent le besoin. La décision
reste **séparée** du reste de la colonne d'attribution (ADSENG31/32/33), qui
fonctionne pleinement **sans** elle.

## 6. Recommandation

Traiter « adopter la WhatsApp Cloud API » comme sa **propre décision gated**
(COST/DECISION), signature fondateur requise — **jamais** un bloqueur pour livrer
le reste du moteur. La **réception** est déjà en place et inerte (ADSDEEP24) : le
jour de la décision, il suffit de provisionner `WHATSAPP_CLOUD_VERIFY_TOKEN` +
`WHATSAPP_CLOUD_APP_SECRET` (+ `WHATSAPP_CLOUD_COMPANY_ID` si multi-société) pour
l'activer. Ne pas construire la **boucle RETOUR** (CAPI Business Messaging) tant
que la décision Cloud API/dataset WABA n'est pas prise.
