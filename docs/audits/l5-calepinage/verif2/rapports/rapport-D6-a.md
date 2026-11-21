# Rapport de vérification — lot D6-a (ACAL851 à ACAL874, 24 tâches)
Code lu : `C:\dev\taqinor-os\.claude\worktrees\l5-verif\` (lecture seule). Toutes les preuves `fichier:ligne` viennent de ce dossier.

### ACAL851 — CORRIGER
Prémisse OK : `optimizer.ts:962` et `zones.ts:445` écrivent « × 720 W » en dur ; `moduleDuPan` existe (`zones.ts:833`) ; `PANEL2_WATT = 720` (`apps/web/src/lib/roofPro2.ts:25`).
Faux/incohérent : (1) la clause « Given » exige `#rp9-reco-kwc` = « 5,68 kWc » (8 × 710) alors que « Hors périmètre » exclut le calcul du kWc du solveur : or le kWc de la carte vient du solveur (`optimizer.ts:604` `o.grid.kwc * placed / count`, `:761` `w.kwc * gapScale`), basé sur 720 W, donc la carte dirait « 5,76 kWc » à côté de « 8 × 710 W » (les deux écrans se contrediraient autrement). Le kWc par pan à partir du module existe déjà ailleurs (`panStats.ts:94` `kwcDuPan(panels, modulePan)`). (2) `moduleDuPan` est une fermeture interne de `zones.ts` ; `paintCard` (`optimizer.ts:949`) n'y a pas accès (elle n'a que `ctx.activeArea()?.moduleId`, cf. `optimizer.ts:406`).
Correction : remplacer « Hors périmètre : le calcul du kWc du solveur » par « le solveur reste en 720 W ; les deux cartes affichent `kwcDuPan(panneaux, module du pan)` (même règle que `panStats.ts:94`) quand un module est choisi, sinon le kWc du solveur » ; ajouter `apps/web/src/scripts/roofPro11/panStats.ts` (lecture) et dire comment `paintCard` reçoit la puissance du module (champ ajouté à `CardData`, rempli par les 4 appelants). Le « constructeur trace d'abord pourquoi 131,04 ≠ 129,22 » est résolu : 182 × 0,72 = 131,04 (solveur) contre 182 × 0,71 = 129,22 (fiche).
(Le document sérialisé garde `result.kwc` en 720 W : voir ACAL862.)

### ACAL852 — CORRIGER
Prémisse OK pour `rp9-reco-savings` (`optimizer.ts:965`, sans garde ; `rp9-reco-cover` gardée en `:964`).
Faux : la phrase « Meilleure combinaison pour votre facture : … ≈ N % de la facture » n'est PAS écrite dans `rp9-maxline` : `paintMaxLine` (`optimizer.ts:1120-1122`) écrit « Rendement max par panneau : ~N° plein sud… ». La phrase « ≈ N % de la facture » est dans `d.why` (`optimizer.ts:775-776`, et `:1291-1292` pour le toit incliné), affichée par `rp9-reco-why` (`optimizer.ts:966-967`).
Correction : Given/Emplacement : remplacer « la phrase `rp9-maxline` dit … » par « la phrase `rp9-reco-why` (construite en `optimizer.ts` ≈ l. 775 et ≈ l. 1291) dit « Facture inconnue — saisissez-la pour voir la couverture » quand la cible est 0 » ; et préciser que la fourchette Année 1 / Année 25 est le bloc `rp9-reco-band` (`:979-1000`).

### ACAL853 — CORRIGER
Constat réel confirmé (deux cartes, deux nombres) mais la cause affirmée est fausse : les deux chemins appliquent déjà le MÊME dérate `facteurDerateAnnuel` (`optimizer.ts:612` et `:760`, `zones.ts:388`). L'écart vient de la BASE : la carte (`renderConfig`, `optimizer.ts:611-612`) utilise PVGIS par kWc (`ctx.pvgisPerKwc * kwc`) ou la table `productionKwh`, et `:760` applique en plus `clipDcAcKwh` et `gapScale`, alors que `liveActiveResult` (`zones.ts:380-392`) prend `w.annualKwh` du solveur × dérate, sans PVGIS, sans écrêtage, sans `gapScale`. Corriger « le dérate d'un seul côté » ne réglera rien (le mutant du test ne prouve pas la bonne cause).
Correction : remplacer la phrase de cause par ci-dessus ; remplacer « corrigée à la source commune » par « `liveActiveResult` lit le kWh DÉJÀ peint sur la carte (`derniereCarte`, `optimizer.ts:526/950`, exposé par `etatCarte` `:1585`) au lieu de `w.annualKwh` » ; mutant : « lire `w.annualKwh` ⇒ les deux nombres divergent ». Mentionner que la carte du toit incliné (`:1198`) et celle du plat (`:611`, `:760`) ont deux formules : la valeur lue doit être celle de la carte, pas recalculée.

