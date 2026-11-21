# Rapport de vérification — lot AUTRES-PLANS (32 tâches), 21/11/2026

Code lu : `C:\dev\taqinor-os\.claude\worktrees\l5-verif\` (lecture seule). Propriété : `python scripts/check_ownership.py --owner-of <chemin>` lancé sur TOUS les fichiers de `Files:` des 31 tâches de code.

## Propriété des fichiers (point supplémentaire du lot)
Aucun écart. Chaque fichier appartient au propriétaire du plan où la tâche est rangée :
stock (ACAL570, 660, 663, 817 ; migrations stock = « surface append-only »), parametres (571, 669 ; migration parametres idem), web (583, 929, 1026), chantiers (589, 597, 666, 667, 668, 670, 903), devis (core/pompage et ventes/domain : 804, 805, 808, 809, 814, 818, 819, 912, 927), moteur (976 : `ventes/economie.py` -> moteur), lead (838, 904), sav (845), deploy (902, 977).
Seul `docs/audits/acceptation/ACAL/` (ACAL1031) sort « AUCUN », comme tout `docs/audits/acceptation/*` existant : sans objet.

## Transversal : dépendances `@after` manquantes (PACT11 / `after_blocked`)
`scripts/plan_lanes.py` ne lit PAS le texte « ordre : après ACAL… » du Constat (grep « après » : aucune lecture) ; seule la balise `@after:` ordonne, y compris entre plans (docstring l.118-124 : « un @after vers un AUTRE fichier plan est attendu »). L'INDEX confirme `after: -` pour 570, 571, 583, 597, 660, 817 et seulement `ACAL667` pour 589. Corrections listées par tâche ci-dessous.

---

### ACAL570 — CORRIGER (@after seul)
Prémisses vraies : dernière migration `0182_fiche_onduleur_dc_max_et_mppt_15_20kw.py` (`apps/stock/migrations/`), `test_golden_fiche_technique_modele.py::GoldenFicheTechniqueModeleTests::test_aucune_migration_a_creer` existe (l.151/206), `serrage` absent du modèle.
Faux : seule la phrase du Constat porte « après ACAL567 » ; `@after` absent. Une migration `AddField` seule, construite avant ACAL567, fait échouer `makemigrations --check` (champs en base absents du modèle).
Correction : ajouter `(@after: ACAL567)` à la ligne `Files:`.

### ACAL571 — CORRIGER
Faux :
1. « un refus du serveur nommant `serrage_source` s'affiche SOUS LE CHAMP » : `DonneesSection.jsx::FichesTechniques` n'a qu'UN bandeau d'erreur (`error`, `frErr`, `DonneesSection.jsx` ~l.418-440 et `enregistrer` l.~486) ; aucun mécanisme d'erreur par champ : ce n'est pas « ≈ 20 l. ».
2. « niveau expert » : le fichier ne contient aucune notion d'expert (grep `expert` : 0).
3. Jumeaux « aucun autre écran de saisie de la fiche module » : FAUX, `frontend/src/pages/stock/ProduitForm.jsx` (blocs module : `ficheFields.pmax_wc` l.1786, `noct_c` l.1843) et `pvondFicheTechnique.js::CHAMPS_PAR_TYPE.module` (l.~219) saisissent déjà la fiche module (même modèle) ; la tâche doit dire qu'elle n'y ajoute pas la zone (ou l'y ajouter).
4. Le champ texte exige aussi `commencerEdition` (relire `serrage_source`) et `buildPayload` (texte) : seules les listes numériques sont citées.
Correction : remplacer la clause d'erreur par « un refus du serveur nommant `serrage_source` s'affiche dans le bandeau d'erreur existant avec le libellé du champ (« Source de la zone de serrage ») » ; supprimer « niveau expert » ; Emplacement : ajouter « `commencerEdition` et `buildPayload` (champ texte `serrage_source`, envoyé seulement s'il est non vide) » ; Jumeaux : « `ProduitForm.jsx` / `pvondFicheTechnique.js` portent le bloc module de la fiche : la zone de serrage n'y est pas saisie (Paramètres › Fiches techniques seul) » ; ajouter `(@after: ACAL567)`.

### ACAL583 — CORRIGER (@after seul)
Ouvert : `estimatorBrainV2.ts` 2 108 l. (ok), `packConfig` l.1321, `PackOptions` l.798, `PanelGrid` l.944, `packCells` l.1010 (`panelsPerCell`, `colGapM`, `rowPitchM`), 9 sites d'appel confirmés (V2 x4, V6, V7, Commun, `scripts/roofPro11/matrix.ts`, `optimizer.ts`), tests V2/V3..V8/packMixed existent. `roof_layout_v2.schema.json` vit côté `backend/django_core/apps/calepinage/contract_samples/`.
Faux : « ordre : après ACAL581/ACAL582 » seulement en texte ; la clé `zones[].chassis` vient du contrat ACAL581 (PACT10 : contrat d'abord).
Correction : `(@after: ACAL581)`.

### ACAL589 — CORRIGER (@after seul)
Ouvert et confirmé : `field_sync.py::apply_batch` (l.608) ne rejoue que des écritures ; `readCache.js` (`put(type,id,data)`/`get`, cap 30) ; `MaJourneePage.jsx` l.253 `readCache.put('tournee', today, stops)`, `FLOW_TABS` l.571 (11 entrées), `InterventionFlowSheet` l.616 ; `DonneesHorsLigneBanner.jsx` l.26 (texte exact) ; `bloc_calepinage_retenu` l.13 / `plan_pose_url` l.43 ; `tests_aud324_n1_dispatch.py::test_ma_tournee_compte_fixe` l.113 ; `views/installation.py` 1 867 l. ; `getInstallation` `installationsApi.js` l.21 ; `IsAnyRole` importé.
Faux : la tâche consomme `apps.calepinage.selectors.plan_pose_svg_pour_devis` (ACAL588, absent aujourd'hui) mais son `@after` ne vise que ACAL667.
Correction : `(@after: ACAL667, ACAL588)`.

### ACAL597 — CORRIGER (@after seul)
Confirmé : `ensure_checklist_items` l.414 (figée à la première matérialisation l.436-437 ; 6 appelants hors tests), seul créateur `ChantierChecklistItem.objects.create` l.452, `cle` max 40 / `unique_together (installation, cle)`, `_gate_check_checklist` l.2252, `services.py` 8 215 l., tests nommés existent.
Faux : appelle `points_de_controle_pose` (ACAL596) sans `@after`.
Correction : `(@after: ACAL596)`. (Précaution : `libelle` est limité à 120 caractères : tronquer ou refuser les libellés plus longs.)

### ACAL660 — CORRIGER
Faux : la tâche migre HUIT colonnes (six d'ACAL659 + `sous_chaines_par_module` d'ACAL720 + `var_bus_dc_redresse_v` d'ACAL816) mais dit « six » partout. Preuve : ACAL659 Persistance = six colonnes (`cellules_serie`, `temp_coeff_isc_pct_c`, `ond_pnom_reduite_debut_c`, `ond_pnom_pente_pct_c`, `ond_mppt_independants`, `opt_onduleurs_compatibles`) ; ACAL720 et ACAL816 en ajoutent chacune une et renvoient « la migration est ACAL660 ». Un constructeur qui écrit « six `AddField` » laisse deux colonnes sans migration -> `makemigrations --check` rouge.
Correction : remplacer « six colonnes » / « six `AddField` » / « les six champs » / « six colonnes optionnelles » par « huit » (Given, Persistance, Emplacement, Test rouge) et lister les huit noms ; ajouter `(@after: ACAL659, ACAL720, ACAL816)`.
Confirmé par ailleurs : 0182 dernière migration, `test_cal_fiche_bifacial.py::FicheBifacialiteTests` existe.

### ACAL663 — CORRIGER
Faux : « boucle `LIBELLES_FICHE[cle]`, lignes 1947-1992 » ne couvre que les blocs optimiseur/pompe/variateur. Les blocs MODULE et ONDULEUR de `ProduitForm.jsx` sont des `FormField` écrits champ par champ (`ficheFields.pmax_wc` l.1786, `ficheFields.ond_ac_kw` l.1654, `noct_c` l.1843) ; le bloc optimiseur liste ses clés EN DUR dans le JSX (l.1957-1962). Ajouter les clés à `CHAMPS_PAR_TYPE` / `LIBELLES_FICHE` ne fait rien afficher. Autres manques : aucune catégorie « liste » n'existe dans `pvondFicheTechnique.js` (`ficheFieldsVides`, `champsFicheDepuisServeur`, `champsFichePourType` ne connaissent que numérique/booléen/choix/TRI/courbe) pour `opt_onduleurs_compatibles` ; `CHAMPS_TRI_PAR_TYPE` ne contient que `variateur_pompage` (l.~263) et son `<Select>` TRI est écrit seulement dans le bloc variateur (l.2029+). `champsFichePourType` envoie `null` (pas 0, pas « rien ») pour un vide : « aucun champ vide n'est envoyé » est inexact, « jamais 0 » est vrai. `ProduitForm.jsx` fait 2 333 l. (pas 2 315) : « ≤ 15 l. » est irréaliste pour 6 champs + 1 choix + 1 liste.
Correction : réécrire Emplacement : « `pvondFicheTechnique.js` (tables + catégorie `CHAMPS_LISTE_PAR_TYPE` : saisie séparée par virgules, `[]`->null à l'envoi, tableau à la relecture ; `CHAMPS_TRI_PAR_TYPE.onduleur = ['ond_mppt_independants']`) et un composant neuf `frontend/src/pages/stock/FicheChampsElectriques.jsx` (≈ 90 l.) monté UNE fois dans `ProduitForm.jsx` (≤ 8 l. ajoutées) » ; Given : « un champ vide part à `null`, jamais à 0 » ; `Files:` + le composant neuf et son test ; `@after: ACAL659, ACAL660, ACAL817`.

### ACAL666 — OK
`calepinage_retenu.json` : clés `endpoint`, `forme_serveur`, `pourquoi`, `exemple`, `exemple_sans_calepinage` (patron correct) ; `tests_cal245_bloc_calepinage.py` existe ; `scripts/check_api_shapes.py` existe ; `CommissioningIVReading.voc_attendu_v/isc_attendu_a/pmax_attendu_w` (models_chantier.py l.405-409) et `IV_CHAMPS` (ChantierGateTimeline.jsx l.85) confirmés.

### ACAL667 — CORRIGER (@after seul)
Confirmé : `CommissioningRecordViewSet` (views/commissioning.py l.37, `READ_ACTIONS` l.32, `ajouter_iv` l.129), route `recettes-commissioning` (urls.py l.78), `calepinage_retenu_du_chantier` (selectors.py l.36 ; 2 appelants : serializers_blocs.py, services.py).
Faux : lit `apps.calepinage.selectors.valeurs_attendues_par_chaine` (ACAL665) ; `@after` = ACAL666 seul.
Correction : `(@after: ACAL666, ACAL665)`.

### ACAL668 — OK
`RecetteDialog` l.389 appelé une fois (l.954), `IV_CHAMPS` 8 champs, deux tests nommés existent, composant neuf monté dans `ChantierGateTimeline.jsx` (cité dans `Files:`), `@after: ACAL667`.

### ACAL669 — CORRIGER
Confirmé : `recette_ecart_pmax_pct` etc. (`models_company.py` l.303-310, `serializers_company.py` l.426-438, `views_config.py` l.66-67, `tests_validation.py` l.475+), dernière migration `0147_textes_lignes_1711.py`.
Faux : la tâche promet « saisir dans les Paramètres » (Given, Preuve en direct) mais aucun écran n'est dans `Files:`. Les trois réglages de recette existants sont saisis par `frontend/src/pages/parametres/reglagesCi.js` (l.13-15 : liste `{champ, label, aide}`) rendue par `AvanceSection.jsx` (test `AvanceSection.ciq639.test.jsx`). Sans cette entrée le champ n'est saisissable que par l'API. Aussi : `_validate_pct_strict` est un contrôle de POURCENTAGE : l'intervalle ]0 ; 1 000] MΩ exige un validateur propre ; « Contrat partagé : échantillon du module paramètres » ne désigne aucun fichier (aucun `contract_samples` de `parametres` ne contient `recette_`).
Correction : ajouter à `Files:` `frontend/src/pages/parametres/reglagesCi.js` (+ `AvanceSection.ciq639.test.jsx`, cas « champ présent ») et une ligne `{ champ: 'recette_isolement_min_mohm', label: 'Résistance d'isolement minimale à la recette (MΩ)', aide: AIDE_SANS_VERDICT }` ; écrire « Contrat partagé : n/a (aucun échantillon ne couvre ces réglages) » ; nommer le validateur propre (pas `_validate_pct_strict`).

### ACAL670 — CORRIGER (@after seul)
Confirmé : `CommissioningRecordSerializer.validate` (serializers_commissioning.py l.120, `resultat_recette_fiche` appelé en tête), `_reglage_recette` l.3396 / `seuil_ecart_pmax` l.3408 / `compute_iv_ecart` l.3413 / `ESSAIS_RECETTE` l.8009 / `essais_recette` l.8038 (contient `isolement_ok`), tests ciq625/ciq626 existent. Précision à garder : le jugement de `isolement_ok` doit être posé dans `attrs` AVANT l'appel à `resultat_recette_fiche`.
Faux : lit le réglage d'ACAL669 (`getattr(..., None)` renverrait None en silence) sans `@after`.
Correction : `(@after: ACAL669)`.

### ACAL804 — OK
Calcul refait à la main (12 journées moyennes sur `JOURS_PAR_MOIS`, règles de la clause, 5 passes) : 177 jours de manque, 174 pleins, 80,66 % -> 80,7 % ; réservoir 0 : 184 jours, 79,84 % -> 79,8 % : les chiffres de la tâche sont exacts. `couverture_besoin_eau` volumes.py l.37 (2 appelants : `apps/calepinage/views/pompage.py` l.361, `core/pompage/conception.py` l.365), `JOURS_PAR_MOIS` l.34, grep `bilan_reservoir|jours_manque|niveau_reservoir` : 0, `test_agr114_production_mensuelle.py` et `test_besoin_eau.py` existent, 580 l. D-ACAL-41 respectée (interne).

### ACAL805 — OK
`hmt_composantes` (hydraulique.py l.277) rend `valeur_m`, `source` ('calculee'/'saisie'), `manquantes` ; `production_mensuelle` (volumes.py l.423) reçoit `hmt_m` scalaire ; appelants : `apps/calepinage/services/pompage.py:140`, `apps/ventes/domain/pompage.py:1280`, `core/pompage/champ.py:338` ; grep `hmt_mensuelle|hmt_m_mois` : 0 ; `test_agr111`, `test_agr114`, `test_agr125_parite_devis` existent.

### ACAL808 — OK
`composer_kit` (kit.py l.139) : option `sonde_niveau` (l.50) décochée par défaut, `var_protection_marche_a_sec` lu seulement pour le motif (l.242-243), `_alerte` l.63, appels `tailles.py` l.145/196 ; `CODES_NOTES_CLIENT` (agricole/synthese.py l.344) ne contient pas le code -> alerte interne ; `test_agr119_kit_options.py` classe `Options` l.146 et test `test_sonde_marche_a_sec_publiee_par_le_variateur` l.195 ; `test_agr121_etude_pompage_preview.py` l.162 exige bien `{code, champ, message}`.

### ACAL809 — OK
`_chaines_pour` (champ.py l.384) mêle fenêtre (`fenetre_admissible`, core/electrique/chaines.py l.318) et adaptation du champ ; `_temperatures` l.372, `spec_module` l.295, `fiche_saisie` l.102 ; fichier 709 l. ; fixtures `PANNEAU` 710 Wc / `FICHE_250_780` existent (test_agr115_champ_chaines.py l.26/30). Recalcul : Voc froid ≈ 52,2 V -> max 15 modules (800 V), Vmp chaud ≈ 35,1 V -> min 8 : 12 conforme, 21 hors fenêtre, cohérent avec « 8 à 15 ». Appelants `apps/ventes/domain/pompage.py:1291` et `champ.py:667` exacts.

### ACAL814 — OK
`conception` (conception.py l.203, 555 l.), `heures_pic` l.61, seul appelant `apps/ventes/domain/pompage.py` (`_conception` l.803-810) ; test `test_agr116_conception.py` existe ; chiffres vérifiés : 12 ÷ 2 h = 6,0 m³/h, 12 ÷ 5 h = 2,4 m³/h, mois critique juillet. `@after: ACAL804` présent.

### ACAL817 — CORRIGER (@after seul)
Confirmé : `_FICHE_VARIATEUR_CHAMPS` (stock/selectors.py l.3167) / `_fiche_pompage_dict` l.3257 ; `produit_pompage.json` (blocs `variateur_pompage` l.~102/117/196) ; `catalogue.js::CHAMPS_FICHE_VARIATEUR` l.381 ; `LIBELLES_FICHE`/`CHAMPS_PAR_TYPE.variateur_pompage` (pvondFicheTechnique.js l.260/549) ; le bloc variateur de `ProduitForm.jsx` (l.2005-2010) liste ses clés en dur : « +1 clé du bloc variateur » est exact ; trois tests existent.
Faux : le champ modèle vient d'ACAL816 (autre plan) sans `@after`.
Correction : `(@after: ACAL816)`.

### ACAL818 — CORRIGER (@after seul)
Confirmé : grep `appoint|hybride|secteur|plusieurs pompes` dans `core/pompage` : 0 ; `fenetre_admissible` seule source de tension ; calcul refait : Vmp chaud unitaire ≈ 35,1 V -> 12 x = 421 V (>= 400), 11 x = 386 V (< 400) : exact.
Faux : lit `var_bus_dc_redresse_v` servi par ACAL817 (et créé par ACAL816) ; `@after` = ACAL809 seul.
Correction : `(@after: ACAL809, ACAL817)`.

### ACAL819 — OK
`conception.py` 555 l., `choisir_variateur` appelé par `conception.py` et `tailles.py` (l.181) ; `variateur["pompe_kw"]` (chaîne) existe dans les fixtures ; 4 x 1,1 = 4,4 kW <= 5,5 et 6 x 1,1 = 6,6 > 5,5 : exact ; `@after: ACAL814`.

### ACAL838 — CORRIGER
Confirmé : `capture_ocr_enabled` (intake_photo.py l.41, drapeau `CRM_CAPTURE_OCR_ENABLED` base.py l.1805 éteint), `_fastapi_ocr_url` l.49, `_service_token_for` l.57, `_run_capture_ocr` l.193 (écrit le lead), `_extract_conso_kwh` l.249 (0 < kWh < 1 000 000), `CaptureOcrTests`/`ExtractionHelpersTests` existent, `intake_photo.py` listé dans `tests_alea_garde_chatter_complet.py` l.74, garde-fous FastAPI (10 Mo, 20/h, octets magiques) exacts.
Faux : « `mois` vaut `donnees_structurees.mois` (entier 1 à 12) si l'OCR le donne » : le prompt OCR (`backend/fastapi_ia/app/services/ocr_service.py::_EXTRACT_PROMPT` l.27-55) ne demande AUCUNE clé `mois` ni `conso_kwh` (clés : numero, date, fournisseur, client, ice, date_echeance, montant_*, taux_tva, conditions_paiement, iban, lignes) : `mois` serait toujours null, et le kWh sort du premier motif « N kWh » du texte brut (l.262-271) d'une facture que le prompt traite comme une facture fournisseur.
Correction : remplacer par « `mois` vaut toujours null (aucune clé `mois` dans la sortie de l'OCR, `ocr_service.py::_EXTRACT_PROMPT`) : l'utilisateur choisit le mois ; le kWh est une proposition à confirmer, tirée du texte brut par `_extract_conso_kwh` ».

### ACAL845 — OK
`ReleveCompteurEquipement` (sav/models.py l.581, `Type.M3` l.595, `valeur`, `date`, `equipement`, `company`), `usage_m3_periode` selectors.py l.1945 (1 appelant `services.py:788`), `releves_portail` l.2081 (appelant `portail/views_client.py:1389`), `moyenne_jour_depuis_precedent` l.1981, `TYPES_RELEVE_PORTAIL_PAR_ROLE` l.2008, `selectors.py` 2 125 l., `Equipement.installation_id` utilisé l.1964, `installation_for_devis(devis, company)` accepte un id de devis (filtre FK), `tests_agr615_releves_m3.py::UsageM3Tests` l.66 et `test_agr617_releves_portail.py` existent. Exemple 450 / 450 / None cohérent avec la règle.

### ACAL902 — OK
`LexiquePage.jsx::TERMES` (l.20) porte HMT, MPPT, P50/P75/P90, PR, Écrêtage ; Voc/Vmp/Isc/DC-AC absents (grep : seules l.8 et l.81 contiennent « voc » via « vocabulaire ») ; trié alphabétiquement ; le test (`LexiquePage.test.jsx` l.19) exige >= 15 entrées : aucun compte figé.

### ACAL903 — CORRIGER
Confirmé : `plan_pose_url` = `/ventes/devis/<id>/3d` (calepinage_retenu.py l.43) ; deux tests figent ce littéral (`tests_cal209...` l.149, `tests_cal245...` l.93) ; l'entrée `plan_pose_pdf` / `plan-pose.pdf/` existe (calepinage/views/sorties.py l.139-140).
Faux : `CalepinageRetenuCard.jsx` ouvre `plan_pose_url` par `navigate(planPoseUrl)` (l.69), c.-à-d. le ROUTEUR du site ; une route d'API `/api/django/calepinage/calepinages/<id>/plan-pose.pdf/` n'est pas une page, et ouverte dans un onglet elle part sans l'en-tête JWT. Le panneau Documents télécharge ses PDF par client HTTP en blob (`PanneauDocuments.jsx` l.95 `responseType: 'blob'`, l.680-681 `createObjectURL` + `window.open`). « Le lien l'ouvre » n'est donc pas obtenu par un changement de valeur + « libellés ».
Correction : Given/Emplacement : garder `plan_pose_url` (page 3D) sous le libellé « Plan 3D » et AJOUTER une clé `plan_pose_pdf_url` (chemin d'API) au bloc, à l'échantillon `calepinage_retenu.json` et aux deux tests ; `CalepinageRetenuCard.jsx` : bouton « Plan de pose (PDF) » qui télécharge en blob avec le client API puis ouvre l'objet (patron de `PanneauDocuments.jsx`) ; réaligner `CalepinageRetenuCard.test.jsx` ; ajouter ce test et `frontend/src/api/installationsApi.js` (ou client calepinage) à `Files:`.

### ACAL904 — OK
`IdentityRail.jsx` : menu « ⋯ » avec `onAction('toiture-3d')` (l.808) et `ouvrirModuleCalepinage` (l.194-218 ; « Ouvrir dans le module Calepinage ») ; `LeadWorkspace.jsx` l.399-431 : `ouvrirConceptionToiture` appelle `ventesApi.creerDevisAuto({ lead })` et affiche l'erreur « Impossible de créer un devis… » quand il échoue : prémisse exacte ; tests `IdentityRail.test.jsx` l.168 et l.739 attendent bien l'entrée « Concevoir la toiture » (à réaligner, dit). Aucun doublon dans l'INDEX.

### ACAL912 — CORRIGER
Confirmé : `ecrire_etude_params` (pipeline.py l.588, appelé une fois l.1011), `lire_layout` (geometrie.py l.628), `pans_du_document` l.445, `poseSurfaces`, `cles_etude_du_layout` (etude_schema.py l.480) qui écrit `production_annuelle` depuis `resultat['annualKwh']` ; `test_pipeline_residentiel_ecrit_comme_avant` l.158.
Faux : « `cles_etude_du_layout` <- `ecrire_etude_params` seul » : second appelant `backend/django_core/apps/ventes/domain/resynchronisation.py:1108-1109` (`etude.update(cles_etude_du_layout(..., result))`). La Persistance de la tâche vise justement les devis « resynchronisés après le merge » : avec la seule modification de `pipeline.py`, la resynchronisation réécrit 40 424 (et `etude.update` ne retire de toute façon aucune clé).
Correction : `Files:` + `backend/django_core/apps/ventes/domain/etude_schema.py` et `backend/django_core/apps/ventes/domain/resynchronisation.py` ; poser la règle dans `cles_etude_du_layout(mode, resultat, layout=None)` (qui rend `{'production_annuelle': None, 'production_source': None, 'economies_annuelles': None}` quand un pan non `toit` à modules > 0 existe), laisser l'écrivain unique retirer les clés `None` côté pipeline et faire `etude.pop` côté resynchronisation ; corriger la ligne Appelants (2 sites) ; ajouter un cas au test de resynchronisation existant.

### ACAL927 — CORRIGER
Confirmé : `quantites_derivees_du_compte` (composition.py l.351 : `{'structure': nb, 'socle': 2 nb}` sans condition), 2 sites d'appel (`composition_residentielle.py:1095`, `pipeline.py:575`) + test, `CLASSES_KIT_COMPLETABLES` l.697, `Devis.regles_calcul` défaut 14 (models.py l.225), dernière migration `0159_regles_calcul_niveau_14.py`, `regles_calcul_ecarts_dryrun` existe.
Faux (contradiction / doublon avec ACAL998, lot D8) : ACAL998 « Déclarer le niveau de règles 15 (`REGLES_POSE_REELLE_2111`) qui porte, pour TOUTE la vague, la production de la pose réelle (D-ACAL-36) ET la fixation des toits affleurants (D-ACAL-39), sans le rendre courant » (activation = ACAL1001 GATED) et nomme explicitement ACAL927 dans son Constat (« chacun aurait posé son niveau »). ACAL927 pose pourtant SON niveau (« niveau de règles suivant », `REGLES_COURANTES`, défaut de `Devis.regles_calcul`, migration, liste de `test_regles_calcul_nouveaux_rendus.py`) : deux niveaux 15, deux migrations, et un défaut courant qui contourne le verrou ACAL1001. Conséquence de « devis neuf aux règles courantes » : tant que 15 n'est pas courant la clause « fini quand » ne s'observe sur aucun devis neuf.
Correction : réécrire Persistance : « aucune constante, aucune migration, aucun défaut : le comportement est conditionné par `regles_au_moins(devis, 15)` (ACAL998) » ; Given : « Given un devis de niveau 15 (posé par le test) dont… » ; `Files:` retirer `regles_calcul.py`, `models.py`, `migrations/NNNN_…`, `test_regles_calcul_nouveaux_rendus.py` et la ligne « niveau de règles » de l'Emplacement ; type SCHEMA -> ROUTINE ; ajouter `(@after: ACAL998, ACAL1029)`.

### ACAL929 — OK
`departageBase` (estimatorBrainCommun.ts l.94, 174 l.), 4 appelants (V3 l.190, V4 l.150, V6 l.622, V7 l.195), aucun test ne l'appelle seule (grep `apps/web/tests` : 0), `estimatorBrainCommun.ts` -> web ; arithmétique F1-023 : 673 kWh / 8 modules = 84 < 47 002 / 48 = 979 : 48 modules gagne ; aucune constante.

### ACAL976 — OK (réserve)
`_donnees_du_devis` (economie.py l.1522), `build_quote_data` rend `conso_annuelle_kwh` (builder.py l.1684, None sans consommation) et `savings_model` (l.1689), `economie.py` 1 607 l., `ContratTest` (test_calx288 l.134). Réserve de construction : la fixture `DONNEES_REFERENCE` (test_calx288_api_economie.py l.35-43) NE contient NI `conso_annuelle_kwh` NI `savings_model` : la garde doit exiger `savings_model == 'estimation'` ET `conso_annuelle_kwh is None` explicitement (clé absente ≠ estimation), sinon les cas « Contrat » de référence deviennent rouges. Conforme D-ACAL-40 (écran/onglet).

### ACAL977 — OK
`.header-menu-btn` `color: #0f172a` (12-progression-mobile.css l.41), aucune règle sombre ailleurs (grep : 3 fichiers JSX/CSS seulement), `--foreground` redéfini sous `.dark` (design/tokens.css l.494), `Header.jsx` l.122, `mobile-foundation.test.mjs` existe.

### ACAL1026 — CORRIGER
Confirmé : `viewerFullBoot.ts::bootViewerFull` l.124, soleil figé (`sunHour: DEFAULT_SUN_HOUR`, `sunDay: WINTER_SOLSTICE_DAY` l.182-183), page `[...token].astro` : `#roof3d` l.3235, `#roof3d-stage` l.3239, `bootViewerFull(...)` l.9044, mécanisme `data-fr/en/ar` présent ; tests `roofImageWJ118.test.ts` (`lirePageProposition`) et `propositionViewerKeyboardWJ90.test.ts` existent ; D-ACAL-38 a est enregistrée dans `docs/audits/decisions.yml` l.1549.
Faux : (1) la tâche dépend d'ACAL487, qui est toujours `[ ]` et marqué « [GATED : autre propriétaire … moitié calepinage seule] » (docs/plans/PLAN_AUDIT_CALEPINAGE.md l.899) : aucun `@after` ni levée du GATED ; elle ne peut pas appeler `soleilPublic.ts` (absent). (2) La page fait 11 469 lignes, pas « 9 000 ».
Correction : `(@after: ACAL487)` et, dans le message d'orchestration, lever le GATED d'ACAL487 au vu de D-ACAL-38 a (sinon ACAL1026 reste bloquée) ; corriger « 9 000 » en « 11 469 ».

### ACAL1031 — OK
Liste d'ids parsée (plages `ACAL492-521`… dépliées) : 471 ids, AUCUN absent de `INDEX.md` (472 lignes d'index = 471 + ACAL1031 elle-même). Les 31 tâches de code de ce lot figurent toutes dans la clause « moitiés routées ». Tâche d'orchestrateur, pas de code.

---

## OPTIONNEL (5 lignes)
- ACAL927 : le catalogue n'a aucun produit « kit de fixation » (`seed_catalogue`) : tant qu'il n'est pas créé et tarifé (geste d'équipe), un devis affleurant de niveau 15 perd structures et socles SANS ligne de remplacement (seul l'avertissement français le dit) ; à rappeler au moment d'activer ACAL1001.
- ACAL976 : « le PDF client n'imprime aucune économie ici » repose sur un rejeu ; D-ACAL-40 veut aussi « ni imprimés » : non vérifié que le PDF premium ne lit jamais `eco_*` sans consommation (`etude_restitution.py`).
- ACAL904 : renommer « Concevoir la toiture (3D) » en « Devis auto » est trompeur : avec un devis concevable existant le geste ouvre simplement `/ventes/devis/<id>/design` ; préférer « Ouvrir le design du devis ».
- ACAL583 : « le fichier fait 2 108 l. : il ne grossit pas » mais la tâche y ajoute ≤ 12 l. : dire « ≤ 12 l. nettes (appel seul) ».
- Plusieurs Constats répètent « Given Given » (ACAL589, 597) : coquille.
