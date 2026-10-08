# Audit J0 « acquisition » — dossier d'évaluation (L2, 08/10/2026)

Unité **J0** du registre (`docs/audits/unites.yml`), groupe **AACQ**, niveau **L2** (défaut du registre : P=4, I=4, score 16 ;
auto-pick go-deep confirmé : saisie client propagée vers le CRM, écritures vers des systèmes externes — Meta, Odoo — et
surface publique non authentifiée ; pas d'argent client direct ⇒ L2, pas L3). Fichier du propriétaire :
`docs/plans/PLAN_AUDIT_ACQUISITION.md` (propriété : `docs/ownership.yml` › `acquisition`, qui prime). Claim : branche
`audit-J0`. Méthode : `docs/audits/METHODE.md` v2. Sorties brutes : scratchpad de la session (`j0/`).

## 0. Préconditions (phase 0)

- **SHA.** Lecture à `origin/main` `cc2fa8b68` (08/10/2026). Pile locale : checkout `C:\dev\taqinor-os` (conteneurs
  `erp-agentique-*`), migrée à `d096f2233` pendant l'audit J5 ; les commits intermédiaires sont docs/plans.
- **Apps parquées.** `check_parked_apps` vert au début de la session (J5).
- **Propriété.** `docs/ownership.yml` › `acquisition` : `apps/adsengine/**`, `apps/contact/**`, `crm/webhooks.py`,
  `crm/odoo_sync.py`, commandes Odoo de crm, `ventes/selectors_publicite.py`, `frontend/src/features/adsengine/**`,
  `WebsiteLeadPayloadsPage`, `tools/adlib_probe/**`, `tools/veille_tri/**`. Les chemins `apps/web/**` du registre (`lead.ts`,
  `pages/api/**`, `mon-toit.astro`) sont au propriétaire **web** (`check_ownership --owner-of`) : lus comme couture, tâches vers
  `docs/WEB_PLAN.md`. Chevauchement déclaré avec `docs/plans/PLAN_CRM_VENTES.md` (webhooks, odoo_sync).

## 1. Charte (phase 1)

- **Système et frontière.** Un prospect arrive par : formulaire / estimateur du site (`apps/web` → proxy → webhook ERP),
  Meta Lead Ads (webhook + rapatriement), questionnaire, prise de RDV, import / synchronisation Odoo ; il devient un `Lead`
  CRM avec sa provenance et son attribution. En sens inverse : le moteur publicitaire (`adsengine`) lit les métriques Meta,
  applique des règles, crée campagnes / audiences / créations, renvoie les conversions (CAPI) ; la veille concurrentielle
  lit la bibliothèque publicitaire.
- **Objet.** Objectifs fondateur 1 (ce que le prospect a saisi se corrige sans être ré-écrasé par une nouvelle
  soumission), 2 (une seule normalisation téléphone / ville / factures), 3 (code propre), 4 (le prospect et le fondateur
  voient le bon chiffre : lead, attribution, coût par lead). Règles maison : **#1 Odoo JSON-2 seulement**, **#3 campagne née
  `PAUSED`**, **#5 aucun scraping sans fichier `tos_risk/` + accord**.
- **Personas réelles** : Administrateur, Responsable, Commercial (CRM) ; « marketeur » n'existe pas — joué en
  `demo_admin`. Prospect : formulaire public sans compte.
- **Niveau** L2 ; **jeu** `demo` ; prod en lecture seule sous accord permanent ; aucun appel réel à Meta / Odoo / SendGrid.
- **Critères retenus** : C1, C2, C3, C4, C5, C6, C7, C8, C10, C11 (#1, #3, #5), C12, C13. C9 via les réglages adsengine.
- **Étapes.** P1 entrée : P1.1 webhook site · P1.2 webhook Meta Lead Ads · P1.3 questionnaire · P1.4 RDV · P1.5 rejeu /
  file des charges utiles · P1.6 dédoublonnage et normalisation. P2 Odoo : P2.1 import · P2.2 synchro · P2.3 push d'étapes.
  P3 moteur pub : P3.1 lecture métriques · P3.2 règles / anomalies / alertes · P3.3 création campagne / audience /
  création · P3.4 CAPI (renvoi de conversions) · P3.5 reporting / simulateur. P4 veille : P4.1 bibliothèque pub · P4.2 tri.
  P5 coutures : P5.1 événements · P5.2 multi-société des vues et tâches · P5.3 parité site ↔ webhook.
- **Non-objectifs.** Intérieur du `Lead` après création (J1a, D1) ; écrans `apps/web` hors couture (WEB_PLAN) ; apps parquées.

## 2. Spécification (phase 2)

- H×H S-1 : la même soumission de site rejouée (double clic, retry du proxy, DLQ) ⇒ UN lead, aucune saisie manuelle écrasée.
- H×H S-2 : un webhook sans signature / secret faux / d'une autre société ⇒ refusé, rien d'écrit.
- H×H S-3 : toute création de campagne / ad set / ad passe `PAUSED` (règle #3), quel que soit le chemin (règle auto,
  modèle, duplication, flightrunner).
- H×M S-4 : un lead corrigé à la main dans le CRM n'est pas ré-écrasé par la synchro Odoo / Meta / une nouvelle soumission.
- H×M S-5 : chaque vue, tâche Celery et action adsengine borne `company` ; un compte publicitaire d'une société n'est jamais
  lu ni écrit pour une autre.
- M×H S-6 : CAPI n'envoie que des données hachées / consenties, une fois par conversion ; un lead effacé (`lead_erased`)
  n'est plus renvoyé.
- M×M S-7 : coût par lead, ROAS, attribution : UNE définition entre reporting, tableau de bord et `selectors_publicite`.
- M×M S-8 : Odoo n'est écrit qu'en JSON-2 (règle #1) ; la veille ne scrape rien sans `tos_risk/` (règle #5).

Seuils : S1 fuite locataire / campagne active créée / argent pub dépensé à tort / lead perdu ; S2 saisie écrasée, geste
cassé ; S3 contournement ; S4 cosmétique. CONFIRMÉ seulement sur preuve exécutée (sonde en transaction annulée, live).

## 3. Plan des lanes (phase 3)

| Ronde | Lanes (modèle / effort) |
|---|---|
| Scout | DET détecteurs + dédoublonnage (haiku/low) |
| R2 (8) | LWH webhooks lead (opus/high) · LODOO synchro Odoo (sonnet/medium) · LMETA client Meta, CAPI, création (opus/high) · LRULES règles, anomalies, métriques, reporting (sonnet/medium) · LVIEWS vues / tâches / multi-société adsengine (opus/high) · LFRONT écrans adsengine + charges utiles (sonnet/medium) · LVEILLE veille + contact + outils (sonnet/medium) · LWEB couture `apps/web` ↔ webhook (sonnet/medium) |
| R3 | un vérificateur FRAIS opus/high par lane, sonde en transaction annulée sur la base démo locale |
| Live | orchestrateur : webhook site joué en local, lead CRM, écrans adsengine (Playwright `demo_admin`) |

## 4. Exécution et manifeste de couverture (phase 4)

- **Détecteurs** (scout haiku, `cc2fa8b68`, sortie brute `j0/scout.md`) : `check_parked_apps`, `check_lead_webhook_parite` (73 clés),
  `check_api_contract`, `check_api_shapes --stats`, `check_services_appeles`, `check_ecrans_atteignables` : **tous verts** ; règle #1 :
  0 `execute(` / `cursor` / `psycopg` dans `odoo_sync.py`, `odoo_leads.py` et les commandes Odoo ; règle #3 : 26 occurrences de
  `ACTIVE` dans adsengine, toutes des lectures / énumérations (création en dur `PAUSED` dans `meta_client.py`) ; règle #5 :
  `tos_risk/` présent (5 fichiers dont `meta_ad_library_api.md`). Aucun détecteur ne voit les classes ci-dessous (d'où les M3
  AACQ75-AACQ79).
- **Lanes R2** (8, notes `j0/<LANE>.md` avec fichiers lus / non lus) : LWH 4, LODOO 6, LMETA 6, LRULES 9, LVIEWS 6, LFRONT 10,
  LVEILLE 8, LWEB 4 = **53 constats bruts**. `views.py` adsengine (4 793 l.) et `services.py` / `tasks.py` lus par sous-flux
  (approbation, garde-fous, import photo, budget) ; le reste est listé non lu dans `j0/LVIEWS.md`.
- **Run live** (orchestrateur, `j0/live.md`) : LIVE-1 webhooks lead fermés sans secret configuré — `website-leads` sans en-tête
  401, avec un octet non-ASCII 401 (pas de 500 : QJR413 tient), `meta-lead-ads` 403 ; LIVE-2 Playwright `demo_admin` : 25 écrans
  `/publicite/*` + `/crm/payloads-site-web` rendus, 0 `console.error`, 0 4xx/5xx. Non joué en live : le chemin AVEC secret (secret
  absent en local ; couvert par les sondes R3).
- **PROD lecture seule** (08/10) : 1 connexion Meta ; miroirs de campagnes PAUSED 8 / ACTIVE 1 (créée le 16/07, origine non
  établie) ; 2 actions moteur (1 proposée, 1 rejetée) ; 410 leads Meta, 414 événements CAPI ; 246 charges utiles du site, toutes
  traitées, 1 sans lead ; 1 045 leads (canal vide 551, meta_ads 405, site_web 68, walk_in 21) ; secret webhook défini, aucun
  jeton Meta en settings.

## 5. Registre des constats (phase 4 → 6)

53 constats bruts ; tâches regroupées par cause racine par les rédacteurs (numérotation C-AACQ-nnn dans le texte des tâches).
**Porte empirique** : 53/53 REPRO (8 vérificateurs frais, sondes en transaction annulée, aucun appel réseau réel). **Seconde
lentille** (2 réfuteurs frais, sondes différentes) sur LVIEWS-1, LMETA-1, LRULES-1, LVIEWS-6, LWEB-4, LWH-1, LWH-3, LVIEWS-2 : 7
maintenus, LWH-3 DÉJÀ PLANIFIÉ (ACRM14). Gravités post-porte : S2 17 · S3 32 · S4 4.

| ID | étape | crit. | grav. | verdict | titre | tâche(s) |
|---|---|---|---|---|---|---|
| LODOO-1 | P2.3 | C10 | S3 | REPRO | Le beat Odoo toutes les 30 min re-avance un lead que l'ERP a reculé (recul confirmé) ou mis au froid | AACQ31, AACQ95 |
| LODOO-2 | P2.3 | C10 | S3 | REPRO | Le push ERP->Odoo traite une colonne Odoo inconnue comme « Nouveau » et l'écrase | AACQ32 |
| LODOO-3 | P2.3 | C5 | S3 | REPRO | L'alignement Odoo ignore les drapeaux perdu, archivé et « ne plus contacter » que tous les autres automates respect | AACQ33, AACQ95 |
| LODOO-4 | P2.3 | C4 | S2 | REPRO | Un lead perdu ou archivé dans Odoo n'est jamais reflété dans l'ERP, et un lead neuf déjà perdu reçoit la cadence d' | AACQ34, AACQ96 |
| LODOO-5 | P4.2 | C4 | S3 | REPRO | Le compteur de leads Odoo du moteur publicitaire omet les leads perdus (archivés), ce qui gonfle le coût par lead | AACQ35 |
| LODOO-6 | P2.3 | C10 | S3 | REPRO | Le push choisit une fiche ERP arbitraire quand plusieurs partagent le même email ou téléphone | AACQ32 |
| LWH-1 | P1.5 | C6 | S2 | REPRO/L2 MAINTENU | Le rejeu d'un payload du site peut créer un lead en double ou un lead fantôme : aucun contrôle d'état, et l'erreur  | AACQ30, AACQ79, AACQ89 |
| LWH-2 | P1.5 | C10 | S3 | REPRO | Un lead du site récupéré par rejeu ne reçoit jamais le devis automatique (auto-pipeline réservé à la vue) | AACQ30 |
| LWH-3 | P1.2 | C2 | S2 | REPRO/L2 DEJA_PLANIFIE | La repasse Meta (webhook rejoué, filet de 15 min, pull de 90 j) écrase en silence une correction manuelle de priori | ACRM14 (déjà planifié) |
| LWH-4 | P1.1 | C3 | S4 | REPRO | Le ping d'engagement de proposition parcourt en Python TOUS les leads de la société au lieu de la recherche indexée | — optionnel |
| LVIEWS-1 | P3.3 | C5 | S2 | REPRO/L2 MAINTENU | Une action moteur approuvée reste modifiable : son type et ses données (PATCH/PUT) puis appliquée sans nouvelle app | AACQ1, AACQ76, AACQ89 |
| LVIEWS-2 | P3.3 | C6 | S2 | REPRO/L2 MAINTENU | Import photo de chantier : le consentement CNDP d'un client X valide la photo du chantier d'un client Y | AACQ5, AACQ6 |
| LVIEWS-3 | P3.3 | C13 | S3 | REPRO | Import photo de chantier : saisir la puissance (kWc) à l'écran renvoie une 500 | AACQ15 |
| LVIEWS-4 | P3.2 | C6 | S3 | REPRO | Garde-fous (singleton guardrail/) : plafonds sans bornes, 500 au lieu de 400 ; le jumeau garde-fous/ valide, lui | AACQ13 |
| LVIEWS-5 | P3.2 | C5 | S3 | REPRO | Quatre yeux (PUB103) inopérant pour toute proposition humaine passant par un producteur curé, la modération ou Inst | AACQ14 |
| LVIEWS-6 | P3.2 | C5 | S3 | REPRO/L2 MAINTENU | Un Commercial ou un Technicien (adsengine_manage, sans approve) relève les plafonds et arme l'auto-application sans | AACQ12 |
| LMETA-1 | P3.3 | C10 | S2 | REPRO/L2 MAINTENU | Toute application d'un changement de budget (rebalance_budget, increase_pace, rebalance_adset_budget, annulation PU | AACQ4 |
| LMETA-4 | P3.3 | C7 | S3 | REPRO | La duplication d'un ad set copie un budget À VIE comme budget QUOTIDIEN (ou 0), sans plafond quotidien appliqué | AACQ16 |
| LMETA-3 | P3.3 | C6 | S3 | REPRO | Le transport Meta rejoue automatiquement les POST non idempotents (créations, posts publiés, réponses aux commentai | AACQ17 |
| LMETA-2 | P3.4 | C3 | S3 | REPRO | CAPI CRM-stage et « visite effectuée » hachent le téléphone en chiffres nus (0612…), pas en E.164 : la clé ph ne co | AACQ18 |
| LMETA-5 | P3.4 | C10 | S3 | REPRO | Le CAPI CRM-stage part en HTTP synchrone dans le post_save, à l'intérieur de la transaction d'acceptation du devis  | AACQ19 |
| LMETA-6 | P3.4 | C8 | S3 | REPRO | Un lead effacé (DSR ou rétention) reste éligible au CAPI : external_id (leadgen_id) et fbclid survivent à l'anonymi | AACQ20, AACQ21 |
| LRULES-1 | P3.2 | C7 | S2 | REPRO/L2 MAINTENU | Les seuils monétaires des règles (threshold_mad) sont comparés à des montants en devise du compte (USD en productio | AACQ2, AACQ3, AACQ90 |
| LRULES-2 | P3.2 | C1 | S2 | REPRO | L'alerte WhatsApp du stop-loss annonce un 'coût par signature' alors que le chiffre est un coût par lead, en 'MAD'  | AACQ7 |
| LRULES-3 | P3.2 | C13 | S3 | REPRO | Les alertes sont réémises à chaque évaluation : branche insufficient_data, règles alerte-seule et miroirs PAUSED/ar | AACQ22 |
| LRULES-4 | P3.2 | C7 | S2 | REPRO | record_anomaly est appelé DANS l'évaluateur cpl_band : le backtest GET en lecture seule, la simulation et chaque pa | AACQ8 |
| LRULES-5 | P3.2 | C10 | S3 | REPRO | La boucle critique de 6 h du Gardien n'évalue rien : zero_delivery n'a pas d'évaluateur, et les détecteurs pic/chut | AACQ24 |
| LRULES-6 | P3.2 | C10 | S3 | REPRO | Les alertes gardées ne sont jamais résolues : resolve_alert n'a aucun appelant, l'escalade WARNING→CRITICAL s'accum | AACQ23 |
| LRULES-7 | P3.5 | C1 | S2 | REPRO | Carte chaleur par ville et calculateur de recyclage COLD affichent des CPL / CAC faux : dépense Meta fenêtrée ÷ lea | AACQ10, AACQ11, AACQ26 |
| LRULES-8 | P3.1 | C10 | S3 | REPRO | L'écran Connexion et l'audit de compte annoncent le connecteur Odoo 'actif' sans ODOO_COMPANY_ID alors que le conne | AACQ25 |
| LRULES-9 | P3.5 | C7 | S2 | REPRO | S-7 non tenu : au moins quatre 'coûts par lead' aux dénominateurs différents portent le même nom, dont celui des rè | AACQ9, AACQ26 |
| LFRONT-1 | P3.3 | C10 | S2 | REPRO | Boîte d'approbation : le diff de budget lit des champs que le serveur n'émet jamais — l'approbateur ne voit pas le  | AACQ60, AACQ63, AACQ89 |
| LFRONT-2 | P3.2 | C10 | S3 | REPRO | Rejet d'une action : le motif structuré choisi par l'opérateur est envoyé sous « reason » alors que le serveur lit  | AACQ60, AACQ64, AACQ89 |
| LFRONT-3 | P3.3 | C2 | S3 | REPRO | Plan de vol : « Enregistrer » supprime puis recrée les phases (non atomique) et écrase budget, dates et nombre de b | AACQ67, AACQ89 |
| LFRONT-4 | P3.2 | C13 | S3 | REPRO | Clôture d'expérience : le serveur ignore un second verdict contraire et l'écran affiche quand même le verdict cliqu | AACQ60, AACQ65, AACQ66, AACQ89 |
| LFRONT-5 | P1.5 | C13 | S2 | REPRO | Listes paginées lues sur la seule page 1 (50 lignes), sans signal de troncature : payloads de lead, backlog sans lo | AACQ60, AACQ61, AACQ62, AACQ67, AACQ68, AACQ77, AACQ89 |
| LFRONT-6 | P3.5 | C3 | S3 | REPRO | Cockpit par ad : la comparaison « dépense totale période » compare un total filtré par la vue à un total de période | AACQ69, AACQ89 |
| LFRONT-7 | P3.1 | C13 | S3 | REPRO | « Synchroniser » annonce « Synchronisation lancée. » même quand le serveur répond synced:false (connexion Meta inac | AACQ70, AACQ89 |
| LFRONT-8 | P3.2 | C2 | S3 | REPRO | Garde-fous budget : saisie décimale acceptée puis tronquée en silence par le serveur, écran non resynchronisé, cham | AACQ71, AACQ89 |
| LFRONT-9 | P3.3 | C6 | S3 | REPRO | Messages d'erreur génériques qui masquent la raison serveur (approbation « permission ? » alors que c'est la règle  | AACQ60, AACQ72, AACQ73, AACQ77, AACQ89 |
| LFRONT-10 | P3.2 | C13 | S3 | REPRO | Un échec de chargement du tableau de bord, des alertes ou des anomalies se lit comme « aucune alerte » / « aucune a | AACQ74, AACQ77, AACQ89 |
| LVEILLE-1 | P4.1 bibliot | C10 | S2 | REPRO | Le transport de rejeu (démo sans jeton, e2e VEIL46) est inatteignable : l'étape de découverte exige un jeton ET l'i | AACQ36 |
| LVEILLE-2 | P4.1 bibliot | C10 | S2 | REPRO | Le client serveur n'envoie pas ad_type alors que la sonde l'envoie à ALL : la découverte risque de ne voir que les  | AACQ37 |
| LVEILLE-3 | P4.2 tri (rè | C7 | S2 | REPRO | legende_vers_domaine réduit les sous-domaines de plateformes et les suffixes à deux niveaux manquants à un domaine  | AACQ38 |
| LVEILLE-4 | P4.1 bibliot | C8 | S4 | REPRO | Le journal de la sonde écrit le jeton en clair dès qu'il ne ressemble pas à « EAA… » : la rédaction se fie au forma | — optionnel |
| LVEILLE-5 | P4.1 bibliot | C11 | S3 | REPRO | La sonde appelle /me avec le jeton du fondateur, hors du périmètre déclaré dans tos_risk (ads_archive + debug_token | AACQ39 |
| LVEILLE-6 | P1.1 webhook | C11 | S4 | REPRO | Le formulaire de contact parqué répond 429 (pas 404) à partir de la 6e requête par heure et par IP | — optionnel |
| LVEILLE-7 | P1.1 webhook | C6 | S4 | REPRO | Le formulaire de contact (quand il est réactivé) renvoie 500 sur un champ non-chaîne ou un saut de ligne dans « nom | — optionnel |
| LVEILLE-8 | P4.1 bibliot | C13 | S3 | REPRO | Une panne réseau ou un 5xx de Meta marque la requête « erreur » définitivement après 3 essais en ~3 s, et la découv | AACQ40 |
| LWEB-1 | P3.x (page p | C8 | S3 | REPRO | proposition-track journalise le jeton porteur de la proposition et la référence quand FUNNEL_WEBHOOK_URL est absent | AACQ42 |
| LWEB-2 | P1.x (soumis | C8 | S3 | REPRO | L'identifiant « non réversible » des logs de lead (leadLogId) est un FNV-1a 32 bits du téléphone, inversible en sec | AACQ43 |
| LWEB-3 | P1.x (soumis | C3 | S3 | REPRO | appareilId() pose un cookie de 2 ans (Domain=taqinor.ma) + localStorage sans consentement dans les jumeaux de soumi | AACQ44 |
| LWEB-4 | P1.x (soumis | C13 | S2 | REPRO/L2 MAINTENU | capture-lead répond « enregistré » alors qu'une absence de LEAD_WEBHOOK_URL jette le lead sans lettre morte ni aler | AACQ41, AACQ78, AACQ89 |

## 6. Constats OPTIONNELS (hors tâches)

- LWH-4 (ping d'engagement en Python sur tous les leads — performance, S4 ; piste X6), LVEILLE-4 (journal de la sonde, jeton non
  « EAA… » en clair — outil local, S4), LVEILLE-6 (contact parqué : 429 avant 404 à la 6e requête, S4), LVEILLE-7 (contact
  réactivé : 500 sur champ non-chaîne, S4 tant que le formulaire est parqué).
- LWH-3 : couvert par ACRM14 (ouverte) ; résidu prouvé par la seconde lentille : `ville` re-remplie hors
  `_apply_meta_form_extras` (branche `existing` de `services.py`) — à intégrer par le propriétaire d'ACRM14 (aucune tâche AACQ en
  doublon).
- LWH-4 (S4 après V) : le ping d'engagement de proposition charge en Python tous les leads de la société (webhooks.py:2614-2627, SELECT sans LIMIT, 131 lignes chargées dans la sonde LWH-4) au lieu de Lead.objects.filter(company, pho
- LVEILLE-4 (S4 après V) : le journal de la sonde adlib_probe écrit en clair un jeton qui ne commence pas par EAA (input_token de E0 non retiré par _safe_params, scrub par motif seulement). Sonde : 'AppId123|appsecretvalue987654' et
- LVEILLE-6 (S4) : le formulaire de contact parqué répond 429 au lieu de 404 dès la 6e requête par heure et par IP (throttle DRF avant le Http404, contact/views.py:12-21). Sonde : [404×5, 429×2], 0 e-mail.
- LVEILLE-7 (S4 après V) : le formulaire de contact, une fois réactivé, renvoie 500 au lieu de 400 sur un champ qui n'est pas une chaîne, ou sur un saut de ligne dans « nom » (contact/views.py:22-26 et 47-57). Il est parqué par défa
- AACQ30 complément UX : masquer « Rejouer » dans WebsiteLeadPayloadsPage.jsx:113 quand p.lead est posé (le 422 explicite suffit pour la correction).
- Note de lane LWH : le téléphone Meta est stocké brut, str(value)[:20] (services.py ~6401), et non au format canonique QJR594. dedupe_event n'est jamais relâché quand le mapping échoue. Le ping d'engagement n'est pas idempotent. ut
- Note de lane LVEILLE : Annonceur.extraits jamais purgé (conservation.py:44-51). Appel HTTP fait sous select_for_update (veille_decouverte.py:467-531). trier.py abandonne tout le lot sur une seule erreur de la CLI.
- Note de lane LWEB : clé morte hasMeterPhoto ; resolveApiBase recopié 3 fois ; questionnaire-repondre sans AbortSignal ; regex e-mail du site plus laxiste que celle de l'ERP (le lead est perdu sans bruit).
- Repli event_id CAPI `${leadLogId(phone)}-${submittedAt}` (lead.ts:1571) : il garde une empreinte inversible du téléphone. Impact marginal, puisque Meta reçoit déjà ph en SHA-256 non salé.
- LFRONT optionnel (S4) — gestes irréversibles sans confirmation : ConsentScreen.revoke, FactTableScreen.removeEntry, bouton « Appliquer » de la boîte d'approbation (la clôture d'expérience est traitée par AACQ66).
- LFRONT optionnel (S4) — unité incohérente : ManualActionComposer saisit en centimes alors que les autres écrans affichent des montants ÷100 (à aligner avec AACQ63 si l'orchestrateur le souhaite).
- LFRONT-5 complément optionnel — filtre serveur `?erreur=1` sur `GET /crm/website-lead-payloads/` (crm/views.py, propriétaire crm) pour que les payloads en erreur ne soient jamais noyés ; AACQ68 règle déjà l'écran par lecture compl
- LFRONT-3 complément optionnel — filtre serveur `?plan=` sur `phases-vol/` (le ViewSet ne filtre pas, adsengineApi.js:259-263) ; AACQ67 lit toutes les pages et filtre côté client.
- LFRONT-5 frères non couverts par une tâche dédiée — rules.list, anomalies.list, comments (CommentListView), consents.list, factTables/factEntries, creativePolicy.list : gelés par la garde AACQ77 (décroissance).
- LVIEWS-2 : dériver client_id du chantier côté serveur et retirer le champ libre « ID client » de frontend/src/features/adsengine/ChantierImportScreen.jsx:76-80 ; contrôler l'existence et la société du client à la création d'un Con
- LVIEWS-3 : type="number" step="any" sur l'input puissance de ChantierImportScreen.jsx:82-87 ; frère CreativeAssetViewSet.upload int(request.data.get('cost_cents') or 0) non capturé → 500 sur valeur non numérique (views.py:851-857)
- LVIEWS-4 : MetaConnectionStatusView.post (views.py:2392-2415) écrit des clés du corps sans sérialiseur, même motif de jumeau que le singleton guardrail/.
- LVIEWS-5 : interrupteur require_four_eyes à l'écran ConnectionScreen (front + échantillon de contrat, @after AACQ14).
- AACQ3 (front) : afficher la devise enregistrée des seuils et plafonds dans RulesScreen.jsx / ConnectionScreen.jsx (contrat M0 d'abord, @after AACQ3) ; adsengine.js:35 libelle aujourd'hui les garde-fous « réellement en MAD ».
- LMETA-3 : au lieu d'un échec « réponse perdue », relire Meta (dédup par nom, patron flightrunner.py:447-500) avant toute reprise d'un POST.
- LMETA-4 : afficher le type de budget (quotidien / à vie) dans serializers.py:671-674 et 753-756 (montants MAD sans type).
- LRULES-5 : câbler ou retirer (C4) detect_spend_anomaly, detect_frequency_runaway (anomaly.py:121, 268), evaluate_creative_fatigue (rules_engine.py:796-891) et les gabarits WhatsApp spend_spike / spend_collapse (alerts.py:232-245) 
- LRULES-6 : résolution automatique des alertes PUB33/34 (anomaly._emit_alert, anomaly.py:726-754) et des AnomalyEvent.
- LRULES-9 : sync.resolve_results (ADSDEEP6, résultats par objectif) n'a aucun appelant hors tests (constat V).
- LRULES-8 : whatsapp_cloud_ctwa — audit.py:225-228 n'exige que deux clés alors que la boucle liste WHATSAPP_CLOUD_COMPANY_ID ; _audit_tracking juge le CAPI sur l'environnement global, pas par société.
- LRULES-2 : reporting.py:517 nomme spend_mad une dépense en devise du compte (renommer la clé = changement de contrat, à faire avec un échantillon M0).

## 7. Vérification adversariale (phase 5)

- **Porte empirique** : 8 vérificateurs frais opus/high, une sonde par constat (`j0/sondes/`), clients Meta / Odoo remplacés par des
  transports simulés (`httpx.MockTransport`, `Mock(spec=…)`) ; non-persistance prouvée par chaque vérificateur. **0 réfuté sur 53** ⇒
  seconde lentille obligatoire.
- **Seconde lentille** : LVIEWS-1 reproduit avec un autre rôle, un autre `kind` et un client typé (contenu réécrit après
  approbation puis appliqué ; journal réécrit ; action appliquée supprimable) ; LMETA-1 prouvé par contrat AST sur tous les
  `_dispatch` : la SEULE méthode appelée absente de `MetaClient` est `update_adset_budget`, jamais existée (`git log -S`) — toute la
  famille budget est morte, masquée par des `Mock()` sans spec ; LRULES-1 reproduit aux bornes sur deux évaluateurs (un seuil saisi
  en MAD agit comme un seuil en USD) — les équivalences en MAD avancées par la lane reposaient sur un taux non sourcé et sont
  RETIRÉES (aucune tâche n'en reprend) ; LWEB-4 : impact S1 (100 % des leads perdus si `LEAD_WEBHOOK_URL` manque) mais déclencheur
  PLAUSIBLE, gardé S2.
- **Fable** : aucun appel (L2, aucune question non résolue par les sondes).

## 8. Non-risques consignés (valides tant que l'hypothèse tient)

- Webhooks lead fail-closed sans secret ; comparaison du secret en octets (pas de 500 sur entrée non-ASCII) — LIVE-1.
- Règle #1 : aucun SQL vers Odoo (détecteur) ; règle #3 : création `PAUSED` codée en dur dans `MetaClient` (garde permanente
  AACQ75 pour que cela reste vrai sur tout chemin futur).
- Écrans Publicité et page des charges utiles : 0 erreur en usage nominal (LIVE-2).
- Portes dédiées d'autonomie et d'approbation refusent Commercial / Technicien (403, seconde lentille LVIEWS-6) — le défaut est
  ailleurs : les vues génériques de garde-fous / règles le permettent.

## 9. Conclusion (phase 6)

- **Couverture.** 8 surfaces lues (non-lus par lane au scratchpad) ; 6 détecteurs exécutés, tous verts ; 53 constats reproduits,
  8 repassés en seconde lentille ; scénarios : S-1, S-2, S-3, S-4, S-5, S-6, S-7, S-8 sondés ; live : webhooks + 26 écrans ; prod
  lue. **Non joués** : jeu `anon`, création réelle de campagne, webhook avec secret en live.
- **Ce qui ne tient pas** : l'approbation d'une action moteur ne fige pas son contenu ; toute modification de budget appliquée
  par le moteur échoue (méthode Meta inexistante) ; les seuils en MAD sont comparés à des montants en USD ; le consentement CNDP
  d'un client valide la photo du chantier d'un autre ; au moins quatre « coûts par lead » différents portent le même nom ; le
  rejeu d'une charge utile du site peut doubler un lead ; la synchro Odoo ré-avance des leads reculés à la main et ignore les leads
  perdus ; le site répond « enregistré » même quand il jette le lead faute d'URL.
- **Registre** : J0 → `audité`, groupe `AACQ`, **65 tâches** : `PLAN_AUDIT_ACQUISITION.md` 56 (dont M1 AACQ90, AACQ95, AACQ96 et
  l'acceptation live AACQ89), `docs/WEB_PLAN.md` 5, `PLAN_AUDIT_TRANSVERSE.md` 2, `PLAN_AUDIT_CHANTIERS.md` 1, `PLAN_AUDIT_DEPLOY.md` 1.
- **Coût.** Scout 1 (haiku) ; lanes 8 (LWH, LMETA, LVIEWS opus/high ; 5 sonnet/medium) ; vérificateurs 8 (opus/high) ; seconde
  lentille 2 (opus/high) ; rédacteurs 3 (opus/high) ; ≈ 4,9 M jetons de sous-agents ; Fable : aucun.
