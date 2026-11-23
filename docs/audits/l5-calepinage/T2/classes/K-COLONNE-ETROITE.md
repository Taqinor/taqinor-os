# Fiche d'invariant — classe `K-COLONNE-ETROITE` (une grille se dimensionne par la largeur de son conteneur)

- **Invariant** : « Aucun bloc du panneau de droite de l'atelier (colonne de 220 à 320 px en Expert) ne choisit son nombre de
  colonnes par un point de rupture de la FENÊTRE ni par une largeur minimale fixe : chiffres, libellés, unités et tableaux
  tiennent dans la colonne à 1440 × 900 sans chevauchement ni défilement horizontal, et les nombres s'écrivent à la française. »
- **Née de** (tour 2, lot B) : T2-F2-POSE-a-002 (S2), -003, -007, -011, -014 (lisibilité) ; T2-F2-POSE-b-001 (présentation),
  -002, -004 (doublon de POSE-a-011) ; reprises d'ACAL610, ACAL607, ACAL619 ; optionnel S4 T2-F2-ELEC-b-007 (bouton qui
  déborde). La classe K-STYLE du tour 1 couvre le jeton et le thème, jamais la largeur : c'est une classe différente.
- **Où il peut être violé** — greps lancés sur la tête de cette session (`ba8ca4707`) :
  - `git grep -n -E "\b(sm|md|lg):grid-cols" -- frontend/src/features/calepinage ':!*test*' ':!*__golden__*'` → 76 lignes dans
    40 fichiers ; les blocs du PANNEAU DE DROITE (colonne étroite) sont ceux du tableau ci-dessous ;
  - `git grep -n -E "min-w-\[[0-9]{3}px\]" -- frontend/src/features/calepinage apps/web/src/scripts/roofPro11 ':!*test*'` →
    `panStats.ts`, `zones.ts`, `TableauComparatif.jsx`, `DemarrageRapide.jsx` (plein écran : hors classe) ;
  - `git grep -n "@media (max-width" -- frontend/src/styles/roofbuilder.css frontend/src/styles/calepinage` → 5 repli sur la
    FENÊTRE dont `roofbuilder.css::.rp9-setbacks` ; précédent de requête de conteneur : `54-etape-resultats.css`
    (`container-type: inline-size`).
  | Endroit | Viole aujourd'hui ? | Couvert par la garde ? |
  |---|---|---|
  | `frontend/src/features/calepinage/ModeTerrain.jsx::ModeTerrain` (`sm:grid-cols-5` chiffres, `sm:grid-cols-3` champs) | oui (POSE-a-002) | non — ACAL1511 |
  | `apps/web/src/scripts/roofPro11/panStats.ts::htmlTableSite` (`min-w-[620px]`) | oui (POSE-a-003) | non — ACAL1513 |
  | `frontend/src/styles/roofbuilder.css::.rp9-setbacks` (2 colonnes + champ de 6 rem) | oui (POSE-a-011) | non — ACAL1519 |
  | `frontend/src/features/calepinage/atelier/InspecteurBuilder.jsx::InspecteurBuilder` (Total, `sm:grid-cols-4`) | oui (POSE-b-002) | non — ACAL1519 |
  | `frontend/src/features/calepinage/atelier/BuilderPose.jsx::BuilderPose` (bandeau, `sm:grid-cols-4`) | oui (POSE-a-014) | non — ACAL1519 |
  | `frontend/src/features/calepinage/atelier/Fixation.jsx::Fixation` (liste et classeur hors colonne) | oui (POSE-a-007) | non — ACAL1518 |
  | `frontend/src/features/calepinage/atelier/TableauComparatif.jsx` (`min-w-[560px]`) | oui (POSE-b-001) | non — ACAL1525 |
  | `frontend/src/features/calepinage/electrique/VerdictElectrique.jsx::TableauTensions` (6 colonnes) | oui (ACAL619) | non — ACAL1544 |
  | `apps/web/src/scripts/roofPro11/zones.ts` (table `min-w-[520px]` des zones) | probable (non relevé) | non |
  | `frontend/src/features/calepinage/electrique/Raccordement.jsx` (limites du distributeur, bouton « Ajouter une plage ») | oui, S4 (ELEC-b-007) | non |
  | 30 autres fichiers à `sm:grid-cols` hors panneau de droite (écrans en pleine largeur) | non (pleine largeur) | n/a |
- **Matrice champ × condition** :
  | Bloc | colonne 220 px (Expert, 1440 × 900) | colonne 320 px | pleine largeur (liste, résultats) | téléphone 375 px | thème sombre |
  |---|---|---|---|---|---|
  | chiffres du champ au sol | casse (POSE-a-002) | casse | n/a — onglet | ? | ? |
  | tableau Site | casse (POSE-a-003) | casse | n/a | ? | ? |
  | retraits (4 champs) | casse (POSE-a-011) | casse | n/a | tient (repli fenêtre) | ? |
  | bandeau des 4 chiffres, Total | casse (POSE-a-014, POSE-b-002) | casse | n/a | ? | ? |
  | nomenclature de fixation | casse (POSE-a-007) | casse | n/a | ? | ? |
  | Comparer les poses | n/a | casse (POSE-b-001) | n/a | ? | ? |
  | Tension par temps froid | n/a | casse (ACAL619) | n/a | ? | ? |
- **Garde** (UNE par classe, famille existante) : étendre `frontend/src/features/calepinage/langageVisuel.test.mjs` (la garde « un
  seul langage visuel », K7) d'une règle « aucune grille du panneau de droite ne dépend d'un point de rupture de fenêtre et
  aucun tableau n'y force une largeur minimale », une assertion par ligne du tableau ci-dessus. Écrite par le rédacteur des
  tests premiers (ACAL1519 la porte avec ses cinq blocs) ; rouge attendu : remettre `sm:grid-cols-4` sur le bloc Total.
- **Cible du tour suivant** : oui — donnée aux relecteurs de beauté : mesurer chaque bloc à 220 px, 320 px et 375 px.
- **Propriétaire** : calepinage (`frontend/src/features/calepinage`, `frontend/src/styles/roofbuilder.css`,
  `apps/web/src/scripts/roofPro11`).
- **Ce qu'elle ne couvre pas** : le fond d'imagerie, la cible tactile de 44 px (ACAL1280), les contrastes (K-STYLE).
- **Question de sortie** : « le système l'attraperait-il tout seul la prochaine fois ? » — oui, par la règle ajoutée à
  `langageVisuel.test.mjs` une fois ACAL1519 construite.
