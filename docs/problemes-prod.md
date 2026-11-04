# Problèmes en production — capture serveur (Sentry backend) et tri du matin

> Conception complète : `docs/boucle-problemes-quotidienne.md`. Décision fondateur D-JPB-2
> (03/11/2026) : **Sentry côté serveur seulement** ; jamais de DSN navigateur (le journal maison
> `reporting.ProblemeClient` garde ce rôle, voir `docs/journal-problemes-utilisateurs.md`).

## Ce que capture Sentry une fois allumé (BPQ9, construit le 03/11/2026)

- chaque **500 Django** (vue DRF ou non) avec sa pile d'appel complète, la route, la société
  (tag `company`, NTPLT46) et l'utilisateur sans donnée personnelle (`send_default_pii=False`) ;
- chaque **tâche Celery en échec** (le SDK s'accroche seul à Celery ; `init_sentry` tourne dans
  chaque worker via `core/apps.py ready()`) ;
- le tag **`request_id`** : le même identifiant que Django renvoie au navigateur dans l'en-tête
  `X-Request-Id` et dans l'enveloppe 500 (`error.request_id`). C'est le lien entre une ligne
  `serveur` du journal des problèmes et l'évènement Sentry qui porte sa trace. Posé par
  `core/middleware.py::RequestIdMiddleware` avant la vue, retiré après (même sur exception) ;
- la **`release`** = sha déployé (`SENTRY_RELEASE`) : Sentry marque « régressé » un problème résolu
  qui revient dans une release plus récente, et « nouveau » ce qui apparaît après un déploiement.

Sans `SENTRY_DSN`, tout cela reste un **no-op total** (aucun import du SDK, aucun appel réseau).

## Allumage (geste de Reda, ~10 minutes)

1. Créer un compte Sentry (palier gratuit : 1 utilisateur, 5 000 erreurs/mois, 30 jours de
   conservation au 03/11/2026) et un projet « Django ». Sentry affiche le DSN
   (`https://…@….ingest.sentry.io/…`).
2. Sur le serveur, dans `/opt/taqinor-os/.env` :

   ```
   SENTRY_DSN=https://…               # le DSN du projet Django
   SENTRY_ENVIRONMENT=production
   SENTRY_TRACES_SAMPLE_RATE=0        # erreurs seulement ; le tracing consommerait le quota
   SENTRY_RELEASE=<sha de main déployé>
   ```

   puis `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` (recréation de
   `django_core`, `celery_worker`, `celery_worker_interactive`, `celery_beat`).
3. **Ne jamais poser `VITE_SENTRY_DSN`** (variable de build du navigateur) : décision D-JPB-2.

`SENTRY_RELEASE` à la main vieillit à chaque déploiement : la bonne place est
`/opt/autodeploy/auto-deploy.sh` (sur le serveur, hors dépôt), qui connaît le sha qu'il déploie —
une ligne `SENTRY_RELEASE=<sha>` réécrite dans `.env` avant le `up -d`. Tant que ce n'est pas fait,
la release reste celle du dernier `.env` posé ; les évènements restent capturés, seul le tri
« régressé / nouveau » perd en précision.

## Vérifier que ça marche (lecture seule)

- `docker logs --since 10m erp-agentique-django_core-1 | grep "Monitoring Sentry initialisé"` :
  une ligne par worker ;
- dans Sentry, l'évènement porte les tags `company`, `request_id` et la release ;
- côté navigateur, la même erreur apparaît dans `manage.py problemes_utilisateurs` (genre
  `serveur`, statut 500) : le `request_id` de l'enveloppe est celui de l'évènement Sentry (le champ
  `request_id` du journal navigateur arrive avec ERR-JPB-REQUEST-ID-PERDU).

## Ce qui n'y est pas (par construction)

- Les **502/504** rendus par nginx ou Caddy pendant un redémarrage : Django ne les voit pas,
  Sentry non plus. Le journal navigateur les enregistre (genre `serveur`, statut 502) et le
  résumé les classe `deploiement` (BPQ1/BPQ2).
