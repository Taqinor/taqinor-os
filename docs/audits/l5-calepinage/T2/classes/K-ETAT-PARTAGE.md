# Fiche d'invariant — classe `K-ETAT-PARTAGE` (un état affiché a UNE source, partagée par tous ses afficheurs)

Pourquoi : quatre constats du lot A viennent du même geste de construction — un état d'écran copié dans un `useState`
local, un `Set` de session ou un index recalculé, au lieu d'être lu d'une source unique. Chaque copie dit juste à son
montage et ment après : « Expert » qui ne se propage pas, un module « à confirmer » qui devient « posé », un pan à deux noms.

- **Invariant** : « Un état que plusieurs écrans montrent ou qui doit survivre (mode Expert, module choisi, nom d'un pan,
  surfaces cochées) vit dans UNE source (document, magasin partagé) ; aucun composant n'en garde une copie de session. »
- **Née de** : T2-F2-TOIT-b-005, T2-F2-TOIT-b-002, T2-F2-GESTES-007 (+ GESTES-015), T2-F2-GESTES-012 ; apparentés : ACAL981
  (le pan actif lit `a.vertices` périmé au lieu de `ctx.vertices`), ACAL994 (production recalculée au lieu de la servie).
- **Où il peut être violé** — liste greppée sur `ba8ca4707` :
  - `git grep -n -E "useState\(\(\) => lire|new Set<string>\(\)|useState\(\[\]\)" ba8ca4707 -- frontend/src/features/calepinage apps/web/src/scripts/roofPro11`
    (états de session) ;
  - `git grep -n "useModeExpert" ba8ca4707 -- frontend/src/features/calepinage` → 5 appelants (`AtelierPanneaux`, `OutilsVue`, `Rail`, `CoqueAtelier`, `EtapeResultats`), chacun son état.
  | Endroit | Viole aujourd'hui ? | Couvert par la garde ? |
  |---|---|---|
  | `atelier/modeExpert.js::useModeExpert` (état par appelant) | oui (TOIT-b-005) → ACAL1438 | non |
  | `zones.ts::panConfirmes` (Set de session) | oui (GESTES-007) → ACAL1415 | non |
  | `zones.ts` liste (`areaLabel(i)`) contre `label` stocké | oui (TOIT-b-002) → ACAL1430 | non |
  | `BoutonDevis.jsx::decochees` (copie locale de la sélection du devis) | oui (GESTES-012) → ACAL1414 | non |
  | `zones.ts` → `computePanStats` (sommets du pan actif périmés) | oui (ACAL981) → ACAL1420 | non |
  | `zones.ts` Total / `affichageErp.ts` (production recalculée) | oui (ACAL994) → ACAL1418 | non |
- **Matrice** (état × afficheur) :
  | État | Afficheur 1 | Afficheur 2 | Après rechargement |
  |---|---|---|---|
  | mode Expert | bandeau (tient) | `OutilsVue`, `EtapeResultats` (casse) | tient (localStorage) |
  | module choisi / de départ | liste du pan (tient) | mention « à confirmer » (casse) | casse |
  | nom du pan | liste (Zone 1) | cadenas, refus, tableau (Zone 2, casse) | casse |
  | surfaces chiffrées | phrase (casse) | génération (tient) | casse |
- **Garde** : une règle de test dans le module existant de chaque famille (`modeExpert.test.js`, `zones.test.ts`,
  `BoutonDevis.test.jsx`) qui monte DEUX afficheurs de l'état et bascule l'un ; une assertion par case ci-dessus. Écrite par le
  rédacteur des tests premiers du tour 3. Rouge attendu sur `ba8ca4707` : modeExpert (deux composants), panConfirmes
  (aller-retour du document), noms de pan — non exécuté.
- **Cible du tour suivant** : oui.
- **Propriétaire** : calepinage (front et `apps/web` roofPro11).
- **Ce qu'elle ne couvre pas** : les états de formulaire en cours de saisie (brouillon : classe `K-SAISIE-PERDUE`).
- **Question de sortie** : non, tant que la garde n'existe pas → à écrire au tour 3.
