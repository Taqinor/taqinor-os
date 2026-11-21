# Rapport de vérification — lot D2-b (29 tâches) — code lu : `C:\dev\taqinor-os\.claude\worktrees\l5-verif\` (HEAD 45eafba77)

Bilan : 12 OK, 11 CORRIGER, 6 DOUBLON, 0 SANS OBJET, 0 À SCINDER (593 est traité en DOUBLON + scission proposée).
Aucune tâche non vérifiée : les 29 ont leur « Emplacement » ouvert et le point 1 cherché.

## Constat TRANSVERSE (touche 579, 584, 585, 593, 608 — à corriger dans la ligne `Code net`)
Garde CI `scripts/check_forme_code.py` règle FICHIER_MUR (`scripts/forme_code/fichier_mur.py:12-30`) : un fichier ≥ 2 000 lignes ne grossit que du
budget `lignes nettes attendues ≤ N` (regex exacte `scripts/forme_code/socle.py:33`, chemin EXACT entre backticks). Aucune des tâches du lot n'écrit cette
phrase (grep : 0) et les tailles citées sont périmées dans l5-verif : `prefill.ts` 2 013 l. (cité 1 999), `roof-tool-pro11.ts` 4 424 l. (cité 4 354),
`scene3d.ts` 3 130 l. (cité 3 115). Budget absent = 0 ⇒ tout +1 ligne logique rougit la CI. Correction pour chaque tâche concernée : écrire sur la ligne
`Code net` « `apps/web/src/scripts/roofPro11/prefill.ts` … lignes nettes attendues ≤ N » avec le N réel (voir chaque entrée) et les tailles à jour.

## Doublons avec des tâches HORS lot (à arbitrer par l'orchestrateur avant l'entrée au plan)
- ACAL593 + ACAL599 (repères de chantier, clé `reperesChantier`) = ACAL532 (D1, `INSERTION-PLAN…md` l. 207 : même fonctionnalité, clé `reperes`, MÊME fichier neuf `apps/web/src/scripts/roofPro11/reperesChantier.ts`).
- ACAL606 + ACAL609 + ACAL607 = ACAL919 + ACAL920 + ACAL917 (D7) : anti-ombrage du Terrain par la latitude, alerte « rangées trop serrées », kWc 124,96 du tableau Site.
- ACAL602 + ACAL603 = ACAL933 (D7, `INSERTION…md` l. 137) : échelle imprimée + cotes du toit seul (même clé `etendue_toit`), avec une CONTRADICTION de conception (voir 602).

---
### ACAL579 — CORRIGER
Trois fautes, preuves lues :
1. Persistance incomplète : `prefill.ts::reconcilier…` (l. 1359-1362) recopie dans chaque pan toute clé relue absente de `CLES_PAN_ATELIER` (l. 1319-1322) tant que `!(cle in z)` ⇒ vider le champ « Portée entre pieds » ne retire jamais `zones[].porteeEntrePieds` (la clé relue revient). Précédent : `pitchSource` est dans `CLES_PAN_ATELIER` (l. 1320). De plus la relecture « rouvrir le dossier : 7 » exige de lire la clé dans `deserializeLayout` (bloc l. 1540-1560 où `pitchSource` et `geometrieEnregistree` sont lus) et un champ sur `SerializedZone` (`prefill.ts` ~l. 339). L'« Emplacement » ne nomme que `serializeLayout` (2 l.).
   Correction : Emplacement/Persistance = « `prefill.ts::serializeLayout` (émission), `::deserializeLayout` (lecture vers `AreaRecord.porteeEntrePieds`), `::SerializedZone` (+1 champ), `::CLES_PAN_ATELIER` (+1 clé sur la ligne existante) » ; test `prefill.roundtrip.test.ts` : cas « saisir, enregistrer, rouvrir ⇒ valeur relue ; vider ⇒ aucune clé ».
