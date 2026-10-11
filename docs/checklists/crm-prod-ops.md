# Checklist — vérification du `.env` de production CRM (CRX42 + QXG5)

**Qui :** Reda, sur le serveur Hetzner (`/opt/taqinor-os/.env`), ~30 min. Claude n'exécute rien
sur le serveur (règle Deploys du 08/09/2026) : cette page est la liste, l'exécution est la tienne.
**Quand :** une fois, puis à chaque nouvelle variable introduite par un merge (le `.env.example`
du dépôt est la référence des noms).
**Règle :** vérifier qu'une variable est POSÉE sans jamais afficher sa valeur ni la coller dans un
chat. La commande `grep -c '^NOM=.\+' .env` répond `1` (posée, non vide) ou `0`.

Décision fondateur du 09/10/2026 (`docs/audits/decisions.yml`, D-CRX42 = (a)) : Claude écrit la
checklist, Reda la joue ; CRX42 est cochée à l'écriture, QXG5 à l'exécution.

## 1. Leads du site web → bonne société

| # | Variable | Doit être vrai | Sinon |
|---|---|---|---|
| 1.1 | `WEBSITE_LEADS_COMPANY_ID` | `grep -c '^WEBSITE_LEADS_COMPANY_ID=.\+' .env` → `1`, et l'id est celui de la société TAQINOR (`manage.py shell -c "from authentication.models import Company; print(list(Company.objects.values_list('id','name')))"`) | `_resolve_company()` (`apps/crm/webhooks.py`, `apps/crm/public_chat_views.py`) prend la PREMIÈRE société par pk ; un `logger.error` bruyant part dès qu'une seconde société existe |
| 1.2 | `WEBSITE_LEAD_WEBHOOK_SECRET` | posée (le récepteur refuse toute requête sans) | les formulaires du site taqinor.ma n'arrivent pas dans le CRM |

## 2. Meta Lead Ads (après CRX4)

| # | Variable | Doit être vrai | Sinon |
|---|---|---|---|
| 2.1 | `META_LEAD_ADS_APP_SECRET` | posée, identique au secret d'application du dashboard Meta (App → Paramètres → Général → Clé secrète) | la signature `X-Hub-Signature-256` du webhook est refusée : aucun lead Meta n'entre |
| 2.2 | Abonnement webhook Meta | l'URL du webhook est bien `https://api.taqinor.ma/api/django/crm/webhooks/meta-leads/` (vérifier le chemin exact dans `apps/crm/urls.py`) et l'app est **whitelistée** dans Leads Access Manager | une app non whitelistée = zéro webhook EN SILENCE (mémoire `marketing_playbook_v3`) |

## 3. E-mail sortant (QW8 / QX13 — relances, devis, notifications)

| # | Variable | Doit être vrai | Sinon |
|---|---|---|---|
| 3.1 | `EMAIL_BACKEND` | `anymail.backends.sendgrid.EmailBackend` **ou** `anymail.backends.sendinblue.EmailBackend` (Brevo) — jamais le backend console en prod | les e-mails sont « envoyés » dans les logs et personne ne les reçoit |
| 3.2 | `SENDGRID_API_KEY` **ou** `BREVO_API_KEY` | posée, cohérente avec 3.1 (une seule des deux) | erreur 401 du fournisseur à chaque envoi |
| 3.3 | `DEFAULT_FROM_EMAIL` | une adresse **vérifiée** chez le fournisseur (SendGrid : Sender Authentication ; Brevo : expéditeurs validés) | l'envoi est refusé ou atterrit en spam |
| 3.4 | Test réel | `docker compose exec django_core python manage.py sendtestemail <ton adresse>` puis réception vérifiée | — |

## 4. Rétention des données (CNDP / RGPD)

| # | Variable | Doit être vrai | Sinon |
|---|---|---|---|
| 4.1 | `RETENTION_AUTO_APPLY` | `0` (les politiques sont calculées et rapportées, jamais appliquées) — passer à `1` est une décision fondateur explicite : la suppression est définitive | des données client peuvent être purgées automatiquement |

## 5. IP réelle derrière le proxy (après CRX30)

| # | Point | Doit être vrai | Sinon |
|---|---|---|---|
| 5.1 | nginx / Caddy devant Django | `X-Forwarded-For` est transmis par le proxy et l'IP cliente lue par la primitive IP du CRM (`apps/crm/public_views.py`, garde `tests_qjr416_primitive_ip.py`) est celle du visiteur, pas celle du proxy | les verrous par IP (ASEC, verrou de connexion compte+IP) et le journal des formulaires publics voient une seule IP : tout le monde est verrouillé ensemble |
| 5.2 | Vérification | ouvrir un formulaire public depuis ton téléphone (4G) et lire l'IP journalisée (`docker compose logs django_core | grep -i "ip="` ou la fiche lead → chatter) : elle doit être ton IP 4G | — |

## 6. Carte (site public, Cloudflare Workers — QXG5)

| # | Point | Doit être vrai | Sinon |
|---|---|---|---|
| 6.1 | `PUBLIC_MAPTILER_KEY` | présente dans le dashboard Cloudflare → Workers → `taqinor-web` → Settings → Variables, sous ce nom exact (secrets = dashboard seulement, jamais `wrangler`) | la carte de la page ville est vide |

## 7. Le conteneur voit bien les variables

```bash
docker compose config | grep -E 'WEBSITE_LEADS_COMPANY_ID|META_LEAD_ADS_APP_SECRET|EMAIL_BACKEND|RETENTION_AUTO_APPLY' | sed -E 's/=.*/=<posée>/'
```

Chaque nom doit apparaître (la valeur est masquée par le `sed`). Un nom absent = variable
ajoutée au `.env` mais non reprise par `docker-compose.yml` (`environment:` / `env_file:`).

## Quand tout est vert

Coche `QXG5` dans `docs/PLAN2.md` avec la date, et note dans `docs/audits/decisions.yml`
(D-CRX42) la date d'exécution. Tout écart trouvé devient une ligne `ERR-…` dans
`docs/ERROR_PLAN.md`, jamais une correction à la main sur le serveur.