- Un worker **tué** (OOM, SIGKILL, délai gunicorn 120 s) : aucun code Python ne s'exécute. Seule
  trace : la ligne gunicorn du conteneur et le 502/499 nginx.
- Le service **FastAPI IA** : processus séparé, non instrumenté (ERR-JPB-IAAPI-SANS-JOURNAL).

## Tri du matin (skill construit : BPQ5 ; routine cloud : BPQ8)

Skill `.claude/skills/problemes-prod/SKILL.md`, lecture seule sur la prod. Il lit `health/ready`, le
résumé des problèmes (`GET /api/django/reporting/problemes/resume/?jours=1&tri=1`, BPQ4, jeton de
service), les issues et runs GitHub des alertes nocturnes, ignore `deploiement`/`connectivite`/
`maintenance` sauf récurrence, dédoublonne sur la `Signature:` contre `docs/ERROR_PLAN.md`
(toutes lignes + intake), note la sévérité (1 personne bloquée sur un geste métier = High, ≥ 3
personnes = Critical) et dépose les `ERR-PROD-<MODULE>-<SLUG>` par UNE PR docs-only
(`gh pr merge --auto --merge`). Rien à déposer : aucun commit. Sortie : `PROBLEMES_PROD_STATUS:
EMPTY|MORE`. Le format des lignes est gardé par `scripts/check_err_prod.py` (BPQ13).

- **Kill switch** : `docs/problemes-prod.config.yml` (`enabled: false`, `max_minutes`,
  `max_findings_per_run`, `base_url`).
- **Sur le poste de Reda** : `powershell -File scripts/nightly-qa.ps1 -Skill problemes-prod`
  (aucun docker, aucun seed, aucun Playwright ; jeton dans `PROBLEMES_RESUME_TOKEN`).
- **Routine cloud** à 07:07 Africa/Casablanca (D-JPB-1, 03/11/2026) : BPQ8.

## Routine cloud du tri du matin (BPQ8, D-JPB-1 = cloud) — recette pas à pas pour Reda

Le skill `problemes-prod` tourne dans le cloud Claude Code : aucune machine allumée, aucun accès
SSH. Il ne lit QUE l'API (le skill détecte l'absence de SSH et ne tente jamais de se connecter).
Coût = l'usage de l'abonnement Claude de Reda (aucune clé API).

1. **Créer le jeton côté serveur** (une fois). Générer une valeur aléatoire longue, la poser dans
   `/opt/taqinor-os/.env` sous `PROBLEMES_RESUME_TOKEN=<valeur>`, recréer `django_core`
   (`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d django_core`). Sans
   cette variable le endpoint de résumé répond fermé (BPQ4). Garder la valeur pour l'étape 3 ; ne
   jamais la committer ni la coller dans une conversation.
2. **Créer l'environnement cloud** « taqinor-prod-lecture » sur claude.ai/code : accès réseau
   *Custom*, avec seulement `api.taqinor.ma`, `github.com` et `api.github.com` (+ `*.sentry.io`
   si l'API Sentry est lue, voir plus haut). Aucune autre sortie.
3. **Secret réseau** : dans cet environnement, enregistrer `PROBLEMES_RESUME_TOKEN` comme secret
   réseau injecté en `Authorization: Bearer` sur l'hôte `api.taqinor.ma`. Il n'est **jamais** une
   variable d'environnement visible de la session (la routine ne peut donc ni l'afficher ni le
   copier dans une PR).
4. **Créer la routine** sur claude.ai/code/routines : dépôt `taqinor/taqinor-os`, environnement
   « taqinor-prod-lecture », déclencheur quotidien à **07:07 Africa/Casablanca**, consigne :
   `run the problemes-prod skill`. Autoriser la routine à ouvrir des PR docs-only et à les mettre
   en file de fusion (`gh pr merge --auto --merge`), rien de plus.
5. **Vérifier** : lancer la routine à la main une fois ; la sortie doit finir par
   `PROBLEMES_PROD_STATUS: EMPTY` ou `MORE`, et `health/ready` doit afficher un
   `dernier_tri_problemes` récent (BPQ6 : sans cela, le bandeau d'alerte apparaît aux superusers
   après 48 h).

