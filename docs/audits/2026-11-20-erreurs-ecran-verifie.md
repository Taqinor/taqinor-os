<!-- verifie | groupe: AERR | pct: 99 | ecarts_s1_s2: 2 | faits: 161 -->
# Vérifie AERR — contre-visite des correctifs du parcours PF12 « erreurs, pertes de saisie et gestes dangereux à l'écran », 20/11/2026

Commande `loop audit` (20/11). La contre-visite de clôture du 14/11 (`docs/audits/2026-11-14-erreurs-ecran-verifie.md`)
avait ouvert 5 écarts S2 et 15 tâches S3, toutes cochées depuis : `audit_registre.py --du` la déclare due (161 tâches
cochées sur 162 constructibles, « écarts S1-S2 du 2026-11-14 tous cochés »). Rien n'a été construit ni déployé ; aucune
base, aucun conteneur, aucune production n'a été lu.

## 0. Préconditions

- **SHA.** `origin/main` = `a923179a4` (PR #1496). Branche de claim : `verifie-aerr-2011`.
- **Registre.** PF12 `erreurs-ecran`, groupe AERR, 161 tâches cochées sur 162. Reste ouverte la tâche d'acceptation AERR131.
- **Échantillon : 14 tâches d'écart du 14/11** (METHODE §C.4-6, S2 d'abord, 14 au plus) : S2 AERR156, ACNC71 (porte
  VER2-201, plan facturation), AERR158, AERR159, AERR160 ; S3 AERR161, AERR164 et AERR167 (anciennes régressions),
  AERR165, AERR166, AERR170, AERR171, AERR172, AERR173. Hors échantillon : AERR162, 163, 168, 169 (S3) ; AERR174 à 180,
  déposées après le 14/11 par d'autres vagues, toutes cochées (statut relevé, non vérifiées).
- **Méthode.** Un vérificateur frais (opus / high, même répertoire) : commits, code servi, corps des tests nommés,
  enregistrements d'acceptation, jumeaux par grep ; sondes du 14/11 rejouées, deux sondes neuves. `frontend/node_modules`
  absent : aucun vitest lancé, verdicts sur lecture.

## 1. Verdicts

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **12** | ACNC71, AERR156, 158, 161, 164, 165, 166, 167, 170, 171, 172, 173 |
| partiel | **2** | AERR159 (panneau étroit oublié), AERR160 (jumeaux oubliés) |
| non-fait / faux / régression / déjà-présent | **0** | — |

| Tâche | Commit | Test nommé (casse si on revient en arrière) |
|---|---|---|
| AERR156 | `88c80c964` | `CallLogPopover.test.jsx` › AERR156, 2 cas (oui) |
| ACNC71 | `706e63f39` | `NoteDebitDialog.test.jsx` « réponse perdue sur A… clé neuve » (oui, compare les deux clés) |
| AERR158 | `18d1ab07e` | `valeursTapees.test.jsx` AERR158 (oui pour E-mail ; Monitoring et Clients sans test) |
| AERR159 | `e53e778f2` | `TicketDetailSplitView.test.jsx` AERR159 (note seule, lit `isAnyFormDirty()`, ne clique pas le ticket B) |
| AERR160 | `f0e5754b8` | recette pompage et `TicketDetailSplitView.test.jsx` AERR160 (oui) |
| AERR161 | `51ef6d2ef` | `wir183.test.jsx`, 3 cas dont « Indicateurs pas à jour » (oui) |
| AERR164 | `9e5cad70a` | `LotsEtBoq.test.jsx` (`Lot A{Enter}{Enter}`) (oui) |
| AERR165 | `feec657aa` | `ControleSuiviPanel.test.jsx` AERR165 (oui) |
| AERR166 | `cbed8900a` | `LeadWorkspace.test.jsx`, 3 cas (mutants déclarés au commit ; corps non relu) |
| AERR167 | `b4023cd10` | `mutateWithUndo.test.jsx` AERR167, cas AERR136 réaligné (oui) |
| AERR170 | `864f22e4f` | `TicketsPage.test.jsx`, 2 cas (oui) |
| AERR171 | `453de38c4` | `appro.test.jsx` AERR171 (oui) — latent, comme au 14/11 |
| AERR172 | `3509492ce` | `cht8.test.jsx` AERR172 (probablement ; corps parcouru) |
| AERR173 | `a1802a85b` | `RetentionPage` et `ApprobationPage` AERR173 (probablement ; corps non relu) |

