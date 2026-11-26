# Visionneuse « soleil qui bouge » pour les clients de confiance (D-ACAL-132)

Demande du fondateur, 26/11/2026, mot pour mot : « i can see now the old calpinage viewer not the new one with
the play button for the sun moving ! i like this one and clients de confiance should get it ». Le même jour,
sur la carte satellite : « just go ahead and show it, i want to go sleep » (D-ACAL-133).

Lu sur `origin/dev-lot6` (fa81c4200, page client relue à 1b645aca7 après le pli de `lot6/schema-w`) le 26/11/2026, sans pile, sans navigateur. Rien n'est construit par ce
document : il pose la carte, le plan et le contrat partagé (`visionneuse_soleil.json`, posé SEUL, PACT10).

## 1. La carte (ce qui existe aujourd'hui)

### 1.a Les visionneuses

**Page client** (`apps/web/src/pages/proposition/[...token].astro`, section `#roof3d` l. 3241-3348, script l. 8941-9159).
Une seule section, rendue quand `show3d` (l. 1793 : `buildViewerModel(parseRoofLayout(data.roof_layout))` non nul),
QUEL QUE SOIT le marché. Au scroll (IntersectionObserver) ou au tap, `boot()` (l. 9042) choisit :

1. **Visionneuse pleine** — `scripts/roofPro11/viewerFullBoot.ts::bootViewerFull` (l. 124). C'est le VRAI rendu de
   l'ERP (`roofPro11/scene3d.ts::createScene3d`, `readOnly: true`) posé sur une carte MapLibre satellite
   (`lib/roofConfig.ts::buildSatelliteStyle` : tuiles Mapbox `mapbox.satellite` « © Mapbox © Maxar » avec le token,
   sinon style hybride MapTiler). Conditions : `roof_layout` porte un calepinage réel (`zones[].geometry.panels`,
   `viewerFullModel.ts::buildViewerFullPlan` l. 277), `/api/roof-config` rend une clé, WebGL présent.
   **Le soleil y est FIGÉ** : `sunHour: 12`, `sunDay: 355` (l. 51-52, « Aucun réglage n'est offert au client »),
   aucun curseur, aucune lecture, aucune teinte par panneau, aucun objet voisin (`shadeObstructions: []`, pas
   d'`environment`). Carte NON bornée (pas de `maxBounds`/`minZoom` — épinglé par
   `apps/web/tests/propositionViewerFull.test.ts` « aucune borne de navigation », l. 298).
2. **Visionneuse simplifiée** — `scripts/roofPro11/viewerOnly.ts::createRoofViewer` (l. 649), Three.js seul sur le
   modèle abstrait `lib/proposition.ts::buildViewerModel`, avec UNE image satellite statique drapée
   (`viewerOnly.ts::buildPublicRoofImageSpec` l. 278 → `mapboxStaticRoofImageUrl` ou `maptilerStaticRoofImageUrl`,
   cadrée sur le contour du toit). Repli quand l'une des conditions de 1 manque.
3. **Poster** — `roof_image_url` (photo d'étude) sous le canvas ; reste seul si l'import ou WebGL échoue
   (`showFallback`, l. 9037).

`calepinageOptions` (`lib/proposition.ts`, servi par `public_views.py::_calepinage_options_publique` l. 867) ne
change PAS de moteur : il échange seulement le `roof_layout` rejoué quand le client choisit une autre TAILLE
(Éco/Max), résidentiel seulement (`est_residentiel`), via l'événement `taqinor:calepinage-option`.
`roofPro11/` est le dossier du constructeur de toiture partagé : la page client n'en charge que `viewerOnly`,
`viewerFullBoot`/`viewerFullModel`/`scene3d` (import dynamique). Poids : Three.js 0.187 + MapLibre 6.12
(`apps/web/package.json` l. 25-27), chargés hors du premier rendu (garde `apps/web/tests/mobilePerfWJ18.test.ts`) ;
poids en Ko NON mesuré (pas de `node_modules` sur ce poste).

**ERP** — l'écran « Panneaux » du calepinage (`frontend/src/features/calepinage/atelier/coque/etapes/EtapePanneaux.jsx`,
`LegendeSoleil` l. 458, `LecteurSoleil` l. 477) n'a AUCUN moteur à lui : il pilote le constructeur
`apps/web/src/scripts/roof-tool-pro11.ts` (alias `@roofpro`) par ses contrôles (`#rp9-sun-hour`,
`[data-sun-season]`, `#rp9-sun-play-day`, `#rp9-heatmap-toggle`).
- Le soleil : `roof-tool-pro11.ts` l. 3762-3944 écrit `ctx.sunDay/ctx.sunHour` puis re-rend ; la lecture de la
  journée est `roofPro11/soleilPlay.ts::createSoleilPlayer` + `sunriseSunsetHours` (un pas toutes les 700 ms,
  pas-à-pas en `reducedMotion`) ; la position est `lib/roofPro2.ts::sunDirection`, lue par
  `scene3d.ts` l. 2600 (ombres Three.js réelles). Hiver = jour 355, Été = jour 172 (année de dessin 2028
  bissextile : « 20 décembre », « 20 juin » — `formats.js::jourMois`).
- La teinte « Ensoleillement de chaque panneau » : `roofPro11/shadingUi.ts::buildHeatmapColorFn` (l. 1071) →
  `heatmapAccessValues` (l. 308) → `lib/shadingEngine.ts::pointSolarAccess` : accès solaire ANNUEL de chaque
  module, calculé DANS LE NAVIGATEUR depuis les ombres tracées, les obstacles à hauteur saisie et les objets
  voisins, pondéré par le profil PVGIS (`ctx.prodPerKwc`). Il ne bouge PAS avec l'heure (seules les ombres
  bougent). Aucune source d'ombre → tout à 1. Couleurs : `shadingEngine.ts::couleurAccesActive`, palette
  « atelier » (bleu nuit → or, posée par `useAtelierBoot.js` l. 433). Appliquée par
  `scene3d.setSolarAccessHeatmap` (pan ACTIF seulement).