### ACAL854 — CORRIGER
Prémisse OK : `validation` servie (contrat `calepinage_resultat.json`, `exemple.validation.ecart_pct` −1,96, `tolerance_pct` 5, `verdict` dans_la_tolerance) ; aucune lecture front (grep) ; onglet `production` déclaré.
Faux : « le monte juste après `TotalKpis` » : `TotalKpis` n'existe plus, c'est `ResultatHeros` (`PanneauProduction.jsx:366`).
Correction : « le monte juste après `<ResultatHeros …/>` (PanneauProduction.jsx l. 366) ».

### ACAL855 — OK
Ouvert : `validation.py` (`verdict`, `tolerance_pct`, `avertissement`), `PanneauProduction.jsx:359` (la liste d'avertissements est vidée pour un résultat simulé : le badge est bien la seule mention), onglet `pertes` (`onglets.js:58`), `ReglagesSimulation.jsx` existe. Dépend d'ACAL854 (déclaré).

### ACAL856 — CORRIGER
OK : `test_cal223_contrats.py` (`POSES_AVANT_LEUR_ROUTE` l. 439, `InventaireDesEchantillonsTest` l. 535, `CheminDeclareTest` l. 696), `check_calepinage_routes_sous_contrat.py` existent.
Faux : (1) les 24 codes ne sont pas tous produits par une tâche : `un_seul_chiffre` et `schema_secours` n'ont AUCUNE tâche productrice dans l'index (ACAL982 est une garde CI, pas un contrôle) ; `pentes_confirmees` est « planifié » mais ACAL417 et ACAL426 sont déjà cochées (`PLAN_AUDIT_CALEPINAGE.md` l. 750, 768) ; `compatibilite_equipements` dépend d'ACAL906 (M2, non construit). Or ACAL860 impose « codes produits == codes du pourquoi » : test impossible à faire passer. (2) « AUCUN recouvrement » avec `calepinage_parcours_guide.json` est inexact : `services/parcours_guide.py` (`regrouper_manque`, l. 52-70) classe déjà les avertissements en lignes `{code, etape, onglet, champ, gravite}`, et `EtapeElectrique.jsx` affiche déjà « n points à régler » ; deux comptes différents sur le même écran (865).
Correction : dans `pourquoi`, séparer deux listes : `codes_produits` (ceux que ACAL857-864/906 produisent : 22) et `codes_reserves` (`un_seul_chiffre`, `schema_secours`, hors périmètre, JAMAIS dans `controles[]`) ; `pentes_confirmees` = produit par ACAL426 (déjà cochée) à brancher en lecture dans ACAL860 ; remplacer « Jumeaux : AUCUN recouvrement » par « recouvrement partiel avec `manque[]` du parcours : le panneau (ACAL865) lit `pret-a-envoyer`, jamais `manque[]` en plus ».

### ACAL857 — CORRIGER
Ouvert : `feu_vert.verifier_avant_publication` (l. 105-150), `MESSAGES_FEU_VERT['devis']`, `MESSAGES_APPROBATION`, `comparaison.simulation_perimee_du_calepinage` (l. 96), `serializers.peremption_du_calepinage(devis, calepinage)` (l. 168), `ventes/selectors_calepinage.refus_kwh_declare_du_devis` (l. 294) : tous existent, tests nommés existent.
Faux : la porte LÈVE à la PREMIÈRE erreur (feu vert `l.137-140`, puis approbation `l.152-156`) : si le feu vert manque, l'approbation n'est jamais évaluée ; capter la `ValidationError` ne donne donc qu'une des deux lignes, et « approbation_a_jour » serait à tort `ok`. Autres cas : porte sans lead (`_lead_id_de_reference` nul) = no-op : ce n'est pas « non exigé par votre société ». `peremption_du_calepinage` exige un `devis` (comment obtient-on le devis lié ? non dit).
Correction : « la fonction appelle la porte avec le geste `devis` ; si elle lève `feu_vert`, la ligne `approbation_a_jour` vaut `info` « non évaluée tant que la visite n'est pas validée » (jamais `ok`) ; sans lead ni devis ⇒ `info` « sans lead : non applicable » ; le devis lié se lit par le sélecteur existant (à nommer : `selectors_calepinage`/`du_devis`) ».

### ACAL858 — CORRIGER
Ouvert : `electrique.py::verdict_publiable` (l. 2788), `_rapport_publication` (l. 2793), `CODE_FICHE_INCOMPLETE` (l. 2725), `_bloc_ratio_dc_ac` (l. 4004), `evaluation_electrique` (l. 2269) : existent ; tests nommés existent.
Faux/incohérent : le titre dit lire « l'état à trois valeurs servi par ACAL934 », mais la clause Given re-dérive elle-même les états depuis les motifs (« `bloquant` si un motif est `bloquant` ou `sans_source`, `a_regler` si seulement `non_verifiable`… ») : c'est la seconde règle qu'ACAL934 supprime (« calculé UNE fois »).
Correction : Given : « `verdict_electrique` = l'état à trois valeurs d'ACAL934 (prêt → ok, à compléter → a_regler, bloquant → bloquant) ; `materiel_designe`, `tension_froid`, `orientation_mppt`, `ratio_dc_ac`, `chutes_tension`, `terre_protections` = lignes lues telles que servies » — supprimer la règle de rangement des motifs.

### ACAL859 — OK
Ouvert : `validation.ecart_vs_pvcalc`, étape `ombrage_proche` et `motif_omission` dans `contract_samples/calepinage_pertes_cascade.json` / `resultat.ombrage.par_pan[].cascade`, `reglementaire.dossiers_du_calepinage` (l. 391), `consommation.py:1143` (`hypotheses` fusionnées dans `avertissements`). Remarque (optionnel) : `hypotheses_conso` n'est pas une clé servie séparément (fusionnée dans `avertissements`) ; la tâche le prévoit (« info » si pas de liste).

### ACAL860 — CORRIGER
Ouvert : `views/parcours_guide.py` (patron de greffe), `views/rattachements.py` (liste `MODULES_RATTACHES` : l'ajout est une ENTRÉE de tuple, pas une « ligne d'import »), `simulation.js` (`parcours: (id)` l. 55), `calepinageApi.golden.*` existent.
Faux : « la liste des codes produits est exactement celle du `pourquoi` » est irréalisable (voir ACAL856 : `un_seul_chiffre`, `schema_secours`, et `compatibilite_equipements` tant qu'ACAL906 n'est pas faite). Même problème dans « Listes figées : le test d'ACAL860 compare les deux » d'ACAL857.
Correction : « les codes produits == `codes_produits` du `pourquoi` ; `codes_reserves` jamais produits » ; remplacer « une ligne d'import en fin » par « une entrée en fin de `MODULES_RATTACHES` ».

### ACAL861 — CORRIGER
Faux : la prémisse « aucune consommation connue = `consumption.courbe24` absente » est fausse. `serializeConsumption` (`apps/web/src/scripts/roofPro11/prefill.ts:734-745`) n'écrit le bloc `consumption` QUE si l'utilisateur a touché la consommation (`touche`) : un lead AVEC facture et sans retouche n'a pas de `consumption` mais porte `billKwh` (`roof_layout_v2.schema.json` l. 49-50). Le contrôle donnerait un faux orange « aucune facture » sur la plupart des leads. D'autre part ACAL922 définit déjà le prédicat « rien ne dimensionne » par `ventes/selectors.py::cible_depuis_lead` (`panneaux` null) : deuxième règle.
Correction : « `controle_taille_sans_facture` utilise le MÊME prédicat qu'ACAL922 (`cible_depuis_lead` du lead lié, ou sans lead : `billKwh` absent ET `consumption.courbe24` absente) ; jamais `courbe24` seule ». Supprimer `profil_depuis_layout` des ancres. Ajouter `@after ACAL922` (déjà) et dire que le contrôle avertit, la confirmation (409) vit dans ACAL922.

### ACAL862 — CORRIGER
Ouvert : `mesures.py::mesures_du_document` (l. 76-160) : confirme que le kWc vient des fiches par pan (`module_wc`), et que `result.kwc` n'est lu qu'en repli (l. 119-124) : le contrôle doit donc lire `layout['result']['kwc']` lui-même, ce que la tâche prévoit.
Faux/incohérent : le document sérialise `result.kwc` issu du solveur en 720 W (ACAL851 laisse ce calcul hors périmètre) ; avec tout module ≠ 720 W le contrôle sortirait orange en permanence, sans que « Reposer les panneaux » puisse le corriger.
Correction : ajouter « Dépend de ACAL851 : le kWc sérialisé dans `result.kwc` est celui de `kwcDuPan(…)` quand un module est choisi » (ou `@after: ACAL851`), sinon le contrôle est irréparable. L'epsilon 0,01 kWc est de l'arithmétique d'arrondi, acceptable.

### ACAL863 — CORRIGER
Ouvert : `core/calepinage/geometrie.py` (fonctions : `point_dans_polygone` l. 141, `est_polygone_simple` l. 186 ; AUCUNE fonction de distance ni de projection), schéma `$defs/obstacle` (`id, centerLng, centerLat, lengthM, widthM, type, heightM, provenance, forme, contour, rayonM`).
Faux : (1) « un sommet hors du contour » : un obstacle par défaut est un rectangle centré (`centerLng/centerLat/lengthM/widthM`), un disque (`rayonM`) ou un polygone (`contour`) : seuls les polygones ont des sommets ; (2) coordonnées en [lng, lat] (degrés), donc « dépasse de 0,4 m » exige une conversion en mètres que `core/calepinage/geometrie` ne fournit pas (« distance calculée par `core/calepinage/geometrie` » est faux) ; (3) `point_dans_polygone` n'a effectivement aucun appelant hors tests (vrai).
Correction : « les points d'un obstacle = les 4 coins du rectangle (centre ± demi-dimensions, orientation de l'obstacle), le contour du polygone, ou 8 points du disque ; un point hors du contour du pan par `point_dans_polygone` ⇒ à régler « la lucarne dépasse du pan A » SANS distance (aucun chiffre en mètres, aucune projection à inventer) ». Supprimer « 0,4 m » de l'exemple.

