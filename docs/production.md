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
| Adresse publique | https://178-105-192-116.sslip.io |
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

## Migrer vers api.taqinor.ma plus tard

1. Pointer le DNS `api.taqinor.ma` (A) vers l'IP du serveur.
2. Sur le serveur, dans `/opt/taqinor-os/.env` : changer `PUBLIC_HOSTNAME`,
   `DJANGO_ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` vers le nouveau nom.
3. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` —
   Caddy obtient le nouveau certificat tout seul.
4. Mettre à jour `LEAD_WEBHOOK_URL` du Worker (`npx wrangler secret put`).

## Restaurer une sauvegarde

Console Hetzner → serveur `taqinor-os` → onglet **Backups** → choisir un
instantané → **Restore** (écrase le serveur avec l'état de ce jour-là).
Pour un besoin ponctuel, « Convert to snapshot » permet de monter la
sauvegarde sur un serveur séparé sans toucher à la prod.

## Récepteur de leads du site

Le Worker Cloudflare du site POSTe les leads qualifiés sur
`https://178-105-192-116.sslip.io/api/django/crm/webhooks/website-leads/`
avec l'en-tête `X-Webhook-Secret`. Le secret n'existe **que** dans l'.env
du serveur et dans la config du Worker (`wrangler secret`) — jamais dans le
dépôt ni dans une conversation.
