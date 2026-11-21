# Inventaire de l'atelier 3D (roofPro11) — a3

Périmètre lu (lecture seule, rien exécuté) : `apps/web/src/scripts/roof-tool-pro11.ts`, `apps/web/src/scripts/roofPro11/**`, `apps/web/src/lib/*` (shadingEngine, horizonEngine, roofConfig, estimatorBrainV*), pages hôtes, `frontend/src/features/calepinage/**`, `frontend/src/pages/ventes/ToitureDesign.jsx`, `backend/django_core/apps/calepinage`, `core/calepinage`.
Légende : P = présent et câblé à l'écran, ~ = partiel, A = absent, M = moteur/fonction existe mais AUCUN bouton/appelant (vérifié par grep hors tests).
Je n'ai pas lancé l'outil : tout ce qui suit est lu dans le code, pas observé à l'écran.

## 0. Architecture en une phrase
Un seul « builder » TypeScript (DOM `rp9-*`, MapLibre + calque Three.js) servi dans 4 modes : (1) page publique/preview `apps/web/src/pages/preview/toiture-3d-pro-11.astro` (estimateur piloté par la facture), (2) ERP atelier calepinage `frontend/src/pages/ventes/ToitureDesign.jsx` + rail de ~40 onglets, qui importe le builder via alias `@roofpro`/`@rooflib` (frontend/vite.config), (3) mode « capture » du tunnel public `/devis/mon-toit` (`roofPro11/captureBoot.ts`, carte + tracé seulement, aucun panneau), (4) visionneuse client en lecture seule `roofPro11/viewerFullBoot.ts` + `viewerOnly.ts` (page `/proposition/[token]`).
Mode « devis » vs « calepinage » : `ToitureDesign.jsx` ne garde plus de mode devis écrivain (commentaire ACAL37 dans `frontend/src/features/calepinage/atelier/useAtelierBoot.js`) ; « devis » = le devis synchronisé est seulement lu pour l'étude bancable ; « calepinage » = enregistre le layout (`enregistrerCalepinage` dans ToitureDesign.jsx). Le mode public « preview » a l'optimiseur piloté par facture (`recommend`, `solveLivePitched`).

## 1. Liste des outils et gestes

