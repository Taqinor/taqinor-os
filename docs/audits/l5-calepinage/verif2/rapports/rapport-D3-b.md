# Rapport vérificateur — lot D3-b (27 tâches) — code lu dans l5-verif

Défaut transversal (6 tâches : 647, 650, 657, 671, 673, 676) : toute clé ajoutée à `CLES_ELECTRIQUE_SOCIETE` exige une ligne
`TYPES_CLES[SECTION_ELECTRIQUE_SOCIETE]` (`parametres_cles.py:260-270`), sinon `tests/test_acal_reglages_types.py::test_chaque_cle_du_registre_a_un_type`
(l.55-62) et `test_calx69_registre_servi.py::test_le_type_servi_est_celui_de_types_cles` (l.113-125) sont rouges. Seule ACAL678 le dit.
Correction commune : ajouter dans chaque « Emplacement » « + une ligne `TYPES_CLES` (type `nombre`, minimum 0) » et nommer `test_acal_reglages_types.py` dans « Assertions existantes ».

### ACAL647 — CORRIGER
- Prémisse de données absente : `AffectationChaines.jsx` ne lit ni réglages ni accès solaire par module (grep `acces` : seul `chaineFaible.acces_solaire`, l.590). Le serveur ne sert que le PIRE module (`services/electrique.py:477-515`, `chaine_la_plus_faible`) ; l'accès par module n'est que dans `zones[].geometry.solarAccess.values` du document. « 6 modules sous le seuil » n'a donc aucune source côté écran, et l'écran « ne compare rien » (AffectationChaines.jsx l.121).
- Doublon partiel : ACAL725 (D4, « poser et montrer le drapeau optimiseur par module à l'écran d'affectation », @after ACAL733) et ACAL733 (D4, drapeau `optimiseur` dans l'affectation manuelle) refont ACAL644 + le marquage de 647 ; 644/733 touchent tous deux `chaines.py::CLES_IMPOSEE` (lanes electrique et simulation différentes).
- Jumeau mal nommé : `SV/polystring.py` n'existe pas (c'est `services/polystring.py`) ; jumeau omis : le réglage `seuil_derivation_acces` (`parametres_cles.py:141`, `etapes/mismatch_ombrage.py:87`) est le même concept (accès sous lequel un module est « dérivé ») : dire pourquoi une 2e clé, ou réutiliser.
- Correction : (1) ajouter à « Emplacement » un calcul serveur de la liste `modules_sous_seuil` (lecture de `solarAccess` du document, comparée au réglage dans `services/ombrage_chaines.py`, servie dans `electrique.chaine_la_plus_faible` voisin ou `affectation`), l'écran ne faisant que l'afficher ; ajouter ces fichiers à `Files:` ; (2) fusionner le marquage au clic dans ACAL725 (647 devient `@after ACAL725` et ne garde que « proposer ») ; supprimer ACAL733 au profit d'ACAL644 ; (3) TYPES_CLES ; (4) corriger `SV/polystring.py` → `services/polystring.py`.

### ACAL648 — OK
Ouvert : `services/chaines.py:143` (`cle_module`), `services/production.py:65-90` (`numeros_des_modules` rend `()` si non numéroté, `cle_de_module` retombe sur le rang), `tests/test_acal_cle_de_pan_stable.py:74,76,93`, `test_cal234_affectation_manuelle.py:69`. Détail : `cle_module(` n'a qu'UN appelant (`affectation`, l.1068/1077), pas trois.

### ACAL649 — CORRIGER
- « Persistance : n/a » et « ancien centre mémorisé avec la ligne à l'enregistrement » se contredisent : `CLES_IMPOSEE = ('module','chaine','mppt','onduleur')` (`chaines.py:1374`) refuse toute autre clé (`normaliser_affectation_imposee`, l.1385-1410) et rien n'écrit de centre ; ligne publiée = 4 clés. Sans centre mémorisé la tâche retombe sur « comportement d'aujourd'hui » : le « fini quand » (modules 4 à 10 gardent leur chaîne) n'est jamais atteint. Le « Given » parle de centres « pour les deux états » : l'état d'avant retrait n'existe plus.
- Correction : ajouter la persistance de `cx, cy` (acceptés par `normaliser_affectation_imposee`, renseignés SERVEUR à l'enregistrement depuis `geometry.panels` ; `Persistance : entree_electrique.affectation_manuelle[].cx/cy`, clés ajoutées à `CLES_IMPOSEE` après celle d'ACAL644, contrat `calepinage_entree_electrique.json` + `test_acal_materiel_electrique.py`), ou supprimer ACAL649 et garder ACAL648 (mesure seule).

