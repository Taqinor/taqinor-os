<!-- verifie | groupe: ACNC | pct: 98 | ecarts_s1_s2: 1 -->
# Vérifie ACNC — contre-visite des correctifs du 14/11 (2e passe), parcours PF9 « gestes rejoués et courses », 15/11/2026

Commande `loop audit` (15/11). Le registre annonce « ACNC : 98 % cochées (54/55) — vérifie dû, contre-visite des correctifs
(écarts S1-S2 du 2026-11-14 tous cochés) ». Contre-visite étroite (METHODE §C.4.6) : les trois tâches d'écart déposées hier
(ACNC70, 71, 72), ce qu'elles ont pu casser, ACNC23 et les deux sondes VER2. Rien n'a été construit, déployé ni coché.

## 0. Préconditions

- **SHA.** `origin/main` = `8fc408bf61` (merge de la PR #1415). Branche : `verifie-1511`.
- **Registre.** `audit_registre.py --du` (garde d'acceptation neutralisée) : ACNC 98 % (54/55). Reste ouverte ACNC56
  (acceptation du groupe). Neuf tâches restent `[BLOCKED: code livré dev-all (13/11/2026), preuve en direct due]` : ACNC7,
  21-24, 28, 29, 42, 44.
- **Échantillon.** Les trois tâches d'écart d'hier, toutes : ACNC70 (S1), ACNC71 (S2), ACNC72 (S3).
- **Commits lus.** `a3ff194619` (ACNC70), `706e63f391` (ACNC71), `b4f94e3386` (ACNC72) ; tests nommés ; enregistrement
  d'acceptation `docs/audits/acceptation/ACNC/2026-11-14-8cd81386e.md` (PASS, `couvre: [ACNC70, ACNC71, ACNC72]`) et sa spec
  `frontend/e2e/acceptation/acnc6.spec.js`.
- **Méthode.** Lecture du code de `8fc408bf61`, greps des chemins de verrou et des créateurs de facture, trois sondes hôte
  jouées (§3, §4). Aucune pile, aucun test Django ni vitest lancé, aucun Docker, aucune production.

## 1. Vérificateur

1 orchestrateur-vérificateur frais (opus/high), lecture seule, en un seul passage (périmètre de trois tâches).

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **2** | ACNC70, ACNC71 |
| régression | **1** | ACNC72 : correct sur le registre ; sur son jumeau « traité ici à l'identique », la fiche facture fournisseur, il ouvre un double règlement (§3) |
| partiel / non-fait / faux | **0** | — |

## 2. Les écarts d'hier, sur pièces

| Écart | Tâche | État | Fermé ? |
|---|---|---|---|
| C-ACNC-VER2-200 (S1) | ACNC70 | cochée (rejeu PASS `8cd81386e`) | **Fermé.** Détail ci-dessous. |
| C-ACNC-VER2-201 (S2) | ACNC71 | cochée (rejeu PASS `8cd81386e`) | **Fermé à l'écran.** Détail ci-dessous. |
| C-ACNC-VER2-202 (S3) | ACNC72 | cochée (rejeu PASS `8cd81386e`) | **Fermé sur le registre** ; régression S1 sur le jumeau (§3). |
| C-ACNC-VER2-203 (S3) | — | sans tâche | **Ouvert, inchangé** (`FactureViewSet.perform_create` intouché depuis `295d52fcc8`). |

### 2.1 ACNC70 — « Facturer la vente » complète ∥ « Annuler » le BC

- **Verrou dans la transaction.** `backend/django_core/apps/ventes/domain/facturation_vente.py::_creer_brouillon_complet` lit
  désormais le BC par `BonCommande.objects.select_for_update().filter(devis=…, company_id=…).first()`. La fonction n'est appelée
  que par `_facturer_complete` ← `facturer_vente`, sous `with transaction.atomic()` après `verrouiller_vente`.
  `facturation_ops.py::facturer_devis_complet` passe par `facturer_vente` : même chemin.
- **Gardes rejouées sur la ligne relue.** Après la prise du verrou, `bc.statut == ANNULE` et
  `Facture.objects.filter(bon_commande=bc).exists()` sont lus sur la ligne relue (nouvelle instruction, READ COMMITTED) :
  - si « Annuler » valide d'abord, la facture naît sans `bon_commande` ;
  - si la facturation valide d'abord, `annuler` relit la facture vivante et répond 409.
- **Ordre des verrous**, relevé sur tous les `select_for_update` du BC et tous les appels à `verrouiller_vente` :
  - `facturer_vente` et `creer_facture` : vente puis BC. `creer_facture` appelle désormais `verrouiller_vente(bc.devis)` avant
    de relire le BC.
  - `annuler`, `confirmer`, `marquer_livre`, `livrer_partiel` : BC seul, puis produits et réservations.
    `_sortir_reliquat_bc`, `lignes_reliquat_vente` et `solder_reservations_chantier_vente` ne verrouillent jamais la vente.
  - `perform_update` (BC) : nouveau devis, puis l'UPDATE du BC.
  - `annuler_facture`, `verrouiller_emission`, `echeancier`, `encaissements`, `devis_cycle` : vente, puis facture, sans BC.
  - `revision.py` (avenant accepté) et `annulation_facture.py::detacher_bc_annules` : écriture du BC sous le verrou de la racine
    déjà pris.
  - `BonCommande.save` ne touche pas au devis, et aucun receveur `post_save` n'est branché sur le BC.
  - **Aucune inversion vente/BC trouvée.** `verrouiller_vente` prend toujours la racine en premier (tri par pk), ce qui
    sérialise aussi le cas d'un BC re-pointé d'une version à l'autre.
- **Autres créateurs.** Seuls trois chemins créent une facture rattachée à un BC : `_creer_brouillon_complet`, `creer_facture`
  et la création CRUD (VER2-203, §6). Ni `_facturer_acompte` ni les tranches ne posent `bon_commande`.
- **Test.** `backend/django_core/apps/ventes/tests/test_aud118_annuler_bc_facture.py::AnnulerBcConcurrenceTests::test_annuler_croise_facturer_vente_complete`.
  - Il oppose **deux vraies connexions** (`TransactionTestCase`, fil avec `connection.close()`) au vrai `facturer_vente`, sans
    verrou posé par le test, et attend `attendre_un_ecrivain_bloque`.
  - Il ne couvre qu'un ordre (facturation d'abord). Aucun test ne croise `creer_facture` avec `facturer_vente` : l'absence
    d'interblocage n'est établie que par lecture.
- **Sonde VER2-200 rejouée** sur `8fc408bf61` : `repro: false` (§4).

### 2.2 ACNC71 — clé et saisie de « Note de débit »

- `frontend/src/pages/ventes/NoteDebitDialog.jsx::NoteDebitDialog` vide `motif` et `montant` dans le bloc d'ouverture ou de
  changement de facture.
- La clé est remise à `null` par `useEffect(() => { if (open) cleEnvoi.current = null }, [open, factureId])`. L'effet s'exécute
  avant tout clic possible, et le commit explique pourquoi la remise est hors du rendu (`react-hooks/refs`).
- Le test vitest « réponse perdue sur A puis ouverture sur B : saisie vide, clé neuve » vérifie les champs vides et deux clés
  différentes. Il n'a pas été lancé ici.
- **Côté serveur, la clé n'est PAS liée à la facture.** Le suffixe `note_debit` est constant
  (`facture_rectificatifs.py::rejeu_par_cle`) et l'empreinte ne porte que le corps (`core/idempotency.py::_fingerprint`). La
  tâche le déclarait hors périmètre. Aucun autre client n'envoie de clé à cette route : rien n'est exploitable aujourd'hui
  (§5).
- **Jumeaux.** Avoir, retour et encaissement groupé (`useFactureGestes.js`, `nouvelleCle()` à l'ouverture) et `PaiementDialog`
  (clé remise quand `facture.id` change) sont conformes. Le paiement fournisseur porte le suffixe `paiements.<pk>`, donc la clé
  y est liée à la facture.

### 2.3 ACNC72 — clé du règlement fournisseur

- **Registre** (`PaiementsFournisseurLedgerPage.jsx`) : `useEffect(() => { cleReglement.current = null }, [draft])`. Saisie
  inchangée : même clé. Saisie changée : clé neuve. Sans réponse, `charger()` relit le registre affiché, comme le suppose le
  Given de la tâche. Conforme, test vitest ajouté.
- **Fiche facture fournisseur** (`FacturesFournisseur.jsx::FactureDetail`, jumeau « traité ici à l'identique ») : même remise,
  sur `[montant, datePaiement, mode]`.
  - Sans réponse, la fiche n'est pas relue : seule la liste derrière l'est. Une retouche crée donc un second règlement : §3.
  - Aucun test vitest pour ce jumeau. L'étape d'acceptation `PF9.4-ACNC72-fiche-facture` joue « 3 000 coupé puis 1 000 », deux
    règlements voulus. Elle n'affirme pas ce que montre la fiche entre les deux clics.

## 3. Écart nouveau

### 3.1 C-ACNC-VER3-300 (S1) — fiche facture fournisseur : réponse perdue, puis saisie retouchée, donne un second règlement

**Mécanisme.**
- `frontend/src/pages/stock/FacturesFournisseur.jsx::FactureDetail` garde sa propre copie, `useState(factureProp)`. Elle n'est
  jamais resynchronisée : `factureProp` n'apparaît que deux fois.
- Sans réponse, `ajouter` appelle seulement `onSaved?.()`. Le parent répond par `reload(); if (msg) setInfo(msg)` : il relit la
  liste, jamais `selected`.
- La fiche montre donc encore « Aucun paiement » et l'ancien solde, alors que le commentaire d'ACNC23 annonce « relire la
  facture ».
- Depuis ACNC72, toute retouche de `montant`, `datePaiement` ou `mode` (date remplie, mode changé, montant retapé) remet la clé
  à zéro. Le clic suivant crée un second règlement.
- Le serveur ne plafonne qu'au solde dû
  (`backend/django_core/apps/stock/services.py::verrouiller_facture_fournisseur_et_verifier_solde`). Il n'existe pas
  d'avertissement de paiement similaire côté fournisseur (grep `paiement_similaire|confirmer_doublon` dans `apps/stock` : 0).
- Avant ACNC72, la même retouche recevait un 409 `IdempotencyConflict` et rien n'était écrit.

**Sonde.** `docs/audits/sondes/ACNC/C-ACNC-VER3-300.py`, jouée sur `8fc408bf61` : `repro: true`.
- Elle exécute par ast les vrais `IdempotentCreateMixin`, `_reserver`, `_fingerprint`, `_liberer` et
  `verrouiller_facture_fournisseur_et_verifier_solde`, avec le suffixe réel `paiements.<pk>`.
- Elle lit le vrai composant : remise sur `montant, datePaiement, mode`, aucune relecture de la fiche sans réponse, `onSaved`
  du parent.
- Résultat : 201 puis 201, deux règlements de 3 000, solde 4 000 au lieu de 7 000.
- Contrôles :
  - clé gardée (l'écran d'avant ACNC72) : 201 puis 409 `IdempotencyConflict`, un règlement, solde 7 000 ;
  - saisie inchangée : rejeu, un règlement.

**Gravité S1** (§B.2 : argent faux). Un règlement est compté deux fois, sans rien à l'écran pour l'en avertir, et le solde dû
est sous-évalué. C'est le même dommage que C-ACNC-VER3-100, classé S1 hier. La probabilité est plus faible : il faut une réponse
perdue PUIS une retouche. Le défaut est latent en production (0 facture fournisseur au 11/11 selon ACNC23, chiffre non relu
ici). Il n'y a pas de dépassement : un règlement complet doublé est refusé par le plafond.

**Correctif.** Relire la facture dans la fiche après une réponse perdue (`stockApi.getFactureFournisseur` puis `setFacture`).
La remise de clé d'ACNC72 reste en place. Ce n'est pas un retour en arrière d'ACNC72 : la règle « saisie changée = clé neuve »
devient sûre dès que l'écran montre ce qui est passé.

**Tâche :** à déposer, ACNC73 (`docs/plans/PLAN_AUDIT_STOCK.md`, propriétaire `stock`).

## 4. Sondes rejouées sur l'hôte (`8fc408bf61`)

| Sonde | Sortie | Encore valable ? |
|---|---|---|
| `C-ACNC-VER2-200.py` | le `__main__` plante (`AssertionError: lecture du BC introuvable dans _creer_brouillon_complet`) | **Partie réelle valable, contrôle périmé.** Le contrôle réécrit `BonCommande.objects.filter(` en `select_for_update().filter(`, une forme que le correctif a fait disparaître. La partie « code réel », jouée seule (`_jouer` sur les vrais `annuler`, `_creer_brouillon_complet` et `_inserer_facture`), donne `repro: false` : facturation 201, annulation **409**, BC `confirme`, `BROUILLON-9` rattachée. Trace : « facturer : verrou BC pris » puis « annuler : verrou BC pris ». |
| `C-ACNC-VER2-201.py` | `repro: true` | **Faux positif, périmée.** Son détecteur d'écran cherche la remise de clé DANS le bloc d'ouverture ; ACNC71 l'a posée dans un `useEffect`. Le rejeu serveur reste vrai par construction (même clé pour B ⇒ note de A rejouée) : il prouve seulement que la clé serveur n'est pas liée à la facture (§2.2), pas que l'écran la réutilise. |
| `C-ACNC-VER3-300.py` (neuve) | `repro: true` | §3. |

ACNC56 exige une sortie « avant `repro` True, après `repro` False » par sonde S2. VER2-200 et VER2-201 doivent être réécrites
pour la donner : contrôle sur la forme corrigée pour l'une, détecteur d'écran sur l'effet pour l'autre (§5).

## 5. Optionnel (non déposé)

- **ACNC23, point 4 de la commande.**
  - Toujours `[BLOCKED: code livré dev-all (13/11/2026), preuve en direct due]` (`docs/plans/PLAN_AUDIT_STOCK.md`).
  - Aucun des cinq enregistrements ACNC ne la couvre (grep `ACNC23` dans `docs/audits/acceptation/ACNC/` : 0).
  - Le texte d'ACNC67 (« se coche avec cette tâche ») est contredit par celui d'ACNC72 (« reste `[BLOCKED…]` ») : c'est le second
    qui décrit l'état réel.
  - Elle ne peut pas se cocher par ricochet : l'enregistrement d'ACNC67 ne rejoue que le registre, pas la réception, l'acompte ni
    le règlement de la fiche.
  - Et METHODE §C.4.7 (c) interdit de la cocher tant que C-ACNC-VER3-300 touche son propre code (`FactureDetail`, commentaire
    ACNC23).
- **Note de débit, même facture.** Après une réponse perdue, une saisie retouchée sur la MÊME facture reçoit le 409 de clé
  jusqu'à la fermeture du dialogue. C'est la classe de VER2-202, avec un contournement (fermer, rouvrir). De plus, `erreur`
  n'est pas vidé à l'ouverture : le message de A s'affiche sous B (S4).
- **Clé serveur non liée au document.** `note_debit`, `avoir` et `retour` utilisent un suffixe constant ; le paiement
  fournisseur utilise `paiements.<pk>`. Lier le suffixe à la facture serait une défense en profondeur. Aucun appelant actuel
  n'est fautif.
- **Acompte, avoir fournisseur, réception BCF.** `FournisseurFiche360.jsx::AcompteForm`, l'avoir et `BcfDetail` gardent une clé
  par ouverture : une saisie changée après une réponse perdue reçoit un 409 répété, que l'on contourne en fermant puis
  rouvrant. Non déposé à dessein : c'est l'état SÛR. Renouveler la clé sans relire l'écran reproduirait §3.
- **VER2-203 sans tâche : la raison donnée hier ne tient pas.** `backend/django_core/apps/facturation/views/facture.py` fait
  349 lignes et `FactureViewSet.perform_create` 60 lignes (`check_forme_code.py --inspecter`) : ni FICHIER_MUR (≥ 2 000) ni
  FONCTION_MUR (> 100). Le S3 peut recevoir sa tâche (`transaction.atomic` + BC relu `select_for_update` + `refuser_portes_fermees`
  rejoué).
- **Test d'ordre des verrous.** Aucun test ne croise `creer_facture` avec `facturer_vente` sur deux connexions : l'absence
  d'interblocage n'est prouvée que par lecture.

## 6. Tableau des écarts

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-ACNC-VER3-300 | ACNC72 (jumeau), ACNC23 | S1 | Réponse perdue sur « Ajouter le paiement » : la fiche n'est pas relue, une saisie retouchée part sous une clé neuve, second règlement (`frontend/src/pages/stock/FacturesFournisseur.jsx::FactureDetail`) | `docs/audits/sondes/ACNC/C-ACNC-VER3-300.py` (`repro: true`) | ACNC73 (à déposer) |
| C-ACNC-VER2-203 | ACNC63 | S3 | Création CRUD d'une facture sur un BC sans devis, sans verrou, croisée avec « Annuler » (`backend/django_core/apps/facturation/views/facture.py::FactureViewSet.perform_create`) | STATIQUE | sans tâche (raison d'hier infirmée, §5) |

**Marqueur.** 1 écart S1-S2 nouveau (VER3-300). Les écarts S1-S2 d'hier (VER2-200, VER2-201) ont leur tâche cochée et sont
fermés. Hors de ce compte : ACNC7 et ACNC21 à 24, S2 d'origine, livrées et toujours en attente de preuve en direct.

## 7. Couverture et sortie de cycle

- **Couvert.**
  - Les 3 tâches d'écart d'hier.
  - Tous les `select_for_update` du BC et tous les appels à `verrouiller_vente` hors tests.
  - Tous les créateurs de facture rattachée à un BC.
  - Les dialogues jumeaux de clé (vente et achat).
  - Trois sondes hôte.
- **Non couvert.**
  - Aucun test Django, vitest ni e2e lancé.
  - Les tests à deux connexions et les vitest neufs sont supposés verts par la CI de #1415 ; le rejeu en direct par son
    enregistrement PASS (`8cd81386e`).
  - Aucun interblocage rejoué sur une vraie base.
  - La sonde VER3-300 simule le comportement de l'écran à partir de sa lecture : la fiche n'a pas été affichée dans un
    navigateur.
- **Statut.** Un écart S1 nouveau : le groupe reste « construit », pas « vérifié ». Le compteur de sortie (deux `vérifie`
  consécutifs à zéro S1-S2) est à 0. Une contre-visite des correctifs sera due quand ACNC73 sera cochée. ACNC56 attend aussi
  les sondes S2 réécrites (§4) et les preuves en direct d'ACNC7, 21-24, 28, 29, 42 et 44.

## 8. Coût

H0 S0 O1 F0 : 1 orchestrateur-vérificateur opus/high, sans sous-agent. Jetons des sous-agents ≈ 0 M. Aucun appel Fable.