| Outil / geste | Statut | Preuve |
|---|---|---|
| Recherche d'adresse (autocomplétion 5 suggestions, pays limité, géoloc « ma position ») | P | `roofPro11/mapDraw.ts::geocode`, `geocodeSearchUrl` (MapTiler), `roof-tool-pro11.ts` GeolocateControl |
| Tracé du contour d'un toit (clic/tap par sommet, double-clic/double-tap = terminer, annuler dernier point) | P | `mapDraw.ts::addVertex`, `redrawTrace`, `roof-tool-pro11.ts` handlers `dblclick`/`touchstart` (W77), boutons `rp9-finish`, `rp9-undo-point`, `rp9-clear` |
| Garde anti auto-intersection du contour | P | `lib/roof.ts::isSimplePolygon` (W76) |
| Aimantation angles droits 90°/45° | P | `roofPro11/snap.ts::contraindreAngle`, `PAS_ANGLE_DEG`, `TOLERANCE_ANGLE_DEG` |
| Aimantation aux zones voisines / bords | P | `snap.ts::aimanterAuxZones`, `accrocheAuxZones` |
| Déplacer un sommet, insérer un sommet sur arête, supprimer un sommet | P | `roof-tool-pro11.ts::tryBeginVertexMove`, `snap.ts::insertionSurContour`, `supprimerSommet` |
| Pan / face / zone multiples (« + Ajouter une zone », liste des zones, total agrégé) | P | `roofPro11/zones.ts`, `rp9-add-area`, `rp9-areas-list` ; `lib/roofAreas.ts` |
| Presets de forme de toit (plat, 1 pan, 2 pans, 4 pans, L, T) | M | `scene3d.ts::generateRoofShapePans` + `zones.ts::buildAreasFromShape` : aucun appelant hors tests (grep) → aucun bouton |
| Type de toit plat / en pente | P | puces `data-rooftype` (`rp9-config`), `lib/roofTypeSelect.ts` |
| Pente en degrés (puces 15/22/30/45° + curseur 5-45°) | P | `BuilderDom.jsx` `rp9-pitch-range`, `data-pitch` |
| Pente en % ou par cotes (portée/faîtage) | ~ | `frontend/.../SaisiePente.jsx` (onglet « Pente ») ; saisie séparée de la carte 3D |
| Azimut / orientation du pan (Sud, SE, SO, E, O + curseur 0-359°) | P | `rp9-facing-range` step any, `data-facing` ; orientation panneaux alignée au toit : `data-azimuth="aligned"` |
| Orientation fine de la disposition ±1° | P | `rp9-layout-az-minus/plus`, `lib/layoutVariability.ts::nudgeAzimuthDeg` |
| Faîtière / arêtiers / noues (lift de faîtière commune entre pans) | ~ | `scene3d.ts` `ridgeLiftM`, `computeMixedAltitudeOffsets` ; pas d'outil de dessin de faîtage/arêtier |
| Type d'arête corrigeable (6 types : rive, égout, faîtage…) | P | `roofPro11/edgesUi.ts` (CALX94), `edges.ts` |
| Retraits de rive (périmètre), par arête, avec acrotère/parapet | P | `lib/roofSetbackEdge.ts`, `lib/roofPro2.ts::PerimeterSetbacks`, `roofPro11/batiment.ts::acrotereDuBatiment`, `rp9-overhang-input` |
| Lucarnes / chien-assis comme obstacle + percement du plan | ~ | `batiment.ts::construireLucarnes`, `percerPanLucarnes` ; type `chien_assis` dans `types.ts` ; saisie comme obstacle générique |
| Obstacles (cheminée, ventilation, édicule, antenne, autre, chien-assis) : poser par glissé, taille ±, redimension, supprimer | P | `roofPro11/obstaclesUi.ts`, `rp9-obstacle`, `rp9-obs-length/width`, `lib/obstacles.ts::ObstacleType` |
| Zones d'exclusion (gabarits réglementaires, ex. allées/dégagements) | P | `obstaclesUi.ts` `rp9-zone-gabarit`, `zones.ts::exclusionZoneRing`, `teinteAllees.ts` |
| Arbres et bâtiments voisins (hauteur/diamètre saisis, ombre portée) | P | `obstaclesUi.ts` `rp9-env-add-tree`, `roofPro11/environment.ts` |
| Ombre voisine « tracée » : pied + bout d'ombre → hauteur déduite (h = L·tan α) | P | `shadingUi.ts`, `lib/shadingEngine.ts::obstructionHeightFromShadow` |
| Hauteur du bâtiment saisie + provenance (OSM, relevé) ; défaut dessin 6 m annoncé hypothèse | P | `batiment.ts::HAUTEUR_DESSIN_M`, `prefill.ts`, `lib/shadingEngine.ts::DEFAULT_ROOF_HEIGHT_M=6` |
| Horizon lointain (profil PVGIS ou saisi) | P | `lib/horizonEngine.ts`, onglet `horizon` (`HorizonPanel.jsx`), serveur `services/horizon.py` |
| Remplissage auto (max de modules selon règles) | P | `optimizer.ts` (`liveResolveFlat`, `liveResolvePitched`), bouton `rp9-layout-fill`, `lib/layoutVariability.ts::fillAll` |
| Portrait / paysage (Auto / Portrait / Paysage) | P | `data-orient` ; `estimatorBrainV2.ts` |
| Inclinaison toit plat (puces reco/29/15/10 + curseur 5-35°) | P | `rp9-tilt-range`, `data-tilt` |
| Pas inter-rangées / châssis toit plat (calculé par pavage + auto-ombrage des rangées) | P | `estimatorBrainV2.ts`, `lib/shadingEngine.ts::rowSelfShading`, `scene3d.ts` ; vue en coupe : onglet `coupe` (`OngletCoupeRangees.jsx`) |
| Est-Ouest | P | `data-family="eastwest"` |
| Sud plein / aligné toit | P | `data-family="south"`, `data-azimuth` |
| Disposition « maille » (cellules) vs « libre » | P | `rp9-layout-mode-lattice/free`, `layoutEditor.ts` |
| Déplacer un panneau (glissé 3D, tap-sélection puis tap-cible), + / − panneau, réinitialiser | P | `layoutEditor.ts`, `rp9-layout-plus/minus/reset`, `rp9-layout-grid` |
| Sélection : clic, Ctrl+clic, cadre, lasso, rangée entière | P | `layoutEditor.ts` `rp9-marquee`, `rp9-layout-lasso`, `rp9-layout-select/row`, `lib/panelSelection.ts` |
| Copier/dupliquer avec décalage ; symétrie par axe | P | `layoutEditor.ts` `rp9-free-dup-btn`, `rp9-free-mirror` |
| Rotation libre, aligner (rangée/colonne), répartir uniformément | M | `layoutEditor.ts::freeRotateSelection`, `freeAlignSelection`, `freeDistributeSelection` exposées sur l'objet retourné mais aucun bouton ni appelant hors tests (grep sur apps/web/src et frontend/src) |
| Coller (copier-coller classique) | A | seule « Dupliquer » existe |
| Annuler / rétablir (Ctrl+Z, Ctrl+Y / Ctrl+Maj+Z) | P (partiel) | `layoutEditor.ts` keydown ; `layoutHistory.ts::LAYOUT_HISTORY_LIMIT = 50` ; l'historique « atelier » généralisé existe (`createWorkshopHistory`) mais le keydown de Ctrl+Z est gardé par `ctx.layoutMode` → n'agit que dans le panneau de disposition (clavier.ts le dit) |
| Choix du module depuis le stock/catalogue société, par pan | P | `roofPro11/moduleSelect.ts`, `zones.ts` `rp9-pan-module-select` ; catalogue servi par `modulesDisponibles` ; modèles sans fiche complète grisés avec motif |
| Câblage : chaînes / MPPT, teinte des modules par chaîne | ~ | `roof-tool-pro11.ts`/`types.ts::setAffectationChaines`, `useAtelierBoot.js::pousserAffectationAtelier` ; onglet `affectation` ; couche électrique `electrique3d.ts` |
| Numérotation des modules (étiquettes) | P | `roofPro11/numerotation.ts`, `scene3d.ts::poserEtiquettesNumeros` |
| Mesure distance / surface / angle | P | `roofPro11/mesureUi.ts`, boutons `rp9-mesure-*` |
| Cotes au clavier (saisie cotée longueur/largeur d'un obstacle) | P | `rp9-obs-length/width`, `rp9-free-setback/gap` (champs texte, `step="any"`) |
| Guides d'alignement visuels (smart guides) | A | aucune occurrence ; seul `layoutVariability`/`freeLayout.snapCandidateForPanel` aimante les panneaux (seuil `FREE_SNAP_THRESHOLD_M`) |
| Multi-sélection puis déplacement groupé | P | `layoutVariability.ts::moveGroup`, `planGroupMove` |
| Zoom / orbite / inclinaison (maxPitch 75°) / boussole | P | `roof-tool-pro11.ts` `new maplibregl.Map({maxPitch:75})`, `NavigationControl`, `rp9-compass` ; remise à plat `pitch:0, bearing:0` |
| Bascule 2D/3D | ~ | pas de bouton de basculement du même canvas : vue 2D plan séparée `frontend/.../Vue2DPlan.jsx` + `planView` ; `PITCH_VIEW=58` à l'ouverture, retour à plat à 0° |
| Plein écran | P | `BuilderDom.jsx` `rp9-plein-ecran-toggle`, `pleinEcran.js` |
| Curseur heure du soleil (6-18 h), saison hiver/été, date | P | `rp9-sun-hour`, `data-sun-season`, `roof-tool-pro11.ts::dayOfYearToDateValue` |
| Animation de la course du soleil (jour / année) | P | `soleilPlay.ts::createSoleilPlayer` (boutons créés dynamiquement dans `roof-tool-pro11.ts::ensureSoleilPlayButtons`, pas de 700 ms) ; onglet `course-soleil` |
| Heatmap d'accès solaire par module | P | `rp9-heatmap-toggle`, `shadingUi.ts::refreshHeatmap`, `lib/shadingEngine.ts::cellsSolarAccess`, `solarAccessColorRGB` |
| Proposition de retirer les modules ombrés | P | `shadingUi.ts` (`proposeShadedRemoval`, seuil `SOLAR_ACCESS_LOW=0.75`) |
| Champ au sol / ombrière / façade (surfaces de pose) | ~ | `roofPro11/poseSurfaces.ts` (`GenrePose = sol|ombriere|facade`, `monterAtelierPose`) ; moteur serveur `POST /calepinage/moteur/pose/` ; écrans `ModeTerrain.jsx`, `Ombriere.jsx` |
| Carport/ombrière : poteaux | ~ | `poseSurfaces.ts` (poteaux saisis, 2 mesures) ; pas d'outil de dessin de structure |
| Parcelle (plan de masse) | P | `rp9-parcelle`, `roofPro11/parcelle.ts` |
| Plan importé (image/plan) calé à 2 points + distance | ~ | `roofPro11/underlay.ts`, `calageFondUi.ts`, `PlanImporteCalage.jsx` ; photo de site à 4 coins `PhotoSiteCalage.jsx` ; Alt+glissé translate le fond, Alt+molette le pivote |
| Calques (visibilité/opacité par couche) | P | `frontend/.../calques.js`, `PanneauCalques.jsx`, `setLayerState` |
| Export image HD / PNG, vue plan | P | `scene3d.ts` rendu hors-écran (`HD_MAX_SIDE_PX=8192`), `rendreImageHd.js`, `exportImage.js`, `OutilsVue.jsx` |

## 2. Carte & imagerie
- Fournisseurs enregistrés dans `lib/roofConfig.ts` : `maptiler` (style hybride satellite + libellés, résolution `null` = non annoncée), `mapbox` (Satellite/Maxar Vivid, tuiles `@2x`, tileSize 256), `ign_bd_ortho` (France, WMTS sans clé), couche optionnelle cadastre FR. Le choix : jeton Mapbox présent → Mapbox, sinon MapTiler (`buildSatelliteStyle`). Le sélecteur de fournisseur par société existe dans les réglages (`imagery.fournisseur_imagerie`, `fournisseurs_autorises`).
- Zoom max : aucun `maxZoom` posé dans `new maplibregl.Map` (défaut MapLibre 22). Les capteurs fournisseurs ne sont pas bornés par `maxzoom` dans le registre (champ optionnel, jamais renseigné pour ces trois). Le zoom d'ouverture sur le toit est 19 ; `zoomToFitRing` pour l'ajustement.
- Imagerie propre à l'utilisateur : plan importé (calage 2 points + distance saisie, jamais d'échelle devinée, `underlay.ts`) et photo de site 4 coins (`PhotoSiteCalage.jsx`). Pas de dépôt direct d'orthophoto drone géoréférencée (GeoTIFF/tuiles) ni de PDF-plan avec détection d'échelle : l'analyseur serveur `services/import_plan.py` rend un contour sans échelle.
- Altitude/MNT/LIDAR : `backend/.../services/lidar_ign.py` (CAL237) suggère pente et azimut par pan, France uniquement (IGN LiDAR HD/RGE ALTI), gaté `pays == 'fr'` avant tout réseau, suggestion jamais appliquée sans validation humaine. Au Maroc : aucune source d'altitude de toit (le code documente « pas de Google Solar au Maroc », `apps/crm/roof_detect.py`).
- Hauteur de toit : saisie (hauteur bâtiment CAL60/CALX100), OSM `building:levels`/`height` proposés avec provenance (`roof_detect.py`, `batiment.ts::BatimentOsmServeur`, bouton « Reprendre la hauteur OSM… »), ou valeur de dessin 6 m nommée hypothèse (`HAUTEUR_DESSIN_M`). Pente : saisie (°, %, cotes) ; ou suggestion IGN (FR) ; ou déduite d'une ombre tracée pour les obstacles (hauteur).
- Géocodage : MapTiler `/geocoding` (limit 5, `country=ma` par défaut, `language=fr`), reverse-geocode idem (`mapDraw.ts`). Empreinte du bâtiment : Overpass/OSM via `roof_detect.py` (best-effort, 3/5 s), consommée dans `useAtelierBoot.js`.