### ACAL650 — CORRIGER
- `_groupes_electriques(layout)` (`chaines.py:367`) ne reçoit aucun réglage : la tolérance société doit traverser `concevoir_par_pan(**options)` (appel unique `services/electrique.py:1524`), fichier absent de `Files:`.
- Chaque chaîne est rattachée à son pan par `PanPose.label`/`cle` (`affectation`, polystring, cheminement, rapport ; `_groupes_du_pan` l.340-353) : le libellé du groupe fusionné et le sort de `verdict_affectation` (refus « UN pan », l.1503-1505) ne sont pas définis. « ≤ 40 l. » semble sous-estimé.
- TYPES_CLES manquant.
- Correction : ajouter `backend/django_core/apps/calepinage/services/electrique.py` à `Files:` (lecture du réglage, passage en option) ; ajouter à « Emplacement » « le groupe fusionné garde le libellé du premier pan et `affectation` publie chaque module avec SON pan d'origine » (ou scinder en deux tâches : noyau + affectation) ; TYPES_CLES.

### ACAL656 — SANS OBJET
Déjà construit par CALX356 (cochée `[x]` dans docs/PLAN2.md l.710) : `importers/fiche_pan_ond.py:90` (`'muVocSpec': ('temp_coeff_voc_pct_c','mv_par_c_relatif_voc')`), `:184-188` (÷ (Voc × 10), refus si Voc ≤ 0), test `test_cal_import_pan_ond.py:100-106` (`assertNotIn('muVocSpec', non_reconnus)` et valeur égale). Les clauses « docstring laisse non reconnus », « MODULE_FIELD_MAP 8 clés / ONDULEUR 6 clés » sont fausses (15 et 11 clés). Seul reste : nommer la conversion dans l'aperçu (aucun champ `conversions` dans `PropositionImport`) → à fusionner dans ACAL658 (« l'aperçu porte la liste des conversions nommées, clé `conversions` ajoutée au contrat `fiche_import_pan_ond.json` »). Supprimer ACAL656.

### ACAL657 — CORRIGER
- Prémisse périmée : CALX339/356/357 sont cochées (docs/PLAN2.md l.692, 710, 711) ; « après CALX356 … ouverte » est faux.
- Le seuil société doit atteindre un lecteur « stdlib seule, aucun import Django » (`fiche_pan_ond.py:3`) : la vue `views/fiche_technique.py:97-172` appelle `parse_pan_ond_bytes` sans réglage et ne connaît pas `refus` ; ni la vue ni `contract_samples/fiche_import_pan_ond.json` ni `parametres_calepinage.json` ne sont dans `Files:`.
- TYPES_CLES manquant.
- Correction : `Files:` + `views/fiche_technique.py` (lit le réglage via `apps.calepinage.selectors.parametres_de_societe` et le passe à `parse_pan_ond_bytes(..., ecart_pmax_pct=)` ; `refus` non vide ⇒ 400 champ `file`) + les deux échantillons ; remplacer « après CALX356 … ouverte » par « CALX356 livrée » ; TYPES_CLES.

### ACAL658 — CORRIGER
- `COEFFICIENTS_DERIVES` (ACAL656) n'existera pas : la conversion se fait dans `_convertir` (`fiche_pan_ond.py:169-189`, branche `mv_par_c_relatif_voc` ; `raw` fourni). Il faut une branche `ma_par_c_relatif_isc` (÷ (Isc × 10)) et une clé `muISC` dans `MODULE_FIELD_MAP` (+ `NCelS` en `int`), pas une table neuve. Retirer `@after ACAL656` (supprimée).
- « 8 clés → 9 » faux : 15 clés → 17.
- Assertions à réaligner : `test_cal_import_pan_ond.py:100` ET `:292-293` (`FichiersPvsystReelsTests` : « muISC non reconnu » sur le vrai .PAN) ; le second n'est pas cité.
- Correction : Emplacement = `_convertir` + `MODULE_FIELD_MAP` ; « Listes figées : 15 → 17 clés » ; Assertions : ajouter `:292-293` ; `@after: ACAL659` seul. Arithmétique vérifiée : 7,5 ÷ (13,9 × 10) = 0,054.

