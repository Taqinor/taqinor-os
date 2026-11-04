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
