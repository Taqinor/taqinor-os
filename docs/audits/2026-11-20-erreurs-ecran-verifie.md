<!-- verifie | groupe: AERR | pct: 99 | ecarts_s1_s2: 0 | faits: 170 -->
# Vérifie AERR — contre-visite des correctifs du parcours PF12 « erreurs, pertes de saisie et gestes dangereux à l'écran », 20/11/2026 (3e passe)

Commande `loop audit` (20/11, troisième passe du jour). La deuxième passe (même fichier, version de `decf0330b^` ; rappel
§5) avait ouvert 1 écart S2 et 3 tâches (AERR187 à 189) ; une autre session les a construites et cochées (PR #1506,
acceptation en direct run 44733207204, 4/4 PASS). `audit_registre.py --du` redemande la contre-visite (170 tâches cochées
sur 171, « écarts S1-S2 du 2026-11-20 tous cochés »). Rien n'a été construit ni déployé ; aucune base, aucun conteneur,
aucune production n'a été lu.

## 0. Préconditions

- **SHA.** `origin/main` = `decf0330b` (PR #1506). Branche de claim : `verifie-aerr-2011c`.
- **Registre.** PF12 `erreurs-ecran`, groupe AERR, 170 tâches cochées sur 171. Reste ouverte la tâche d'acceptation AERR131.
- **Échantillon : les 3 tâches d'écart de la deuxième passe** (METHODE §C.4-6) : AERR187, AERR188 (S2), AERR189 (S3).
- **Méthode.** Un vérificateur frais (opus / high, même répertoire) : commits, code servi, corps des tests nommés, spec et
  enregistrement d'acceptation (`frontend/e2e/acceptation/aerr16.spec.js`, SHA d'essai `66a28e594` :
  `git diff 66a28e594 origin/main -- frontend/src` vide), effets de bord des deux correctifs trouvés au rejeu
  (`7bf83b30b`, `f9a0987fc`) ; sondes rejouées, une sonde neuve. `frontend/node_modules` absent : aucun vitest lancé.

## 1. Verdicts

| Tâche | Verdict | Commit | Test nommé (casse si on revient en arrière) | L'acceptation affirme la clause |
|---|---|---|---|---|
| AERR187 | ok | `51bea8b8f` | `ProduitForm.test.jsx` (2 cas), `ReceptionsFournisseur.series.test.jsx` (3 cas) : « Rester » garde la valeur sans `onClose`, « Quitter » ferme une fois (oui) | oui : sans saisie, fermeture directe ; avec saisie, demande, « Rester » garde, « Quitter » ferme ; aucune écriture réseau ; base relue sans création |
| AERR188 | ok | `27f9628a2` | `FactureForm.erreursLignes.test.jsx` (3 cas) (oui) | oui : même scénario, nombre de factures inchangé en base |
| AERR189 | ok | `c5b04ec96`, `7bf83b30b` | `LeadsPagePlanifierRelance.test.mjs` (lecture du source, rouge sur `c5b04ec96^`) ; `KanbanView.test.jsx` couvre le retour de focus du menu (oui) | en grande partie : date et objet gardés sur A après fermeture et réouverture, aucune écriture, relance de A nulle en base ; B vide ; enregistrement : toast, fermeture, relance posée en base (deux écarts de geste, §4) |

**AERR189, effets de bord vérifiés.**
- `f9a0987fc` ne touche que la spec d'acceptation (requête sur la marque commune) : aucun code applicatif, aucune carte du
  kanban masquée ou montrée autrement.
- Données périmées : aucune ; chaque réouverture passe par le lead frais de la liste, la saisie est gardée pour le même id,
  `key={relanceLead.id}` remonte une fenêtre vide pour un autre lead.
- Double envoi : aucun (`busy` désactive le bouton ; au succès `reset()`, fermeture, `onLogged`).
- Succès faux du 14/11 (VER2-200) : impossible ici, le mode planification n'appelle jamais `logInteraction`.
- Correctif du rejeu (`frontend/src/pages/crm/leads/views/LeadCard.jsx`, `onCloseAutoFocus` empêché sous `relanceChoisie`,
  posé par le seul item « Planifier une relance ») : le focus reste dans la fenêtre ; les autres items gardent le retour de
  focus ; la vue prévision réutilise `LeadCard`.

