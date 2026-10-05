# Audit J6 « documents » — dossier d'évaluation (L2, 05/10/2026)

Unité **J6** du registre (`docs/audits/unites.yml`), groupe **ADOC**, niveau **L2** (défaut du registre ;
auto-pick go-deep confirmé : sortie client — portail, PDF de chantier, page publique — et multi-société,
mais ni moteur de devis ni chaîne argent possédés ⇒ L2, pas L3). Claim : branche `audit-J6` (`47dfd46c6`).
Méthode : `docs/audits/METHODE.md` v2. Sorties brutes (cartes, constats bruts, verdicts, JSON du run live) :
scratchpad de la session — seuls la commande, le SHA et un extrait court figurent ici.

## 0. Préconditions (phase 0)

- **SHA.** Lecture à `origin/main` `7e325e0ae` (05/10/2026). Pile locale : la checkout principale
  `C:\dev\taqinor-os` sur `main` `7e325e0ae` (montée dans `erp-agentique-django_core-1`).
- **Propriété.** `docs/ownership.yml` existe et PRIME : J6 = `apps/documents/**`, `apps/portail/**`,
  `ventes/selectors_portail.py`, `templates/pdf/document_*`, `api/{documents,ged,portail}Api*`,
  `features/{ged,portail}/**`, `pages/ged/**`, résiduel `apps/ged/**`. **`apps/web/src/pages/suivi/**`
  n'est PAS à J6** (propriétaire `web` → `docs/WEB_PLAN.md`) alors que `unites.yml` le revendique encore :
  le registre est corrigé dans cette PR (§9).
- **Apps parquées.** `python scripts/check_parked_apps.py` → « OK — aucune référence vers les 47 apps
  parquées ».
- **Dédoublonnage** : voir §4 (scout haiku, résultat au scratchpad `doc/dedupe.md`).

## 1. Charte (phase 1)

- **Système et frontière.** Possédé (ownership.yml) ci-dessus. `perimetre_lu` : sélecteurs lus par le
  portail (ventes, ged, installations, crm, sav, stock) ; couture `document_produit` (ventes / calepinage →
  `ged/receivers.py`) ; endpoint public `GET /api/django/ventes/suivi/<token>/` (QX34, J1b) consommé par la
  page `apps/web` `suivi/[token].astro` (propriétaire web). Contrats : `apps/portail/contract_samples/`
  (13 échantillons). Apps parquées exclues.
- **Objet.** Objectifs fondateur 1 (tout se corrige après coup), 2 (une fonction par geste), 3 (code
  propre), 4 (le client voit le bon chiffre). Contrat J6 (METHODE §D.6) : le client voit TOUJOURS la
  version en vigueur (« mis à jour le … »), rien hors de son périmètre (NTPRT14), même CGV que le PDF.
- **Personas réelles** (`roles/models.py` `CANONICAL_SYSTEM_ROLES`) : Administrateur, Commercial,
  Technicien responsable ; **client portail** (`ComptePortail`), partenaire et fournisseur portail
  (comptes externes). Aucun compte portail n'est seedé : le run live en crée un en local (couverture
  déclarée en §4).
- **Niveau** L2 ; **jeu de données** `demo` (société démo) + second locataire (C5).
- **Critères retenus** : C1, C2, C3, C4, C5, C6, C8, C9, C10, C11 (règle #4 : un devis montré au portail
  passe par `/proposal`), C13 ; C7 limité à « montant portail = montant facture/devis ». **Non retenus** :
  C12 (hors rejeu live), C14 (unité X6).