2. Budget FICHIER_MUR (voir transverse) : `prefill.ts` 2 013 l. et `scene3d.ts` 3 130 l. et `roof-tool-pro11.ts` 4 424 l. : « lignes nettes attendues ≤ N » absent ; `prefill.ts` ≤ 2 est incompatible avec 1+2+3 ci-dessus (écrire ≤ 8).
3. Décision D-ACAL-38 : `createScene3d` sert aussi le viewer CLIENT (`viewerFullBoot.ts:245`, `readOnly: true`) ; la tâche écrit « le client voit des pieds espacés, effet voulu » = un ajout visible du client qui n'est pas parmi les quatre autorisés. Correction : soit ne filtrer les triangles que si `!deps.readOnly` (atelier seul), soit marquer la tâche « décision fondateur requise avant construction ».

### ACAL580 — OK
Ouvert : `planche.py::_surfaces_de_pose` (l. 368, aucune clé `appuis`), `_corps_feuille_surface` (l. 1054, « Tables posées : %d » l. 1092), `_corps_feuille_toit` (l. 1105) ; `poseSurfaces.ts` `appuis.pasM/sectionM` (l. 57-60, 356-360) et `positionsAppuis` (l. 740) ; tests cités tous présents (`test_acal_planche_surfaces_pose.py`, `test_cal211_plan_pose.py`, `test_cal172_legende.py`, `test_cal224_perf.py`). `@after ACAL578` couvre la source unique des pieds/poteaux.

### ACAL581 — OK
Ouvert : `core/calepinage/types.py::Kit` (l. 158-215, `modules_par_table` seul, aucun `rangs_par`/`rowsPerFrame` : grep 0) ; `serialisation.py::_kit`/`_kit_depuis` (l. 191-212) ; `schema.json` kit (l. 70-83, pas de `additionalProperties:false` sur le kit) ; golden `apps/stock/golden/fiche_technique_selecteurs.json` fige bien le `repr` de `Kit` (l. 37, 82) ; `selectors_fiche_technique.py:341` et `contenance_declaree.py:126` fabriquent des `Kit(` ; `CLASSEMENT_PAN` existe (`test_acal_garde_empreintes.py:74`) ; `KitsDerives` présent (`test_calepinage_types.py:29`).

### ACAL582 — CORRIGER
Faute de conception, preuve : le pas anti-ombrage d'un toit plat vient de `traduction.py::_politique` (l. 504-524 : `AntiOmbrage(latitude_deg)`), dont `politique_pas.py::AntiOmbrage.hauteur_module_m` (l. 211-214) = `kit.cote_dans_la_pente_m × sin(inclinaison)` = UN module de haut. Avec un châssis 2 rangs la table est 2 fois plus haute : l'ombre portée est sous-estimée de moitié et les rangées se font de l'ombre. La tâche dit « poseur.py et moteur.py ne changent PAS » mais ne touche pas `politique_pas.py`.
Correction : ajouter à Emplacement/Files `backend/django_core/core/calepinage/politique_pas.py::AntiOmbrage.hauteur_module_m` (hauteur = `rangs_par_table` × côté dans la pente × sin(inclinaison), 1 l.) + cas rouge « châssis 2 × 10 à 30,4° ⇒ entraxe appliqué ≥ celui d'une table de 2 modules de haut » ; ajouter `core/tests/test_calepinage_politique_pas.py` aux Files. Le reste (types.py l. 191-215, `_kit` l. 254, `ContraintesMoteurTests` l. 46, `DessineEgaleCompte` l. 37, `garde_fous.py:149-154`) est exact.

### ACAL584 — CORRIGER
Seule faute : budget FICHIER_MUR (voir transverse) pour `roof-tool-pro11.ts` (4 424 l., cité 4 354). Écrire « `apps/web/src/scripts/roofPro11/roof-tool-pro11.ts`… » : le chemin cité en Files est `apps/web/src/scripts/roof-tool-pro11.ts` (exact) ; ajouter « lignes nettes attendues ≤ 10 ». Prémisses vérifiées : `packConfig` `uStart = uMin + setbacks.lateralM` (`estimatorBrainV2.ts:1074,1192`), `departagerRemplissage`/`translater` (`optimizer.ts:1769,1752`), `checkPanelAt` (`freeLayout.ts:321`, 1 appelant `layoutEditor.ts:2447`), `alignPanels` (`freeLayout.ts:781`), sélecteur `rp9-priorite-remplissage` (`roof-tool-pro11.ts:3253`), tests cités présents.

