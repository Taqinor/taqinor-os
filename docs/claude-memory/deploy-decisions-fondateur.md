---
name: deploy-decisions-fondateur
description: Décisions deploy — D-ADEP-3 (09/10/2026, clés .env inertes) et D-ADEP-103 (25/10/2026, secret de relais Worker → API)
metadata:
  type: project
---

**D-ADEP-3 (09/10/2026, fondateur, ADEP92) — aucune clé présente, rien ne s'active.**
Relevé en prod, en lecture seule, des NOMS (jamais les valeurs) dans `/opt/taqinor-os/.env` :
`WHATSAPP_CLOUD_*`, `WHATSAPP_ENABLED`, `WHATSAPP_ACCESS_TOKEN`, `ESIGN_*`, `GED_OFFICE_URL`,
`GED_PADES_*`, `CMI_*`, `PAYMENT_PROVIDER`, `GEOIP_PATH`, `OPENSEARCH_URL`, `CF_CONNECTING_IP_TRUSTED`
→ **aucune n'est présente** (grep sans résultat). Déclarer ces clés dans les settings (ADEP32,
ADEP35-ADEP39) n'active donc RIEN au prochain déploiement. Le fondateur a validé : construire ces
tâches.

**Why:** C-ADEP-004 — ces variables étaient lues par le code sans être déclarées ; le risque était
qu'une clé déjà posée sur le serveur prenne effet en silence (paiement CMI, e-signature, WhatsApp,
confiance IP Cloudflare).

**How to apply:** chaque fonction ne s'allumera que si quelqu'un AJOUTE sa clé au `.env` du serveur —
ce qui est alors un geste explicite (changement visible client pour CMI et e-signature : le
reconfirmer avec le fondateur à ce moment-là). Les tâches ADEP32/35-39 recopient « D-ADEP-3 : aucune
clé présente » dans leur ligne DONE LOG.

**D-ADEP-103 (25/10/2026, fondateur) — l'IP transmise par Cloudflare n'est crue qu'avec le secret de relais (option c).**
api.taqinor.ma n'est PAS derrière le proxy Cloudflare (DNS direct vers l'origine). Les plages Cloudflare que
Caddy/nginx croient (ADEP102) sont communes à tous les comptes : un Worker tiers forgeait `X-Forwarded-For`.
Choix : notre Worker envoie `X-Taqinor-Relais` = `RELAIS_API_SECRET` (secret Worker dashboard-only + même
clé dans le `.env` serveur, passée à Caddy) ; sans le bon secret Caddy retire l'IP transmise. Écartés :
(a) proxifier l'API + Authenticated Origin Pulls (limites 100 Mo / 100 s, bascule DNS) ; (b) mTLS du Worker.

**Why:** C-L3-LIEN-09 (S2) — IP de preuve de signature et seaux de limite de débit forgeables.

**How to apply:** clé absente = comportement d'avant (D-ADEP-3). Activation par Reda, **Worker d'abord
puis serveur** (`up -d caddy`), procédure docs/production.md. Tout nouveau relais Worker → API passe par
`entetesIpVisiteur` (`apps/web/src/pages/api/_apiBase.ts`) — garde `scripts/tests/test_caddyfile_adep103_relais.py`.
