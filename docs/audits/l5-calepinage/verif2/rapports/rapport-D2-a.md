# Rapport vérificateur — lot D2-a (30 tâches) — code lu dans `C:\dev\taqinor-os\.claude\worktrees\l5-verif\`

Chemins `fichier:ligne` ci-dessous relatifs à ce dossier ; lignes vues au 21/11 (quelques dérives de 5-15 lignes par rapport aux clauses, sans conséquence).

### ACAL546 — OK
`frontend/src/pages/ventes/ToitureDesign.jsx:1414` porte `rp9-areas-window`, aucun `rp9-compare` dans `frontend/src` ; `apps/web/src/scripts/roofPro11/matrix.ts:170-205` (`paintComparison` : `if (!tbody) return;` l.177, sixième cellule `fmtMad` l.~204) ; `optimizer.ts:1367` idem ; goldens `.calepinage/.devis/.lead.html` présents ; `matrix.test.ts` CALX114 l.64 ; `TableauComparatif.jsx` n'existe pas.

### ACAL547 — CORRIGER
Faux : « `pickVariantCards` n'est testée nulle part ». Elle l'est par `apps/web/tests/variantCardsPV64.test.ts` (l.32 `expect(cards.length).toBe(3)`, ids triés `['aligned','eastwest','south-max']`, l.59-69). Une quatrième carte `couvre-besoin` fait rougir ces assertions dès que le jeu `MATRIX` a une ligne ≥ 100 %.
Correction : remplacer « Assertions existantes : aucune sur `pickVariantCards` … » par « `apps/web/tests/variantCardsPV64.test.ts` : `toBe(3)` et la liste triée des trois identifiants (l.32-36) à réaligner (la carte `couvre-besoin` s'ajoute quand une ligne atteint 100 %) » ; ajouter ce fichier à `Files:` ; faire poser le test rouge neuf dans ce même fichier (pas dans `optimizer.test.ts`, qui n'importe pas `pickVariantCards`). Corriger aussi le Constat (« pas testée » → « testée par PV64 pour trois cartes »).

### ACAL548 — OK
`optimizer.ts:226-238` (`poserChoixOptimisation`/`poserCibleOptimisation` ne posent que `cible`), lecteur `optimizer.ts:426`, `shadingUi.ts:398` (`filtrerEmplacementsSousSeuil`, seuil 0..1, refus nommé), schéma `roof_layout_v2.schema.json:775` ; `BuilderDom.jsx:132/169` (`rp9-flat-controls`, « Débord ») ; `shadingUi.ts:489` reçoit `recalcDisplays` ; aucun champ seuil dans `frontend/src` (grep).

### ACAL549 — DOUBLON (partiel, avec ACAL881)
`ACAL881` (docs/plans/PLAN_AUDIT_CALEPINAGE.md:1335, lot D6) construit lui aussi, dans un module neuf (`remplissageVide.ts`), les quatre mêmes causes d'un pan sans module (retrait de rive, module plus grand que le pan, seuil d'accès, zones interdites) pour la note de « Remplir automatiquement », dans un AUTRE ordre que 549 (549 : retrait, obstacles, seuil, module ; 881 : retrait, module, seuil, zones) et avec d'autres phrases. Deux fonctions « cause d'un pan vide » divergeraient.
Prémisses de 549 vérifiées : `optimizer.ts:539-571` (phrase « (toit ou obstacles) »), `estimatorBrainV2.ts:968` (`usableAreaM2`), `prefill.ts:1311` (`CLES_RACINE_ATELIER`), `optimisationDocument.ts:50`.
Correction : garder 549 comme SEUL propriétaire (`motifPanVide.ts::causeDuPanVide`, ordre unique) ; ajouter à ACAL881 `@after: ACAL549` et remplacer son « Emplacement `remplissageVide.ts` (quatre tests) » par « appelle `causeDuPanVide` de ACAL549 et n'écrit que la phrase de la note » ; mentionner ACAL881 dans le Constat de 549 (à côté de ACAL397). Note : `prefill.ts` fait déjà 2 013 lignes (la clause dit 1 999) : « lignes nettes = 0 » reste exigible.

### ACAL550 — OK
`services/planche.py:233-330` (`geometrie_de_planche`, pan = `repere`, `modules`), `:85` `GRIS_TEXTE`, `:99` `CONTENU_POSE`, `:1105` `_corps_feuille_toit`, `:1282` `_assainir`, `:1371` `_verifier_absence_d_argent` (n'examine que bandeau/catalogue, le motif document n'y entre pas) ; `tests/test_cal211_plan_pose.py:99` `ReperesDePoseTest` ; `views/sorties.py:325`. (Chemins sous `backend/django_core/apps/calepinage/`.)

