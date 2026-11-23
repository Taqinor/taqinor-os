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

## 6. Points « à corriger après » de la critique de la vague A (`T2/critique-vague-A.md`)
- Fond satellite de l'atelier (ACAL1421) : CORRIGÉ avant la fusion (commit a37c9be26).
- Garde de société de `views/calepinages.py::_devis_lie` (ACAL1413) : CORRIGÉE (commit f26d073102, vague B).
- Champ au sol encore compté deux fois quand il est le SEUL pan (`poseSurfaces.ts::retirerPanDeTrace`, ACAL1412) :
  lane `production-web`.
- Exemple `apps/ventes/contract_samples/etude_horaire.json` périmé par ACAL1537 : à régénérer (plan du propriétaire
  de `ventes`).
- Deux écarts de signe opposé entre l'onglet Économie et le bandeau Production (ACAL1611) : lane
  `ecran-elec-resultats`.
- Lien « Renseigner la facture du lead » caché quand la facture manque (ACAL1517) ; toit plat non enregistré :
  « Confirmer » refuse encore (ACAL1428 × ACAL1429) : lane `ecran-toit-panneaux`.
- L'épingle du lead réapparaît à « + Ajouter une zone » (`roof-tool-pro11.ts::clearEditorState`, ACAL1423) : lane
  `production-web`.
- Sans fourchette réglée, plus aucun avertissement de ratio panneaux / onduleur, même à 2,0 (ACAL1538, conforme au
  texte de la tâche) : À DIRE au fondateur (régler une fourchette en production, ou garder une alerte de repli).
- Sur la page privée `/preview/toiture-3d-pro-11` du site public, neuf retouches de l'atelier arrivent sans qu'une
  tâche nomme le site (toit grisé pendant l'ajout d'un pan, tableau Site en deux colonnes, puces d'objectif, groupe
  « Structure et pose »…) : sans effet sur les pages des visiteurs ; à dire au fondateur.

## 7. Autres restes de la vague 2
- ACAL1608 (la facture du lead n'atteint pas encore la simulation) : poser `facture_lead` dans `simulation.py` (le
  contexte de simulation ne porte ni société ni lead) et le dire dans `ChargesAjoutees.jsx`.
- ACAL1709 : impossible tant qu'ACAL1001 (niveau de règles 15, décision du fondateur) n'est pas tranchée.
- ACAL1705 (carte « Devis créé » à boîte nulle) : non reproduite en test ; cause probable : le portail de la coque
  qui se remonte après `onRecharger`.
- ACAL1703 : l'obstacle fautif n'est pas sélectionné à l'arrivée (`EtapeToit.jsx`) ; `GroupesPretAEnvoyer.jsx` :
  montrer le geste sur la ligne.
- ACAL1550 : `protections.questions` n'est servie par aucune réponse (libellé recopié en dur).
- Hors réseau : `heures` = longueur totale de la série (87 600 h en pluriannuel), non divisée.
- Les étapes IAM, LID, qualité, MPPT, ohmique, onduleur, vieillissement, diodes, bifacial lisent encore la fiche du
  module par défaut, pas celle du module posé (ACAL1607 ne corrige que la thermique).
- `PhotoSiteCalage.jsx` : champ fichier natif (« Choose File ») ; `ParcoursDuPan.jsx` : `sm:grid-cols-2`.
- `calepinage-mesures-ecran.baseline.json` : à régénérer UNE fois sur la pile (35 contrôles attendus au premier
  écran après ACAL1805, +1 avec ACAL1809).
