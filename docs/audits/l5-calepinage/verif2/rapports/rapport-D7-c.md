# Rapport de vérification — lot D7-c (24 tâches), code lu dans l5-verif

### ACAL967 — OK
`useAtelierBoot.js:446-447` écrit « Calepinage ${titre || calepinageId} chargé. Ajustez… » et « … en lecture seule » (défaut présent). `DiffVersions.jsx:171-178` imprime `ecart.avant/apres` bruts ; `calepinage_versions_diff.json:33,49` porte des `layout_hash` de 64 car. `contexteAtelier.js` et `ToitureDesignCibleAvec.test.mjs` existent.

### ACAL968 — CORRIGER
Files incomplet : la sélection `surfaces_chiffrees` doit être lue et validée (400) dans la vue `views/calepinages.py::generer_devis` (l.792-833, qui ne lit que taux_tva/remise_globale/derogation_electrique) et `sync_devis` (l.845-870, avec son `inline_serializer('CalepinageSyncDevisCorps')` d'OpenAPI l.836-840). Aucun de ces fichiers n'est dans `Files:`. `calepinageApi.js:213-214` passe déjà un corps libre (rien à changer). `choixConception` accepte une clé de plus (`roof_layout_v2.schema.json:2081 additionalProperties: true`).
Correction : ajouter à `Files:` `backend/django_core/apps/calepinage/views/calepinages.py` (lecture du corps, 400 nommant `surfaces_chiffrees`, serializer OpenAPI de sync-devis) ; et dans « Hors périmètre » remplacer « (ACAL915, déjà livrés » par « (ACAL915, construit avant : @after »).

### ACAL969 — OK
`roof-tool-pro11.ts:3485,3500,3531,3548` crée `rp9-priorite`, `rp9-note`, `rp9-setbacks` ; `roofbuilder.css` n'a aucune règle pour ces trois classes ni pour `rp9-input` (grep : 0 ; `rp9-input` = ACAL503, en @after). `.rp9-chip:hover` pose le contour doré (css 244-247), `[aria-pressed]` le fond (248-252). `langageVisuel.test.mjs` existe déjà. (Le badge est déjà à 0.75rem = 12 px, css 289 : la clause « ≥ 12 px » est déjà vraie, sans conséquence.)

### ACAL970 — OK
`PanneauProduction.jsx:269-312` : cellules `py-1 text-right` sans px ; `PanneauBatterie.jsx:171-176` select `bg-black/30`, `:207` `<input type="checkbox">` « Le site est hors réseau » ; `ui/Checkbox.jsx`, `ui/Input.jsx`, `--control-h` (tokens.css) existent ; `onglets.js:72` monte bien `PanneauBatterie`.

### ACAL971 — OK
`ReglagesGabarits.jsx:132,134,138-143` (libellés bruts, `input type="file"`, `acal242-fichier`) ; `PanneauSeries.jsx:369-376` ; `reglementaire.py:903-907` `GENRES_FRANCE` = 3 clés. Tests présents.

### ACAL972 — OK
`roof-tool-pro11.ts:438-461` marqueur MapLibre ; `removeClientPinMarker` appelé seulement à `:2438` (clearEditorState) et dans `planterClientPinMarker` ; `prefill.pinSource.test.ts` existe ; `ToitureDesign.jsx:1261` porte le bouton « Recentrer sur le GPS du lead ». Note : après fermeture le repère ne peut plus être glissé à la main (ACAL193), à dire dans « Hors périmètre » (OPTIONNEL).

### ACAL974 — OK
`electrique.py:132-160` `TemperaturesSite` (5 clés `froid_c, chaud_c, source, mention, detail`), `:330 temperatures_pour_calepinage` ; `evaluerElectrique` ← `VerdictElectrique.jsx` ; champs « Température minimale du site » = `SaisiesElectriques.helpers.js:6`. Aucun chiffre ajouté.

### ACAL975 — OK
`optimizer.ts:949-977` : phrase bifacial pour toute carte à `annualKwh > 0` ; `paintCard` appelé aux l.616, 777 (toit plat) et 1201, 1293 (`family: 'south'` affleurant) ; `CardData` (`types.ts:600-618`) n'a pas `flush` ; constantes 0,05 / 0,03 à `estimatorBrainV2.ts:299-300`. `optimizer.test.ts` existe.

### ACAL978 — OK
`selectors.py:348-386` `comparer_variantes` ne sert que `variantes(calepinage)` ; `VariantesCompare.jsx:202-206` dit « rien à comparer » sous 2 lignes ; contrat et test existent. Point à surveiller par le constructeur (OPTIONNEL) : quand une variante retenue est identique à la conception (D-ACAL-2), la colonne « courante » la double.

### ACAL979 — OK
`views/simulation.py:52-86` `publication_des_pertes` ne sert aucune valeur société ; `remplace_reglage_societe` n'existe que dans le contrat JSON (l.44) et le panneau (`PanneauPertes.jsx:235`), jamais émis par le code ; `chaine_pertes.py:195-209` `POSTE_PAR_ETAPE` ; `parametres_cles.py:98,99,111,112,115,121,179` (`REGISTRES`) ; `pertes.py:56` `CATALOGUE`. Valeurs d'exemple (ASHRAE, 0,05) tirées du réglage, pas inventées.

### ACAL980 — CORRIGER
(1) longueur 16 : OK (`electrique.py:2979-3004`). (2) `core/calepinage/types.py:462 allee_m: float = 0.60` : OK. (3) `profil_conso_depart` : FAUX tel quel — `_profil_de_repli` (`profils_types.py:109`) n'est lu que par `views/consommation.py` ; `resultat_calepinage` (`electrique.py:1746`) ne touche jamais `profils_types` (grep : 0), et `Files:` ne contient aucun fichier de consommation : le constructeur n'a ni condition de déclenchement ni point de lecture. Aussi le champ « Réglages › Allées » n'existe pas : il n'y a pas d'écran `reglages/` d'allées (grep « Allées » dans `reglages/*.jsx` : 0) ; l'allée est propre au calepinage (`traduction.py:534 alleeTechnique`, `PanneauAllees.jsx`) ou section dégagements société (`degagements.py`).
Correction : réduire `suppose[]` à DEUX codes (`longueur_chaine_dossier`, `allee_par_defaut`), supprimer `profil_conso_depart` (le profil de départ sourcé relève d'ACAL404/405) — ou, si le fondateur le veut, le re-créer comme tâche à part avec sa condition (`profil.source == SOURCE_REPLI`) et `services/profils_types.py`/`views/consommation.py` dans `Files:` ; champ de l'allée : « panneau Allées de l'atelier (largeur de l'allée technique) » au lieu de « Réglages › Allées » ; « Given … un lead sans profil saisi » et « tout réglé ⇒ liste vide » en conséquence.

### ACAL981 — CORRIGER
Le défaut visible vit ailleurs que dans l'Emplacement : le tableau « Site — pans de toit et surfaces de pose » est `panStats.ts::htmlTableSite` (`panStats.ts:343` : `l.buildingId ?? 'Bâtiment sans id'` ; total `:350` `t.buildingId ?? 'du site'`), PAS `zones.ts::buildingLabel` (`zones.ts:357`, non exporté, utilisé seulement `:502` et `:534`, le second sous `multiBuilding`). Corriger `buildingLabel` ne change donc pas le tableau cité par le « fini quand ». Le motif `panStats.ts:290` est bien là. Faux aussi : « Assertions existantes : `panStats.test.ts` (motif) et `zones.test.ts` (libellé) » — aucune assertion sur « contour du pan non tracé » ni « sans id » dans ces deux fichiers (grep `*.test.ts` : 0) ; les tests de `computeSiteStats`/`htmlTableSite` sont dans `poseSurfaces.test.ts:688-759`.
Correction : Emplacement = `panStats.ts::htmlTableSite` (l.343, libellé « Bâtiment <rang> » passé par `computeSiteStats`) + `panStats.ts:290` (motif) ; `zones.ts::buildingLabel` seulement pour le cas multi-bâtiments (exporter la fonction pour la tester) ; Assertions existantes = `poseSurfaces.test.ts` (cas `htmlTableSite`) à réaligner, nouveaux cas dans `panStats.test.ts` ; ajouter `poseSurfaces.test.ts` à `Files:` si réaligné.

### ACAL982 — CORRIGER
Le document golden `apps/web/tests/userJourneyPro11.document.json` n'est lu par AUCUN test backend aujourd'hui (grep `backend/.../tests` : 0) ; la convention du dépôt est inverse : le web lit `backend/django_core/apps/calepinage/contract_samples/` (`userJourneyPro11.test.ts:1154`) et les tests backend ne lisent jamais `apps/web` (le conteneur de test backend ne le monte pas forcément). Aussi `test_cal223_contrats.py::InventaireDesEchantillonsTest.test_chaque_echantillon_est_declare_ici` (l.546, glob `*.json` hors `.schema.json`) refuserait un nouveau `.json` dans `contract_samples/` non déclaré. Faux aussi : « `userJourneyPro11.test.ts` : 2 `it` » (il y en a ≈ 22, l.402-1194).
Correction : héberger le document partagé dans `backend/django_core/apps/calepinage/tests/donnees/userJourneyPro11.document.json` (hors `contract_samples`, hors inventaire), faire lire ce chemin par le test web (déjà fait pour `roof_layout_v2.schema.json`) et par `test_acal_verdict_unique.py` ; ajuster `Files:`, « Contrat partagé » et « Appelants » (« ≈ 22 `it` »).

### ACAL983 — CORRIGER
Le nouveau `contract_samples/defauts_annonces.json` casse `test_cal223_contrats.py::InventaireDesEchantillonsTest` : `test_chaque_echantillon_est_complet` exige les clés `endpoint`, `pourquoi`, `exemple` (l.541) et `test_chaque_echantillon_est_declare_ici` (l.546-555) exige qu'il soit listé dans `AVEC_PRODUCTEUR_PUR` ou `SANS_PRODUCTEUR_PUR` ; ce fichier n'est pas dans `Files:`.
Correction : soit ajouter `backend/django_core/apps/calepinage/tests/test_cal223_contrats.py` à `Files:` (déclarer le fichier dans `SANS_PRODUCTEUR_PUR` avec sa raison, lui donner `endpoint`/`pourquoi`/`exemple`), soit loger la liste hors `contract_samples/` (ex. `apps/calepinage/tests/donnees/defauts_annonces.json`, lue par chemin relatif par le test web comme `roof_layout_v2.schema.json`).

### ACAL984 — CORRIGER
`@after` incomplet : la clause (1) exige que la « forme du plan de câblage » ait l'emprise vraie ; c'est ACAL605 (INDEX l.103 : « Dessiner le plan de câblage … avec l'emprise vraie ») qui le fait, absent de `@after: ACAL915, ACAL916, ACAL921, ACAL608, ACAL601, ACAL604, ACAL933` → la garde serait rouge au départ. De plus `emprise_modules.py` (cité par le mutant) n'existe pas dans le code (`coins_du_module` : 0 ; seul `planche.py:641 _dessin_des_modules` existe) : à rattacher à ACAL601.
Correction : `@after: … , ACAL605` ; mutant = « permuter côté court et long dans le module d'emprise créé par ACAL601 (nom à lire à la livraison d'ACAL601) ». Les quatre tests et classes existent (`GeometrieDePlancheTest:44`, `AllerRetourDxfTest:41`, `PlanDeCablageTest:118`, `CompteSurfacesPosePartoutTest:40`).

### ACAL985 — OK
Fichiers et classes existent (`RegleDeCopieTest:55`, `contexteAtelier.js:74,124`, `roof-tool-pro11.ts:2839-2859 flush/cancelPendingVertex`, `:2980` et `:2995`). Deux comptes inexacts, non bloquants (OPTIONNEL) : `contexteToDevisPayload` n'a aucun appelant de production (seulement `ToitureDesignCibleAvec.test.mjs` et le golden) ; `userJourneyPro11.test.ts:1060` joue déjà un « Effacer » (la confirmation), mais pas son effet sur `neededPanels`.

### ACAL986 — OK
Liens `/calepinage/reglages` : `Bibliotheque.jsx:601`, `PanneauMasseLestage.jsx:53`, `PanneauProduction.jsx:217`, `BandeauProvenanceProduction.jsx:113`, `DossiersReglementaires.jsx:508` (vers `/gabarits`) ; `ListeManques.jsx:17` construit déjà `#<champ>`. Information pour l'orchestrateur : le champ norme est DÉJÀ monté (`ReglagesNorme.jsx` : `id="norme"`, monté `ReglagesSimulation.jsx:671`, test ACAL397 `ReglagesSimulation.test.jsx:487`) — ACAL937 (hors de mon lot, `@after` de cette tâche) est probablement déjà construit ou à réduire.

### ACAL987 — OK
`TapisHoraire.jsx:244-250` appelle `exportCsv(id,'horaire')` au montage (useEffect) ; `documents/__init__.py:371 inventaire_des_documents` ; motifs « Aucune conception enregistrée » (`__init__.py:112`, `sorties.py:65-69`) ; spec et test existent.

### ACAL988 — OK
`playwright.config.js:98` projet `mobile-safari` existe ; `calepinage_tactile.spec.js` existe ; `ACAL926/949-952` présents dans l'index.

### ACAL989 — OK
`calepinage-mesures-ecran.spec.js:60,133` (ACAL385/478) et `.baseline.json` existent ; `BuilderDom.jsx:85 #rp9-finish`, `BarreEnregistrement.jsx:15 cal-enregistrer-calepinage` (barre déjà collante : la garde reste valable).

### ACAL990 — CORRIGER
Le mutant « remettre `(CAL197)` dans `Bibliotheque.jsx` ⇒ échec » n'est tué par aucun des deux tests de `Files:` (`test_cal223_contrats.py` lit des phrases serveur, `PanneauProduction.test.jsx` rend la Production) ; le « (CAL197) » existe bien à `Bibliotheque.jsx:608`. Et la phrase « sélectionnez la norme dans les réglages du module » vit dans `norme.py:176-177` (relayée par cables/protections/terre), pas dans ces trois fichiers.
Correction : mutant = « remettre `CAL197` dans une phrase de `norme.py`/`ombrage_chaines.py` ⇒ échec » ; ou ajouter `frontend/src/features/calepinage/Bibliotheque.test.jsx` (si existant) à `Files:` avec un cas « aucun texte rendu ne contient CAL suivi de chiffres » ; « Test rouge » : « la phrase de `norme.py:176` relayée par `cables.py`, `protections.py`, `terre.py` ».

### ACAL1027 — CORRIGER
Contradiction interne : « le bouton … et son aide ne sont pas rendus » (Then) mais le test et le comportement gardent « « ? » ouvre quand même l'aide » ; or l'aide `cal-raccourcis-aide` (`RaccourcisAtelier.jsx:82`) n'est rendue qu'ouverte, et `?` est écouté en capture (`:58-68`).
Correction : « Then le bouton « Raccourcis clavier (?) » n'est pas rendu ; l'aide s'ouvre toujours par la touche « ? » et les raccourcis restent écoutés ». Le reste est confirmé (`RaccourcisAtelier.jsx:72-80` bouton toujours rendu, aucun `matchMedia`, helper `estSaisieEnCours` `helpers.js:37`).

### ACAL1028 — OK
`SchemaUnifilairePanel.jsx:16-43` `Motifs` n'affiche que les listes ; `svg` nul ⇒ pas de boutons d'export (`:169-211`) ; maquette `Schema.dc.html` existe ; aucun chiffre. (`onglets.js` est dans `Files:` sans changement : OPTIONNEL.)

### ACAL1029 — OK
`geometrie.py:445-528` `pans_du_document` : aucune lecture de `flush` (grep `apps/ventes/domain` : 1 commentaire `:170`) ; `thermique.py:189-201 _pose_du_plan` lit `flush` booléen ; `modeles_designes:607` présent ; `test_lire_layout_surfaces_pose.py` et `test_acal_pans_du_document.py` existent. Nombre d'appelants « 7 sites » sous-évalué (≈ 13 hors tests, dont `ventes/services.py`, `selectors.py`, `balayage.py`) : sans conséquence, clé additive.

## OPTIONNEL
- ACAL968 : « dès 2 surfaces » dépasse D-ACAL-37 (toit ET champ au sol) : à confirmer ou restreindre.
- ACAL982 : « en attente de D-ACAL-36 » → D-ACAL-36 est tranchée ; l'attente est ACAL1001 (niveau 15 courant).
- ACAL985 : appelants/`Effacer` voir ci-dessus.
- ACAL972 : dire que le glissement manuel de l'épingle (ACAL193) cesse après fermeture.
- ACAL971 : `GENRES_GABARIT` recopie `GENRES_FRANCE` en JS ; préférer le servir.
