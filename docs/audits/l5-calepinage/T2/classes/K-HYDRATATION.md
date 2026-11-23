# Fiche d'invariant — classe `K-HYDRATATION` (un écran relit le document à chaque ouverture)

Pourquoi : au tour 2, le lot A a prouvé que des saisies bien ENREGISTRÉES (présentes au document) ne reviennent pas à
l'écran à la réouverture : le champ est vide, la liste est vide, le chiffre est celui d'une hypothèse. Chaque correction
du tour 1 avait réparé l'écriture ; personne n'avait parcouru la LECTURE écran par écran. Différence avec `K-SAISIE-PERDUE`
(la saisie atteint le calcul) : ici le calcul est juste, c'est l'écran qui n'est pas remis à jour.

- **Invariant** : « Tout champ, objet ou choix que le document porte est relu par son écran à la réouverture et nourrit les
  mêmes chiffres qu'avant l'enregistrement ; un simple chargement n'écrit rien et n'efface rien. »
- **Née de** (tour 2, lot A) : T2-F2-TOIT-a-008, T2-F2-TOIT-a-010, T2-F2-TOIT-a-017, T2-F2-TOIT-b-004 (régression d'ACAL510),
  T2-F2-GESTES-012 ; restes d'ACAL500, 501, 502, 504, 509, 533, 1291, 968, 918, 510.
- **Où il peut être violé** — liste greppée sur `ba8ca4707` :
  - commande : `git grep -n -E "^\s*ensure[A-Z][A-Za-z]+\(\);" ba8ca4707 -- apps/web/src/scripts/roofPro11` → 14 montages ; ceux qui
    créent un écran lu UNE fois au montage sont les endroits à risque (`mapDraw.ts` ×3, `obstaclesUi.ts` ×3) ;
  - `git grep -n "appliquerHydratation" ba8ca4707 -- apps/web/src/scripts` : l'unique point de relecture (roof-tool-pro11.ts) ;
  - `git grep -n -E "useState\(\[\]\)|useState\(\(\) => lire" ba8ca4707 -- frontend/src/features/calepinage` : états d'écran initialisés
    sans le document (`BoutonDevis.jsx::decochees`).
  | Endroit | Viole aujourd'hui ? | Couvert par la garde ? |
  |---|---|---|
  | `mapDraw.ts::ensureImageCaptureFields` (date de photo, source) | oui (TOIT-a-008) → ACAL1405 | non |
  | `shadingUi.ts::syncHeightUi` (hauteur + provenance du bâtiment) | probable (TOIT-a-008) → ACAL1405 | non |
  | `obstaclesUi.ts::redrawEnvironment` (liste des objets d'environnement) | oui (TOIT-a-010) → ACAL1406 | non |
  | `roof-tool-pro11.ts::syncObsEdit` → `objetsSite.redessiner` (liste des obstacles) | oui (ACAL1291) → ACAL1409 | non |
  | `CourseSoleil.jsx::CourseSoleil` (hauteur du bâtiment sans `buildingId`) | oui (TOIT-a-017) → ACAL1447 | non |
  | `optimizer.ts::refusPanExistant` (réouverture d'un pan existant) | probable (régression ACAL510) → ACAL1404 | non |
  | `BoutonDevis.jsx::decochees` (surfaces cochées du devis lié) | oui (GESTES-012) → ACAL1413, ACAL1414 | non |
  | `ModeTerrain.jsx` (surface `sol` à contour) | probable (ACAL918) → ACAL1425 | non |
- **Matrice champ × condition** (lignes = ce que le document porte ; colonnes = ouverture Guidé · ouverture Expert · après
  Enregistrer + recharger · document sans cette clé) :
  | Champ | Guidé | Expert | Recharger | Clé absente |
  |---|---|---|---|---|
  | date de photo + source | n/a — Expert seul | casse (ACAL1405) | casse | tient |
  | hauteur du bâtiment + provenance | n/a — Expert seul | casse (ACAL1405) | casse | tient |
  | objets d'environnement (liste + ombrage) | n/a — Expert seul | casse (ACAL1406) | casse | tient |
  | obstacles (liste « nom · cotes · hauteur ») | casse (ACAL1409) | casse | casse | tient |
  | hauteur lue par la course du soleil | n/a | casse (ACAL1447) | casse | tient |
  | pan existant (toit + liste) | casse (ACAL1404) | casse | casse | tient |
  | surfaces cochées du devis lié | casse (ACAL1414) | casse | casse | tient |
- **Garde** (UNE, dans une famille existante) : étendre `apps/web/src/scripts/roofPro11/prefill.roundtrip.test.ts` par un
  parcours « document → écran → document » : pour chaque clé de la matrice, hydrater un document qui la porte, lire le DOM de
  l'écran (champ, liste) et le comparer à l'objet source ; elle parcourt les 7 lignes, pas le seul symptôme. Écrite par le
  rédacteur des tests premiers du tour 3, pas par la lane qui corrige. Preuve rouge : sur `ba8ca4707` les lignes date, bâtiment,
  environnement, obstacles échouent (non exécuté ici : aucune pile).
- **Cible du tour suivant** : oui — donnée aux relecteurs (rouvrir chaque calepinage de la matrice).
- **Propriétaire** : calepinage ; la garde est une tâche `[ ]` de son plan (non écrite ici : elle déclenche les jobs lourds de la CI).
- **Ce qu'elle ne couvre pas** : l'apparence des champs relus ; les clés du serveur seul (liste du détail).
- **Question de sortie** : « le système l'attraperait-il tout seul la prochaine fois ? » — non, tant que la garde n'existe pas
  → à écrire au tour 3 (le plan n'en porte pas : ajout par l'orchestrateur à la consolidation générale).
