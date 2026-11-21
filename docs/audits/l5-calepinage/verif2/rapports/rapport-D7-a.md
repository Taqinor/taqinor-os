# Rapport vérificateur — lot D7-a (25 tâches), code lu dans l5-verif (main, HEAD 45eafba77)

Note : l5-verif contient déjà `docs/plans/PLAN_AUDIT_CALEPINAGE.md` avec les blocs D2/D3/D4 (ACAL572, 602, 603, 606, 607, 609, 612, 613, 687, 770…), et ACAL397 est COCHÉE (ReglagesNorme.jsx construit). Plusieurs tâches D7 refont ce que ces tâches décrivent déjà.

### ACAL911 — CORRIGER (mineur)
Prémisse vraie : `ventes/domain/geometrie.py:105` écarte `geometry` si `family == 'eastwest'` ; `pvgis_serie.py::jambes_du_pan` (l.234-300) lit déjà `geometry.azimuthDeg/tiltDeg` seul. Mais `ventes/tests/test_acal_orientation_pose.py::test_eastwest_garde_la_lecture_actuelle` (l.78) casse forcément (il fige 0°/180/'toit') et n'est pas dans `Files:` (la clause dit « même merge » ET « autre geste » : contradictoire).
Correction : ajouter `backend/django_core/apps/ventes/tests/test_acal_orientation_pose.py` à `Files:` et supprimer « autre geste : docs/plans/PLAN_AUDIT_DEVIS.md » de la clause Assertions existantes.
OPTIONNEL : la clause cite D-ACAL-6 pour « la production imprimée ne change pas » ; D-ACAL-36 (21/11) l'a remplacée pour les nouveaux devis (ACAL973) : citer D-ACAL-36.