### ACAL551 — OK
`layoutEditor.ts:2417-2441` (`previewFreeDrag` garde le dernier aperçu valide, `showMeasure`), `:2652` `endLayoutDrag` ; `freeLayout.ts:102-107` (`FreeCheck.hard`), `:343` `panelCornersUV`, `:129` `toENU`, `:554` `placeFreePanels` (refuse aussi `setback`/`gap`, donc l'ambre est atteignable) ; `viewerOnly.ts:329` `enuToLngLat` ; aucun `silhouetteGlisse.ts`.

### ACAL552 — OK
`shadingUi.ts:253` `heatmapAccessValues`, `optimizer.ts:~420-448` `filtrageSeuil`, aucun appelant de `mesuresCible` dans `apps/web/src/scripts` (grep), `accesSolaireMoyen` jamais rempli ; puces `data-orient` `BuilderDom.jsx:159-161`.

### ACAL553 — CORRIGER
Depuis ACAL414 (déjà sur main) la table des touches est UNIQUE : `apps/web/src/scripts/roofPro11/raccourcisAtelier.ts:27` (`TABLE_RACCOURCIS`, portée `atelier`, `Ctrl + D` l.~52) ; `frontend/src/features/calepinage/RaccourcisAtelier.helpers.js:12` ne fait que `lignesDePortee('atelier').map(...)` : y ajouter deux lignes à `RACCOURCIS` ne ferait rien (ou casserait la dérivation). La clause « Emplacement/Listes figées/Appelants » (`RACCOURCIS` d'abord, « après ACAL414 : … ») est périmée.
Correction : Emplacement : remplacer `frontend/src/features/calepinage/RaccourcisAtelier.helpers.js::RACCOURCIS (…)` par `apps/web/src/scripts/roofPro11/raccourcisAtelier.ts::TABLE_RACCOURCIS` (deux lignes portée `atelier`, touches `c` et `v`, modificateur `ctrl`) ; `Files:` : retirer `RaccourcisAtelier.helpers.js`, ajouter `raccourcisAtelier.ts` et son test s'il existe (`clavier.test.ts` lit la table) ; Listes figées : `ACTIONS_RACCOURCIS` (`entreeMoteur.ts:600`, huit actions) et `TABLE_RACCOURCIS`. Le reste (collage, dupliquer `layoutEditor.ts:1080`, `construireRaccourcis` `roof-tool-pro11.ts:4248`, Ctrl+D = obstacle l.4271) est exact.

### ACAL554 — CORRIGER
Faux : « la fonction pure réutilise `CLES_JEU` » / « `CLES_JEU` … le report de pan lit la même liste ». `jeuReglages.ts:29` : `CLES_JEU = ['roofType','pitchDeg','facingAzimuthDeg','facingManual','neededAuto']` — SANS `moduleId` (champ de pan : `types.ts:690`) et AVEC `neededAuto` (que la tâche ne veut pas copier : le besoin du pan cible lui est propre).
Correction : Jumeaux/Listes figées : « `reglagesDePan` copie `moduleId` + les clés de `CLES_JEU` sauf `neededAuto` ; `CLES_JEU` inchangée (elle ne porte pas `moduleId`) » ; préciser « source sans `moduleId` ⇒ le pan cible repasse au module par défaut (`delete a.moduleId`, comme `zones.ts:878`) » ; `facingManual` suit la source (retirer « à vrai » ou le justifier). Le reste est exact (`zones.ts:361` `createZones`, `roof-tool-pro11.ts:2694` `selectArea`, `ZonesDeps` sans `selectArea` : à ajouter).

### ACAL555 — CORRIGER
`tests/test_acal_garde_empreintes.py:122` (`test_chaque_cle_du_schema_est_classee`) exige une classe d'empreinte pour CHAQUE propriété RACINE du schéma (`CLASSEMENT_RACINE`, l.36-70). Ajouter `motifsPansVides` à la racine rougit ce test ; la tâche ne cite ni ce fichier ni la classe (`Assertions existantes`/`Files` ne l'ont pas).
Correction : ajouter `backend/django_core/apps/calepinage/tests/test_acal_garde_empreintes.py` à `Files:` et à « Assertions existantes » (« `CLASSEMENT_RACINE` reçoit `motifsPansVides` : classe `DOCUMENT` — versionnée, jamais « imprimée » : ce n'est pas un chiffre du devis ; `imprimee` exigerait d'élargir `apps.ventes.domain.geometrie.CLES_IMPRIMEES`, hors lane ») ; test : « la clé est classée `document` ». Le reste est exact (schéma racine `additionalProperties: true`, `valider_document` nomme le chemin pointé `io_layout.py:262`).

### ACAL557 — OK
`tests/test_cal223_contrats.py:84` `SANS_PRODUCTEUR_PUR`, `:439` `POSES_AVANT_LEUR_ROUTE`, `:535-546` `InventaireDesEchantillonsTest` ; `models.py:1480` `ModePose`, `:1557` `Role` ; `scripts/check_contrats_calepinage_deux_moities.py` (cite le nom des deux côtés) et `frontend/src/api/calepinageApi.js` (bloc de commentaires de fin) ; `gabarits_dossier_reglementaire.json` existe.

### ACAL558 — OK
`models.py:1455-1622` (champs, `clean`, contrainte unique `company+code`), `:174` FK `SET_NULL`, `services/catalogue_fixation.py:102/115` (`systemes_actifs`, `systeme_de_societe`), `views/consommation.py:40-48` (patron `ScopedPermission`/`CAL_VOIR`/`CAL_GERER`), `views/gabarits_dossier.py`, `urls.py:73-86` ; `admin.py` n'enregistre aucun système ; `tests/test_structure_urls.py:83`.

### ACAL559 — OK
`atelier/Fixation.jsx:33` (« LIMITE CONNUE »), `reglages/ReglagesGabarits.jsx`, `module.config.jsx:134-173` (route `reglages/gabarits` avant `/:id`), `api/calepinageApi.js:423` (`gabarits`), `calepinageApi.golden.json` + test, `module.config.test.jsx:89`, aucun `SystemeFixation` dans `frontend/src`.

### ACAL560 — OK
`Fixation.jsx:190-194` (`<input type="text" data-testid="acal82-champ-systeme">`), `Fixation.test.jsx` (5 occurrences du hook, `fireEvent.change` l.122 et 154), `atelier/onglets.js:86` (clé `fixation`) ; hook absent de tout e2e.

### ACAL561 — OK
`services/degagements.py:81/100/159` (`CLE_RETRAIT`, `allees_circulation`, `normaliser_section_degagements`), `edges.ts:66` (`EDGE_TYPES` = 6 dont `inconnue` ⇒ 5 types), `lib/roofSetbackEdge.ts:9-15` (retrait par arête s'ajoute), `PanneauAllees.jsx` (patron), `contract_samples/parametres_calepinage.json:10` (`exemple.degagements`), `reglages/ReglagesSimulation.jsx` (733 l., `servis` = GET).

### ACAL562 — OK
`roof-tool-pro11.ts:4152` (`degagementsSociete: opts.reglagesAtelier?.degagements`), `types.ts:142-147`, `edges.ts:36/87/421`, `edgesUi.ts:212/232-235` (aucune saisie de retrait, il ne préserve que `retraitM`), `lib/roofSetbackEdge.ts:182` `supplementsParArete`, `roof-tool-pro11.ts:2383` `close` ; `$defs/edge` du schéma : `index,type,manuel,retraitM`, `additionalProperties: true`. Tests `edges.test.ts`/`edgesUi.test.ts` existent.

### ACAL563 — OK
`services/lestage.py:56` `PARAMETRES` (10 entrées comptées), `:85` `NOMBRES_DE_FORME`, `:94` `CLES_DE_STRUCTURE`, `:120` `normaliser_section_lestage`, `:605/648`, `tests/test_lestage_parametre.py:56/188`.

### ACAL564 — OK
Calcul de la clause vérifié à la main : 4×6 modules au pas de 1 m dans [0,4]×[0,6], coin ≤ 0,8 m d'un sommet (centres à 0,707 m) = 4, bande ≤ 1,0 m d'une arête = 12, centre = 8 ; `planche.py:233` (`points`, `modules` en mètres), `tests/test_calx17_masse_lestage.py:122`.

### ACAL565 — OK
`planche.py` ne contient aucun « lest » (grep) ; `services/feu_vert.py:50` `PIECES_EXECUTION`, `views/sorties.py:94/175/296-330` (`inventaire_des_sorties`, `porte_execution`, patron `plan-pose.pdf`), `calepinage_sorties.json` : exactement 12 codes ; tests `test_calx321…`, `test_calx327…`, `test_acal_portee_approbation.py` existent.

### ACAL566 — CORRIGER
Contradiction interne : le Given dit que A (« tuiles ») est retenu alors que C (couvertures vides = compatible) l'est aussi, puis « plusieurs compatibles : refus listant les compatibles » — A et C étant compatibles, la règle écrite refuse au lieu de retenir A.
Correction : « le système retenu est l'UNIQUE actif dont `couvertures` CONTIENT celle du lead ; les systèmes à `couvertures` vide ne sont retenus que si aucun système ne déclare cette couverture et qu'il n'y en a qu'un ; plusieurs déclarants : le refus existant ne liste que les déclarants ; aucun déclarant ni système vide unique : règle d'aujourd'hui ». Test rouge à compléter : « A tuiles + C vide + lead tuiles ⇒ A (source `couverture`) ». Facultatif : migrations lues jusqu'à `0035_acal400_brouillon_serveur.py` (ACAL400 est construite) : la clause « dernière lue 0034, 0035 réservé » est périmée → « 0035 pris, prochain libre 0036 ».

### ACAL567 — CORRIGER
Champs de modèle sans migration : `models_fiche_technique.py` gagne trois colonnes, mais la migration est dans ACAL570 (plan stock), qui est `@after` 567 : les tests de 567 tournent sur une base bâtie par les migrations et échoueraient (colonnes absentes), et `makemigrations --check` serait rouge sur le groupe.
Correction : fusionner ACAL570 dans ACAL567 (ajouter la migration additive de `apps/stock/migrations/` à `Files:` de 567 et à « Emplacement », « Persistance : migration additive incluse ») et supprimer ACAL570 du plan stock ; OU, si la propriété des migrations stock l'interdit, inverser : ACAL570 pose champs ET migration, ACAL567 devient `@after: ACAL570` limité au serializer/sélecteur/goldens. Prémisses vérifiées : `serializers_fiche_technique.py:367-383` (règle croisée `struct_masse_kg_m2`↔`struct_notice`, `refus_etat`), `selectors_fiche_technique.py:26` (bloc PLAT par `type_fiche`), goldens et tests listés existent, aucun « serrage » dans `apps/stock`.

### ACAL568 — OK
`services/fixation.py:399-431` (`bom_de_fixation`, 2 appelants `views/fixation.py:70` et `table_fixation`), `services/electrique.py:1227` (`resoudre_materiel`, `produits.module`, lecture par `apps.stock.selectors`), `tests/test_calx359…`, `test_calx335…` existent ; dépend de ACAL567/566/559 (`@after` présent). (Même remarque facultative sur le numéro de migration que 566.)

### ACAL569 — OK
`catalogue_fixation.py:31` `BASES` (6), `fixation.py:105` `_grandeurs_du_document` (compte les rangées par `_rangees_orientees`), `services/rangees.py:94`, `schema panel` = `cx,cy,face,n,rangee` (aucune orientation avant ACAL601, qui écrit `geometry.panelOrientation`) ; `@after: ACAL601` correct ; tests `GrandeursDuDocumentTest` (:126) et `RegleDeQuantiteTest` (:130) existent.

### ACAL572 — OK
`selectors.py:1091` `registre_des_reglages()` (sans argument, dict section→lignes ; la clé `lestage` s'y ajoute sans casser `simulation`/`electrique_societe`), `services/lestage.py` 10 paramètres, `SECTIONS_LECTURE_SEULE` `selectors.py:54`, aucun écran lestage dans `reglages/`. Note : les lignes existantes portent `reference`/`type` — la clause annonce `texte`/`bloc` : ce sont des clés en plus, pas un conflit.

### ACAL573 — OK
Schéma `$defs/zone/properties` : 21 clés exactement (`id … cotesReleve`), `CLASSEMENT_PAN` 21 clés (`test_acal_garde_empreintes.py:74`), `ImporterLayoutTest` `test_cal216_import_export.py:59`. À signaler (autre lot) : ACAL510 (D1, docs/plans/PLAN_AUDIT_CALEPINAGE.md:1085) ajoute AUSSI ces deux propriétés au schéma et à l'exemple — contraire au « SEUL » et à « exemple inchangé » de 573 ; retirer le schéma des `Files:`/`Emplacement` de ACAL510 (il est `@after` 573).

### ACAL574 — CORRIGER
Chevauche ACAL510 (D1, plan :1085), qui crée déjà `AreaRecord.existant`/`anneeMiseEnService`, la case « Modules déjà en place », le refus du glissé/suppression/re-pavage et `panExistant.ts::motifPanExistant` avec SON texte (« Pan 1 : modules déjà en place — décochez-le d'abord »). 574 définit une seconde `motifPanExistant` dans `zones.ts` avec un autre texte, une autre étiquette de case (« Pan existant »), et n'a pas `@after: ACAL510` alors que son test et sa preuve en direct en dépendent (aucun champ `existant` sur `AreaRecord` aujourd'hui : `types.ts:653-700`).
Correction : `@after: ACAL573, ACAL510` ; supprimer « (une seule fonction `motifPanExistant`) … ≈ 12 l. dans zones.ts » et écrire « réutilise `panExistant.ts::motifPanExistant` (ACAL510), même texte, même étiquette « Modules déjà en place » » ; périmètre propre de 574 = pivoter, redimensionner (`zones.ts:102/126`, fonctions pures : le garde se pose dans `createZones`), changer de module (`zones.ts:878`), re-paver (`optimizer.ts:885/1244`) et bouton grisé ; le refus du glissé/suppression/re-pavage par `beginLayoutDrag` reste à ACAL510 (le retirer de 574 ou de 510, pas des deux). Corriger « Personnaliser la disposition » : le bouton est `rp9-layout-toggle` (« Déplacer les panneaux », `layoutEditor.ts:259`).

### ACAL575 — OK
`planche.py:641` `_dessin_des_modules`, `:735` `_entrees_de_legende`, `fixation.py:105` ; `GRIS_MODULE` n'existe pas encore (à créer, pas une prémisse fausse) ; tests cités existent (`test_acal_planche_module_document.py`, `test_cal178_dxf.py`, `test_cal179_export_tableur.py`, `test_calx310_plan_cablage.py`, `test_acal_rangees_orientees.py`, `test_cal172_legende.py`).

### ACAL576 — OK
Vérifié : 20 colonnes, coupure tous les 8, n = 1 ⇒ bandes aux colonnes 9 et 18, rangées 8+8+2 ; `roof-tool-pro11.ts:491-497` (`obstructionRings`/`obstructionClearances` parallèles), `lib/roofGrid.ts:57/80`, `lib/freeLayout.ts` `geomAxes`, `lib/roofPro2.ts:138`, `zones.ts:1122/1303`, `prefill.ts` (2 013 l.) ; `@after: ACAL586` (existe au plan :1146).

### ACAL577 — OK
`services/traduction.py:124-163` (`Traduction`, `regle_ilots`), `:571` `entree_depuis_layout` (appelée par `villa_service.py:219` ; `selectors.py:1202` et la commande dry-run ne la citent qu'en docstring), `:653` `Rives(laterale_m=…)`, `core/calepinage/ilots.py:52/68/96` (112 l.), `core/calepinage/types.py:191`, `test_ciq136_contraintes_site.py:46/67`.

### ACAL578 — OK
`catalogue_fixation.py:31` (six bases), `planche.py:368` `_surfaces_de_pose` (`engine.tables`), `poseSurfaces.ts:740` `positionsAppuis`, schéma `appuisOmbriere` = `pasM, sectionM` ; calcul des 7 pieds vérifié (k = ⌊2,4/1,15⌋ = 2 ; ⌈12/2⌉ + 1) ; `@after ACAL587, ACAL575` présents.

## OPTIONNEL (5 lignes)
- Les lanes `calepinage/fixation` (561, 566, 568, 569) et `calepinage/lestage` (563-565, 572) se partagent des fichiers (`ReglagesSimulation.jsx`, `parametres_calepinage.json`, `test_cal223_contrats.py`, `fixation.py`, `catalogue_fixation.py`, `test_calx359…`) : `plan_lanes.py` les unira ; ne pas s'en étonner.
- ACAL578 écrit « BASES (6 → 9 entrées) » alors que ACAL569 en ajoute aussi quatre : l'effectif dépend de l'ordre (13 si 569 d'abord).
- ACAL572 compte « dix paramètres » ; ACAL939 (D7) en retire deux (pesanteur, masse volumique de l'air) : dire « les paramètres de `PARAMETRES` ».
- Dérives de lignes (non bloquantes) : `prefill.ts` 2 013 l. (clauses : 1 999), `roof-tool-pro11.ts` 4 424 l., `layoutEditor.ts` 3 225 l., `zones.ts` 1 493 l., `optimizer.ts` 1 839 l.
- ACAL559/558 : `produit_id` est libre côté POST ; le lire borné société (`valid_produit_ids`) à la lecture suffit déjà, rien à ajouter.

## Non vérifié
Aucune tâche du lot sauf en profondeur partielle : pour 559, 560, 565, 572, 578 j'ai confirmé emplacements et prémisses structurelles mais pas ouvert chaque fichier de test en entier ; je n'ai pas relu ACAL470/586/587/601 en entier (seulement leur existence au plan).
