# Audit J0 « acquisition » — dossier d'évaluation (L2, 08/10/2026)

Unité **J0** du registre (`docs/audits/unites.yml`), groupe **AACQ**, niveau **L2** (défaut du registre : P=4, I=4, score 16 ;
auto-pick go-deep confirmé : saisie client propagée vers le CRM, écritures vers des systèmes externes — Meta, Odoo — et
surface publique non authentifiée ; pas d'argent client direct ⇒ L2, pas L3). Fichier du propriétaire :
`docs/plans/PLAN_AUDIT_ACQUISITION.md` (propriété : `docs/ownership.yml` › `acquisition`, qui prime). Claim : branche
`audit-J0`. Méthode : `docs/audits/METHODE.md` v2. Sorties brutes : scratchpad de la session (`j0/`).

## 0. Préconditions (phase 0)

- **SHA.** Lecture à `origin/main` `cc2fa8b68` (08/10/2026). Pile locale : checkout `C:\dev\taqinor-os` (conteneurs
  `erp-agentique-*`), migrée à `d096f2233` pendant l'audit J5 ; les commits intermédiaires sont docs/plans.
- **Apps parquées.** `check_parked_apps` vert au début de la session (J5).
- **Propriété.** `docs/ownership.yml` › `acquisition` : `apps/adsengine/**`, `apps/contact/**`, `crm/webhooks.py`,
  `crm/odoo_sync.py`, commandes Odoo de crm, `ventes/selectors_publicite.py`, `frontend/src/features/adsengine/**`,
  `WebsiteLeadPayloadsPage`, `tools/adlib_probe/**`, `tools/veille_tri/**`. Les chemins `apps/web/**` du registre (`lead.ts`,
  `pages/api/**`, `mon-toit.astro`) sont au propriétaire **web** (`check_ownership --owner-of`) : lus comme couture, tâches vers
  `docs/WEB_PLAN.md`. Chevauchement déclaré avec `docs/plans/PLAN_CRM_VENTES.md` (webhooks, odoo_sync).

## 1. Charte (phase 1)

- **Système et frontière.** Un prospect arrive par : formulaire / estimateur du site (`apps/web` → proxy → webhook ERP),
  Meta Lead Ads (webhook + rapatriement), questionnaire, prise de RDV, import / synchronisation Odoo ; il devient un `Lead`
  CRM avec sa provenance et son attribution. En sens inverse : le moteur publicitaire (`adsengine`) lit les métriques Meta,
  applique des règles, crée campagnes / audiences / créations, renvoie les conversions (CAPI) ; la veille concurrentielle
  lit la bibliothèque publicitaire.
- **Objet.** Objectifs fondateur 1 (ce que le prospect a saisi se corrige sans être ré-écrasé par une nouvelle
  soumission), 2 (une seule normalisation téléphone / ville / factures), 3 (code propre), 4 (le prospect et le fondateur
  voient le bon chiffre : lead, attribution, coût par lead). Règles maison : **#1 Odoo JSON-2 seulement**, **#3 campagne née
  `PAUSED`**, **#5 aucun scraping sans fichier `tos_risk/` + accord**.
- **Personas réelles** : Administrateur, Responsable, Commercial (CRM) ; « marketeur » n'existe pas — joué en
  `demo_admin`. Prospect : formulaire public sans compte.
- **Niveau** L2 ; **jeu** `demo` ; prod en lecture seule sous accord permanent ; aucun appel réel à Meta / Odoo / SendGrid.
- **Critères retenus** : C1, C2, C3, C4, C5, C6, C7, C8, C10, C11 (#1, #3, #5), C12, C13. C9 via les réglages adsengine.
- **Étapes.** P1 entrée : P1.1 webhook site · P1.2 webhook Meta Lead Ads · P1.3 questionnaire · P1.4 RDV · P1.5 rejeu /
  file des charges utiles · P1.6 dédoublonnage et normalisation. P2 Odoo : P2.1 import · P2.2 synchro · P2.3 push d'étapes.
  P3 moteur pub : P3.1 lecture métriques · P3.2 règles / anomalies / alertes · P3.3 création campagne / audience /
  création · P3.4 CAPI (renvoi de conversions) · P3.5 reporting / simulateur. P4 veille : P4.1 bibliothèque pub · P4.2 tri.
  P5 coutures : P5.1 événements · P5.2 multi-société des vues et tâches · P5.3 parité site ↔ webhook.
- **Non-objectifs.** Intérieur du `Lead` après création (J1a, D1) ; écrans `apps/web` hors couture (WEB_PLAN) ; apps parquées.

## 2. Spécification (phase 2)

- H×H S-1 : la même soumission de site rejouée (double clic, retry du proxy, DLQ) ⇒ UN lead, aucune saisie manuelle écrasée.
- H×H S-2 : un webhook sans signature / secret faux / d'une autre société ⇒ refusé, rien d'écrit.
- H×H S-3 : toute création de campagne / ad set / ad passe `PAUSED` (règle #3), quel que soit le chemin (règle auto,
  modèle, duplication, flightrunner).
- H×M S-4 : un lead corrigé à la main dans le CRM n'est pas ré-écrasé par la synchro Odoo / Meta / une nouvelle soumission.
- H×M S-5 : chaque vue, tâche Celery et action adsengine borne `company` ; un compte publicitaire d'une société n'est jamais
  lu ni écrit pour une autre.
- M×H S-6 : CAPI n'envoie que des données hachées / consenties, une fois par conversion ; un lead effacé (`lead_erased`)
  n'est plus renvoyé.
- M×M S-7 : coût par lead, ROAS, attribution : UNE définition entre reporting, tableau de bord et `selectors_publicite`.
- M×M S-8 : Odoo n'est écrit qu'en JSON-2 (règle #1) ; la veille ne scrape rien sans `tos_risk/` (règle #5).

Seuils : S1 fuite locataire / campagne active créée / argent pub dépensé à tort / lead perdu ; S2 saisie écrasée, geste
cassé ; S3 contournement ; S4 cosmétique. CONFIRMÉ seulement sur preuve exécutée (sonde en transaction annulée, live).

## 3. Plan des lanes (phase 3)

| Ronde | Lanes (modèle / effort) |
|---|---|
| Scout | DET détecteurs + dédoublonnage (haiku/low) |
| R2 (8) | LWH webhooks lead (opus/high) · LODOO synchro Odoo (sonnet/medium) · LMETA client Meta, CAPI, création (opus/high) · LRULES règles, anomalies, métriques, reporting (sonnet/medium) · LVIEWS vues / tâches / multi-société adsengine (opus/high) · LFRONT écrans adsengine + charges utiles (sonnet/medium) · LVEILLE veille + contact + outils (sonnet/medium) · LWEB couture `apps/web` ↔ webhook (sonnet/medium) |
| R3 | un vérificateur FRAIS opus/high par lane, sonde en transaction annulée sur la base démo locale |
| Live | orchestrateur : webhook site joué en local, lead CRM, écrans adsengine (Playwright `demo_admin`) |
