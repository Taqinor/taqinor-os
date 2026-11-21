# Rapport de vérification — lot D4-a (ACAL692 à ACAL719, 28 tâches)

Code lu : `C:\dev\taqinor-os\.claude\worktrees\l5-verif\` (Grep/Read seulement, rien modifié). Chemins ci-dessous relatifs à ce dossier.

### ACAL692 — OK
`services/validation.py:91` (CLES_VALIDATION), `:161` (ecart_vs_pvcalc), `:353-391` (`_mensuel` sert `chaine_locale_kwh`), `:394` (`_pertes_totales`), `:473` (`_bloc_vide`) ; échantillon `contract_samples/calepinage_simulation.json:749` écrit bien `chaine_kwh` ; 0 lecteur ailleurs (grep). Tests nommés présents (`test_calx195_validation.py:320,326`, `test_calx5_simulation.py:603`). Étape publiée porte `etape, libelle, perte_kwh, perte_pct, rang` (`chaine_pertes.py:339`).
Réserve (OPTIONNEL) : le bloc `validation` de `calepinage_resultat.json` (l.741 et l.2061) est tronqué à 8 clés (ni `pertes_totales`, ni `mensuel`) : « mensuel[].chaine_locale_kwh » n'y a pas de `mensuel` où se poser ; n'y ajouter que `poste_principal`.

### ACAL693 — OK
`services/etapes/vieillissement.py:111` (tableau_pluriannuel, bloc `_bloc` l.270 avec horizon/source/produit/motif), `:232` (`_fiches`), `CLE_HORIZON='annees_exploitation'` l.72 ; `simulation.py:1461-1471` réduit bien `projection` à la liste de lignes ; `projection` absent de `calepinage_resultat.json` (grep) ; garanties dans `equipements.py:76` et `apps/stock/models_fiche_technique.py:275`. 0 lecteur front de `projection` (grep).

### ACAL694 — OK
`services/rapport/production.py:258` (html_de_section : mensuel, par pan, quantiles, écart devis, aucun vieillissement), `:146` (`_table_mensuelle`), `rapport/__init__.py:245` (`nombre_tel_que_servi`, None → « — »), `MODULES_DE_SECTION` l.91 ; classes de test `test_calx301_section_production.py` présentes. Dépend bien de ACAL693 par `@after`.
Réserve : « Contrat partagé : `%scalepinage_resultat.json` » — le `%s` est un reste de gabarit ; lire `backend/django_core/apps/calepinage/contract_samples/calepinage_resultat.json`.

### ACAL695 — CORRIGER
Faux : `ORDRE_ETAPES` compte **25** noms, pas 24 (`services/chaine_pertes.py:103-134`, comptage Python = 25) : `ombrage_diffus` (ACAL461, déjà construite) manque à la table de correspondance de la tâche (5+2+1+6+10 = 24). La tâche exige « couvrir EXACTEMENT ses 24 noms » : le test de couverture serait rouge dès le premier jour, et la chaîne « 24 étapes » est répétée (Constat, Given, Listes figées).
Correction : dans « Given », ajouter `ombrage_diffus` à `ombres_proches` (« horizon, ombrage_proche, acces_module, ombrage_diffus, inter_rangees, mismatch_ombrage » — c'est de l'ombrage lié au ciel, même famille) et remplacer « 24 étapes / 24 noms » par « autant d'étapes que `len(ORDRE_ETAPES)` (25 aujourd'hui) ». Le reste (clé dans `cascade`, `BLOCS_SIMULATION` à 12 blocs `services/electrique.py:438`, tests à réaligner `test_calx141_contrat_cascade.py:53`) est exact.

### ACAL696 — OK
Prémisse vraie : `production/PanneauProduction.jsx` n'a aucun lecteur des postes ; `CascadePertesLignes.jsx:107` existe (ACAL444). Précision non bloquante : ce composant prend `lignes` (sortie de `construireCascadeDetaillee(etapes, totalPct)` de `DiagrammePertes.helpers.js:22`), pas `cascade` : le constructeur appellera cette fonction avec `cascade.etapes`.

### ACAL697 — CORRIGER
Faux/incomplet : un nouveau code dans `_DEFINITIONS_DOCUMENTS` (`services/documents/__init__.py:187`) doit aussi avoir une entrée `MISES_EN_PAGE['pertes_en_postes']` (comme `presentation_compacte`, l.453) sinon `scripts/check_documents_calepinage.py` (garde CI, `PRODUIT_AILLEURS` l.77) échoue, et `test_calx327_aucun_montant.py::DerivationEtCouvertureTest` (l.419-449) exige que chaque code PDF dérivé soit couvert ou exempté. La tâche cite le script `check_calepinage_routes_sous_contrat` mais pas ces deux gardes.
Correction : ajouter à « Emplacement » : « et `MISES_EN_PAGE['pertes_en_postes'] = lambda: _piece('pertes_en_postes').html_de_pertes_en_postes` dans `services/documents/__init__.py` » ; à « Listes figées » : « `scripts/check_documents_calepinage.py` et `test_calx327_aucun_montant.py::DerivationEtCouvertureTest` (le code neuf est couvert par sa mise en page) ». Le reste est exact (9 documents, `REGISTRE_REMISE` `views/remise_document.py:48`, `CHEMIN_GET` `test_acal_remise_document.py:53,209`, pas de prix, autorisé par D-ACAL-38 d).

### ACAL698 — CORRIGER
Incomplet : « Voir les sources » doit ouvrir le `<details>` de `ReglagesUtilises`, qui est un `<details>` NON contrôlé dans `production/BandeauProvenanceProduction.jsx:131-167` ; ce fichier n'est pas dans `Files:`. Aucun moyen propre d'ouvrir un `<details>` d'un autre composant sans le modifier (prop `ouvert`/ref).
Correction : ajouter `frontend/src/features/calepinage/production/BandeauProvenanceProduction.jsx` (+ son test `BandeauProvenanceProduction.test.jsx`) à `Files:` et dire « `ReglagesUtilises` gagne une prop `ouvert` pilotée par `LigneValeursPubliees` ». Le préfixe existe (`reglages/profilDepart.js` : `estProfilDepart`, ACAL405 construite) ; clés `simulation` sans préfixe (`simulation.py:127`), `electrique_societe.` préfixées : le repli « clé brute » couvre.

### ACAL699 — OK
`chaine_pertes.py:1431` (`completude_de_la_chaine` ne publie que le compte), `services/etapes/__init__.py:218-226` (`etape_omise` écrit « Champ manquant : « … » »), `parametres_cles.py:191` (`registre(section)` → (libellé, unité, référence)), `champ=` réels dans `services/etapes/` : `simulation.<clé>`, `fiche_module.<champ>`, `serie.*`, `ombrage.*`, `electrique.*` — cohérent avec la répartition réglage/fiche/non localisable. (`electrique_societe.<clé>` n'est jamais émis par une étape aujourd'hui : branche inoffensive.)

### ACAL700 — OK
`ListeManques.jsx` (ACAL397), `atelier/ouvrirChamp.js`, `BandeauBorneHaute` (`BandeauProvenanceProduction.jsx:95`), onglet `fiches` existe (`atelier/onglets.js:53`), `DemarrageRapide.jsx` existe ; `@after` correct (699, 695).
OPTIONNEL : le calcul du lien de `lienManque` est privé à `ListeManques.jsx` ; le constructeur devra l'exporter ou le recopier.

### ACAL701 — CORRIGER
Chiffre périmé : « ≤ 24 entrées plus `sans_bande` » et « les 24 étapes » ; `ORDRE_ETAPES` en compte 25. Correction : « ≤ 25 entrées ». Le reste est exact (aucun `plages_usuelles` dans le dépôt ; `data/` existe avec `profil_depart.json` ; aucune valeur écrite par le plan).

### ACAL702 — OK
`cascade.total_pct` et `gain` présents (`chaine_pertes.py` l.2470-2505, 339), `BLOCS_SIMULATION` ne sert que 12 blocs (cascade DEDANS) ; tests à réaligner existants ; `@after ACAL701` même lane.

### ACAL703 — CORRIGER
`Files:` incomplet : `ResultatHeros` ne reçoit que `total/simule/motif/avertissements` (`production/ResultatHeros.jsx:13`) et `CascadePertesLignes` ne reçoit que des `lignes` précalculées par `construireCascadeDetaillee` (`DiagrammePertes.helpers.js:22`, aucune notion de bande). Pour porter `cascade.plages` il faut modifier `PanneauProduction.jsx` (passer `plages` au héros), `DiagrammePertes.jsx` (l.125-149, passer `cascade.plages`) et `DiagrammePertes.helpers.js` (reporter `statut/min/max/url` dans chaque ligne). De plus, l'onglet Production n'affiche des lignes d'étapes qu'après ACAL696 (dépliage).
Correction : ajouter à `Files:` `production/PanneauProduction.jsx`, `production/DiagrammePertes.jsx`, `production/DiagrammePertes.helpers.js` ; mettre `@after: ACAL702, ACAL696` ; dire dans « Emplacement » que la ligne de l'onglet Production vient du dépliage d'ACAL696.

### ACAL704 — CORRIGER
(1) Le test qui échouera n'est pas nommé : `tests/test_calx145_parametres_simulation.py::ProfilDepartFichierTest::test_chaque_valeur_est_sourcee_et_chaque_cle_comptee` exige que `valeurs ∪ sans_source` du FICHIER `data/profil_depart.json` égale tout le registre (ACAL403/404 sont construites : 11 valeurs + 29 sans_source = 40 clés). Ajouter deux clés au registre sans les inscrire dans ce fichier le rend rouge ; idem `test_cal223_contrats.py:586-606` (échantillon). Ni `data/profil_depart.json` ni `calepinage_profil_depart.json` ni ces deux tests ne sont dans `Files:`.
(2) Comptes périmés : `CLES_SIMULATION` = 31 clés aujourd'hui (`parametres_cles.py:94`) + 9 électriques = 40, pas « 37 → 39 ».
Correction : ajouter à `Files:` `backend/django_core/apps/calepinage/data/profil_depart.json`, `…/contract_samples/calepinage_profil_depart.json`, `…/tests/test_calx145_parametres_simulation.py`, `…/tests/test_cal223_contrats.py` (les deux clés vont dans `sans_source` avec leur motif) ; remplacer le compte par « 31 → 33 clés simulation ». La prémisse (constante `(600.0, 2400.0)` `chaine_pertes.py:1240`, usage l.1356, test `test_acal_annee_moyenne.py:139`) est vraie.

### ACAL705 — CORRIGER
(1) Mauvais golden : `tests/golden_simulation/casablanca_ramadan.json` ne contient que `decalage_minutes/etapes/total_pct` (test d'instant UTC, ACAL131) — pas de `mensuel`, ni de kWc. Le golden de `test_calx196_golden.py` est `cascade_pluriannuelle_casablanca.json` (production.mensuel + total, l.205-224). Corriger « Given le golden `…/cascade_pluriannuelle_casablanca.json` ».
(2) Contraire à D-ACAL-7 (déjà codée) : quand `production.total.complete` est faux, le PR annuel et les quantiles sont masqués (`chaine_pertes.py:1370-1383`, « borne haute fausse »). Un `pr` mensuel publié dans ce cas contourne cette règle (et ACAL700 écrit « l'indice de performance s'affiche dès que le résultat est complet »). Ajouter au Given : « `complete` faux ⇒ `pr` de chaque mois `null` avec le motif `production.total.performance_ratio_motif` ; `temperature_ambiante_c` reste servie ».
Réserve : `%scalepinage_resultat.json` = reste de gabarit (lire `contract_samples/calepinage_resultat.json`).

### ACAL706 — CORRIGER
Faux : `cascade.irradiation_incidente_kwh_m2` est l'irradiation de la FENÊTRE ENTIÈRE (`chaine_pertes.py:513-520`, commentaire ACAL128 « fenêtre entière »), alors que `ghi_annuel_kwh_m2` est « ramené à l'année moyenne ». Avec une fenêtre pluriannuelle (jusqu'à 10 ans) `gain_pct` serait faux d'un facteur N.
Correction : « `plan_annuel_kwh_m2` = somme des 12 `production.irradiation_mensuelle[].irradiation_plan_kwh_m2` (année moyenne, `services/irradiation_mensuelle.py:75-88`) ; jamais `cascade.irradiation_incidente_kwh_m2` ». OPTIONNEL : dire quel horizon la requête à 0° applique (un masque PVGIS réduirait le GHI) ; la fixture `fixtures_pvgis` existe (`tests/fixtures_pvgis/`).

### ACAL707 — OK
`PanneauProduction.jsx:241-267` (`TableauMensuel` « Mois / P50 »), `atelier/modeExpert.js` (`useModeExpert`, ACAL394), aucun lecteur front de `irradiation_mensuelle`/`bilan_mensuel`. Note : « ligne 400 » n'existe plus (fichier de 397 lignes) : non bloquant.

### ACAL708 — OK
`services/rapport/production.py:146` (`_table_mensuelle(mensuel, irradiation=None)` déjà étendue par ACAL452), `TableMensuelleTest` présent. Dépend de 705/706 par `@after`.

### ACAL709 — CORRIGER
Faux : (a) `exemple_vide` de `calepinage_resultat.json` a `"autoconsommation": null` (l.1140, 1299) — pas de `taux_couverture` null ni de `motif_absence` ; ces clés ne sont dans un bloc objet que dans `calepinage_simulation.json` (`exemple_vide`). (b) `energie.apres_batterie` est servi par le code (`services/etapes/autoconsommation.py:351`) mais ABSENT de `calepinage_resultat.json` (présent seulement dans `calepinage_simulation.json:436,1508`). (c) `ResultatHeros` ne reçoit pas `autoconsommation` (`ResultatHeros.jsx:13` ; `PanneauProduction.jsx:366` ne le passe pas) : `PanneauProduction.jsx` doit changer, or il n'est pas dans `Files:`.
Correction : « Given » = `exempleContrat('calepinage','calepinage_simulation','exemple')` (porte `apres_batterie` true) puis `exemple_vide` du même fichier ; ajouter le cas résultat à bloc `autoconsommation: null` ⇒ « non calculée » (sans motif servi, repli « Aucune consommation connue ») ; ajouter `production/PanneauProduction.jsx` à `Files:`.

### ACAL710 — OK
Prémisses vraies (aucun lecteur front de `projection`/`duree_de_vie`, P90 replié dans « Détails statistiques » `ResultatHeros.jsx:49-65`), `@after ACAL693` ; N lu dans la dernière année, pas de verdict.

### ACAL711 — OK
`services/etapes/mismatch_ombrage.py:303` (`_publier_chaine` sans bornes), `:322` (`_borne` agrégé), `:230-260` (`entree.bornes` agrégées au pan), `chaine_pertes.py:768-771` (`_etape_sommee` : `dict(appliquees[0] …)` perd l'entrée du 2ᵉ pan) ; `appliquer` filtre déjà `chaine['pan'] == repere`. Valeurs de l'exemple recalculées à la main : 2,5 / 1,5 / 2,0, 20 %, 40 %, 33,333 %, 50 % : exactes. `GardeAntiForfait` (`test_calx168…:362`) admet {0,1,3,6,0.0,1.0,100.0} comme dit.

### ACAL712 — CORRIGER
Dépendance manquante (PACT11) : la carte affiche « l'hypothèse servie `entree.hypothese_orientation.texte` (ACAL713) » et l'échantillon `exemple_ombrage_chaines` ne gagne cette clé que par ACAL713, tâche d'une AUTRE lane (`calepinage/simulation`) ; or `@after` ne nomme que ACAL711 → départ en parallèle, texte vide/échantillon sans la clé.
Correction : `(@after: ACAL711, ACAL713)`. Réserve : `%s/electrique/VerdictElectrique.test.jsx` = reste de gabarit (`frontend/src/features/calepinage/electrique/VerdictElectrique.test.jsx`, existe, 366 l.). Le reste est exact (`VerdictElectrique.jsx:205` `BlocDerogations`, 421 l.).

### ACAL713 — OK
`roof_layout_v2.schema.json` `$defs/panel` : `cx, cy, face, n` (+ `additionalProperties: true`), `angleDeg` écrit par `apps/web/src/scripts/roofPro11/prefill.ts:221-227,1051`, atelier en paysage (`apps/web/src/lib/roofPro2.ts:7,22`). Texte sans chiffre, marqué hypothèse.

### ACAL714 — CORRIGER
Test irréalisable tel quel : `renderSolarAccess` est une fermeture de `createShadingUi` (`shadingUi.ts:488, 936-978`) et l'en-tête de `shadingUi.test.ts` dit que « le reste de `createShadingUi` a besoin d'une carte MapLibre + du DOM, hors de portée d'un test pur » : le cas « aucun bouton, la ligne dit où régler » ne peut pas s'y écrire. 
Correction : extraire la construction du HTML de proposition (et de la ligne « Retrait proposé : aucun seuil réglé… ») dans une fonction pure exportée (ex. `htmlProposition(resume, seuil, peutRetirer)` dans `shadingUi.ts`) et tester CELLE-LÀ ; garder `proposeShadedRemoval(…, null) === null` dans `shadingEngine.test.ts`. Autres prémisses vraies (`SOLAR_ACCESS_LOW` 7 occurrences ; `shadingEngine.ts:474,504,577` ; `shadingUi.ts:32,951,971` — numéros décalés par rapport au texte : 934/954 → 951/971 ; `useAtelierBoot.js:98-107`, appelé aux l.161 et 317 ; `types.ts:142`). Réserve : `%s/parametres_calepinage.json` = reste de gabarit (`…/contract_samples/parametres_calepinage.json`). Hypothèse de départ : doit aussi passer par ACAL716 (déjà en `@after`).

### ACAL715 — OK
Fonction pure neuve testable (`verdictOmbrage.ts`), `renderSolarAccess` l.936, `s.average` `shadingEngine.ts:496-505`, aucune borne préremplie (D-ACAL-31 respectée : étiquette seulement si les deux bornes sont saisies).

### ACAL716 — CORRIGER
Comptes périmés et fichier manquant : `CLES_SIMULATION` compte **31** clés aujourd'hui (pas 28 → « 28 avant, 31 après »), total registre 40 (pas 37 → 40). Surtout, `data/profil_depart.json` (le FICHIER lu par `services/profil_depart.py:23`) n'est pas dans `Files:` alors que `test_calx145_parametres_simulation.py::ProfilDepartFichierTest::test_chaque_valeur_est_sourcee_et_chaque_cle_comptee` exige `valeurs ∪ sans_source == tout le registre` et que `test_cal223_contrats.py:779-790` compare le GET servi à l'échantillon.
Correction : ajouter `backend/django_core/apps/calepinage/data/profil_depart.json` et `…/tests/test_calx145_parametres_simulation.py` à `Files:` (les trois clés y entrent dans `sans_source` avec motif) ; corriger les comptes en « 31 → 34 clés simulation, 40 → 43 au total ». Types `nombre`/`pourcentage` avec bornes : supportés (`parametres_cles.py:225-262`).

### ACAL717 — OK
`shadingEngine.ts:222` (isSunBlocked), `:264` (hourlyShadeFactors, diffus 0,25 `:49`), `:62` (MID_MONTH_DAY_OF_YEAR, décembre = 349), `roofPro2.ts:343-355` (formule δ = −23,44°·cos(2π(j+10)/365) comme dans le test annoncé), `roof-tool-pro11.ts:3959` (`applySoleilStep`) ; barre du soleil montée dans `BuilderDom.jsx:266` (ACAL434 construite). Valeurs recalculées : à 33,57° N en décembre le soleil passe sous 20° avant 9,1 h solaire (points horaires 7,5 h et 8,5 h masqués, 9,5 h non) : la phrase « entre 7 h et 9 h » est cohérente.

### ACAL718 — OK
`core/calepinage/soleil.py` : `_elements_solaires`, `_jour_julien`, `DEGRES_PAR_MINUTE_HORAIRE=0.25` (l.95), `EntreeInvalide` (l.75), `__all__` (l.78) ; formule de l'heure solaire (l.240-245) = celle de la tâche ; recalculé : écart = 60 + 14,2 + 30,4 = 104,6 min, midi légal 13,743 h ; classes de test nommées présentes (`test_calx146_soleil.py:343 EntreesRefusees`, oracle pvlib avec `skipTest`).

### ACAL719 — CORRIGER
`Files:` incomplet : la tâche dit elle-même que les trois goldens `frontend/src/features/calepinage/__golden__/toitureDesign.{lead,devis,calepinage}.html` sont « À RÉALIGNER » (une ligne ajoutée dans `BuilderDom.jsx`) mais ne les liste pas (ACAL434 les liste). Correction : les ajouter à `Files:` ; sinon la CI (golden) est rouge. Dépendance serveur (ACAL730, `@after` correct) hors lot ; `calepinageApi.js` fin de fichier append-only OK ; `calepinageApi.golden.json` et `.golden.test.mjs` existent.

---
## OPTIONNEL (5 lignes max)
- ACAL692 : le bloc `validation` de `calepinage_resultat.json` est tronqué (8 clés) ; n'y ajouter que `poste_principal`.
- ACAL696 : préciser « `construireCascadeDetaillee(cascade.etapes, cascade.total_pct)` puis `CascadePertesLignes lignes=` ».
- ACAL700 : `lienManque` est privé à `ListeManques.jsx` — l'exporter.
- ACAL706 : dire si la requête à 0° applique ou non le masque d'horizon PVGIS.
- Restes de gabarit `%s` dans ACAL694, 705, 712, 714 (chemins de contrat/test).

## Résumé par verdict
OK : 692, 693, 694, 696, 699, 700, 702, 707, 708, 710, 711, 713, 715, 717, 718 (15)
CORRIGER : 695, 697, 698, 701, 703, 704, 705, 706, 709, 712, 714, 716, 719 (13)
SANS OBJET / DOUBLON / À SCINDER : aucun. Tâches non vérifiées : aucune (les 28 ont été lues ; les URL publiées citées n'ont pas été rouvertes, hors code).