### ACAL585 — CORRIGER
1. `@after` manquant : le Constat dit « ordre : après ACAL583 » mais la ligne ne porte que `@after: ACAL581`. ACAL583 (`docs/WEB_PLAN.md:923`) fournit l'option `chassis` de `packConfig` dont dépend tout le comportement (PACT11). Correction : `@after: ACAL581, ACAL583`.
2. Même défaut de persistance que 579 : `CLES_PAN_ATELIER` (`prefill.ts:1319`), lecture dans `deserializeLayout` (l. 1540-1560) et `SerializedZone` non nommés ; « vider les champs rend le pavage d'aujourd'hui » est faux sans eux (la clé relue revient, `prefill.ts:1359-1362`). `prefill.ts` ≤ 2 insuffisant (≤ 8).
3. Budget FICHIER_MUR : `prefill.ts` 2 013 l., `roof-tool-pro11.ts` 4 424 l. sans « lignes nettes attendues ≤ N ».

### ACAL586 — OK
Ouvert : schéma `$defs.zone.properties`, `CLASSEMENT_PAN`/`test_chaque_cle_du_schema_est_classee` (`test_acal_garde_empreintes.py:74,125-130`) ; `layout_hash` hache le pan entier (`ventes/domain/geometrie.py:319-325`) donc « imprimee » est juste ; `valider_document` nomme le chemin (`io_layout.py:259-266`) ; `ImporterLayoutTest` (`test_cal216_import_export.py:59`) ; `ilots.py::bandes_allees/zones_allees` (l. 52, 68). Formule de bande vérifiée (k=1 : N·c ; k=2 : (2N+n)·c).

### ACAL587 — OK
Même lecture que 586 ; arithmétique vérifiée (m=12, p=1,15, valeurM=2,4 ⇒ k=2, 7 pieds ; portée < pas ⇒ k=1 ⇒ 13). `scene3d.ts:2071-2074` confirme « N+1 triangles ».

