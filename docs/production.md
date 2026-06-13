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

## Mode DEBUG (décision du propriétaire, 2026-06-12)

Le serveur tourne **volontairement en mode DEBUG** (`settings.dev`,
`DJANGO_DEBUG=True` dans l'.env du serveur) tant que Reda teste — il
préfère voir les erreurs détaillées. Risque assumé : les pages d'erreur
exposent des détails techniques à tout visiteur, et l'hôte public est
découvrable (journaux de certificats). **Avant d'ouvrir aux clients**,
basculer dans `/opt/taqinor-os/.env` :

```
DJANGO_SETTINGS_MODULE=erp_agentique.settings.prod
DJANGO_DEBUG=False
```

puis `powershell -File scripts\deploy-prod.ps1` (ou redémarrer django_core).

## Mettre à jour la production

Une commande, depuis le PC :

```powershell
powershell -File scripts\deploy-prod.ps1
```

(pull de `main` sur le serveur → rebuild → migrations → redémarrage.)

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

## Récepteur de leads du site

Le Worker Cloudflare du site POSTe les leads qualifiés sur
`/api/django/crm/webhooks/website-leads/` avec l'en-tête `X-Webhook-Secret`
(URL configurée par le secret Worker `LEAD_WEBHOOK_URL` — encore l'hôte
sslip.io tant que la bascule dashboard vers api.taqinor.ma, décrite plus
haut, n'est pas faite ; les deux hôtes acceptent le webhook). Le secret
n'existe **que** dans l'.env du serveur et dans les secrets du Worker —
jamais dans le dépôt ni dans une conversation.