### ACAL913 — OK
`roofPro11/moduleSelect.ts:131` `MODULE_PAR_DEFAUT_ATELIER` 720 Wc ; `zones.ts:841-868` `syncModulePicker` (mention « aucun module du catalogue n'est posé ») ; `roof-tool-pro11.ts:669` `newAreaRecord` (3 appels : 674, 2534, 2632) ; aucun `moduleId` posé par défaut. Tests nommés existent.

### ACAL914 — OK
`calepinage/services/devis.py::_garde_kwh_declare` (l.217) et `_generer_sous_verrou` (l.265, `build_devis_from_layout` + garde dans `transaction.atomic`) ; `DevisRefuse(..., statut=409, donnees=...)` supporte un `code` ; `assistant.py:520` appelle `generer_devis`. `BoutonDevis.jsx:152` range un 409 `detail` sans `errors` en `conflit` qui affiche `detail` tel quel (sans bouton révision) : le texte du 409 s'y lit correctement.

### ACAL915 — CORRIGER (mineur)
Prémisse vraie (`pans_du_document` additionne pans + `poseSurfaces`, `geometrie.py:445`). Faux : « Appelants : `BoutonDevis` ← `ToitureDesign.jsx` (1 site) » : le seul importeur est `AtelierPanneaux.jsx:12/280` (cf. ACAL923 qui le dit juste).
Correction : remplacer par « `BoutonDevis` ← `AtelierPanneaux.jsx` (1 site) ».

### ACAL916 — CORRIGER
(a) Contradiction interne : le Constat dit que `modeles_designes` rend `[]` sans `produit_id` (vrai, `geometrie.py:607-620`) mais Given/Then attend que `modeles_designes` rende deux modèles `produit_id: None` ; il faut dire que `modeles_designes` doit aussi rendre les groupes quand ≥ 2 puissances distinctes (sinon la composition reste à un seul watt).
(b) Clause « une surface à `moduleId` le résout dans `modules[]` (inconnu ⇒ refus `poseSurfaces.N.moduleId`) » : aucun écrivain ne produit `poseSurfaces[].moduleId` (Hors périmètre le dit ; `pans_du_document` l. 548 pose `module_id: None`), la clé n'est pas dans `roof_layout_v2.schema.json` (Contrat « n/a »). Lecture d'une clé jamais écrite = à retirer.
Correction : supprimer la phrase sur `moduleId` de surface ; ajouter à « Emplacement » : `modeles_designes` rend les groupes dès que les puissances diffèrent.

### ACAL917 — DOUBLON
Identique à ACAL607 (D2, même figure 176 × 710 = 124,96 kWc, même cause `computeSiteStats` sans `moduleFor`, même fichiers). Prémisse vraie (`zones.ts:523`, `panStats.ts:276-300`, `SurfacePoseLigne` sans `moduleWc`) mais déjà planifiée. Correction : supprimer ACAL917 (garder ACAL607).
OPTIONNEL : « modulesPoses rend le module d'une surface » est faux (il rend un nombre, `poseSurfaces.ts:408`).

### ACAL918 — OK
`poseSurfaces.ts:557-583` `enregistrerContour` pousse `verdict.surface` sans `engine` (liste « — (plan du moteur non reçu) » l.551) ; `monterAtelierPose` ← `mapDraw.ts:1623` et `roof-tool-pro11.ts:1893` ; `calepinageApi.moteur.pose` (calepinageApi.js:367) ; patron `proposerConsommation` (types.ts:121, useAtelierBoot.js:70). Dépend de ACAL919 : voir ce verdict (si 919 est supprimé, `@after` doit viser ACAL606/609).

### ACAL919 — DOUBLON
Fusionner dans ACAL606 (+ ACAL609 pour l'écran) : même constat (176 modules à 0,60 m, `SurfaceSol` sans appelant — vérifié `grep` : seule `core/calepinage/surfaces/sol.py`), même correctif (`calepiner` sans politique, `moteur_service.py:187-230`). Les deux tâches inventent deux contrats concurrents (919 : `type:'sol'` dans `surfaces` + `latitude_deg` ; 606/609 : `sol: {latitude_deg}` HORS de `demande`) → deux lanes différentes, collision certaine sur `pose.json`/`moteur_service.py`. Correction : supprimer ACAL919, garder 606/609.
OPTIONNEL : « Contrat partagé … affirmé par `test_axe_rangee_auto.py`, importé par `ModeTerrain.test.jsx` » est faux aujourd'hui (aucune des deux ne lit `pose.json`).

### ACAL920 — DOUBLON (et un défaut propre)
Même alerte « allée imposée ombre la rangée suivante » que ACAL609. En plus, faux : le message et `instant: 'midi solaire du solstice d'hiver'` utilisent « le soleil de `position_solaire_solstice` » or son défaut est `HEURE_SOLAIRE_DIMENSIONNEMENT = 10.0` (`core/calepinage/politique_pas.py:51-53`, 10 h, pas midi) : le chiffre affiché ne correspondrait pas au texte. Correction : supprimer ACAL920 (609 couvre l'alerte) ; si une version est gardée, écrire « à 10 h solaire au solstice d'hiver (heure de dimensionnement du pas) » ou passer `heure_solaire=12.0` explicitement.

### ACAL921 — CORRIGER
Prémisse vraie : seul lecteur +90 = `geometrie.py:543-554` ; la façade (`poseSurfaces.ts:1178/1220`, cap de la normale) et le terrain écrivent une FACE. Oubli : un ÉCRIVAIN suit la convention +90 : `calepinage/services/balayage.py:210` `objet['rowAzimuthDeg'] = (azim - 90.0) % 360.0` (azim = face). Retirer le +90 du lecteur sans changer cet écrivain décalerait de 90° tout calepinage balayé. De plus la convention est gravée dans `roof_layout_v2.schema.json` l.1462 ET l.1515 (« rowAzimuthDeg + 90 (défaut gravé) ») : deux endroits à réécrire, pas « le schéma » au singulier.
Correction : ajouter à `Files:` `backend/django_core/apps/calepinage/services/balayage.py` (écrire `azim` tel quel, plus de `- 90.0`) et son test, et préciser « schéma l.1462 et l.1515 ».

### ACAL922 — CORRIGER
`cible_depuis_lead` (`ventes/selectors.py:1612-1676`) rend `panneaux: None` aussi pour un lead C&I/agricole (« la taille se décide par l'étude C&I »), pour un kWh incohérent (`MESSAGE_KWH_INCOHERENT`, déjà refusé par `_garde_kwh_declare`) et pour toute `AutoDevisError` : la condition « `panneaux` null » poserait la question « Aucune facture ni taille souhaitée » à tort. La clé s'appelle `refus`, pas `motif`.
Correction : condition = lead résidentiel sans `taille_souhaitee_kwc` ET refus de type facture absente (`MOTIF_FACTURE_ABSENTE`, `ventes/domain/taille.py:91`) ; comme `cible_depuis_lead` ne porte pas le code, ajouter `ventes/selectors.py` à `Files:` (clé additive `motif_code`) ; lire `refus` et non `motif`.

### ACAL923 — OK
`BoutonDevis.jsx:152` classe tout 409 `detail` nu en `conflit` (prémisse vraie) ; `executer` l.129 ; `BoutonDevis` ← `AtelierPanneaux` ; hooks `E2E_HOOKS.md` et `e2eHooks.test.mjs` existent. Dépend du correctif de ACAL922.

### ACAL924 — OK
`consumption.ts:692-740` `monterProposition` n'appelle `proposer({source:'lead'})` qu'au clic « Reprendre du lead » (l.727) ; `useAtelierBoot.js:70-72,395` fournit `proposerPourAtelier` en mode calepinage et `null` en mode lead (l.258) ; test `roofPro11QuoteFirstSizing.test.ts` existe.

### ACAL925 — OK
`roof-tool-pro11.ts:2453-2454` `clearEditorState` remet `neededPanels = 0`, `neededAuto = true` ; `imposeTarget` (l.2033) est une closure de `applyDevisHydration` (l.2007) ; `reset` l.2522 ; `userJourneyPro11.test.ts` et golden existent.

### ACAL926 — OK
`roof-tool-pro11.ts:2992-2996` `dblclick` appelle `cancelPendingVertex()` puis `close()` ; le clic proche du sommet en attente retourne sans le poser (l.2977-2979) → le 4ᵉ coin est bien jeté ; `flushPendingVertex` existe (l.2839).

### ACAL928 — OK
`estimatorBrainV7.ts:353-356` `tiltCandidates` rend `matrixTiltGrid` pour toute orientation ; `estimatorBrainV6.ts:248` `EW_TILTS = [10,12,15]` (non exporté) ; `solveConstrained` appelé 4 fois (l.509,515,521,526) ; test V7 « aucune autre config » parcourt `matrixTiltGrid` (l.82-90). Chiffres repris du code V6 (aucun inventé). Rejeu 35°/0° Marrakech non refait (non exécutable ici).

### ACAL933 — DOUBLON
Partie (1) = ACAL602 (« imprimer l'échelle réellement dessinée ») mais avec l'approche OPPOSÉE (933 recale le tracé sur un rang normalisé ; 602 imprime `round(1000/échelle)`) ; parties (2)+(4) = ACAL603 (cotes du toit seul + DXF, même `etendue_toit`, même `_coter`). Construites toutes les deux : conflit sur `_echelle_nommee`/`_etendue`. De plus 3 comportements dans une tâche. Correction : supprimer ACAL933 ; si le listage « Hors toit : <repère> » est voulu, le garder comme tâche seule `@after: ACAL603`.

### ACAL934 — DOUBLON
Même défaut et même correctif que ACAL612 (D3) : `_rapport_publication` (`electrique.py:2793`) ne compte pas `non_verifiable`/`omis` ; 612 sert `etat` « publiable_avec_reserves »/`reserves`, 934 sert `etat` « pret/a_completer/bloquant »/`points` : deux vocabulaires pour la même donnée. Correction : fusionner dans ACAL612 (ou faire de 934 un complément `@after: ACAL612` qui n'ajoute `etat`/`points` qu'à `verdict_de_conception`, `evaluation_electrique` et `_bloc_electrique`, en réutilisant le vocabulaire de 612 ; ACAL858 du lot D6 doit alors lire ce vocabulaire).

### ACAL935 — DOUBLON
L'onglet `VerdictElectrique.jsx:350-353` (`calx249-publiable`, « Publiable / Non publiable ») est exactement ce que ACAL613 (D3) remplace ; 935 le remplace à son tour par `acal935-etat`. Correction : retirer la partie onglet (613) ; garder uniquement `BoutonDevis.jsx` (`manquantesElectriques`, l.46, cadre `cal-devis-indetermine` l.435) et `AffectationChaines.jsx:488` (`cal234-verdict-etat`), `@after` la tâche qui fixe le vocabulaire (612).

### ACAL936 — DOUBLON
Identique à ACAL687 (D3, même titre, même lane `calepinage/electrique`). Prémisse vraie (`raccordement.py:619-625` lit `saisie['phases']` seul ; repli déjà dans `electrique.py:2637,2645`). Correction : supprimer ACAL936.

### ACAL937 — SANS OBJET (reste un lien)
Prémisse fausse : `reglages/ReglagesNorme.jsx` existe (construit par ACAL397, cochée) : carte « Norme électrique », options « Aucune » et `nf_c_15_100`, `PUT parametres/` avec la section servie (`...servi`, coefficients gardés), monté en `ReglagesSimulation.jsx:671`, champ d'id `norme`. Reste seulement : le lien « Choisir la norme » dans `commun/Provenance.jsx::SourcesNormatives` (aucun lien aujourd'hui). Correction : supprimer la tâche, ou la réduire à ce lien vers `/calepinage/reglages#norme` (id réel) ; la phrase « ACAL397 se construit après cette tâche » est périmée.

### ACAL938 — À SCINDER
La carte « Lestage » des Réglages est déjà planifiée par ACAL572 (D2, non cochée : dix paramètres + zones de pose, `PUT` de la section entière) ; 938 en demande une seconde dans le même fichier (8 paramètres) → double construction. Prémisse vraie (aucun lestage dans `reglages/*.jsx` ; `PanneauMasseLestage.jsx:53` `CHEMIN_REGLAGES` sans ancre). Correction : ne garder que le lien profond (`CHEMIN_REGLAGES` + `#<ancre du premier manquant>`) et « Saisir le lestage » dans `SourcesNormatives`, `@after: ACAL572`, et faire dire à ACAL572 de ne pas demander pesanteur/air (ACAL939).

### ACAL939 — OK
`lestage.py:56-67` `PARAMETRES` contient les deux clés ; usages l.379-433 ; `NOMBRES_DE_FORME` garde de `test_lestage_parametre.py:200`. Valeurs avec source nommée (3ᵉ CGPM 1901, atmosphère type) et « le constructeur relit à la source » : pas un chiffre inventé.
OPTIONNEL : l'en-tête CAL163 / D-CALX 7 interdisait toute constante ici ; la levée mériterait une ligne de décision fondateur.

### ACAL940 — OK
`simulation.py:736-765` `verifier_simulable` s'arrête au premier manque (mode météo, plans, épingle, tmy) ; `chaine_pertes.py:2055,2127` `decision_meteo`/`_fenetre_pluriannuelle` ; `PanneauProduction.jsx:217` lien `/calepinage/reglages` sans ancre ; ids `calx69-<clé>` existent (`ReglagesSimulation.jsx:197`) ; ACAL386 cochée (forme `cible`) ; tests nommés existent (`test_acal_refus_simulation.py:124,126`). 5 assertions `/calepinage/reglages` dans `PanneauProduction.test.jsx` (la tâche en annonce 3 : à recompter).

### ACAL941 — DOUBLON
ACAL770 (D4) désactive déjà « tmy » (et `martin_ruiz`) dans Réglages avec motif (piloté par le serveur `valeurs_non_servies`), même cause (`verifier_simulable` `MOTIF_TMY_HORIZONTAL`). 941 en fait une table figée dans le composant, même fichier : conflit. Correction : fusionner dans ACAL770.

---
Totaux : OK 10 (913, 914, 918, 923, 924, 925, 926, 928, 939, 940) ; CORRIGER 5 (911, 915, 916, 921, 922) ; DOUBLON 8 (917, 919, 920, 933, 934, 935, 936, 941) ; SANS OBJET 1 (937) ; À SCINDER 1 (938).
Non vérifié : aucun rejeu à l'écran ni exécution de test (lecture seule) ; chiffres de rejeu (34,08 kWc, 168 800 MAD, 111 420 kWh) pris tels quels.
OPTIONNEL (5 max) : voir les notes ACAL911 (D-ACAL-36), 917 (modulesPoses), 919 (contrat pose.json), 939 (D-CALX 7), 940 (5 assertions et non 3).
