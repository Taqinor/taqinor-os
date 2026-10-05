# Runbook — Onboarding d'un client sur le moteur publicitaire (adsengine)

Ce runbook décrit comment brancher un NOUVEAU client (tenant) sur le moteur
publicitaire Meta Ads (`apps/adsengine`) **sans jamais mélanger les données entre
clients**. Il complète l'audit multi-tenant automatisé
(`apps/adsengine/tests/test_tenancy.py`, ENG30) : le code garantit le scoping,
ce runbook garantit la conformité côté Meta + l'accord écrit.

> Règle d'or : **une société ERP = un tenant = un ad account Meta séparé.**
> Aucune donnée (leads, dépense, créatifs, tokens) n'est jamais partagée entre
> deux clients. Le moteur est déjà scopé par `authentication.Company` (chaque
> modèle ENG hérite de `core.TenantModel`, FK `company` obligatoire) ; l'isolement
> côté Meta doit être posé manuellement en suivant les étapes ci-dessous.

## 1. Côté Meta — Business Portfolio & Partner access

1. Le client garde la **propriété** de son Business Portfolio (Meta Business
   Manager), de sa Page et de son ad account. On ne recrée jamais ses actifs
   dans notre propre portfolio.
2. Le client nous accorde un **accès Partenaire** (Partner access) sur SON ad
   account + SA Page, depuis *Paramètres du Business > Partenaires*. On demande
   le rôle minimal nécessaire (gestion des annonces), jamais la propriété.
3. On génère un **token System-User long-lived** côté NOTRE business, restreint à
   CET ad account partagé. Jamais un token de session navigateur (il expire vite
   et ne convient pas à un service serveur).
4. Le token est stocké **write-only** dans `MetaConnection.credentials`
   (`{"access_token": "…"}`) de la société correspondante — jamais relu par
   l'API (un GET n'expose que sa présence, cf. ENG2).

## 2. Côté ERP — un tenant, un ad account

- Créer / confirmer la `Company` du client dans l'ERP.
- Renseigner **une seule** `MetaConnection` pour cette société :
  `ad_account_id`, `page_id`, `pixel_id` propres au client, `enabled=True` une
  fois le token posé. Tant que `enabled` est faux ou que le token manque, le
  moteur no-ope proprement (aucun appel réseau).
- Poser les garde-fous du client (`GuardrailConfig`) et sa policy créative
  (`CreativePolicy`) via `python manage.py seed_adsengine` (idempotent — ne
  touche jamais une config existante) puis ajuster au besoin.
- **Ne jamais** réutiliser l'ad account, le pixel ou le token d'un autre client.
  Un `ad_account_id` ne doit apparaître que sur UNE seule `MetaConnection`.

## 3. Accord écrit — checklist avant la première campagne

Avant toute activité publicitaire pour un client, obtenir un **accord écrit**
couvrant :

- [ ] Mandat de gestion des annonces sur l'ad account du client (périmètre,
      durée, résiliation).
- [ ] Budget mensuel plafond + qui paie Meta (moyen de paiement sur l'ad account
      du client, jamais le nôtre).
- [ ] Propriété des actifs : la Page, l'ad account, le pixel et les audiences
      restent au client.
- [ ] Traitement des données personnelles (leads) conforme à la loi 09-08 / CNDP :
      finalité, conservation, jamais de partage entre clients.
- [ ] Politique créative validée (aucun faux chantier / client / témoignage ni
      chiffre non vérifié — check-list ENG16 confirmée règle par règle par un
      humain avant diffusion).
- [ ] Règle permanente respectée : **les campagnes naissent PAUSED** et le moteur
      **n'active jamais** une campagne automatiquement (invariant produit).

## 4. Ce que le code garantit déjà (rappel)

- Chaque modèle ENG porte une FK `company` (audit `test_tenancy.py`).
- Chaque ViewSet est scopé `request.user.company` (`CompanyScopedModelViewSet`) —
  `perform_create` force la société côté serveur, jamais depuis le corps de
  requête.