- **Sous-domaine** : support (GED, portail) ⇒ L2.
- **Étapes (identifiants stables).**
  P1 GED interne — P1.1 dépôt / classement (dossiers, tags, règles) · P1.2 versions et remplacement ·
  P1.3 navigateur / recherche · P1.4 ACL, partages, coffres · P1.5 approbation · P1.6 rétention, legal
  hold, corbeille, destruction · P1.7 numérisation / OCR / lots · P1.8 modèles de documents, tampons.
  P2 Signature et dépôt public — P2.1 demande de signature · P2.2 page publique (OTP) · P2.3 multi-
  signataires / champs · P2.4 dépôt public.
  P3 Documents de chantier (`apps/documents`) — P3.1 PV de réception · P3.2 bon de livraison · P3.3
  dossier de remise · P3.4 attestation.
  P4 Couture documents produits → GED — P4.1 `document_produit` (facture, calepinage) → classement ·
  P4.2 version en vigueur côté GED.
  P5 Portail client — P5.1 provisionnement / invitation / mot de passe · P5.2 tableau de bord · P5.3 mes
  devis (+ acceptation) · P5.4 mes factures (+ paiement) · P5.5 mes chantiers / jalons / photos · P5.6 mes
  documents · P5.7 livraisons / preuve · P5.8 demandes SAV / fil · P5.9 équipe · P5.10 export, recherche,
  consommation.
  P6 Portails externes — P6.1 partenaire (soumissions, commissions, ressources) · P6.2 fournisseur (BCF,
  factures, candidature, performance).
  P7 Administration portail (écrans ERP) — comptes, acceptations, paiements, documents client, jalons,
  demandes de ticket.
  P8 Suivi public — P8.1 `suivi/[token]` ← `ventes/suivi/<token>/`.
- **Non-objectifs.** Intérieur du moteur `/proposal` (D2/X4) ; PDF facture legacy (J5) ; studio toiture
  et livrables calepinage (D3, déjà audité) ; apps parquées.

## 2. Spécification (phase 2)

**Scénarios H×H (joués en direct à L2)** — stimulus → réponse → mesure :
S-A version en vigueur : un devis/facture déjà visible au portail est corrigé côté ERP → le portail et le
document téléchargé montrent la nouvelle version et sa date (parité écran ERP = JSON portail = PDF).
S-B étanchéité : client portail A demande les objets du client B (même société) et d'une autre société
(identifiants substitués) → 404, jamais 403 ni donnée. S-C `prix_achat` / marge jamais dans un JSON
portail, une page à jeton ou un PDF de chantier. S-D GED aller-retour : déposer → renommer / reclasser /
nouvelle version → rouvrir ⇒ identique, chatter old→new. S-E signature publique : demande → OTP → signé →
document final versionné, lien rejoué refusé. S-F document de chantier (PV / BL) régénéré après correction
du chantier ⇒ reflète la correction. S-G suivi public : jeton valide / révoqué / d'une autre société.

**Saisie → consommateurs.**

| Saisie | Écrite par | Lue par |
|---|---|---|
| fichier / version GED | navigateur GED, `document_produit`, dépôt public, signature | navigateur, recherche, portail « mes documents », partages, rétention |
| document client portail (`DocumentClientPortail`) | admin portail | portail client |
| devis / facture / BC (ventes) | ventes | portail mes devis / factures (via `selectors_portail`), PDF |
| jalons chantier portail | admin portail / installations | portail mes chantiers, suivi public |
| identité client (nom, e-mail) | crm / ventes | compte portail, invitation, PDF chantier |
| CGV (`parametres`) | paramètres | PDF devis, portail (acceptation) |

**Chaîne documentaire 1:N.** client 1-N comptes portail ; devis 1-N révisions (V2) → portail montre la
version en vigueur ; facture 1-N paiements portail ; chantier 1-N jalons / photos / PV / BL ; document GED
1-N versions ; demande de signature 1-N signataires.

**Seuils.** S1-S2 ⇒ tâche ; S3 ⇒ tâche si effort ≤ M ; S4, style, durcissement hypothétique ⇒ liste
OPTIONNELLE. Chiffre client / multi-société : toujours correctness, CONFIRMÉ seulement sur preuve exécutée.

**Détecteurs prévus (4-a).** `check_parked_apps`, `check_services_appeles`, `check_ecrans_atteignables`,
`rapport_backend_sombre`, `check_api_shapes`, `check_api_contract`, `check_openapi_shapes`,
`check_tests_source_regex`, `check_invariants`, `core/event_coverage.py` (abonnés/émetteurs ged/portail),
`lint-imports`, `makemigrations --check --dry-run` (conteneur), `audit_coherence` (aucune règle J6 attendue).
