# Audit J5 « facturation » — dossier d'évaluation (L3, 08/10/2026)

Unité **J5** du registre (`docs/audits/unites.yml`), groupe **AFAC**, niveau **L3** (défaut du registre : P=4, I=5, score 20 ;
auto-pick go-deep confirmé : argent, documents fiscaux imprimés, paiement en ligne public, multi-société). Fichier du
propriétaire : `docs/plans/PLAN_AUDIT_FACTURATION.md` (propriété : `docs/ownership.yml` › `facturation`, qui prime).
Claim : branche `audit-J5`. Méthode : `docs/audits/METHODE.md` v2. Sorties brutes : scratchpad de la session (`j5/`).

## 0. Préconditions (phase 0)

- **SHA.** Lecture à `origin/main` `d096f2233` (07/10/2026, merge de la PR #857). Pile locale : checkout
  `C:\dev\taqinor-os` avancée en fast-forward de `3c7b29427` à `origin/main`, `manage.py migrate`,
  `docker compose up -d --build frontend`.
- **Apps parquées.** `python scripts/check_parked_apps.py` : OK — aucune référence vers les 47 apps parquées.
- **Groupe antérieur décisif : ATOT (X2, 07/10/2026, PR #844).** La chaîne d'argent devis → BC → facture(s) → paiements →
  avoirs a été auditée la veille : 22 constats, 16 tâches ATOT déjà dans `PLAN_AUDIT_FACTURATION.md` (ATOT2-ATOT17 :
  quatre portes de facturation, recopie devis → facture, échéancier, avoirs au taux mélangé, payé/reste/statut, facture
  émise modifiable, pro-forma, PDF sans Total HT, numéro à l'émission D-ATOT-5, REM/LIC sans unique, oracles). **J5 ne
  ré-audite pas ces classes** : chaque constat AFAC est vérifié « hors ATOT/ASEC/ASTK/ADOC » par le scout de
  dédoublonnage. Autres tâches ouvertes sur les fichiers J5 : ADOC74, ASTK135, ASTK197, ASEC (frère C-ATOT-008).

## 1. Charte (phase 1)

- **Système et frontière.** Après l'acceptation d'un devis : BC → facture (brouillon, émission, annulation) → encaissements
  (paiement manuel, paiement en ligne et webhook prestataire, import de relevé bancaire, remise d'encaissement et
  bordereau, mandat de prélèvement) → avoirs, notes de débit, retenues → relances, promesses, pénalités, contentieux →
  sorties (PDF facture legacy, reçu, relevé, lettre de relance, exports comptables, UBL/Factur-X/DGI, journal) → écrans
  facture/paiements/avoirs/relances/remises/mandats/BC. Chemins possédés = bloc `facturation` de `docs/ownership.yml`.
  Coutures lues seulement : `ventes.selectors` (totaux, exception import-linter), crm (client), portail (paiement),
  installations (BC), core/events.
- **Objet.** Objectifs fondateur 1 (tout se corrige après coup — par avoir pour une facture émise, D-ATOT-1),
  2 (une fonction par geste), 3 (code propre), 4 (le client voit le bon chiffre). Contrat J5 (METHODE §D.6) : chaque
  montant suit UNE chaîne, facture corrigée par avoir jamais en place, totaux au centime.
- **Personas réelles** (`CANONICAL_SYSTEM_ROLES`) : Administrateur, Responsable, Commercial. Aucun rôle « comptable » :
  la facturation se joue en `demo_admin` (dit ici). Client final : page publique de paiement à jeton, portail.
- **Niveau** L3 ; **jeu de données** `demo` (société 1) + second locataire (société « complet ») ; `anon` non chargé
  (machine partagée par d'autres sessions — écart déclaré) ; prod en lecture seule sous accord permanent.
- **Critères retenus** : C1, C2, C3, C4, C5, C6, C7, C8, C9 (paramètres de relance / pénalités), C10, C12, C13.
  C11 non applicable (aucune règle #1-#5 dans le périmètre hors #4 « facture PDF ≠ quote PDF ») ; C14 relève de X6.
- **Étapes (identifiants stables).**
  P1 facture : P1.1 création depuis BC · P1.2 brouillon édité (lignes, remise) · P1.3 émission · P1.4 annulation ·
  P1.5 consolidée / bulk · P1.6 statut et kanban.
  P2 encaissement : P2.1 paiement manuel · P2.2 paiement rejeté / effet · P2.3 import de relevé + rapprochement ·
  P2.4 remise d'encaissement + bordereau · P2.5 mandat de prélèvement · P2.6 acompte / dépôt.
  P3 paiement en ligne : P3.1 création du lien · P3.2 page publique à jeton · P3.3 webhook prestataire · P3.4 expiration.
  P4 corrections : P4.1 avoir total/partiel · P4.2 note de débit · P4.3 retenue à la source (RAS) · P4.4 retour client /
  abandon de créance.
  P5 recouvrement : P5.1 relance manuelle · P5.2 relances planifiées (Celery beat) · P5.3 promesse de paiement ·
  P5.4 pénalités de retard · P5.5 dossier contentieux · P5.6 paramétrage des relances.
  P6 sorties : P6.1 PDF facture / reçu / relevé · P6.2 exports comptables et journal · P6.3 UBL / Factur-X / DGI ·
  P6.4 numérotation (vue + audit) · P6.5 KPI / insights / alerte crédit.
  P7 coutures : P7.1 événements émis / abonnés · P7.2 multi-société sur viewsets, tâches et fichiers.
- **Non-objectifs.** Les classes ATOT déjà planifiées ; l'intérieur de `/proposal` (D2) ; le portail côté écran (J6) ;
  apps parquées (compta, frais…) sauf « code MVP qui référence une parquée ».

## 2. Spécification (phase 2)

**Scénarios (stimulus → réponse → mesure, priorité importance × risque).**
- H×H S-1 : un paiement en ligne réussi notifié DEUX fois par le prestataire ⇒ UN paiement, reste dû exact (idempotence).
- H×H S-2 : un webhook non signé / d'une autre société / montant ≠ lien ⇒ refusé, aucune écriture.
- H×H S-3 : un relevé bancaire importé deux fois ⇒ aucune ligne ni paiement en double ; un rapprochement lettré se défait.
- H×H S-4 : une relance planifiée ne part jamais pour une facture payée, annulée, en litige ou sous promesse ; une seule
  relance par niveau ; aucun envoi réel en local.
- H×M S-5 : un avoir / une note de débit / une retenue modifient « reste dû » et statut par UNE définition (D-ATOT-4).
- H×M S-6 : une remise d'encaissement ne peut contenir un paiement d'une autre société ni deux fois le même paiement ; son
  bordereau = Σ lignes.
- H×M S-7 : une facture brouillon se corrige (ligne, remise, client) puis se rouvre identique ; une facture émise refuse
  l'édition en argent (renvoi ATOT9) ; l'annulation libère proprement (paiements, BC, réservations).
- M×H S-8 : chaque viewset / tâche / export J5 borne `company` (lecture ET FK du corps).
- M×M S-9 : PDF facture, reçu, relevé, lettre de relance, export comptable et UBL portent les mêmes montants que l'objet.
- M×M S-10 : chaque événement émis par J5 a un abonné vivant ou figure dans `ALLOWED_UNCONSUMED` avec raison.

**Table saisie → consommateurs** (à compléter par les lanes) : paiement (montant, date, mode) → facture.montant_paye,
statut, relances, KPI, exports, reçu PDF, portail ; avoir → reste dû, statut, exports, DGI ; paramètre de relance →
tâches planifiées, lettre ; RIB / mandat → prélèvement.

**Seuils.** S1 argent faux / perte / fuite locataire / envoi client faux ; S2 saisie effacée, geste cassé sans
contournement ; S3 contournement ; S4 cosmétique (optionnel). Chiffre client, argent, multi-société : CONFIRMÉ
seulement sur preuve exécutée.

## 3. Plan des lanes (phase 3)

| Ronde | Lanes (modèle / effort) |
|---|---|
| Scouts | DET détecteurs (haiku/low) · DED dédoublonnage ATOT/ASEC/ASTK/ADOC + plans (haiku/low) |
| R2 jugement (8) | FBC facture & BC (opus/high) · FENC encaissements, relevé, remises, mandats (opus/high) · FPAY paiement en ligne & webhooks (opus/high) · FCOR avoirs, notes de débit, RAS, retours (opus/high) · FREC recouvrement & tâches planifiées (sonnet/medium) · FDOC sorties PDF / exports / DGI (sonnet/medium) · FUI écrans (sonnet/medium) · FEVT événements & multi-société (opus/high) |
| R3 porte empirique | vérificateurs FRAIS opus/high (jamais l'auteur), une sonde par constat dans une transaction ANNULÉE sur la base démo locale |
| Live | orchestrateur : Playwright `demo_admin`, pile locale |

## 4. Exécution (phase 4) — état intermédiaire

- **Détecteurs** (scout haiku, `d096f2233`) : `check_parked_apps`, `check_services_appeles` (576 fonctions, 0 nouvelle dette),
  `check_ecrans_atteignables` (585 écrans), `check_api_shapes --stats` (318 endpoints), `check_api_contract` (2 054 appels),
  `check_tests_source_regex`, `check_invariants` (19), `ci_guards stage-names` : **8/8 verts** alors que les constats ci-dessous se
  reproduisent. Non exécutés : `lint-imports` (non rapporté par le scout), `audit_coherence` (aucune règle facture/paiement).
- **Lanes R2** : 8 lanes → **72 constats bruts** (FBC 7, FENC 9, FPAY 8, FCOR 8, FREC 11, FDOC 12, FUI 13, FEVT 4).
- **Porte empirique R3** : 8 vérificateurs frais opus ; **72/72 REPRO ou STATIQUE, 0 réfuté** (sondes dans des transactions
  annulées, non-persistance prouvée par lane). Taux de réfutation nul ⇒ seconde lentille (3 réfuteurs) sur les 13 plus lourds.
- **Scout de dédoublonnage : sortie FAUSSE écartée** (il déclarait les tâches ATOT « cochées et mergées » ; `grep` : 16/16 ATOT
  ouvertes dans `PLAN_AUDIT_FACTURATION.md`) — le dédoublonnage est fait par l'orchestrateur et la seconde lentille.