- Les lectures cross-app (leads CRM pour le coût-par-signature) passent par
  `apps/crm/selectors.py`, scopées société — jamais un import de modèles.
- Les secrets (token Meta, clés fabrique) ne fuient jamais : l'endpoint santé du
  câblage (ENG12) ne rapporte que leur PRÉSENCE.

## 5. Off-boarding

- Retirer l'accès Partenaire côté Meta (le client révoque, ou nous nous retirons).
- Passer `MetaConnection.enabled=False` et vider `credentials` (le moteur no-ope).
- Conserver l'historique (miroirs, actions, briefs) scopé à la société pour
  l'audit, ou le supprimer sur demande du client (droit à l'effacement).

## 6. Activation pour un client (MVP solaire, 20/09/2026)

Décision fondateur 5 (20/09/2026, Groupe SOLMVP) : **Publicité est un module
VENDU aux clients**, au même titre que CRM/Ventes/Chantiers — pas un outil
interne. SOLMVP17 a corrigé un trou constaté ce jour-là : le manifeste du
module (`apps/adsengine/apps.py`) portait `installable=False`, ce qui faisait
que `core.permissions.DisabledModuleMiddleware` IGNORAIT complètement ce
module — désactiver « Publicité » (`ModuleToggle.actif=False`) masquait bien
l'écran côté frontend mais **ne coupait rien côté API**. Le manifeste porte
maintenant `installable=True` : le toggle gate désormais l'API exactement
comme les autres modules vendus (vérifié par
`apps/adsengine/tests/test_module_toggle_gate.py` sur un endpoint réel,
`GET /api/django/adsengine/connexions/`).

- **Activé par défaut.** Une société NEUVE n'a AUCUNE ligne `ModuleToggle`
  pour `adsengine` — `core.feature_flags.module_actif` renvoie alors son
  défaut (`actif=True`, comme tout module non explicitement désactivé) : le
  module est donc actif dès la création du tenant, sans étape manuelle.
- **Étape 1 — brancher le client.** Créer la `MetaConnection` de la société
  dans la console Publicité (routeur `router.register(r'connexions', …)` de
  `apps/adsengine/urls.py`, servi sous
  `POST/GET /api/django/adsengine/connexions/`) en suivant les sections 1 et 2
  ci-dessus (Business Portfolio, Partner access, token write-only,
  `ad_account_id`/`page_id`/`pixel_id` propres au client).
