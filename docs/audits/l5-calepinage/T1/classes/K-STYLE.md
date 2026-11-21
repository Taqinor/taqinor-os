# Fiche d'invariant — classe `K-STYLE` (un seul langage visuel, le thème de l'ERP)

- **Invariant** : « Le module n'emploie que les jetons et composants de l'ERP : il suit le thème clair/sombre, contraste
  ≥ 4,5:1, 3-4 styles de boutons, un style « choisi » et un style « recommandé » ; aucune classe du site public sans règle. »
- **Née de** : T1-B1-001, T1-T1-017, T1-B1-005, T1-B1-006, T1-F1-009 (+ B1-008, B1-009, T1-010), T1-T1-011, T1-T1-018,
  T1-B1-017, T1-B1-018, T1-B1-021, T1-B1-011, T1-T1-013 ; hors périmètre : T1-B1-025, T1-T1-026 (propriétaire deploy).
- **Où il peut être violé** : `frontend/src/styles/roofbuilder.css::.rp9-host` (palette littérale), les classes posées par
  `roof-tool-pro11.ts::ensureSetbackInputs` (`rp9-setbacks`, `rp9-input`, `rp9-note`, AUCUNE règle CSS — lu par WA), les
  fichiers listés par ACAL427/428/429/432/442.
  | Endroit | Viole ? | Garde ? |
  |---|---|---|
  | `.rp9-host` palette sombre fixe, `<select>` natifs illisibles en clair | oui | ACAL430 |
  | panneaux d'onglets à classes du site public | oui | ACAL427/428/429/432/442 |
  | `ensureSetbackInputs` (classes sans règle, texte nu) — fichier hors des listes de migration | oui | non |
  | 3 styles « choisi » (`.rp9-chip[aria-pressed]`, contour, coche) | oui | non |
  | contrastes, < 12 px | oui | ACAL438, ACAL439 |
- **Garde** : `langageVisuel.test.mjs` créée par ACAL427, rendue stricte par ACAL479 — y ajouter `roof-tool-pro11.ts`
  (classes créées en JS) et une règle « un seul état choisi ». ACAL439 (axe-core clair + sombre) pour les contrastes.
- **Cible du tour suivant** : oui (après la vague de migration).
- **Propriétaire** : calepinage ; `deploy` pour les deux hors-périmètre.
- **Question de sortie** : oui une fois ACAL479 strict + l'ajout de `roof-tool-pro11.ts` (D7-24).
