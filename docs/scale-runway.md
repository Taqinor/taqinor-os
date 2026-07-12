# Scale runway — TAQINOR OS

Document vivant : baseline de capacité mesurée/déduite, config actuelle
chiffrée, et piste de découpage physique quand la boîte unique Hetzner ne
suffit plus. Alimenté par la lane `infra/compose` (SCA7-SCA17, `docs/PLAN.md`
groupe SCA). Aucune section de ce document ne remplace une mesure réelle
faite sur la boîte de production quand elle est marquée « à mesurer » —
c'est un engagement explicite à recalibrer, pas un chiffre définitif.

**Contrainte d'origine de ce document** : rédigé SANS accès SSH/administrateur
à la boîte de production. Toute donnée qui exige la boîte vivante (marges
mémoire réelles, req/s mesurés, point de saturation réel) est marquée
« à mesurer — méthode prête », avec le script `scripts/capacity_probe.py`
committé et la procédure hors heures ouvrées écrite ci-dessous. L'arithmétique
et la configuration, elles, sont calculées à partir des fichiers du dépôt —
donc fiables dès aujourd'hui.

## Baseline 2026-07

### Config actuelle chiffrée (source : fichiers du dépôt, pas la boîte vivante)

| Composant | Réglage actuel | Fichier |
|---|---|---|
| Django gunicorn (prod) | `--workers 3 --threads 4 --preload --timeout 120` | `docker-compose.prod.yml:38-41` |
| Django gunicorn (dev/compose de base) | `--workers 4 --timeout 120 --worker-class sync` (pas de `--threads`) | `docker-compose.yml:22` |
| Celery worker | 1 conteneur, `-Q default,interactive,scheduled`, pas de `--concurrency` explicite (défaut = nombre de CPU de l'hôte, **inconnu pour la boîte Hetzner — à mesurer**) | `docker-compose.yml:81` |
| Celery beat | 1 conteneur, planificateur seul (pas de traitement de tâches) | `docker-compose.yml:97` |
| FastAPI (OCR + agent SQL) | `uvicorn --workers 2` | `docker-compose.yml:39` |
| Postgres | `pgvector/pgvector:pg16` — **stock**, aucun `postgresql.conf` monté avant SCA11 (`shared_buffers=128MB`, `work_mem=4MB`, `max_connections=100` par défaut pg16) | `docker-compose.yml:127` |
| Redis | `redis:7.4-alpine`, une seule instance, broker (db0) + cache (db1) confondus, aucune police d'éviction posée avant SCA10 (défaut `noeviction`) | `docker-compose.yml:153-158`, `settings/base.py:305-324` |
| CONN_MAX_AGE | 60 s (env `DB_CONN_MAX_AGE`, défaut) — connexions Django réutilisées, pas ouvertes/fermées par requête | `erp_agentique/settings/base.py:187-199` |

### Arithmétique connexions DB réelle (calculée depuis les fichiers, pas mesurée)

Chaque thread/worker Django ouvre au plus **une** connexion Postgres
(réutilisée grâce à `CONN_MAX_AGE=60`, jamais fermée/rouverte par requête tant
qu'elle reste valide — `CONN_HEALTH_CHECKS=True` la revalide avant réemploi).
Donc le plafond de connexions Django = workers × threads, pas
workers × threads × requêtes/s.

```
Django (gunicorn prod)      : 3 workers × 4 threads         = 12 connexions max
Celery worker (défaut host) : 1 conteneur × concurrency ?   = INCONNU (à mesurer nproc réel Hetzner)
Celery beat                 : 1 conteneur × 1 (scheduler)   =  1 connexion
FastAPI (SQLAlchemy)        : 2 workers uvicorn × pool_size par défaut 5
                               (SQLAlchemy create_engine() sans pool_size
                               explicite → défaut 5 + max_overflow 10,
                               alloué à la demande, pas au démarrage)
                                                              = jusqu'à 10 en
                                                                usage normal,
                                                                jusqu'à 30 en
                                                                pic (overflow)
                               + moteur SÉPARÉ pour l'agent SQL
                               (SQL_AGENT_DATABASE_URL, backend/fastapi_ia/
                               app/services/sql_agent_service.py:998) —
                               ce 2e moteur n'est instancié QUE quand l'agent
                               SQL est invoqué (clé GROQ_API_KEY posée) et
                               utilise un rôle Postgres LECTURE SEULE dédié
                               (voir docker-compose.yml:45-58) : ne partage
                               pas le pool du premier moteur, ni sa charge
                               habituelle.
----------------------------------------------------------------------------
Plancher connu (sans pic FastAPI, sans Celery concurrency)  : 12 + 1 = 13
Plafond raisonnable observable (FastAPI en usage normal)    : 12 + 1 + 10 = 23
Plafond théorique pire cas (FastAPI en pic + overflow)      : 12 + 1 + 30 = 43
                                                                (+ Celery
                                                                concurrency
                                                                inconnue)

max_connections Postgres (pg16 stock, aucun override)       : 100
```

**Conclusion arithmétique** : même dans le pire cas théorique connu
(43 + Celery), on reste sous `max_connections=100` — MAIS la variable
inconnue est la concurrency par défaut de Celery sur la boîte Hetzner réelle
(dépend du nombre de vCPU du plan Hetzner ; non lisible depuis ce dépôt). Sur
un CX-line Hetzner typique (2-4 vCPU pour un plan CX21/CX31 — hypothèse,
**à confirmer**), Celery ajouterait 2-4 connexions supplémentaires : le total
resterait confortablement sous 100. Le déclencheur documenté en SCA14 pour
pgbouncer (NTPLT58) est : **(workers×threads + celery concurrency) approche
`max_connections`** — ce n'est pas le cas aujourd'hui d'après cette
arithmétique, mais elle doit être recalculée à chaque changement de
dimensionnement (SCA16 rend `GUNICORN_WORKERS`/`CELERY_CONCURRENCY`
surchargeables par env — recalculer cette section après tout changement).

### Méthode de mesure live — « à mesurer — méthode prête »

Les chiffres suivants EXIGENT la boîte de production vivante et ne sont PAS
mesurables depuis ce dépôt seul :

- p50/p95 de latence sur les 4 endpoints chauds (login, liste devis, liste
  leads, `/proposal`) sous charge concurrente réelle ;
- nombre de rendus PDF concurrents avant saturation (dégradation `/core/
  health/` ou erreurs 5xx) ;
- marge mémoire réelle par conteneur (RSS observé vs limite) ;
- concurrency par défaut effective du worker Celery sur la boîte Hetzner
  (dépend du nombre de vCPU réel du plan).

**Procédure hors heures ouvrées (à exécuter par le fondateur ou un run
explicitement autorisé, jamais en heures de bureau marocaines ~9h-18h WEST/
WET) :**

1. Se connecter en SSH à la boîte (`ssh -i ~/.ssh/taqinor_hetzner root@178.105.192.116`
   ou l'hôte `api.taqinor.ma`).
2. Récupérer un jeton JWT access valide (compte de test dédié, PAS un compte
   client réel) et, si la sonde PDF concurrente est voulue, un token
   `/proposal/<token>/` existant (devis de test, PAS un devis client réel).
3. Lancer, DEPUIS UN POSTE AYANT ACCÈS RÉSEAU (pas nécessairement la boîte
   elle-même — un simple accès HTTPS suffit, le script est un client) :
   ```
   python scripts/capacity_probe.py --base-url https://api.taqinor.ma \
       --token "<jwt-access-test>" \
       --proposal-token "<token-devis-test>" \
       --duration 60 --concurrency 4 \
       --out /tmp/sca7-baseline-$(date +%Y%m%d).json
   ```
   Durée bornée (`--duration`, plafond dur 600 s/endpoint dans le script) ;
   le script interroge `/api/django/core/health/ready/` avant CHAQUE salve et
   s'arrête net dès que le statut n'est plus `ok` (pas de saturation
   prolongée volontaire).
4. Pour la marge mémoire par conteneur, sur la boîte : `docker stats
   --no-stream` pendant/juste après la sonde (aucun script dédié nécessaire —
   commande native Docker, zéro risque).
5. Pour la concurrency Celery réelle : sur la boîte, `nproc` (ou lire le plan
   Hetzner dans la console) donne le nombre de vCPU = concurrency par défaut
   d'un worker Celery sans `--concurrency` explicite (comportement prefork
   standard de Celery : `cpu_count()`).
6. Coller les résultats (JSON produit par le script + `docker stats` +
   `nproc`) dans une section datée ci-dessous, sous ce même titre
   « Baseline 2026-07 » (ou une nouvelle section datée si mesurée plus tard).

**État au 2026-07-09** : mesures live NON EFFECTUÉES (contrainte de cette
tâche — aucun accès SSH/production disponible depuis cet environnement). Deux
sondes read-only HTTPS ont pu être faites depuis ce poste (voir SCA12/SCA17
ci-dessous pour ce qu'elles ont révélé) — elles ne remplacent pas
`capacity_probe.py` sous charge, seulement des GET isolés sans concurrence.

## SCA8 — Limites de ressources conteneurs

Avant SCA8 : zéro `mem_limit`/`cpus` dans les deux compose (`docker-compose.yml`,
`docker-compose.prod.yml`) — vérifié par grep, aucune ligne trouvée. Un
rendu WeasyPrint fou ou une fuite mémoire pouvait affamer Postgres et Redis
sur la même boîte sans aucune garde-fou du côté Docker.

**Hypothèse RAM totale retenue (à recalibrer après SCA7 — mesure live)** :
une boîte Hetzner CX-line typique pour ce profil de charge (ERP multi-tenant
petite/moyenne échelle) est dimensionnée entre 8 et 16 Go de RAM. Cette
section retient **16 Go** comme hypothèse de travail conservatrice (permet de
poser des limites sûres sans sur-contraindre ; si la boîte réelle a moins de
RAM, ces limites resteront valides mais laisseront moins de marge libre — à
vérifier avec `free -h` sur la boîte lors de la prochaine session avec accès).
Voir `backend/db/postgresql.conf` (SCA11) qui dérive `shared_buffers` de la
même hypothèse — les deux sections doivent être recalibrées ENSEMBLE si
l'hypothèse RAM change.

Répartition posée (voir commentaires dans `docker-compose.prod.yml`) :

| Service | mem_limit | cpus | Justification |
|---|---|---|---|
| db | 4g | 2.0 | Protégé en priorité — Postgres ne doit jamais être OOM-killed par un voisin bruyant ; `shared_buffers` SCA11 vise ~25% de 16G = 4G, donc la limite conteneur doit AU MOINS couvrir shared_buffers + work_mem×connexions + overhead. |
| redis | 1g | 1.0 | Protégé en priorité — broker Celery : une éviction de tâches en attente est un incident. `maxmemory` Redis (SCA10) sera posé SOUS cette limite conteneur pour laisser de la marge overhead process. |
| django_core | 3g | 2.0 | 3 workers × 4 threads = 12 connexions/requêtes concurrentes ; WeasyPrint + matplotlib chargés au `--preload` (mémoire partagée entre workers forkés, mesurée ~3-4,5s/rendu, pas de fuite connue). |
| celery_worker | 2g | 1.5 | Rendu PDF interactif (WeasyPrint) — mêmes libs lourdes que django_core mais 1 seul process. |
| celery_worker_interactive (SCA9) | 1g | 1.0 | Queue interactive isolée — charge plus légère et bornée (rendu PDF synchrone déclenché par un clic, jamais un batch). |
| celery_beat | 256m | 0.25 | Scheduler seul, aucun traitement de tâche — empreinte minimale connue. |
| fastapi_ia | 2g | 1.5 | 2 workers uvicorn + modèles OCR/LangChain en mémoire (cache HuggingFace monté en volume séparé). |
| frontend | 256m | 0.25 | Sert des fichiers statiques (nginx interne à l'image), aucune charge dynamique. |
| nginx | 256m | 0.5 | Reverse proxy pur, empreinte minimale connue. |
| caddy | 256m | 0.5 | TLS + reverse proxy pur. |
| minio | 1g | 0.5 | Stockage objets, charge dominée par l'I/O disque, pas le CPU/RAM. |

Total mem_limit ≈ 3+2+1+1g+256m+2+256m+256m+256m+1g+4g ≈ **~15.3 Go** sur une
hypothèse de 16 Go — volontairement serré mais sous le total (marge overhead
OS/Docker ~0.7 Go, **à recalibrer** si la boîte réelle a une RAM différente ;
si `free -h` montre moins de marge que prévu, réduire d'abord `django_core`
et `fastapi_ia` qui ont la plus grande marge relative).

Réversible : suppression pure de clés compose, aucun changement de code
applicatif.

## SCA9 — Deuxième worker Celery dédié `interactive`

Avant SCA9 : `docker-compose.yml:81`, un seul conteneur `celery_worker`
consommait les 3 queues (`default,interactive,scheduled`) — le commentaire
YOPSB9 (alors `:74-80`) admettait explicitement zéro isolation : un backlog
`scheduled` (ex. `core.dump_database`, `ged.verifier_integrite_archives`,
plusieurs dizaines de tâches planifiées — voir `CELERY_TASK_ROUTES` dans
`settings/base.py:376-419`) pouvait retarder un rendu PDF `interactive`
déclenché par un commercial en attente.

Après SCA9 : deux conteneurs.
- `celery_worker` — `-Q default,scheduled` (retire `interactive`).
- `celery_worker_interactive` — `-Q interactive`, concurrency explicite via
  `CELERY_INTERACTIVE_CONCURRENCY` (défaut conservateur `2` — assez pour
  absorber plusieurs rendus PDF synchrones simultanés sans sur-allouer).

`CELERY_TASK_ROUTES` (`settings/base.py:376-419`) est **inchangé** — le
routage `ventes.generate_devis_pdf`/`ventes.generate_facture_pdf`/
`chat.transcribe_voice_attachment` → `interactive` existait déjà ; seule la
consommation compose change.

**Preuve statique de l'isolation** : avec deux conteneurs distincts écoutant
des queues DISJOINTES (`default,scheduled` vs `interactive` — aucun overlap),
un backlog Redis sur la queue `scheduled` (LLEN élevé) ne peut structurellement
PAS retarder la consommation de la queue `interactive` : ce sont deux
processus Celery indépendants, chacun avec son propre event loop de
consommation, chacun ne PEUT PAS voir les messages de l'autre queue (Celery
`-Q` restreint strictement les queues consommées — documenté par le
comportement Celery natif, pas une hypothèse de ce repo). Aucun test
d'intégration nécessaire pour établir ce fait : c'est une propriété du
mécanisme de routage par queue nommée lui-même, pas un comportement
applicatif à vérifier empiriquement.

`deploy-prod.ps1` : vérifié — ne référence AUCUN worker Celery par nom de
service (`grep -n "celery_worker" scripts/deploy-prod.ps1` → aucun résultat).
Le script agit uniquement sur `django_core`, `nginx`, `caddy` par nom, et sur
l'ensemble de la stack via `docker compose ... up -d --build --remove-orphans`
qui recrée TOUS les services définis, y compris le nouveau
`celery_worker_interactive` — aucun changement fonctionnel requis.

## SCA10 — Split Redis broker/cache + politiques d'éviction

Avant SCA10 : `settings/base.py:305-324`, `CACHES['default']` pointait vers
`redis://.../1` (db1) sur la MÊME instance Redis que le broker Celery
(`CELERY_BROKER_URL` → db0, `settings/base.py:323`) — une seule instance,
AUCUNE police de mémoire posée (défaut Redis = `noeviction`). Sous pression
mémoire, `noeviction` fait échouer les ÉCRITURES (y compris les enqueues
Celery) plutôt que d'évincer des clés cache — un cache qui grossit sans
limite pouvait donc, en théorie, bloquer l'enqueue de nouvelles tâches sur la
MÊME instance.

Après SCA10 : deux instances Redis distinctes.
- `redis` (broker, inchangé de nom pour rétro-compatibilité) — garde
  `noeviction` (explicite désormais, pas seulement le défaut implicite) +
  `maxmemory` dimensionné (256mb, sous la limite conteneur SCA8 de 1g — une
  file de tâches ne devrait jamais approcher cette taille en usage normal) +
  `appendonly yes` (persistance AOF — un restart ne perd plus les tâches en
  file d'attente, alors qu'avant SCA10 un restart Redis perdait TOUT).
- `redis_cache` (nouveau) — `maxmemory 256mb` + `--maxmemory-policy
  allkeys-lru` (éviction des clés les moins récemment utilisées sous
  pression — comportement correct pour un cache, jamais pour un broker) +
  AUCUNE persistance (`--save ""` — un cache est par nature jetable, pas
  besoin de survivre à un restart).

`CACHES['default']['LOCATION']` lit désormais `REDIS_CACHE_HOST`/
`REDIS_CACHE_PORT` (env, défauts = `REDIS_HOST`/`REDIS_PORT` actuels) —
**rétro-compatible** : sans ces nouvelles variables posées, `CACHES` pointe
EXACTEMENT vers `redis:6379/1` comme avant (comportement byte-identique).
`CELERY_BROKER_URL` reste sur `REDIS_HOST`/`REDIS_PORT` (db0) sans
changement.

## SCA11 — postgresql.conf tuné et monté

`backend/db/postgresql.conf` (nouveau), monté en lecture seule sur le
conteneur `db` dans les deux compose (`docker-compose.yml` pour le
comportement de base, hérité tel quel par `docker-compose.prod.yml` qui ne
surcharge pas ce montage).

Valeurs posées, dérivées de l'hypothèse RAM 16 Go (SCA8) et de l'arithmétique
connexions ci-dessus (SCA7) :

| Paramètre | Valeur | Justification |
|---|---|---|
| `shared_buffers` | `1GB` | ~25 % de la limite mémoire du conteneur `db` (4g posée en SCA8, pas les 16G machine totale — shared_buffers doit rester sous la RAM ALLOUÉE à Postgres, pas la RAM machine totale partagée avec 10 autres conteneurs). Recalibrer si SCA8 change la limite `db`. |
| `effective_cache_size` | `3GB` | ~75 % de la limite mémoire du conteneur `db` — indique au planner combien de cache OS/Postgres est raisonnablement disponible pour les I/O, sans réserver la mémoire (contrairement à shared_buffers). |
| `work_mem` | `8MB` | Raisonné vs concurrence : plafond connexions arithmétique SCA7 ~13-23 en usage normal ; `work_mem` est alloué PAR OPÉRATION DE TRI/HASH, potentiellement plusieurs fois par requête — `8MB × 23 connexions × ~2 opérations concurrentes` reste largement sous la limite conteneur de 4g. Le défaut pg16 (4MB) était trop bas pour du reporting multi-tenant (agrégations/tris sur de plus gros volumes) ; 8MB double la marge sans risquer l'OOM. |
| `max_connections` | `100` | Aligné sur le défaut pg16 ET sur l'arithmétique SCA7 (plafond théorique pire cas ~43 + Celery, largement sous 100) — AUCUN changement nécessaire tant que SCA7 live ne montre pas un besoin réel plus élevé. Si la concurrency Celery mesurée s'avère élevée (boîte à beaucoup de vCPU), recalculer ; le déclencheur pgbouncer (NTPLT58, voir SCA14) est justement `(workers×threads + celery) approche max_connections`. |
| `maintenance_work_mem` | `256MB` | Valeur standard pour VACUUM/CREATE INDEX sur une base de taille modeste — pas mesurée, valeur de bon sens PostgreSQL (~64-512MB typique), marquée à recalibrer si des VACUUM lents sont observés. |

Toutes les valeurs sont marquées `-- SCA11: recalibrer apres mesure live`
dans le fichier lui-même. **Recalibrage post-mesure requis** dès que SCA7 vit
(RAM réelle de la boîte, concurrency Celery réelle).

## SCA12 — nginx : gzip + timeout `/api/django/` aligné

Avant SCA12 : zéro directive `gzip` dans `backend/nginx/nginx.conf` (grep
vérifié) et la `location /api/django/` (`:148-155`) ne posait aucun
`proxy_read_timeout` explicite — nginx retombe sur son défaut (60s), en
dessous du `--timeout 120` de gunicorn (`docker-compose.prod.yml:41`) : une
requête Django légitimement longue (un `/proposal` lent, un export volumineux)
pouvait recevoir un 504 de nginx AVANT même que gunicorn n'ait eu le temps
d'échouer proprement.

**Risque de double-gzip — vérifié empiriquement (2026-07-09, requête HTTPS
GET read-only autorisée par cette tâche)** :
```
curl -sS -D - -H "Accept-Encoding: gzip, deflate, br" https://api.taqinor.ma/api/django/core/health/ready/
```
→ Réponse SANS aucun header `Content-Encoding` (malgré `Accept-Encoding: gzip`
envoyé), avec `Server: nginx/1.27.5` et `Via: 1.1 Caddy` — confirme la chaîne
Caddy → nginx → Django. Les corps de réponse atteignables sans authentification
depuis ce poste (18-49 octets) sont trop petits pour déclencher `encode gzip`
de Caddy de toute façon (`gzip_min_length`/seuil minlength standard), donc
cette sonde seule ne PROUVE pas l'absence de compression sur les payloads
réels (listes JSON de plusieurs Ko) — mais **`backend/caddy/Caddyfile` a
été lu directement** et confirme sans ambiguïté : `encode gzip` EST déjà
actif sur `{$PUBLIC_HOSTNAME}, api.taqinor.ma` (le bloc qui sert TOUT le
trafic public de l'OS).

**Décision — pas de risque de double-compression** : le module `encode` de
Caddy (`caddyhttp/encode`, comportement documenté du projet Caddy) vérifie le
header `Content-Encoding` de la réponse amont AVANT d'encoder — s'il est déjà
posé (ce que ferait un `gzip on` nginx), Caddy NE compresse PAS une seconde
fois ; il relaie tel quel. Activer `gzip` côté nginx est donc sans risque de
double-compression : soit nginx compresse et Caddy relaie (nginx gagne, motif
le plus probable vu qu'il est directement derrière Django), soit un cas
limite fait que ni l'un ni l'autre ne compresse un corps borderline — jamais
une double compression. Bénéfice : nginx compresse AU PLUS PRÈS de la source
(Django), réduisant la bande passante interne nginx→Caddy en plus de
Caddy→client.

**Config posée** (`backend/nginx/nginx.conf`, bloc `http {}`) :
```
gzip on;
gzip_types application/json application/javascript text/css image/svg+xml;
gzip_comp_level 5;   # niveau modéré — CPU/latence vs ratio de compression
gzip_min_length 512; # sous ce seuil, l'overhead de compression n'en vaut pas la peine
gzip_vary on;        # pose Vary: Accept-Encoding — cohérent avec le Vary déjà observé sur la boîte live
```
Et sur `location /api/django/` : `proxy_read_timeout 120s; proxy_send_timeout
120s; proxy_connect_timeout 10s;` (cohérent avec `proxy_read_timeout 120s`
déjà posé sur `/api/fastapi/` en `:119-145`, et avec `--timeout 120` gunicorn).

`/proposal` et les timeouts FastAPI existants (`:119-145`) : **intouchés** —
seule la location `/api/django/` a changé de timeout ; `/proposal` est servi
PAR `/api/django/` donc hérite du même nouveau timeout (120s, aligné sur
gunicorn — c'était déjà l'intention implicite, maintenant explicite). Les
rate-limits (`:18-21, 97-155`) sont restés strictement intacts (grep diff
vérifié — aucune ligne `limit_req` modifiée).

## SCA13 — Copie de sauvegarde hors-boîte (key-gated OFF)

`restore_drill` (`core/backup.py:313`) prouve la restaurabilité d'un dump
SUR LA MÊME instance Postgres (base scratch, même conteneur `db`) — un
sinistre boîte entière (disque Hetzner mort, corruption du volume Docker,
incident datacenter) n'était PAS couvert avant SCA13 : le dump lui-même vit
dans MinIO, qui est SUR LA MÊME BOÎTE.

Après SCA13 : `dump_database()` (YOPSB1), après un upload MinIO local
réussi, tente un upload ADDITIONNEL vers une cible S3-compatible EXTERNE si
`BACKUP_OFFSITE_ENDPOINT` + `BACKUP_OFFSITE_BUCKET` +
`BACKUP_OFFSITE_ACCESS_KEY` + `BACKUP_OFFSITE_SECRET_KEY` sont TOUTES posées
en environnement. **OFF par défaut** — sans ces 4 variables, le comportement
est byte-identique à avant SCA13 (aucun appel réseau supplémentaire, aucun
nouveau code exécuté au-delà d'une vérification de config qui retourne
immédiatement). Réutilise le client `boto3` déjà en dépendance
(`requirements.txt:44`, déjà utilisé par `_minio_client()`) — **aucune
nouvelle dépendance**.

Rétention distante simple : garde les N derniers dumps offsite
(`BACKUP_OFFSITE_RETAIN_LAST`, défaut `7`) — supprime les plus anciens à
chaque push réussi (pas de schéma GFS complexe côté offsite, le GFS complet
reste sur la copie locale via `purger_backups`).

**Échec de l'upload offsite N'ÉCHOUE PAS le `BackupRun`** — le backup local
(MinIO) reste la source de vérité du statut `termine`/`echec` ; l'offsite est
une couche de résilience additionnelle, best-effort, dont l'échec est
journalisé (`run.detail['offsite']`) sans changer `run.statut`. Ainsi une
cible offsite mal configurée ou temporairement injoignable ne bloque jamais
un backup local par ailleurs réussi.

**Activation** (à faire par le fondateur, choix du fournisseur de stockage
distant lui appartenant — voir note DONE LOG) :
```
BACKUP_OFFSITE_ENDPOINT=https://<endpoint-s3-compatible>
BACKUP_OFFSITE_BUCKET=<nom-bucket>
BACKUP_OFFSITE_ACCESS_KEY=<clé>
BACKUP_OFFSITE_SECRET_KEY=<secret>
BACKUP_OFFSITE_RETAIN_LAST=7  # optionnel, défaut 7
```
Posées dans `.env` sur le serveur puis `docker compose ... up -d --build`
(pas de rebuild d'image nécessaire, juste un redémarrage des conteneurs
`django_core`/`celery_worker` qui lisent l'env — mais un `up -d --build`
standard suffit, cohérent avec `deploy-prod.ps1`).

**Choix du fournisseur/coût du stockage distant : décision fondateur, non
tranchée par cette tâche** (Hetzner Storage Box, Backblaze B2, AWS S3, autre —
tous compatibles S3 ou proche-S3 fonctionnent avec ce client boto3
générique via `endpoint_url`). Voir note DONE LOG dédiée.

## SCA15 — Santé : mémoire Redis + profondeur des queues Celery

`core/health.py:37-55` (`_check_db_connections`) surveille déjà la
saturation connexions Postgres selon un motif éprouvé (seuil `degraded` à
80 %, best-effort, jamais bloquant). Avant SCA15, RIEN ne surveillait
`used_memory` Redis vs `maxmemory` (SCA10 vient d'introduire une police
d'éviction — sans observabilité, une saturation `redis_cache` passerait
inaperçue jusqu'à ce que les hit rates chutent silencieusement) ni la
profondeur des queues Celery (un backlog `scheduled` qui grossit sans borne
est justement le scénario que SCA9 isole de `interactive`, mais rien ne
l'ALERTE).

Après SCA15, deux sondes ajoutées à `check_services()` (même motif défensif
que les 7 sondes existantes — jamais d'exception, toujours un dict
`{name, status, detail}`) :

- `_check_redis_memory()` — lit `INFO memory` sur CHAQUE instance Redis
  configurée (broker + cache, SCA10), calcule `used_memory / maxmemory`,
  `degraded` si ≥80 % sur l'une des deux (seuil `REDIS_MEMORY_DEGRADED_RATIO`,
  env, défaut `0.8` — même seuil que `CONN_SATURATION_DEGRADED_RATIO`
  existant, cohérence de convention). `unknown` si `maxmemory` vaut `0`
  (pas de limite posée — ne peut pas calculer un ratio, jamais une fausse
  alerte).
- `_check_queue_depth()` — `LLEN` par queue nommée (`default`, `interactive`,
  `scheduled` — les 3 queues YOPSB9/SCA9), seuils configurables par env
  (`QUEUE_DEPTH_DEGRADED_{QUEUE}`, défaut `500` par queue — valeur de bon
  sens, PAS mesurée sur un volume réel de production ; à recalibrer une fois
  un volume de tâches réel observé).

Tests avec Redis mocké/simulé (motif `unittest.mock` déjà utilisé par
`test_health.py`/`test_dump_database.py` — jamais de Redis réel requis pour
ces tests).

## SCA16 — Dimensionnement gunicorn/celery par variables d'env

Avant SCA16 : `--workers 3 --threads 4` (prod) et `--workers 4` (dev) figés
en dur dans la commande compose — tout recalibrage post-SCA7 (mesure live)
exigeait d'éditer `docker-compose.prod.yml` et de redéployer.

Après SCA16, les commandes lisent :
```
GUNICORN_WORKERS   (défaut 3 en prod, 4 en dev — valeurs ACTUELLES, comportement inchangé sans .env)
GUNICORN_THREADS   (défaut 4 en prod ; en dev, --threads n'était pas posé — reste absent par défaut, pas de changement de comportement)
CELERY_CONCURRENCY (défaut vide = comportement Celery natif actuel, càd cpu_count() — PAS une valeur forcée, pour ne rien changer sans action explicite)
```

**Formule de dimensionnement** (à appliquer lors d'un recalibrage post-mesure
SCA7) :
```
GUNICORN_WORKERS  ≈ (2 × vCPU) + 1        (règle de bon sens gunicorn standard pour worker-class sync/thread)
GUNICORN_THREADS  ≈ 4                      (I/O-bound : DB + WeasyPrint ; ne pas dépasser ~4-8 sans mesurer la contention GIL)
CELERY_CONCURRENCY ≈ vCPU disponibles restants après Django/FastAPI, jamais < 1
```
Ces coefficients sont des règles de dimensionnement standard (gunicorn/Celery),
PAS des valeurs mesurées sur la boîte Hetzner — appliquer la formule seulement
APRÈS avoir mesuré `vCPU` réel (SCA7, `nproc` sur la boîte) et re-vérifié
l'arithmétique connexions ci-dessus (plus de workers/threads = plus de
connexions DB simultanées potentielles).

Défauts identiques au comportement actuel : sans `.env` posé, les 3
variables retombent sur les valeurs `3`/`4`/vide qui reproduisent EXACTEMENT
la commande compose d'avant SCA16.

## SCA17 — Vérifier puis documenter le module de settings prod (contradiction DEBUG)

**Constat de départ** : `erp_agentique/settings/prod.py:8` pose
`DEBUG = False` INCONDITIONNELLEMENT (pas de lecture d'env — c'est un
littéral Python, pas `os.environ.get(...)`). La mémoire fondateur
(`production_server.md`) affirme « DEBUG intentionally on » en prod — une
contradiction apparente à trancher SANS accès SSH à la boîte.

**Ce que le dépôt permet d'établir avec certitude :**

1. `docker-compose.prod.yml` (superposé à `docker-compose.yml` en prod, ligne
   `django_core.command`) **ne pose PAS `DJANGO_SETTINGS_MODULE`** dans le
   compose lui-même — cette variable vient de `env_file: ./.env`
   (`docker-compose.yml:28-29`, hérité par le compose prod qui ne le
   surcharge pas). `.env.example:22` documente
   `DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev` comme valeur
   d'EXEMPLE — donc **le fichier `.env` réel du serveur Hetzner (hors dépôt,
   jamais committé) décide seul** quel module de settings est chargé. Si le
   `.env` du serveur pointe vers `erp_agentique.settings.dev` (au lieu de
   `.prod`) — ce qui est plausible si le serveur n'a jamais eu son `.env`
   mis à jour depuis un déploiement initial rapide — alors `DEBUG` viendrait
   de `settings/dev.py`, PAS de `settings/prod.py`, et la note fondateur
   « DEBUG intentionally on » serait cohérente et exacte.
2. `deploy-prod.ps1` ne pose ni ne modifie `DJANGO_SETTINGS_MODULE` — le
   script fait `git reset --hard origin/main` + rebuild, JAMAIS de
   modification du `.env` serveur (qui n'est pas dans le dépôt, donc pas
   touché par `git reset`). Le `.env` serveur, une fois posé une première
   fois, PERSISTE tel quel à travers tous les déploiements suivants — c'est
   cohérent avec l'hypothèse d'un `.env` jamais mis à jour vers `.prod`
   depuis le déploiement initial.
3. **Indice fort trouvé dans `deploy-prod.ps1:74`** (healthcheck post-
   déploiement, YHARD11) : le script Python exécuté DANS le conteneur pour
   sonder `core.health` fait explicitement
   `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.prod')`
   AVANT `django.setup()`. `setdefault` ne pose la valeur QUE si la clé est
   ABSENTE de l'environnement — si `DJANGO_SETTINGS_MODULE` était déjà réglé
   sur `.prod` par le `.env` du serveur, ce `setdefault` serait un no-op
   inutile. Sa présence même, écrite comme un FILET DE SÉCURITÉ explicite
   pour CE SEUL sous-process de healthcheck, suggère que l'auteur du script
   savait ou soupçonnait que le `.env` du serveur ne pose PAS
   `DJANGO_SETTINGS_MODULE=erp_agentique.settings.prod` de façon fiable pour
   le process gunicorn principal — cohérent avec l'hypothèse ci-dessus. (Ce
   `setdefault` ne change RIEN au comportement du process gunicorn principal
   lui-même, qui lit sa propre variable d'environnement au démarrage,
   indépendamment de ce sous-process de sonde ponctuel.)
4. **Sonde HTTPS read-only effectuée (2026-07-09, dans le budget autorisé de
   cette tâche)** :
   ```
   curl -sS -D - https://api.taqinor.ma/api/django/core/health/ready/
   ```
   → Réponse `200 OK`, corps minimal (`{"status": "ready"}` probable, 18
   octets — pas inspecté en détail, hors scope de cette sonde), headers de
   sécurité présents (`X-Content-Type-Options`, `Content-Security-Policy`,
   `X-Frame-Options` — DEUX fois avec des valeurs DIFFÉRENTES, `DENY` ET
   `SAMEORIGIN`, ce qui révèle que nginx ET Django posent CHACUN leurs propres
   headers de sécurité indépendamment — nginx pose `SAMEORIGIN`
   (`nginx.conf:70`), Django/prod.py pose `X_FRAME_OPTIONS='DENY'`
   (`prod.py:15`) — un chevauchement pré-existant hors scope de cette tâche,
   signalé ici pour mémoire mais NON corrigé). **Cette réponse seule ne
   permet PAS de trancher DEBUG** : une page 200 sur un endpoint qui répond
   normalement ne révèle rien sur `DEBUG` (qui n'affecte que les pages
   d'ERREUR — la page jaune Django `DEBUG=True` n'apparaît que sur une
   exception 500 non gérée). Provoquer volontairement une 500 sur la prod
   pour vérifier serait une action à risque/mutation implicite — **exclu par
   la contrainte de cette tâche** (aucune requête qui provoquerait un effet
   ou un risque sur le système vivant).

5. **Chaîne de déduction décisive (fichiers du dépôt + la sonde 200 OK
   ci-dessus)** — elle permet de trancher BEAUCOUP plus fort que prévu :
   - `erp_agentique/wsgi.py` (ce que gunicorn charge) fait
     `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.prod')`
     — donc SANS la variable dans le `.env` serveur, gunicorn chargerait
     BIEN `settings.prod`. Mais `manage.py` et `celery.py` défaut-ent sur
     `settings.dev`, et `.env.example` pose
     `DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev` — un `.env` serveur
     copié de l'exemple SURCHARGE le setdefault de wsgi.py vers `.dev`.
   - `settings/prod.py:28-29` pose `SECURE_PROXY_SSL_HEADER =
     ('HTTP_X_FORWARDED_PROTO', 'https')` + `SECURE_SSL_REDIRECT = True`.
   - Or `backend/nginx/nginx.conf` (`location /api/django/`) fait
     `proxy_set_header X-Forwarded-Proto $scheme` — nginx écoute en HTTP
     PUR (port 80) derrière Caddy, donc `$scheme` vaut TOUJOURS `http` :
     nginx ÉCRASE le `X-Forwarded-Proto: https` que Caddy avait posé
     (`header_up X-Forwarded-Proto {scheme}`). Django ne voit donc JAMAIS
     `https` dans ce header sur le chemin public.
   - Conséquence si `settings.prod` était actif : `request.is_secure()` =
     False sur CHAQUE requête → `SECURE_SSL_REDIRECT` renverrait un 301
     vers https:// sur CHAQUE requête → la requête redirigée re-arrive avec
     `X-Forwarded-Proto: http` → **boucle de redirection infinie, l'API
     serait inutilisable**. Et le header `Strict-Transport-Security`
     (SECURE_HSTS_SECONDS, prod.py:16) ne serait posé que sur une requête
     jugée sécurisée — donc jamais sur ce chemin.
   - **Observé en vif** : `200 OK` direct, AUCUN 301, AUCUN header
     `Strict-Transport-Security` (deux réponses sondées). L'API est
     manifestement utilisable en production depuis des mois.

**Conclusion — l'évidence dit DEBUG probablement ACTIF en prod** : le
comportement vivant observé est INCOMPATIBLE avec `settings.prod` actif
(boucle 301 obligatoire vu l'écrasement X-Forwarded-Proto par nginx) et
COMPATIBLE avec `settings.dev` actif (aucun SSL redirect, aucun HSTS,
`DEBUG = True` — `dev.py:8`). Le module actif sur la boîte est donc, avec
une confiance élevée, `erp_agentique.settings.dev` via le `.env` serveur —
ce qui AVÈRE la note fondateur « DEBUG intentionally on » (mémoire
`production_server.md`). Ce n'est PAS un bug du code committé : `prod.py`
est correct par construction ; c'est l'état de configuration serveur.
Reste à confirmer sur la boîte (une commande) :
`cat /opt/taqinor-os/.env | grep DJANGO_SETTINGS_MODULE`.

**DECISION (fondateur — aucun changement unilatéral effectué)** :
1. Si « DEBUG on » reste voulu : rien à faire (état documenté ici).
2. Si le fondateur veut passer en `settings.prod` un jour : il faudra
   D'ABORD corriger l'écrasement `X-Forwarded-Proto` dans
   `backend/nginx/nginx.conf` (relayer le header entrant de Caddy au lieu
   de `$scheme`, ex. `proxy_set_header X-Forwarded-Proto
   $http_x_forwarded_proto;`) — sinon la bascule casse l'API en boucle de
   redirection le jour même. Cette correction n'a PAS été faite par cette
   tâche (elle ne change rien tant que `.dev` est actif, et la décision de
   bascule appartient au fondateur).

**Aucun changement de `settings/prod.py`, `docker-compose.prod.yml`, ni du
`.env` serveur n'a été fait par cette tâche** — uniquement de la
documentation.

## Piste de découpage physique (SCA14)

Constat : `docs/new_tasks_plan.md` possède les fixes applicatifs nommés
(NTPLT2 — RLS par introspection ; NTPLT58 — pgbouncer optionnel) mais aucune
tâche queuée ne documentait l'ORDRE de découpage physique quand la boîte
Hetzner unique ne suffit plus. Cette section comble ce trou, avec des
déclencheurs CHIFFRÉS (pas des impressions).

La baseline SCA7 ci-dessus (arithmétique connexions, config actuelle
chiffrée) est le point de départ de CHAQUE étape ci-dessous — recalculer
l'arithmétique avant de décider de franchir une étape.

### Étape 1 — pgbouncer même boîte

**Déclencheur** : `(workers × threads + celery concurrency)` (voir
arithmétique SCA7 ci-dessus) approche `max_connections` (100 par défaut pg16,
ou la valeur posée par SCA11). Avec la config actuelle (12 Django + ~1-4
Celery + jusqu'à 30 FastAPI en pic), on est loin du seuil — mais SCA16 rend
`GUNICORN_WORKERS`/`CELERY_CONCURRENCY` surchargeables, donc un recalibrage
agressif SANS repasser par cette arithmétique pourrait s'en approcher plus
vite qu'attendu.

**Implémentation** : `NTPLT58` (déjà nommée dans `docs/new_tasks_plan.md:810`)
— service compose `pgbouncer` en transaction pooling derrière un profil
Docker `--profile scale`, `PGBOUNCER=1` bascule l'hôte DB applicatif vers
pgbouncer + force `CONN_MAX_AGE=0` (une connexion persistante Django vers un
pooler transaction-mode serait contre-productive — le pooler EST la couche
de réutilisation).

**Contrainte de conception RLS × pooling** (à respecter dès l'introduction
de pgbouncer, que RLS — `NTPLT2` — soit déployé ou non) :
- Toute policy RLS Postgres qui s'appuie sur `current_setting('app.
  current_company', true)` DOIT être posée via `SET LOCAL` **scopé à la
  transaction** (jamais un `SET` de session) — en mode pooling transaction,
  une connexion physique est partagée entre PLUSIEURS transactions logiques
  successives ; un `SET` de session fuiterait le `company_id` d'un tenant
  vers la transaction du tenant suivant sur la MÊME connexion physique. Un
  bug de ce type serait une fuite multi-tenant critique (violerait le
  principe de scoping `company` de CLAUDE.md).
- `CONN_MAX_AGE=0` **obligatoire** côté Django dès que pgbouncer est en
  transaction-mode — une connexion Django "longue" par-dessus un pooler déjà
  multiplexé casse l'hypothèse du pooler (double-pooling incohérent).
- `DISABLE_SERVER_SIDE_CURSORS=True` **obligatoire** en transaction-mode
  pgbouncer — les curseurs serveur Postgres (utilisés par Django pour
  `.iterator()` et certaines requêtes larges) exigent que la MÊME connexion
  physique serve toutes les requêtes du curseur ; en transaction-mode, rien
  ne garantit ça entre deux `FETCH` (la connexion peut être recyclée vers un
  autre client entre deux transactions).
- **Migrations routées HORS du pooler** — `manage.py migrate` doit se
  connecter DIRECTEMENT à Postgres (pas via pgbouncer), car les migrations
  utilisent des verrous/transactions longues + parfois du DDL en dehors d'une
  transaction explicite (`CREATE INDEX CONCURRENTLY`) — incompatible avec le
  multiplexage transaction-mode. `deploy-prod.ps1` devra pointer
  `manage.py migrate` vers `DB_HOST`/`DB_PORT` directs (pas
  `PGBOUNCER_HOST`) le jour où pgbouncer est activé — noté ici pour la
  future implémentation NTPLT58, PAS fait par cette tâche.

### Étape 2 — Postgres sur sa propre boîte

**Déclencheur** : CPU/IO de la boîte DB (une fois séparée logiquement via
pgbouncer ou observée via `docker stats`) est haut ET le CPU applicatif
(Django/Celery/FastAPI) reste bas — signe que la base est le facteur limitant,
pas le calcul applicatif. Se mesure via le harnais NTPLT47-49/NTOBS12
(nommés dans `docs/new_tasks_plan.md`, pas réimplémentés ici).

### Étape 3 — boîte workers dédiée

**Déclencheur** : l'inverse de l'étape 2 — CPU applicatif haut (Django/
Celery/FastAPI saturés) ET CPU/IO DB bas. Signale que c'est le calcul
(rendu PDF, OCR, agent SQL) qui limite, pas la base — sortir les workers sur
leur propre boîte avant de toucher à Postgres.

### Étape 4 — réplique de lecture

**Déclencheur** : le QPS lecture domine largement le QPS écriture (mesurable
via `pg_stat_statements` ou le harnais NTOBS12) — une réplique de lecture
Postgres (streaming replication) absorbe les listes/rapports/exports sans
toucher à l'instance d'écriture primaire. Dernière étape de cette piste :
n'a de sens qu'après avoir confirmé (étapes 1-3) que le goulot n'est ni la
connexion, ni le CPU applicatif, ni le CPU/IO DB en écriture.

---

## Implémentation pgbouncer optionnel (NTPLT58)

Concrétise l'« Étape 1 » ci-dessus. pgbouncer reste **opt-in** derrière un
profil docker `scale` — la stack par défaut n'en dépend pas.

### Service compose (profil `scale`)

Ajouter à `docker-compose.yml` (le service ne démarre qu'avec
`docker compose --profile scale up`) :

```yaml
  pgbouncer:
    image: edoburu/pgbouncer:1.23.1
    profiles: ["scale"]
    environment:
      DB_HOST: db
      DB_PORT: "5432"
      DB_USER: ${POSTGRES_USER}
      DB_PASSWORD: ${POSTGRES_PASSWORD}
      POOL_MODE: transaction
      MAX_CLIENT_CONN: "1000"
      DEFAULT_POOL_SIZE: "25"
    depends_on:
      - db
    ports:
      - "6432:6432"
```

### Contrat d'activation (`.env` + settings)

`PGBOUNCER=1` bascule l'hôte DB applicatif vers pgbouncer et impose les
réglages **obligatoires** du mode transaction (déjà exigés par SCA14) :

```python
# erp_agentique/settings/base.py — bloc gardé par PGBOUNCER
if os.environ.get("PGBOUNCER") == "1":
    DATABASES["default"]["HOST"] = os.environ.get("PGBOUNCER_HOST", "pgbouncer")
    DATABASES["default"]["PORT"] = os.environ.get("PGBOUNCER_PORT", "6432")
    # Transaction pooling : pas de connexions persistantes ni de curseurs
    # serveur, sinon corruption inter-requêtes.
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
```

### Migrations HORS pooler

`manage.py migrate` (et `dump_database`, `restore_drill`) doivent pointer la DB
**directe**, jamais pgbouncer (le DDL et les curseurs serveur cassent en
transaction pooling). `deploy-prod.ps1` conserve `DB_HOST`/`DB_PORT` directs
pour l'étape migrations.

### RLS sous pooler

Le GUC tenant (`SET LOCAL app.current_company`, NTPLT2-4) est posé **par
requête dans la transaction** (`SET LOCAL`, jamais `SET` de session) — donc
compatible transaction pooling : chaque transaction repose son GUC, aucune
fuite entre clients multiplexés sur la même connexion serveur.

### Arithmétique des connexions (baseline Hetzner)

```
connexions serveur Postgres nécessaires
  = DEFAULT_POOL_SIZE (25) par (base × utilisateur)   via pgbouncer
côté clients (multiplexés) :
  4 workers gunicorn × N instances Django
  + workers Celery (default+interactive+scheduled+bulk)
  + FastAPI (agent SQL)
```

pgbouncer effondre des centaines de connexions client en ~25 connexions
serveur — c'est précisément ce qui repousse le mur `max_connections` de
Postgres sans surdimensionner la base.

---

*Référence CODEMAP : voir `docs/CODEMAP.md` §7 (ou section infra/capacité la
plus proche) pour un pointeur vers ce document — ligne exacte à ajouter
fournie dans le rapport final de la lane `infra/compose` (cette tâche
n'édite PAS CODEMAP.md, réservé à l'orchestrateur).*
