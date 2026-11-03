# Boucle quotidienne des problèmes — revue L3 du journal (03/11/2026) et conception

> Question de Reda (02/11, parcours cadence de Meryem) : « quand quelqu'un travaille sur mon ERP et
> rencontre un problème de connexion ou n'importe quel autre problème, avec ou sans notification, est-ce
> consigné quelque part ? et peut-on lire ce journal pour trouver TOUS les problèmes que les utilisateurs
> rencontrent et les résoudre ? ». Le journal YJPB (PR #1231, `docs/journal-problemes-utilisateurs.md`)
> répond à la première moitié. Ce document répond à la seconde : ce qui marche, ce qui manque, et la
> boucle quotidienne qui transforme les problèmes vécus en corrections. Revue L3 (03/11/2026) : 5 lanes,
> 1 vérificateur indépendant, 1 critique final ; prod lue en lecture seule (accord permanent).

## 1. Ce qui est vrai en production au 03/11 (mesuré, lecture seule)

| Fait | Mesure |
|---|---|
| Journal déployé | PR #1231 mergée 02/11 17:43, en prod depuis le déploiement de 10:46 le 03/11 |
| Lignes en 36 h | **38**, toutes d'UNE personne (Meryem, Chrome Windows + Chrome Android) ; 5 utilisateurs actifs |
| Dont bruit de déploiement | 22 × 502 à 10:44:52 (25 × 502 nginx dans la même seconde, django recréé 10:44:46) — comptées, pas distinguées |
| Dont connectivité téléphone | 6 × ECONNABORTED à 06:01 sur Android, 6 routes de polling la même seconde ; aucune de ces requêtes n'a atteint nginx |
| Dont vrai défaut | 4 × délai 20 s sur `POST ventes/devis/<id>/replace-lines/` (devis 491/492) : nginx `urt≈20 s, us="-"`, **mais Django a fini ensuite** (devis 491 mis à jour 10:56:25, 492 à 12:43:02) : l'utilisatrice a vu « La connexion a expiré » alors que son travail était enregistré, et a recliqué |
| Lignes `script` / `ecran` | **0** (voir J1 : l'écran tombé ne peut pas émettre) |
| Routes > 5 s (24 h) | `devis/auto/` 16-47 s (délai dédié 120 s, OK) ; `devis/<id>/proposal/` 14-19 s (90 s, OK) ; `kpi-federes` 11-13 s ; `etude-horaire/preview` ≤ 12 s ; `crm/leads/` 376 appels, moy 2,6 s, max 10 s |
| 500 Django (24 h) | 0 ligne. 90 tracebacks = 100 % avertissements « comportement dégradé » (ai.search ×20, crm.stages ×10, permissions ×5) + 1 erreur gunicorn |
| Celery (24 h) | 204 lignes ERROR/Traceback : 80 « core.rls has local company fk » (bruit) + `ventes.audit_coherence_nuit` **tuée chaque nuit** (soft 120 s à 05:17, hard 180 s à 05:18, SIGKILL) → l'auditeur de cohérence ne finit jamais, rien persisté, aucun digest |
| Rétention | `core.run_retention: apply=False policies=11` → les 11 purges (dont les 90 j du journal) sont des **essais à blanc** ; `RETENTION_AUTO_APPLY` absent du `.env` prod |
| Mémoire | 8 Go, 454 Mo libres ; django_core 2,7/3 Gio ; workers gunicorn 895/773/1258 Mio **après** le correctif AOOM (#1233 déployé) ; `GUNICORN_MAX_REQUESTS` absent du `.env` → filet désarmé ; 5 OOM-kills le 02/11 |
| Sentry | DSN absent ; **mais** `sentry-sdk==2.70.0` est dans `requirements.txt` et `@sentry/react` dans `package.json` (la doc disait « non installé ») |
| Nightly QA (portable) | `C:\dev\taqinor-os\scripts\nightly-qa.ps1` **supprimé du disque** (` D` dans `git status`), checkout principal figé à 7bb3a35d3 (14/10, 4 435 commits derrière) ; tâche « Interactive only » sans StartWhenAvailable/WakeToRun ; dernier résultat `-196608` = « fichier -File introuvable » ; dernier intake QAH : 14/10 |
| error-autopilot | jamais planifié (dernier run manuel 29/09) ; aucune routine cloud |
| Nocturnes GitHub | `release-verify` rouge 30/10, 31/10, 03/11 (e2e-full) ; `api-fuzz-full` rouge 01/11 ; issues d'alerte **ouvertes et sans réponse** : #726 (depuis 28/09, 33 commentaires du bot), #1002, #461 |
| ERROR_PLAN.md | 184 cochées, 1 ouverte (bloquée) → **le drain marche ; c'est l'ENTRÉE qui est morte** |

## 2. Défauts du journal (vérifiés code + prod, chacun déposé dans `docs/ERROR_PLAN.md` sous `ERR-JPB-*`)

- **J1 — genre `ecran` jamais émis.** Les deux error boundaries n'appellent pas le journal ; React 19 (`onCaughtError` par défaut = `console.error`, rien vers `window.error`) et `main.jsx` sans `onCaughtError` → un écran tombé = 0 ligne. Un chunk 404 après déploiement (`import()` de `React.lazy`) finit dans la boundary : invisible aussi.
- **J2 — plafond 40 et dédoublonnage = état de MODULE** (vie de l'onglet SPA) : un déploiement consomme 22/40 ; au 40e l'onglet est muet jusqu'au rechargement complet.
- **J3 — `estIdentifiant` masque les slugs ≥ 20 caractères** : `/reporting/approbations-en-attente/` → `/reporting/<id>/`, `bons-commande-fournisseur` → `<id>` (exécuté) ; ≥ 20 routes de `src/api` fusionnent.
- **J4 — le scénario de l'incident ne laisse aucune ligne.** Le refresh de session passe par axios brut sans intercepteur ni délai ; `catch {}` avale TOUT (502 de déploiement, coupure, délai) ; `emitSessionExpired()` ouvre la modale « reconnectez-vous » sur une session encore valide, et `return` avant le journal. C'est très probablement le « je dois me déconnecter/reconnecter » de Meryem.
- **J5 — `request_id` perdu** : Django le renvoie (en-tête `X-Request-Id` + `error.request_id`) ; l'émetteur ne le lit pas, le modèle n'a pas le champ, nginx ne le logge pas.
- **J6 — `iaApi.js`** (copilote, agent SQL, OCR, transcription, pages IA) : deuxième instance axios sans délai ni journal ; FastAPI n'a aucun `exception_handler`.
- **J7 — `replaceLignesDevis` sans délai dédié** (20 s global) alors que `devis/auto`, `proposal`, `accepter` ont 90-120 s ; nginx `proxy_read_timeout` et gunicorn `--timeout` sont à 120 s : le navigateur abandonne un travail que le serveur termine.
- **J8 — résumé** : `ecran` absent de la clé (tous les `TypeError` fusionnent ; « depuis quel écran ? » sans réponse) ; `dernier cas` en UTC.
- **J9 — la balise n'a pas de refresh** : cookie d'accès 30 min → onglet en veille → `POST` 401 → ligne perdue en silence.
- **J10 — fenêtre de déploiement non distinguée** (le sous-comptage supposé n'est pas confirmé : 22 lignes pour 25 × 502).
- **J11 — purge 90 j = dry-run** tant que `RETENTION_AUTO_APPLY` n'est pas posé (doc muette).
- **J12 — doc** : « sentry-sdk non installé » et « écran tombé couvert » sont faux ; « hors session » sous-estime (portail client par jeton, 6 écrans SPA sans login, `/proposal/<tok>`).
- **J13 — sans test** : câblage des boundaries, plafond, slugs ≥ 20, chemin refresh, request_id, throttle, `log_format taqinor`, `x-journaux`.

## 3. Ce qui n'est capturé nulle part durablement

- **S1** 500 Django : console → `docker logs` (rotation 20 Mo × 5), meurt au redéploiement. Pas de table, pas de mail, pas de Sentry.
- **S2** Échecs Celery : `task_failure` → compteurs en mémoire (`core/metrics`), rien de durable ; un kill dur ne déclenche rien.
- **S3** Worker tué (OOM, SIGKILL, délai 120 s) : aucun handler Python ; seule la ligne gunicorn + 502/499.
- **S4** Lettres mortes de l'outbox (WhatsApp/e-mail : `STATUT_DEAD`) et `BackupRun` en échec (105/105, incident ouvert 08/10) : en base, jamais résumés.
- **S5** Bruit : 4 sources d'avertissement avec traceback (ai.search → `contrats.contrat`/`kb.kbarticle` parqués ; crm.stages → `import STAGES` impossible en conteneur avant le repli `/opt/STAGES.py` qui, lui, réussit ; permissions → jeton périmé ; rls → `FieldDoesNotExist` normal) : 90 traces/24 h pour 0 incident.
- **S6** Beat mort : détecté par `health/ready` (`degraded`), que seul `deploy-prod.ps1` lit.
- **S7** Nocturnes GitHub : alertes ouvertes, personne ne les lit.
- **S8** Visiteurs hors session (portail, proposal, kiosque, fournisseur) : rien côté navigateur, par construction.

## 4. La boucle quotidienne (conception retenue)

Principe : **une source durable** (la base), **un résumé** lisible par un agent (commande + API, même fonction),
**un dépôt** dans `ERROR_PLAN.md` (format existant), **un drain** (existant, prouvé : 184/185), **une preuve
de clôture** (la signature disparaît), et **une alarme si la boucle elle-même s'arrête**.

### Couche 0 — réparer les détecteurs existants (sans conception, semaine 1)
- Nightly QA : restaurer `scripts/nightly-qa.ps1` + `scripts/pile_locale.ps1` sur le checkout principal (le dépôt les a), remettre `main` propre et à jour ; `setup-nightly-qa.ps1` : `StartWhenAvailable` + `WakeToRun` ; TTL sur le verrou ; journal de bord hors dépôt ; historique du planificateur activé.
- Auditeur de cohérence : délais propres à la tâche (mesurer d'abord `audit_coherence --json --no-persist` en prod), relancer `SoftTimeLimitExceeded` avant les `except Exception`, persister par lots, cache calepinage/lignes par devis.
- Bruit : les 4 sources en DEBUG sans `exc_info` (ou première tentative corrigée).
- Reda, `.env` serveur : `GUNICORN_MAX_REQUESTS=300`, `GUNICORN_MAX_REQUESTS_JITTER=60`, `RETENTION_AUTO_APPLY=1`, puis recréer les conteneurs.
- error-autopilot : **ne pas** le ré-armer tel quel sur le portable (son STEP 0 joue les tests Django en docker local, contraire à « CI d'abord ») ; sa surface « nocturnes rouges + issues d'alerte » passe dans la couche 3.

### Couche 1 — capturer (durable)
- Corriger J1-J13.
- Côté serveur : **D-JPB-2** — Sentry **backend seulement** (SDK déjà installé, 1 variable, pas de DSN front donc ni replay ni donnée navigateur) couvre S1-S3 avec `request_id` et le sha de release ; sinon `reporting.ProblemeServeur` minimal (hash de trace + route + jour, dédup obligatoire, exemption RLS, rétention 90 j, hook gunicorn `worker_abort`).
- Fenêtre de déploiement : au démarrage de chaque process Django, un horodatage dans Redis (`erp:demarrages`) ; le résumé classe `deploiement` toute ligne 5xx/`reseau` dans les 3 minutes qui suivent.
- Bundle périmé : `window.addEventListener('vite:preloadError')` → ligne `ecran` `ChunkLoadError` + un rechargement unique ; bandeau « Nouvelle version » monté dans le shell ERP (aujourd'hui seulement dans 4 écrans adsengine).

### Couche 2 — résumer (une fonction, deux portes)
- `manage.py problemes_utilisateurs --json --jours 1` : lignes navigateur + outbox mortes + sauvegardes en échec + beat/health + fenêtres de déploiement ; clé `(genre, méthode, route, statut, code, ecran)` ; occurrences, personnes, premier/dernier cas ; classe `deploiement` / `connectivite` (rafale ≥ 4 routes en < 2 s pour une personne) / `maintenance` / `reel` ; tendance J-7.
- `GET /api/django/reporting/problemes/resume/?jours=1` : même JSON, **une seule** authentification : jeton de service `PROBLEMES_RESUME_TOKEN` (en-tête Bearer, plateforme, toutes sociétés — même patron que `RELAIS_API_SECRET`), jamais une clé API société.
- Pas de `signatures.yml` : la ligne `ERR-PROD-*` porte `Signature: genre|méthode|route|statut|code` ; « connu / régressé » = grep d'ERROR_PLAN.

### Couche 3 — trier chaque matin (skill `problemes-prod`, 07:00 Casablanca)
1. `GET /health/ready` (beat, DB, Redis) → `degraded` = item P0 automatique.
2. `GET …/problemes/resume/?jours=1&tri=1` (le `tri=1` horodate le dernier tri dans Redis = battement de cœur).
3. `gh issue list --label nightly-alert …` + `gh run list` des nocturnes → tri ou fermeture motivée.
4. Ignore `deploiement`/`connectivite`/`maintenance` sauf récurrence ; dédoublonne (ERROR_PLAN + intake log) ; sévérité = personnes touchées × gêne (1 personne bloquée sur un geste métier = High ; ≥ 3 personnes = Critical) ; relie la trace serveur par `request_id`.
5. Dépose `ERR-PROD-<MODULE>-<SLUG>` (gabarit qa-explorer, `found via: journal prod <date>`, Confiance « constat prod, lecture seule », test rouge **dans le module existant**, jamais `test_err_*.py`), ligne d'intake, **une** PR docs-only via la merge queue (`gh pr merge --auto --merge`, Auto-fix ON), `PROBLEMES_PROD_STATUS: EMPTY|MORE`. Rien déposé → aucun commit.
- **Où** (D-JPB-1) : routine cloud Claude Code (sans portable ; réseau Custom `api.taqinor.ma` + `github.com` ; secret réseau = le jeton en Bearer) — **recommandé** ; repli : `nightly-qa.ps1 -Skill problemes-prod` sur le portable (SSH possible, mais 20 nuits mortes prouvées). La routine **ne reproduit pas** : le test rouge est écrit par le drain et prouvé par la CI seule (règle « CI d'abord »).
- **Dead-man's switch** : `health/ready` expose `dernier_tri_problemes` ; le shell ERP affiche un bandeau superuser au-delà de 48 h. Le canal que Reda voit est l'ERP lui-même, pas GitHub.

### Couche 4 — corriger
`work on error plan` (existant). Rythme : routine « drain » à 09:00 si `PROBLEMES_PROD_STATUS: MORE`, ou Reda tape la commande. Règles existantes : test rouge dans le module existant, acceptation en direct (3-bis) pour tout parcours visible, Reda déploie.

### Couche 5 — prouver la clôture
Une `ERR-PROD` cochée n'est « résolue » que si sa signature n'apparaît plus **7 jours après le déploiement** du correctif (sinon `regresse` → nouvel item `-2`). Un correctif mergé non déployé reste « en attente de déploiement » (statut nommé). Le lundi, le rapport de la routine donne à Reda : problèmes de la semaine, personnes touchées, top 3, corrigés, régressés, en attente — et le même résumé est affiché dans l'ERP (bandeau/page superuser, tâche BPQ).

## 5. Hors boucle (dit explicitement)
- Navigateur des visiteurs hors session (portail client, `/proposal/<tok>`, kiosque, portail fournisseur) : non journalisé par construction ; leurs 500 serveur sont couverts par la couche 1. Une balise publique bridée = décision **D-JPB-6** (défaut : non).
- Site public `apps/web` (Cloudflare) : aucune capture navigateur ; lettre morte des leads dans le KV du Worker. Hors périmètre ERP, à traiter dans `WEB_PLAN`.
- `/metrics` : compteurs en mémoire par process, aucun scrapeur : ignoré.
- Sondes externes (Cloudflare Health Check / ping gratuit sur `/health/ready`) : seule mesure qui vit hors du serveur ; **D-JPB-7** (défaut : oui si gratuit).

## 6. Décisions à prendre (Reda)
- **D-JPB-1** Où tourne le tri quotidien — **EN ATTENTE (Reda, 03/11)** : « dis-moi d'abord si c'est le même coût en tokens ; on pourra aussi utiliser le portable ET le desktop, celui des deux qui est allumé et a assez de jetons ». Réponse : même coût (routine cloud et `claude -p` local tirent tous deux sur l'usage de l'abonnement, même modèle, même prompt ; la seule différence est l'accès : le cloud lit l'ERP par l'API à jeton (BPQ4), le local peut aussi faire du SSH). Option hybride proposée : une tâche Windows sur CHAQUE PC à 07:00, la première qui pose la claim `refs/plan-claims/tri-problemes:<date>` (`scripts/plan_claims.py`, mécanisme existant) fait le tri, l'autre sort ; le cloud reste possible plus tard sans rien changer au skill.
- **D-JPB-2** — **TRANCHÉ (Reda, 03/11/2026) : Sentry backend seul** (SDK déjà installé, pas de DSN front donc aucune donnée navigateur ; compte gratuit : 1 utilisateur, 5 000 erreurs/mois, 30 j au 03/11). BPQ9 se construit dans sa branche Sentry ; `ProblemeServeur` n'est pas construit.
- **D-JPB-3 / D-JPB-4** — **ACCEPTÉS (Reda, 03/11/2026)** : Reda pose `RETENTION_AUTO_APPLY=1`, `GUNICORN_MAX_REQUESTS=300`, `GUNICORN_MAX_REQUESTS_JITTER=60` dans `/opt/taqinor-os/.env` puis `docker compose up -d` (recréation). Vérification lecture seule ensuite : `core.run_retention: apply=True` dans le log celery à 03:00 et `--max-requests 300` dans `docker inspect` de django_core.
- **D-JPB-5** replace-lines : délai dédié 120 s d'abord, puis tâche de performance (les deux).
- **D-JPB-6** Balise publique hors session (défaut : non). **D-JPB-7** Sonde externe gratuite (défaut : oui).

## 7. La première passe manuelle = cette revue
Le critique final recommandait de **jouer la boucle à la main une fois avant d'automatiser** (c'est l'étape que la
QA de nuit a sautée). C'est fait ici : le résumé prod du 03/11, `health`, les issues et runs nocturnes ont été lus,
et les constats sont déposés dans `ERROR_PLAN.md` (`ERR-JPB-*`) avec les tâches de construction dans
`docs/PLAN.md` (groupe BPQ). Coût de cette passe manuelle : ~15 min de lecture prod + le tri.