- **Étape 2 — invariant permanent.** Toute campagne créée par le moteur naît
  TOUJOURS `PAUSED` (règle #3 du CLAUDE.md, codée en dur côté `meta_client`) —
  ceci ne dépend d'aucun toggle et n'est jamais désactivable, y compris pour un
  client Publicité payant.
- **Bascule marche/arrêt.** Un admin (Directeur) désactive ou réactive
  « Publicité » pour SA société depuis **Paramètres → Applications**
  (`frontend/src/pages/parametres/ApplicationsSection.jsx`, onglet ADMIN-GATED
  branché sur `GET/POST /api/django/core/modules/…`). Depuis SOLMVP17, ce
  même interrupteur ferme aussi l'API : société désactivée → toute route
  `/api/django/adsengine/…` (et son miroir `/api/v1/adsengine/…`) répond `404`
  pour ses utilisateurs, sans affecter les autres sociétés (isolation
  multi-tenant, `DisabledModuleMiddleware`).

## 7. Pilote de veille « YanBow » (PLAN_VEILLE, D-VEIL-5)

Le pilote de veille publicitaire (trouver les vendeurs UE + Royaume-Uni par
l'API officielle Meta Ad Library) tourne dans une société **« YanBow »** de
l'ERP actuel, module Publicité. Un serveur YanBow séparé n'est monté qu'au
**premier client payant** (avec ses données réelles et SON accès officiel).

1. **Créer la société** par l'admin Django : `/{DJANGO_ADMIN_URL}`
   (défaut `/api/django/admin/`) → *Authentication › Companies › Ajouter*
   (`CompanyAdmin`, `backend/django_core/authentication/admin.py`). JAMAIS par
   `manage.py init_tenant` ni par l'inscription publique
   (`RegisterCompanyView`, `authentication/views.py`) : les deux appliquent le
   gabarit solaire (catalogue, étapes, modèles) qui n'a rien à faire chez
   YanBow. Noter l'**identifiant** de la société créée.
2. **Créer le compte responsable/admin** : même admin → *Authentication ›
   Users › Ajouter* (`CustomUserAdmin`), société = YanBow, puis lui affecter
   un rôle (*Roles › Ajouter*, `apps/roles/admin.py`) portant au minimum
   `adsengine_view` et `adsengine_manage` (lancer une découverte, corriger un
   verdict, étiqueter, tirer l'échantillon, exporter).
3. **Désactiver les autres modules** si utile : connecté en admin YanBow,
   **Paramètres → Applications** (`frontend/src/pages/parametres/
   ApplicationsSection.jsx`) → couper CRM, Ventes, Chantiers… ; chaque coupure
   crée une ligne `ModuleToggle` (`core/models.py`) pour la société seulement.
   Laisser **Publicité** actif (aucune ligne = actif par défaut).
4. **Variables `.env` du pilote** (lues par
   `erp_agentique/settings/base.py`, déclarées commentées dans `.env.example`),
   puis redémarrer `django` et `celery_worker` :
   - `META_AD_LIBRARY_ENABLED=1`, `META_AD_LIBRARY_ACCESS_TOKEN`,
     `META_AD_LIBRARY_APP_ID`, `META_AD_LIBRARY_APP_SECRET` — l'accès de test
     de Reda, application dédiée « YanBow Veille » ; SÉPARÉ de tout ce qui sert
     aux campagnes TAQINOR (jamais `MetaConnection`, jamais
     `META_SYSTEM_USER_TOKEN` / `META_LEAD_ADS_*`) ;
   - `VEILLE_SOCIETES_AUTORISEES=<id de YanBow>` (D-VEIL-12 : vide = personne ;
     aucune autre société ne peut lancer de découverte sous ce jeton) ;
   - facultatif : `VEILLE_PAUSE_USAGE_PCT` (pause préventive, défaut 75),
     `VEILLE_CONSERVATION_PUBS_JOURS` (défaut 90) ;
   - démonstration sans jeton : `META_AD_LIBRARY_FIXTURES_DIR=<dossier>` avec
     `META_AD_LIBRARY_ENABLED=0` (transport de rejeu, aucune connexion) ;
   - tri IA dans l'ERP : `VEILLE_IA_CLE_API` reste **vide** pendant le pilote
     (tri par la session Claude, `tools/veille_tri/trier.py`, D-VEIL-8).
5. **Atterrissage** : `/publicite/veille` (entrée de nav « Veille
   concurrentielle », `frontend/src/features/adsengine/module.config.jsx`).
   Le bandeau affiche la couverture par pays et l'état de l'accès (`pret`,
   `expire_bientot`…) servis par `GET /api/django/adsengine/veille/couverture/`
   (`?verifier=1` déclenche UN `debug_token` à la demande). Onglets :
   Découverte → Annonceurs → Échantillon de mesure → Mesures.
6. **Commandes utiles** (`backend/django_core/apps/adsengine/management/
   commands/`) : `veille_exporter_fiches --decouverte <id>`,
   `veille_importer_verdicts <fichier> --company <id>`,
   `veille_mesurer --decouverte <id>`, et en fin de pilote
   `veille_purger --company <id>` (`--simulation` d'abord).

**Limites connues du pilote.** La page de connexion affiche « Taqinor » ;
les autres écrans Publicité (campagnes, créatifs…) restent visibles pour la
société YanBow tant que le module est actif ; les résultats obtenus sous
l'accès de test de Reda sont une **démonstration à l'écran**, sans remise de
fichier ni de liste (D-VEIL-7 — l'export CSV est l'outil de la mise en
service, pas du pilote). **Déclencheur du serveur séparé** : le premier client
payant — mise en service sous SON accès officiel, YanBow prestataire
technique.
