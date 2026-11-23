# Complément du lot A (tour 2) aux classes du tour 1 encore violées

Les fiches du tour 1 (`T1/classes/K-*.md`) sont COMPLÉTÉES ici (endroits et matrice), jamais dupliquées. Preuves : constats
`registre/constats/T2-F2-TOIT-a.jsonl`, `T2-F2-TOIT-b.jsonl`, `T2-F2-GESTES.jsonl`, `T2-F2-GESTES-b.jsonl` ; décisions
`registre/evenements/T2-consolidation-A.jsonl`.

## K-GESTE — encore violée (6 endroits de plus)
| Endroit neuf | Constat | Tâche |
|---|---|---|
| `layoutEditor.ts::pushWorkshopHistory` (Annuler/Rétablir de la barre jamais activés) | TOIT-a-004, GESTES-013 | ACAL1403 |
| `AtelierPanneaux.jsx` (aide « ? » invisible en Guidé) | TOIT-a-005 | ACAL1435 |
| `50-coque-atelier.css` (champ d'adresse masqué en Guidé) | TOIT-a-007 | ACAL1410 |
| `roof-tool-pro11.ts::go3DView` (Terminer / Créer le toit : 3D, dézoom) | GESTES-001, TOIT-a-003 | ACAL1422 |
| `CoqueAtelier.jsx::onDevis` (bouton de la barre qui ne génère jamais) | GESTES-003 | ACAL1437 |
| `roof-tool-pro11.ts::clearEditorState` (épingle du lead non replantée) | ACAL972 | ACAL1423 |
Matrice K-GESTE, colonnes ajoutées : « barre du plan à la souris » (Annuler, Rétablir), « mode Guidé » (aide, adresse).

## K-DEFAUT-CHOIX — encore violée
Module de départ présenté comme choisi après rechargement (GESTES-007, 015 → ACAL1415), pente d'un tracé libre présentée comme
un fait (GESTES-008 → ACAL1429), calepinage créé depuis un devis automatique marqué « complet » (ACAL1006 → ACAL1419), pose
auto-remplie / étape Panneaux « faite » (TOIT-a-001 → GATED ACAL1448). Ligne de matrice ajoutée : « après Enregistrer + recharger ».

## K-RETOUR-FAUX — encore violée
Perte d'ombrage −72 % figée (TOIT-a-011, 014 → ACAL1407), carte d'accès solaire sans couleur (TOIT-a-002 → ACAL1408),
« Aucun écart mesurable » alors que rien n'est comparé (TOIT-a-015 → ACAL1411), refus dit deux fois (GESTES-006 → ACAL1439 ;
ACAL946 → ACAL1424), production double (ACAL994 → ACAL1418). Un de ces retours (toast « Aucun changement », GESTES-002) est
DÉJÀ corrigé sur la branche (commit 6dd9d51955).

## K-GRANDEUR-UNIQUE, K-SAISIE-PERDUE, K-STYLE, K-JARGON, K-DOC-GEOMETRIE, K-IMPASSE
- K-GRANDEUR-UNIQUE : kWc 2,84 / 2,88 après Effacer (GESTES-009 → ACAL1416), surface « non tracée » d'un pan tracé (ACAL981 → ACAL1420).
- K-SAISIE-PERDUE : module choisi perdu à l'Effacer (GESTES-014 → ACAL1416), virgule décimale refusée (TOIT-a-009 → ACAL1436).
- K-STYLE : carte obstacle, panneau Expert, champs de saisie, diagramme de course du soleil, étape Toit face à Main
  (ACAL1441 à ACAL1445) ; croquis de schéma illisible (ACAL1427).
- K-JARGON : gabarit de zone avec noms de clés (TOIT-a-013 → ACAL1433, ACAL1434) ; clé brute « motif » (ACAL946 → ACAL1424).
- K-DOC-GEOMETRIE : le contour enregistré en champ au sol laisse son pan de tracé, chiffré deux fois (GESTES-004 → ACAL1412, S1).
- K-IMPASSE : 409 « module_substitue » d'une surface sans issue (GESTES-005 → ACAL1440, abaissé à S3 : le produit CALX109 est un artefact).