**Écart S2 d'origine (C-AERR-VER4-401) : fermé.** Les trois « Annuler » passent par `confirmLeaveIfDirty(dirty)`, le même
booléen que leur `<Dialog>` ; la sonde de balayage VER4-400 ne trouve plus aucune sortie nue.

## 2. Sondes

| Sonde | Verdict | Observé (hôte, `decf0330b`) |
|---|---|---|
| `C-AERR-VER4-400.py` (2e passe) | réfutée | `repro: false` : 11 composants à garde de saisie, `sorties_nues` et `onOpenChange_nus` vides ; reste le seul booléen différent connu (`ToitureDesign.jsx::AtelierToiture`, juste, ACAL85) |
| `C-AERR-VER2-200.py` (14/11) | réfutée | `repro: false` (toujours fragile) |
| `C-AERR-VER5-500.py` (neuve) | réfutée | `repro: false`, 12 contrôles vrais (montage gardé, `open` piloté par un état, `onOpenChange` ne démonte plus, `onLogged` ferme et relit, drapeau du menu posé en un seul lieu, remise à zéro de la fenêtre d'appel seulement après journalisation ou changement de lead) ; les contrôles de la liste échouent sur `c5b04ec96^` : la sonde attrape un retour en arrière |

## 3. Écarts retenus

Aucun. Le « Fermer » de la vue détail d'une réception (`frontend/src/pages/stock/ReceptionsFournisseur.jsx::ReceptionDetail`)
n'est pas gardé, mais elle ne tient aucun brouillon libre que le contrat de `frontend/src/ui/useDirtyGuard.js` demande de
confirmer ; AERR187 l'avait déjà écarté comme autre geste.

## 4. Optionnel (non déposé)

- AERR189 : le rejeu ferme par Échap quand la clause nomme un clic extérieur ; les deux passent par `onOpenChange(false)`
  et `ui/Popover.jsx` ne personnalise aucun des deux : même comportement, geste exact non rejoué.
- AERR189 : la spec affirme une relance non nulle, pas égale à la date choisie (« Demain »).
- AERR189 : le test de la liste lit le source ; la survie des valeurs à la réouverture n'est couverte que par les tests
  d'AERR186 et le rejeu en direct.
- Après Échap, le focus revient sur `body` (déclencheur `aria-hidden`) : accessibilité, antérieur à AERR189.

## 5. Rappel des passes précédentes du jour

| Passe | SHA | Échantillon | Écarts retenus | État ce soir |
|---|---|---|---|---|
| 1re | `a923179a4` | 14 tâches d'écart du 14/11 (12 ok, AERR159 et AERR160 partielles) | C-AERR-VER3-300 (S2) → AERR181-183 ; C-AERR-VER3-301 (S2) → AERR184 ; C-AERR-VER3-302 (S3) → AERR185 ; C-AERR-VER3-303 (S3) → AERR186 | tous fermés (2e passe) |
| 2e | `5a77c93d9` | AERR181 à 186 (toutes ok) | C-AERR-VER4-401 (S2) → AERR187, AERR188 ; C-AERR-VER4-402 (S3) → AERR189 | tous fermés (cette passe) |

## 6. Couverture et sortie de cycle

- **Couvert.** Les 3 tâches d'écart de la deuxième passe : commits, code servi, tests nommés, spec et enregistrement
  d'acceptation, effets de bord des correctifs du rejeu ; balayage de tous les composants à garde de saisie ; sondes rejouées.
- **Non couvert.** Aucun vitest, aucun rejeu navigateur ; l'acceptation AERR131 reste ouverte.
- **Sortie de cycle.** Aucun écart S1-S2 ouvert ni nouveau. Compteur des `vérifie` consécutifs à zéro S1-S2 : **1**. Il en
  faut un second pour sortir du cycle.

## 7. Coût

H0 S0 O3 F0 · jetons sous-agents ≈ 0,62 M sur la journée (trois vérificateurs opus, un par passe). Aucun appel Fable : aucun S1.