Acceptation : `docs/audits/acceptation/AERR/2026-11-15-5a349379e.md` (PASS, `couvre:` 156, 158 à 167, 169, 170, 172, 173) ;
ACNC71 a son propre enregistrement PASS (groupe ACNC). AERR159 n'a été rejouée qu'en largeur bureau : le panneau étroit
n'a jamais été joué (L7).

**Les cinq écarts S2 du 14/11, sur `origin/main` :**
- C-AERR-VER2-200 (AERR156) : **fermé.** `frontend/src/features/crm/CallLogPopover.jsx::CallLogPopover` rappelle `reset()`
  (drapeau compris) à la fermeture et au changement de lead.
- C-AERR-VER2-201 (ACNC71) : **fermé.** `frontend/src/pages/ventes/NoteDebitDialog.jsx::NoteDebitDialog` prend une clé
  neuve, un motif et un montant vides à chaque ouverture ou changement de facture.
- C-AERR-VER2-202 (AERR158) : **fermé.** `frontend/src/pages/parametres/ParametresEntreprise.jsx::ParametresEntreprise` garde
  E-mail, Monitoring et Clients montés (`SectionGardee`).
- C-AERR-VER2-203 (AERR159) : **partiellement.** Changer de ticket, J/K et « Fermer » demandent ; le `<Sheet>` du mode
  étroit perd encore les brouillons (C-AERR-VER3-301).
- C-AERR-VER2-204 (AERR160) : **fermé pour ses deux sites** ; le même défaut reste ouvert sur trois composants frères
  (C-AERR-VER3-300).

## 2. Sondes

