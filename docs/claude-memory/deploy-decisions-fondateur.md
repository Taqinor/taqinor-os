---
name: deploy-decisions-fondateur
description: Décision D-ADEP-3 (09/10/2026) — clés .env inertes que les tâches ADEP32/35-39 rendent actives
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