### ACAL659 — CORRIGER
Colonnes absentes confirmées (`models_fiche_technique.py` : aucun `cellules*`, `opt_*` sans compat., `ond_compteurs_compatibles` l.775 seul). Mais le modèle change sans migration dans la tâche : ACAL660 (PLAN_AUDIT_STOCK, `@after: -`, lane `stock/fiches`) migre aussi les champs d'ACAL720 et ACAL816, qui annoncent chacune leur propre migration (INDEX l.198, 291) ⇒ `makemigrations --check` rouge ou 3 migrations en collision sur la même app.
Correction : mettre `@after: ACAL659, ACAL720, ACAL816` sur ACAL660 et retirer « avec sa migration » d'ACAL720 / ACAL816 (une seule migration, ACAL660, mono-écrivain), ou faire porter la migration par ACAL659 (Files + `migrations/`).

### ACAL661 — OK
Ouvert : `services/chaines.py:415` (`_specs_onduleur`, appelants l.451 et 896 : exact), `:586-620` (`_verdict_mppt`), `core/electrique/chaines.py:566-587` (`_allouer_mppt` : avec n=1 les pans retombent sur l'entrée 1 — comportement visé), `core/electrique/types.py:230` (`SpecOnduleur` champs optionnels en fin).

### ACAL662 — CORRIGER
- `_regle_de_chaine(module_specs, onduleur_specs, optimiseur_specs, *, designation)` (`electrique.py:3650`) ne reçoit aucune identité d'onduleur ; la clause laisse « le constructeur lit `resoudre_materiel` pour fixer lequel » alors que le mutant exige « SKU ». Indécis = non faisable d'un coup.
- Assertion non citée : `test_calx211_optimiseur_longueur.py:94` (`FicheCompleteTest` : `bornes_non_verifiables == []`) devient rouge (fiche complète sans liste ⇒ une entrée de plus) ; seuls les trois `len(...)==1` (l.114,126,134) sont cités.
- Correction : Emplacement : « `_regle_de_chaine` reçoit `onduleur_sku` ; l'appelant le lit par `Produit.sku` du produit désigné (`materiel_resolu`, sélecteur stock) » ; Assertions : ajouter `:94` à réaligner. (`apps/ventes/compatibilites.py` : `optimiseur` = 0 occurrence, confirmé.)

### ACAL664 — CORRIGER
La température utilisée est fausse : `TemperaturesSite.chaud_c` est une température de CELLULE (`electrique.py:98-99`, « le chaud est une température de CELLULE » ; défaut 70 °C, `core/electrique/types.py:60`), alors que le déclassement d'un onduleur dépend de la température d'AIR (`temperatures_tmy.py:109` `temperature_max_c` = T2m ; ACAL740 utilise `t2m_c`). Avec le défaut 70 °C, une fiche « −2 %/°C au-delà de 45 °C » rendrait 50 % et non la réalité.
Correction : remplacer « la température maximale du site (`TemperaturesSite.chaud_c`) » par « la température d'air maximale du site (T2m du TMY, `temperatures_tmy.py`, ou saisie dédiée) ; absente ⇒ motif `non_verifiable` « température d'air non connue » » ; Given : « site à `temperature_air_max_c` = 50 °C ». Coordonner avec ACAL740 (une seule fonction `puissance_a_temperature`, ACAL740 la réutilise : `@after ACAL664`).

### ACAL665 — OK
Ouvert : `selectors.py:727` (`calepinage_retenu_pour_devis`), `installations/selectors.py:36` (`calepinage_retenu_du_chantier`), `installations/models_chantier.py:381-409` (`voc_attendu_v`, `isc_attendu_a`, `pmax_attendu_w`), `tests/test_elec_affectation_chaines.py:91` (`AffectationTest`). Arithmétique 10 × 49,5 = 495 ; 10 × 710 = 7100. Voir OPTIONNEL (test de sélecteur à base).

### ACAL671 — CORRIGER
La « perte d'ombrage de chaîne publiée » n'est pas disponible dans `_rapport_publication` (évaluation électrique pure, `electrique.py:2793-2860`, aucune simulation) : `ombrage_chaines` ne publie que de la géométrie (`acces_min`, `ecart_interne`, « AUCUN kWh », `mismatch_ombrage.py:7-12`) ; la perte en % vient de la cascade simulée (D4). Le « 12 % » de l'exemple n'a pas de source. TYPES_CLES manquant pour les 2 clés.
Correction : Emplacement : « la perte lue dans `resultat['pertes']` (étape `mismatch_ombrage`, borne retenue) ; calepinage non simulé ⇒ motif `non_verifiable` « perte d'ombrage non simulée » » ; ou remplacer l'entrée par `ecart_interne` (géométrique, publié) avec un seuil nommé `seuil_ecart_acces_optimiseur` ; TYPES_CLES ×2.

### ACAL672 — OK
Ouvert : `services/documents/plan_cablage.py:266` (`_lignes_de_chaine`), `:272` (`_lignes_de_legende`), `:288` (`_verifier_legende_sans_montant`), `:505` (`_plan_du_calepinage`), `tests/test_calx310_plan_cablage.py:138,151` (les deux tests cités existent).

### ACAL673 — CORRIGER
Aucun type « texte » : `TYPES_CLES` n'admet que nombre, pourcentage, entier, enum, table_mensuelle, intervalle_annees, booleen, table (`parametres_cles.py:212-224`, `services/parametres.py:482-491, 654-700` ; une clé sans type déclaré est refusée par la garde). Une consigne en phrase ne peut pas être déclarée sans un type neuf, donc sans toucher `services/parametres.py` (+ `_NOMS_DE_TYPE`, contrat `parametres_calepinage.json` `pourquoi` listant les types, `test_calx69_registre_servi.py`) — aucun n'est dans `Files:`.
Correction : ajouter un type `texte` (`{'type':'texte'}`, chaîne non vide, ≤ 500 car.) : `Files:` + `services/parametres.py`, `tests/test_acal_reglages_types.py` ; ou renoncer au réglage et passer par `table` avec forme `{'texte': string}` dans `FORMES_TABLES`.

### ACAL674 — CORRIGER
- « Le plan de câblage fournit déjà `chaine`, `mppt`, `onduleur` par module » est faux : les `modules[]` ne portent que `chaine`, `couleur`, `manuel`, `centre`, `module_m` (`plan_cablage.py:149-165, 204-216`) ; `mppt`/`onduleur` ne sont que dans la légende par chaîne. `_calque_chaines` (`export_dxf.py:249-285`) ne lit que `chaine`. `plan_cablage.py` est absent de `Files:`. L'attribut `N` n'est pas défini.
- `_calque_chaines` est aussi modifié par ACAL605 (lane planche, « emprise vraie ») : 674 n'est que `@after ACAL604` ⇒ collision sur la même fonction ; le « Jumeaux » décrit exactement 605 sans le nommer.
- Correction : `Files:` + `services/documents/plan_cablage.py` (`_plan_de_cablage` recopie `onduleur`, `mppt` et `rang` dans chaque module) ; définir `N` = numéro du module dans sa chaîne (ordre de l'affectation) ; `@after: ACAL605` (en plus de 604) ; remplacer « constat T1-F1-031, autre tâche » par « ACAL605 ».

### ACAL675 — OK
Ouvert : `services/protections.py:73` (`_ajout`), `:137` (`checklist_protections`, clés `organes/justifications/omissions`), `:236` (`organes_retenus`), `champs_entree.py:117` (`protections` = objet libre : `exigences` passe), tests `test_elec_checklist_protections.py:52,127`. Voir OPTIONNEL (aucun écran ne lit `questions`).

### ACAL676 — CORRIGER
Même défaut transversal : la clé `distance_separation_foudre_min_m` n'a pas de ligne `TYPES_CLES`. Reste OK (`protections.py:137`, tests cités existent).
Correction : ajouter « + ligne `TYPES_CLES` (nombre, minimum 0) ».

### ACAL677 — OK
Ouvert : `core/calepinage/geo.py:109` (`aire_anneau_m2`, lacet : le calcul (0,0),(1,0),(2,0),(3,0),(1,5;3) donne 4,5 m² comme annoncé), `services/cables.py:174` (`course_de_chaine`, `point_collecte`), `services/production.py:65` (`numeros_des_modules`), `views/electrique.py:193-198` (`forme_reponse` liste les clés), `services/electrique.py:2269` (`evaluation_electrique`), `tests/test_calx218_motif_parcours.py:167`, `test_elec_bloquants_onduleur.py:171`.

### ACAL678 — CORRIGER (mineur)
- « Preuve en direct / Then » : l'alerte « apparaît dans la liste des alertes du verdict » (étape Électrique). Faux pour `VerdictElectrique.jsx` : il lit `publication.motifs` et `resultat.verdicts` (l.220-241, 280-295), pas `data.alertes` ; les `alertes[]` (chaînes) ne sont affichées que par `plan/AffectationChaines.jsx:303,498` (« Affectation des chaînes »).
- Correction : Preuve : « ouvrir l'onglet Affectation des chaînes : l'alerte est dans sa liste d'alertes (`AffectationChaines.jsx:498`) » ; le reste est conforme (`raccordement.py:780-794` `_reglage` exige la source ; ligne `TYPES_CLES` bien prévue ; 9 clés aujourd'hui).

### ACAL681 — DOUBLON
Prémisse vraie (`p_dc_kw` : aucun écrivain ; `electrique.py:1653`, `etapes/__init__.py:95`), mais ACAL752 (D4, INDEX l.229) fait exactement la même chose (« écrire `p_dc_kw` à l'étape onduleur », lane calepinage/simulation, mêmes fichiers `etapes/onduleur.py`, `test_calx170_onduleur.py`). Correction : fusionner dans ACAL681 (garder la plus ancienne) et supprimer ACAL752 (ou inverse), en reportant `@after ACAL681` sur 738/740.

### ACAL682 — DOUBLON
Doublon d'ACAL736 (D4 : histogramme d'énergie par classe de puissance, `entree.distribution` de l'étape `ecretage`) et paire 683/684 ↔ 736/737 (D4 : même graphe « Panneaux pour l'onduleur », niveau expert). À trancher : garder UNE paire (recommandation : 682-684, contrat propre PACT10, lecture de la série persistée) et supprimer 736/737, ou l'inverse. En plus, correction d'Emplacement : un échantillon sans producteur appelable va dans `SANS_PRODUCTEUR_PUR` (avec sa raison, `test_cal223_contrats.py:84`) + `POSES_AVANT_LEUR_ROUTE` (l.439), pas dans `AVEC_PRODUCTEUR_PUR` (l.63 : exige un producteur comparé) ; « Listes figées : une entrée chacune » dans les TROIS listes est contradictoire (`test_chaque_echantillon_est_declare_ici` l.546 : AVEC ∪ SANS).

### ACAL683 — DOUBLON
Voir ACAL682 (doublon d'ACAL736). Prémisses vérifiées vraies : `views/rattachements.py:169-209` (`MODULES_RATTACHES`), `permissions.py:75` (`PeutVoirCalepinage`), `selectors.py:1230` (`resultat_servi`), `chaine_pertes.py:968-979` (`tronquee`). Si 683 est gardée : l'exemple est incohérent (puissance nominale 5 kW, `p_dc_kw` 6 et 9 kW avec `ecretage_kw` 0 et 1) ; mettre `ecretage_kw` 0, 0, 1, 4 (énergie écrêtée 5) pour que le mutant « classer sur `p_ac_kw` » soit un vrai test.

### ACAL684 — DOUBLON
Doublon d'ACAL737 (D4, même graphe, même carte, même écran). Prémisses vérifiées : `VerdictElectrique.jsx` 421 l., `production/DiagrammePertes.jsx` + `ChartFrame` (l.12,198), `atelier/onglets.js:80`, `api/calepinageApi.golden.json`. Garder l'une des deux (voir ACAL682).

### ACAL685 — CORRIGER (mineur)
« La phrase de l'alerte reste dans la liste des alertes déjà affichée » et Jumeaux « AlertePassable … celle de la boucle y apparaît déjà » sont faux : `AlertePassable` (`VerdictElectrique.jsx:153,220-243`) filtre `resultat.verdicts` (objets `conforme === false`), pas la liste `alertes[]` de `evaluerElectrique`. L'alerte de 678 n'apparaîtra pas dans ce verdict ; la ligne « au-dessus » de 685 la remplace.
Correction : supprimer ces deux affirmations (« l'alerte est dans `Affectation des chaînes` ») ; le reste est conforme.

### ACAL686 — CORRIGER
`blocs_du_schema` (`core/electrique/schema.py:279-304`) ne dessine bien disjoncteur AC / compteur production / TGBT / compteur ONEE que si `QAC1` existe. Mais une assertion existante dit le CONTRAIRE : `tests/test_acal_sld_conception_reelle.py:133-147` (`test_sans_norme_topologie_sans_calibre` : `assertNotIn('disjoncteur_ac', clefs)` et « aucun repère imprimé » sans norme) — décision tenue « aucun organe décidé sans norme ». La tâche ne la cite pas (elle ne nomme que `test_calx235_sld_dxf.py`) et ne dit pas qu'elle l'inverse ; `core/electrique/nomenclature.py` est lu mais absent de `Files:`.
Correction : Assertions existantes : « `test_acal_sld_conception_reelle.py::test_sans_norme_topologie_sans_calibre` est INVERSÉ (disjoncteur_ac, compteur_production, tgbt, reseau présents sans calibre ni repère) » + `Files:` ajoute ce test et `core/electrique/nomenclature.py` ; confirmer avec le fondateur que dessiner un « Disjoncteur AC » sans norme n'est pas « décider un organe ».

### ACAL687 — OK
Ouvert : `electrique.py:2614` (`_motifs_du_raccordement(conception, saisie, reglages)`), `:2645` (`_phases_du_champ`), `raccordement.py:619-647` (`_verdict_regime_phases`), `:435` et `:1311` (`verdicts_raccordement`), `tests/test_acal_raccordement_unique.py:117-175` (la saisie 1 phase l'emporte sur `phases: 3` de l'entrée : reste vert). Détail : `_motifs_du_raccordement` n'a pas `donnees` en paramètre (seul `_rapport_publication` l'a, l.2816) : ajouter le paramètre.

## OPTIONNEL (5 lignes)
- ACAL665 : le test rouge est dans un module `SimpleTestCase`/`_Calepinage` sans base ; le sélecteur `valeurs_attendues_par_chaine(devis_id, company)` exige un devis en base : tester `services/valeurs_attendues.py` pur, et le sélecteur dans un module `BaseApiCalepinage`.
- ACAL675 : aucun écran ni contrat ne lit `questions` ni ne permet de saisir `exigences` (front « hors lot » sans tâche dans l'INDEX) : l'organe ne sera atteignable que par l'API.
- ACAL682 : `pas_classe = puissance nominale ÷ 10` est une convention d'affichage nommée (non technique) ; à confirmer comme tolérée par la règle « aucun chiffre inventé » ou à passer en réglage.
- ACAL672 : l'exemple « Voc à −5 °C : 594 V » vaut 12 × 49,5 V, soit la tension STC : exemple de test à choisir à une vraie valeur à froid.
- Lanes : 672/673 (documents) et 605 (planche) partagent `plan_cablage.py` (fonctions disjointes) ; 674 doit suivre 605 (voir plus haut).

## Non vérifié
Aucune tâche non vérifiée. Non ouverts : les maquettes `docs/audits/l5-calepinage/maquettes/*.dc.html` (clauses d'affichage de 647, 684, 685), et la compatibilité exacte des 27 `Files:` avec `scripts/plan_lanes.py`.
