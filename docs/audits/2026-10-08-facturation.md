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

## 4. Exécution et manifeste de couverture (phase 4)

- **Détecteurs** (scout haiku, `d096f2233`, sortie brute `j5/detecteurs.md`) : `check_parked_apps`, `check_services_appeles`
  (576 fonctions, 0 nouvelle dette), `check_ecrans_atteignables` (585 écrans), `check_api_shapes --stats` (318 endpoints),
  `check_api_contract` (2 054 appels), `check_tests_source_regex`, `check_invariants` (19), `ci_guards stage-names` : **8/8 verts
  alors que 63 constats se reproduisent** — aucune garde ne voit ces classes (d'où les M3 AFAC44, AFAC62, AFAC93-AFAC97).
  Non exécutés : `lint-imports` (non rapporté), `audit_coherence` (aucune règle facture/paiement).
- **Lanes R2** (8, notes `j5/<LANE>.md` avec fichiers lus / non lus) : FBC 7, FENC 9, FPAY 8, FCOR 8, FREC 11, FDOC 12, FUI 13,
  FEVT 4 = **72 constats bruts**. Principaux non lus (manifestes + critique Fable §A) : `facturation_ops.py:1013-1249` (lu
  ensuite par le rédacteur W5, portes SAV/intervention sondées), `tools/facture/**` (lu par Fable), `apps/facturation/migrations|tests`,
  `domain/argent.py` et `echeancier.py` hors plages (couverts par ATOT), `frontend/e2e/{avoirs,receivables}*`.
- **Scout de dédoublonnage : sortie FAUSSE écartée** (il déclarait les ATOT « cochées et mergées » ; `grep` : 16/16 ouvertes) — le
  dédoublonnage est fait par l'orchestrateur, la seconde lentille (lentille « déjà-planifié ») et Fable.
- **Run live** (orchestrateur, Playwright, `demo_admin` société 2, pile `d096f2233`, `j5/live.md`) : LIVE-1 FAC-DEMO-0002 « Payée »
  sans paiement, écran « Dû 0,00 » / modèle `montant_du` 6 984 (frère C-ATOT-005, données seedées) ; LIVE-2 sur-paiement 40 000
  refusé (400) ; LIVE-3 montant à 3 décimales refusé, motif en toast seulement (C-AFAC-052) ; LIVE-4 paiement partiel 1 000,50 →
  onglet « Partiellement payées », Encaissements à jour ; **LIVE-5 « Payer en ligne » → `pay_url` RELATIF ouvrant l'API DRF
  navigable (JSON + notes internes), aucune page client** (C-AFAC-017) ; LIVE-6 page Relances « aucun envoi automatique » mais
  colonne « Automatique » ; LIVE-7 six écrans J5 : 0 `console.error`, 0 4xx/5xx. Rejeu Chrome DevTools : non fait (candidats
  reproduits par sondes rejouables). Persistance locale : 1 paiement + 1 lien sur FAC-DEMO-0001 (démo).
- **PROD lecture seule** (08/10, `manage.py shell`) : `PUBLIC_BASE_URL` absent ⇒ le QR de facture serait relatif aussi ; 0
  `PaymentLink` ; factures émise 2 / en retard 4 / brouillon 1 / annulée 4 ; 0 payée sans paiement ; 8 `RelanceLog`.

## 5. Registre des constats (phase 4 → 6)

72 constats bruts → **63 constats par cause racine** (fusions : FUI-9→003, FDOC-3→005, FPAY-4→011, FREC-10+FDOC-12→019,
FREC-9→032, FEVT-2→035, FEVT-1→036, FEVT-3→048). Format §C.1 complet au scratchpad (`j5/consolide.json`, `j5/V-*.md`,
`j5/L2-groupe*.md`). Gravité = verdict post-porte (seconde lentille prioritaire). Comptes : **S1 7 · S2 31 · S3 24 · S4 1**.
Les 13 constats les plus lourds ont passé une seconde lentille (3 réfuteurs frais) : 13 maintenus, C-AFAC-054 re-gradé S2,
C-AFAC-018 re-gradé S3 (latent : page injoignable aujourd'hui). Une tâche peut couvrir plusieurs constats (fusions Fable §B).

| ID | lanes | étape | crit. | grav. | verdict | titre | tâche(s) |
|---|---|---|---|---|---|---|---|
| C-AFAC-001 | FBC-1 | P1.1 / P1.6 | C7 | S2 | REPRO | Livrer le BC ressort tout le panier sans lire ce qui est déjà sorti (livraisons partielles, facture directe, d | AFAC15 |
| C-AFAC-002 | FBC-2 | P1.4 | C6 | S1 | REPRO | Annuler une facture encaissée depuis l'écran laisse l'acompte sur la facture morte ; il disparaît du solde du  | AFAC1, AFAC12, AFAC13, AFAC80 |
| C-AFAC-003 | FBC-3+FUI-9 | P1.3 / P1.6 | C6 | S2 | REPRO | Une facture BROUILLON s'encaisse et passe PAYÉE sans jamais être émise | AFAC2, AFAC9, AFAC10 |
| C-AFAC-004 | FBC-4 | P1.2 | C6 | S2 | REPRO | « Remettre en brouillon » ne contrôle que les paiements directs et les avoirs | AFAC11 |
| C-AFAC-005 | FBC-5+FDOC-3 | P1.3 | C1 | S2 | REPRO | La date d'émission imprimée est la date de création du brouillon (auto_now_add), jamais celle de l'émission | AFAC14 |
| C-AFAC-006 | FBC-6 | P1.1 / P1.4 | C6 | S2 | REPRO | Livraison partielle et annulation du BC hors machine à états (BC non confirmé/annulé livrable, annulation aprè | AFAC15 |
| C-AFAC-007 | FBC-7 | P1.3 / P1.5 | C3 | S3 | REPRO | « Émettre » (écran) refuse une facture à libellé sans lignes que le service et le lot acceptent | — (optionnel / couvert) |
| C-AFAC-008 | FENC-1 | P2.3 | C6 | S1 | REPRO | Import de relevé : la déduplication ne regarde que l'empreinte des octets du fichier, donc un relevé ré-export | AFAC5, AFAC96 |
| C-AFAC-009 | FENC-2 | P2.3 | C10 | S2 | STATIQUE | Import de relevé : l'écran ne montre ni la file de revue, ni les lignes déjà importées, ni le bilan par ligne, | AFAC3, AFAC6, AFAC7 |
| C-AFAC-010 | FENC-3 | P2.1 | C7 | S2 | REPRO | Encaissement groupé avec répartition explicite : le reliquat (montant − Σ parts) n'est ni enregistré ni signal | AFAC8 |
| C-AFAC-011 | FENC-4+FPAY-4 | P2.1 | C3 | S2 | REPRO | Pas de porte unique d'encaissement : la garde légale CAD122 (acompte signé à domicile, J+7) ne protège que le  | AFAC9, AFAC86 |
| C-AFAC-012 | FENC-5 | P2.4 | C5 | S2 | REPRO | Remise d'encaissement : statut modifiable par le corps (création et PATCH) et DELETE ouvert à tout rôle — la c | AFAC16 |
| C-AFAC-013 | FENC-6 | P2.3 | C2 | S3 | REPRO | Aucun geste pour corriger ou délettrer un paiement mal saisi ou mal rapproché ; le seul contournement est de l | AFAC4, AFAC17, AFAC18, AFAC81 |
| C-AFAC-014 | FENC-7 | P2.2 | C6 | S3 | REPRO | Une avance rejetée reste listée comme disponible et peut encore être ventilée | AFAC9 |
| C-AFAC-015 | FENC-8 | P2.5 | C4 | S3 | STATIQUE | Pile « mandat de prélèvement » inerte en MVP : aucun appelant pour le débit, la tokenisation ou les retentativ | AFAC19, AFAC82 |
| C-AFAC-016 | FENC-9 | P2.3 | C6 | S3 | REPRO | Import de relevé : une date non reconnue est remplacée sans prévenir par la date du jour | AFAC5, AFAC96 |
| C-AFAC-017 | FPAY-1 | P3.1 / P3.2 | C10 | S2 | REPRO | Le bouton « Payer en ligne » copie un chemin RELATIF vers une API JSON (aucune page client) et annonce le mont | AFAC20, AFAC21, AFAC22, AFAC26, AFAC83, AFAC94 |
| C-AFAC-018 | FPAY-2 | P3.2 / P3.4 | C1 | S3 | REPRO | Le lien de paiement survit à l'annulation et au solde de la facture : la page publique réclame le TTC d'une fa | AFAC23, AFAC83 |
| C-AFAC-019 | FPAY-3+FREC-10+FDOC-12 | P3.1 / P3.2 | C7 | S2 | REPRO | Le paiement en ligne réclame montant_du (retenue de garantie comprise) alors que le dû actuel est montant_exig | AFAC24, AFAC25, AFAC26 |
| C-AFAC-020 | FPAY-5 | P3.1 / P3.3 | C6 | S3 | REPRO | La clé provider du corps n'est pas validée et le fournisseur de TEST figure au registre de production : erreur | AFAC20, AFAC21, AFAC83 |
| C-AFAC-021 | FPAY-6 | P3.1 / P3.3 | C10 | S3 | REPRO | « Demander un paiement carte » (FG370) crée une transaction SANS facture cible : une capture ne créera jamais  | AFAC35, AFAC36, AFAC37, AFAC83 |
| C-AFAC-022 | FPAY-7 | P3.1 | C3 | S4 | REPRO | Trois piles de paiement en ligne pour un même geste, dont une morte, et un lien vers une route qui n'existe pa | AFAC83 |
| C-AFAC-023 | FPAY-8 | P3.3 | C7 | S3 | REPRO | Webhook (latent) : repli sur le montant FIGÉ du lien, et lien marqué « payé » après un paiement partiel, contr | AFAC23, AFAC83 |
| C-AFAC-024 | FCOR-1 | P4.4 | C7 | S1 | REPRO | retour-client crée son propre avoir sans la remise globale de la facture : le client est crédité du HT brut | AFAC27 |
| C-AFAC-025 | FCOR-2 | P4.4 | C7 | S2 | REPRO | Annuler un avoir de retour re-stocké laisse le stock ré-entré ; un second retour des mêmes unités re-stocke en | AFAC28 |
| C-AFAC-026 | FCOR-3 | P4.2 | C2 | S2 | REPRO | Note de débit : aucune annulation possible, et l'écran ne sait créer qu'une ND égale à toute la facture | AFAC20, AFAC32, AFAC33, AFAC84 |
| C-AFAC-027 | FCOR-4 | P4.2 | C7 | S2 | REPRO | Frère non couvert de C-ATOT-006 : la note de débit et l'avoir de retour ne recalculent pas le statut de la fac | AFAC29 |
| C-AFAC-028 | FCOR-5 | P4.3 | C7 | S2 | REPRO | RAS subie calculée comme un bouche-trou (reste − paiement) au lieu de TVA × taux : un impayé devient une « ret | AFAC30 |
| C-AFAC-029 | FCOR-6 | P4.3 | C13 | S3 | REPRO | Paiement avec retenue : l'action contourne toute validation, saisie non numérique ou incomplète = 500 | AFAC30 |
| C-AFAC-030 | FCOR-7 | P4.4 | C7 | S2 | REPRO | Abandon de créance stocké dans un champ unique écrasé et sans reprise : un second abandon efface le premier, u | AFAC34, AFAC85 |
| C-AFAC-031 | FCOR-8 | P4.2 | C1 | S2 | REPRO | Relevé de compte client (écran, PDF, portail) : Facturé − Payé − Avoirs ≠ Solde dû dès qu'il y a une note de d | AFAC31, AFAC97 |
| C-AFAC-032 | FDOC-1+FREC-9 | P6.1 | C1 | S1 | REPRO | Le relevé de compte (email mensuel, portail, PDF) compte les factures BROUILLON comme dues | AFAC40 |
| C-AFAC-033 | FREC-1 | P5.2 | C7 | S2 | REPRO | Relance planifiée consignée et niveau consommé même quand l'email n'est pas parti (pas d'adresse / SMTP en éch | AFAC45 |
| C-AFAC-034 | FREC-2 | P5.2 | C7 | S2 | REPRO | Facture rouverte après un rejet de paiement jamais ré-armée : EN_RETARD sans prochaine_relance, invisible aux  | AFAC46 |
| C-AFAC-035 | FREC-3+FEVT-2 | P5.6 | C5 | S1 | REPRO | PATCH d'un paramétrage de relance : client et responsable non bornés à la société ; mode manuel appliqué globa | AFAC47 |
| C-AFAC-036 | FREC-4+FEVT-1 | P5.2 | C5 | S2 | REPRO | Tâches de recouvrement balayant aussi les sociétés suspendues (les tâches sœurs utilisent active_companies) | AFAC43, AFAC44, AFAC93 |
| C-AFAC-037 | FREC-5 | P5.1 | C7 | S2 | REPRO | Deux définitions du niveau courant : le cron compte les notes automatiques, l'aperçu et la relance manuelle li | AFAC46 |
| C-AFAC-038 | FREC-6 | P5.2 | C7 | S3 | REPRO | Facture sans date_echeance : le cron la met EN_RETARD à +30 j mais jours_retard vaut 0 partout (message, liste | AFAC48 |
| C-AFAC-039 | FREC-7 | P5.3 | C7 | S3 | REPRO | Promesse de paiement partielle honorée marquée « rompue » : montant_promis n'est jamais comparé | AFAC49, AFAC87 |
| C-AFAC-040 | FREC-8 | P5.4 | C6 | S2 | REPRO | facturer-penalites non idempotent : chaque appel crée et émet une nouvelle facture de pénalités ; base montant | AFAC24, AFAC50 |
| C-AFAC-041 | FREC-11 | P5.6 | C9 | S3 | REPRO | Niveaux de relance semés à l'inscription sans message : les trois niveaux envoient le même texte générique | — (optionnel / couvert) |
| C-AFAC-042 | FDOC-2 | P6.1 | C1 | S1 | REPRO | Facture envoyée par email ou téléchargée en interne : PDF périmé, ou email 'ci-joint' sans PDF | AFAC41, AFAC42 |
| C-AFAC-043 | FDOC-4 | P6.1 | C1 | S2 | REPRO | Le PDF facture n'imprime ni les conditions/mode de paiement ni la retenue de garantie | AFAC56 |
| C-AFAC-044 | FDOC-5 | P6.2 | C6 | S2 | REPRO | Export comptable : la 'Date de fin' saisie est exclue (borne haute exclusive non dite) | AFAC51 |
| C-AFAC-045 | FDOC-6 | P6.2 | C7 | S2 | REPRO | Journal des ventes / export comptable : tranche à taux mixtes ventilée au taux mélangé (résumé TVA faux) | AFAC52 |
| C-AFAC-046 | FDOC-7 | P6.3 | C3 | S3 | REPRO | Deux fabricants UBL jumeaux : l'export DGI sans correction remise globale, et aucune ligne pour une tranche | — (optionnel / couvert) |
| C-AFAC-047 | FDOC-8 | P6.5 | C7 | S2 | REPRO | KPI Quote-to-Cash : Facturé/Encours/DSO sur Sum(montant_ttc) NULL hors tranche ; Encaissé compte les rejetés | AFAC53 |
| C-AFAC-048 | FDOC-9+FEVT-3 | P6.5 | C5 | S2 | REPRO | Sorties J5 bornées à la société mais pas à la portée de visibilité (rôles équipe) | AFAC54, AFAC55 |
| C-AFAC-049 | FDOC-10 | P6.1 | C1 | S3 | REPRO | Bloc 'Déjà payé / Reste à payer' du PDF facture qui ne retombe pas sur TTC - payé (notes de débit, abandons) | AFAC31, AFAC97 |
| C-AFAC-050 | FDOC-11 | P6.1 | C1 | S2 | REPRO | Facture en arabe : blocs ajoutés après XSAL13 restent en français | AFAC57, AFAC58 |
| C-AFAC-051 | FEVT-4 | P2.6 (couture  | C9 | S3 | REPRO | Le RIB de l'acompte (e-mail de confirmation de signature, charge utile post-signature) lit un réglage GLOBAL j | AFAC59 |
| C-AFAC-052 | FUI-1 | P2.1 paiement  | C6 | S3 | REPRO | Encaissement : montant vide / plus de 2 décimales renvoyé 400 par champ, l'écran affiche un toast générique sa | AFAC61 |
| C-AFAC-053 | FUI-2 | P5.1 relance m | C13 | S3 | REPRO | Relances : 'Consigner', lot, exclusion et historique avalent toute erreur serveur (catch vide) — la modale res | AFAC61, AFAC62, AFAC95 |
| C-AFAC-054 | FUI-3 | P2.4 remise d' | C6 | S2 | REPRO | Remise d'encaissement : l'écran propose des paiements que le serveur refuse puis cache la raison | AFAC60, AFAC61 |
| C-AFAC-055 | FUI-4 | P2.1 paiement  | C1 | S2 | REPRO | Cinq écrans lisent la page 1 (50 lignes) d'une liste paginée : 'Total encaissé', compteur d'avoirs, bons de co | AFAC63, AFAC64, AFAC95 |
| C-AFAC-056 | FUI-5 | P2.1 paiement  | C1 | S3 | REPRO | PaiementDialog affiche un instantané de la facture : 'Payé — / Dû' vide et 'Aucun paiement enregistré' faux de | AFAC65 |
| C-AFAC-057 | FUI-6 | P1.1 création  | C3 | S1 | REPRO | Nouvelle facture avec BC choisi : cinquième porte de facturation côté écran — remise globale, taux, option eff | AFAC66, AFAC67 |
| C-AFAC-058 | FUI-7 | P1.2 brouillon | C7 | S3 | REPRO | Totaux du formulaire facture calculés en JS sans l'arrondi du noyau serveur : HT + TVA affichés != TTC, palier | AFAC68 |
| C-AFAC-059 | FUI-8 | P1.2 brouillon | C6 | S3 | REPRO | Facture : remise > 100, quantité/prix négatifs sont laissés aux CHECK Postgres (500) et les lignes en échec ne | AFAC69, AFAC70 |
| C-AFAC-060 | FUI-10 | P1.4 annulatio | C3 | S3 | REPRO | 'Marquer payée' et 'Annuler la facture' affichés à tous les rôles alors que le serveur les réserve à IsAdminRo | — (optionnel / couvert) |
| C-AFAC-061 | FUI-11 | P1.6 statut et | C2 | S2 | REPRO | Écran d'édition de facture ouvert sur n'importe quel statut (Kanban, ?id=) avec sélecteurs Statut et Télédécla | AFAC71 |
| C-AFAC-062 | FUI-12 | P1.6 statut et | C7 | S3 | STATIQUE | Kanban : la colonne 'Partiellement payée' ne reçoit jamais de facture et le prédicat 'en retard' diverge de ce | AFAC72 |
| C-AFAC-063 | FUI-13 | P6.5 KPI / ins | C1 | S3 | REPRO | Carte 'À échoir ≤ 7 j' : le montant vient du serveur (fenêtre 7 jours) mais le nombre de factures est compté s | — (optionnel / couvert) |

## 6. Constats OPTIONNELS (hors tâches — S4, style, hypothétique, inerte)

- C-AFAC-007 (règle d'émission dupliquée, sans effet client), C-AFAC-041 (texte générique des niveaux de relance), C-AFAC-046
  (deux fabricants UBL — repasse P1 au jour où la télédéclaration DGI est activée), C-AFAC-060 (boutons visibles, serveur
  refuse), C-AFAC-063 (compteur ≠ fenêtre) : sans tâche (Fable §D).
- C-AFAC-055 : agrégat serveur du « Total encaissé » (comme factures/kpis) au lieu d'une somme front sur toutes les pages — amélioration, non construite.
- C-AFAC-058 : endpoint d'aperçu des totaux facture (même chaîne que totaux.py) pour un total exact pendant l'édition — remplacé par le libellé « Estimation » (AFAC68).
- RemisesEncaissementPage.jsx:98,337 : écart prévisionnel en flottant (100,10+200,20-300,30 = -5.7e-14) affiché « 0,00 MAD » en rouge (S4, node).
- LIVE-3 / PaiementDialog : l'alerte d'erreur globale reste affichée après l'enregistrement suivant réussi (S4).
- FactureList.jsx handleBulkAction : « N échec(s) » sans le motif par facture (S4).
- FactureList.jsx:978-984 « Exporter Excel » exporte toutes les factures chargées, pas le filtre ni la sélection, avec `.catch(() => {})` silencieux (S4).
- NoteDebitDialog / PaiementEnLigneDialog lisent `facture.montant_du` d'un instantané (ouverts seulement depuis FactureList, forme complète) — à relire si un autre appelant apparaît.
- C-AFAC-063 (compteur « 7 prochains jours » ≠ fenêtre serveur) et C-AFAC-060 (boutons visibles, serveur refuse) : OPTIONNELS selon FABLE §D, hors lot W4.
- test_aud135_remise_encaissement.py:59-61 : commentaire faux (« l'écran l'envoie explicitement ») — fichier propriétaire devis, à corriger au passage par son propriétaire.
- Second appel séquentiel de POST sav/tickets/<id>/facturer/ renvoie 201 (même facture) au lieu de 200 — cosmétique, vue SAV (autre propriétaire) ; sondé W5-1.
- Portes 6/7 : prix HT/TTC = NON-RISQUE (Produit.prix_vente est HT, solar.js ttcFromHt ; W5-2 : 1 000 HT → TTC 1 200) ; appel séquentiel idempotent = NON-RISQUE (W5-1).
- Intervention couverte par un CONTRAT de maintenance facturée par generer_facture_intervention : PLAUSIBLE non confirmé (docstring ZFSM4 « hors contrat ») — non sondé.
- FABLE A.3 : .env.example:112 pose EMAIL_BACKEND=anymail SendGrid ; danger pour sondes/qa-explorer si une vraie clé est présente — hazard infra à banker (local_ci_via_docker), pas une tâche W5.
- FABLE A.1.4 : docs/ownership.yml:158 déclare core/events/facturation.py qui n'existe pas — correction registre 1 ligne (hors lot W5).
- C-AFAC-036 (frère) : `engagement_followup_engine` (scheduled.py:614) balaie les liens de partage de toutes les sociétés, y compris suspendues (hors argent) — à sonder avant d'en faire une tâche.
- C-AFAC-033 : prévenir le responsable après N échecs d'envoi d'affilée d'une relance (aujourd'hui l'échec n'est visible que dans l'onglet e-mails de la facture).
- C-AFAC-042 (frère) : le téléchargement et l'e-mail des PDF d'avoir et de note de débit n'ont pas de garde de fraîcheur (ces PDF n'impriment pas de reste à payer ; aucun chiffre faux prouvé).
- C-AFAC-047 : fenêtre propre du DSO (aujourd'hui la période du tableau) ; une troisième définition, `compta.dso` (apps/semantic), n'a pas été lue.
- C-AFAC-050 (frère) : `recu.html` et `releve.html` restent en français pour un client arabophone — à documenter comme exception ou à traduire.
- C-AFAC-051 (frère) : `email_service._reply_to_address` (INBOUND_REPLY_EMAIL, jamais défini) et `_from_email` (DEFAULT_FROM_EMAIL global) : même motif « réglage global dans un système multi-société », sans effet prouvé.
- C-AFAC-048 (frère) : `extra_docs_views.fiche_remise_premium` utilise le même `_scope` (société seule) — non sondé.
- C-AFAC-023 frère (FPAY-8) : le récepteur FG370 `receivers.py:122-136` borne la capture au reste dû mais ne trace pas l'excédent capturé (S4, inerte sans PSP).
- C-AFAC-031 frère (L2-C-AFAC-031) : avoir sur une facture déjà payée — le crédit client (trop-perçu) est invisible au relevé (`du` forcé à 0) ; à traiter seulement si le fondateur veut un solde créditeur affiché.
- C-AFAC-027 frère (V-FCOR) : retour qui solde une facture partiellement payée — le sur-paiement du client (600) est invisible car `montant_du` est borné à 0 ; même sujet « crédit client ».
- FABLE §D / P3.4 : `expirer_liens_paiement_perimes` n'est appelé par aucun beat (seulement à la ré-émission, `encaissements.py:553`) — un lien périmé reste `en_attente` en base jusqu'au prochain geste (cosmétique, `is_valid` refuse).
- `serializers_facturation.py:293-297` force `montant_du='0.00'` pour une facture payée : sans effet une fois le statut dérivé (ATOT8/AFAC29) ; frère de C-ATOT-005 / LIVE-1 (FAC-DEMO-0002 payée sans paiement), à laisser à ATOT.
- `COMPANY_RIB` est lu par `getattr(settings, …)` (`public/paiement_views.py:26-33`) mais n'est déclaré nulle part dans les settings (même défaut que PUBLIC_BASE_URL) : la page `/payer` n'affichera pas de RIB tant qu'il n'est pas déclaré et p
- Signature réelle de `HostedGatewayProvider.verify_webhook` laissée en `# ... vérifier` (`providers.py:177`) : latent, fail-closed aujourd'hui (noop), à couvrir par QXG2.
- C-AFAC-010 : le toast de l'encaissement groupé compte l'avance du reliquat comme une facture (FactureList.jsx:876) ; l'avance est déjà rendue dans la réponse.
- C-AFAC-001/006 : masquer « Livrer » à côté de « Livrer partiellement », et « Annuler » sur un BC partiellement livré (BonCommandeList.jsx:355-391). Le serveur refuse déjà après AFAC15.
- C-AFAC-004 : vrai contrôle de période comptable YLEDG3 sur remettre-brouillon ; le texte de confirmation de FactureList.jsx:193-195 promet ce contrôle, qui n'existe pas.
- C-AFAC-005 : NoteDebit.date_emission (models_facturation.py:450) reste auto_now_add. Sans écart aujourd'hui : la note de débit naît ÉMISE (views/facture.py:1398).
- C-AFAC-011 branche (c) : escompte XFAC12, arrondi espèces et tolérance absents de l'import de relevé. Constat STATIQUE, relève d'un choix produit (L2-groupe1).
- C-AFAC-015 : retirer les clés i18n inertes nav.mandats_paiement (catalogues fr/en/ar, fichiers deploy).
- C-AFAC-012 : MandatPaiementViewSet DELETE en cascade des TentativeDebitMandat. Sans objet si AFAC19 parque la pile ; sinon, tâche de durcissement à créer.

## 7. Vérification adversariale (phase 5)

- **Porte empirique** : 8 vérificateurs frais opus/high (jamais l'auteur), une sonde par constat dans une transaction ANNULÉE
  sur la base démo locale (`j5/sondes/`, 120+ scripts) ; non-persistance prouvée par chaque vérificateur (comptes à 0 en fin de
  passe). **72/72 REPRO ou STATIQUE, 0 réfuté** — taux de réfutation nul ⇒ calibration douteuse (METHODE §E.2), d'où :
- **Seconde lentille** (3 réfuteurs frais opus/high, lentilles déjà-planifié / spec / reproduction INDÉPENDANTE, sondes
  différentes) sur C-AFAC-002, 008, 011, 017, 018, 024, 028, 031, 032, 035, 042, 054, 057 : 11 MAINTENUS, 2 GRAVITÉ REVUE ;
  élargissements prouvés : 024 (le palier `arrondi_pas` rend aussi un retour total impossible), 042 (un reste à payer FAUX
  imprimé, pas seulement un bloc absent), 057 (option facturée et remise perdue : 57 600 au lieu de 45 600).
- **Critique de complétude Fable** (1 appel, `j5/FABLE.md`) : 2 trous comblés (portes de facture 6 et 7 SAV / intervention →
  sondées par W5 : 3 défauts REPRO, AFAC90-92 ; deux non-risques prouvés : prix HT, appel séquentiel idempotent) ; `tools/facture`
  hors ERP avec un JSON client versionné (AFAC88, décision) ; aucune notion de facture « contestée » (AFAC89) ; 10 fusions ;
  6 constats prolongent une ATOT ouverte (→ `@after`, jamais de réécriture d'ATOT) ; 10 décisions fondateur.
- **Recouvrement avec ADEV (audit devis, fusionné sur main pendant cet audit)** : à la synchronisation, ADEV70 (pagination des écrans facture / avoirs / paiements) et ADEV35 (pagination du store des BC) recouvrent AFAC63 et AFAC64 ; ces deux tâches sont gardées (référencées par d'autres AFAC), préfixées « Recouvre ADEVn » et chaînées `@after` — le constructeur coche « déjà présent » si ADEV les livre.
- **Correction de fait relevée** : `docs/ownership.yml` déclare `core/events/facturation.py`, fichier inexistant (glob mort
  signalé par `check_ownership --verbose`, laissé à la session de propriété).

## 8. Non-risques consignés (valides tant que l'hypothèse tient)

- Sur-paiement refusé à l'encaissement manuel (live LIVE-2, `select_for_update` sur `montant_du`) ; montant à > 2 décimales refusé
  (jamais arrondi en silence).
- Webhook du fournisseur « noop » fail-closed : ne confirme jamais un paiement (`providers.py`, QX3) ; idempotence d'une
  notification rejouée STATIQUE (`encaissements.py:630-651`, statut PAYÉ sous verrou) — non exécutée (S-1).
- Portes SAV / intervention : `Produit.prix_vente` HT, TTC = HT × 1,2 (sonde W5-2) ; appel séquentiel idempotent (W5-1).
- Événements J5 : chaque émis a un abonné vivant ou figure dans `ALLOWED_UNCONSUMED` avec raison (lane FEVT, `event_coverage`).
- Six écrans J5 sans erreur console ni 4xx/5xx en usage nominal (LIVE-7).

## 9. Conclusion (phase 6)

- **Couverture.** 8 surfaces sur 8 lues (non-lus §4) ; 8 détecteurs exécutés, tous verts ; 63 constats par cause racine (7 S1,
  31 S2, 24 S3, 1 S4), 72/72 bruts reproduits, 13 repassés en seconde lentille ; scénarios H×H : S-2, S-3, S-4 joués par sondes,
  S-1 statique ; live : facture → encaissement partiel → lien de paiement → page publique, six écrans ; prod lue (4 mesures).
  **Non joués** : jeu `anon`, deux sociétés en écran, avoir / retour en écran (prouvés par sondes), PSP réel (inexistant).
- **Ce qui ne tient pas** (S1) : une facture encaissée s'annule et l'acompte disparaît du solde (002) ; un relevé bancaire
  ré-exporté recrée les paiements (008) ; le retour client crédite le HT brut sans remise ni palier (024) ; le relevé de compte
  ENVOYÉ au client compte les brouillons (032) ; PDF facture téléchargé / envoyé périmé, reste à payer faux (042) ; le paramétrage
  de relance accepte le client d'une autre société et coupe ses relances (035) ; l'écran facture est une cinquième porte qui
  perd la remise et facture l'option (057).
- **Registre** : J5 → `audité`, groupe `AFAC`, **89 tâches AFAC** : `PLAN_AUDIT_FACTURATION.md` 77 (dont 10 M1 bloquant-fondateur
  AFAC80-89 et l'acceptation live AFAC99), `PLAN_AUDIT_DEPLOY.md` 5 (gardes), `PLAN_AUDIT_DEVIS.md` 3, `PLAN_AUDIT_TRANSVERSE.md` 4.
- **Coût.** Scouts 2 (haiku) ; lanes 8 (FBC, FENC, FPAY, FCOR, FEVT opus/high ; FREC, FDOC, FUI sonnet/medium) ; vérificateurs 8
  (opus/high) ; seconde lentille 3 (opus/high) ; Fable 1 (critique de complétude) ; rédacteurs 5 (opus/high) ; ≈ 6,7 M jetons de
  sous-agents. Run live, prod en lecture seule, triage, routage : orchestrateur.