## 3. Rendu 3D
- MapLibre GL (carte) + calque personnalisé Three.js posé dans le même contexte WebGL (`scene3d.ts::customLayer`, `new THREE.WebGLRenderer({canvas: map.getCanvas(), context: gl, antialias: !lowEnd})`). Pas de moteur custom canvas pour la 3D.
- Réalisme : vrai soleil (`lib/roofPro2.ts::sunDirection`), ombres portées Three (`PCFSoftShadowMap`, carte d'ombre 1024 bas de gamme / 2048 sinon), modèle de module Canadian Solar 720 W avec texture procédurale demi-cellules et cadre (`panelTexture.ts`), rails/châssis galvanisés texturés perforés, bâtiment extrudé (hauteur du document), acrotère, photo satellite drapée en texture sur la dalle (`applyRoofPhoto`), obstacles en boîtes 0,8 m (`OBSTACLE_BOX_H_M`) avec étiquettes de cote. Pas de ciel/atmosphère dédiés : le fond est la carte ; pas de textures de toiture (tuiles) ni de végétation 3D détaillée.
- Perf : un `InstancedMesh` par type de pièce (7 max en plat, 2 en affleurant). Test CAL106 `roofPro11/perf.test.ts` : champ de 2 000 modules, coût PUR (construction du plan 3,5-4,8 ms, matrices 1,7-2,2 ms, élagage 0,7-1,8 ms, re-snap indexé 20-40 ms) ; explicitement PAS le rendu WebGL (vitest sans GPU). Cas `lowEnd` (≤ 4 Go ou ≤ 4 cœurs) : antialias coupé, ombres réduites. Gestion de perte de contexte WebGL (`webglcontextrestored`). Aucun plafond dur de modules dans le code lu (`plafonnerSelection` borne la sélection).
- Export : `scene3d.ts` rend un PNG (carte + 3D composées via rendu hors-écran `preserveDrawingBuffer: true`, `HD_MAX_SIDE_PX = 8192`), planche calepinage du PDF devis. Visionneuse client : même scène en `readOnly: true`, orbite/inclinaison/zoom libres, aucun geste d'édition (`viewerFullBoot.ts`) ; ancienne visionneuse abstraite `viewerOnly.ts` avec drapé satellite.

## 4. Interface
- Comptage (grep des balises dans les gabarits, hors éléments injectés) : page preview 73 `<button>` + 13 `<input|select>` (+130 ids `rp9-*`) ; page publique `mon-toit.astro` 32 boutons + 28 champs ; DOM builder de l'ERP `BuilderDom.jsx` ≈ 75 boutons/chips + ~12 champs, auxquels s'ajoutent des panneaux créés dynamiquement par le script (zones, module par pan, arbres, gabarits, dupliquer, symétrie, lasso, soleil, surfaces de pose) et le rail ERP de ~40 onglets (`frontend/.../atelier/onglets.js`, groupes Site / Système / Résultats / Dossiers).
- Flux : barre d'adresse → carte → tracé → `rp9-config` (type de toit, famille, inclinaison, orientation, pose, marge) → obstacles → disposition (fenêtre « Personnaliser ») → résultats/production → onglets du rail. Ce n'est pas un assistant à étapes numérotées ; c'est un empilement de sections révélées (`hidden` retiré après le tracé).
- Raccourcis clavier :
  - Plan déclaratif `roofPro11/clavier.ts::PLAN_CLAVIER` (modes trace/mesure/obstacle/zone) : flèches = déplacer le curseur de pose (pas fin ; Maj = pas rapide), Entrée = poser un sommet / fermer, Retour arrière = annuler dernier point, Suppr = retirer, Échap = sortir, `?` ou F1 = aide. Se retire si le focus est dans un champ.
  - ERP `RaccourcisAtelier.helpers.js::RACCOURCIS` : T tracé, O obstacle, Z zone, M mesure, A aimantation, Suppr, Ctrl+D dupliquer, F plein écran.
  - Disposition (`layoutEditor.ts` keydown) : Ctrl/⌘+Z, Ctrl+Y / Ctrl+Maj+Z, Échap (désarme ajout/symétrie/sélection), flèches = nudge de la sélection d'un pas de rangée.
  - Souris : Alt+clic supprime un panneau ; Ctrl/⌘+clic ajoute à la sélection ; Alt+glissé translate le fond importé, Alt+molette le pivote.
- Tactile : événements `touchstart/touchmove` carte (`roof-tool-pro11.ts`, `obstaclesUi.ts`, `layoutEditor.ts`), double-tap = terminer, appui long, seuils doigt (`VERTEX_GRAB_PX=14`, `LAYOUT_GRAB_PX=12`) ; e2e `frontend/e2e/calepinage_tactile.spec.js`. Pas de gestes pinch/rotation propres : on s'appuie sur MapLibre natif.
- Messages : zone `aria-live` de statut (`rp9-status`, `rp9-layout-note`) ; règle fondateur « un refus nomme le champ fautif » (`clavier.ts`, `poseSurfaces.ts`) ; refus de geste nomme sa raison (« Pas de place dans cette direction — rien n'a bougé. »).
- Sauvegarde : « Enregistrer le calepinage » explicite + brouillon LOCAL (localStorage, `brouillon.js`, intervalle `reglages.calepinage.brouillon_intervalle_secondes`), reprise proposée à l'ouverture, garde de sortie (`useDirtyGuard`), conflit d'écriture (`conflitEcriture.js`). Pas d'autosave serveur.
- Annuler : 50 pas (`LAYOUT_HISTORY_LIMIT`), pile par snapshot.
- i18n : atelier ERP et builder en français uniquement (libellés en dur dans les .ts/.jsx) ; la page publique `mon-toit` existe en `/fr`, `/en/devis/mon-toit`, `/ar/devis/mon-toit` pour le mode capture seulement.
- CSS builder ERP : `frontend/src/styles/roofbuilder.css` 392 lignes (un seul `@media`: `prefers-reduced-motion`).

## 5. Frictions démontrables dans le code
1. Azimut et pente se règlent par curseur/puces numériques (`rp9-facing-range` 0-359 step any ; `rp9-pitch-range` 5-45) : aucune lecture automatique du toit, l'utilisateur doit connaître l'azimut (hors France IGN).
2. Trois façons de saisir la pente (°, %, cotes) vivent dans des écrans différents (carte vs onglet `pente`), pas au même endroit.
3. Presets de forme (2 pans, 4 pans, L, T) codés (`generateRoofShapePans`) mais sans bouton : l'utilisateur doit dessiner chaque pan à la main.
4. Rotation libre, aligner, répartir : fonctions testées sans commande à l'écran (M ci-dessus).
5. Pas de « coller », pas de guides d'alignement visuels, pas de copie entre pans.
6. Undo/redo clavier uniquement tant que le mode disposition est actif ; le tracé, les obstacles et les zones n'ont que « Annuler le dernier point » (`rp9-undo-point`) et « Effacer » (`rp9-clear`, tout-ou-rien).
7. Un panneau « Personnaliser la disposition » (fenêtre repliée) contient la majorité de l'édition de panneaux ; deux modes (maille/libre) avec contrôles différents (`rp9-free-controls` caché hors mode libre).
8. Raccourcis uniquement par touche nue T/O/Z/M, sans indication à l'écran sauf l'aide `?`/F1 ; deux tables clavier distinctes (`clavier.ts` et `RaccourcisAtelier.helpers.js`) et un troisième keydown dans `layoutEditor.ts`.
9. Hauteur bâtiment : défaut 6 m annoncé comme « hypothèse de dessin » (honnête mais l'ombre dépend d'une saisie de l'utilisateur) ; sans OSM/relevé, l'ombrage de rive est approximatif.
10. Hors France, aucune aide pour mesurer pente/hauteur (pas de MNS) ; au Maroc il faut tout relever sur place.
11. Orthophoto drone non importable comme fond géoréférencé : seulement plan avec calage 2 points + distance saisie, ou photo 4 coins calée ailleurs.
12. Le rail de ~40 onglets expose des écrans techniques (pertes, schéma unifilaire, masse & lestage, fixation…) au même niveau que le dessin ; sans `?onglet=` aucun panneau n'est ouvert (voulu), mais il n'y a pas de parcours guidé.
13. Gestes destructifs sans confirmation visible dans le code lu : « Effacer » (`rp9-clear`), « Tout effacer » obstacles (`rp9-obstacle-clear`).
14. Alt+clic = supprimer un panneau (geste caché, PV29) : le clic simple a été changé en sélection, le geste de suppression n'a pas de bouton.
15. Fonctions « existantes mais discrètes » : lasso/dupliquer/symétrie créés dynamiquement (aucun gabarit ERP ne les montre), animation du soleil créée dynamiquement, module par pan créé dynamiquement.
16. Plein écran 3D : le bouton de sortie vit DANS l'enveloppe carte (commentaire CALX129) : bonne parade, mais les panneaux de réglage ne sont plus accessibles en plein écran.

États invalides possibles : un panneau déplacé est validé tout-ou-rien (`checkPanelAt`) donc peu d'états invalides ; en revanche un contour peut être valide mais sans pente/azimut confirmés (valeurs par défaut 22° / Sud 180°, puces `aria-pressed="true"` au chargement), ce qui produit un chiffre de production « plausible » sans saisie réelle.

## 6. Intelligence de conception automatique
- Optimiseur vivant : toit plat `liveResolveFlat` (axes inclinaison, orientation, pose, marge, cible « panneaux nécessaires » ; verrouiller un axe re-résout les autres ; valeur « Recommandé » badgée), toit en pente `solveLivePitched` (pas d'axe inclinaison, orientation = face) (`estimatorBrainV7.ts`, `estimatorBrainV8.ts`, `roofPro11/optimizer.ts`). Matrice complète triable (tilt 0→35°, azimut sud ±45°, E-O, portrait/paysage, marge) avec production PVGIS : `estimatorBrainV6.ts::fineGridMatrixV6`, `roofPro11/matrix.ts`.
- Cible : « panneaux nécessaires » depuis la facture (`billToAnnualKwh`, `neededPanelsForTarget`, champs `rp9-need-*`, `rp9-bill`). Le « Remplir » = max de modules (`rp9-layout-fill`). Retirer les modules ombrés (`proposeShadedRemoval`).
- Serveur : `backend/django_core/core/calepinage/{moteur,optimum,poseur}.py` = moteur à deux chemins indépendants (compteur / poseur) avec programme dynamique exact « optimum prouvé » seulement si la méthode est exacte ; suggestions d'alternatives (`calepinage_json(suggestions=True)`), sensibilités.
- Détection de toit : empreinte de bâtiment OSM seulement (`apps/crm/roof_detect.py`, Overpass), pas de vision IA ; détection d'obstacles « hors périmètre » (documenté). IGN LiDAR (FR seulement) pour pente/azimut. Aucune détection par vision sur imagerie.
- « Un clic » : pas de parcours « saisir une adresse → conception complète » unique dans l'atelier ; la page publique fait adresse → tracé → recommandation instantanée, c'est le plus proche.

## 7. Calculs navigateur vs serveur
- Navigateur : pavage des panneaux, optimiseur live, matrice, ombrage proche (`lib/shadingEngine.ts` : obstructions, `hourlyShadeFactors`, accès solaire par module), horizon (`lib/horizonEngine.ts`, qui consomme un profil déjà obtenu), production à partir de données PVGIS déjà récupérées (`lib/productionEngine.ts`, le navigateur ne touche jamais PVGIS : CORS ; passe par `/api/roof-production`, `/api/roof-yield` d'apps/web). L'ERP n'a pas ces routes : repli `fallbackPerKwc()` étiqueté « estimation » (`useAtelierBoot.js::productionAtelierErp`).
- Serveur : `apps/calepinage/services/{production,pvgis_serie,pertes_politique,simulation,p50p90,horizon,ombrage_chaines}.py` ; politique de pertes unique (`pertes_politique.py`, règle CAL238 « loss est une entrée, jamais un 14 % caché », contrat `calepinage_resultat.json`) ; moteur `core/calepinage` ; résultats servis `calepinages/<id>/resultat/`.
- Source de vérité : pour le livrable/devis c'est le serveur (`Devis.etude_params`, quote_engine, règle #4) ; le navigateur affiche une estimation. Divergences connues dans le code : (a) deux sources de production selon la page (PVGIS direct apps/web vs repli table dans l'ERP) ; (b) ombrage proche et horizon sont deux facteurs distincts multipliés côté navigateur (`optimizer.ts`) tandis que le serveur a sa propre chaîne de pertes (`chaine_pertes.py`) ; des tests de non-régression existent (« production IDENTIQUE » après réouverture, `apps/web/tests/userJourneyPro11.test.ts` : D-ACAL-VER2-1 pour documents stockés sans signature d'ombrage). Je n'ai pas exécuté de comparaison chiffrée navigateur/serveur.

## 8. Tailles
- `apps/web/src/scripts/roof-tool-pro11.ts` : 4 354 lignes (orchestrateur).
- `apps/web/src/scripts/roofPro11/` : 95 fichiers ; code hors tests ≈ 33 030 lignes ; tests ≈ 14 133 lignes (42 fichiers `*.test.ts`) ; ≈ 1 038 cas `it(`/`test(` (grep de motifs, ordre de grandeur).
- Plus gros fichiers : `layoutEditor.ts` 3 223, `scene3d.ts` 3 115, `prefill.ts` 1 999, `optimizer.ts` 1 831, `obstaclesUi.ts` 1 788, `mapDraw.ts` 1 655, `zones.ts` 1 488, `poseSurfaces.ts` 1 306, `shadingUi.ts` 1 284.
- `apps/web/src/lib` (moteurs utilisés) : estimatorBrainV2 2 108, V3 779, V7 560, V8 381, shadingEngine 730, horizonEngine 171, productionEngine 391, freeLayout 839, layoutVariability 453, roofConfig 646, roofPro2 479, panelSelection 219, obstacles 278.
- Pages hôtes : `pages/preview/toiture-3d-pro-11.astro` 1 185 lignes ; `pages/devis/mon-toit.astro` 1 295 ; ERP `frontend/src/pages/ventes/ToitureDesign.jsx` 1 738.
- ERP `frontend/src/features/calepinage/` : 123 fichiers non-test, ≈ 28 996 lignes ; ≈ 97 fichiers de test ; e2e : `frontend/e2e/calepinage-onglets.spec.js`, `calepinage-parcours.spec.js`, `calepinage-parite-crm.spec.js`, `calepinage_tactile.spec.js`.
- Tests du builder côté site : `apps/web/tests/userJourneyPro11.test.ts` (14 cas, parcours résidentiel jsdom, carte mockée, aucune scène GPU), `estimatorPreviewPro11.test.ts`, `estimatorRuntimePro10Pro11.test.ts`, `roofPro11QuoteFirstSizing.test.ts`.
- Backend : `apps/calepinage/services` ≈ 53 917 lignes (compte du dossier services), `core/calepinage` ≈ 6 673 lignes.

## 9. Comparaison avec les outils du marché (lecture du code, pas des produits)
Présent : pans multiples, pente/azimut, obstacles avec dégagement, retraits, accès solaire par module (heatmap), course du soleil, horizon PVGIS, modules du stock, câblage en chaînes + schéma unifilaire, DXF/images/planches, variantes/versions/approbation, visionneuse client 3D lecture seule, tactile.
Absent ou non câblé : détection automatique du toit sur imagerie (Aurora, OpenSolar, Pylon le font), modèle de toit 3D reconstruit (MNS/LIDAR hors France), outil faîtage/arêtier/noue à dessiner, presets de forme câblés, copier-coller, guides d'alignement, rotation/aligner/répartir à l'écran, import orthophoto drone géoréférencée, chemin « une adresse → conception complète en un clic », parcours guidé par étapes, i18n du builder.
