# Audit PF3 « deploy, CI, gardes, performance » — 2026-11-10 — L2
<!-- dossier-v3 | groupe: ADCG | base: dc496b2 | fraicheur: ce4e5fc | constats: 62 | taches: 93 | decisions: 3 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PF3 (livrer, faire tourner et réparer la production) : lu `scripts/**`, `.github/**`, `docker-compose*.yml`, les Dockerfiles, `backend/{caddy,nginx,minio,db}`, `core/{backup,health,tasks}`, réglages, `frontend/{Dockerfile.prod,vite.config.js,src/sw.js}`, `apps/web/{worker,astro.config.mjs}` ; aucune table `PF3.json` |
| Niveau | L2 — ni chiffre client ni multi-société, mais une erreur ici perd ou arrête la production ; 8 surfaces indépendantes |
| Données | aucune donnée démo (pile locale non montée : son checkout a 5 999 commits de retard) ; anon : non requis ; prod lecture seule le 10/11 (orchestrateur, SSH, aucune écriture) : voir §2 |
| Critères retenus | C3, C4, C9, C10, C11, C12, C13, C14, C20 |
| Étapes | PF3.1 livraison en production · PF3.2 sauvegardes et restauration · PF3.3 réglages · PF3.4 intégration continue · PF3.5 gardes · PF3.6 budgets de performance · PF3.7 santé et alertes · PF3.8 outillage des runs · PF3.9 front et site public (parcours : PF3) |
| NE PAS REFAIRE | groupes ADEP, AMET, APRF, BPQ et erreurs `ERR-JPB-*` ; ENF11, ENF15, AMET101, NTOBS12, QAH10 (ouvertes) ; ASOC92 ; D-ADEP-*, D-JPB-*, D-ENF* ; incident `prod-sans-sauvegarde` (clos par ce dossier) |
| Non-objectifs | sécurité applicative (PF1) ; socle (PF2) ; construction d'un environnement de pré-production ; choix d'un hébergeur |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| découverte : livraison en production | opus/high | `auto-deploy.sh`, `deploy-prod.ps1`, `land.ps1`, compose de prod, Dockerfile Django, Caddy, nginx, `ci-image.yml`, `release-verify.yml` | unités systemd (absentes du dépôt) |
| découverte : sauvegardes et réglages | opus/high | `core/backup.py`, commandes et tâches de sauvegarde, réglages, `.env.example`, compose, MinIO, base, runbook | `settings/base.py` en partie ; modules de test |
| découverte : intégration continue | sonnet/high | `ci.yml` entier, 9 autres workflows, `dependabot.yml`, scripts `ci_*` ; 60 runs, 40 PR Dependabot, 217 alertes | `ci_frontend_shard.py`, `ci_fast_gate_steps.py` |
| découverte : gardes | sonnet/high | `ci_guards.py`, cliquet, exceptions permanentes, 20 gardes en entier, tailles des listes sur 30 jours ; famille `stage-names` jouée | corps d'environ 85 `check_*.py` |
| découverte : performance | sonnet/high | budgets de requêtes, dossier APRF et sa contre-visite, tests de charge, workers, planning beat, budget de bundle | `capacity_probe.py` ; durées réelles en prod |
| découverte : santé, alertes, outils locaux | sonnet/medium | `core/health.py`, journaux, nocturnes, `sonde.py`, `pile_locale.ps1`, `gc-workspace.ps1`, tâche planifiée du poste | `.env` du serveur |
| découverte : outillage des runs | sonnet/medium | `plan_lanes.py`, `plan_claims.py`, `plan_progress.py`, `audit_tache.py`, empreinte CODEMAP ; mutants sur copies | `split_plan.py`, `ownership.yml` (corps) |
| découverte : front et site public | sonnet/medium | `Dockerfile.prod`, garde de contexte, Vite, service worker, CSP, `apps/web/worker`, `astro.config.mjs` | tableau de bord Cloudflare |
| sondes (3 séries) | opus/high | 27 constats ; 20 sondes hôte sur les vrais scripts (fausses commandes, copies temporaires) | 7 constats sans sonde possible hors prod |
| critique de complétude | opus/high | 9 pistes : 6 trous retenus, lus ; 6 pistes saines | aucun trou sondé |
| rédaction des tâches | opus/high | 93 tâches v3 (4 rédacteurs) | — |
Détecteurs : `ci_guards.py stage-names` (180 gardes, 0 échec, 671 s en local), `check_settings_declares.py`, `check_binaires_image.py`, `check_query_budgets.py`, `check_exports_bornes.py`, `check_dockerfile_context.mjs` → OK @dc496b2 · non exécutés : `backend-lint-fast` (exige flake8 et lint-imports), `check_parcours.py` et `rejouer_parcours.py` (pas de table PF3).
Live : aucun scénario navigateur (parcours sans écran) · prévus non joués : deploy réel, restauration réelle · prod : voir ligne suivante.
Prod (lecture seule, 10/11) : dernier commit de `main` déployé, 12 conteneurs, 0 migration en attente, 0 réponse 5xx en 24 h, script du serveur identique au dépôt, aucun échec de deploy depuis le 01/10 ; 38 sauvegardes réussies depuis le 09/10, copie distante « off », 271 Mo de fichiers sans copie ; 42 exceptions en 24 h dans le worker ; aucun objet touché.

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-ADCG-001 | PF3.1 | C13 | S2 | `scripts/auto-deploy.sh::LAST` | le chemin automatique n'a ni contrôle de santé ni retour arrière ; le retour arrière manuel vise un commit déjà avancé et le chemin manuel n'écrit pas le dernier commit déployé → un « dernier commit sain » partagé, visé par le retour arrière | `docs/audits/sondes/ADCG/C-ADCG-001.py` | ADCG5 |
| C-ADCG-002 | PF3.1 | C13 | S2 | `scripts/auto-deploy.sh::BACKEND_TOUCHE` | le code neuf est servi avant `migrate` dans les deux chemins ; un `migrate` en échec boucle chaque minute sans alerte → migrations avant le redémarrage, échec visible et sans boucle | `docs/audits/sondes/ADCG/C-ADCG-002.py` | ADCG2, ADCG3, ADCG12 |
| C-ADCG-003 | PF3.1 | C13 | S3 | `scripts/deploy-prod.ps1::deployExitCode` | « rollback automatique effectué » affiché pour toute sortie non nulle, 9 sorties sur 9 ne restaurent rien → message qui dit ce qui a été fait | `docs/audits/sondes/ADCG/C-ADCG-003.py` | ADCG6 |
| C-ADCG-004 | PF3.1 | C13 | S2 | `scripts/deploy-prod.ps1::HEALTH_STATUS` | contrôle de santé vert quand il ne peut pas s'exécuter (sortie vide) ; Celery mort passe ; aucun test du chemin servi ; migrations en attente lues 0 si la commande échoue → vide ou échec = refus | `docs/audits/sondes/ADCG/C-ADCG-004.py` | ADCG4 |
| C-ADCG-005 | PF3.1 | C12 | S2 | `scripts/auto-deploy.sh::NONDOC` | tout fichier `.txt` est classé documentation : un merge de dépendances seul saute la reconstruction et avance le commit déployé (latent : prod conforme le 10/11) → une dépendance n'est jamais une doc | `docs/audits/sondes/ADCG/C-ADCG-005.py` | ADCG7 |
| C-ADCG-006 | PF3.1 | C3 | S2 | `scripts/deploy-prod.ps1::RIEN_CONSTRUIT` | deux copies divergées de la séquence : le manuel ne redémarre pas le backend après un rebuild du front seul ; l'automatique n'a ni attente de la base, ni contrôle des migrations, ni purge du cache de build → une seule séquence | `docs/audits/sondes/ADCG/C-ADCG-006.py` | ADCG1 |
| C-ADCG-007 | PF3.1 | C12 | S2 | `scripts/auto-deploy.sh::A_CONSTRUIRE` | la configuration du proxy n'est validée ni en CI ni au deploy ; un rechargement refusé est avalé et annoncé « OK » → configuration validée avant d'être servie | `docs/audits/sondes/ADCG/C-ADCG-007.py` | ADCG8, ADCG9 |
| C-ADCG-008 | PF3.1 | C13 | S3 | `scripts/deploy-prod.ps1::remote` | le script distant est celui de la copie locale du poste, déposé à un chemin fixe écrasable, sans détachement de la session → script du dépôt du serveur, exécution détachée | STATIQUE | ADCG1 |
| C-ADCG-009 | PF3.1 | C12 | S3 | `scripts/auto-deploy.sh::A_CONSTRUIRE` | `apps/web/worker`, l'image MinIO et la configuration Postgres ne déclenchent ni reconstruction ni redémarrage (6 cas sur 6 inertes) → tout fichier embarqué déclenche son service | `docs/audits/sondes/ADCG/C-ADCG-009.py` | ADCG10 |
| C-ADCG-010 | PF3.9 | C4 | S3 | `frontend/src/features/auth/pages/Login.jsx::Login` | quatre variables `VITE_*` lues par le code ne sont jamais passées à la construction (nom du produit, inscription, clé de notifications push, URL du site) → variable lue = variable passable, ou lecture retirée | STATIQUE | ADCG11 |
| C-ADCG-011 | PF3.2 | C13 | S1 | `backend/django_core/core/backup.py::dump_database` | seuls les dumps Postgres sont sauvegardés ; les fichiers (pièces, PDF : 271 Mo en prod) n'ont aucune copie → les fichiers entrent dans le périmètre de sauvegarde | STATIQUE | ADCG30 |
| C-ADCG-012 | PF3.2 | C13 | S1 | `backend/django_core/core/backup.py::_push_offsite` | aucune copie hors du serveur (prod : « off ») ; copie non chiffrée ; un échec de copie distante laisse le run « termine » → copie distante existante, échec visible | `docs/audits/sondes/ADCG/C-ADCG-012.py` | ADCG31, ADCG32 |
| C-ADCG-013 | PF3.2 | C10 | S2 | `backend/django_core/authentication/services.py::artefact_backup_disponible` | la garde « jamais de purge sans sauvegarde » accepte un export réduit à un comptage ou un dump ancien ou déjà purgé → seul un dump existant, récent et non purgé compte | `docs/audits/sondes/ADCG/C-ADCG-013.py` | ADCG33, ADCG34 |
| C-ADCG-014 | PF3.2 | C13 | S3 | `backend/django_core/core/backup.py::restore_drill` | l'exercice de restauration hérite de la limite de 120 s ; au dépassement le run reste « en cours » pour toujours (marge mesurée 52 à 71 s) → limite propre et statut final | `docs/audits/sondes/ADCG/C-ADCG-014.py` | ADCG35 |
| C-ADCG-015 | PF3.2 | C10 | S2 | `backend/django_core/apps/reporting/kpi_alertes.py::_compute_jours_depuis_dernier_drill_reussi` | l'alerte sur les exercices de restauration est muette quand aucun n'a jamais réussi → « jamais réussi » déclenche l'alerte | `docs/audits/sondes/ADCG/C-ADCG-015.py` | ADCG36 |
| C-ADCG-016 | PF3.2 | C13 | S2 | `backend/django_core/core/backup.py::executer_restauration` | aucune procédure exécutable de restauration de la production : le runbook ne décrit que l'exercice, le script ne restaure rien, les rôles ne sont pas dans le dump → procédure testée base, rôles, fichiers | STATIQUE | ADCG37 |
| C-ADCG-017 | PF3.2 | C13 | S3 | `backend/django_core/core/backup.py::restore_drill` | l'exercice « réussit » même sur une restauration vide ou un dump très ancien ; un écart par société n'est qu'un avertissement → un écart fait échouer l'exercice | `docs/audits/sondes/ADCG/C-ADCG-017.py` | ADCG38, ADCG39 |
| C-ADCG-018 | PF3.2 | C10 | S3 | `backend/django_core/core/serializers.py::BackupRunSerializer` | une société peut créer un run « exercice de restauration » terminé qui fausse l'alerte de toutes les sociétés → types système refusés depuis l'API | `docs/audits/sondes/ADCG/C-ADCG-018.py` | ADCG40 |
| C-ADCG-019 | PF3.2 | C10 | S3 | `backend/django_core/core/backup.py::resume_sauvegardes` | le « dernier exercice » servi à l'écran et à l'API publique est le dernier ÉCHEC (prod : 05/10 « echec », 5 réussites depuis) → dernier exercice réel, âge sur le dernier succès | `docs/audits/sondes/ADCG/C-ADCG-019.py` | ADCG41, ADCG42 |
| C-ADCG-021 | PF3.3 | C4 | S3 | `backend/django_core/erp_agentique/settings/base.py::MINIO_ACCESS_KEY` | deux variables MinIO déclarées ne sont lues par personne ; l'application tourne avec les identifiants racine du stockage → une variable par réglage, lue | STATIQUE | ADCG43 |
| C-ADCG-022 | PF3.7 | C13 | S2 | `backend/django_core/core/health.py::etat_ready` | le point de santé ne teste que la base et le battement de beat (Redis tombé : 200) ; aucun `healthcheck` dans les fichiers compose → santé qui reflète les services | `docs/audits/sondes/ADCG/C-ADCG-022.py` | ADCG13, ADCG14 |
| C-ADCG-023 | PF3.7 | C13 | S2 | `scripts/nightly-qa.ps1::Invoke-NightlyPass` | le QA nocturne du poste est mort depuis le 14/10 : la tâche lance un script absent du checkout, sans trace ni contrôle du dernier passage → lanceur indépendant du checkout, échec visible | STATIQUE | ADCG15, ADCG16, ADCG17 |
| C-ADCG-024 | PF3.7 | C13 | S3 | `backend/django_core/erp_agentique/celery.py::_yhard6_on_task_failure` | un échec de tâche planifiée ne prévient personne (prod : 42 exceptions en 24 h) ; un deploy automatique en échec non plus → échec répété signalé | STATIQUE | ADCG18 |
| C-ADCG-025 | PF3.7 | C10 | S3 | `backend/django_core/core/health.py::sha_deploye` | le commit déployé n'est jamais transmis au conteneur (prod : `sha` nul) → le deploy pose le commit servi | STATIQUE | ADCG19 |
| C-ADCG-026 | PF3.7 | C13 | S3 | `backend/django_core/apps/ventes/coherence/contexte.py::ContexteAudit.donnees_devis` | l'auditeur de cohérence nocturne échoue chaque nuit sur 6 devis impossibles à rendre (aucun onduleur reconnu) et renvoie le même résumé → un devis non rendable est un verdict, pas un échec | STATIQUE | ADCG44, ADCG45 |
| C-ADCG-027 | PF3.7 | C13 | S3 | `backend/django_core/apps/ventes/tasks.py::audit_coherence_nuit` | la tâche nocturne lève une erreur APRÈS l'envoi du résumé (« 1 règle sans verdict », 6 erreurs de règle) : même échec et même résumé chaque nuit → une règle qui ne peut pas juger est un verdict compté une fois | STATIQUE | ADCG44 |
| C-ADCG-028 | PF3.8 | C13 | S3 | `scripts/sonde.py::CONTENEUR` | les sondes d'audit visent en dur un conteneur monté sur un checkout qui peut être périmé (5 999 commits de retard), sans le dire → la sonde annonce le commit du code joué | STATIQUE | ADCG20, ADCG100 |
| C-ADCG-029 | PF3.8 | C4 | S3 | `scripts/gc-workspace.ps1::Invoke-Gc` | le nettoyage des worktrees n'est appelé par personne et ignore le préfixe `worktree-agent-` (51 Go, 131 worktrees le 10/11) → purge régulière aux préfixes réels | STATIQUE | ADCG21, ADCG22 |
| C-ADCG-030 | PF3.8 | C13 | S3 | `scripts/e2e-local.sh::stop` | l'arrêt coupe la base, Redis et le stockage partagés de toutes les sessions → n'arrête que ce qu'il a démarré | STATIQUE | ADCG23 |
| C-ADCG-031 | PF3.8 | C11 | S3 | `scripts/preflight.ps1::Invoke-Preflight` | `CLAUDE.md` (étape 3, plancher de merge) et l'en-tête du script demandent encore un test docker avant le push, contre la règle du 27/10 → une seule consigne | STATIQUE | ADCG24 |
| C-ADCG-032 | PF3.8 | C14 | S3 | `scripts/audit_registre.py::acceptation` | la garde d'acceptation est relancée groupe par groupe : la liste des contre-visites dues prend 309 s → un seul calcul | STATIQUE | ADCG25 |
| C-ADCG-033 | PF3.4 | C13 | S2 | `scripts/check_cve_severite.py::main` | l'audit des dépendances ne peut pas échouer (tuyau sans `pipefail`) : 31 vulnérabilités graves imprimées, étapes vertes ; trois manifestes hors audit → garde réellement bloquante sur tous les manifestes | `docs/audits/sondes/ADCG/C-ADCG-033.py` | ADCG60, ADCG61, ADCG62, ADCG63 |
| C-ADCG-034 | PF3.4 | C13 | S2 | `scripts/fuzz/api_fuzz_scope.py::resume_markdown` | l'agrégateur du fuzz hebdomadaire compte toujours 0 constat (format lu ≠ format écrit) : 5 tranches rouges, alerte verte, aucune issue → compteur exact, issue mise à jour | `docs/audits/sondes/ADCG/C-ADCG-034.py` | ADCG64 |
| C-ADCG-035 | PF3.4 | C12 | S3 | `scripts/codemap_fingerprint.py::main` | 14 PR Dependabot sur 40 échouent sur l'empreinte de la carte, qu'elles ne peuvent pas régénérer ; un bump incompatible bloque tout son groupe, correctifs critiques compris → PR de dépendances fusionnables | STATIQUE | ADCG65, ADCG66, ADCG67 |
| C-ADCG-036 | PF3.4 | C13 | S3 | `frontend/e2e/i18n-quote-journey.spec.js::NTI18N47` | le contrôle nocturne est rouge 7 nuits : tests du site lancés avant sa construction ; un parcours ne clique qu'une fois là où une confirmation est désormais demandée → nocturne vert | `docs/audits/sondes/ADCG/C-ADCG-036.py` | ADCG68, ADCG69 |
| C-ADCG-037 | PF3.4 | C13 | S3 | `scripts/nightly_alert_gate.py::main` | l'alerte nocturne commente la même issue sans jamais la fermer au retour au vert (39 commentaires) → issue fermée au vert, rouge nouveau distinct | STATIQUE | ADCG70 |
| C-ADCG-038 | PF3.4 | C14 | S3 | `scripts/ci_merge_group_reuse.py::est_allege` | tout run de PR est jugé « allégé » (le journal recopie le script) : le vert n'est jamais repris par la file, la CI complète tourne deux fois → décision sur la sortie réelle | `docs/audits/sondes/ADCG/C-ADCG-038.py` | ADCG71 |
| C-ADCG-039 | PF3.4 | C11 | S3 | `scripts/ci_guards.py::main` | trois contrôles de sécurité annoncés bloquants ne sont ni requis ni joués dans la file de fusion → bloquants pour de bon | STATIQUE | ADCG72 |
| C-ADCG-040 | PF3.6 | C14 | S3 | `load/locustfile.py::ErpUser` | les tests de charge ne mesurent rien : l'un est rouge 9 fois sur 10 sur des erreurs de scénario, l'autre tourne sur une base vide → charge réaliste, seuil qui échoue pour de bonnes raisons | STATIQUE | ADCG73 |
| C-ADCG-041 | PF3.4 | C14 | S3 | `scripts/ci_shard.py::main` | le lot 0 des tests backend est le chemin critique (suite d'étanchéité en série) : gate de 12,7 à 16,5 min pour 6 à 10 annoncés → lots équilibrés | STATIQUE | ADCG74 |
| C-ADCG-042 | PF3.5 | C20 | S3 | `scripts/forme_code/baseline_grossit.py::BASELINES` | des listes gelées échappent au cliquet ou se repèrent par numéro de ligne (un registre passé de 3 à 70 entrées, 57 commits de recalage en 30 jours) → toute liste sous le cliquet, par symbole | STATIQUE | ADCG75, ADCG76, ADCG77 |
| C-ADCG-043 | PF3.5 | C20 | S3 | `scripts/check_audit_dossier.py::verifier_methode` | des gardes n'échouent jamais : plafond de la méthode non câblé, 318 identifiants périmés en simple rapport, ancre introuvable en rapport, vert si le fichier de données manque → une garde échoue ou n'existe pas | STATIQUE | ADCG78, ADCG79, ADCG80, ADCG81 |
| C-ADCG-044 | PF3.5 | C13 | S3 | `scripts/check_tests_sautes_environnement.py::_sites_fichier` | un test sauté par `raise unittest.SkipTest` n'est pas vu par la garde des sauts signés → tout saut est vu | STATIQUE | ADCG82 |
| C-ADCG-045 | PF3.6 | C14 | S3 | `scripts/check_exports_bornes.py::EXCEPTIONS` | 37 exports synchrones sans plafond sont gelés sans échéance (journal des ventes, grand livre, valorisation) → exports bornés ou dette datée | STATIQUE | ADCG46 |
| C-ADCG-046 | PF3.6 | C14 | S3 | `backend/django_core/apps/ventes/serializers_facturation.py::BonCommandeSerializer.get_facturable` | la liste des bons de commande fait une à deux requêtes par ligne dans le cas courant, que le test existant ne couvre pas → budget tenu sur le cas courant | STATIQUE | ADCG47 |
| C-ADCG-047 | PF3.6 | C14 | S3 | `scripts/check_query_budgets.py::_has_budget_test` | le manifeste des budgets annonce 12 et 23 requêtes quand les tests en tolèrent 15 à 40 ; une entrée vise une route inexistante → valeur testée = valeur du manifeste | STATIQUE | ADCG48, ADCG49 |
| C-ADCG-048 | PF3.6 | C14 | S3 | `backend/django_core/apps/visites/views.py::VisiteTerrainViewSet` | la liste des visites n'est ni paginée ni plafonnée → liste bornée | STATIQUE | ADCG50 |
| C-ADCG-050 | PF3.8 | C13 | S3 | `scripts/audit_tache.py::listes_figees` | le générateur de clauses plante sur une ancre de symbole et sur un fichier JSX, et compte « 0 écran » pour une action appelée par un écran → clauses exactes ou refus en clair | STATIQUE | ADCG83, ADCG84 |
| C-ADCG-051 | PF3.8 | C13 | S3 | `scripts/plan_claims.py::cmd_claim` | le retour arrière du « tout ou rien » supprime un bail déjà tenu ; les échecs d'envoi sont avalés ; deux sessions du même poste partagent le même propriétaire ; aucun test → baux fiables et testés | STATIQUE | ADCG85, ADCG86 |
| C-ADCG-052 | PF3.8 | C11 | S3 | `scripts/plan_lanes.py::apply_contract_pairing_gate` | la règle de contrat front et back refuse sur simple co-présence et ne reconnaît pas une tâche qui porte ses deux moitiés → refus seulement sur un lien réel | STATIQUE | ADCG87 |
| C-ADCG-053 | PF3.8 | C13 | S3 | `scripts/plan_lanes.py::load_build_order` | les outils de plan continuent en silence sur une entrée malformée (ordre de vague tronqué : 59 arêtes lues 6 ; ligne de tâche cassée) → échec bruyant | STATIQUE | ADCG88, ADCG89 |
| C-ADCG-054 | PF3.9 | C13 | S2 | `apps/web/worker/deadLetter.mjs::resendDeadLetters` | un lead refusé par le CRM part en file de secours, échoue à chaque renvoi et expire après 7 jours sans alerte ; le visiteur a reçu une confirmation → échec durable signalé | STATIQUE | ADCG51 |
| C-ADCG-055 | PF3.9 | C8 | S3 | `frontend/src/features/auth/store/authSlice.js::logoutUser` | les aperçus de documents mis en cache par le service worker ne sont pas purgés à la déconnexion (poste partagé) → cache purgé à la déconnexion | STATIQUE | ADCG52 |
| C-ADCG-056 | PF3.9 | C12 | S3 | `frontend/src/lib/monitoring.js::initMonitoring` | la politique de sécurité de contenu bloquerait Sentry et le fond de carte IGN s'ils étaient activés, et aucune violation ne remonte → politique alignée, violations remontées | STATIQUE | ADCG53, ADCG54 |
| C-ADCG-057 | PF3.9 | C10 | S3 | `apps/web/worker/headers.mjs::applySecurityHeaders` | le widget d'estimation prévu pour une iframe partenaire est interdit d'iframe par les en-têtes du site → exception pour ce chemin | STATIQUE | ADCG55 |
| C-ADCG-058 | PF3.9 | C9 | S3 | `apps/web/src/pages/api/_apiBase.ts::resolveApiBase` | six pages du site lisent l'adresse de l'API en direct au lieu du lecteur unique → une seule lecture | STATIQUE | ADCG56 |
| C-ADCG-059 | PF3.4 | C12 | S3 | `scripts/check_parite_image_ci.py::main` | aucune CI ne construit les images de production ; la garde de parité ignore la version de Python → un Dockerfile de production cassé rougit la CI | STATIQUE | ADCG90, ADCG91 |
| C-ADCG-060 | PF3.1 | C13 | S3 | `scripts/check_safe_migrations.py::main` | aucune sauvegarde avant `migrate` ; la garde ne voit pas une suppression de lignes dans une migration de données → dump avant migration, suppression signalée | STATIQUE | ADCG92, ADCG93 |
| C-ADCG-061 | PF3.7 | C13 | S2 | `backend/django_core/core/health.py::_check_storage` | rien ne surveille l'espace disque du serveur (prod : 50 %, 21 Go de cache de build jamais purgé) → espace libre mesuré, seuil signalé | STATIQUE | ADCG94 |
| C-ADCG-062 | PF3.3 | C13 | S3 | `backend/django_core/core/health.py::check_services` | les limites mémoire supposent 16 Go (15,5 cumulés pour 7,75 réels) et rien ne protège la base de l'arrêt mémoire → limites recalibrées, base protégée | STATIQUE | ADCG95 |
| C-ADCG-063 | PF3.2 | C13 | S2 | `scripts/auto-deploy.sh::LAST` | l'état du serveur hors dépôt (service de deploy, fichier de secrets) n'a ni copie ni procédure de reconstruction → reconstruction décrite et versionnée | STATIQUE | ADCG96, ADCG97 |
| C-ADCG-064 | PF3.7 | C10 | S2 | `frontend/src/components/TriProblemesBanner.jsx::lire` | les alarmes décidées début novembre ne sont pas armées (prod : ni Sentry ni jeton du résumé) et le bandeau reste muet quand le tri n'a jamais tourné → « jamais tourné » alerte | STATIQUE | ADCG98, ADCG99 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| C-ADCG-003 | requalifié S2 → S3 | le piège est documenté et la sortie SSH affichée montre l'étape en échec ; 9 sorties sur 9 sans restauration (`docs/audits/sondes/ADCG/C-ADCG-003.py`) |
| C-ADCG-013 | requalifié S1 → S2 | la garde est sans effet, mais la purge est un geste manuel, en simulation par défaut, à double confirmation et 30 jours de grâce |
| C-ADCG-014 | réfuté en partie, S2 → S3 | le dump finit bien en « echec » (`core/backup.py::dump_database`) ; seul l'exercice de restauration reste « en cours » ; marge mesurée 52 à 71 s |
| C-ADCG-019 | requalifié (cause corrigée) | le défaut n'est pas l'écran mais le tri de `core/backup.py::resume_sauvegardes` ; confirmé en prod |
| C-ADCG-036 | réfuté en partie | le dépassement « 76 pour 72 liens » n'existe pas sur `main` : artefact du build lancé pendant les tests |
| envoi réel d'e-mail par la pile locale | réfuté | `.env` du checkout principal : moteur d'e-mail en console, clé d'envoi vide |
| requirements classés documentation (C-ADCG-005) | maintenu, latent | prod : paquets installés identiques aux dépendances déclarées le 10/11 |
Porte : 0 réfuté en entier, 2 en partie / 27 vérifiés · 4 gravités revues · seconde lentille : non requise (les 2 S1 sont des absences constatées et mesurées en prod).

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| script d'auto-deploy du serveur | md5 identique au dépôt, lu en prod le 10/11 | personne n'édite le fichier sur le serveur |
| verrou entre deux deploys | `flock` tenu sur toute la durée, libéré à la sortie du processus | les deux chemins gardent le même fichier de verrou |
| cache de base de test en CI | manifeste comparé octet par octet ; chaîne complète rejouée chaque nuit | `ci_testdb_manifest_diff.py` inchangé |
| checks requis | aucun `continue-on-error` ; agrégateurs rouges si un lot est annulé | la protection de branche garde ses 6 contextes |
| Redis, beat, journaux des conteneurs | `appendonly`, `acks_late`, un seul beat, fuseau Africa/Casablanca, rotation 20 Mo × 5 | compose de prod inchangé |
| correctifs de performance APRF | 45 tâches relues, tests présents | — |
| sauvegarde de la base | 33 dumps et 5 exercices réussis, dernier le 10/11 à 03:00 | l'image garde le client PostgreSQL 16 |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-ADCG-1 | Où envoyer la copie des sauvegardes hors du serveur (base et fichiers) ? | ouverte | ADCG32 |
| D-ADCG-3 | Classer un micro-onduleur comme onduleur réseau pour que son devis se rende ? | ouverte | ADCG45 |
| D-ADCG-2 | Fusionner automatiquement les PR Dependabot de sécurité à un seul paquet quand elles sont vertes ? | ouverte | ADCG67 |

## 7. Optionnel (jamais une tâche)
- Dumps derrière PgBouncer — latent : la variable n'est pas posée en prod.
- Liens publics du devis qui re-rendent le PDF à chaque lecture — arithmétique non mesurée.
- Worker Celery sans recyclage ni concurrence explicite — mécanisme lu, effet non mesuré.
- Deux gardes de migrations aux listes d'exceptions presque disjointes — doublon de listes, pas de règle.
- Lot 0 des tests backend plus long que les autres — voir C-ADCG-041 si le gate dépasse 20 min.
- `.claude/skills/audit/SKILL.md` allongé le 10/11 par deux pièges d'outillage — à replier quand le plafond sera câblé (C-ADCG-043).

## 8. Limites, non couvert, écarts
- Non couvert : aucun deploy ni aucune restauration réels joués ; unités systemd du serveur ; tableau de bord Cloudflare ; option « Backups » de l'hébergeur (non vérifiée) ; environ 85 gardes lues par leur en-tête seulement ; identité des 4 devis réels que l'auditeur de cohérence ne sait pas rendre.
- Écart à la méthode : sondes écrites pour l'hôte (sans Django ni conteneur), lancées à la main et non par `scripts/sonde.py`, qui vise un conteneur monté sur un code périmé → ponctuel : le défaut de l'outil est le constat C-ADCG-028.
- Écart à la méthode : deux lanes ont envoyé des requêtes de lecture vers les hôtes publics (point de santé, en-têtes) → ponctuel : consigne ajoutée aux briefs suivants.
- Écart à la méthode : pas de tâche d'acceptation en navigateur (parcours sans écran) → l'acceptation du groupe est le rejeu des 20 sondes.
- Incident prod : aucun incident nouveau ; l'incident `prod-sans-sauvegarde` du 08/10 est clos (38 sauvegardes réussies). Deux risques ouverts sans incident : C-ADCG-011 et C-ADCG-012 → ADCG30, ADCG31, ADCG32 P0.

## 9. Coût et routage
Coût : H0 S6 O10 F0 · jetons sous-agents ≈ 4,7 M · tâches 93 (M0 0 M1 29 M2 0 M3 58 GATED 6).
Routage : `PLAN_AUDIT_DEPLOY.md` 65 · `PLAN_AUDIT_SECURITE.md` 14 · `PLAN_AUDIT_TRANSVERSE.md` 4 · `WEB_PLAN.md` 3 · `PLAN_AUDIT_ANALYSE.md` 2 · `PLAN_AUDIT_DEVIS.md` 1 · `PLAN_AUDIT_FACTURATION.md` 1 · `PLAN_AUDIT_LEAD.md` 1 · `PLAN_AUDIT_MOTEUR.md` 1 · `PLAN_AUDIT_PARAMETRES.md` 1 · acceptation ADCG100 · PR #NUM_PR.