**Rotation du jeton** (à chaque départ d'une personne ayant vu la valeur, ou tous les 6 mois) :
nouvelle valeur dans `.env` serveur + recréation de `django_core`, puis mise à jour du secret
réseau de l'étape 3. L'ancienne valeur cesse de marcher dès la recréation.

**Kill switch** : `docs/problemes-prod.config.yml`, `enabled: false` (commit sur `main`) — la
prochaine passe imprime `PROBLEMES_PROD: DISABLED (config flag off)` sans rien écrire. L'autre
interrupteur est la mise en pause de la routine sur claude.ai/code/routines. Le jeton ne se révoque
que côté serveur (retirer la variable).

## Clôture prouvée et rapport du lundi (BPQ11)

Une `ERR-PROD` cochée n'est pas « réglée » tant que la prod ne le prouve pas.

- **Régression** : si la `Signature:` d'une `ERR-PROD` cochée réapparaît dans le résumé **≥ 7 jours
  après le déploiement du correctif**, le skill la marque `regresse` et dépose un nouvel item
  `<ID>-2` qui cite l'original (id, signature, sha du correctif). L'item d'origine n'est pas décoché.
- **Date de déploiement du correctif** : le premier sha de `erp:demarrages` (`dernier_demarrage` de
  `health/ready`, BPQ2) qui contient le commit du correctif (`git merge-base --is-ancestor`).
  Une réapparition avant ces 7 jours, ou avant tout déploiement, n'est pas une régression.
- **En attente de déploiement** : un correctif mergé sur `main` mais dont le commit n'est pas
  encore dans le sha déployé reste « en attente de déploiement » ; le résumé le dit, le skill ne
  dépose rien dessus.
- **Rapport du lundi** (sortie de la routine, et le même résumé affiché par BPQ6 aux superusers) :
  1. problèmes de la semaine (signatures distinctes) ;
  2. personnes touchées (somme des `personnes` du résumé, sans doublon d'identifiant) ;
  3. top 3 par personnes touchées puis par gravité ;
  4. corrigés (cochés et absents depuis ≥ 7 jours après déploiement) ;
  5. régressés (`<ID>-2` ouverts cette semaine) ;
  6. en attente de déploiement.

## Sonde externe hors serveur (BPQ12, D-JPB-7 = oui) — geste de Reda, ~5 minutes

Seule mesure qui vit HORS du serveur : si la machine, Caddy ou Django tombe, rien sur le serveur ne
peut alerter. `GET https://api.taqinor.ma/api/django/core/health/ready/` (public, sans jeton) répond :

- `200 {"status": "ready", …}` : base joignable et Celery Beat vivant (ou heartbeat pas encore reçu) ;
- `503 {"status": "not-ready", …}` : la base ne répond pas ;
- `503 {"status": "degraded", …}` : Celery Beat arrêté (heartbeat périmé) — plus de relances, de tri
  ni de sauvegardes planifiées.

Création (tableau de bord Cloudflare, JAMAIS un jeton API Cloudflare dans le dépôt) :

1. Cloudflare → zone `taqinor.ma` → **Traffic → Health Checks → Create** (gratuit sur l'offre Free ;
   à défaut, un moniteur HTTP gratuit équivalent, ex. UptimeRobot).
2. Adresse `api.taqinor.ma`, chemin `/api/django/core/health/ready/`, HTTPS, port 443, méthode GET,
   code attendu `200`, intervalle 5 min (le minimum de l'offre), 2 échecs consécutifs avant alerte.
3. **Notifications → Add → Health Check status notification** sur ce contrôle, destinataire l'e-mail
   de Reda.
4. Vérifier : l'onglet du contrôle passe « Healthy » ; arrêter `celery_beat` quelques minutes au-delà
   du seuil de péremption doit faire passer le contrôle « Unhealthy » et envoyer l'e-mail.

Rien côté serveur ni `.env` : seule la réponse 503 sur beat arrêté est dans le code
(`core/views.py::health_ready`, `core/health.py::check_beat`).