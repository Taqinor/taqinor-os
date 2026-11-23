# Entrées du lot O (orchestrateur) — ce qui n'appartient à aucun lot A-E · ids ACAL1900 à ACAL1949

Tenu par l'orchestrateur au fil de la vague 2. Le lot O se rédige quand les lots D et E sont rendus (pour ne rien
doubler). Chaque ligne dit la source ; « à vérifier » = relire le code sur la tête de la branche avant d'écrire.

## 1. `ok` contredits par la relecture adverse, hors des lots qui les ont repris
- **ACAL987** (lot A, `T2-audit-ok.jsonl`) : un 409 sur `plan-importe` et un `console.error` à l'ouverture de 15 onglets ;
  la spec e2e n'a pas été lancée. Le lot A classe le 409 en artefact du jeu d'essai (document d'exemple au plan de fond
  détaché) : à vérifier, puis reprise ou « preuve à rejouer ».
- **ACAL444** (`T2-audit-ok-D-2.jsonl`) : la ligne dépliée de la cascade ne montre jamais « Entrée » —
  `CascadePertesLignes.jsx` ne l'affiche que si c'est une chaîne, le serveur la sert en objet.

## 2. Tâches de spec que seul l'orchestrateur pouvait jouer (verdict : partiel, d'après `T2/base-e2e.md` et RATT-1)
- **ACAL1315** (comparaison aux maquettes en contrôle permanent) : la spec est rouge sur 12 maquettes pour des défauts de
  SPEC (libellés attendus absents de la maquette elle-même, état de départ sans pose ni simulation) ; à reprendre en la
  visant sur les maquettes v2 (lot E) avec un état de départ construit.
- **ACAL385** (mesures de l'atelier) : « contrôles visibles : 35 dépasse la base 34 », base du 22/11 ; trois cas non
  lancés (mode série). À re-baser après la coque v2, et dire quel contrôle est le 35e.
- **ACAL891** (refus au-delà de la limite de modules) : `frontend/e2e/calepinage-perf.limite.json` absent → le refus est
  inerte (RATT-1). Reprise : produire le fichier par la spec de perf ou lire la limite d'un réglage.

## 3. Demandes croisées laissées par les lanes de la vague 2 (non honorées à ce jour)
- `optimizer.ts` (lane zones) : passer le kWc de la carte à `peindreBande`, et faire repeindre la production de la carte
  et le Total par `majChiffrage` après « Enregistrer ».
- `optimizer.ts::renderLiveWinner` (lane scene, ACAL1523 déclarée impossible dans sa lane) : ajouter
  `chassis: optionChassis(...)` à son `packConfig` et appeler `majNoteChassis(pack, grid)` après `renderScene` ; même
  fonction : `module: cotesDuModuleDuPanActif()` n'est pas passé (le rendu peut paver aux cotes du module par défaut —
  touche le kWc affiché : à traiter comme une tâche de justesse, opus).
- `shadingUi.ts::moduleShadeTooltip` (lane scene) : utiliser `clePanAffectation`.
- `layoutHistory` (lane scene) : photographier `activeAreaId` et `surfacesPose` ; `deleteArea` appelle
  `pushWorkshopHistory` (pour que « Annuler » de la barre défasse aussi le remplacement d'un pan par un champ au sol).
- Contrat d'abord (lane zones) : ajouter `orientation_nord` aux motifs de pan vide du schéma v2, puis l'émettre dans le
  chemin « toit en pente » de l'optimiseur.
- `matrix.recomputeMatrix` (lane balayage) : ne passe ni `setbacksM`, ni `obstructionClearancesM`, ni `overhangM`.
- `prodWindow.ts` et `roof-tool-pro11.ts` (lane editeur-1) : multiplient encore par `PANEL_KWC` (720 W) ; la fenêtre de
  production peut lire 3,60 là où le bandeau lit 3,55.
- Tableau par pan de `zones.ts` : `min-w-[520px]` (classe K-COLONNE-ETROITE, lane zones).
- Ombrière : même doublon pan + surface que le champ au sol corrigé par ACAL1412 (lane scene).
- Anneau posable vide : `pack.origin` à [0,0], la note dit « ne laisse que 0,00 m sur 0,00 m » (lane scene).
- `imagerie.fournisseur` rangé par la société, `fournisseur_imagerie` lu par le registre (lane carte-a) — si le lot D ne
  l'a pas inscrit.
- `calepinage_publication.json` : pas d'exemple du 409 `module_substitue` pour une surface (lane contrats-suite) — si
  le lot D ne l'a pas inscrit.

## 4. Tâches pour un AUTRE plan (texte complet dans `lot-C.md` § 5)
- **deploy** : recycler le processus du worker Celery (`CELERY_WORKER_MAX_TASKS_PER_CHILD`,
  `CELERY_WORKER_MAX_MEMORY_PER_CHILD`) et dimensionner `celery_worker` (constat T2-ORCH-001).
- **stock** : saisir dans la fiche produit la dégradation, les garanties à 10/25 ans et les champs de l'optimiseur.
- Journal du serveur en avance d'une heure sur l'heure servie (la base de fuseaux du système est antérieure au décret
  du 20/09/2026 ; `zoneinfo` lit le paquet `tzdata` épinglé, `time.localtime()` lit le système) — vu par
  l'orchestrateur le 23/11 sur la pile de revue ; à vérifier sur l'image de prod avant d'écrire une tâche (plan deploy).

## 5. Décisions ouvertes posées pendant la vague 2
D-ACAL-80 (température de froid) · D-ACAL-81 (NASA POWER) · D-ACAL-82 (valeurs par défaut de quatre pertes) ·
D-ACAL-83 (mesure de l'ombre proche : centre du pan ou panneaux posés) · D-ACAL-84 (ligne thermique d'un toit affleurant)
· D-ACAL-85 (composition du P90).