| Sonde | Tâche | Verdict | Observé (hôte, `a923179a4`) |
|---|---|---|---|
| `C-AERR-VER2-200.py` (14/11) | AERR156 | réfutée | `repro: false` (fragile : le motif `.current = false` a disparu) |
| `C-AERR-VER2-201.py` (14/11) | ACNC71 | réfutée | `repro: false` |
| `C-AERR-VER2-202.py` (14/11) | AERR158 | réfutée | `repro: false` |
| `C-AERR-VER2-203.py` (14/11) | AERR159 | **périmée** | `repro: true` faux positif : elle lit le `useMemo` `dirty`, le correctif a mis les brouillons dans l'argument de `useDirtyGuard` ; le vrai reste est VER3-301 |
| `C-AERR-VER2-204.py` (14/11) | AERR160 | réfutée | `repro: false` (fragile : la garde s'écrit désormais avec `.then`) |
| `C-AERR-VER3-300.py` (neuve) | AERR160 (jumeaux) | **REPRO** | « Fermer » `onClick={onClose}` dans un composant à `useDirtyGuard` : `InstallationDetail`, `EquipementDetailCorps`, `BcfDetail` ; les deux sites corrigés ne sortent pas (témoin négatif) |
| `C-AERR-VER3-301.py` (neuve) | AERR159 (jumeau) | **REPRO** | `useDirtyGuard` cite `noteBody`, `dirty` non ; le `<Sheet>` ferme par `confirmLeaveIfDirty(dirty)` |

## 3. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-AERR-VER3-300 | AERR160 (jumeaux) | **S2** | Trois fiches enregistrent `useDirtyGuard` et gardent Échap et le clic extérieur, mais leur bouton « Fermer » est `onClick={onClose}` : une fiche modifiée se ferme sans demande (`frontend/src/pages/installations/InstallationDetail.jsx::InstallationDetail`, `frontend/src/pages/sav/EquipementsPage.jsx::EquipementDetailCorps`, `frontend/src/pages/stock/BonsCommandeFournisseur.jsx::BcfDetail`) | `C-AERR-VER3-300.py` (REPRO) | AERR181 (chantiers), AERR182 (SAV), AERR183 (stock) |
| C-AERR-VER3-301 | AERR159 (jumeau) | **S2** | Sous 1 280 px, le `<Sheet>` de la fiche ticket ferme par `confirmLeaveIfDirty(dirty)` : note, compte rendu, pièce, retrait et motif tapés perdus sans demande sur Échap, la croix ou le fond (`frontend/src/pages/sav/TicketsPage.jsx::TicketDetailCorps`) | `C-AERR-VER3-301.py` (REPRO) | AERR184 (SAV) |
| C-AERR-VER3-302 | AERR173 (jumeaux) | S3 | « Révoquer » un partage GED et retirer une entrée de droits partent d'un clic (`frontend/src/features/ged/advanced/RetentionPage.jsx::RetentionPage`, `frontend/src/features/ged/GedDocumentInsights.jsx::GedDocumentInsights`) | STATIQUE | AERR185 (documents) |
| C-AERR-VER3-303 | AERR156 (effet de bord) | S3 | Une fermeture accidentelle de la fenêtre d'appel (clic extérieur, Échap) efface l'issue, la note et la date avant toute journalisation (`frontend/src/features/crm/CallLogPopover.jsx::CallLogPopover`) | STATIQUE | AERR186 (lead) |

**Pourquoi ces gravités.**
- **VER3-300, VER3-301 (S2).** Même grille que les écarts VER2-202 à 204 du 14/11 : une perte de saisie réelle, sans
  avertissement, sur un geste ordinaire (« Fermer », Échap sur un téléphone ou un portable étroit). Les fiches enregistrent
  déjà leur garde : seul le geste nommé y échappe.
- **VER3-302 (S3).** Retrait irréversible mais rare (gouvernance GED, Directeur), même famille qu'AERR173.
- **VER3-303 (S3).** La remise à zéro a été demandée par AERR156 contre un succès faux ; elle efface trop large. Perte
  légère (une issue et une note), refaite en quelques secondes.
- **Pas de S1.**

**Routage.** `check_ownership.py --owner-of` : chantiers AERR181 ; SAV AERR182, AERR184 ; stock AERR183 ; documents
AERR185 ; lead AERR186. VER3-300 est scindé par propriétaire (trois correctifs indépendants, un par fiche).

## 4. Optionnel (non déposé)

- `NoteDebitDialog` : `erreur` n'est pas effacée à l'ouverture ou au changement de facture (le texte d'erreur de A
  s'affiche sous B) ; cosmétique.
- Sondes du 14/11 : VER2-203 périmée (faux positif), VER2-200 et VER2-204 fragiles (elles cherchent l'absence de l'ancien
  motif) ; à faire détecter le correctif lui-même.
- `frontend/src/features/ged/GedSearch.jsx` : la suppression d'une vue enregistrée part d'un clic (objet personnel).
- `TicketDetailCorps` : un motif tapé dans « Annuler ce ticket ? » puis abandonné garde la fiche « modifiée ».
- Tests plus étroits que le texte : AERR158 (Monitoring et Clients sans test), AERR159 (la note seule, jamais le clic).

## 5. Couverture et sortie de cycle

- **Couvert.** 14 tâches d'écart du 14/11 : commits, code servi, tests nommés, enregistrements d'acceptation, jumeaux par
  grep ; 5 sondes du 14/11 rejouées, 2 neuves.
- **Non couvert.** Aucun vitest lancé (`node_modules` absent), aucun rejeu navigateur ; AERR162, 163, 168, 169 ; AERR174
  à 180 ; l'acceptation AERR131 reste ouverte.
- **Sortie de cycle.** Quatre écarts S2 du 14/11 fermés, un partiellement ; deux écarts S2 nouveaux (AERR181 à 184, sur
  le même défaut que VER2-203 et VER2-204). Le groupe reste « construit » ; compteur des `vérifie` consécutifs à zéro
  S1-S2 : **0**. Contre-visite d'AERR181 à 184 une fois cochées.

## 6. Coût

H0 S0 O1 F0 · jetons sous-agents ≈ 0,23 M (un vérificateur opus seul). Aucun appel Fable : aucun S1.
