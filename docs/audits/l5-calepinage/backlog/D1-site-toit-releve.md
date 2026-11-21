# D1 — Site, toit et relevé : liste consolidée des capacités (campagne L5 calepinage, tour 1)

Juge de consolidation D1, 21/11/2026. Dépôt lu en LECTURE seule
(`C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5`, branche `claude/calepinage-fichiers-publics`) :
aucun fichier modifié, pas de docker, pas de test lancé, aucun écran ouvert.

**Comment ce fichier a été fait.** Cinq lecteurs ont extrait des onze fichiers d'étude toutes les propositions et grappes
du domaine D1 (B1+B2, B3+B4, B5 allemand+français+nl-pl-tr-ar, B5 anglais+espagnol, B6+B7). J'ai ensuite fusionné les
doublons et vérifié MOI-MÊME chaque capacité retenue dans le code (grep et lectures ciblées, preuves en `fichier::symbole`).
Les comptes de preuves sont ceux que les lanes écrivent. Les lecteurs n'ont pas lu les annexes en entier (voir « Non vérifié »).

**Barème.** Preuves 1-5 (lanes distinctes × force : forum réel > notes de version > page commerciale) ; adéquation 1-5 (toits
résidentiels, terrasses béton, toits tertiaires, champs au sol agricoles, pompage, commerciales non-ingénieures, équipe de
pose, français) ; effort S = 1, M = 2, L = 3. Score = preuves × adéquation ÷ effort. Les capacités PRÉSENT SANS ÉCRAN sont
en tête quel que soit leur score (le travail est fait, il manque le bouton).

Tous les fichiers cités dans les découpes appartiennent au propriétaire `calepinage`, vérifié par
`python scripts/check_ownership.py --owner-of <fichier>` (mapDraw.ts, obstaclesUi.ts, lib/obstacles.ts, environment.ts,
roofConfig.ts, shadingEngine.ts, scene3d.ts, zones.ts, BuilderDom.jsx, ReglagesSite.jsx, PhotoSiteCalage.jsx,
PlanImporteCalage.jsx, HorizonPanel.jsx, export_dxf.py, reprise_visite.py, traduction.py, core/calepinage/types.py → tous
`calepinage`). Exceptions dites dans la fiche : `apps/visites/selectors.py` et `frontend/src/features/visites/visitesOffline.js`
→ propriétaire `lead` ; `apps/web/src/pages/devis/mon-toit.astro` → `web`.

---

## A. PRÉSENT SANS ÉCRAN — le travail est fait, il manque le bouton

### CAP-D1-01 — Dupliquer un obstacle et le poser en série (trame N × M)
- **Besoin** : « insupportable de tout redessiner sur une halle à 40 lanterneaux » (commentaire du code, `lib/obstacles.ts`) ;
  copier-coller et répéter les climatiseurs, lanterneaux, exutoires d'un toit tertiaire.
- **Preuves** : B3 N13/N13b (HelioScope Bulk Actions + Alt-glisser, SMA « copier », archelios « duplication en un clic ») ;
  B6 R2 (5 outils : PVcase RM 1.52, SolarEdge Designer 2020-01, PVsyst 7.2.15, Scanifly…) ; B7 U8 (12 lignes, 8 sources) ;
  B4 rang 5 (« coller », VF1094/VF1096) ; B5 anglais P2.1 I. URL : https://help-center.helioscope.com/hc/en-us/articles/7900008804755-Copy-Keepout-Zones ·
  https://www.pv-tech.org/solaredge-bolsters-design-tool-to-streamline-ci-rooftop-planning-process ·
  https://www.trace-software.com/en/archelios-pro-the-new-standard-in-photovoltaic-self-consumption/