### ACAL588 — OK
Ouvert : `selectors.py::calepinage_retenu_pour_devis` (l. 727), `asbuilt.py::conception_du_chantier` (l. 191), `planche.py::_rendre_plan_pose_svg` (l. 1482, garde d'argent incluse), `PlancheRefusee` (l. 119), `Calepinage.layout_hash` (`models.py:96`), `layout.py::empreinte_document` (l. 136), appelants de `rendre_plan_pose_pdf` (`pack_technique.py:170,504`, `views/sorties.py:309`), `bloc_calepinage_retenu` (`installations/calepinage_retenu.py:43`). Frontière inter-apps respectée (lecture ventes par `selectors`).

### ACAL590 — OK
Ouvert : `html_de_planche(svg)` (`planche.py:1243`, A3 paysage figé, 5 appelants exacts), `plan_cablage.py::_plan_de_cablage` (l. 166, couleurs par ordre d'apparition `PALETTE_CHAINES` `chaines.py:979`, lève `PlanCablageRefuse` sans chaîne : la tâche doit l'attraper pour « modules neutres + MENTION_NON_CHAINE » — dit), `production.py::numeros_des_modules` (l. 65), `cle_de_module` (l. 85). Séquence `@after ACAL601` correcte.

### ACAL591 — CORRIGER
Faute : la clause mesure « le bord extrême d'un module (cotes `module_m` du pan) » — c'est exactement le défaut d'ACAL601 : `planche.py::_dessin_des_modules` (l. 641-690) pose `module_m[0]` en X sans lire l'orientation. Mesurer N/S/E/O avec `module_m` donnerait des marges fausses pour tout module posé en portrait ou tourné par l'azimut.
Correction : remplacer par « bord extrême = min/max des 4 sommets rendus par `coins_du_module(pan, centre)` (ACAL601, `@after` transitif via 590) ; si `coins_du_module` rend `None` (orientation non enregistrée) ⇒ aucune distance et le motif « orientation du module non enregistrée : distances non calculées » ». Mutant à ajouter : poser `module_m[0]` en X ⇒ échec sur un module portrait.

### ACAL592 — OK
Ouvert : `fixation.py::_grandeurs_du_document` (l. 105-162, boucle par pan, `_pas_du_pan`/`_segments`/`_rangees_orientees` l. 65-100), `_quantite` (l. 193), `_lignes_de_fixation` (l. 212), `bom_de_fixation` (l. 399), `table_fixation` (l. 433) ; `test_aucune_constante_hors_0_1_2` présent (`test_calx359_bom_fixation.py:110`).

### ACAL593 — DOUBLON (avec ACAL532, D1) + scission proposée
1. ACAL532 (`INSERTION-PLAN…md` l. 207) pose la MÊME couche : repères de chantier (ancrage antichute à rayon saisi, passage de câble…) dans l'atelier, persistés, cercle du rayon, fichier neuf `apps/web/src/scripts/roofPro11/reperesChantier.ts`, `serializeLayout`, `CLES_RACINE_ATELIER` ; seule différence : clé `reperes` {lng,lat} (532) contre `reperesChantier` {point,type…} (593/599) et l'impression A4 (593 seulement). Deux constructeurs créeraient le même fichier avec deux contrats.
   Correction proposée : garder le contrat 599 (clé `reperesChantier`) ; réécrire ACAL532 comme la moitié ATELIER de 593 sur la clé `reperesChantier` (`@after: ACAL599`) ; réduire ACAL593 à la moitié IMPRESSION (`planche_pan.py::_reperes_de_chantier`, `@after: ACAL590, ACAL532`) ⇒ ce qui scinde aussi 593 (atelier TS + planche Python dans une seule tâche, deux lanes). 532 propose en plus un panneau créé à l'exécution sous `rp9-mesure-list` (pas de `BuilderDom.jsx`, aucun golden HTML à régénérer) : à préférer à la version 593 (BuilderDom + 3 goldens).
2. Faux dans la tâche : « `prefill.ts` reste à 1 999 l. … ≤ 0 ligne nette (l'import et l'appel remplacent deux lignes vides) » — `prefill.ts` fait 2 013 l. et l'import + l'appel sont 2 lignes LOGIQUES (les lignes vides ne comptent pas, `fichier_mur.py`). Écrire « lignes nettes attendues ≤ 2 » (et ≤ 14 pour `roof-tool-pro11.ts`, 4 424 l.).
3. Omission : les points `[lng, lat]` doivent suivre le recentrage ; voir ACAL599 (`CHEMINS_TRANSLATES`).

### ACAL594 — CORRIGER
1. Écriture incomplète du module : la tâche écrit seulement `modules[]` + `geometry.moduleId` et dit « reproduit l'écriture de `moduleSelect.ts` ». Or `moduleSelect.ts::ecrireModulesDansDocument` (l. 420-465) écrit AUSSI `zones[].geometry.kwc` (count × pmaxWc ÷ 1000), `result.kwc` (somme) et `panelWatt` (module majoritaire en modules posés). Sans eux la variante créée garde le kWc et le `panelWatt` du module A (le devis lit `panelWatt` d'abord : `ventes/domain/geometrie.py:474,707`) ; le comparatif (`_ligne_comparaison` : `kwc`) mentirait.
   Correction : ajouter à « Then » : « chaque variante reçoit aussi `zones[].geometry.kwc` = nombre de modules × `pmaxWc` ÷ 1000, `result.kwc` = somme, et `panelWatt` = `pmaxWc` du module choisi ; `result.annualKwh` et la simulation de la variante sont marqués périmés (aucune production recopiée de A) » ; cas rouge « kWc de la variante B = n × 430 ÷ 1000, pas celui de A ».