- **Ce calcul est PERSISTÉ** à l'enregistrement : `zones[].geometry.solarAccess = {values, method, assumptions,
  computedAt}` (`prefill.ts::serializeSolarAccess` l. 302, CAL248 ; `values` dans l'ordre de `panels`, `null` =
  non calculé, écrit seulement quand une source d'ombre existe — `calepinage_documents.json` « manque »).
  Le backend le lit déjà : `apps/calepinage/services/ombrage_chaines.py::acces_par_module` (l. 101), l'étape de
  pertes `services/etapes/acces_module.py`.
- « Montrer au client » = route ERP authentifiée `/calepinage/:id/client`
  (`frontend/src/features/calepinage/client/VueClient.jsx`, `HabillageClient.jsx`) : l'atelier lui-même en mode
  présentation, soleil ouvert en été à midi sauf instant choisi par le commercial
  (`vueClient.helpers.js::instantSoleilChoisi`, `roof_layout.scene{sunDay,sunHour}`). Aucun partage public : son
  pied renvoie au lien de la proposition (« Envoyer au client » de la fiche lead).

### 1.b Pourquoi CE client voit l'ancienne visionneuse

Il n'y a pas de porte qui l'exclut : **la visionneuse au soleil n'existe sur la page client pour AUCUN devis,
aucun niveau, aucun marché**. La page n'a ni curseur, ni lecture, ni teinte (grep `sunHour|soleilPlay|heatmap|
solarAccess` sur `[...token].astro` : 0 ligne), `viewerFullBoot` fige le soleil, et le backend ne sert ni l'accès
par module ni l'instant de scène : `public_views.py::_safe_zone_geometry` (l. 488) recopie la géométrie champ par
champ sans `solarAccess`, `_safe_roof_layout` (l. 559) ne garde ni `scene`, ni `environment`, ni `shading12x24`,
ni `shadeObstructions`. Le niveau du lien n'y change rien (`roof3d` est servi aux deux niveaux depuis L-SECT,
l. 1361) ; `calepinageOptions` vaut `None` pour un industriel mais il ne choisit pas de moteur. Ce que ce client
a vu exactement (pleine ou simplifiée) dépend de la clé carte du Worker et de la `geometry` de son devis : NON
vérifié (pas de navigateur, pas de lecture de la prod).

### 1.c Niveaux de partage

`apps/ventes/models.py::ShareLink` l. 1204-1255 : `niveau` (`standard` par défaut, `confiance`), `sections`
(JSON à trois états, liste blanche `SECTIONS_CLES` : roof3d, sld, pdf, bankable, economies, jour_type, gammes,
taille_eco, taille_max). Lecture : `apps/ventes/public/noyau.py::_niveau_lien` (l. 260), `_section_servie`
(l. 268). « Confiance » donne aujourd'hui : schéma unifilaire et conception électrique complets (calibres,
sections — `_conception_electrique_publique`, `_safe_sld_svg(standard=…)`), kit détaillé, pas de filigrane PDF ;
tous les chiffres sont identiques aux deux niveaux. Une section se pose en ajoutant sa clé à `SECTIONS_CLES`
(aucune migration) puis en testant `_section_servie(link, '<clé>')` dans la vue ; la dégradation par niveau est
décidée DANS la vue (`est_standard`), la page n'a rien à deviner (`payload['niveau']`).

### 1.d Vie privée, coût, sécurité

- **Imagerie** : la page client affiche DÉJÀ le satellite du toit du client à tout visiteur du lien, aux deux
  niveaux (visionneuse pleine : tuiles Mapbox ; simplifiée : une image statique). Zoom initial =
  `viewerFullModel.ts::zoomForSpanM` (cadre l'emprise du toit), dézoom libre jusqu'à la ville.
- **Token** : `/api/roof-config` (`apps/web/src/pages/api/roof-config.ts`) rend `PUBLIC_MAPTILER_KEY` et
  `PUBLIC_MAPBOX_TOKEN` du Worker à tout navigateur (`no-store`) ; son en-tête dit ces clés « restreintes par
  domaine (taqinor.ma) côté fournisseur » — NON vérifié (compte Mapbox hors dépôt). L'ERP lit les MÊMES noms de
  variables (`apps/ventes/views/roof_config.py` → `selectors.config_carte`, réservé aux connectés) ; que la
  valeur soit la même des deux côtés : non vérifié. Rien de NOUVEAU n'est exposé par ce plan : même fournisseur,
  même token, même compte.
- **Coût** : chaque ouverture de la visionneuse pleine charge des tuiles raster Mapbox + UNE image statique
  (la photo drapée par `scene3d.ts` l. 1699). Plan et quota du compte : non lisibles dans le dépôt. Ordre de
  grandeur estimé (non mesuré) : quelques dizaines à une centaine de tuiles par ouverture, mises en cache par le
  navigateur.
- **Données internes** : aucun prix, `prix_achat`, consommation ni facture dans ce qui est ajouté ; les valeurs
  d'accès sont des facteurs 0-1 rendus en COULEUR seulement (aucun chiffre neuf à l'écran). Les objets voisins
  sont une géométrie sans libellé (un libellé libre peut nommer un voisin).

### 1.e Gardes qui épinglent l'existant

`apps/web/tests/propositionViewerFull.test.ts` (lecture seule stricte : aucun module d'édition importé par
`viewerFullBoot`, seuls écouteurs `load`/`error`, aucune borne de navigation), `propositionViewerWJ25/WJ27`,
`roofImagePublic.test.ts`, `roofImageWJ118.test.ts`, `mobilePerfWJ18.test.ts` (aucun import statique de Three /
MapLibre / `roofPro11` dans la page), `roofPro11/soleilPlay.test.ts`, `layoutManualEditPV29`,
`propositionPanneauxFidelesWJ130` ; `apps/web/astro-check-frozen-errors.json` (plafond par fichier et code ts,
`[...token].astro` y est : pas de « » dans un attribut JSX neuf) ; contrats
`apps/web/src/contract_samples/proposal_data.json` (`forme_serveur: complete`) et son jumeau backend,
`scripts/check_api_shapes.py::echantillons_de_contrat` + `echantillons_web_jumeaux` ; backend
`apps/ventes/tests/test_qj26_roof_layout_proposal.py`, `test_acal_liste_blanche_3d_publique.py`,
`test_roof_layout_v2.py`, `test_calepinage_options.py`. Aucune spec e2e de la page client (pas de `apps/web/e2e`).

## 2. La conception retenue (la plus petite qui tient)

**Une seule source pour la couleur** : l'accès par module ENREGISTRÉ par le calepinage
(`geometry.solarAccess.values`), le calcul de l'ERP, servi tel quel — jamais un second moteur d'ombrage sur la
page. **Un seul soleil** : `lib/roofPro2.ts::sunDirection` via `scene3d.ts` et `soleilPlay.ts`, les modules mêmes
de l'ERP. **Une seule scène** : la visionneuse pleine existante, enrichie, jamais une copie.

1. **Serveur** — clé ADDITIVE `visionneuse_soleil` de la charge publique (contrat
   `apps/ventes/contract_samples/visionneuse_soleil.json`, posé dans ce commit). ABSENTE (jamais `null`) sauf
   quand : niveau `confiance` ET `roof_layout` servi (case roof3d cochée, pas de brouillon « conception rapide »).
   Contenu : `zones` (accès par module des pans qui en portent un, aligné sur les `panels` PUBLIÉS),
   `environnement` (objets voisins à hauteur saisie, géométrie seule), `instant_choisi` (scène choisie par le
   commercial, sinon `null`). La porte est décidée par le serveur ; la page ne lit jamais `niveau` pour cela.
2. **Page** — quand la clé est présente ET que la visionneuse pleine a démarré, un module chargé à la demande
   (`viewerSoleil.ts`) pose sous la scène la barre de l'ERP : légende « Ensoleillement de chaque panneau »
   (Ombragé → Plein soleil), bouton lecture de la journée, curseur d'heure (lever → coucher), Hiver / Été ;
   teinte les panneaux depuis `zones[].acces` (palette « atelier », comme l'écran que le fondateur a vu) ;
   dessine les objets voisins ; BORNE la carte au toit (D-ACAL-138). Tout le reste inchangé : autre niveau,
   ancienne charge (backend pas encore déployé), carte indisponible ou WebGL absent → exactement la page
   d'aujourd'hui. La clé absente → aucune barre (zéro CLS : la barre est rendue côté serveur seulement quand la
   clé est là, hauteur réservée, contrôles inertes jusqu'au démarrage).
3. **Ordre de déploiement indifférent** : le site part au merge (Cloudflare), le backend au déploiement de Reda.
   Site neuf + backend ancien → pas de clé → page d'aujourd'hui. Backend neuf + site ancien → clé ignorée.
4. Un devis envoyé garde son PDF ; seule la page (vue vivante) change.

Ce qui n'est PAS fait : aucune teinte inventée (un pan sans `solarAccess` n'est pas teinté et la légende est
masquée), aucune teinte des pans secondaires (`setSolarAccessHeatmap` ne teinte que le pan actif), aucun chiffre
d'accès affiché, aucun changement de l'ERP, de `scene3d.ts`, du PDF.

## 3. Les lanes (fichiers disjoints)

### Lane B — charge publique (backend) · `@model:opus` (surface publique, liste blanche)

Fichiers :
- NOUVEAU `backend/django_core/apps/ventes/public/visionneuse_soleil.py` (≈ 120 lignes) :
  `visionneuse_soleil_publique(devis, layout_public, niveau) -> dict | None`. Relit `devis.roof_layout` brut ;
  pour chaque zone publiée, réaligne `solarAccess.values` sur les panneaux GARDÉS par `_safe_zone_geometry`
  (même filtre cx/cy numériques, même plafond `_MAX_PANNEAUX_PUBLIES` — import fonction-local depuis
  `public_views`), valeurs bornées [0 ; 1] arrondies à 3 décimales, `null` conservé ; une zone dont le nombre de
  valeurs ≠ nombre de panneaux bruts est OMISE (jamais réalignée au hasard). `environnement` : liste blanche
  `kind, centerLng, centerLat, heightM (> 0), crownDiameterM, evergreen, footprint, lengthM, widthM, diameterM,
  trace, epaisseurM` ; exclus : `id`, `label`, `supposeCoupe: true` (objet écarté), `hauteurFutureM`, `dansAns`.
  `instant_choisi` : `roof_layout.scene{sunDay, sunHour}` seulement s'il diffère de (355, 12) (règle de
  `instantSoleilChoisi`). Best-effort, ne lève jamais.
- `backend/django_core/apps/calepinage/selectors.py` : + sélecteur mince `acces_solaire_par_module(layout)` qui
  délègue à `services/ombrage_chaines.py::acces_par_module` (≤ 8 lignes nettes) — lecture via le sélecteur,
  règle de frontière. **Attend le pli de `origin/lot6/schema-b`** (même fichier, +18).
- `backend/django_core/apps/ventes/public_views.py` : ≤ 6 lignes nettes après le bloc `_calepinage_options`
  (l. 1804) : `if niveau == ShareLink.NIVEAU_CONFIANCE and _roof_layout_public: … payload['visionneuse_soleil']`.
  **Attend le pli de la lane backend en cours** (même fichier, budget +12 de son côté ; fichier > 2 000 lignes).
- `backend/django_core/apps/ventes/contract_samples/proposal_data.json` + jumeau
  `apps/web/src/contract_samples/proposal_data.json` : nommer `visionneuse_soleil` dans `cles_additives…` et
  `cles_avec_contrat_dedie` (les deux copies identiques). **Attend la même lane en cours** (elle édite ces deux
  fichiers).
- Tests dans les modules EXISTANTS : `apps/ventes/tests/test_qj26_roof_layout_proposal.py` (servie en confiance ;
  absente en standard, case roof3d décochée, sans layout ; alignement après filtre ; zone omise si longueurs
  différentes ; `instant_choisi` nul au défaut) et `test_acal_liste_blanche_3d_publique.py` (aucun `label`,
  `prix`, `prix_achat`, `produitId` dans la clé).
- Gardes : flake8, compileall, `lint-imports` (ventes → `apps.calepinage.selectors`, fonction-local),
  `scripts/check_api_shapes.py` (jumeaux + exemple), `codemap_fingerprint.py --check`.
- Taille : 2 à 3 h.

### Lane W — page client (site public) · `@model:opus` (scène 3D partagée avec l'ERP)

Fichiers :
- `apps/web/src/scripts/roofPro11/viewerFullBoot.ts` (290 lignes, ≈ +45) : poignée enrichie, ADDITIVE —
  `carte` (la `maplibregl.Map`), `poserInstant(jour, heure)` (écrit `ctx.sunDay/sunHour`, rejoue
  `scene3d.renderScene` avec les mêmes arguments, repose la teinte), `teinter(colorFor | null)`
  (`scene3d.setSolarAccessHeatmap`, reposée après chaque rendu) ; option `environnement` → `ctx.environment`.
  INTERDIT ici : `maxBounds:`, `minZoom:`, `.setMaxBounds(` et tout `map.on(` autre que `load`/`error`
  (le test les épingle).
- NOUVEAU `apps/web/src/lib/visionneuseSoleil.ts` (pur, ≈ 150 lignes) : lecture/validation de la clé (forme du
  contrat, longueurs contre `parseRoofLayout`), libellé du jour FR/EN/AR selon la convention 2028 de l'ERP
  (355 → « 20 décembre »), bornes de carte (emprise des sommets + 150 m, zoom mini = zoom initial − 2).
- NOUVEAU `apps/web/src/scripts/roofPro11/viewerSoleil.ts` (chargé par `import()`, ≈ 180 lignes) : relie la
  barre à la poignée — `createSoleilPlayer` (700 ms, pas-à-pas en reduced-motion), `sunriseSunsetHours` pour les
  bornes du curseur, Hiver 355 / Été 172, teinte `couleurAccesActive(a, 'atelier')` (zone d'index
  `plan.activeIndex` seulement), `carte.setMaxBounds/setMinZoom/setMaxPitch(60)`.
- NOUVEAU `apps/web/src/components/proposition/BarreSoleil.astro` (≈ 120 lignes) : balisage de la barre, 3
  langues (`data-fr/en/ar`, arabe à faire relire), cibles tactiles ≥ 44 px, sous la scène au téléphone.
- `apps/web/src/pages/proposition/[...token].astro` : ≤ 25 lignes nettes — lire la clé, la passer dans
  `viewerConfig`, rendre `<BarreSoleil>` sous `#roof3d-stage` quand elle est là, et dans `boot()` après
  `fullHandle` prêt : `import('../../scripts/roofPro11/viewerSoleil')`. `origin/lot6/schema-w` (même fichier,
  section `#sld`) est DÉJÀ plié dans `dev-lot6` (merge 1b645aca7) : aucune attente ; revérifier au départ
  qu'aucune autre lane n'a ce fichier en cours. Garder vert `apps/web/tests/propositionSldWJ128.test.ts` (garde
  de placement posée par schema-w).
- Tests : NOUVEAU `apps/web/src/lib/visionneuseSoleil.test.ts` (Nouveau fichier car : module neuf) ; étendre
  `apps/web/tests/propositionViewerFull.test.ts` (poignée additive, toujours aucune borne dans `viewerFullBoot`,
  aucun module d'édition) et `apps/web/tests/mobilePerfWJ18.test.ts` (`viewerSoleil` jamais importé
  statiquement).
- Gardes : vitest, `npm run check` (plafond astro gelé), eslint, `astro build`, `check:locale-parity`,
  `scripts/check_api_shapes.py`.
- Taille : 5 à 7 h.

### Lane E — ERP : aucune

Rien à changer : la valeur vient de l'enregistrement du calepinage qui existe déjà. Option plus tard : dire dans
le dialogue d'envoi ce que « Confiance » ajoute.

### Acceptation (orchestrateur, pile locale, navigateur réel)

Même devis ouvert dans l'ERP et sur sa page en confiance : mêmes panneaux teintés de la même couleur, même
soleil à la même heure ; téléphone 390 × 844 et bureau, WebKit compris ; lecture, curseur, Hiver/Été ;
reduced-motion = pas-à-pas ; carte bornée ; lien standard = page d'aujourd'hui ; charge sans la clé = page
d'aujourd'hui ; aucune erreur console ; nombre de tuiles chargées par ouverture (onglet réseau). Rien de cela
n'est vérifiable par les lanes (pas de navigateur) ni par ce document.

Taille totale : ≈ 8 à 10 h de lanes + 1 à 2 h d'acceptation.

## 4. Décisions

- D-ACAL-132 (fondateur) : les clients de confiance ont la visionneuse au soleil qui bouge.
- D-ACAL-133 (fondateur, en session) : la carte satellite est montrée sur la page de confiance.
- D-ACAL-134 à 138 : prises par l'orchestrateur, à confirmer (niveau standard inchangé ; instant d'ouverture et
  Hiver/Été ; teinte = accès enregistré, palette atelier, rien quand non mesuré ; objets voisins dessinés ;
  carte bornée au toit). Détail dans `docs/audits/decisions.yml`.
