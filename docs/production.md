# Production — serveur Hetzner (source de vérité)

Depuis le 2026-06-12, **le Taqinor OS de production tourne 24/7 sur un
serveur Hetzner** ; le PC de Reda n'est plus que l'environnement de
développement (localhost). **Les données qui comptent (devis, leads,
catalogue, utilisateurs) vivent sur le serveur** — la base locale du PC
est une copie de dev qui peut diverger sans conséquence.

## L'essentiel

| Quoi | Valeur |
|---|---|
| Serveur | Hetzner cx23 (2 vCPU / 4 Go / 40 Go), Falkenstein |
| Adresse publique | **https://api.taqinor.ma** (canonique) — l'ancienne https://178-105-192-116.sslip.io répond toujours |
| Code déployé | branche `main` uniquement, clonée dans `/opt/taqinor-os` |
| Reverse proxy | Caddy (HTTPS Let's Encrypt automatique) — seul service exposé |
| Pare-feu cloud | entrées 22 / 80 / 443 uniquement (Postgres/Redis/MinIO internes) |
| SSH | clé dédiée `%USERPROFILE%\.ssh\taqinor_hetzner`, root, mot de passe désactivé |
| Secrets serveur | `/opt/taqinor-os/.env` (jamais dans le dépôt) |
| Sauvegardes | Hetzner Backups (7 instantanés glissants, quotidiens) |

## Mode DEBUG (décision du propriétaire, 2026-06-12) — à basculer (D-ASEC-6)

Le serveur tourne **volontairement en mode DEBUG** (`settings.dev`,
`DJANGO_DEBUG=True` dans l'.env du serveur) tant que Reda teste — il
préfère voir les erreurs détaillées. Risque assumé : les pages d'erreur
exposent des détails techniques à tout visiteur, et l'hôte public est
découvrable (journaux de certificats). Mesuré le 07/10/2026 (audit sécurité,
C-ASEC-029) : `settings.dev`, `DEBUG=True`, `NUM_PROXIES=1`. **Décision
D-ASEC-6 (07/10/2026)** : la production passe sur `settings.prod` maintenant
que les correctifs cookie `Secure` et proxy (ASEC52, ASEC15) sont livrés ; la
bascule est un **geste du fondateur**, décrit ci-dessous.

## Bascule vers settings.prod (ASEC48)

`erp_agentique/settings/prod.py` est prouvé pour la chaîne réelle
**Caddy → nginx → Django** par `scripts/tests/test_settings_prod_asec48.py`
(job CI `backend-openapi`) : un interpréteur neuf charge `settings.prod` avec
un environnement type prod (valeurs factices) ; `check --deploy` ne lève
aucune erreur et seulement les avertissements listés plus bas ; une requête
arrivée avec `X-Forwarded-Proto: https` est vue `is_secure()`, reçoit HSTS et
n'est jamais redirigée ; les sondes de santé ne sont jamais redirigées ; les
cookies session/CSRF/JWT sont `Secure` ; `CORS_ALLOW_ALL_ORIGINS=False` ;
l'adresse retenue pour la limitation est le visiteur, jamais l'appelant.

**Personne d'autre que Reda ne fait cette bascule** (aucun run Claude ne
touche le serveur ni son `.env`). Ne JAMAIS la faire pendant un déploiement
(l'auto-deploy du serveur tourne après chaque merge sur `main`) : attendre
qu'il soit fini.

### Variables du `.env` serveur (`/opt/taqinor-os/.env`)

| Variable | Valeur en production | Obligatoire ? | Si absente / fausse |
|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `erp_agentique.settings.prod` | oui | reste en `settings.dev` (DEBUG, aucun durcissement) |
| `DJANGO_DEBUG` | `False` | oui | le garde de démarrage de `SECRET_KEY` (`base.py`) n'est pas évalué |
| `DJANGO_SECRET_KEY` | la clé réelle déjà en place (jamais un `change_me…`) | oui | `RuntimeError` au démarrage / erreur `core.E_AUD410_SECRET_KEY` |
| `DJANGO_ALLOWED_HOSTS` | `api.taqinor.ma,178-105-192-116.sslip.io` (les deux hôtes de la Caddyfile ; le 2e = `PUBLIC_HOSTNAME`) | oui | **toute requête refusée (400)** et erreur `core.E_QJR423_ALLOWED_HOSTS` : en prod il n'y a plus de défaut `localhost` |
| `CSRF_TRUSTED_ORIGINS` | `https://api.taqinor.ma,https://178-105-192-116.sslip.io` (déjà posée) | recommandé | complétée automatiquement des origines CORS |
| `CORS_ALLOWED_ORIGINS` | `https://taqinor.ma,https://www.taqinor.ma` | non (c'est le défaut de `settings.prod`) | défaut : les deux domaines publics |
| `MINIO_ROOT_PASSWORD` | le mot de passe réel (jamais un `change_me…`) | oui | erreur `core.E_AUD410_MINIO` |
| `NUM_PROXIES` | absente, ou `1` | non | absente = 1 ; `0` ou illisible ⇒ **démarrage refusé** (tout Internet dans un seul seau de limitation) |
| `AUTH_COOKIE_SECURE` | **absente** | non | `0` retirerait `Secure` aux cookies JWT — ne jamais la poser en prod |
| `ODOO_COMPANY_ID` | id numérique de la société propriétaire du connecteur Odoo (ASEC40) | si Odoo est utilisé | le tableau Odoo s'éteint (fail-closed) |
| `TENANT_SIGNUP_ENABLED` | `0` (ou absente) | non | `1` rouvrirait l'inscription publique de sociétés (D-ASEC-2) |
| `DJANGO_ADMIN_URL` | recommandé : un chemin non devinable SOUS `api/django/`, terminé par `/` (ex. `api/django/<mot-choisi>/`) | non | défaut `api/django/admin/` (devinable). Hors `api/django/`, nginx ne relaierait pas l'admin |
| `PUBLIC_BASE_URL` | `https://api.taqinor.ma` | recommandé | liens client relatifs (comportement historique) |
| `LOG_LEVEL` | `INFO` | non | défaut `INFO` (journaux lisibles sans DEBUG) |

### Avertissements acceptés de `manage.py check --deploy`

Seuls ces avertissements sont attendus (toute ERREUR, ou tout autre
avertissement, bloque la bascule) — ce sont des fonctionnalités à clé,
volontairement en pause tant que la clé n'est pas posée :

| Identifiant | Sens |
|---|---|
| `crm.W010` | `META_LEAD_ADS_APP_SECRET` absent : webhook Meta Lead Ads fermé (403), synchro entrante en pause (DR3) |
| `notifications.W010` | `WHATSAPP_BSP_APP_SECRET` absent : webhook BSP WhatsApp fermé (403) (DR3) |

Le contrôle de déploiement de drf-spectacular (≈ 600 avertissements de
documentation du schéma OpenAPI) est coupé dans `settings.prod` : le schéma
est gardé en CI par `scripts/check_openapi_schema.py`.

### Procédure (Reda, sur le serveur)

1. **Sauvegarder l'état actuel, lecture seule** :

   ```bash
   cd /opt/taqinor-os
   cp .env .env.avant-settings-prod
   grep -E '^(DJANGO_SETTINGS_MODULE|DJANGO_DEBUG|DJANGO_ALLOWED_HOSTS|CSRF_TRUSTED_ORIGINS|CORS_ALLOWED_ORIGINS|NUM_PROXIES|AUTH_COOKIE_SECURE|ODOO_COMPANY_ID|TENANT_SIGNUP_ENABLED|DJANGO_ADMIN_URL|PUBLIC_HOSTNAME)=' .env
   ```

   Noter aussi un lien public de devis déjà envoyé (`/proposal`) et l'ouvrir :
   il servira de témoin « identique avant/après ».

2. **Poser les variables** du tableau ci-dessus dans `.env` (au minimum
   `DJANGO_SETTINGS_MODULE`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`).

3. **Essai à blanc, sans toucher aux conteneurs en service** (conteneur
   jetable, lit le nouveau `.env`) :

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps django_core python manage.py check --deploy
   ```

   Attendu : aucune ligne `ERROR`, seulement les avertissements acceptés
   ci-dessus. Une erreur nomme la variable à corriger ; corriger puis relancer.

4. **Basculer** (recrée Django + Celery avec le nouvel `.env`, puis nginx
   pour qu'il retrouve la nouvelle adresse de Django) :

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate django_core celery_worker celery_worker_interactive celery_beat
   docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
   ```

### Vérification après bascule (lecture seule)

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://api.taqinor.ma/                              # 200
curl -s -o /dev/null -w '%{http_code}\n' https://api.taqinor.ma/api/django/ventes/devis/       # 401 (jamais 301/302 : sinon boucle)
curl -sI https://api.taqinor.ma/api/django/core/health/live/ | grep -iE '^HTTP|strict-transport' # 200 + strict-transport-security
curl -s https://api.taqinor.ma/api/django/page-inexistante/ | grep -c URLconf                  # 0 (page 404 sans détail technique)
curl -sI https://api.taqinor.ma/<DJANGO_ADMIN_URL>login/ | grep -i set-cookie                 # csrftoken …; Secure
docker ps --format '{{.Names}}' | wc -l                                                         # 12
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --since 10m django_core | grep -ciE 'DisallowedHost|Traceback'   # 0
```

Puis dans le navigateur : se connecter à l'ERP — outils de développement →
Application → Cookies : les cookies de connexion portent `Secure`. Rouvrir le
lien `/proposal` témoin : même page, même PDF. Ouvrir une page publique (suivi
SAV, signature) : servie en HTTPS comme avant. Le formulaire du site
(taqinor.ma → webhook des leads) continue de créer des leads.

**Symptômes et cause probable** : `400 Bad Request` partout →
`DJANGO_ALLOWED_HOSTS` incomplet ; « trop de redirections » → l'en-tête
`X-Forwarded-Proto` n'arrive pas (Caddyfile `header_up X-Forwarded-Proto
{scheme}` et plages de confiance de `backend/nginx/nginx.conf`, ASEC52) ;
`403 CSRF` sur l'admin → `CSRF_TRUSTED_ORIGINS`.

### Retour arrière

Revenir à `settings.dev` en restaurant le `.env` sauvegardé, puis la même
recréation :

```bash
cd /opt/taqinor-os
cp .env.avant-settings-prod .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate django_core celery_worker celery_worker_interactive celery_beat
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
```

Aucune donnée n'est touchée par la bascule ni par le retour (seuls les
réglages changent). L'en-tête HSTS déjà reçu par les navigateurs reste un an :
sans effet, le site est servi en HTTPS par Caddy dans les deux cas.

## Mettre à jour la production

Une commande, depuis le PC :

```powershell
powershell -File scripts\deploy-prod.ps1
```

(pull de `main` sur le serveur → rebuild → migrations → redémarrage.)

## Heure légale — 20/09/2026

**Ce qui a changé.** Le Maroc est repassé **définitivement à l'heure GMT
(UTC+0)** dans la nuit du samedi 19 au dimanche 20 septembre 2026 (02:00 →
01:00) : décret n° 2.26.530 relatif à l'heure légale, adopté en Conseil de
gouvernement le 25/06/2026 et publié au **Bulletin officiel n° 7521 du
29/06/2026**. Il abroge le décret 2.18.855 de 2018 (UTC+1 permanent, avec
retour à UTC+0 pendant le Ramadan). **Il n'y a plus aucune bascule** — ni
saisonnière, ni pendant le Ramadan.

L'ERP ne code aucun décalage : il **nomme** son fuseau
(`TIME_ZONE = 'Africa/Casablanca'`, `CELERY_TIMEZONE` idem, et
`Intl.DateTimeFormat(..., timeZone: 'Africa/Casablanca')` côté écran). C'est
correct **si la base de fuseaux est à jour**, et faux d'une heure pleine sinon
— partout et en silence : relances envoyées trop tôt, regroupements par jour
décalés autour de minuit, courbes de production décalées d'un cran.

**Ce que fait l'image.** Deux verrous, déjà dans le dépôt :

1. `tzdata==2026.4` est **épinglé** dans `backend/django_core/requirements.txt`
   et `backend/fastapi_ia/requirements.txt` (IANA encode le décret depuis
   tzdata 2026c) ;
2. les Dockerfiles posent **`PYTHONTZPATH=""`** : Python ignore alors
   `/usr/share/zoneinfo` et ne lit **que** ce paquet-là. C'est indispensable —
   la tzdata de Debian peut être en retard sur IANA (bookworm servait encore
   **2026b** le 21/09/2026, donc *sans* le décret).

Un simple `deploy-prod.ps1` suffit : il reconstruit l'image, donc réinstalle le
paquet épinglé.

**Vérifier (30 secondes).** Un contrôle système bloque le démarrage si la base
de fuseaux de Python est périmée :

```bash
docker compose exec django_core python manage.py check --database default
```

Doit être **vert**. S'il sort `core.E_TZ_MAROC_PYTHON_PERIMEE`, l'image n'a pas
été reconstruite depuis le pin : `docker compose up -d --build`.

**Postgres a SA propre base de fuseaux.** Elle vient de son image
(`pgvector/pgvector:pg16`, Debian) et sert tous les regroupements par jour
(`Trunc*`/`Extract*` : le découpage est délégué à Postgres, pas à Python). Si
la commande ci-dessus affiche l'**avertissement** (non bloquant)
`core.W_TZ_MAROC_POSTGRES_PERIMEE`, mettez la base à jour :

```bash
docker compose pull db && docker compose up -d db
```

**Les navigateurs, eux, se mettent à jour seuls** : Chrome, Firefox, Edge et
Safari embarquent leur propre base de fuseaux, rafraîchie avec le navigateur.
Rien à faire côté poste client — sauf un navigateur volontairement figé depuis
des mois, qui afficherait alors les heures avec une heure de décalage.

## Édition du produit — `TAQINOR_EDITION` (groupe SOL, 02/09/2026)

TAQINOR OS se vend comme ERP **spécialisé solaire**. Une variable d'environnement
serveur décide de l'édition déployée :

| Valeur | Qui l'utilise | Effet |
|---|---|---|
| `full` (défaut) | dev, tests, gate CI | tout est chargé — zéro churn de schéma, toutes les baselines restent valides |
| `solar` | **la production** | les sept verticaux non adaptables (`agriculture`, `ecommerce_connect`, `education`, `hospitality`, `immobilier`, `mrp`, `sante`) sortent d'`INSTALLED_APPS`, des urls, du planning Celery et du bundle frontend |

**Aucune donnée n'est supprimée par la bascule** : tables, lignes et chaînes de
migrations restent intactes. Repasser à `full` réactive tout à l'identique.
Une valeur inconnue **fait échouer le démarrage** — jamais de repli silencieux.

Côté frontend, l'équivalent au BUILD est `VITE_EDITION=solar` (le bundle ne
contient alors plus aucun écran des verticaux parqués).

### Procédure de bascule

1. **Préflight, LECTURE SEULE**, depuis l'édition complète (la seule qui puisse
   compter les données des apps parquées) :

   ```bash
   docker compose exec django python manage.py preflight_edition --edition solar
   ```

   Il imprime, en français : lignes par société dans chaque table parquée,
   tâches beat qui disparaissent, jobs de fond en file, `ModuleToggle`,
   préférences de notification et permissions concernés. Il n'écrit rien et se
   relance autant de fois qu'on veut.

2. **Lire le rapport.** Des données métier VIVANTES dans une app parquée, ou une
   tâche encore en file, se remontent au fondateur AVANT la bascule.

3. **Basculer** : dans le `.env` du serveur, poser **les DEUX** variables —
   `TAQINOR_EDITION=solar` (backend, lu via `env_file` par django_core, celery
   et beat) **et** `VITE_EDITION=solar` (frontend, passé en argument de BUILD
   par `docker-compose.yml` → `frontend/Dockerfile.prod`). Un backend solaire
   servi par un frontend complet afficherait des écrans dont les routes
   n'existent plus. Puis `powershell -File scripts\deploy-prod.ps1` : le
   frontend est un flag BUILD-TIME, il faut un **rebuild** de son image
   (`docker compose up -d --build frontend`), jamais un simple redémarrage.

4. **Vérifier** : `docker compose exec django python manage.py verifier_edition`
   doit répondre « Édition « solar » cohérente », puis le contrôle de santé
   habituel (`curl` racine=200 / api=401, `docker ps` = 12 conteneurs).

**Qui l'exécute** : le run qui termine le groupe SOL, de bout en bout, après le
préflight — règle Deploys du 02/09/2026 (Claude fait toute la chaîne et ne
laisse aucune étape manuelle). Reda n'a rien à appliquer à la main.

## api.taqinor.ma (fait le 2026-06-13)

La Caddyfile sert les DEUX hôtes (`{$PUBLIC_HOSTNAME}, api.taqinor.ma`) —
un certificat Let's Encrypt chacun, l'ancienne adresse sslip.io reste
vivante. `DJANGO_ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` du `.env` serveur
listent les deux. Le script de déploiement recharge Caddy à chaque passage.

`LEAD_WEBHOOK_URL` du Worker est un **secret dashboard-only** (plus de token
CLI sur le PC) : pour le basculer, dash.cloudflare.com → Workers & Pages →
`taqinor-web` → Settings → Variables and Secrets → `LEAD_WEBHOOK_URL` →
valeur `https://api.taqinor.ma/api/django/crm/webhooks/website-leads/` →
Deploy. Une minute, à faire par Reda.

## Restaurer une sauvegarde

Console Hetzner → serveur `taqinor-os` → onglet **Backups** → choisir un
instantané → **Restore** (écrase le serveur avec l'état de ce jour-là).
Pour un besoin ponctuel, « Convert to snapshot » permet de monter la
sauvegarde sur un serveur séparé sans toucher à la prod.

## Récupération du compte propriétaire

Le système garantit qu'il existe **toujours** au moins un compte propriétaire
(administrateur) actif : le serveur ET l'interface refusent de supprimer ou de
rétrograder le dernier propriétaire, et le compte propriétaire `demo_admin` est
marqué **protégé** (ni supprimable ni rétrogradable, par personne — même
lui-même). On ne peut donc pas se verrouiller dehors depuis l'application.

Si malgré tout l'accès propriétaire est perdu (mot de passe oublié, compte
désactivé à la main en base, compte effacé), la récupération passe par
**l'accès SSH au serveur** (que vous seul possédez) — **il n'existe aucun mot
de passe par défaut, aucun compte caché, aucun secret dans le code**. La racine
de confiance, c'est « j'ai le SSH du serveur ».

Sur le serveur :

```bash
cd /opt/taqinor-os               # dossier du dépôt sur le serveur
docker compose exec django_core python manage.py recover_owner
```

- Sans argument : réinitialise `demo_admin`, le réactive, lui rend le rôle
  propriétaire, le marque protégé, et **génère un mot de passe fort affiché
  une seule fois** (à noter immédiatement).
- Choisir le compte / le mot de passe :
  `recover_owner --username reda --password 'MonNouveauMdp!2026'`
- Recréer le propriétaire s'il a disparu :
  `recover_owner --username reda --company taqinor-demo` (le `--company` n'est
  nécessaire que s'il y a plusieurs sociétés en base).

La commande est idempotente : on peut la relancer sans risque.

## Récepteur de leads du site

Le Worker Cloudflare du site POSTe les leads qualifiés sur
`/api/django/crm/webhooks/website-leads/` avec l'en-tête `X-Webhook-Secret`
(URL configurée par le secret Worker `LEAD_WEBHOOK_URL` — encore l'hôte
sslip.io tant que la bascule dashboard vers api.taqinor.ma, décrite plus
haut, n'est pas faite ; les deux hôtes acceptent le webhook). Le secret
n'existe **que** dans l'.env du serveur et dans les secrets du Worker —
jamais dans le dépôt ni dans une conversation.

## Email sortant (QW8 — rendre l'envoi réel)

Sans configuration, l'email reste un NO-OP réseau (backend console) —
comportement préservé par défaut. Pour un envoi RÉEL en prod (ex. l'email de
rappel QW4), il faut TOUS les trois réglages suivants dans l'`.env` du
serveur :

- `EMAIL_BACKEND=anymail.backends.sendinblue.EmailBackend` (Brevo, ex-
  Sendinblue — le backend anymail déjà installé, aucune nouvelle dépendance) ;
- `BREVO_API_KEY=<clé API Brevo>` (rangée sous `ANYMAIL['SENDINBLUE_API_KEY']`
  côté settings — **ne PAS** chercher une clé nommée littéralement
  `BREVO_API_KEY` dans `ANYMAIL`, c'est le bug QW8 corrigé) ;
- `DEFAULT_FROM_EMAIL=<expéditeur vérifié Brevo>`.

`apps.ventes.email_service.is_email_configured()` (réutilisé par
`apps.notifications.services._is_email_configured()`) vérifie
`ANYMAIL['SENDINBLUE_API_KEY']` OU `ANYMAIL['SENDGRID_API_KEY']` (héritage) —
sans l'une des deux, tout reste console/NO-OP, jamais une erreur.
