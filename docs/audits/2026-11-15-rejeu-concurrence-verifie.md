<!-- verifie | groupe: ACNC | pct: 98 | ecarts_s1_s2: 0 -->
# Vérifie ACNC — contre-visite d'ACNC74 et ACNC75 (VER5, 3e passe du 15/11), parcours PF9 « gestes rejoués et courses », 15/11/2026

Le registre annonce « ACNC (PF9 rejeu-concurrence) : 98 % cochées (57/58) — vérifie dû, contre-visite des correctifs (écarts
S1-S2 du 2026-11-15 tous cochés) » (`audit_registre.py --du`, garde d'acceptation neutralisée, relu dans cette passe).
Contre-visite étroite (METHODE §C.4.6) : les deux tâches d'écart déposées par la 2e passe du jour, ACNC74 (C-ACNC-VER4-400, S2)
et ACNC75 (C-ACNC-VER4-401, S3), ce qu'elles ont pu casser (ACNC67, ACNC72, ACNC73), la sonde VER4-400, ACNC23 et le S3
VER2-203. Rien n'a été construit, déployé ni coché. Ce compte rendu remplace celui de la 2e passe (§C.4.5 f) ; les deux passes
précédentes du jour sont résumées en §8.

## 0. Préconditions

- **SHA.** `origin/main` = `5290db5dad` (merge de la PR #1421, 15/11 06:19 UTC). Branche : `verifie-1511c`, à jour.
- **Commits lus.** `57b5549874` (ACNC74 : serveur, deux écrans, tests), `4353a5a243` (ACNC75), `c0e5862e55` (test RAS-TVA
  réaligné), `bdcf8be176` / `0ac08b1e7f` (spec `frontend/e2e/acceptation/acnc8.spec.js`), enregistrement
  `docs/audits/acceptation/ACNC/2026-11-15-0ac08b1e7.md` (PASS, `couvre: [ACNC70 … ACNC75]`).
- **CI de la PR #1421** (lue par `gh pr view 1421`) : backend-tests (8 tranches), frontend-vitest (4), e2e, api-fuzz, ci-gate :
  tous SUCCESS. Les tests n'ont pas été relancés ici.
- **Méthode.** Lecture du code de `5290db5dad` (deux portes serveur, service commun, deux écrans, tests, spec), grep de tous les
  créateurs de `PaiementFournisseur` et de tous les appels front qui en créent, sonde VER4-400 rejouée sur l'hôte (§5). Aucune
  pile, aucun Docker, aucune base, aucune production.

## 1. Vérificateur

1 orchestrateur-vérificateur frais (opus/high), lecture seule, en un seul passage (périmètre de deux tâches).

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **2** | ACNC74, ACNC75 |
| partiel / non-fait / faux / régression | 0 | — |

## 2. ACNC74 sur pièces

### 2.1 La garde

- **Un seul service.** `backend/django_core/apps/stock/services_verrous.py::refuser_reglement_identique` (20 l.). Appelée par
  les deux portes : `backend/django_core/apps/stock/views/facture_fournisseur.py::FactureFournisseurViewSet._ajouter_paiement`
  et `backend/django_core/apps/stock/views/paiement_fournisseur.py::PaiementFournisseurViewSet.perform_create` (grep : 2
  appelants, aucune seconde implémentation).
- **Sous le verrou : oui.** Dans les deux portes, l'appel suit `verrouiller_facture_fournisseur_et_verifier_solde`
  (`select_for_update` de la facture), dans le même `transaction.atomic()`, avant `serializer.save`. La requête
  `facture.paiements.filter(...)` est une instruction neuve prise après l'obtention du verrou : en READ COMMITTED elle voit le
  règlement que la requête concurrente vient de commiter. Deux envois simultanés sont donc sérialisés : le second relit et
  reçoit 409. Le refus lève avant tout `save` : rien d'écrit (transaction annulée).
- **« Identique ».** Même facture, même `montant`, même jour : `date_paiement` égale, ou, pour un règlement sans date, même jour
  de `date_creation` ; un envoi sans date vaut aujourd'hui (`timezone.localdate()`). Le mode n'entre pas en compte. Fenêtre = le
  jour calendaire, pas une durée glissante. Parité avec la porte client
  (`backend/django_core/apps/ventes/domain/encaissements.py::encaisser_sur_facture` : montant + date ; ses statuts non comptés
  n'ont pas d'équivalent fournisseur, `PaiementFournisseur` n'a pas de statut).
- **Confirmation explicite : passe.** `confirmer_doublon` vrai (`True`, `'true'`, `'1'`) saute la garde. Le 409 libère la clé
  d'idempotence (`backend/django_core/core/idempotency.py::IdempotentCreateMixin._avec_idempotence` : `_liberer` sur exception
  comme sur statut ≥ 400), donc « Confirmer » repart sous la même clé avec un corps différent sans 409 de clé.
- **Phrase.** `ConflitEtat({'detail': 'Un règlement de 3 000 MAD a déjà été enregistré aujourd'hui sur cette facture : confirmer ?', 'code': 'paiement_similaire'})`.

### 2.2 Autres chemins d'écriture d'un règlement fournisseur

| Chemin | Garde ? |
|---|---|
| Fiche facture (`factures-fournisseur/<id>/paiements/`) | oui |
| Registre (`stock/paiements-fournisseur/` et alias `achats/paiements-fournisseur/`, même viewset) | oui |
| Campagne de paiement `backend/django_core/apps/stock/services.py::enregistrer_paiement_fournisseur_depuis_run` | non, mais aucun appelant (grep hors définition : 0) |
| `add_paiement_sous_traitant` (même fichier) | non, seul appelant dans `backend/parked/` |
| Import, action de lot, commande de gestion, action d'assistant | aucun (grep `PaiementFournisseur.objects.create` : 2 occurrences, les deux ci-dessus ; `agent_actions.py` et `management/` : 0) |
| Front (`stockApi.ajouterPaiementFournisseur`, `stockApi.createPaiementFournisseur`) | 2 appels, les deux écrans ci-dessous |

### 2.3 Écrans

- **Fiche** `frontend/src/pages/stock/FacturesFournisseur.jsx::FactureDetail` : le 409 `paiement_similaire` affiche la phrase
  serveur et un bouton « Confirmer » (`ConfirmerDoublon`), sans bandeau d'échec ; « Confirmer » renvoie `confirmer_doublon: true`
  sous la même clé.
- **Registre** `frontend/src/pages/stock/PaiementsFournisseurLedgerPage.jsx::PaiementsFournisseurLedgerPage` : même composant,
  le toast d'échec n'est plus émis pour ce code.
- Rejeu en direct : spec `acnc8.spec.js`, deux étapes (fiche seule ; fiche puis registre), 409 + phrase + « Confirmer » affirmés,
  deux règlements après confirmation, PASS sur runner (`0ac08b1e7`).

### 2.4 Tests

- `backend/django_core/apps/stock/test_zacc9_paiement_fournisseur_ecriture.py::TestGardeSurPaiement::test_reglement_identique_demande_confirmation` :
  les deux portes, 201 puis 409 `paiement_similaire` (un règlement), puis 201 confirmé (deux, solde 4 000). **Un seul fil** :
  la course n'est pas jouée par deux connexions. Il échoue si la garde saute (2e envoi 201) et si `confirmer_doublon` est
  ignoré (3e envoi 409). Il ne détecte pas une garde déplacée avant le verrou ; la tenue sous course repose sur la lecture du
  §2.1 et sur l'emplacement fixé par la tâche. Le test à deux fils existant (`TestAUD208DeuxPaiementsConcurrentsNeDepassentPlusLeSolde`,
  70 + 70 sur 120) est refusé par le plafond, avant la garde : il ne la touche pas.
- Vitest : un cas par écran (phrase, « Confirmer », même clé). Trois tests réalignés sur des montants distincts ou une
  confirmation (`test_astk_perm_achats_payer`, `test_astk_ras_tva_acompte`) : intention gardée.

**Verdict ACNC74 : ok.** C-ACNC-VER4-400 fermé sur `origin/main` : une saisie retouchée, un délai dépassé, deux onglets ou fiche
+ registre ne créent plus un second règlement identique sans confirmation.

## 3. ACNC75 sur pièces

- `FactureDetail::ajouter`, branche `!err?.response` : la relecture `stockApi.getFactureFournisseur` est attendue (`await`)
  dans le `catch`, donc avant le `finally { setBusy(false) }` : le bouton reste « … » jusqu'à son retour.
- `total_paye` relu > celui d'avant ⇒ `setError(null)` et « Paiement de 3 000 MAD enregistré (réponse perdue, fiche relue). » ;
  sinon le bandeau d'échec reste.
- **La relecture échoue** : son `catch` remplace le bandeau par « Le paiement n'a pas pu être confirmé — rouvrez la facture. »,
  la copie locale est gardée, le bouton est rendu. Un reclic, saisie inchangée, part sous la même clé (rejeu ou 409 « en cours ») ;
  une saisie retouchée au même montant et au même jour tombe maintenant sur la garde d'ACNC74. Cas non couvert par un test
  (la tâche ne l'exigeait pas).
- Test : `FacturesFournisseur.test.jsx` › « réponse perdue : bouton occupé jusqu'à la relecture, plus de bandeau d'échec »
  (relecture tenue par une promesse non résolue, bouton absent pendant l'attente, message de succès, bandeau absent). Retirer
  l'`await` le fait échouer (lu, non lancé ici).

**Verdict ACNC75 : ok.** C-ACNC-VER4-401 fermé.

## 4. Régressions

- **ACNC72 non rouverte.** Remise de clé sur saisie changée inchangée (`useEffect` sur `[montant, datePaiement, mode]` à la fiche,
  sur `[draft]` au registre). Après un 409 `paiement_similaire` la clé est libérée côté serveur : ni « Confirmer » ni un reclic
  ne rendent de 409 de clé.
- **ACNC67 non cassée.** Le registre garde sa clé entre deux clics et relit après une réponse perdue (`charger()`) ; l'étape
  `acnc5.spec.js` ACNC67 rejoue sous la même clé (rendu mémorisé, servi avant la garde) et règle ensuite un autre montant.
- **ACNC73 non cassée.** La relecture de la fiche reste, désormais attendue.
- Specs `acnc6.spec.js` / `acnc7.spec.js` : montants distincts ou rejeu même clé (commit `57b5549874`), rejouées vertes dans
  l'enregistrement `0ac08b1e7`.

## 5. Sondes rejouées sur l'hôte (`5290db5dad`)

| Sonde | Sortie | Encore valable ? |
|---|---|---|
| `C-ACNC-VER4-400.py` | **plante** : `AttributeError` dans `_ecran` (la regex attend `const ajouter = async () =>`, la signature est devenue `async (confirmerDoublon = false) =>`) | **Périmée.** Rejouée par un lanceur jetable qui ne change que cette regex : `repro: false` ; la partie statique voit la garde dans `_ajouter_paiement` et `perform_create`, l'écran voit la relecture attendue. Sa partie serveur reste 201, 201 parce que le harnais de VER3-300 recopie l'ANCIEN geste (il n'appelle pas `refuser_reglement_identique`) : elle ne prouve plus rien. |

## 6. ACNC23 et VER2-203

- **ACNC23** : toujours `[BLOCKED: code livré dev-all (13/11/2026), preuve en direct due]` ; aucun enregistrement ACNC ne la
  couvre (grep `ACNC23` dans `docs/audits/acceptation/ACNC/` : 0). Plus aucun écart S1-S2 ouvert sur son geste : elle est
  cochable dès que sa preuve en direct est jouée.
- **C-ACNC-VER2-203 (S3)** : ouvert, inchangé ; `backend/django_core/apps/facturation/views/facture.py::FactureViewSet.perform_create`
  juge le BC par `refuser_portes_fermees` sur la copie validée, sans `transaction.atomic` ni `select_for_update` (dernier commit
  du fichier : `80667a967f`, ACNC5). `BonCommandeViewSet.annuler` (ACNC62) verrouille le BC mais peut lire « aucune facture »
  avant le commit d'une création concurrente. Le test `AnnulerBcConcurrenceTests::test_annuler_croise_creer_facture` simule la
  création en prenant le verrou lui-même, ce que le vrai chemin ne fait pas. La raison « fichier mur » ne tient pas
  (`facture.py` 348 l. ; le correctif va dans `facture_portes.py`, 55 l.). **Tâche déposée par cette passe** (proposée au
  propriétaire `facturation`, `docs/plans/PLAN_AUDIT_FACTURATION.md`) : ACNC76.

## 7. Écarts et tableau

**Aucun écart nouveau.**

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-ACNC-VER4-400 | ACNC73, ACNC4 (jumeau) | S2 | Second règlement fournisseur identique sans confirmation (`backend/django_core/apps/stock/services_verrous.py::refuser_reglement_identique`) | `docs/audits/sondes/ACNC/C-ACNC-VER4-400.py` (périmée ; rejouée corrigée : `repro: false`) | ACNC74, cochée : **fermé** |
| C-ACNC-VER4-401 | ACNC73 | S3 | Bandeau « a échoué » sous le règlement relu ; bouton rendu avant la relecture (`frontend/src/pages/stock/FacturesFournisseur.jsx::FactureDetail`) | STATIQUE | ACNC75, cochée : **fermé** |
| C-ACNC-VER2-203 | ACNC63 | S3 | Facture CRUD sur un BC sans devis, sans verrou, croisée avec « Annuler » (`backend/django_core/apps/facturation/views/facture.py::FactureViewSet.perform_create`) | STATIQUE | ACNC76 (déposée par cette passe) |

**Marqueur.** 0 écart S1-S2 nouveau ; tous les écarts S1-S2 des comptes rendus `vérifie` antérieurs ont leur tâche cochée
(VER2-100 → ACNC62, VER2-200 → ACNC70, VER2-201 → ACNC71, VER3-300 → ACNC73, VER4-400 → ACNC74). Hors compte, comme dans les
trois passes précédentes : ACNC7 et ACNC21 à 24, S2 du dossier d'origine, livrées et en attente de preuve en direct
(`[BLOCKED…]`).

**Optionnel (non déposé).**
- Sonde VER4-400 : regex de `_ecran` à mettre à jour ; partie serveur à rebrancher sur le vrai geste (ou à retirer).
- Test d'ACNC74 : un cas à deux connexions (deux `TransactionTestCase` en fil, corps identiques, clés différentes) fixerait la
  garde sous le verrou ; la lecture du §2.1 suffit aujourd'hui.
- Les deux écrans gardent la phrase et « Confirmer » affichés quand la saisie change ensuite : « Confirmer » envoie alors la
  NOUVELLE saisie avec `confirmer_doublon`. Effet seulement si la nouvelle saisie est elle-même un doublon d'un autre règlement.
- `confirmer_doublon` n'accepte pas `'True'` ni `'on'` (formulaires multipart) ; les écrans envoient `true` en JSON.

## 8. Rappel des passes précédentes du jour

- **1re passe (matin, `8fc408bf61`, PR #1415).** Contre-visite d'ACNC70, 71, 72 : ACNC70 (S1) et ACNC71 (S2) ok ; ACNC72
  régression sur son jumeau, la fiche facture fournisseur ⇒ écart S1 C-ACNC-VER3-300 (réponse perdue puis retouche ⇒ second
  règlement), sonde `repro: true`, tâche ACNC73. Sondes VER2-200 / VER2-201 notées à réécrire. Marqueur `pct: 98 | ecarts_s1_s2: 1`.
- **2e passe (après-midi, `d9164c12e2`, PR #1419).** ACNC73 partielle : relecture livrée à l'écran seulement ⇒ écart S2
  C-ACNC-VER4-400 (aucune garde serveur du règlement identique, sonde `repro: true`, tâche ACNC74) et S3 C-ACNC-VER4-401 (tâche
  ACNC75). Marqueur `pct: 98 | ecarts_s1_s2: 1`.
- **3e passe (celle-ci, `5290db5dad`, PR #1421).** ACNC74 et ACNC75 ok ; 0 S1-S2.

## 9. Couverture et sortie de cycle

- **Couvert.** ACNC74 et ACNC75 (code, tests, spec, enregistrement, CI de la PR) ; tous les créateurs de `PaiementFournisseur`
  hors tests ; les deux appels front ; les régressions ACNC67, 72, 73 ; la sonde VER4-400 ; ACNC23 ; VER2-203.
- **Non couvert sans pile.** Aucun test Django, vitest ni e2e relancé (verdicts de la CI #1421 et de l'enregistrement lus) ; la
  course à deux connexions sur la garde d'ACNC74 n'est établie que par lecture (verrou, READ COMMITTED), pas sur une vraie base ;
  aucun écran affiché dans un navigateur.
- **Sortie de cycle.** Premier `vérifie` à zéro S1-S2 : compteur **1 sur 2**. `audit_registre.py` lira ACNC « vérifié » (il ne
  lit que le dernier fichier), mais la règle METHODE §C.4.3 demande un second `vérifie` consécutif à zéro, à jouer sur un autre
  fichier daté (une nouvelle passe aujourd'hui remplacerait celle-ci). ACNC56 attend encore les preuves en direct d'ACNC7, 21-24,
  28, 29, 42 et 44.

## 10. Coût

H0 S0 O1 F0 · jetons sous-agents ≈ 0 M : 1 orchestrateur-vérificateur opus/high, sans sous-agent. Aucun appel Fable.
