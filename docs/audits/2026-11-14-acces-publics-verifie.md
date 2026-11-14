<!-- verifie | groupe: APUB | pct: 97 | ecarts_s1_s2: 0 -->
# Vérifie APUB — contre-visite de clôture du parcours PF5 « accès publics », 14/11/2026

Commande `loop audit` (14/11). Le groupe APUB a franchi 95 % de tâches cochées (`audit_registre.py --du` : « 97 % cochées
(42/43) — vérifie dû, clôture (≥ 95 %) »). C'est la contre-visite de clôture, après celle de mi-parcours du 13/11 (zéro écart
S1-S2 sur 42 tâches relues). Rien n'a été construit, aucun plan modifié, aucune pile ni base touchée.

## 0. Préconditions

- **SHA.** `origin/main` = `a12f40f821` (branche `verifie-cloture-1411`, à jour). Base de la contre-visite précédente :
  `d64fa1e4e4` (seconde passe du 13/11) ; 551 commits depuis.
- **Registre.** PF5 `acces-publics`, groupe APUB : 42 tâches cochées sur 43 constructibles (97 %). La 43ᵉ est APUB74, la tâche
  `@acceptation` (rejeu par l'orchestrateur, jamais construite par une lane).
- **Cochées depuis le dernier vérifie.** Aucune tâche cochée après le commit du compte rendu du 13/11 (`8a447794d4`) : les 24
  cochées sur rejeu runner l'ont été dans ce même commit, après leur seconde passe (verdict ok ×24). Aucune tâche d'écart déposée
  le 13/11 (zéro écart).
- **Code livré depuis, non coché (preuve en direct due).** APUB7, APUB10, APUB15, APUB39, APUB73 — « non couverts » du 13/11,
  donc le cœur de cette clôture.
- **Échantillon.** 100 % : les 5 tâches à code neuf (toutes droit, données personnelles ou accès public) relues à fond ; les 42
  cochées contrôlées en non-régression par le diff `d64fa1e4e4..a12f40f821` de chaque fichier produit qu'un commit APUB a touché
  (118 fichiers, 31 modifiés depuis, relus un par un).
- **Méthode.** Lecture des commits, du code et des tests nommés ; sondes du dossier PF5 rejouées sur l'hôte (lecture statique et
  exécution de corps extraits par AST) ; tests hôte `scripts/tests/` lancés. Aucun Docker, aucun test Django, aucune production.

## 1. Vérificateur (1, orchestrateur de la contre-visite, lecture seule)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok (code neuf) | **5** | APUB7, 10, 15, 39, 73 |
| ok (non-régression des cochées) | **42** | APUB1-6, 8, 9, 11-14, 30-38, 40-57, 70-72 |
| partiel / non-fait / faux / régression / déjà-présent | **0** | — |

- **APUB7.** `installations/public_views.py::_rapport_publiable`, seule garde des trois vues (page, PDF, photos, 3 appelants
  au grep), refuse au-delà de `DUREE_LIEN_RAPPORT_JOURS = 90` après `cloturee_notifiee_le`, repli `date_realisee` puis
  `date_creation`, comme la tâche l'écrit. Test `tests_zfsm2_lien_rapport.py::test_lien_expire_90_jours_apres_la_cloture` : J-91,
  J-89, repli J-120, trois vues, jeton inchangé par `lien-rapport/`.
- **APUB10.** `crm/public_chat_views.py::_exiger_livechat_ouvert` en tête des trois vues ; `LIVECHAT_PUBLIC_ENABLED` à `'0'` par
  défaut dans `settings/base.py` et `.env.example` ; un seul chemin d'écriture (`create_lead_from_livechat` : 1 appelant). Test
  `tests_xmkt37_livechat.py::test_livechat_eteint_par_defaut_404_sans_ecriture` ; classes existantes réalignées sans retrait.
- **APUB15.** `location /api/public/` de `backend/nginx/nginx.conf` : `proxy_pass` Django, `limit_req zone=api_limit`, en-têtes
  de `/api/django/`, `no-store` hérité. Les deux préalables de la tâche (APUB11, APUB47) sont cochés.
- **APUB39.** `crm/cadence_signaux.py::notify_client_contact_request` n'appelle plus la levée (fonction supprimée, golden
  réaligné 666 → 665) ; note « opposition loi 09-08 active » et touche posées. Plus aucun chemin public ne lève l'opposition
  (grep des écritures `ne_plus_contacter=False` hors filtres : 0). Le test relit lead, empreintes, registre, note et touche.
- **APUB73.** `CORS_ALLOW_CREDENTIALS = False` dans `settings/prod.py`, juste après `CORS_ALLOWED_ORIGINS` ; `base.py` et
  `dev.py` intacts ; `test_settings_prod_asec48.py::test_site_public_sans_identifiants` et `docs/production.md` alignés.

## 2. Tests nommés