2. « `views/calepinages.py` n'est PAS touché » est faux : les actions à corps JSON y sont déclarées dans `parsers_par_action` (`views/calepinages.py:356-367`, y compris `import_layout` greffée depuis un autre fichier) ; sans `'variantes_par_module': [JSONParser]` le fuzz api-fuzz (tous checks bloquants) enverra du multipart. Ajouter la ligne (+1 l., fichier 1 958 l.) et `views/calepinages.py` aux Files.
3. Nouvelle route POST ⇒ l'inventaire `docs/openapi-schema.yml` change et `scripts/check_openapi_schema.py:19` rougit si l'instantané n'est pas régénéré (16 autres tâches du plan citent ce fichier ; format `- post /api/django/calepinage/moteur/pose/ -> …` l. 680 et miroir `/api/v1/…` l. 4770). Ajouter `docs/openapi-schema.yml` aux Files.
(Pour le reste : `creer_variante` `services/variantes.py:85`, `modules_disponibles_du_calepinage` `modules_stock.py:168`, `module_du_pan` `io_layout.py:85`, `MODULES_RATTACHES` `rattachements.py:169`, id `produit-<pk>` via `_entree_module`, tests présents : exacts.)

### ACAL595 — CORRIGER (mineur)
`variantes_comparer.json` porte DEUX jeux de `lignes` : `exemple` (l. 10) ET `exemple_vide` (l. 191) ; la tâche ne complète que `exemple`. `VariantesCompare.test.jsx:49` lit `exemple_vide` (`CONTRAT_UNE_SEULE`) et le contrat est `forme_serveur: complete` (clé en trop ou en moins = rouge, `check_api_shapes.py`). Correction : « clé additive `module` sur chaque ligne de `exemple` ET de `exemple_vide` (valeur `null` ou module B), plus un cas `mixte` dans `exemple` ». Le reste (`_ligne_comparaison` `selectors.py:435`, `module_du_pan`, test `test_prod2_comparaison_variantes.py`) est exact.

### ACAL596 — OK
Ouvert : `selectors.py::resultat_servi` (l. 1230), table `electrique.affectation` (`chaines.py:1312`, `plan_cablage.py::_plan_de_cablage`), `fixation.py::resoudre_systeme` (l. 347), `calepinage_simule_reel` (`acal_livrables_helpers.py:125`), `SystemeFixation` (`models.py:1455`), « connecteur » : 0 occurrence dans apps/calepinage (hors tests), `ChecklistTemplate`/`ChantierChecklistItem` (`models_chantier.py:26,694`). `@after ACAL588` (même fichier) correct.

