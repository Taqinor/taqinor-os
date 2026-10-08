# Audit J2 « chantiers » — dossier d'évaluation (L2, 08/10/2026)

Unité **J2** du registre (`docs/audits/unites.yml`), groupe **ACHT**, niveau **L2** (défaut : P=3, I=4, score 12 ; auto-pick
go-deep : sous-domaine support, saisie propagée devis → chantier → stock → parc SAV, documents client — PV, bon de livraison,
compte-rendu ⇒ L2). Fichier du propriétaire : `docs/plans/PLAN_AUDIT_CHANTIERS.md` (`docs/ownership.yml` › `chantiers`, qui
prime). Claim : branche `audit-J2`. Méthode v2. Sorties brutes : scratchpad (`j2/`).

## 0. Préconditions (phase 0)

- **SHA.** Lecture à `origin/main` `d169957da` (08/10/2026). Pile locale `erp-agentique-*` (code monté depuis
  `C:\dev\taqinor-os`, migré à `d096f2233` ; commits intermédiaires = docs).
- **Groupes voisins à ne pas redire** : ASTK (stock ↔ chantier : réservations, sorties, double décompte — 16 tâches dans ce
  fichier), ADOC (GED / PV), ACAL (feu vert visite → calepinage), ASEC (multi-société), AFAC (BC / facture), APDF (PV, BL,
  compte-rendu imprimés : photos, intervenant, ICE, prestations listées comme composants).

## 1. Charte (phase 1)

- **Système et frontière.** Devis accepté → chantier (création par `devis_accepted`, nomenclature figée, étapes) → achats et
  réception fournisseur → kitting / livraison → interventions (planification, équipe, terrain hors-ligne, compte-rendu, photos,
  signature) → réception du chantier → bascule de la nomenclature en parc SAV (`sweep_bom_to_parc`) → rapport de production.
  Outillage (prêt / retour d'outils) et paramètres chantier (étapes, check-lists, équipe terrain, modèles de fiche).
- **Objet.** Objectifs 1 (une V2 de devis met à jour le chantier comme décidé ; une intervention se corrige après coup),
  2 (une seule nomenclature), 3, 4 (PV / compte-rendu justes). Contrat J2 (METHODE §D.6).
- **Personas réelles** : Administrateur, Responsable, Technicien responsable, Technicien ; client (PV, page publique de
  compte-rendu). **Niveau** L2 ; **jeu** `demo` ; prod en lecture seule.
- **Critères** : C1, C2, C3, C4, C5, C6, C7, C9, C10, C12, C13.
- **Étapes.** P1 création : P1.1 `devis_accepted` → chantier · P1.2 nomenclature figée · P1.3 V2 / révision du devis · P1.4
  annulation. P2 achats : P2.1 demande d'achat · P2.2 réception fournisseur. P3 kitting / livraison. P4 interventions : P4.1
  planification · P4.2 terrain hors-ligne / synchro · P4.3 compte-rendu, photos, signature · P4.4 correction après coup.
  P5 réception → parc SAV, commissioning, rapport de production. P6 outillage et paramètres. P7 coutures : événements,
  multi-société, tâches Celery.
- **Non-objectifs.** Intérieur du stock (J3), des PDF (X4 vient de passer), de la GED (J6) ; apps parquées.

## 2. Spécification (phase 2)

- H×H S-1 : un devis accepté crée UN chantier (rejeu de l'événement, double acceptation ⇒ pas de doublon).
- H×H S-2 : une révision V2 acceptée met à jour la nomenclature du chantier selon la règle décidée, sans écraser une saisie
  terrain ni perdre une réservation.
- H×M S-3 : une intervention terminée se corrige / se rouvre avec trace ; une synchro hors-ligne rejouée n'écrase pas une
  correction plus récente.
- H×M S-4 : la réception du chantier crée le parc SAV une fois, avec les vrais numéros de série et la garantie à partir de la
  réception.
- M×H S-5 : chaque viewset / action / tâche / page publique à jeton borne la société ; un technicien ne voit que ses chantiers
  si la portée le dit.
- M×M S-6 : statuts du chantier : machine d'états respectée (pas de saut, pas de retour silencieux) ; annulation propagée.

Seuils : S1 perte / fuite locataire / document client faux ; S2 saisie écrasée, geste cassé ; S3 contournement ; S4 cosmétique.

## 3. Plan des lanes (phase 3)

| Ronde | Lanes |
|---|---|
| Scout | détecteurs + dédoublonnage (haiku/low) |
| R2 (8) | CCRE création / révision / annulation (opus/high) · CACH achats / réception (sonnet/medium) · CKIT kitting / livraison (sonnet/medium) · CINT interventions et terrain (sonnet/medium) · CREC réception → parc, commissioning, rapport (sonnet/medium) · CTEN multi-société / permissions / tâches (opus/high) · CFRONT écrans (sonnet/medium) · COUT outillage + paramètres chantier (sonnet/medium) |
| R3 | un vérificateur FRAIS opus/high par lane, sondes en transaction annulée |
| Rédaction | 2 rédacteurs opus/high, fourchettes d'ID disjointes |
| Live | orchestrateur : écrans chantiers / interventions / outillage (Playwright `demo_admin`) |