- **Qui le fait** : HelioScope / SolarEdge : sélectionner, Ctrl+C / Ctrl+V ou Alt-glisser ; « répéter N fois » au pas choisi.
- **Chez nous** : PRÉSENT SANS ÉCRAN. Le code CAL73 existe : `apps/web/src/scripts/roofPro11/obstaclesUi.ts` lit
  `rp9-obs-duplicate`, `rp9-obs-grid-spacing`, `rp9-obs-grid-cols`, `rp9-obs-grid-rows`, `rp9-obs-grid-place` (duplication +
  trame en UNE photo d'historique) et le raccourci `roof-tool-pro11.ts::dupliquer` clique `rp9-obs-duplicate`. Mais AUCUN
  balisage ne crée ces éléments : grep de ces identifiants dans `apps/web/src` et `frontend/src` ne rend que les lecteurs
  (ni `frontend/src/features/calepinage/atelier/BuilderDom.jsx`, ni `apps/web/src/pages/preview/toiture-3d-pro-11.astro`).
  Le bouton est donc introuvable et le raccourci clique dans le vide. (B3 §7.2 l'avait corrigé en « PRÉSENT » : faux pour
  l'utilisateur.) Multi-sélection d'obstacles : ABSENTE.
- **Plus petite version crédible** : dans la carte d'édition d'un obstacle sélectionné, deux lignes : « Dupliquer » et
  « Poser en série : pas __ m, __ colonnes × __ lignes, [Poser] ». Le pas est SAISI (aucun pas par défaut). Le serveur ne
  calcule rien de plus (les obstacles voyagent dans `roof_layout`). Pas de pas saisi ⇒ le bouton refuse en nommant le champ
  (le message existe déjà : « Pas ou nombre de trame invalide… »).
- **Simplicité** : étape Toit, essentiel ; visible seulement quand un obstacle est sélectionné.
- **Découpe** :
  1. Monter dans `BuilderDom.jsx` le bouton `rp9-obs-duplicate` et les quatre champs de trame dans la carte d'édition
     d'obstacle ; fini quand dupliquer puis poser une trame 3 × 2 depuis l'atelier ERP crée 6 obstacles annulables d'un seul
     Annuler. Fichiers : `frontend/src/features/calepinage/atelier/BuilderDom.jsx`, son test.
  2. Lister « Dupliquer l'obstacle » dans l'aide des raccourcis ; fini quand la touche de l'aide duplique l'obstacle
     sélectionné. Dépend d'ACAL414 (table unique des raccourcis).
- **Score** : preuves 4 · adéquation 5 · effort S → **20**. Rang 1.

### CAP-D1-02 — Écran « Gabarits d'obstacle de la société » (citerne, cage d'escalier, groupe de clim…)
- **Besoin** : « les dimensions d'une citerne, d'une cage d'escalier, d'un climatiseur saisies UNE fois, pas à chaque pose ».
- **Preuves** : B3 N19 (SMA/PVcase types d'objets ; Scanifly préréglages par forme avec hauteur et retrait — ligne 296) ;
  B1 V069 (gabarits PVsyst réutilisables) ; B6 K17 (Scanifly 2026-08-18 « exclusion-zone presets », n°436) ; B6 R4 (en
  partie). URL : https://scanifly.com/?p=9329 · https://scanifly.com/blog/whats-new-in-scanifly-summer-2026/ ·
  https://help-center.helioscope.com/hc/en-us/articles/7900025079187-Create-Keepout-Zones
- **Qui le fait** : Scanifly : la société règle une fois ses préréglages (forme, hauteur, retrait) ; le dessinateur choisit
  dans une liste.
- **Chez nous** : PRÉSENT SANS ÉCRAN (côté écriture). L'atelier sait LIRE et POSER un gabarit
  (`obstaclesUi.ts::remplirGabarits`, sélecteur `rp9-obs-gabarit` + « Poser ce gabarit », CALX104 ; gabarits de zone
  `rp9-zone-gabarit`, ACAL291) depuis la section société `zones_types`, que le serveur normalise
  (`apps/calepinage/services/zones_reglementaires.py::normaliser_section_zones_types`, branché dans
  `services/parametres.py`). Mais AUCUN écran n'écrit `zones_types` : grep `zones_types` dans `frontend/src` ne rend que les
  lecteurs (`atelier/contexteAtelier.js`, `atelier/useAtelierBoot.js`) ; `reglages/ReglagesSite.jsx` écrit `imagerie`,
  `reglages/ReglagesGabarits.jsx` gère les gabarits de DOSSIER réglementaire, `Bibliotheque.jsx` écrit `presets`. Résultat :
  l'atelier dit toujours « Aucun gabarit d'obstacle n'est enregistré dans les réglages de votre société ».
- **Plus petite version crédible** : dans Réglages › Calepinage, une table « Gabarits d'obstacle » : nom, type, forme
  (rectangle / cercle), cotes, hauteur, dégagement, SOURCE de chaque cote (« relevé chantier X », « fiche fabricant »). Le
  serveur valide avec son normaliseur et refuse sous le champ fautif. Un gabarit sans cote est refusé (déjà la règle CALX104).
- **Simplicité** : invisible pour la commerciale (elle choisit dans une liste dans l'étape Toit) ; l'écran de réglage est
  pour le porteur du droit de réglage.
- **Découpe** :
  1. Ajouter la section « Gabarits d'obstacle » à Réglages › Calepinage (lecture + écriture de `zones_types`, refus
     serveur sous la ligne) ; fini quand un gabarit créé là apparaît dans le sélecteur de l'atelier au rechargement.
     Fichiers : `frontend/src/features/calepinage/reglages/` (nouvel écran ou `ReglagesSite.jsx`), `api/calepinageApi.js`
     (`parametres.update` existe).
  2. Ajouter la partie « gabarits de ZONE » (même section, autre type d'entrée) ; fini quand une zone-type créée là se pose
     depuis `rp9-zone-gabarit`.
- **Score** : preuves 3 · adéquation 4 · effort M → **6**. Rang 2 (tête de liste : PRÉSENT SANS ÉCRAN).

### CAP-D1-03 — Mesurer la hauteur d'un arbre ou d'un voisin par son ombre sur l'image
- **Besoin** : au Maroc il n'y a ni modèle de surface ni LiDAR ; la hauteur du voisin est inconnue (B5 espagnol : immeuble
  de 15 étages, « hauteur inconnue »).
- **Preuves** : B5 allemand K01 (15 fils / 24 voix, ombrage proche digne de confiance ; `obstructionHeightFromShadow` cité) ;
  B3 R16 (hauteur depuis l'ombre, « PRÉSENT ») ; B6 R25 (date de l'image, 3 outils) pour l'hypothèse de prise de vue.
  URL : https://www.photovoltaikforum.com/thread/261874-schattenanalyse-%C3%BCbers-jahr-simuliert/ ·
  https://forum.valentin-software.com/topic/1096-pvsol-wunschliste/page/4/
- **Qui le fait** : outils à LiDAR (Aurora) le lisent directement ; sans LiDAR, la règle « ombre ÷ tan(hauteur du soleil) »
  est la méthode des installateurs.
- **Chez nous** : PRÉSENT SANS ÉCRAN. `apps/web/src/lib/shadingEngine.ts::obstructionHeightFromShadow` et le tracé
  pied → bout d'ombre de `apps/web/src/scripts/roofPro11/shadingUi.ts` (CAL66) existent, mais les contrôles
  `rp9-shade-add`, `rp9-shade-hour`, `rp9-shade-height`, `rp9-shade-list` n'ont AUCUN balisage (grep : seuls les lecteurs dans
  `shadingUi.ts`). PIÈGE chiffre inventé : l'hypothèse de prise de vue part de
  `shadingEngine.ts::IMAGERY_SUN_DEFAULT = { dayOfYear: 80, solarHour: 10.5 }`, une date et une heure que personne n'a
  déclarées.
- **Plus petite version crédible** : bouton « Mesurer une hauteur par son ombre » ; l'outil DEMANDE d'abord la date et
  l'heure de prise de vue de l'image (champ obligatoire, source « déclarée » ; si le fournisseur publie la date, elle est
  proposée avec sa source — voir CAP-D1-08) ; sans elles, l'outil refuse et le dit. Puis clic pied, clic bout ⇒ hauteur
  proposée, provenance `DEVINE` (non engageable, `lib/obstacles.ts::NON_ENGAGEABLE_PROVENANCES`) jusqu'à confirmation.
- **Simplicité** : étape Toit, expert (bouton dans la carte « Bâtiment voisin / arbre »).
- **Découpe** :
  1. Remplacer le défaut `IMAGERY_SUN_DEFAULT` par une date/heure de prise de vue SAISIE (absente ⇒ outil refusé avec motif) ;
     fini quand aucune hauteur ne sort sans date déclarée. Fichiers : `apps/web/src/lib/shadingEngine.ts`, `shadingUi.ts`.
  2. Monter le bouton et la liste des ombres tracées dans `BuilderDom.jsx` ; fini quand tracer une ombre de 10 m avec un soleil
     déclaré à 45° propose 10 m sur l'objet, marqué « à confirmer ».
- **Score** : preuves 3 · adéquation 5 · effort M → **7,5**. Rang 3. Partie D4 (comment l'obstruction tracée entre dans
  l'ombrage) : déjà calculée par `shadingUi.ts::activeShadeEntries`, rien à faire chez D4.

### CAP-D1-04 — Plus de types d'obstacles : lanterneau, climatiseur, citerne, garde-corps, exutoire, joint de dilatation
- **Besoin** : la bibliothèque d'obstacles couvre les objets réels des toits-terrasses marocains (citerne d'eau, groupe de
  clim, lanterneau, cage d'escalier).
- **Preuves** : B2 rang 3 (OpenSolar 3.10 « Objects & Trees ») ; B6 R4/K14 (4 outils : OpenSolar 3.10, PVcase RM 1.56,
  PVsyst 6.40, SolarEdge 2022-02) ; B5 anglais ligne 364 (lanterneaux ronds, clims, paratonnerres ; lanterneau plafonné à 0,5 m
  alors que réel ~0,8 m) ; B3 N19. URL : https://www.opensolar.com/product-updates/release-3-10/ ·
  https://help.pvcase.com/hc/en-us/articles/46003220223507-Release-notes-1-56 ·
  https://forum.valentin-software.com/topic/9228-skylights-on-flat-roof/
- **Qui le fait** : OpenSolar : palette d'objets, ombre portée ajoutée d'office.
- **Chez nous** : PARTIEL, et en partie PRÉSENT SANS ÉCRAN. L'atelier n'offre que 6 types
  (`apps/web/src/scripts/roofPro11/types.ts::OBSTACLE_TYPES` ; `lib/obstacles.ts::ObstacleType` = cheminee, ventilation,
  chien_assis, edicule, antenne, autre). Le moteur en connaît 13 (`core/calepinage/types.py::TypeObstacle` : CLIMATISEUR,
  LANTERNEAU, CAGE_ESCALIER, GARDE_CORPS, EVACUATION_EU…) et la traduction atelier → moteur accepte DÉJÀ `lanterneau`,
  `exutoire`, `joint_dilatation` (`apps/calepinage/services/traduction.py::TYPES_MOTEUR`) que l'atelier ne peut jamais émettre ;
  les dégagements société ont déjà les clés `lanterneau`, `exutoire`, `joint_dilatation`
  (`services/degagements.py::CLES_DEGAGEMENT_PROJET`). Citerne : aucun type nulle part.
- **Plus petite version crédible** : 6 types de plus au sélecteur (lanterneau, exutoire de fumée, climatiseur, citerne,
  garde-corps, joint de dilatation), chacun traduit vers son type moteur exact (citerne et autres sans équivalent ⇒
  `NATURE_INCONNUE`, règle déjà écrite dans `traduction.py`). Hauteur SAISIE. Dégagement : celui que la société a saisi pour ce
  type (`degagements`), sinon le recul de base actuel, NOMMÉ « recul de base, aucun dégagement société pour ce type ».
  JAMAIS une nouvelle valeur codée dans `CLEARANCE_BY_TYPE` (voir note D2 ci-dessous).
- **Simplicité** : étape Toit, essentiel (même menu, plus de lignes, icônes).
- **Découpe** :
  1. Étendre `ObstacleType`/`OBSTACLE_TYPES` et `TYPES_MOTEUR` (climatiseur → CLIMATISEUR, garde-corps → GARDE_CORPS) ;
     fini quand un climatiseur posé à l'atelier arrive au moteur en `CLIMATISEUR` (test de `traduction.py`). Fichiers :
     `apps/web/src/lib/obstacles.ts`, `apps/web/src/scripts/roofPro11/types.ts`, `apps/calepinage/services/traduction.py`.
  2. Lire le dégagement d'un nouveau type dans `degagements` de la société, sinon dire « recul de base » ; fini quand un
     lanterneau d'une société qui a saisi 1,8 m (préréglage `services/preset_fm_ds_1_15.py`) porte 1,8 m et le dit.
- **Score** : preuves 4 · adéquation 5 · effort S → **20**. Rang 4 (classé après les trois « sans écran » purs).
- **Note pour D2** : `types.ts::CLEARANCE_BY_TYPE` (0,50 m cheminée / lucarne / édicule) et `OBSTACLE_CLEARANCE_M` (0,30 m) sont
  des coefficients codés en dur justifiés par un raisonnement, pas par une page publiée — à confronter à D-ACAL-31 par le juge
  D2 (dégagements = pose).

---

## B. Capacités ABSENTES ou PARTIELLES, classées

### CAP-D1-05 — Démarrer en collant des coordonnées GPS ou un lien de carte
- **Besoin** : « Trouver un toit par latitude/longitude ou épingle, pas seulement par adresse » (B7, Photonik R284) ; les
  leads et les clients envoient souvent une position (lien de carte, position partagée — inférence, non vérifiée).
- **Preuves** : B2 rang 5 (OpenSolar 3.8) ; B6 R45/K21 (OpenSolar 3.8 2026-06-26, 3.13 2026-11-16 lien Google Maps / position
  actuelle, Scanifly 2025-11-19) ; B7 U24 (4 sources) ; B5 français rang 7 et B7 U27 (lat/long inversés). URL :
  https://www.opensolar.com/product-updates/release-3-8/ · https://www.opensolar.com/product-updates/release-3-13/ ·
  https://scanifly.com/blog/november-2025-pv-design-platform-updates/
- **Qui le fait** : OpenSolar : coller « 33.57, -7.58 » ou un lien Google Maps dans la barre d'adresse ⇒ la carte se centre.
- **Chez nous** : ABSENT. `apps/web/src/scripts/roofPro11/mapDraw.ts::geocode` envoie la saisie telle quelle à
  `geocodeSearchUrl` (MapTiler, borné au pays) ; aucune reconnaissance d'un couple de nombres. Un LEAD porte déjà son repère
  toit (`CalepinageNouveau.jsx`, `repere_toit` ACAL251) ; un CLIENT non (« il n'existe AUCUN géocodage serveur », même fichier).
- **Plus petite version crédible** : dans le même champ d'adresse, une saisie « nombre, nombre » (virgule ou espace) ou un
  lien de carte contenant `@lat,lng` / `q=lat,lng` centre la carte et pose l'épingle, provenance « coordonnées collées ».
  Contrôle d'inversion : le géocodage INVERSE existant (`mapDraw.ts::geocodeReverseUrl`, borné au pays) dit le lieu ; si le point
  tombe hors du pays du projet et que l'inverse y tombe, proposer « Vouliez-vous dire lng, lat ? » (aucune boîte de pays codée).
- **Simplicité** : automatique, étape Toit, aucun bouton nouveau.
- **Découpe** :
  1. Reconnaître « lat, lng » et les liens de carte dans `geocode` et recentrer sans appeler le géocodeur ; fini quand
     « 33.5731, -7.5898 » pose l'épingle à ces coordonnées (test pur). Fichier : `mapDraw.ts`.
  2. Proposer l'inversion quand le point n'est pas dans le pays du projet ; fini quand « -7.5898, 33.5731 » propose l'échange.
- **Score** : preuves 3 · adéquation 4 · effort S → **12**. Rang 5.

### CAP-D1-06 — Dire d'où vient l'image : fournisseur, date et résolution annoncées
- **Besoin** : « images pas toujours récentes » (Pylon, Capterra) ; image satellite périmée qu'on ne peut pas remplacer
  (B5 anglais #209) ; savoir si la photo date d'avant la construction de l'étage.
- **Preuves** : B6 R25 (OpenSolar 3.6/3.7, Scanifly 2025-08-27, RatedPower) ; B4 §2 (VF11006, VF10856, 2-3 sources) ;
  B5 anglais IMAGERY (8 fils, dont VF10067). URL : https://www.opensolar.com/product-updates/release-3-7-0/ ·
  https://scanifly.com/blog/august-2025-pv-design-platform-updates/ ·
  https://forum.valentin-software.com/topic/10067-updating-satellite-image-in-3d-design/
- **Qui le fait** : OpenSolar : sélecteur de date de prise de vue ; Scanifly : aperçu avant achat.
- **Chez nous** : PARTIEL. Le registre des fournisseurs a un champ `resolutionM` (`apps/web/src/lib/roofConfig.ts::ImageryProvider`)
  mais il vaut `null` pour les trois fournisseurs déclarés et n'est lu nulle part hors du fichier (grep `resolutionM`) ; aucune
  date de prise de vue. La section société `imagerie` (`apps/calepinage/services/site.py::CLES`) n'a ni date ni résolution.
- **Plus petite version crédible** : une ligne sous la carte : « Image : Mapbox (Maxar) — date et résolution non annoncées par le
  fournisseur » ; si un fournisseur publie sa résolution, la valeur vient de sa page avec l'URL (jamais estimée) ; un champ
  facultatif « date de prise de vue constatée » (saisie, source) qui alimente CAP-D1-03 et le rapport d'ombrage (D4).
- **Simplicité** : automatique, étape Toit ; la saisie de date est expert.
- **Découpe** :
  1. Afficher fournisseur + « date / résolution non annoncées » (ou la valeur publiée et sa source) sous la carte ; fini quand
     chaque fournisseur du registre rend sa ligne. Fichiers : `roofConfig.ts`, `BuilderDom.jsx`.
  2. Ranger une date de prise de vue saisie (valeur + source) dans le document ; fini quand elle survit à l'enregistrement et
     que CAP-D1-03 la lit.
- **Score** : preuves 3 · adéquation 4 · effort S → **12**. Rang 6.

### CAP-D1-07 — Marquer un pan ou des modules « déjà posés » (extension d'une installation existante)
- **Besoin** : « Mark a subsystem as existing, subtract its yield, evaluate the extension » (B5 anglais, 4 likes) ; extension
  d'une installation Huawei/Deye existante.
- **Preuves** : B5 allemand P3 (9 fils / 9 voix ; K50 7/7) ; B5 anglais P3 (4 fils, VF10736 : 13 000 modules) ; B5 espagnol 9
  (14 fils, K19 rang 7) et 16 (réserver l'extension future) ; B4 rang 7 ; B7 U21 ; OpenSolar 3.0. URL :
  https://forum.valentin-software.com/topic/9390-ertragssimulation-von-erweiterungen/ ·
  https://www.photovoltaikforum.com/thread/266042-huawei-anlage-erweitern-an-bestehenden-wr-string-verl%C3%A4ngern/ ·
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-conectados-red/60589-nueva-instalacion-fotovoltaica-deye-10kw.html
- **Qui le fait** : OpenSolar 3.0 / PV*SOL (bricolage « sous-système existant ») : les modules existants restent dessinés,
  leur énergie compte, ils sortent de la nomenclature.
- **Chez nous** : ABSENT. Aucun drapeau « existant » sur une zone (`apps/web/src/scripts/roofPro11/types.ts` : grep `existant`
  ne rend que des commentaires) ni dans `apps/calepinage/models.py`.
- **Plus petite version crédible (part D1)** : une case par pan « Modules déjà en place » avec année de mise en service SAISIE ;
  le pan est dessiné hachuré, ses modules sont non déplaçables. Parts des autres juges : D2 (nomenclature et plan de pose les
  ignorent), D3 (alerte de modules mélangés sur un même MPPT), D4 (production avec son âge). Sans année ⇒ D4 dit « âge non
  saisi », aucune dégradation inventée.
- **Simplicité** : étape Toit, expert (case repliée dans la carte du pan).
- **Découpe (D1)** :
  1. Ajouter `existant` + `anneeMiseEnService` au pan, sérialisés et relus ; fini quand le drapeau survit à l'enregistrement et
     que les modules du pan refusent le glissé en nommant la raison. Fichiers : `types.ts`, `zones.ts`, schéma `roof_layout`.
  2. Rendre le pan existant hachuré en 2D et 3D ; fini quand la vue plan (`Vue2DPlan.jsx`) et la 3D le distinguent.
- **Score** : preuves 5 · adéquation 4 · effort M → **10**. Rang 7.

### CAP-D1-08 — Comparer la visite technique et le toit dessiné, avant le devis
- **Besoin** : voir les écarts entre ce que le technicien a relevé (longueur, largeur, pente, orientation) et le toit dessiné
  sur l'image, avant d'envoyer le devis ou de commander.
- **Preuves** : B2 rang 20 (Aurora « drone true-up ») ; B3 N24 (Scanifly SimpleDesign) ; B5 allemand K51 (indirect). URL :
  https://aurorasolar.com/design-mode/ · https://scanifly.com/blog/introducing-simpledesign/
- **Qui le fait** : Aurora : la conception vendue est recalée sur le relevé drone, une feuille d'écarts sort avant le permis.
- **Chez nous** : PARTIEL. La visite relève déjà `longueur_m`, `largeur_m`, `pente_deg`, `orientation` par zone
  (`apps/visites/visite_checklist.py::CATEGORIES`, catégories `toiture` et `toiture_ci`) ; la reprise les range telles que saisies
  (`apps/calepinage/services/reprise_visite.py`) et `reprise_visite.py::_ecart` compare seulement le relevé repris à la visite
  ACTUELLE — jamais au toit dessiné. `services/asbuilt.py::ecarts_du_calepinage` compare le posé au prévu APRÈS chantier.
- **Plus petite version crédible** : dans l'onglet « Reprise de la visite », un tableau « Visite / Dessin / Écart » pour la
  pente (degrés contre `pitchDeg` du pan) et les cotes (longueur × largeur relevées contre le rectangle englobant du pan) ;
  l'orientation est montrée côte à côte, SANS conversion (« sud » n'est pas un azimut — règle D7 du fichier). Aucun seuil
  inventé : l'écart est affiché, pas jugé ; un pan sans mesure correspondante dit « non relevé ».
- **Simplicité** : étape Toit, essentiel, sous forme d'un bandeau « 2 écarts avec la visite » qui ouvre le tableau.
- **Découpe** :
  1. Calculer côté serveur les écarts visite ↔ dessin (pente, cotes) par pan ; fini quand un pan dessiné à 15° sur une visite à
     22° rend l'écart 7° avec ses deux sources. Fichiers : `apps/calepinage/services/reprise_visite.py`, son contrat.
  2. Afficher le tableau dans `atelier/RepriseVisite.jsx` ; fini quand l'écart se lit sans ouvrir la visite.
  Lecture de la visite : par `apps.visites.selectors.releve_pour_calepinage` (propriétaire `lead`, existe déjà — rien à changer).
- **Score** : preuves 2 · adéquation 5 · effort M → **5**. Rang 8.

### CAP-D1-09 — Contrôle d'échelle d'un plan DXF par son unité déclarée
- **Besoin** : « un plan d'architecte importé avec sa vraie taille ; refus clair d'un DWG avec la marche à suivre » (B5 allemand P10).
- **Preuves** : B5 allemand P10/K27 (5 fils / 5 voix) ; B5 anglais CAD-IN (6 fils : #12, #221, ligne 589) ; B6 R42 (Pylon
  2026-05 échelles A4 1:200, rognage 2026-11-18). URL :
  https://forum.valentin-software.com/topic/11069-kann-ich-grundst%C3%BCcke-als-dwg-oder-dxf-in-die-3d-planung-%C3%BCbernehmen/ ·
  https://forum.valentin-software.com/topic/10370-einf%C3%BCgen-von-pdf-pl%C3%A4nen-bei-der-3d-planung/ ·
  https://getpylon.com/blog/may-2026-update/
- **Chez nous** : PARTIEL. Le serveur LIT l'unité du DXF (`apps/calepinage/analyse_plan.py::_unite_document`, table
  `_UNITES_INSUNITS`, facteurs `_FACTEUR_UNITE`) et l'écran l'affiche (`PlanImporteCalage.jsx`, `cal-calage-unite`), mais l'échelle
  vient EXCLUSIVEMENT de deux points + distance saisie (`PlanImporteCalage.helpers.js::echelleDepuisDeuxPoints`), choix écrit en
  tête du fichier (CAL63). Refus DWG : déjà un message (`analyse_plan.py`, « pas DWG »). Rognage du plan : ABSENT.
- **Plus petite version crédible** : garder la règle (l'échelle vient de la distance SAISIE) et ajouter un CONTRÔLE : quand le
  fichier déclare une unité, l'écran affiche « selon l'unité du fichier (mm), A–B mesure 9,84 m » à côté de la distance tapée et
  signale un écart. Aucune échelle déduite sans confirmation ; unité « inconnu » ⇒ ligne absente et nommée.
- **Simplicité** : étape Toit, expert (écran d'import de plan).
- **Découpe** :
  1. Servir, pour un DXF à unité déclarée, la longueur A–B en mètres selon cette unité ; fini quand un DXF en mm de 9 840 unités
     rend 9,84 m, et un DXF sans `$INSUNITS` rend « inconnu ». Fichier : `analyse_plan.py` ou `services/import_plan.py`.
  2. Afficher le contrôle et l'écart dans `PlanImporteCalage.jsx` ; fini quand une distance tapée de 98,4 m pour 9,84 m déclarés
     affiche l'écart ×10.
- **Score** : preuves 3 · adéquation 3 · effort S → **9**. Rang 9.

### CAP-D1-10 — Pivoter tout le site d'un coup
- **Besoin** : « Can you rotate multiple buildings or change the orientation » (VF10941) ; orienter la scène entière, pas objet
  par objet (B4, FP21692/FP25823).
- **Preuves** : B5 anglais P13 (6 fils) ; B4 rang 14 (2-3 sources) ; B6 R53/K74 (PVsyst 8.0.0 2024-11-07, SolarEdge 2021-07,
  PVcase RM 1.48 ; K74 : 6 outils). URL : https://forum.valentin-software.com/topic/10941-can-you-rotate-multiple-buildings-or-change-the-orientation/ ·
  https://www.pvsyst.com/help/release-notes/index.html · https://marketing.solaredge.com/solaredge-designer-0-8
- **Chez nous** : PARTIEL. Un pan pivote seul (`apps/web/src/scripts/roofPro11/zones.ts::pivoterPan`, CALX97) avec les aides
  `pivoterPoint`/`pivoterAnneau` ; ACAL411 vise la sélection de PANNEAUX ; rien ne pivote pans + obstacles + objets
  d'environnement ensemble.
- **Plus petite version crédible** : « Pivoter le site » : un angle SAISI, autour du barycentre de tout le document ; pans,
  obstacles, objets d'environnement, panneaux posés tournent ensemble ; refus nommé si un pan n'est pas fermé. Utile surtout
  pour un plan importé ou un toit tracé sans fond d'image.
- **Simplicité** : étape Toit, expert ; une seule photo d'historique (un Annuler).
- **Découpe** :
  1. Écrire la rotation de tout le document (pure, testée) ; fini quand pivoter de 90° puis de -90° rend le document identique
     au millimètre. Fichier : `zones.ts`.
  2. Monter le bouton + champ d'angle ; fini quand l'atelier ERP pivote site et obstacles d'un seul geste annulable.
- **Score** : preuves 4 · adéquation 2 · effort S → **8**. Rang 10.

### CAP-D1-11 — Relever l'horizon au téléphone (boussole + inclinaison)
- **Besoin** : « Sans MNS ni LiDAR au Maroc, relever arbres et immeubles voisins en 30 s » (B5 allemand P2) ; mettre collines,
  bâtiments et arbres dans le calcul « sans la deviner » (B5 français, capacité #11).
- **Preuves** (les plus fortes du domaine) : B5 allemand P2 (9 fils / 18 voix, K25) ; B5 français rang 4 (6 sources ; capacité
  #11 : 8) ; B5 anglais P5 (5 fils ; ligne 497 « Horizon line scanner for Android ») ; B2 rang 18 (Scanifly) ; B7 U12 (25 lignes,
  5 sources) ; B1 V041 (PVsyst : boussole, clinomètre, photo panoramique) ; B4 flux #8 (FP64776 : boussole, rapporteur, fil à
  plomb). URL : https://www.photovoltaikforum.com/thread/257113-pv-sol-pv-gis-und-die-prognose-des-ertrages-aber-was-mit-dem-horizont-horizont-d/ ·
  https://akkudoktor.net/t/skaduz-horizont-verschattungsanalyse/42228 · https://forum-photovoltaique.fr/viewtopic.php?t=50584
- **Qui le fait** : Skaduz (application web) : gyroscope + boussole, visées successives ; SunEye (matériel payant, écarté).
- **Chez nous** : PARTIEL. Horizon PVGIS + saisie de points (`frontend/src/features/calepinage/HorizonPanel.jsx`,
  `apps/calepinage/services/horizon.py::ClientHorizon`, `_profil_saisi`, `_refuser_un_tour_incomplet`) ; import de fichier
  PLANIFIÉ (ACAL458). Aucun capteur : grep `DeviceOrientation|deviceorientation|webkitCompassHeading` dans `frontend/src` et
  `apps/web/src` = 0. Le relevé terrain sait déjà exiger une PRÉCISION pour un azimut boussole
  (`apps/calepinage/models.py::ReleveTerrain.azimut_boussole_deg` + `precision_azimut_deg`).
- **Plus petite version crédible** : au téléphone, bouton « Relever l'horizon » : on vise le haut de l'obstacle, on touche ⇒
  un point (azimut de la boussole, hauteur de l'inclinomètre) ; 8 à 12 visées guidées autour du site (B5 français) ; le profil
  part en « saisi », source « relevé téléphone », date, précision DÉCLARÉE par l'utilisateur (même règle que l'azimut boussole).
  Tour incomplet ⇒ refus existant. Capteur absent ou refusé (iOS) ⇒ saisie manuelle, dit.
- **Simplicité** : étape Toit, visible seulement sur téléphone/tablette ; remplace PVGIS seulement après validation.
- **Découpe** :
  1. Lire boussole + inclinaison du téléphone (permission iOS comprise) dans une petite couche partagée ; fini quand un faux
     capteur de test rend {azimut, hauteur} et qu'un refus de permission bascule en saisie manuelle.
  2. Mode « visée » dans `HorizonPanel.jsx` qui ajoute un point par toucher, provenance et précision portées ; fini quand
     10 visées donnent un profil accepté par `horizon.py::_profil_saisi`.
  3. Jouer le geste en spec téléphone (WebKit, capteurs simulés) ; dépend d'ACAL423/ACAL482.
- **Score** : preuves 5 · adéquation 4 · effort L → **6,7**. Rang 11.

### CAP-D1-12 — Objets d'environnement fins : poteau, câble aérien, haie, mur voisin
- **Besoin** : « Savoir combien une ombre précise coûte à l'année » : cheminée, poteau, arbre, haie, mur (B5 français, capacité
  #1 = 18 sources) ; ombre d'un câble aérien (B5 polonais).
- **Preuves** : B5 français rang 5 (6 sources) ; B5 nl-pl-tr-ar 5 (1 fil, faible) ; B6 R36 (PVcase GM 2.58, PVsyst 6.79
  pylône + câbles, OpenSolar 3.10) ; B5 espagnol 13 (poteaux de ligne de vie 40 cm, energeticambiente 38462). URL :
  https://forum-photovoltaique.fr/viewtopic.php?t=12923 · https://forum-photovoltaique.fr/viewtopic.php?t=82356 ·
  https://www.elektroda.pl/rtvforum/topic4062535.html
- **Chez nous** : ABSENT. `apps/web/src/scripts/roofPro11/environment.ts::EnvironmentKind = 'arbre' | 'batiment'` seulement.
- **Plus petite version crédible (part D1)** : deux genres de plus : « poteau » (point : hauteur + diamètre saisis) et « ligne »
  (haie, mur, câble : tracé en polyligne, hauteur et épaisseur saisies). Sans hauteur ⇒ aucune ombre (règle déjà écrite en
  tête d'`environment.ts`). Part D4 : la conversion d'une ligne en obstructions d'ombrage
  (`environment.ts::environmentShadeEntries` → `shadingEngine.ts`) est à confirmer par le juge D4.
- **Simplicité** : étape Toit, expert (« Poser un poteau », « Tracer une haie / un mur » à côté de « Poser un arbre »).
- **Découpe (D1)** :
  1. Ajouter le genre `poteau` (création, édition, anneau d'affichage) ; fini quand un poteau de 8 m posé au clic survit à
     l'enregistrement et porte une ombre dans la vue soleil.
  2. Ajouter le genre `ligne` (polyligne + hauteur + épaisseur) ; fini quand une haie de 20 m à 3 m de haut se trace, se relit et
     ombre.
- **Score** : preuves 3 · adéquation 4 · effort M → **6**. Rang 12.

### CAP-D1-13 — Aperçu des panneaux sur la photo du site (usage interne)
- **Besoin** : montrer les panneaux posés sur la vraie photo, pour un client ou une mairie qui ne lit pas la 3D.
- **Preuves** : B1 C12 (PV*SOL « Photo Plan ») ; B5 français rang 18 (capacité #33, 3 sources : FP#39769, FP#14538, FP#8836) ;
  B5 espagnol 19 (Solarius, page éditeur seule) ; B5 anglais #36 (photoplan). URL :
  https://help.valentin-software.com/pvsol/en/pages/pv-modules/photo-plan/ · https://forum-photovoltaique.fr/viewtopic.php?t=39769 ·
  https://www.accasoftware.com/en/solarius-pv
- **Chez nous** : ABSENT dans ce sens. `frontend/src/features/calepinage/PhotoSiteCalage.jsx` cale la photo sur la carte par
  4 coins et la DRAPE sur la carte (photo → carte) ; rien ne projette les modules SUR la photo (carte → photo). Sortie image 3D :
  `frontend/src/features/calepinage/exportImage.js`.
- **Plus petite version crédible** : « Voir sur la photo » : avec le calage 4 coins existant, les rectangles des modules posés sont
  projetés sur la photo (projection plane inverse, toit supposé plan — dit à l'écran), export PNG interne. Sans calage ⇒ bouton
  absent et nommé. RÈGLE #4 : rien dans le PDF client hors `/proposal` ; toute version client part chez D6 avec accord de Reda.
- **Simplicité** : onglet Photos du site, essentiel (un bouton).
- **Découpe** :
  1. Projeter les modules de la carte vers les pixels de la photo calée (fonction pure, inverse du calage) ; fini quand les
     4 coins de calage reviennent sur leurs pixels à moins d'un pixel.
  2. Bouton « Voir sur la photo » + export PNG dans `PhotoSiteCalage.jsx` ; fini quand l'image montre les modules du pan.
- **Score** : preuves 3 · adéquation 4 · effort M → **6**. Rang 13.

### CAP-D1-14 — Détecter aussi les obstacles et proposer les semblables (IA)
- **Besoin** : après le contour, proposer les climatiseurs / lanterneaux visibles, à confirmer un par un.
- **Preuves** : B2 rang 7 (Aurora IA d'obstacles, SolarEdge Designer, Reonic) ; B3 N22 (HelioScope « Similar Obstruction
  Detection », ≥ 70 % de ressemblance ; SolarEdge 2022-02) ; B6 K15 (5 outils) et K47. URL :
  https://help-center.helioscope.com/hc/en-us/articles/32833326179347-Similar-Obstruction-Detection ·
  https://marketing.solaredge.com/solaredge-designer-0-20 · https://aurorasolar.com/pricing/
- **Chez nous** : DÉJÀ PLANIFIÉ pour le contour et les pans (ACAL391 contrat, ACAL485 serveur, ACAL488 onglet ; IA admise par
  D-ACAL-33) ; obstacles : ABSENT et non planifié.
- **Plus petite version crédible** : la même demande d'ACAL485 rend aussi une liste d'obstacles PROPOSÉS (type, rectangle en
  fractions d'image), cochables sous le contour proposé, provenance `DEVINE` jusqu'à confirmation.
- **Simplicité** : étape Toit, essentiel, dans l'onglet « Détection du toit ».
- **Découpe** :
  1. [après la mesure de fiabilité d'ACAL485, comme le dit B3] Étendre le contrat `calepinage_detection_toit.json` aux
     obstacles proposés ; fini quand l'échantillon porte une liste d'obstacles et ses refus nommés. Dépend d'ACAL391/485.
  2. Afficher et cocher les obstacles proposés ; fini quand un obstacle coché devient un obstacle de l'atelier à confirmer.
     Dépend d'ACAL488.
- **Score** : preuves 4 · adéquation 3 · effort M → **6**. Rang 14.

### CAP-D1-15 — Arbre : aujourd'hui, plus tard, ou coupé
- **Besoin** : « les arbres vont grandir » (staff Valentin, VF10451) ; arbre caduc moins opaque l'hiver ; « et si on abattait
  cet arbre ? ».
- **Preuves** : B5 anglais P4 (3 fils + ligne #287 « deciduous trees stay opaque in winter ») ; B5 français rang 5 (caduc) ;
  B3 N27 (Scanifly « Occluders », jusqu'à 16). URL : https://forum.valentin-software.com/topic/10451-shadows/ ·
  https://www.solarquotes.com.au/blog/solar-panels-trees-shade/ · https://scanifly.com/?p=9329
- **Chez nous** : PARTIEL. Le drapeau « persistant / caduc » est SAISI et rangé (`environment.ts::withEvergreen`, case
  `data-env-evergreen` dans `obstaclesUi.ts`, relu par `prefill.ts`) mais aucun calcul ne le lit (grep `evergreen` absent de
  `lib/shadingEngine.ts`) ; hauteur future : ABSENTE ; « ignorer cet objet » : ABSENT (aucune bascule dans `environment.ts`).
- **Plus petite version crédible (part D1)** : par arbre, deux champs facultatifs « hauteur dans __ ans : __ m » (les deux
  SAISIS, aucune croissance inventée) et une case « Supposer coupé ». Part D4 : afficher la perte d'ombrage avec la hauteur
  future et sans l'arbre ; la transparence saisonnière d'un caduc ne s'applique que si une transparence mensuelle SOURCÉE est
  saisie (sinon opaque, dit) — calcul pour D4.
- **Simplicité** : étape Toit, expert ; masqué si le site n'a pas d'arbre.
- **Découpe (D1)** :
  1. Ajouter `hauteurFutureM` + `dansAns` et `supposeCoupe` à l'objet arbre, sérialisés ; fini quand les trois survivent à
     l'enregistrement et qu'un arbre « supposé coupé » ne porte plus d'ombre dans la vue soleil.
- **Score** : preuves 3 · adéquation 3 · effort M → **4,5**. Rang 15.

### CAP-D1-16 — Pente et orientation d'un pan mesurées en posant le téléphone sur le toit
- **Besoin** : « il faut tout relever sur place » (B6, Maroc sans MNS) ; aide quand le toit est mal vu (B4 #22, VF10794/VF10856).
- **Preuves** : B6 R55/K56 (Scanifly Mobile 2026-10-21 : inclinaison téléphone posé + lecture d'azimut) ; B4 wishlist #22 ;
  B7 (avis d'applis : imprécision de boussole, PV Solar Tilt, Sun Seeker). URL :
  https://scanifly.com/blog/scanifly-mobile-solar-site-survey-app (URL tronquée dans l'extrait B6) ·
  https://apps.apple.com/gb/app/id1492982128
- **Chez nous** : ABSENT (aucun capteur, voir CAP-D1-11). Le relevé terrain a les champs `azimut_boussole_deg` +
  `precision_azimut_deg` obligatoires ensemble (`models.py::ReleveTerrain.clean`) et la provenance RELEVE existe
  (`lib/obstacles.ts::ObstacleProvenance`).
- **Plus petite version crédible** : bouton « Mesurer avec le téléphone » dans la carte du pan (téléphone seulement) : l'inclinaison
  posé à plat sur la tuile, l'azimut boussole ; valeurs PROPOSÉES, précision déclarée, confirmées par un toucher, source
  « relevé téléphone ». Toit métallique : avertissement « la boussole peut dévier près du métal » (texte, aucun chiffre).
- **Simplicité** : étape Toit, essentiel au téléphone, invisible au bureau.
- **Découpe** :
  1. Brancher la couche capteurs de CAP-D1-11 sur la carte du pan ; fini quand un faux capteur à 22° propose 22° « à confirmer »
     et que confirmer écrit la source. Dépend de CAP-D1-11 tâche 1 et d'ACAL417 (pente « à confirmer »).
- **Score** : preuves 2 · adéquation 4 · effort M → **4**. Rang 16.

### CAP-D1-17 — Repères de chantier sur le plan : ancrage antichute avec rayon, passage de câble, note
- **Besoin** : annoter le plan pour l'équipe de pose (points d'ancrage et leur rayon de travail sûr, passages, emplacement
  onduleur, note libre).
- **Preuves** : B2 rang 4 (OpenSolar 3.8 annotations, 3.10/3.12 ancrage + rayon ; Scanifly photos annotées) ; B6 R44/K18
  (OpenSolar 3.10 2026-08-21, Pylon 2026-09). URL : https://www.opensolar.com/product-updates/release-3-10/ ·
  https://www.opensolar.com/product-updates/release-3-12/ · https://www.opensolar.com/product-updates/release-3-8/
- **Chez nous** : ABSENT (grep `ancrage|anchor|ligne de vie` : seuls des « ancrages » géographiques, `entreeMoteur.ts::Ancrage`).
  Seul l'outil de mesure existe (`roofPro11/mesureUi.ts`).
- **Plus petite version crédible (part D1)** : un calque « Repères » : type (ancrage, passage de câble, onduleur, tableau, note),
  texte, rayon facultatif SAISI ; rangé au document. Part D6 : impression sur le plan de pose / plan de masse avec légende
  (jamais sur le PDF client).
- **Simplicité** : étape Toit, expert (outil à côté de « Mesure »).
- **Découpe (D1)** :
  1. Ajouter les repères au document (pose au clic, édition, suppression, relecture) ; fini quand un ancrage de rayon 2,5 m saisi
     survit à l'enregistrement et se dessine avec son cercle.
- **Score** : preuves 2 · adéquation 4 · effort M → **4**. Rang 17.

### CAP-D1-18 — Liste des objets du site en tableau
- **Besoin** : gérer un toit tertiaire à 30 obstacles et plus sans les cliquer un par un.
- **Preuves** : B1 C13 (PVsyst « List and management of objects » : filtre, tri, édition groupée, CSV) ; B6 R54/K75 (PVsyst
  6.40…7.2.9, SolarEdge 2021-07, Polysun). URL :
  https://www.pvsyst.com/help/project-design/shadings/near-shadings-advanced-selection/List-and-management-of-objects.html ·
  https://www.pvsyst.com/help/release-notes/index.html
- **Chez nous** : PARTIEL. Les objets d'environnement ont une liste (`obstaclesUi.ts`, `rp9-env-list`) ; les obstacles s'éditent un
  par un (`rp9-obs-edit`), sans tableau ni filtre.
- **Plus petite version crédible** : un tableau replié « Objets du site » (type, cotes, hauteur, provenance, pan) : un clic
  sélectionne l'objet sur la carte ; filtre par type et par provenance (« non relevés » d'abord). Pas d'export (D6 si demandé).
- **Simplicité** : étape Toit, expert.
- **Découpe** :
  1. Afficher le tableau lu dans le contexte de l'atelier, clic = sélection ; fini quand 30 obstacles se listent et que cliquer une
     ligne sélectionne l'obstacle. Fichiers : `obstaclesUi.ts` ou un panneau React d'`atelier/`.
- **Score** : preuves 2 · adéquation 3 · effort M → **3**. Rang 18.

### CAP-D1-19 — Verrouiller un bâtiment ou un pan contre le faux clic
- **Besoin** : « Lock a complex building and its surroundings so one misclick cannot destroy the layout » (VF, 2020 et 2023).
- **Preuves** : B5 anglais P7 (3 fils) ; B4 wishlist #1 (VF1094, VF1096). URL :
  https://forum.valentin-software.com/topic/1094-pvsol-wishlist/page/2/ · https://forum.valentin-software.com/topic/1096-pvsol-wunschliste/page/3/
- **Chez nous** : ABSENT. Le seul verrou est celui des versions figées (`apps/calepinage/services/verrou.py`) ; ACAL413 couvre
  « Tout effacer » sans filet, pas le verrou d'un objet.
- **Plus petite version crédible** : un cadenas par pan (et par objet d'environnement) : verrouillé ⇒ sommets, glissé et
  suppression refusés avec le motif « pan verrouillé — déverrouillez-le d'abord ».
- **Simplicité** : étape Toit, expert ; utile au téléphone (ACAL423).
- **Découpe** :
  1. Ajouter `verrouille` au pan et le faire respecter par les gestes de sommet, glissé et suppression ; fini quand chaque geste
     refuse en nommant le pan.
- **Score** : preuves 2 · adéquation 3 · effort M → **3**. Rang 19.

### CAP-D1-20 — Aide « hauteur d'un bâtiment voisin » (étages × hauteur d'étage)
- **Besoin** : estimer la hauteur d'un immeuble voisin quand on ne la connaît pas (B5 espagnol : 15 étages, « 45 à 50 m »).
- **Preuves** : B5 espagnol 17 (1 fil, 2 lignes). URL :
  https://www.solarweb.net/forosolar/fotovoltaica-sistemas-conectados-red/14550-sombras-sketchup.html
- **Chez nous** : ABSENT pour un voisin ; le bâtiment PROPRE a déjà `etages` × `hauteurEtageM` SAISIS
  (`apps/web/src/scripts/roofPro11/batiment.ts`, CALX100) ; un voisin n'a que `heightM` (`environment.ts::EnvironmentObject`).
- **Plus petite version crédible** : dans la carte d'un bâtiment voisin, « nombre d'étages × hauteur d'étage » (les deux SAISIS)
  propose une hauteur marquée « estimée », modifiable ; aucune hauteur d'étage par défaut.
- **Simplicité** : étape Toit, essentiel, deux petits champs.
- **Découpe** :
  1. Réutiliser le calcul de `batiment.ts` pour les voisins ; fini quand 5 étages × 3 m proposent 15 m « estimée ».
- **Score** : preuves 1 · adéquation 3 · effort S → **3**. Rang 20.

### CAP-D1-21 — Lire pente et orientation sur le relief d'un drone (GeoTIFF fourni par l'installateur)
- **Besoin** : « le toit lu sur la photo du drone » : pente, azimut, hauteurs sans LiDAR (B2 rang 1).
- **Preuves** : B2 rang 1 (Aurora drone mapping, Reonic) ; B6 R6 (PVcase RM 1.48 Airteam, Aurora, Scanifly, PV*SOL Rexplorer) ;
  B7 U23 (4 sources) ; B5 allemand K04 (8 fils / 23 voix) et K24 ; B5 anglais MESH (27 fils cumulés). URL :
  https://aurorasolar.com/drone-mapping/ · https://help.pvcase.com/hc/en-us/articles/40353898032915-Release-notes-1-48 ·
  https://www.photovoltaikforum.com/thread/211998-3d-drohnenvermessung-welches-softwaretool/
- **Chez nous** : PARTIEL. Le moteur d'ajustement de plan existe et accepte un altimètre injecté
  (`apps/calepinage/services/lidar_ign.py::suggerer_pentes(…, altimetre=…)`, `_ajuster_plan`, suggestions jamais appliquées sans
  validation) mais il est réservé à la France (`service_disponible`, `pays == 'fr'`). ACAL424 (PLANIFIÉ) ne cale que l'IMAGE
  (fichier monde). La photogrammétrie elle-même reste GATED (CALX374, VTG1).
- **Plus petite version crédible** : déposer un GeoTIFF d'altitudes produit par l'outil du drone de l'installateur ; un altimètre
  « fichier » le lit et la même proposition « pente / azimut à confirmer » sort par pan. Pas de calcul de photogrammétrie chez
  nous. Nouvelle dépendance de lecture GeoTIFF probable : à NOTER (DONE LOG) et à faire valider ; si refusée, la capacité reste
  ABSENTE.
- **Simplicité** : onglet Pente, expert (« Lire la pente sur un relief de drone »).
- **Découpe** :
  1. Écrire un altimètre qui lit un GeoTIFF déposé (projection en degrés seulement, comme ACAL424 ; mètres refusés en le
     nommant) ; fini quand un relief synthétique incliné de 20° vers le sud rend 20° / 180° par `suggerer_pentes`.
  2. Ouvrir `suggerer_pentes` à cet altimètre hors France sans toucher la porte IGN ; fini quand une société marocaine obtient
     une suggestion depuis son fichier et zéro appel IGN. Dépend d'ACAL424 (même dépôt de fichier géoréférencé).
- **Score** : preuves 4 · adéquation 2 · effort L → **2,7**. Rang 21.

### CAP-D1-22 — Exporter la géométrie du site (GeoJSON / KML pour Google Earth, glTF pour un architecte)
- **Besoin** : « sortir la scène 3D avec l'implantation pour un client ou un architecte » (B5 allemand P18) ; ouvrir le champ
  agricole dans Google Earth.
- **Preuves** : B5 allemand P18/K19 (1 fil « Wunschliste », 17 voix) ; B6 R56 (PVcase GM 2.53…2.64 KML) ; B6 K52 (6 outils
  d'export CAO/SIG). URL : https://forum.valentin-software.com/topic/1096-pvsol-wunschliste/ ·
  https://help.pvcase.com/hc/en-us/articles/54734740370323-Release-notes-2-64
- **Chez nous** : PARTIEL. DXF présent (`apps/calepinage/services/export_dxf.py`), plus XLSX/CSV/JSON ; KML, GeoJSON et glTF
  absents des exports (grep `kml|gltf|GLTFExporter` : aucun exportateur ; les hits sont des lectures GeoJSON internes).
- **Plus petite version crédible** : dans Documents, « Exporter pour Google Earth » (KML : pans, zones interdites, rangées, en
  lng/lat déjà au document) ; glTF de la scène Three.js existante (`scene3d.ts`) en second. Rien ne part au client par ce chemin.
- **Simplicité** : étape Documents, expert.
- **Découpe** :
  1. Exporter pans + zones + modules en KML ; fini quand le fichier s'ouvre dans un lecteur KML de test avec le bon nombre de
     polygones. Fichiers : nouveau service d'export dans `apps/calepinage/services/`.
  2. Exporter la scène en glTF depuis l'atelier ; fini quand le fichier relu par le chargeur glTF de three rend le même nombre de
     modules.
- **Score** : preuves 3 · adéquation 2 · effort M → **3**. Rang 22.

### CAP-D1-23 — Toit en sheds (dents de scie)
- **Besoin** : poser sur une toiture de hall industriel en sheds, avec l'ombre d'un shed sur l'autre.
- **Preuves** : B5 français rang 17 (2 fils 2008-2009, preuve mince, inférence « halls industriels marocains » non vérifiée).
  URL : https://forum-photovoltaique.fr/viewtopic.php?t=8846 · https://forum-photovoltaique.fr/viewtopic.php?t=8851
- **Chez nous** : ABSENT. Le préréglage `shed` de `apps/web/src/scripts/roofPro11/scene3d.ts::RoofShapePreset` est un appentis
  (une seule pente).
- **Plus petite version crédible** : un préréglage « Sheds » qui découpe le contour en N bandes identiques SAISIES (nombre,
  pente, sens) ; chaque bande devient un pan.
- **Simplicité** : étape Toit, une puce de plus dans la rangée « Forme du toit ».
- **Découpe** :
  1. Ajouter `sheds` à `generateRoofShapePans` ; fini quand un contour 30 × 20 m en 5 sheds rend 5 pans de 6 m. Dépend
     d'ACAL410 (les puces).
- **Score** : preuves 1 · adéquation 3 · effort M → **1,5**. Rang 23.

---

## C. Table de synthèse

| Rang | CAP | Titre | Verdict | Tâches | Effort | Score |
|---|---|---|---|---|---|---|
| 1 | CAP-D1-01 | Dupliquer un obstacle et le poser en série | PRÉSENT SANS ÉCRAN | 2 | S | 20 |
| 2 | CAP-D1-02 | Écran des gabarits d'obstacle (et de zone) de la société | PRÉSENT SANS ÉCRAN (écriture) | 2 | M | 6 |
| 3 | CAP-D1-03 | Hauteur par l'ombre sur l'image (+ date de prise de vue saisie) | PRÉSENT SANS ÉCRAN | 2 | M | 7,5 |
| 4 | CAP-D1-04 | Plus de types d'obstacles (lanterneau, clim, citerne…) | PARTIEL (moteur et traduction prêts) | 2 | S | 20 |
| 5 | CAP-D1-05 | Démarrer en collant des coordonnées GPS ou un lien | ABSENT | 2 | S | 12 |
| 6 | CAP-D1-06 | Fournisseur, date et résolution de l'image | PARTIEL | 2 | S | 12 |
| 7 | CAP-D1-07 | Pan « déjà posé » (extension) — part D1 | ABSENT | 2 | M | 10 |
| 8 | CAP-D1-08 | Écarts visite technique ↔ toit dessiné | PARTIEL | 2 | M | 5 |
| 9 | CAP-D1-09 | Contrôle d'échelle d'un DXF par son unité | PARTIEL | 2 | S | 9 |
| 10 | CAP-D1-10 | Pivoter tout le site | PARTIEL | 2 | S | 8 |
| 11 | CAP-D1-11 | Horizon relevé au téléphone | PARTIEL | 3 | L | 6,7 |
| 12 | CAP-D1-12 | Poteau, câble, haie, mur voisin | ABSENT | 2 | M | 6 |
| 13 | CAP-D1-13 | Panneaux sur la photo du site (interne) | ABSENT | 2 | M | 6 |
| 14 | CAP-D1-14 | Obstacles détectés par l'IA | DÉJÀ PLANIFIÉ (toit) / ABSENT (obstacles) | 2 | M | 6 |
| 15 | CAP-D1-15 | Arbre : plus tard, caduc, coupé — part D1 | PARTIEL | 1 | M | 4,5 |
| 16 | CAP-D1-16 | Pente/azimut au téléphone posé sur le toit | ABSENT | 1 | M | 4 |
| 17 | CAP-D1-17 | Repères de chantier (ancrage + rayon) — part D1 | ABSENT | 1 | M | 4 |
| 18 | CAP-D1-18 | Tableau des objets du site | PARTIEL | 1 | M | 3 |
| 19 | CAP-D1-19 | Verrou d'un pan / bâtiment | ABSENT | 1 | M | 3 |
| 20 | CAP-D1-20 | Hauteur d'un voisin par ses étages | ABSENT | 1 | S | 3 |
| 21 | CAP-D1-21 | Pente lue sur un relief de drone (GeoTIFF) | PARTIEL | 2 | L | 2,7 |
| 22 | CAP-D1-22 | Export KML / glTF | PARTIEL | 2 | M | 3 |
| 23 | CAP-D1-23 | Toit en sheds | ABSENT | 1 | M | 1,5 |

Total : 23 fiches, 40 tâches. Ordre : les trois PRÉSENT SANS ÉCRAN purs en tête (brief), puis par score, à score proche
l'adéquation l'emporte (CAP-D1-04 placé juste après la tête car son moteur est prêt).

---

## D. Déjà planifié (aucune fiche : la tâche existe)

| Capacité | Tâche existante | Ce qu'elle couvre / ce qui reste |
|---|---|---|
| Formes de toit en un clic (Plat, 1, 2, 4 pans, L, T) | ACAL410 | Couvre tout. PRÉSENT SANS ÉCRAN : `scene3d.ts::generateRoofShapePans` et `zones.ts::buildAreasFromShape` n'ont AUCUN appelant (grep). Sheds = CAP-D1-23. |
| Toit par longueur × largeur | ACAL422 (+ CALX90/CALX97 faits : longueur tapée, cotes d'un pan) | Couvre tout. |
| Annuler / rétablir dès le tracé ; filet des effacements | ACAL412, ACAL413 | Couvre le tracé et les obstacles ; « coller » reste dans CAP-D1-01. |
| Atelier au téléphone (390 px) et parcours téléphone | ACAL423, ACAL482 | Couvre l'affichage ; capteurs = CAP-D1-11/16. |
| Orthophoto de drone par fichier monde | ACAL424 | Couvre l'image ; le relief = CAP-D1-21. |
| Horizon depuis un fichier (.hor, PVGIS) | ACAL458 | Couvre l'import ; relevé téléphone = CAP-D1-11. |
| Quatre vues de caméra (Dessus, Sud, 3/4, Face) | ACAL435 | Couvre les vues. Vue de dessus orthographique : `Vue2DPlan.jsx` (CAL104) EXISTE en lecture ; poser des obstacles en vue ortho n'est pas demandé au-delà (B5 anglais P9 avait tort de dire « ABSENT »). |
| « Je ne connais pas la pente » ; pente « à confirmer » ; avertissement au devis | ACAL416, ACAL417, ACAL426 | Couvre aussi « 60 % saisi pour 60° » (B5 français rang 7, B7 U27). |
| Relief d'un champ au sol | ACAL466 (Copernicus GLO-30) | Couvre (B5 français #35, B5 anglais TERRAIN). |
| Contour et pans par IA | ACAL391, ACAL485, ACAL488 | Couvre le toit ; obstacles = CAP-D1-14. |
| Conception automatique depuis le lead (OSM + optimiseur) ; passerelle devis rapide → atelier | ACAL421 | Couvre la moitié de B3 N15 ; le reste est D6. |
| Brouillon côté serveur | ACAL400 | Couvre (B4 rang 17 côté bureau). |
| Aide flottante « Localisez le toit » | ACAL420 | D6 surtout. |

## E. Présent et visible (aucune fiche)

- **Relevé de visite au téléphone, photos nommées obligatoires, file d'envoi hors ligne** : PRÉSENT dans l'app Visites
  (propriétaire `lead`) : `apps/visites/visite_checklist.py::CATEGORIES` (tuiles photo nommées avec `min_photos`, mesures
  attendues, complétude calculée serveur) ; `frontend/src/features/visites/visitesOffline.js` (mesures et PHOTOS mises en file,
  rejouées au retour du réseau, VTA10) ; reprise dans le calepinage par `apps/calepinage/services/reprise_visite.py` (CALX364).
  Checklist toit-terrasse (B5 français rang 13) : `toiture_ci` avec `toiture_etancheite` et l'objet « Étanchéité » (type, âge).
- Fond de plan PDF/DXF/image calé par 2 points + distance (`PlanImporteCalage.jsx`, CALX107/108) ; photo calée 4 coins
  (`PhotoSiteCalage.jsx`) ; fournisseurs d'imagerie (`roofConfig.ts`) ; plusieurs bâtiments (`types.ts` `buildingId`, CAL59) ;
  lucarne qui perce le pan (CALX102) ; acrotère en volume (CALX101) ; obstacle polygonal et circulaire (CALX103/104) ; arbre et
  bâtiment voisin au clic (CALX105) ; hauteur OSM proposée (CALX106/132) ; arêtes typées et retrait par arête (CALX93-95) ;
  mesure (`mesureUi.ts`) ; export DXF (`export_dxf.py`) ; refus DWG nommé (`analyse_plan.py`).

## F. Écarté (raison en une ligne)

- Google Solar, LiDAR / imagerie payante, Nearmap, Rexplorer, Google 3D (B1 S035/S036, B2 A03/O03, B3 R8, B6 K20, B5 anglais #138) : données payantes ou sans couverture Maroc (D-CALX-PAYANT ; CAL51 et CALX131 GATED).
- Photogrammétrie par drone côté serveur, service de modélisation à distance (B2 A04, B3 R79/R199, B5 allemand K04 partie service) : payant / différé (CALX374, VTG1 GATED).
- Import de modèle 3D (OBJ, glTF, IFC, SketchUp, CityGML, DAE) comme volume d'ombrage (B2 rang 15, B1 V073/V074/S041, B6 K24, B5 anglais MESH/#22) : aucun chargeur (grep `GLTFLoader|OBJLoader` vide), sans source de maillage tant que la photogrammétrie est GATED ; la garde « modèle trop lourd » (B4 rang 20) tombe avec lui.
- Export COLLADA / PVCollada vers PVsyst (B6 R17, B3 §4) : aucun consommateur chez cet utilisateur (PVsyst payant ; Reda ne peut fournir aucun fichier PVsyst, commit `5a75a182b`).
- Export DWG (B5 nl 7, une page éditeur) : le DXF couvre ; pas de lecteur/écrivain DWG libre sans dépendance lourde.
- Superposition KMZ/KML en import (B3 R4/R7, B3 §4) : rare ; ACAL424 couvre l'orthophoto.
- Alerte d'écart d'azimut pan / bâtiment (B6 R61) : 1 outil, seuil de 10° non sourcé.
- Contrôle de raccord 3D des pans (B6 R41) : 2 outils en notes de version, aucune voix d'utilisateur ; les pans sont plans et calés par `scene3d.ts::computeMixedAltitudeOffsets`.
- Pente par ARÊTE d'un même polygone (B2 rang 13, B6 K22) : déjà faisable en traçant un pan par pente (pente par pan) ; formes = ACAL410.
- Toit courbe, aplatir un toit non plan, modules sur les faces de lucarne (B5 anglais #152-153, B3 §4) : hors des toits visés.
- Bâtiments réutilisés d'un projet à l'autre (B5 anglais P2.1 I, B4 wishlist #17) : chaque toit est unique ; variantes dupliquées par `services/variantes.py`.
- Éblouissement aviation / voisins (B5 anglais #40) : 1 fil, calcul D4, non proposé.
- Commande vocale « calepinage depuis la fiche lead » (B2 rang 19, B6 R63) : D6 (assistant), interrupteurs éteints.
- Textures de couverture (B5 allemand P15, K42) : renvoyé à D6 (apparence) ; texture des modules = ACAL433.

## G. Renvoyé à un autre juge (part hors D1)

- D2 : surélévation / façade (B5 français rang 16), dalle béton à pieds (B2 rang 6, B6 R14), type de couverture par pan qui pilote
  la fixation (B6 R11), retraits par TYPE d'arête et multi-arêtes (B3 N26, B6 R58), retraits/acrotère « Maghreb » (B5 français
  rang 11), appliquer les réglages d'un pan à un autre (B3 N14), « pourquoi aucun module ? » (B3 N28), inclinaison sur dalle
  pentue (B3 N3), et la note « coefficients codés » de `CLEARANCE_BY_TYPE` (CAP-D1-04). Échafaudage (B5 anglais P12) : ligne de
  nomenclature = D2/D6 ; D1 fournit déjà périmètre et hauteur (CALX100) ; la marge « + 2 m » de la formule citée n'a pas de source.
- D3 : import de plan de chaînes (B4 rang 8, B7 U28, B5 allemand P8) ; DXF en blocs nommés par chaîne (B3 N20, B6 R33).
- D4 : seuil d'accès solaire codé `SOLAR_ACCESS_LOW` (B6 R40) ; `DIFFUSE_FRACTION_WHEN_SHADED = 0.25` vu en passant dans
  `shadingEngine.ts` ; parts calcul de CAP-D1-12/15.
- D6 : vidéo orbite (B3 N32), visionneuse 3D client (B6 R18), photos de visite dans le rapport interne (B4 rang 13, B6 R59),
  plan de pose lisible hors ligne pour le chef d'équipe (B3 N10), verrou à l'acceptation du devis (B3 N16, décision fondateur),
  impression des repères (CAP-D1-17), projets d'exemple (B1 C18).

## H. Contradictions entre lanes tranchées par le code

1. **Relevé hors ligne et photos obligatoires** — B3 N10 (« hors ligne non vérifié »), B6 R12 (« pas d'app hors ligne »), B4 rangs
   17/19 (« ajouter une file d'attente ») avaient TORT : `apps/visites/visite_checklist.py` déclare les photos nommées et
   `min_photos`, `frontend/src/features/visites/visitesOffline.js` met mesures ET photos en file. Ce qui manque est la comparaison
   visite ↔ dessin (CAP-D1-08), pas le relevé.
2. **Nombre de types d'obstacles** — « 6 types » (B2, B6 R4, B5 nl) contre « 13 types » (B5 français) : les deux ont raison à deux
   étages différents (`types.ts::OBSTACLE_TYPES` = 6 ; `core/calepinage/types.py::TypeObstacle` = 13) ; l'écart est la capacité
   CAP-D1-04.
3. **Duplication d'obstacle** — B3 §7.2 la corrige en « PRÉSENT » : le code existe mais le bouton n'a aucun balisage
   (CAP-D1-01) ; pour l'utilisateur c'est absent.
4. **Hauteur par l'ombre** — B3 R16 et B5 allemand K01 « PRÉSENT » : sans balisage `rp9-shade-*` (CAP-D1-03), et avec une date de
   prise de vue par défaut inventée.
5. **Gabarits d'obstacle de la société** — B1 V069 et B6 R4 les donnent présents (CALX104) : lus et posés oui, mais aucun écran
   pour les créer (CAP-D1-02).
6. **Import 3D** — B2 rang 15 le propose, B1 §5 l'écarte : écarté (aucun chargeur, source de maillage GATED).
7. **Vue orthographique** — B5 anglais P9 « ABSENT (seule caméra ortho = celle de l'ombre) » : `Vue2DPlan.jsx` est une vue plan
   orthographique (CAL104) ; le reste est ACAL435.
8. **Unité du DXF** — B5 allemand P10 « lit déjà l'unité » : juste (`analyse_plan.py::_unite_document`), mais l'écran l'ignore
   VOLONTAIREMENT pour l'échelle (en-tête CAL63) ; d'où un CONTRÔLE et non une échelle déduite (CAP-D1-09).
9. **Formes L/T** — B5 anglais et B6 K22 « codées sans bouton » : juste (aucun appelant), ACAL410 planifiée.
10. **Arbre caduc** — B5 français « drapeau saisi, jamais utilisé » : juste (`withEvergreen` saisi, absent de `shadingEngine.ts`).

## I. Tableau de correspondance (id d'origine → sort)

- **B1** : C12 → CAP-D1-13 · C13 → CAP-D1-18 · C02 → D2/D4 · C09 → D4 (vue soleil ACAL434) · C18 → D6 · V040 présent · V041 → CAP-D1-11 · V042 → ACAL458 · V069 → CAP-D1-02 · V072 → ACAL435 · V073/V074/S041 → écarté · V075 → écarté · V076 → ACAL466 · V077 présent / ACAL424 · V078 → CAP-D1-18 · V079 → CAP-D1-15 (bascule) · S052 → CAP-D1-13 · S035/S036 → écarté. Autres C (01, 03-08, 10, 11, 14-17, 19-26) : hors D1.
- **B2** : 1 → CAP-D1-21 · 3 → CAP-D1-04 · 4 → CAP-D1-17 · 5 → CAP-D1-05 · 7 → CAP-D1-14 · 13 → écarté (pente par arête) / CALX102 fait · 15 → écarté · 18 → CAP-D1-11 · 20 → CAP-D1-08 · 6 → D2 · 9 → D2 · 19 → écarté (D6). Autres rangs : hors D1.
- **B3** : N13/N13b → CAP-D1-01 · N19 → CAP-D1-02 · N22 → CAP-D1-14 · N24 → CAP-D1-08 · N26 → D2 · N27 → CAP-D1-15 · N3 → D2 · N10 → D6 · N14 → D2 · N15 → ACAL421 / D6 · N16 → D6 · N17 → D5/lead (hors D1 : consommation) · N20 → D3 · N28 → D2 · N32 → D6. Autres N : hors D1.
- **B4** : rang 5 → CAP-D1-01 (coller) + ACAL412 · 7 → CAP-D1-07 · 8 → D3 · 13 → D6 · 14 → CAP-D1-10 · 17 → présent (Visites) + ACAL400 · 19 → présent (Visites) · 20 → écarté · wishlist #1 → CAP-D1-19 · #2 → CALX90 fait · #8 → ACAL410 · #21 → CAP-D1-06 · #22 → CAP-D1-16 / ACAL416 · #23-24 → écarté.
- **B5 allemand** : P2 → CAP-D1-11 · P6 (échelle depuis un objet connu : tuile, porte, module) → **non retenu en fiche** : la calibration par 2 points + distance SAISIE (`PlanImporteCalage.jsx`) le permet déjà si l'utilisateur tape la longueur de l'objet ; la table de 350 modèles de tuiles (Tegrona) serait une donnée à sourcer — écarté pour ce tour · P10 → CAP-D1-09 · P15 → écarté (D6) · P18 → CAP-D1-22 · P3 → CAP-D1-07 · P5 → D2 · P1 → D6/D4 · K01 → CAP-D1-03 · K04 → écarté · K05/K06 → ACAL422 + présent · K13 → présent + CAP-D1-04 · K24/K49 → CAP-D1-21 / P6 · K25 → CAP-D1-11 · K26 → CAP-D1-06 + présent · K27 → CAP-D1-09 · K30 → ACAL423 · K37 → présent / ACAL466 · K40 → ACAL435 · K42 → écarté · K50 → CAP-D1-07 · K51 → CAP-D1-08 (indirect).
- **B5 français** : 4 → CAP-D1-11 · 5 → CAP-D1-12 + CAP-D1-15 · 13 → présent (Visites `toiture_ci`) · 16 → D2 · 17 → CAP-D1-23 · 18 → CAP-D1-13 · 7 → CAP-D1-05 (lat/long) + ACAL416 · 8, 11, 14 → D2 · 9 → D2/D4.
- **B5 nl-pl-tr-ar** : 5 → CAP-D1-12 · 7 → écarté (DWG) · grappes 4, 15 → présent.
- **B5 anglais** : 4 → CAP-D1-15 · 5 → CAP-D1-11 · 7 → CAP-D1-19 · 9 → ACAL435 + présent (`Vue2DPlan.jsx`) · 13 → CAP-D1-10 · 3 → CAP-D1-07 · 12 → D2/D6 · 20 → ACAL440 (D2/D4) · #1/ROOFSHAPE → ACAL410 + CAP-D1-04 · IMAGERY → écarté + CAP-D1-06 · CAD-IN → CAP-D1-09 + présent · MESH → écarté · EXIST → CAP-D1-07 · #40 → écarté · TERRAIN → ACAL466.
- **B5 es-pt-it** : 17 → CAP-D1-20 · 19 → CAP-D1-13 · 9, 16 → CAP-D1-07 · 13 → CAP-D1-12 (poteaux) / D2 · 18 → D4/D2 · 27 → D5 · K24 → présent / ACAL421/485 · K13 → présent (`services/contenance.py`) · K39 → présent.
- **B6** : R4 → CAP-D1-04 · R6 → CAP-D1-21 · R12 → présent (Visites) · R17 → écarté · R25 → CAP-D1-06 · R36 → CAP-D1-12 · R41 → écarté · R42 → CAP-D1-09 (rognage : non retenu, 1 outil) · R44 → CAP-D1-17 · R45 → CAP-D1-05 · R53 → CAP-D1-10 · R54 → CAP-D1-18 · R55 → CAP-D1-16 · R56 → CAP-D1-22 · R58 → D2 · R59 → D6 · R61 → écarté · R2 → CAP-D1-01 · R38 → ACAL412 · R37, R10, R14, R11, R51 → D2 · R24 → D6 · R33 → D3 · R40 → D4 · R18, R63 → D6/écarté · K14-K24, K52, K56, K59 (HORS DÉCISION), K74-K76, K82, K83, K96 → répartis ci-dessus.
- **B7** : U2 → présent (Visites) + ACAL400/423/482 · U12 → CAP-D1-11 · U23 → CAP-D1-21 + ACAL424 · U24 → CAP-D1-05 · U8 → CAP-D1-01 + ACAL412 · U21 → CAP-D1-07 · U27 → CAP-D1-05 + ACAL416 · U28 → D3 · U17 → D3/D6 · grappes #6/#43/#81 → présent (Visites) · #45 → CAP-D1-05 · #51 → CAP-D1-21 · #58 → ACAL458 · #64 → présent · #70 → écarté.

## J. Non vérifié

- Les lecteurs n'ont PAS lu en entier : annexes de B5 allemand (l. 744-873) et B5 français (l. 131+), annexes de B5 anglais
  passe 2 et B5 espagnol (grep par mots-clés seulement), B1 l. 125-257 (balayage), B3 §1 et la table passe 2 (grep). Une
  proposition D1 sans les mots-clés cherchés a pu échapper.
- Aucun écran ouvert, aucune spec ni test lancé : « PRÉSENT SANS ÉCRAN » repose sur des grep d'identifiants DOM (balisage absent
  de `BuilderDom.jsx`, de `toiture-3d-pro-11.astro` et de toute création dynamique trouvée). Les contrôles créés à la volée que
  j'ai vérifiés (`rp9-env-panel`, `rp9-obs-type`, `rp9-obs-gabarit`) sont bien injectés ; pour `rp9-obs-duplicate`,
  `rp9-obs-grid-*`, `rp9-shade-*`, aucune création trouvée.
- Je n'ai pas testé ce que le géocodeur MapTiler fait d'un couple « lat, lng » (aucun appel réseau).
- Les jugements d'adéquation au Maroc (positions WhatsApp partagées, halls en sheds, drones chez les installateurs, extensions
  « très courantes ») sont des INFÉRENCES des lanes ou de moi, non mesurées.
- URL Scanifly Mobile de B6 R55 tronquée dans l'extrait ; non relue.
- Le comportement exact de `toiture-3d-pro-11.astro` (propriétaire non vérifié) n'a pas été lu au-delà du grep.
