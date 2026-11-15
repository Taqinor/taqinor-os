<!-- verifie | groupe: ACNC | pct: 98 | ecarts_s1_s2: 1 -->
# Vérifie ACNC — contre-visite d'ACNC73 (3e passe ACNC, 2e du 15/11), parcours PF9 « gestes rejoués et courses », 15/11/2026

Le registre annonce « ACNC (PF9 rejeu-concurrence) : 98 % cochées (55/56) — vérifie dû, contre-visite des correctifs (écarts
S1-S2 du 2026-11-15 tous cochés) » (`audit_registre.py --du`, garde d'acceptation neutralisée, relu dans cette passe).
Contre-visite étroite (METHODE §C.4.6) : la seule tâche d'écart déposée ce matin, ACNC73 (C-ACNC-VER3-300, S1), ce qu'elle a
pu casser (ACNC67, ACNC72), la sonde VER3-300, ACNC23 et le S3 VER2-203. Rien n'a été construit, déployé ni coché. Ce compte
rendu remplace celui du matin (§C.4.5 f) ; la passe du matin est résumée en §8.

## 0. Préconditions

- **SHA.** `origin/main` = `d9164c12e2` (merge de la PR #1419). Branche : `verifie-1511b`, à jour.
- **Commits lus.** `a7bc1291ec` (ACNC73, code + vitest), `0d6d14351d` / `c3820441e6` (spec `frontend/e2e/acceptation/acnc7.spec.js`),
  `4452ed31d6` (enregistrement `docs/audits/acceptation/ACNC/2026-11-15-c3820441e.md`, PASS, `couvre: [ACNC73]`).
- **Méthode.** Lecture du code de `d9164c12e2` (écran ET serveur des deux portes de règlement fournisseur), greps des créateurs
  de `PaiementFournisseur`, des tests et des specs qui règlent une facture fournisseur, deux sondes hôte jouées (§4). Aucune
  pile, aucun test Django ni vitest lancé, aucun Docker, aucune base, aucune production.

## 1. Vérificateur

1 orchestrateur-vérificateur frais (opus/high), lecture seule, en un seul passage (périmètre d'une tâche).

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | 0 | — |
| partiel | **1** | ACNC73 : tenu sur le chemin spécifié ; la clause « une saisie retouchée ne crée plus un second règlement à l'insu de l'utilisateur » ne tient pas sur trois chemins voisins, faute de garde serveur (§3.1) |
| non-fait / faux / régression | **0** | — |

## 2. ACNC73 sur pièces

### 2.1 Ce qui est livré

- `frontend/src/pages/stock/FacturesFournisseur.jsx::FactureDetail`, branche `!err?.response` d'`ajouter` : `onSaved?.()`
  (liste) puis `stockApi.getFactureFournisseur(facture.id).then((r) => setFacture(r.data))`, avec en cas d'échec de la
  relecture « Le paiement n'a pas pu être confirmé — rouvrez la facture. ». La remise de clé ACNC72
  (`useEffect` sur `[montant, datePaiement, mode]`) est inchangée. +4 lignes nettes, conforme au « Code net ».
- **Serveur : rien.** Les deux portes, `apps/stock/views/facture_fournisseur.py::FactureFournisseurViewSet._ajouter_paiement`
  (suffixe d'idempotence `paiements.<pk>`) et `apps/stock/views/paiement_fournisseur.py::PaiementFournisseurViewSet.perform_create`
  (registre, autre espace de clés), ne refusent sous verrou que l'excédent du solde
  (`apps/stock/services.py::verrouiller_facture_fournisseur_et_verifier_solde`). Aucun contrôle du paiement identique
  (grep `confirmer_doublon|paiement_similaire` dans `apps/stock` : 0). La protection d'ACNC73 est **à l'écran seulement**.

### 2.2 Chemin par chemin

| Chemin | Résultat sur `d9164c12e2` |
|---|---|
| Réponse perdue APRÈS commit, puis retouche de date / mode / montant | Sûr si la relecture revient : la fiche montre le règlement et le solde relu (vitest + rejeu PASS). La retouche crée encore un second règlement, mais visible. Le bandeau « L'enregistrement du paiement a échoué. » reste affiché à côté (§3.2). |
| Délai de 20 s dépassé (`frontend/src/api/axios.js`, toast « … réessayez ») pendant que le POST est encore en vol | **Non sûr.** La relecture part aussitôt, non attendue, et lit la facture AVANT le commit : « Aucun paiement », solde 10 000, sans erreur. Une retouche part sous une clé neuve ; le serveur attend le verrou, puis accepte (3 000 ≤ 7 000). |
| Relecture elle-même en échec (réseau toujours coupé) | Copie périmée gardée, avec le message « … n'a pas pu être confirmé — rouvrez la facture. ». Une retouche crée un second règlement. |
| Double clic | Sûr : bouton `loading`, et clé posée avant l'`await` (même clé, rejeu ou 409 en vol). |
| Deux onglets, ou fiche + registre, sur la même facture | **Non sûr** : deux clés, deux espaces de clés ; aucun contrôle serveur ; second règlement silencieux (jumeau exact de D-ACNC-1). |
| Registre (`PaiementsFournisseurLedgerPage.jsx`) | Inchangé depuis ACNC72 (`git log` : dernier commit `b4f94e3386`) : `charger()` relit la ligne ; ACNC67 n'est pas cassée. |
| Règlement groupé (campagne de paiement) | `apps/stock/services.py::enregistrer_paiement_fournisseur_depuis_run` ni verrou ni plafond, mais **aucun appelant** (grep `depuis_run` : 1 définition ; `apps/compta` en coquille). Idem `add_paiement_sous_traitant` (seul appelant : `backend/parked/compta`). Optionnel. |
| Reprise après rechargement | Sûr : `openFacture` relit la facture ; un nouveau règlement est alors un geste voulu, sur une fiche juste. |

### 2.3 Test et régressions

- **Test livré.** `FacturesFournisseur.test.jsx` › « réponse perdue : la fiche relit la facture et montre le règlement » : le POST
  rejette `Network Error`, il attend `getFactureFournisseur(7)`, la disparition de « Aucun paiement. », « Déjà payé » 3 000 et
  « Solde dû » 7 000. Retirer la relecture le fait échouer (lu, non lancé ici). Il ne joue ni la retouche, ni la relecture en
  échec, ni la relecture lente.
- **Spec d'acceptation** `acnc7.spec.js` : relecture GET 200 affirmée, règlement et solde 7 000 affirmés avant le second clic,
  réessai sous la MÊME clé ⇒ un règlement, persistance à la réouverture et au rechargement. Elle ne joue pas la retouche (le
  cœur de VER3-300) et note le bandeau sans l'affirmer.
- **ACNC72 non rouverte.** La remise de clé sur saisie changée reste : aucun 409 de clé répété. **ACNC67 non cassée** : fichier
  du registre intouché.

## 3. Écarts nouveaux

### 3.1 C-ACNC-VER4-400 (S2) — règlement fournisseur identique : aucune garde serveur, la seule barrière est l'écran

**Mécanisme.** Côté client, D-ACNC-1 (réponse `accepter_apres_confirmation`) est appliquée par
`apps/ventes/domain/encaissements.py::encaisser_sur_facture` : même montant + même date ⇒ 409 `paiement_similaire` sans
`confirmer_doublon`. ACNC4 ne visait que le client (« Jumeaux : corps identiques 1 → traité ici »). Les deux portes
fournisseur n'ont pas ce contrôle. Dès que l'écran n'a pas montré le premier règlement — POST en vol au-delà de 20 s,
relecture en échec, deux onglets, fiche + registre — un second règlement identique passe en silence.

**Sonde.** `docs/audits/sondes/ACNC/C-ACNC-VER4-400.py`, jouée sur `d9164c12e2` : `repro: true`.
- Rejeu serveur par le harnais de VER3-300 (vrais `IdempotentCreateMixin`, `_reserver`, `_fingerprint`, `_liberer`,
  `verrouiller_facture_fournisseur_et_verifier_solde`, extraits par ast) : deux corps identiques de 3 000 sous deux clés ⇒
  201, 201, deux règlements, solde 4 000 ; date nulle puis date remplie (relecture lue avant le commit) ⇒ idem.
- Lecture statique : les trois méthodes des portes fournisseur sans garde ; la porte client avec garde.
- Écran : relecture présente mais non attendue (`await` absent), bouton rendu dans `finally`.
- Contrôle : même clé, même corps ⇒ rejeu, un règlement.

**Gravité S2** : même mécanisme et même gravité que C-ACNC-001 (S2), le jumeau client. Le chemin S1 du matin (réponse perdue
après commit) est fermé ; restent des chemins à déclencheur plus rare ou humain. Argent faux si atteint (solde dû sous-évalué).

**Correctif.** Jumeau fournisseur de D-ACNC-1 sous le verrou de la facture, après le plafond, sur les deux portes ; « Confirmer »
à l'écran. La relecture d'ACNC73 reste. **Tâche :** ACNC74, à déposer (`docs/plans/PLAN_AUDIT_STOCK.md`, propriétaire `stock`).

### 3.2 C-ACNC-VER4-401 (S3) — la fiche dit « échoué » d'un règlement passé, et rend le bouton avant la relecture

`FactureDetail::ajouter` : `setError("L'enregistrement du paiement a échoué.")` n'est jamais remplacé quand la relecture montre
le règlement ; `setBusy(false)` en `finally` précède le retour de la relecture. Effet consigné par l'enregistrement
`2026-11-15-c3820441e.md` (« le bandeau … reste affiché à côté du règlement relu »). Contournement : le règlement et le solde
sont visibles. STATIQUE. **Tâche :** ACNC75, à déposer (`@after: ACNC74`, même fichier). Le champ Montant est gardé à dessein :
le vider remettrait la clé à zéro (ACNC72) et un reclic créerait un second règlement.

## 4. Sondes rejouées sur l'hôte (`d9164c12e2`)

| Sonde | Sortie | Encore valable ? |
|---|---|---|
| `C-ACNC-VER3-300.py` | `repro: false` ; `sans_reponse_relit_la_fiche: true` ; partie serveur toujours 201, 201, solde 4 000 | **Valable, avec une limite.** Le détecteur d'écran voit la relecture (motif `getFactureFournisseur` dans la branche) et bascule à `false` comme attendu ; il ne vérifie ni l'`await`, ni l'échec de la relecture. Sa partie serveur, inchangée, montre que le serveur ne protège rien (§3.1). Libellé `copie_locale_jamais_resynchronisee: true` devenu trompeur (seul `factureProp` est compté). |
| `C-ACNC-VER4-400.py` (neuve) | `repro: true` | §3.1. Doit passer à `false` quand la garde serveur existe sur les deux portes. |

## 5. ACNC23 et VER2-203

- **ACNC23** : toujours `[BLOCKED: code livré dev-all (13/11/2026), preuve en direct due]` ; aucun enregistrement ACNC ne la
  couvre (grep `ACNC23` dans `docs/audits/acceptation/ACNC/` : 0) ; non cochable tant que VER4-400 touche son geste (§C.4.7 c).
- **VER2-203 (S3, n° 203 d'hier)** : ouvert, inchangé ; `apps/facturation/views/facture.py::FactureViewSet.perform_create`
  sans `transaction.atomic` ni BC relu `select_for_update` (aucun commit sur ce fichier depuis `8fc408bf61`) ; toujours sans tâche.

## 6. Optionnel (non déposé)

- **Sonde VER3-300** : renforcer son détecteur d'écran (exiger l'`await`, jouer la relecture en échec).
- **Campagne de paiement** : `enregistrer_paiement_fournisseur_depuis_run` sans verrou ni plafond, à reprendre si `compta`
  sort de la coquille.
- **Registre** : même patron que §3.2 (toast « a échoué », `charger()` non attendu), atténué : le toast s'efface et la ligne
  relue est visible.
- **D-ACNC-1** : sa question vise « une facture » sans préciser client ou fournisseur ; ACNC74 l'applique au fournisseur par
  lecture. Si le fondateur la veut client seule, ACNC74 devient une décision.

## 7. Tableau des écarts

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-ACNC-VER4-400 | ACNC73, ACNC4 (jumeau) | S2 | Second règlement fournisseur identique accepté sans confirmation sur les deux portes (`backend/django_core/apps/stock/views/facture_fournisseur.py::FactureFournisseurViewSet._ajouter_paiement`, `backend/django_core/apps/stock/views/paiement_fournisseur.py::PaiementFournisseurViewSet.perform_create`) | `docs/audits/sondes/ACNC/C-ACNC-VER4-400.py` (`repro: true`) | ACNC74 (à déposer) |
| C-ACNC-VER4-401 | ACNC73 | S3 | Bandeau « a échoué » sous le règlement relu ; bouton rendu avant la relecture (`frontend/src/pages/stock/FacturesFournisseur.jsx::FactureDetail`) | STATIQUE | ACNC75 (à déposer) |
| C-ACNC-VER3-300 | ACNC72, ACNC23 | S1 | Réponse perdue, fiche non relue, retouche ⇒ second règlement | `docs/audits/sondes/ACNC/C-ACNC-VER3-300.py` (`repro: false`) | ACNC73, cochée : **fermé sur son chemin** |
| C-ACNC-VER2-203 | ACNC63 | S3 | Création CRUD d'une facture sur un BC sans devis, sans verrou (`backend/django_core/apps/facturation/views/facture.py::FactureViewSet.perform_create`) | STATIQUE | sans tâche |

**Marqueur.** 1 écart S1-S2 nouveau (VER4-400). VER3-300 a sa tâche cochée : hors compte. Hors compte aussi, comme ce matin :
ACNC7 et ACNC21 à 24, S2 d'origine, livrées et en attente de preuve en direct.

## 8. Rappel de la passe du matin (sur `8fc408bf61`, PR #1415)

- Contre-visite d'ACNC70, 71, 72 : ACNC70 (S1) et ACNC71 (S2) ok ; ACNC72 régression sur son jumeau, la fiche facture
  fournisseur.
- Écart S1 C-ACNC-VER3-300 (réponse perdue puis retouche ⇒ second règlement), sonde `repro: true` ⇒ tâche ACNC73, livrée et
  cochée l'après-midi (PR #1419, rejeu PASS `c3820441e`).
- Sondes VER2-200 (partie réelle `repro: false`, contrôle périmé) et VER2-201 (faux positif) à réécrire pour ACNC56.
- VER2-203 laissé sans tâche ; la raison « fichier mur » avait été infirmée (349 l.).
- Marqueur du matin : `pct: 98 | ecarts_s1_s2: 1`.

## 9. Couverture et sortie de cycle

- **Couvert.** ACNC73 (code, test, spec, enregistrement) ; les deux portes serveur de règlement fournisseur ; tous les
  créateurs de `PaiementFournisseur` hors tests ; les specs et tests qui règlent une facture fournisseur deux fois ; deux sondes.
- **Non couvert sans pile.** Aucun test Django, vitest ni e2e lancé ; la course « POST en vol au-delà de 20 s » n'est établie que
  par lecture (relecture non attendue, READ COMMITTED, verrou de facture) et par le rejeu en mémoire, pas sur une vraie base ;
  la fiche n'a pas été affichée dans un navigateur.
- **Sortie de cycle.** Un écart S2 nouveau : le groupe reste « construit ». Le compteur (deux `vérifie` consécutifs à zéro
  S1-S2) reste à **0**. Une contre-visite sera due quand ACNC74 sera
  cochée ; ACNC56 attend aussi les sondes S2 réécrites et les preuves en direct d'ACNC7, 21-24, 28, 29, 42 et 44.

## 10. Coût

H0 S0 O1 F0 : 1 orchestrateur-vérificateur opus/high, sans sous-agent. Jetons des sous-agents ≈ 0 M. Aucun appel Fable.