### ACAL864 — CORRIGER
Ouvert : `mesures.py` (`MOTIF_NON_PAVE`, `motif` par pan l. 109) : le cas « 0 module ⇒ motif non pavé » est vrai.
Faux : « n'ajoute « sous-garni » QUE quand `RemplissageProuve` publie un maximum supérieur au posé » : `RemplissageProuve.jsx` est un composant FRONT qui obtient son maximum du moteur (`moteur.calculer`) ; le résultat servi (`pose`, contrat `calepinage_resultat.json`) ne porte aucun maximum : un service serveur ne peut pas le lire. Le « motif » lu est de plus une constante unique (« non pavé »), pas une cause.
Correction : supprimer la branche « sous-garni » (« seul le cas 0 module est signalé ; le maximum prouvé reste montré par `RemplissageProuve`, hors de ce contrôle ») et retirer « Jumeaux/Appelants : régime de preuve lu au résultat servi (`pose`) ».

### ACAL865 — CORRIGER
Ouvert : `atelier/parcoursGuide.js` (EXISTE, 112 l., `ECRANS_ETAPE` : electrique → `EtapeElectrique`, resultats → `PanneauPertesUnifie` ; pas d'entrée `documents`), `commun/RailGuide.jsx` (EXISTE, dans `commun/`, pas `atelier/`), `atelier/ouvrirChamp.js` (ACAL397 livré), `electrique/EtapeElectrique.jsx` (affiche déjà « n points à régler » depuis `parcours.manque`), `docs/audits/l5-calepinage/maquettes/Electrique.dc.html` et `Documents.dc.html` existent.
Faux : (1) « `parcoursGuide.js` et `RailGuide.jsx` créés par ACAL393 (git grep : 0 aujourd'hui) » et le chemin `atelier/RailGuide.jsx` : faux (fichier réel `commun/RailGuide.jsx`) ; (2) « monté … par `RailGuide.jsx` » : le mécanisme de montage d'un écran d'étape est `ECRANS_ETAPE` de `parcoursGuide.js`, et l'étape Électrique est `EtapeElectrique.jsx` (absente des `Files:`) ; (3) deux « n points à régler » différents sur le même écran (synthèse d'ACAL395 depuis `manque[]` vs panneau).
Correction : Emplacement/Files : remplacer `atelier/RailGuide.jsx` par `electrique/EtapeElectrique.jsx` (monter `PretAEnvoyer` en tête) et `parcoursGuide.js` (entrée `documents` dans `ECRANS_ETAPE`) ; supprimer « (git grep : 0 aujourd'hui) » ; préciser que la synthèse d'`EtapeElectrique` (`syntheseElectrique`) est REMPLACÉE par le compte du panneau (un seul nombre).

### ACAL866 — CORRIGER
Ouvert : `BoutonDevis.jsx` : lien « Ouvrir le devis » vers `/ventes/devis/${retour.devisId}/design` (l. 461) ; `/ventes/devis?devis=<id>` confirmé (`lib/search/entityRoutes.js:27`, `ia/cartes/CarteDevisCree.jsx:93`) ; `calepinage_publication.json` porte `reference` (l. 6).
Faux/incomplet : la carte n'apparaît que dans la branche « messages ou manquantes » (`BoutonDevis.jsx:200-206`) ; dans le cas propre (aucun message) le code NAVIGUE directement vers `/ventes/devis/${nouveau}/design` (`:212`) : le « fini quand le lien mène à `/ventes/devis?devis=<id>` » n'est pas atteint dans ce cas, et la carte « Devis DEV-… créé » n'est jamais vue.
Correction : ajouter au Given « sans message ni manquante, la navigation `:212` va elle aussi à `/ventes/devis?devis=<id>` » (ou affiche la carte de succès) ; la référence n'est pas dans `retour` aujourd'hui (`:206`) : à lire de `res.data.reference`.

### ACAL867 — CORRIGER
Faux : « il n'existe PAS de maquette `Documents.dc.html` » : elle EXISTE (`docs/audits/l5-calepinage/maquettes/Documents.dc.html`, 36 Ko) et montre l'écran de fin : « Prêt à envoyer ? 9 contrôles sur 10 sont bons… », bouton « Générer le devis », puis 5 cartes (Plan de pose, Schéma électrique, Note de calcul, Rapport d'étude, Plan DXF) ; pas de carte « Dossier réglementaire ». Libellé : la maquette et `BoutonDevis.jsx:329` disent « Générer le devis », pas « Créer le devis ». « Appelants/Constat » reprend aussi le faux « parcoursGuide.js : 0 aujourd'hui » (voir ACAL865).
Correction : réécrire Constat/Hors périmètre : « composé d'après `Documents.dc.html` » ; Given : les cartes = celles de la maquette (+ « Dossier réglementaire » seulement si l'onglet `dossiers` doit rester atteignable : à trancher) ; bouton primaire « Générer le devis ». Le mount passe par `ECRANS_ETAPE` (comme ACAL865).

### ACAL868 — CORRIGER
Ouvert : `atelier/BarreEnregistrement.jsx` EXISTE (ACAL399 livrée, 37 l., emplacement `children`, `sticky bottom-0`) ; elle est montée par `pages/ventes/ToitureDesign.jsx:1548` ; `BoutonDevis` est monté par `AtelierPanneaux.jsx:280`, et l'étape active est calculée dans `Rail.jsx:174` (état URL).
Faux : (1) « à créer » / « créés par ACAL399 et ACAL393 (git grep : 0 aujourd'hui) » : ils existent ; (2) la barre (ToitureDesign) et l'étape active (Rail, sous AtelierPanneaux) sont dans deux composants distincts, et `BoutonDevis` ne vit pas dans la barre : l'action principale par étape exige de remonter l'étape active et de déplacer/monter `BoutonDevis` dans la barre : `ToitureDesign.jsx`, `AtelierPanneaux.jsx`, `Rail.jsx` absents de `Files:` ; (3) libellé « Créer le devis » vs « Générer le devis » (maquettes `Main/Panneaux/Electrique/Resultats` et bouton existant).
Correction : ajouter `ToitureDesign.jsx`, `AtelierPanneaux.jsx`, `Rail.jsx` aux Files avec la méthode (lire `?onglet=` / `useSearchParams` côté barre, ou remonter `etapeActive`) ; remplacer « Créer le devis » par « Générer le devis ».

### ACAL869 — CORRIGER
Ouvert : `BuilderDom.jsx` (470 l.), ids `rp9-layout-*` (l. 292-460), `ToitureDesign.jsx:1347` (seul importateur), test et golden `ToitureDesign.calepinage.test.jsx` / `__golden__/toitureDesign.calepinage.html` existent, `ToitureDesign.jsx` fait 1776 l. (pas 1738).
Faux : (1) « Retirer la sélection » (ACAL418) n'est pas dans `BuilderDom.jsx` : c'est un bouton créé par `apps/web/src/scripts/roofPro11/barreSelection.ts:84` ; `BuilderDom` a « ✕ Effacer la sélection » (`#rp9-layout-clear-sel`, l. 408-410) ; le sélecteur de module n'est pas non plus dans `BuilderDom` ; donc le « compte de 5 contrôles » ne peut pas être obtenu en ne repliant que le DOM de `BuilderDom`. (2) Le mode guidé/expert et l'étape sont un état URL/localStorage lu dans `Rail.jsx:163-174` (`useModeExpert`, `?mode=`) ; `ToitureDesign.jsx` ne les lit pas ; « passer le mode à `BuilderDom` (≈ 4 l.) » omet cette remontée ; et la scène 3D est visible à toute étape : rien ne dit qu'on est à « l'étape Panneaux ».
Correction : « le volet « Réglages avancés » replié (`<details>`) contient le mode libre, +/−, réinitialiser, rangée, azimut, plan des emplacements ; restent visibles : « Remplir automatiquement », « Annuler », « Rétablir », (`#rp9-layout-clear-sel` renommé ou doublé par le bouton `barreSelection.ts`), le sélecteur de module (hors `BuilderDom` : à nommer) ; le mode vient de `useModeExpert` lu dans `ToitureDesign.jsx` ; la règle « guidé » s'applique à la scène quelle que soit l'étape (à trancher par Reda) ». Ajouter `barreSelection.ts` ou renoncer au chiffre « 5 ».

### ACAL870 — CORRIGER
Ouvert : contrats voisins (`calepinage_parcours_guide.json` etc.), `test_cal223_contrats.py` ; `calepinage_explications.json` absent (OK, neuf).
Faux : « `HelpTip` … a 0 importeur dans `features/calepinage` » : `atelier/Rail.jsx:7` l'importe et l'emploie (`:258`, bulle par onglet d'ACAL419, livrée). Le test rouge nommé (`InventaireDesEchantillonsTest`) n'est pas celui qui échoue pour un échantillon neuf non déclaré : c'est `CheminDeclareTest` (`test_cal223_contrats.py:696-715`, route absente des sources).
Correction : « HelpTip a un seul importateur dans le module (Rail.jsx, bulle d'onglet ACAL419) » ; Test rouge : `CheminDeclareTest::test_chaque_chemin_du_module_existe_dans_les_sources`.

### ACAL871 — CORRIGER
Faux/incohérent : le test exige « aucune phrase ne contient … un nombre » ; or la phrase de l'exemple d'ACAL873 est « année moyenne ; 9 fois sur 10 la production est au-dessus de {p90_kwh} kWh », qui contient 9 et 10 ; et « un identifiant en snake_case » se heurte aux trous `{p90_kwh}` si les accolades ne sont pas retirées avant le test. De plus, le contrat (ACAL870) pose 3 entrées dans `exemple` dont le test d'ACAL871 exige qu'elles soient « un extrait du registre » : le registre doit donc déjà contenir 3 entrées à ce stade (voir ACAL872 pour la garde « toute entrée est employée »). Route : `GET calepinage/explications/` n'est pas liée à un `pk` : action `detail=False` (le patron de `rattachements.py` est écrit pour `detail=True`).
Correction : Given : « aucune phrase ne contient de chiffre (écrire « neuf fois sur dix ») après retrait des `{trou}` » et préciser `detail=False` ; ajouter à ACAL873 la phrase « neuf fois sur dix ».

### ACAL872 — CORRIGER
Faux/incohérent : (1) garde (b) « toute entrée du registre est employée par un écran » échoue dès ACAL872/871 (3 entrées d'exemple posées, aucun écran câblé avant ACAL873-878) : séquence irréalisable. (2) Appelants : « `HelpTip` … 0 dans le module calepinage » : faux (Rail.jsx, ACAL419). (3) Files contient `module.config.jsx` sans qu'aucune clause l'explique (Emplacement n'en parle pas).
Correction : garde (b) « toute entrée du registre dont `ecrans[]` est non vide est employée » (ou liste de tolérance qui rétrécit à zéro avec ACAL878) ; corriger Appelants (HelpTip : 1 importateur dans le module, `Rail.jsx`) ; retirer `module.config.jsx` des Files ou dire pourquoi.

### ACAL873 — CORRIGER
Ouvert : `ResultatHeros.jsx` (9 tuiles `Stat` : P50, puissance, productible, pertes, P75, P90, P95, variabilité, PR : vrai), `DiagrammePertes.jsx:268` (`DiagrammePertesCascadeDetaillee`), `PanneauProduction.jsx:241` (`TableauMensuel`).
Faux : `Files:` omet `ResultatHeros.jsx` (où sont les tuiles) alors que l'Emplacement en fait le site principal ; la phrase de l'exemple porte des chiffres (« 9 fois sur 10 ») contre la règle d'ACAL871 ; la liste inclut « écart PVGIS » (ACAL854) sans `@after: ACAL854`.
Correction : ajouter `ResultatHeros.jsx` aux Files ; `@after: ACAL854` ; phrase « neuf fois sur dix ».

### ACAL874 — CORRIGER
Ouvert : `Raccordement.jsx` (élévation `:293`, marge `:298`, puissance injectée `:303`, déséquilibre `:311`), `CheminementCables.jsx` (chutes DC/AC cumulées `:154-161`, section et longueur par tronçon `:182-230`) : OK.
Faux : « tension à froid et à chaud, ratio DC/AC, écrêtage » ne sont affichés par aucun des trois écrans : « écrêtage » n'apparaît nulle part dans `frontend/src/features/calepinage` (grep) ; `VerdictElectrique.jsx` ne rend que des motifs de publication (`motif.libelle`, `:111-112`) et la liste « Alertes non bloquantes » (`:239`, verdicts non conformes seulement) : le test « la tension à froid porte un « ? » » n'a pas de chiffre où l'accrocher quand le verdict est conforme.
Correction : limiter la liste aux grandeurs réellement affichées : élévation, marge, puissance injectée, déséquilibre (Raccordement), chutes DC/AC cumulées, sections, métré (Cheminement), alertes non bloquantes (Verdict, quand elles existent) ; retirer « tension à froid et à chaud, ratio DC/AC, écrêtage » ou les rattacher à un écran existant (nommer lequel).

## OPTIONNEL (5 lignes)
- ACAL859 : `hypotheses_conso` n'est pas une clé servie (fusionnée dans `avertissements`, `consommation.py:1143`) ; garder le repli « info ».
- ACAL857/860/871 : `MODULES_RATTACHES` est une tuple de noms (`rattachements.py`), pas des lignes d'import : reformuler.
- ACAL851/852 : des comptes « 4 appels internes à paintCard » sont exacts (`optimizer.ts:616, 777, 1201, 1293`) ; lignes de fichiers un peu décalées (1 839 et 1 493 l.), sans conséquence.
- ACAL862 : epsilon 0,01 kWc acceptable (arrondi), à nommer comme `EPSILON_PERTE_PCT` (`validation.py:106`).
- ACAL861/865 : le nom « Créer le devis » est employé à plusieurs endroits du lot alors que les maquettes et `BoutonDevis.jsx:329` disent « Générer le devis » : uniformiser.

## Règles et décisions du fondateur
Aucune violation trouvée : pas d'argent hors `apps/ventes` (ACAL861 ne montre que des kWc), pas de PDF devis, pas de prix d'achat, pas d'import de `models` d'une autre app métier (857 passe par `ventes.selectors_calepinage`), pas de dépendance payante. D-ACAL-40 respectée par 852 ; D-ACAL-32 respectée par 865-869 ; D-ACAL-36 respectée par 853.

## Tâches non vérifiées
Aucune tâche sautée. Limites : la preuve en direct (PA2.5) et les goldens HTML n'ont pas été ouverts ; le contenu exact du composant `Stat` du design système et le comptage « 33 balises `<Stat` » (872) n'ont pas été recomptés (32 hors tests trouvées).