Les cinq tests nommés existent et jouent le comportement (vrais appels HTTP anonymes, état relu en base, mutant décrit cohérent).
Aucun test APUB n'a perdu d'assertion depuis le 13/11 : les diffs de `tests_sortie_signe_desaccepte.py`,
`test_ntobs7_export_historique.py`, `test_adminops.py`, `test_yhard6_metrics.py`, `tests_zfsm2_lien_rapport.py` et
`tests_xmkt37_livechat.py` n'ajoutent que des tests (seul retrait : un `@override_settings()` vide remplacé par sa forme réglée).
Tests hôte : `python -m unittest scripts.tests.test_nginx_cache_control` → 8 tests OK (dont `test_api_publique_routee_vers_django`).
`scripts.tests.test_settings_prod_asec48` ne charge pas sur l'hôte (`ModuleNotFoundError: weasyprint`) : environnemental, il
tourne dans le job CI `backend-lint`.

## 3. Sondes et preuve en direct

- **Rejouées telles quelles, ne reproduisent plus :** 002 (garde de rang, admins restants intacts), 004 (jeton de 5 ans servi :
  faux), 009 (plans de vol sous `adsengine_flightplan_manage`), 038 (CORS : `repro` faux).
- **Sonde 001** : affiche toujours « reproduit », faux positif déjà noté le 13/11 ; elle lit `permission_classes` de
  `ExportReversibiliteHistoriqueView` et ne voit pas la garde `_is_directeur_or_admin` posée dans sa méthode `list`
  (`core/export_registry.py`, relue) ; sa partie stockage ne reproduit plus.
- **Sonde 007 (APUB10)** : plante telle quelle (`NameError: _exiger_livechat_ouvert`, la garde n'est pas dans son périmètre
  d'extraction). Rejouée inchangée par un harnais qui ajoute la garde au périmètre : réglage éteint → `Http404`, rien d'écrit ;
  réglage allumé → l'ancien comportement (200, historique écrit), comme la tâche le prévoit.
- **Plantent à l'extraction depuis les correctifs** : 003, 005, 008, 010, 037 (noms ou imports déplacés) ; tâches couvertes
  par lecture du code.
- **Preuve en direct.** Deux enregistrements PASS du 13/11 sous `docs/audits/acceptation/APUB/` couvrent 24 tâches. Les deux
  écarts acceptés (APUB55, APUB57 : appels 403 hors des tâches) ont été repris par ADRG110 et ADRG111, dont le code est sur
  `main` (garde `useDroitMetier` relue dans `onboardingHelpers.js` et `ParametresEntreprise.jsx`). Les cinq tâches à code neuf
  restent « preuve en direct due » : runner ou pile pour APUB7, 10, 39 ; `curl` après déploiement pour APUB15 et 73.

## 4. Écarts retenus

Aucun. Zéro S1-S2, zéro S3-S4 sur les tâches relues.

## 5. Optionnel (non déposé)

- APUB7 : `cloturee_notifiee_le` n'est posé qu'à la première clôture (`installations/services.py`, ACHT36). Une intervention
  rouverte puis re-clôturée plus de 90 jours après sa première clôture a un lien mort dès la re-validation. C'est conforme au
  texte de la tâche ; le fondateur peut préférer la dernière clôture.
- APUB15 : la nouvelle `location` n'a ni `limit_req_status 429` ni `proxy_read_timeout 120s` (défaut nginx : 503 et 60 s).
  Sa jumelle `/api/django/` n'a pas non plus le statut 429.
- APUB39 : la touche de rappel d'un lead opposé est posée, mais le digest de 08 h 30 ne compte que les leads non opposés
  (`notifier_relances_dues.py::_a_des_leads_actifs`) ; la file de touches dues, elle, ne filtre pas l'opposition.
- Rafraîchir les sondes 001, 003, 005, 007, 008, 010 et 037 du dossier PF5 (déjà demandé le 13/11).
- Les points optionnels du 13/11 restent valables (404 final du test d'APUB2, seau commun d'APUB51, course d'APUB5, etc.).

## 6. Couverture et sortie de cycle

- **Couvert.** Les 5 tâches à code neuf (code, commit, test, appelants, jumeaux) ; la non-régression des 42 cochées sur les
  fichiers que leurs commits ont touchés.
- **Non couvert.** Aucun test Django lancé (la CI de `main` fait foi) ; `test_settings_prod_asec48` non chargeable sur l'hôte ;
  le réglage réel `DJANGO_SETTINGS_MODULE` du serveur, dont dépend APUB73 (`wsgi.py` vaut `settings.prod` par défaut ; `.env` de
  prod non lu) ; une régression venue d'un fichier qu'aucun commit APUB n'a touché (route neuve qui contournerait une garde).
- **Statut.** Deuxième `vérifie` consécutif à zéro S1-S2 : la condition de sortie de cycle est remplie. `vérifié` attend
  aussi que la couverture d'acceptation soit complète : APUB74 et les cinq preuves en direct dues.

## 7. Coût

- 1 vérificateur (opus, lecture seule) ; aucun sous-agent, aucun appel Fable.
