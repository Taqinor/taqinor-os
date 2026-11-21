# Rapport de vérification — lot D4-b (28 tâches, ACAL720 à ACAL748 sans ACAL739)

Code lu : `C:\dev\taqinor-os\.claude\worktrees\l5-verif\` (lecture seule). Chemins ci-dessous relatifs à ce dossier.
Abréviations : B = `backend/django_core/apps`, C = `backend/django_core/apps/calepinage`, F = `frontend/src/features/calepinage`, W = `apps/web/src/scripts/roofPro11`.

### ACAL720 — CORRIGER
Prémisse vraie : aucun `diode|sous_chaine` dans `B/stock` (hors goldens/migrations), `tolerance_pmax_max_pct` en `B/stock/models_fiche_technique.py:316`, `serializers_fiche_technique.py:206`, `selectors_fiche_technique.py:126`, trois goldens + `test_cal_fiche_bifacial.py` existent, tête de migration 0182.
Faux/incomplet (point 8) : un champ de modèle sans migration dans `Files:`, et la migration est portée par ACAL660 (PLAN_AUDIT_STOCK), qui n'a AUCUN `@after` (index : `after: -`, l'ordre n'est qu'écrit dans son Constat) alors qu'elle doit venir APRÈS ACAL659, ACAL720 et ACAL816. ACAL720 n'a pas non plus `@after: ACAL659` alors qu'ils régénèrent les mêmes trois goldens et le même `Meta.fields`. Le « fini quand » + la preuve « `makemigrations --check` vert » ne sont pas observables dans ACAL720 seule.
Correction : ajouter `@after: ACAL659` à ACAL720 ; ajouter `@after: ACAL659, ACAL720, ACAL816` à ACAL660 ; dans ACAL720, remplacer la Preuve par « n/a ici — `makemigrations --check` est la preuve d'ACAL660, même merge ».

### ACAL721 — OK
Ouvert : `apps/web/src/lib/shadingEngine.ts:370` (`pointSolarAccess`), `:421` (`cellsSolarAccess`), les 3 occurrences « bandeau » seules (601, 615, 651) ; `W/prefill.ts:264-305` (`SerializedSolarAccess` sans `bandes`, `serializeSolarAccess` ne recopie que values/method/assumptions/computedAt, donc le champ `bandes?` est bien à ajouter) ; `deserializeSolarAccess` repasse par `serializeSolarAccess` (aller-retour couvert) ; `roof-tool-pro11.ts:4043` (`activeSolarAccessMeta` n'écrit que `values`) ; `apps/web/src/lib/roofPro2.ts:22` (`PANEL2_LONG_M` — le fichier est `lib/roofPro2.ts`, pas `scripts/`). Tests nommés existent.

### ACAL722 — CORRIGER
Calcul de l'exemple vérifié à la main (linéaire 1,8333 ; retenues 5/3 ; série 1,0 ; excédent 9,0909 % ; `[1;1;0,9]` ⇒ 0) : juste. `chaine_pertes.py` (`ORDRE_ETAPES` l.103-135 : `diodes` entre `mismatch_ombrage` et `ohmique_dc`, `EXCLUSIVITES` l.290, prédicat vrai ⇒ étape omise avec le motif, comptage `motif == exclusivite[1]` l.1458-1460) confirme le mécanisme « omise non comptée ».
Faux : « `TOUJOURS_OMISES` (3 → 2 entrées) » — `chaine_pertes.py:312-322` n'en a que 2 (`spectral`, `diodes`) ; `neige` est dans `OMISES_NON_COMPTEES` (l.327). Ce sera 2 → 1. Aussi : « 2 514 l. » est 2 534 (anodin).
Correction : « `TOUJOURS_OMISES` (2 → 1 entrée : `spectral` seul) ». Ajouter en Assertions existantes que `test_calx148_ordre.py:174-178` (`TOUJOURS_OMISES[nom]` pour `('spectral','diodes')`) lèverait KeyError : la boucle de la ligne 174 est à réduire à `('spectral',)`, pas seulement la ligne 169.

### ACAL723 — CORRIGER
Prémisse vraie : `fiche_optimiseur` posé à `simulation.py:649` (la tâche dit l.646), `opt_rendement_pct` (`models_fiche_technique.py:653`) publié en `rendement_pct` (`selectors_fiche_technique.py:234`), seul lecteur de `fiche_optimiseur` = `mismatch_ombrage.py:436`. Valeurs 0,20 % et 0,1111 % justes.
Faux : « `len(ORDRE_ETAPES) == 24` » et « `ORDRE_ETAPES` (24 → 25) » : `ORDRE_ETAPES` compte DÉJÀ 25 étapes (`chaine_pertes.py:103-135`) et `test_calx148_ordre.py:40` pose `assertEqual(len(ORDRE_ETAPES), 25)` (test nommé `test_vingt_cinq_etapes_sans_doublon`).
Correction : remplacer partout « 24 » par « 25 » et « 24 → 25 » par « 25 → 26 » ; renommer le test (ou réaligner `test_vingt_cinq_etapes_sans_doublon`) ; `@after: ACAL722, ACAL644` (voir ACAL733).

### ACAL724 — CORRIGER (dépendance)
Prémisse vraie : `mismatch_ombrage.py:412-431` (`_chaines_sans_contrainte` exempte la chaîne dès qu'UNE ligne porte l'un des 4 `CHAMPS_SANS_CONTRAINTE`, l.101), `_mesurer_chaine` l.266, `_publier_chaine` l.303 ; calculs 40 % et 8,70 % vérifiés (1,5/2,5 ; 2,1 contre 2,3).
Problème : ACAL644 (D3, index l.133) fait « fini quand une chaîne dont deux modules portent un optimiseur sort comme exemptée » = le comportement par chaîne que ACAL724 remplace par « exemptée seulement si TOUS les modules sont équipés ». Les deux tâches se contredisent si 724 passe avant, et 724 n'a pas `@after` sur le producteur.
Correction : `@after: ACAL711, ACAL713, ACAL644` (ACAL733 supprimée, voir ci-dessous) ; et ACAL644 ne doit plus promettre l'exemption de la chaîne (voir ACAL733).

### ACAL725 — CORRIGER (dépendance)
Prémisse vraie : `F/plan/AffectationChaines.jsx` 609 l., `manuellesDuServeur` l.15, `tableAffichee` l.30, `lignesProposees` l.148, « Relancer » envoie `affectation_manuelle: []` (l.259-265), aucun `optimiseur` dans `plan/` ; `exempleContrat` existe (`frontend/src/test/fixtures/contractSamples.js:63`) ; onglet `affectation` déclaré `atelier/onglets.js:54`.
Correction : remplacer `@after: ACAL733` par `@after: ACAL644` et la clause Contrat partagé « variante `exemple_affectation_optimiseur`, ACAL733 » par « (ACAL644) ». Chevauchement à connaître : ACAL647 (D3) pose aussi `optimiseur` depuis ce même composant (bouton « Les équiper ») — comportements distincts, même fichier, même lane : à enchaîner, pas à fusionner.

### ACAL726 — OK
Ouvert : `F/documents/deposerImage.js:62-70` (`deposerCarteDeChaleur` → `rendreImageHd` → `renderImageHd(2)`), `F/rendreImageHd.js:6-13`, `roof-tool-pro11.ts:4355` (`renderImageHd: scene3d.renderOffscreen`), `W/types.ts:205` (`RoofToolApi`), `W/shadingUi.ts:70,85-87` (`applyHeatmap`, `refreshHeatmap`) ; `C/services/rapport_ombrage.py:374` imprime la dernière image déposée. Appelant unique `PanneauDocuments.jsx`. Option : le cas « sans ombre » de `PanneauDocuments.test.jsx` mocke `deposerCarteDeChaleur` ; il faudra mocker `builderApi.renderCarteAccesHd` plutôt (OPTIONNEL).

### ACAL727 — CORRIGER
Prémisse vraie : `C/services/rapport_ombrage.py:357-361,374-409` (`MOTIF_CARTE_ABSENTE`, `LEGENDE_CARTE`, `html_carte_de_chaleur`), appelants `rapport_ombrage.py:469` et `services/rapport/ombrage.py:256` (la tâche dit l.160) ; `shadingEngine.ts:726-733` (`solarAccessColorRGB` : (1,0,0), (1,1,0) à 0,5, (0,1,0)) ; alias `@rooflib` existe (`frontend/vite.config.js:246`).
Faux : le nouvel échantillon `contract_samples/legende_acces_solaire.json` avec « `endpoint` null » casse `C/tests/test_cal223_contrats.py:538-544` (`test_chaque_echantillon_est_complet` exige `endpoint`, `pourquoi`, `exemple` et fait `donnees['endpoint'].strip()` ⇒ AttributeError sur null) et `:546-556` (`test_chaque_echantillon_est_declare_ici` exige que le fichier soit déclaré dans `AVEC_PRODUCTEUR_PUR`/`SANS_PRODUCTEUR_PUR`). `test_cal223_contrats.py` n'est pas dans `Files:`.
Correction : donner au JSON `endpoint` (chaîne non vide, ex. « n/a — rendu serveur du rapport d'ombrage, aucune route »), `pourquoi`, `exemple: {stops: […]}` ; ajouter `C/tests/test_cal223_contrats.py` à `Files:` (déclarer le fichier dans `SANS_PRODUCTEUR_PUR` avec sa raison). Alternative : ranger les stops hors de `contract_samples/` (dossier `tests/`).

### ACAL728 — CORRIGER
Prémisse partiellement fausse : « l'accès d'un pan non actif est celui ENREGISTRÉ au document (`geometrieEnregistree.solarAccess.values`) » n'est vrai que pour un pan relu du document et jamais activé. `roof-tool-pro11.ts:2544-2549` (`capturerGeometrieActive`) capture un pan qu'on quitte par `geometrieZoneActive(ctx)` SANS `meta` (`W/prefill.ts:1575-1577`), or `solarAccess` n'est ajouté à une zone que par `meta.solarAccessByZone` (`prefill.ts:1075-1076`) : la géométrie capturée n'a donc pas de `solarAccess`, et `prefill.ts:1004-1008` réémet verbatim cette géométrie. Tout pan visité puis quitté dans la session sortirait « non calculé » dans le tri (et perd aussi son accès à l'enregistrement).
Correction : ajouter à la tâche (et à `Files:`, `roof-tool-pro11.ts`) « `capturerGeometrieActive` passe `activeSolarAccessMeta()` à `geometrieZoneActive` pour que la géométrie capturée porte son accès », avec un cas de test « pan quitté puis trié : sa valeur est conservée » ; sinon retirer « celui ENREGISTRÉ » et dire que l'accès d'un pan visité est « non calculé ». Le reste est vrai (`zones.ts:424` `renderAreasPanel`, liste `rp9-areas-list`, aucun tri).

### ACAL729 — OK
Ouvert : `W/shadingUi.ts:1000-1013` (`moduleShadeTooltip`, phrase « non renseigné — aucune obstruction n'a été saisie » présente), `W/scene3d.ts:1050-1075` (`AffectationColoring` sans libellé par module, `buildAffectationColoring`), `:1115` (`identifiantsModulesParCellule`), `roof-tool-pro11.ts:1616` (la tâche dit l.1582). Aucun chiffre inventé.

### ACAL730 — CORRIGER
Prémisse vraie : `C/services/site.py:459,485` (`fuseau_du_site`, `decalage_utc_minutes`), `C/selectors.py:865` (`contexte_geographique`), `C/views/export_csv.py:112-114` (modèle d'action, `PeutVoirCalepinage`), `views/rattachements.py` (tuple `MODULES_RATTACHES`, « ligne d'import » = en réalité un nom ajouté au tuple, l.≈20).
Faux : les cas HTTP 200/400/409/**404 « autre société »** sont posés dans `C/tests/test_calx146_soleil.py`, dont tous les tests sont `SimpleTestCase`/`unittest` et dont l'en-tête (« AUCUN RÉSEAU, AUCUNE BASE … donc hors du gate migrations ») interdit la base ; un 404 inter-société exige des données (`BaseApiCalepinage`, cf. `tests/test_api_liste.py`).
Correction : mettre les cas HTTP dans un module à base existant (ex. `test_cal223_contrats.py` n'a pas de client ; prendre `tests/test_api_liste.py`-famille ou un « Nouveau fichier car : cas HTTP avec base ») ; garder dans `test_calx146_soleil.py` seulement un cas sans base (`correspondance_du_jour` sur un double). « une ligne d'import » → « un nom ajouté en fin de `MODULES_RATTACHES` ».

### ACAL731 — CORRIGER
Prémisse vraie : `C/services/modules_stock.py:112-137` (`_entree_module`, clés listées), `ombrage_chaines.py:59` (`acces_par_module` ne lit que `values`), `roof_layout_v2.schema.json:1025` (`moduleDocument`) et `:1214` (`solarAccess`, `additionalProperties: true`), `test_calx109_modules_disponibles.py`, `test_acal_empreinte_document.py`, `test_prod2_ombrage_chaines.py` existent ; l'empreinte ignore seulement `computedAt` (`services/layout.py:57`).
Faux 1 : « `test_acal_schema_dossier.py` » comme garde du contrat du schéma (Assertions existantes + Contrat partagé + `Files:` non, mais cité deux fois) : ce fichier teste `DossierReglementaire.genere_empreinte` (lignes 1-4, 12-30), rien du document `roof_layout`.
Faux 2 : « une liste de bandes de longueur différente de celle de `values` … est refusée EN BLOC par le schéma » : JSON Schema ne peut pas comparer la longueur de deux tableaux frères ; rien dans le dépôt ne valide l'égalité `values`/`panels` côté serveur non plus (`acces_par_module` ne vérifie aucune longueur).
Correction : le schéma ne porte que `bandes` = tableau de (tableau de 2 à N nombres dans [0 ; 1], ou `null`) ; `acces_par_bande(layout)` rend `None` pour un pan dont `len(bandes) != len(values)` ou dont une valeur sort de [0 ; 1] (refus en bloc par le CODE, avec test) ; remplacer `test_acal_schema_dossier.py` par `test_acal_acces_module_document.py` (déjà dans `Files:`).

### ACAL732 — OK
Ouvert : `C/services/documents/__init__.py:131-137` (`MANQUE_SOLAR_ACCESS`, `ou_saisir` « Calculer l'ombrage dans l'atelier 3D … », `onglet: None`), `calepinage_documents.json:63` (même phrase), seules 2 occurrences dans le dépôt (aucune dans `frontend/src` ni `apps/web/src`), `test_calx321…::test_rapport_ombrage_nomme_l_acces_solaire_manquant` (l.217) existe, `activeSolarAccessMeta` → `solarAccessAnnuel` rend `null` sans source (`roof-tool-pro11.ts:4043-4055`). Option : l'accès se calcule aussi avec un horizon saisi sans obstacle (CAL97) ; la phrase ne le dit pas (OPTIONNEL).

### ACAL733 — DOUBLON
Doublon de **ACAL644** (D3, index l.133, `lane: calepinage/electrique`) : même clé `optimiseur` booléenne par ligne d'affectation imposée, mêmes fichiers (`chaines.py::CLES_IMPOSEE`, `normaliser_affectation_imposee`, `_appliquer_imposee`, `test_cal234_affectation_manuelle.py`, `calepinage_entree_electrique.json`), même nombre de lignes. Prémisse de 733 vraie (`chaines.py:1374` `CLES_IMPOSEE` à 4 clés, `:1405-1410` refus « Clé inconnue », `:1117-1129` `_appliquer_imposee` ne recopie pas) mais à ne construire qu'une fois ; deux lanes différentes (`electrique` et `simulation`) l'écriraient en parallèle ⇒ collision garantie sur `chaines.py`.
Correction : supprimer ACAL733 ; verser dans ACAL644 ses apports (refus de `« oui »` en 400 nommant module et champ, variante de contrat `exemple_affectation_optimiseur`, mutant « écrire `optimiseur: None` ») ; réécrire le « fini quand » de 644 en « la clé est acceptée, conservée et servie » (l'exemption de chaîne est redéfinie par ACAL724) ; remplacer `@after: ACAL733` par `@after: ACAL644` dans ACAL723, ACAL724, ACAL725.

### ACAL734 — OK
Ouvert : `C/services/etapes/mppt.py:166-220` (`_examiner`, `heures_sous_demarrage` l.172/191-192/214, aucune énergie), docstring l.45-46 (« informe sans commander le retrait »), `tests/test_calx171_mppt.py:77,83` (noms exacts), série de test l.21-31 : T=70/72 °C ⇒ 328 / 324,8 V sous 340 V ⇒ 2 heures, énergie 2,0 ; fenêtre étroite 350-430 ⇒ déjà retirée 2,0 ; grep `heures_sous_demarrage` = `mppt.py` + ce test seuls.

### ACAL735 — CORRIGER
Faux : « aucun composant ne lit l'`entree` d'étape (grep `entree` dans `production/DiagrammePertes*.js*` : 0) ». `F/production/DiagrammePertes.helpers.js:58` fait `entree: etape.entree ?? null` et `F/production/CascadePertesLignes.jsx:25` (créé par ACAL444) affiche `['Entrée', ligne.entree || '—']`. Or l'échantillon de contrat porte `entree` en CHAÎNE (`"seriescalc"`) alors que le serveur publie `entree` en DICTIONNAIRE pour toute étape appliquée (`C/services/etapes/__init__.py:237-250`, ex. `mppt.py:161-163`, `ecretage.py:144-157`) : rendre ce dictionnaire comme enfant React lève « Objects are not valid as a React child » dès que l'onglet Pertes affiche une vraie cascade. La tâche doit corriger ce point, sinon elle se construit sur un détail déjà cassé.
Correction : remplacer la clause Constat par « `Detail` (`CascadePertesLignes.jsx:20-43`) affiche `ligne.entree` tel quel ; c'est une chaîne dans l'échantillon mais un objet en production » ; ajouter au « fini quand » : « `Detail` n'affiche `Entrée` que si `entree` est une chaîne, et lit les clés `heures_sous_demarrage`, `energie_sous_demarrage_kwh`, `energie_sous_demarrage_deja_retiree_kwh` de l'objet pour l'étape `mppt` » ; test rouge : un cas avec `entree` objet qui ne plante pas.

### ACAL736 — OK
Ouvert : `C/services/etapes/ecretage.py:97-158` (`puissances_kw` avant plafonnement, `borne_kw`, `ecretage_pct`, `heures_ecretees`, aucun histogramme), `services/electrique.py:3979-4001` (`ecretage_depuis_serie`, ignore les puissances ≤ 0), `distribution.py` absent, `test_calx172_ecretage.py` (classes `BorneDEcretageTest`, `ProprieteMonotoneTest` l.85,132). Calcul de l'exemple juste (total 23,1 ; écrêté 0,2 + 2,0 = 2,2 ; 9,524 %). OPTIONNEL : la largeur de classe « 1/20 de la borne » est une règle de présentation, à garder nommée en constante avec sa source.

### ACAL737 — OK
Ouvert : `F/electrique/VerdictElectrique.jsx` (421 l., `calepinages.resultat` l.211), onglet `verdict-electrique` (`atelier/onglets.js:80`), `atelier/modeExpert.js`, `ui/charts/ChartFrame.jsx`, aucun `ecretage` dans `F` ; ACAL394/395 cochées au plan.

### ACAL738 — OK
Ouvert : `F/production/TapisHoraire.jsx` (468 l., `journeesTypes` l.160, `LineChart`/`Line` l.409-439), `serieHoraire.js` (créé par ACAL446, ne lit pas `p_dc_kw` ⇒ ajout justifié), `C/services/export_csv.py:269` (`p_dc_kw` dans `COLONNES_HORAIRE`), `calepinage_serie_horaire.json:23`, `@after: ACAL752` (P_DC vide) cohérent.

### ACAL740 — OK
Ouvert : `C/services/etapes/ecretage.py:163-183` (`_borne_kw` constante), `t2m_c` conservé dans les points (`simulation.py:866-883`), champs `pnom_reduite_debut_c`/`pnom_pente_pct_c` introduits par ACAL659 (`@after: ACAL659` présent). Exemple recalculé : 5 ; 5 ; 4,5 ; 4,0 ⇒ écrêté 1,0 ; 1,0 ; 1,5 ; 2,0 ; `heures_declassees` 2. Aucune valeur par défaut.

### ACAL741 — CORRIGER
Faux/périmé : (a) « Appelants : `propose_mapping` ← `apps/stock/views/fiche_technique.py` » : la vue importe `parse_pan_ond_bytes` (`B/stock/views/fiche_technique.py:10,127`), pas `propose_mapping` ; (b) la décision que la tâche renvoie à la lane est déjà lisible : le `.OND` réel du dépôt est déjà là, `B/stock/contract_samples/pvsyst/CPS_SCH275KTL-DO-US-800-250kW_275kVA_1.OND` (SOURCE.md : pvlib v0.16.1), et il publie TROIS points de déclassement, pas deux : `TPNom=45.0`/`PNomConv=250`, `TPLim1=50.0`/`PLim1=225`, `TPLimAbs=60.0`/`PLimAbs=90` (pentes 2 % puis 5,4 % de PNom par °C) : une seule paire (début, pente) ne se déduit pas « sans hypothèse ».
Correction : réécrire en « lire le `.OND` du dépôt ; ses trois points ne se ramènent pas à une pente unique ⇒ la tâche s'ARRÊTE et le dit » (SANS OBJET), ou la remplacer par une tâche de table de déclassement par segments (change ACAL659/740) — décision à prendre au plan, pas par le constructeur. Corriger l'appelant en `parse_pan_ond_bytes`.

### ACAL742 — CORRIGER
Faux : « `test_acal_reglages_types.py::test_chaque_cle_du_registre_a_un_type` fige `total == 37` (à réaligner : 39) » : le test fige 40 (`C/tests/test_acal_reglages_types.py:63`, commentaire « 31 simulation + 9 electrique_societe ») ⇒ 42.
Oublié : `C/data/profil_depart.json` (11 `valeurs` + 29 `sans_source` = 40) doit aussi recevoir les deux clés en `sans_source`, sinon `tests/test_calx145_parametres_simulation.py:431-446` (`proposees | sans == tout`) devient rouge ; la tâche ne cite que l'échantillon `contract_samples/calepinage_profil_depart.json` (dont le test `test_cal223_contrats.py:584-610` exige la même égalité).
Correction : « 40 → 42 » ; ajouter `backend/django_core/apps/calepinage/data/profil_depart.json` à Emplacement et `Files:` (deux lignes `sans_source`, même motif que les 29 autres).

### ACAL743 — CORRIGER
Faux : « le pan se lit par `iam.py::_plan`, déjà employé par `mismatch_ombrage.py` et `bifacial.py` : aucun sixième lecteur ». `iam._plan` (`C/services/etapes/iam.py:290`) n'est appelé que par `iam.py:208` ; `mismatch_ombrage.py` lit le pan par son propre `_repere_du_pan` (l.377, un NOM, pas une inclinaison) et `bifacial.py` par `CHEMINS_INCLINAISON` (l.117) ; `thermique.py:189` a un 3ᵉ lecteur. `salissure.py` (277 l., `appliquer` l.108) n'a aucun accès au pan.
Correction : lire l'inclinaison par `bifacial.py::CHEMINS_INCLINAISON` (+ son lecteur `_valeur`) ou par `iam._plan` importé explicitement, dire « chemins `plan.inclinaison_deg` / `plan.geometry.tiltDeg` » et prévoir le cas `contexte['plan']` str + `contexte['plans']` ; retirer « aucun sixième lecteur ».

### ACAL744 — OK
Ouvert : `C/services/pvgis_serie.py:88-91,785` (`BASES_RAYONNEMENT`, `BASE_PAR_DEFAUT`, `_base_admise`, ERA5 seul là), `simulation.py:921-927` (`base=BASE_PAR_DEFAUT` seul appel), `:938-959` (précédent : un appel PVGIS de plus compté dans `appels_pvgis`), `:979` (`meteo['fichier']`), `test_calx154_bloc_meteo.py:102,117` (noms exacts), `test_calx155_appels_pvgis.py:43`, `sigma_biais_meteo_pct` présent (`parametres_cles.py` TYPES_CLES). Simulation 1 824 l. (la tâche dit 1 753, anodin). Aucun seuil, aucun chiffre ajouté.

### ACAL745 — OK
Ouvert : `F/production/BandeauProvenanceProduction.jsx` (256 l., `EcartDevis` l.79, `SourceMeteo` l.181 exportée), tests nommés présents, consommateurs `PanneauProduction.jsx` et `atelier/PanneauSeries.jsx`.

### ACAL746 — OK
Ouvert : aucun `nasa` dans `C` ; `C/services/meteo_horizontale.py:19,54,117,190` fixe bien le format `points[annee,mois,jour,heure,ghi_w_m2,dni_w_m2,dhi_w_m2,t2m_c,ws10m]` + `plan_des_donnees 'horizontal'` ; `pvgis_serie.py:359` (`_Cache`) et `ClientPvgis` (l.426) existent. La clause d'ARRÊT protège la règle d'usage. OPTIONNEL : client sans appelant (livré mort tant qu'aucune tâche ne le branche).

### ACAL747 — OK
Ouvert : `albedo_mensuel` typé `table_mensuelle` (`parametres_cles.py` TYPES_CLES), `F/reglages/ReglagesSimulation.test.jsx` existe, aucun `albedoSurfaces.json` encore ; la règle « une seule valeur imprimée, jamais le milieu d'une fourchette » respecte D-ACAL-31. Non vérifié : le contenu de la page PVsyst (lecture web, à faire par le constructeur).

### ACAL748 — OK
Ouvert : `F/reglages/ReglagesSimulation.jsx` (733 l.) `LigneReglage` l.227 (type `table_mensuelle` l.188), route `/calepinage/reglages` (`module.config.jsx:128`), `DemarrageRapide.jsx` (ACAL405) existe, tests nommés l.48-145 présents.

## OPTIONNEL (5 lignes)
- ACAL726 : mocker `builderApi.renderCarteAccesHd` (pas `deposerCarteDeChaleur`) pour tester le cas « sans ombre ».
- ACAL732 : un horizon saisi sans obstacle déclenche aussi le calcul d'accès ; la phrase ne le mentionne pas.
- ACAL736 : garder la largeur de classe 1/20 en constante nommée avec sa source.
- ACAL746 : client sans appelant — dire quelle tâche le branchera.
- Beaucoup de tâches du lot (722, 723, 724, 734, 736, 740) écrivent `calepinage_pertes_cascade.json` et `chaine_pertes.py` : une seule lane, ordre 711 → 722 → 724 → 723 à fixer par `@after`.
