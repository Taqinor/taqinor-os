<!-- verifie | groupe: ACNC | pct: 96 | ecarts_s1_s2: 2 -->
# Vérifie ACNC — contre-visite de clôture du parcours PF9 « gestes rejoués et courses », 14/11/2026 (2e passe)

Commande `loop audit` (14/11, soir). Le groupe ACNC a franchi 95 % de tâches cochées : `vérifie` de CLÔTURE. Cette 2e passe du
même jour remplace le compte rendu de mi-parcours du matin (git garde la 1re ; son rappel est au §6). Rien n'a été construit,
déployé ni coché.

## 0. Préconditions

- **SHA.** `origin/main` = `84561dcd3a` (merge de la PR #1411). Branche de claim : `verifie-cloture-1411b`.
- **Registre.** `audit_registre.py --du` (garde d'acceptation neutralisée) : « ACNC : 96 % cochées (50/52) — vérifie dû,
  clôture ». Restent ouvertes ACNC56 (acceptation du groupe) et ACNC68 (S3). Neuf tâches sont `[BLOCKED: code livré, preuve en
  direct due]` : ACNC7, 21-24, 28, 29, 42, 44.
- **Échantillon.** 40 tâches ont été cochées depuis le matin (12 → 52 cochées sur `47f925be1` → `84561dcd3a`). 31 sont contrôlées :
  - **les 16 cochées après le rectificatif**, toutes : ACNC4, 15, 57 à 67, 69 ;
  - **toutes les S2 cochées par rejeu** : ACNC1, 2, 3, 5, 6, 8, 25, 41 ;
  - **sept S3** : ACNC9, 10, 13, 26, 27, 33, 35.
  - Non relues : ACNC11, 12, 45, 46, 47, 49, 52, 53, 55 (S3, rejouées en direct).
- **Méthode.** Commits, code de HEAD, tests nommés et enregistrements d'acceptation lus. Trois sondes jouées sur l'hôte (§3) ;
  la garde `check_read_modify_write.py` et ses tests joués. Aucune pile, aucun test Django, aucun Docker, aucune production.

## 1. Vérificateurs

1 orchestrateur (opus) et 2 vérificateurs frais en lecture seule : opus/high sur l'argent (ACNC1-9), sonnet/high sur l'échantillon
S3 (ACNC10-41).

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **28** | ACNC1, 3, 4, 5, 6, 8, 9, 10, 13, 15, 25, 26, 27, 33, 35, 41, 57, 58, 59, 60, 61, 63, 64, 65, 66, 67, 69 ; ACNC62 sur ses deux gestes nommés |
| partiel | **2** | ACNC2 (clé gardée d'une facture à l'autre à l'écran, §3.2) ; ACNC62 (jumeau « Facturer la vente » laissé sans verrou, §3.1) |
| non-fait / faux / régression | **0** | — |

ACNC15 est jugée sur son commit (`6fe0c073f0`), son test vitest et son rejeu PASS. Son code n'a pas été relu ligne à ligne.

## 2. Les écarts graves du matin, sur pièces

| Tâche | État | Commit | La course est-elle fermée ? |
|---|---|---|---|
| ACNC62 (S1) | cochée (rejeu PASS `ff2ba7f2d`) | `c95b604d3e` | **Oui pour « Créer la facture » et « Livrer partiellement ».** `annuler` relit le BC par `select_for_update` dans `transaction.atomic()` et rejoue ses trois gardes sur la ligne relue. C'est la ligne que `creer_facture` et `livrer_partiel` verrouillent ; `porte_facture_bc` refuse un BC annulé. La sonde `C-ACNC-VER1-104.py`, rejouée sur le code réel, donne `repro: false` : 200 pour l'annulation, 409 pour la création de facture. Le test est à deux vraies connexions. **Non pour « Facturer la vente »** : §3.1. |
| ACNC67 (S1) | cochée (rejeu PASS `ff2ba7f2d`) | `d9028af82e` | **Oui.** La clé est gardée dans `useRef`, envoyée par `stockApi.createPaiementFournisseur` → `avecCle`, remise à `null` au succès, et le registre est relu sans réponse. Côté serveur, la réservation passe sous la contrainte unique `(company, endpoint, key)` avant la création (`core/idempotency.py::_reserver`). Reste un S3 : une saisie changée reçoit un 409 répété (§3.3). ACNC23 reste `[BLOCKED…]` alors que le texte d'ACNC67 la dit « cochée avec cette tâche » : tenue de plan à faire. |
| ACNC57 (S2) | cochée | `ca74c6a0c4` | **Oui.** Livraison relue `select_for_update` dans l'`atomic` ; contre-transfert dans un point de sauvegarde ; statut `annulee` posé dans la même transaction. Même verrou de ligne qu'`expedier` et `livrer`. Test `AnnulerConcurrenceTests` à deux fils. La sonde `C-ACNC-VER1-100.py` plante désormais à l'import du vrai `django.db.transaction`, comme elle l'annonçait par construction. |
| ACNC63 (S2) | cochée | `295d52fcc8` | **Oui, pour son périmètre** (chemin SANS course) : `refuser_portes_fermees` répond 409 `bon_commande_annule` et l'écran ne propose plus le BC annulé. La course CRUD ∥ « Annuler » sur un BC sans devis reste ouverte, sans verrou : S3, §3.4. |
| ACNC64 (S2) | cochée | `89d441a9fc` | **Oui.** La reprise et la pose du conflit sont des `UPDATE … WHERE statut <> appliquee` conditionnels. En READ COMMITTED, Postgres réévalue la condition sur la ligne validée après l'attente du verrou de `_executer` : 0 ligne touchée ⇒ rejeu. Test à deux fils. |
| ACNC4 (S2, D-ACNC-1) | cochée (rejeu PASS) | `66c27be9b9` | **Oui.** Sous le verrou de la facture, après la relecture par clé et les gardes : un paiement compté de même montant et même `date_paiement` (champ obligatoire, `models.DateField()`) ⇒ 409 `paiement_similaire`, rien d'écrit sans `confirmer_doublon`. `PaiementDialog` affiche la phrase et renvoie la même clé. « Facturer la vente » passe `confirmer_doublon=True` (paiements déclarés). Conforme à D-ACNC-1. L'assistant ne peut pas confirmer : §5. |

Les autres écarts du rectificatif sont tenus : ACNC65, 66, 69 (S3) sont cochées et leurs correctifs lus ; ACNC68 (S3) est ouverte.

## 3. Écarts nouveaux

### 3.1 C-ACNC-VER2-200 (S1) — « Facturer la vente » croisé avec « Annuler » le BC

**Mécanisme.**
- `facturer_vente` ne verrouille que le devis (`verrouiller_vente`), que l'annulation ne prend jamais.
- Dans cette transaction, `backend/django_core/apps/ventes/domain/facturation_vente.py::_creer_brouillon_complet` lit le BC du
  devis par `BonCommande.objects.filter(…).first()`, sans verrou. Il juge « non annulé, sans facture » puis insère la facture
  complète avec `bon_commande=bc`.
- `BonCommandeViewSet.annuler`, sous le seul verrou du BC, relit les factures vivantes avant ce commit et n'en voit aucune. Il
  écrit `annule`, puis les deux transactions valident.
- Résultat : un BC annulé porte une facture vivante, l'état qu'AUD118 et ACNC62 interdisent. Le brouillon reste émettable.
- C'est le seul autre créateur d'une facture rattachée à un BC dans `apps/ventes/domain` (grep `bon_commande=` : 1).

**Sonde.** `docs/audits/sondes/ACNC/C-ACNC-VER2-200.py`, jouée le 14/11 sur `84561dcd3a` : `repro: true`. L'annulation répond
200, le BC finit `annule`, la facture `BROUILLON-9` reste vivante et rattachée. Trace : « facturer : BC lu (verrou=False) » avant
« annuler : verrou BC pris ». Elle exécute les vrais `annuler`, `_creer_brouillon_complet` et `_inserer_facture` extraits par ast.
Contrôle : la même facturation, avec le BC lu par `select_for_update()`, donne 409 à l'annulation et `repro: false`.

**Limite de la sonde.** L'entrelacement est simulé (base factice à deux couches, vrai verrou de ligne), comme les autres sondes
PF9.

**Gravité S1.** Même état final et même dommage que C-ACNC-VER2-100 (ACNC62), classé S1 le matin. La probabilité est plus faible
(deux écrans différents : fiche du devis et liste des BC).

**Correctif et piège d'interblocage.** Verrouiller le BC dans `_creer_brouillon_complet` met l'ordre vente → BC. Or
`creer_facture` prend le BC puis la vente (`retirer_brouillons_de_la_vente` → `annuler_facture` → `verrouiller_vente`). La tâche
impose donc `verrouiller_vente` en tête de `creer_facture`. Le test d'ACNC62 simule le concurrent par un verrou du BC : il ne
pouvait pas voir ce jumeau.

**Tâche :** ACNC70 (`docs/plans/PLAN_AUDIT_FACTURATION.md`).

### 3.2 C-ACNC-VER2-201 (S2) — la clé de « Note de débit » passe d'une facture à l'autre

**Mécanisme.**
- `frontend/src/pages/ventes/NoteDebitDialog.jsx::NoteDebitDialog` ne remet `cleEnvoi` à zéro qu'au succès.
- Le bloc d'ouverture ou de changement de facture ne touche ni la clé, ni `motif`, ni `montant`, et le dialogue reste monté
  (`FactureList.jsx`).
- Côté serveur, l'espace de clés est (société, `…FactureViewSet.note_debit`, clé) et l'empreinte est le corps seul
  (`core/idempotency.py::_fingerprint`), sans l'id de la facture.

**Scénario.** La réponse d'une note de 500 sur A est perdue, puis l'utilisateur rouvre le dialogue sur B (même taux) et clique
« Créer » : le corps est identique, le serveur rejoue la note de A en 201. Le toast annonce « Note de débit … créée », la note de A
s'affiche sous B, et B n'est jamais majorée. Avec un corps différent, l'utilisateur reçoit un 409 de clé jusqu'au rechargement.

**Sonde.** `docs/audits/sondes/ACNC/C-ACNC-VER2-201.py` : `repro: true`. Elle exécute les vrais `IdempotentCreateMixin`,
`_reserver`, `_fingerprint`, `rejeu_par_cle` et `cle_du_corps`, et lit le vrai composant. Contrôle avec une clé neuve pour B :
deux notes créées.

**Gravité S2, pas S1.** Aucun montant n'est compté deux fois. Mais un succès faux est annoncé sur un geste d'argent, sans
contournement visible à l'écran. Les autres dialogues (paiement, avoir, retour, encaissement groupé) renouvellent leur clé à
l'ouverture.

**Tâche :** ACNC71 (`docs/plans/PLAN_AUDIT_FACTURATION.md`).

### 3.3 C-ACNC-VER2-202 (S3) — règlement fournisseur : 409 de clé répété après une saisie changée

`PaiementsFournisseurLedgerPage.jsx::enregistrer` (et `FacturesFournisseur.jsx::FactureDetail`) gardent la clé jusqu'à un succès,
quelle que soit la saisie. Après une réponse coupée, un règlement d'une autre facture ou d'un autre montant reçoit le 409
`IdempotencyConflict` à chaque clic, jusqu'au rechargement. C'est un contournement, pas de l'argent faux. Verdict STATIQUE (lecture
de `_reserver` et du composant). **Tâche :** ACNC72 (`docs/plans/PLAN_AUDIT_STOCK.md`).

### 3.4 C-ACNC-VER2-203 (S3) — facture CRUD sur un BC sans devis croisée avec « Annuler »

`FactureViewSet.perform_create` juge le BC par `refuser_portes_fermees` sur la copie validée, sans transaction ni verrou ; l'annulation
peut lire « aucune facture » puis écrire `annule`. Même état final que §3.1, mais sur un BC saisi sans devis (rare) et avec un
contournement (annuler la facture). STATIQUE. **Sans tâche :** le correctif exige une transaction dans
`backend/django_core/apps/facturation/views/facture.py`, fichier-mur C20 qui ne grossit plus ; à reprendre avec sa sortie du mur.

## 4. Tableau des écarts

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-ACNC-VER2-200 | ACNC62 | S1 | « Facturer la vente » complète croisée avec « Annuler » : BC annulé portant une facture vivante (`backend/django_core/apps/ventes/domain/facturation_vente.py::_creer_brouillon_complet`) | `docs/audits/sondes/ACNC/C-ACNC-VER2-200.py` (`repro: true`) | ACNC70 |
| C-ACNC-VER2-201 | ACNC2 | S2 | Clé et saisie de « Note de débit » gardées d'une facture à l'autre : note de A rejouée pour B (`frontend/src/pages/ventes/NoteDebitDialog.jsx::NoteDebitDialog`) | `docs/audits/sondes/ACNC/C-ACNC-VER2-201.py` (`repro: true`) | ACNC71 |
| C-ACNC-VER2-202 | ACNC67 | S3 | Clé du règlement gardée après une saisie changée : 409 répété (`frontend/src/pages/stock/PaiementsFournisseurLedgerPage.jsx::enregistrer`) | STATIQUE | ACNC72 |
| C-ACNC-VER2-203 | ACNC63 | S3 | Création CRUD d'une facture sur un BC sans devis, sans verrou, croisée avec « Annuler » (`backend/django_core/apps/facturation/views/facture.py::FactureViewSet.perform_create`) | STATIQUE | sans tâche : fichier-mur C20 |

**Marqueur.** 2 écarts S1-S2 nouveaux (200, 201). Tous les écarts S1-S2 du compte rendu du matin ont leur tâche cochée (ACNC57,
62, 63, 64, 67) : aucun n'est ajouté. Hors de ce compte : ACNC7 et ACNC21 à 24, S2 d'origine, livrées et en attente de preuve en
direct.

## 5. Optionnel (non déposé)

- **Assistant et D-ACNC-1.** `apps/ventes/agent_actions.py::ENREGISTRER_PAIEMENT` n'a ni `confirmer_doublon` ni clé : un second
  paiement identique saisi par l'assistant est toujours refusé, la question « confirmer ? » n'a pas de réponse possible. Il faut
  concevoir le parcours de confirmation de l'assistant (copilote éteint par défaut).
- **Paiement client.** ACNC1 ne compare pas le corps : la même clé avec un autre montant, après un délai expiré, rend l'ancien
  paiement en 200 et l'écran dit « Paiement enregistré ».
- **Écritures non bornées par ACNC41.** Environ 100 `perform_update` appellent `serializer.save()` sans `super()` et échappent à la
  borne ACNC41 (`apps/facturation/views/facture.py::FactureViewSet.perform_update` notamment). Non sondé.
- **Gardes ACNC25 sur instance périmée.** Les gardes de la livraison et de la demande de transfert lisent l'instance périmée :
  un PATCH `{depot}` croisé avec « Expédier » écrit un champ censé être figé.
- **Tests de relecture sans fil concurrent.** Les tests d'ACNC5, ACNC6 et ACNC13 prouvent la relecture, pas le verrou. La course
  n'est prouvée qu'en direct.
- **Sondes à entretenir.**
  - Le contrôle de `C-ACNC-VER1-104.py` s'interbloque sur le code corrigé (double prise du verrou factice) : le `__main__` ne
    rend plus la main.
  - `C-ACNC-VER1-100.py` plante à l'import.
  - ACNC56 demande « avant reproduit, après non » sur les sondes S2.
- **Idempotence.** `_avec_idempotence` libère la clé si une exception survient après le commit de la création ; une réservation
  « en cours » orpheline expire au bout de 15 min, puis la clé est reprise.

## 6. Rappel de la passe du matin (mi-parcours, `47f925be1`, rectifiée le soir)

- **C-ACNC-VER1-100 (S2)**, deux « Annuler » croisés d'une livraison : **fermé** par ACNC57 (§2).
- **C-ACNC-VER1-101 à 103 (S3)**, tests de course manquants pour « Expédier », « Livrer » et la suppression d'un avoir, et clés
  périmées de la garde : **fermés** par ACNC58, 59, 60 et 61. Les tests sont à deux connexions. La garde rend 0 et ses 54 tests
  passent ; une clé gelée qui n'est plus signalée est refusée.
- **C-ACNC-VER2-100 (S1)**, « Annuler » un BC sans verrou : **fermé** pour ses deux gestes nommés par ACNC62 ; le jumeau est ouvert
  en §3.1.
- **C-ACNC-VER2-101 (S2)** : fermé par ACNC63. **C-ACNC-VER2-102 (S2)** : fermé par ACNC64. **C-ACNC-VER2-103 et 104 (S3)** :
  fermés par ACNC65 et 66.
- **Rectificatif.**
  - **C-ACNC-VER3-100 (S1)**, règlement fournisseur sans clé : **fermé** par ACNC67.
  - **C-ACNC-VER3-101 (S3)** : ACNC68, ouverte.
  - **C-ACNC-VER3-102 (S3)** : fermé par ACNC69.
  - Les sondes 004 à 006 étaient périmées ; ACNC21 à 24 sont livrées et attendent leur preuve en direct.
- **ACNC4** (D-ACNC-1), ouverte le matin : **livrée et cochée** (§2).

## 7. Couverture et sortie de cycle

- **Couvert.** 31 tâches sur 40 cochées depuis le matin, dont toutes les S1-S2 et toutes celles cochées après le rectificatif.
  Trois sondes hôte ont été jouées : VER1-104, rejouée sur le code réel avec `repro: false`, et les deux nouvelles VER2-200 et
  VER2-201. La garde `check_read_modify_write.py` rend OK.
- **Non couvert.**
  - Aucun test Django, vitest ni e2e lancé. Les tests à deux connexions sont supposés verts par la CI des merges, et les rejeux
    en direct par leurs enregistrements PASS (`ff2ba7f2d`, `f4c345110`, `c5c831e37`, `3d6d2abe8`).
  - Neuf S3 cochées n'ont pas été relues (§0).
  - L'ordre des verrous a été vérifié par lecture seulement : aucun interblocage n'a été rejoué sur une vraie base.
- **Statut.** Deux écarts S1-S2 nouveaux : le groupe reste « construit », pas « vérifié ». Une contre-visite des correctifs sera due
  quand ACNC70 et ACNC71 seront cochées.

## 8. Coût

H0 S1 O2 F0 : 1 orchestrateur opus, 1 vérificateur opus/high (argent), 1 vérificateur sonnet/high (S3). Jetons des sous-agents
≈ 0,45 M. Aucun appel Fable.