### ACAL598 — OK
Ouvert : `catalogue_fixation.py::BASES` (6 bases, l. 31), `models.py::ComposantFixation.Role` (l. 1557, 7 valeurs aujourd'hui : rail, pince_milieu, pince_fin, crochet, embout, lest, visserie ⇒ 8 après), `edges` type `egout` et `buildings[].hauteurM` + `source` obligatoire (schéma l. 965-1010, 2427-2430), test d'égalité des rôles `test_calx358_systeme_fixation.py:90-92` (à réaligner, nommé), `ROLES` borne supérieure `test_calx335…:30`. Dernière migration réelle = 0035 (la tâche dit « 0034 » et demande de relire le numéro : sans conséquence).

### ACAL599 — CORRIGER (+ voir DOUBLON ACAL532/593)
Deux gardes existantes rougissent et ne sont ni nommées ni dans `Files:` :
1. `test_acal_garde_empreintes.py::test_chaque_cle_du_schema_est_classee` (l. 125-130) exige que toute clé racine de `properties` soit dans `CLASSEMENT_RACINE` (l. 36-70) : `reperesChantier` doit y être classée `DOCUMENT` (précédent : `'alleeTechnique': DOCUMENT`, `'parcelle': DOCUMENT`).
2. `repere.py::CHEMINS_TRANSLATES` (l. 60-80) + `test_acal_derive_repere.py::test_le_schema_est_entierement_couvert` (l. 225-235) : toute coordonnée `[lng, lat]` du schéma doit être translatée au recentrage ou exemptée. `reperesChantier[].point` est un couple GPS : sans `'reperesChantier[].point': ('couple', 'lng_lat')` le test est rouge et un repère ne suit pas « recentrer sur le lead » (même classe que ACAL352 `bout`, DONE).
Correction : Files += `backend/django_core/apps/calepinage/services/repere.py`, `backend/django_core/apps/calepinage/tests/test_acal_garde_empreintes.py`, `backend/django_core/apps/calepinage/tests/test_acal_derive_repere.py` ; Listes figées : `CLASSEMENT_RACINE` (+`reperesChantier`), `CHEMINS_TRANSLATES` (+1 entrée) ; cas rouge « recentrage de 500 m ⇒ le point du repère se déplace du même vecteur ».
Note : la garde `scripts/check_calepinage_cles_document.py` exige aussi un ÉCRIVAIN de toute clé racine (hors tests) : ACAL599 « SEUL » ne passe cette garde que si ACAL593/532 (atelier) est dans le même merge ; le dire.

### ACAL600 — CORRIGER
Le bouton doit n'apparaître qu'« en niveau expert » (Then + `AtelierPanneaux.test.jsx`), mais ce niveau vit UNIQUEMENT dans `atelier/Rail.jsx:169` (`useModeExpert`, état local de `modeExpert.js:38-45`, mémoire localStorage par composant) ; `AtelierPanneaux.jsx` n'a aucune notion d'expert (grep : 0) et c'est lui le PARENT du rail (`module.config.jsx:183` : « Le rail est monté par AtelierPanneaux.jsx »). Un second `useModeExpert` dans `AtelierPanneaux` ne se resynchronise pas quand l'utilisateur coche « Mode expert » dans le rail. `Rail.jsx` et `modeExpert.js` ne sont pas dans `Files:`.
Correction : ajouter à l'Emplacement « remonter `useModeExpert` dans `AtelierPanneaux.jsx` et le passer au `Rail` en props (`expert`, `onBasculerExpert`) » avec `Rail.jsx` en Files (+ son test `Rail.test.jsx`), ou monter le bouton dans un onglet déjà expert du rail. Le reste est exact : `cal-lien-variantes` (`AtelierPanneaux.jsx:166`), `LIGNES_TABLEAU` (`VariantesCompare.jsx:102`), redirection `/calepinage/:id/variantes` (`module.config.jsx:190`), `calepinages.modulesDisponibles` (`calepinageApi.js:228`), golden `CALEPINAGE_GOLDEN_ECRIRE` (`calepinageApi.golden.test.mjs:136`).

### ACAL601 — OK
Ouvert : `_dessin_des_modules` (l. 641-690, grand côté `module_m[0]` en X, aucun azimut), `_modules_du_pan` (l. 464, ne lit que `cx/cy/n/rangee`), `rangees.py::_axes` (l. 42), `inferPanelPose` (`proposition.ts:3335`, mêmes axes u/f), `prefill.ts:1048,1057` n'écrit que `{cx, cy, face}` (+`angleDeg` libre), `$defs.zoneGeometry`/`$defs.panel` (schéma l. 630, 693), `__all__` (`planche.py:50`), tests nommés présents (`test_acal_planche_module_document.py:53,73,79,86` [2.172, 2.278, 2.278]). Formule cohérente avec `u = (−cos az, sin az)`, `f = (sin az, cos az)`.

### ACAL602 — DOUBLON (avec ACAL933, D7) — et contradiction de conception
`_echelle_nommee` (`planche.py:707-724`) arrondit bien au rang supérieur (51,9 ⇒ 100), prémisse exacte ; tests `test_cal194_plans.py:118-134` exacts. Mais ACAL933 (`INSERTION…md` l. 137) traite le même défaut à l'opposé : « tracé calé sur une échelle NORMALISÉE, mention identique » (`_echelle_de_dessin` change la taille du dessin), alors que 602 déclare hors périmètre « choisir une échelle normalisée (changerait la taille du dessin) » et imprime 1/52. Deux constructeurs, deux comportements pour la même ligne de PDF.
Correction : garder 602 (plus petit, `haiku`, pas de changement de taille) ; supprimer la partie (1) de 933 (ou supprimer 933) ; ACAL984 (`@after … ACAL933`) à ré-aligner.

### ACAL603 — DOUBLON (avec ACAL933, D7)
Prémisses exactes (`_corps_feuille_toit` l. 1105-1108 lit `etendue` de `_etendue` l. 525-545 qui réunit contour, pans, modules, zones, obstacles ; `export_dxf._document_dxf` l. 166 `_coter(espace, geometrie.get('etendue'))`). Mais ACAL933 (2)-(4) fait exactement la même chose avec la MÊME clé `etendue_toit` dans les mêmes fonctions (+ une liste « Hors toit »). Correction : garder 603 ; réduire 933 à son point (3) « Hors toit : <repère> » (ou le retirer au profit d'ACAL863 D6 qu'elle cite) ; mettre à jour `@after` d'ACAL984.

### ACAL604 — OK
Ouvert : `export_dxf.py::_rectangle` (l. 93), `_document_dxf` (l. 101-180 : contour puis chaque `pan['points']` ⇒ doublon quand pan = contour, MODULES l. 160-165), `_calque_chaines` (l. 249), `CALQUES` (l. 69) ; `test_la_toiture_porte_le_contour_et_les_pans` attend bien 2 (`test_cal178_dxf.py:60-62`) ; `test_calx235_sld_dxf.py` présent.

### ACAL605 — OK
Ouvert : `plan_cablage.py::_coins` (l. 301), `_forme_de_module` (l. 309-335), `_modules_du_plan` (l. 129-163, porte déjà `module_m` par module), `export_dxf._calque_chaines` (l. 249-282, `_rectangle(centre, cotes[0], cotes[1])`) ; `test_calx310_plan_cablage.py` présent.

### ACAL606 — DOUBLON (avec ACAL919 + ACAL920, D7)
Prémisses exactes (`calepiner` appelle `machine.calculer(surface, parametres, lot, zones)` sans politique `moteur_service.py:233-234` alors que `calculer` accepte `politique` l. 97 ; `SurfaceSol.politique_pas` sans appelant applicatif ; `surface_vers_dict` refuse `SurfaceSol` `test_calepinage_surface_sol.py:170`). Mais ACAL919 (`INSERTION…md` l. 128, `@after: -`, `opus`) fait le même chantier par une autre conception : `sol` DANS `demande`, nouveau `type: 'sol'` dans `core/calepinage/schema.json` et `serialisation.py` (touche le contrat moteur et `hash_entree`), alors que 606 garde `sol` HORS de `demande` et ne touche pas le noyau. Les deux ne peuvent pas être construits (même `calepiner`, même `demandeMoteur`, même `pose.json`, même `ModeTerrain.jsx`).
Correction proposée : garder 606 + 609 (moins invasives : aucun changement de `core/calepinage/serialisation.py`), supprimer ACAL919/ACAL920, ré-aligner ACAL918 (`@after ACAL913, ACAL919` ⇒ `@after ACAL913, ACAL606`) ; reprendre de 919 la clause manquante à 606 : « Chiffre client : le compte du champ suit ce pas (nouveaux rendus) ; devis déjà envoyés inchangés ; dry-run des écarts avant toute réparation » (D-ACAL-36 / règle du 08/10).

### ACAL607 — DOUBLON (avec ACAL917, D7)
Prémisse exacte (`zones.ts:523` appelle `computeSiteStats(stats, ctx.surfacesPose)` sans `moduleFor` ; `panStats.ts:299-300` ne calcule `kwc` que par `moduleFor` ; `SurfacePose.moduleWc` `poseSurfaces.ts:119`). ACAL917 (INDEX l. 376, `@after: -`) a le même fini-quand (176 × 710 W ⇒ 124,96 kWc dans la ligne et le total du site). Garder 607 (Files précis), supprimer 917.

### ACAL608 — CORRIGER
1. Faux : « `prefill.ts` (1 999 l.) ne dépasse pas 2 000 » — il fait 2 013 l. ; FICHIER_MUR s'applique et « lignes nettes ≤ 50 » ne vise pas ce chemin. Écrire « `apps/web/src/scripts/roofPro11/prefill.ts` … lignes nettes attendues ≤ 4 » (appel + 2 champs de `SerializedZoneGeometry` + `orient` par panneau).
2. Cas non couvert, qui fait dessiner un module faux : en placement libre (`freePosed`, `prefill.ts:1038-1050`) chaque panneau peut porter `angleDeg` (rotation propre, CALX113) alors que `grid.panelOrientation` reste celui du pavage ; écrire `portrait` pour un module tourné de 90° ferait dessiner un rectangle debout par ACAL601 (qui ne lit pas `angleDeg`). Correction : « en placement libre, `panelOrientation` n'est écrit que si aucun panneau ne porte d'`angleDeg` non nul ; sinon clé omise » + cas rouge.

### ACAL609 — DOUBLON (avec ACAL920 + ACAL919) + CORRIGER
Doublon : voir ACAL606 (ACAL920 = même alerte « chaque rangée ombre la suivante », chiffres du serveur ; garder 609).
Faute si on la garde : la tâche lit la latitude dans « `doc.document.pin.lat` » et affiche « Épingle du site absente » sinon. Le hook `useDocumentCalepinage.js:150 useLatitudeDuSite(calepinageId, document)` (ACAL251) existe pour exactement cela (`pin.lat` du document, sinon `contexte_geographique.pin` du détail) et sert déjà `HorizonPanel.jsx:99` et `CourseSoleil.jsx:97`. Sans lui, un calepinage neuf à repère servi mais sans `pin` écrit dirait « épingle absente » à tort. Correction : Emplacement/Jumeaux = « latitude lue par `useLatitudeDuSite` (`useDocumentCalepinage.js`) ; aucune seconde lecture de `pin.lat` ».

### ACAL610 — CORRIGER
Faute : la cellule lit `kwc` « de la réponse du moteur », mais après réouverture le plan affiché est reconstruit par `surfacePose.js::reponseDepuisSurface` (l. 213-221) qui ne porte ni `kwc` ni puissance (`plans`, `version_moteur`, `hash_entree`, `_pasRecharge` seulement), branché par `useSurfacePose.js:70-77`. Le kWc s'afficherait « — Puissance non calculable » à chaque réouverture d'un champ enregistré, alors que `moduleWc` et `engine.modules` sont stockés.
Correction : « `kwc` = `reponse.kwc` si présent ; sinon (plan relu) `plan.modules × nombre(saisie.puissanceWc) ÷ 1000` si les deux sont > 0 ; sinon « — » » ; cas rouge « plan relu d'une surface enregistrée à 710 Wc et 176 modules ⇒ 124,96 ». Pas de nouvel écrivain de kWc : même formule que ACAL607 (Jumeaux à le dire).

---
## OPTIONNEL (5 lignes)
- `planche.py` (1 551 l.) reçoit dans la vague 580 (≤ 45) + 590 (≤ 12) + 601 (≤ 90) + 602 (≤ 15) + 603 (≤ 30) ≈ +192 → ~1 743 avant les autres lots : surveiller le mur des 2 000.
- ACAL601/608 : tout calepinage déjà enregistré (sans `panelOrientation`) imprimera des cercles au lieu de rectangles jusqu'à son prochain enregistrement, et ce ré-enregistrement change `layout_hash` (le pan entier est imprimé) donc `layout_stale` des devis liés : à faire confirmer par le fondateur.
- ACAL598 : « `BASES` 8 bases après cette tâche » est faux puisque 598 est `@after ACAL578` (6 + 3 + 2 = 11) ; et le `pourquoi` de `calepinage_fixation_bom.json` énumère les rôles (vocabulaire contrôlé) : y ajouter « échafaudage ».
- ACAL593/600 citent « maquette réalisée » mais `Panneaux.dc.html` / `Main.dc.html` ne dessinent ni « Comparer d'autres modules » ni « Repères de chantier » (seuls « Jinko Tiger Neo 580 Wc » et « Obstacles » y sont) ; ACAL579/584/585 citent une rubrique « Personnaliser la disposition » absente de la maquette (seul « Avancé » y est).
- Vocabulaire : `zones[].chassis` (ACAL581/585) coexiste avec `chassis_sous_pente_deg`/`chassis_inclinaison_deg` (châssis incliné, `traduction.py:542-560`) : deux sens de « châssis » dans le même module.
