# r2 — ajouts de l'orchestrateur à la vague 3 (hors rapports des relecteurs)

Vus en CI (PR 1481) ou sur la pile, à donner à la lane qui possède le fichier :

- **Saisie — une lettre perdue après le choix d'un projet dans la liste `#`** (`features/taches/saisie/FeuilleSaisie.jsx`,
  `ui/ChampSaisie.jsx`). Test `FeuilleSaisie.test.jsx` « R2-003 — sans accents ni casse, flèches puis Entrée, ou au
  doigt ; Échap ferme la liste, pas la feuille » : vert sur le poste, ROUGE en CI sous charge (shard vitest 2, tête
  `2d65165d6`) : attendu « Photos #Site_web et #Chantier_Bénali_9_kWc », reçu « Photos #Site_web t #Chantier… » — le
  « e » tapé juste après l'insertion du projet est avalé. Même famille que R2-001 : l'insertion du jeton réécrit le
  champ à partir d'une valeur périmée. Correction à la racine (insertion calculée sur la valeur COURANTE du champ, au
  moment de l'écriture ; rien d'asynchrone entre le choix et l'écriture), test qui tape la suite SANS attendre
  (plusieurs frappes enchaînées dans le même `act`), rejoué 20 fois de suite.
- **Cloche de l'en-tête** : nom lu « Notifications : 14 » (axe-core 4.14 de la CI refuse « Notifications (14) » avec
  la pastille « 14 ») — FAIT (`2d65165d6`). Le `node_modules` du poste porte axe 4.12.1 : une spec axe verte ici ne
  prouve rien ; vérifier contre 4.14.0 (`…\scratchpad\r2\orchestrateur\axe414\package\axe.min.js`, script
  `axe-cloche3.cjs` à côté).
- L'outil `capturer-reel.cjs`, étape `menu-ligne` : touche l'étoile cachée sous le bouton invisible et modifie le
  compte (signalé par T2-B1) : corriger le geste du script (appui long ou ⋯ visible).
