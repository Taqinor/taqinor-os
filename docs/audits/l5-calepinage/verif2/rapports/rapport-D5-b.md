# Rapport de vérification — lot D5-b (28 tâches), code lu dans l5-verif

Légende des chemins : `BE` = `backend/django_core/apps/calepinage`, `FE` = `frontend/src/features/calepinage`.

### ACAL810 — OK
`BE/views/pompage.py:209-385` (`pompage` : aucun contrôle de chaîne, `_kwc_retenu` l.103, `_champs_corps` l.185, `_NOMBRES_POMPAGE` l.151) ; `produits_pompage` + `fiche` servis (`stock/selectors.py:3167,3279`) ; `resoudre_materiel` (`BE/services/electrique.py:1227`), `temperatures_pour_calepinage` (l.330) ; `test_agr125_parite_devis.py:141` (`set(donnees)`) ; `grep variateur` dans `services/electrique.py` = 0. `controle_chaine_variateur` absent du code (attendu : ACAL809, autre plan).

### ACAL811 — OK
`FE/pompage/PompagePanel.jsx:46-76` (`CHAMPS`, aucun champ de chaîne), `VolumesMensuels` l.169, hooks `cal-pompage-*` présents dans `E2E_HOOKS.md` et `e2eHooks.test.mjs` ; onglet « pompage » dans l'étape Panneaux (`atelier/parcoursGuide.js:19`).

### ACAL812 — OK
`BE/services/balayage.py:252-311` (classe sur `specific_yield_kwh_kwc`, `appels_pvgis` calculé), `BE/views/balayage.py:88-122`, `chaine_pertes.py:1382,1410` (`production.total.kwc`, `production.mensuel[].p50_kwh`) ; `calepinage_balayage.json` existe ; `test_calx155_appels_pvgis.py` existe et couvre le balayage. (ACAL468 est déjà construit : « créé par ACAL468 » est périmé mais sans effet.)

### ACAL813 — OK
`FE/atelier/PanneauOptimiser.jsx` (« Appliquer l'optimum » l.163-170, `choixConception` l.83), `atelier/onglets.js:98` (monté), onglet « optimiser » dans l'étape Résultats, expert (`parcoursGuide.js:24`), `PanneauOptimiser.test.jsx` existe.

### ACAL815 — OK
`BE/views/pompage.py:361` (`couverture_besoin_eau` seul, aucune comparaison), `_NOMBRES_POMPAGE` l.151 ; `comparaison_direct_reservoir` = ACAL814 (autre plan, absent du code comme attendu).

### ACAL816 — CORRIGER
La tâche est incohérente avec elle-même : « Persistance … migration `AddField` seule » mais l'Emplacement dit que la migration est ACAL660 (plan stock, `@after: -`) et `Files:` ne contient aucune migration ; or le « fini quand » exige `makemigrations --check` vert et un enregistrement/relecture (colonne obligatoire en base). Seule, ACAL816 est rouge (modèle sans colonne) ; ACAL660 (qui migre `var_bus_dc_redresse_v`) seul est rouge aussi (migre un champ absent du modèle). Preuve : `stock/models_fiche_technique.py:764` (champ voisin), dernière migration stock = `0182_fiche_onduleur_dc_max_et_mppt_15_20kw.py` (donc « numéro libre suivant 0182 » est décalé : 0183 ou la suite).
Correction : mettre la migration `AddField` dans ACAL816 (ajouter `backend/django_core/apps/stock/migrations/NNNN_acal816_var_bus_dc_redresse.py` à `Files:`, retirer « la migration est ACAL660 … ») et retirer `ACAL816 (var_bus_dc_redresse_v)` de la liste d'ACAL660 ; ou, à défaut, donner `@after: ACAL816`… et ne pas exiger `makemigrations --check` dans ACAL816. Corriger « numéro libre suivant 0182 » en « à relire sur origin/main (dernier : 0182) ».

### ACAL820 — OK
Mêmes ancres qu'ACAL810 (`pompage`, `_champs_corps`, `test_agr125_parite_devis.py`), `@after` ACAL810 ; dépend d'ACAL817/818 (autres plans, absents comme attendu). (Voir OPTIONNEL 1.)

### ACAL821 — OK
`BE/views/pompage.py::pompage` (une seule pompe, l.270-330), `PompagePanel.jsx`, tests existants ; `controle_pompes_par_variateur` = ACAL819 (autre plan). (Voir OPTIONNEL 1.)

### ACAL822 — OK
`BE/models.py:1069-1160` (`GabaritDossierReglementaire` : ni `limites` ni `verifie_le` ni `distributeur` ; `FRAGMENT_DOUBLON` l.1113), `services/reglementaire.py:1006` (`CHAMPS_GABARIT`), :1045 (`gabarit_publie`), :1121 (`_premier_element_fautif`), :1213 (`_appliquer`), `views/gabarits_dossier.py:43` (`_FORME_GABARIT`) ; tests `test_acal_gabarits_dossier.py` (`DepotTest` l.84, `RefusTest` l.174), `test_cal223_contrats.py:755` (`test_gabarit_publie` compare les clés) ; `FE/reglages/ReglagesGabarits.test.jsx` importe bien l'échantillon. Aucune pièce ni limite livrée (D-ACAL-43 respectée).

### ACAL824 — OK
`FE/DossiersReglementaires.jsx:363,401,406-409` (`Dossier`, ligne « déposé le », bandeau `role="alert"` `genere_sur_conception_perimee` = le patron cité), `BE/services/parametres_cles.py:158,179,225` (`CLES_ELECTRIQUE_SOCIETE`, `REGISTRES`, `TYPES_CLES`), `selectors.py:954` (`parametres_de_societe(company)`), `reglementaire.py:361,391`, `test_cal191_preremplissage.py:175` (`GabaritManquantTest`). Aucun N par défaut.

### ACAL827 — CORRIGER
« Assertions existantes » est inexact : `tests/test_calx244_bloc_raccordement.py` porte SA PROPRE constante `CHAMPS_CALCUL` (4 clés, l.53) comparée à `set(bloc['calcul'])` (l.111, `test_les_quatre_grandeurs_calculees`) : elle devient rouge dès que `calcul` gagne `plafond_injection_kw_converti` et `plafond_injection_conversion`. Le test 205 a aussi `COUPLES_SOURCES` (`test_calx205_contrat_raccordement.py:77-80`, « une source sans valeur n'existe pas ») : un état d'échantillon qui saisit les ampères avec une justification et `plafond_injection_kw` à null le rend rouge.
Correction : remplacer « `tests/test_calx244_bloc_raccordement.py` (l.104 compare à la constante : vert) » par « `tests/test_calx244_bloc_raccordement.py` (`CHAMPS_CALCUL` l.53 : 4 → 6, à réaligner ; l.104 vert) ; `test_calx205_contrat_raccordement.py` (`CHAMPS_SAISIE` 9 → 10, `CHAMPS_CALCUL` 4 → 6, `COUPLES_SOURCES` : ajouter `('plafond_injection_a', 'plafond_injection_justification')` si un état saisit les ampères) ». Vérifié par ailleurs : √3 × 400 × 16 = 11 085,1 W donc 11,085 kW ; `CHAMPS_SAISIE` = 9 aujourd'hui (`services/raccordement.py:973`), `INTITULES_SAISIE` l.995 ; `saisie_du_calepinage` aux l.563 et 687 de `simulation.py` (et non 560/684).

### ACAL828 — OK
`BE/services/autoconsommation.py:86` (`plafond_injection`, 239 l.), `batterie.py:721,738,740` (3 appels), `etapes/autoconsommation.py:231,298` (`bloc_autoconsommation`, `_publier`), `etapes/batterie.py:557` (heure du premier point), `test_calx190_autoconsommation.py:123` (`PlafondInjectionTest`). Compte 10 → 11 champs cohérent avec ACAL827. (Voir OPTIONNEL 2.)

### ACAL829 — OK
`etapes/autoconsommation.py:298-359` (`_publier` calcule `imports` après batterie), `test_calx190…::ProprieteAutoconsommeTest` l.96 existe ; compte 11 → 13 cohérent ; `puissance_souscrite_kva` ne sert qu'au verdict d'injection.

### ACAL830 — CORRIGER
La clause « les écarts `profil_distributeur.ecarts` (ACAL826) s'affichent en avertissements sous le champ » vise une clé et une tâche qui n'existent pas : ACAL826 (comme ACAL823 et ACAL825) n'est pas dans l'index de la vague, `grep profil_distributeur` dans le code = 0, et D-ACAL-43 range le profil par distributeur en réserve (ACAL822 le dit : « retiré »).
Correction : supprimer de « Given … Then » la clause « les écarts `profil_distributeur.ecarts` (ACAL826) s'affichent en avertissements sous le champ » et la mention d'ACAL826 dans « Constat ». Reste vérifié : `Raccordement.helpers.js:37-100` (`CHAMPS` = 9, `corpsDeSaisie` l.145 envoie `null`), `atelier/onglets.js:76`, `Raccordement.test.jsx:51`.

### ACAL831 — CORRIGER
(a) La porte `pompage/` est `permission_classes=[PeutVoirCalepinage]` (`BE/views/pompage.py:206`, droit de LECTURE) : la tâche y fait écrire `Calepinage.resultat['pompage_dernier']` ; un simple lecteur modifierait la base. (b) `tests/test_acal_garde_routes_verrou.py:150` classe `('POST','pompage')` « proposition de pompage (lecture calculée) » dans `ROUTES_HORS_VERROU` : ce motif devient faux et le fichier n'est ni dans `Files:` ni dans « Assertions existantes ». (c) « aucune clé prix dans l'échantillon » est inexact mot pour mot : `calepinage_pompage.json:41` a `sans_prix` (sans conséquence : le pare-feu `note_calcul._cle_interdite` compare des jetons entiers et n'a que `prix` exact).
Correction : ajouter à la clause : « la porte reste ouverte à `calepinage_voir` pour le calcul ; l'enregistrement n'a lieu que si l'appelant porte `calepinage_gerer` (sinon `enregistre: false`, `motif_non_enregistre` « droit calepinage_gerer manquant »), testé par un cas lecteur seul » ; ajouter à `Files:` et « Assertions existantes » `backend/django_core/apps/calepinage/tests/test_acal_garde_routes_verrou.py` (réécrire le motif de `('POST','pompage')` : « calcul + enregistrement du dernier dimensionnement, jamais 409 »). Vérifié : `modifier_resultat` (`services/resultat.py:74`), `verifier_ecriture_autorisee` lève `VerrouilleRefuse` (`services/verrou.py:75-103`, à attraper), `BLOCS_SIMULATION` = 12 blocs sans pompage (`services/electrique.py:438`), `rattachements.py:67`.

### ACAL832 — OK
`BE/services/rapport/__init__.py:91-102` (`MODULES_DE_SECTION`, aucune section consommation), `construire_rapport` l.348, `annexe_hypotheses.py:149` (`_non_calcule`), `contract_samples/rapport_etude.json` (ordres 50/60 : 52, 54, 56 libres), `courbe_charge.py:884-896` (clés `courbe_origine`, `total_kwh`, `total_base_kwh`, `total_charges_kwh`, `charges[]`, `profil_mensuel[]` = `{mois, kwh}`), `consommation` ∈ `BLOCS_SIMULATION`, `libelles_document.py:52,124`, tests `test_calx292…:40` (`CODES_ATTENDUS`), `test_calx297…:86` (`AssemblageTest`), `test_calx296…:44`.

### ACAL833 — OK
`etapes/hors_reseau.py:152-157,297-314` (toutes les clés citées servies : `defaillance_kwh`, `par_mois`, `mois_le_plus_defavorable`, `soc_minimal_pct`, `banque`, `quantiles_publiables: False`, `mentions`), `rapport/systeme.py:180` (`_bloc_batterie`), `hors_reseau` ∈ `BLOCS_SIMULATION`.

### ACAL834 — OK
Dépend d'ACAL831 (`pompage_dernier`) et d'ACAL832 (omission) ; `verifier_etancheite` couvre le stocké (`rapport/__init__.py:180`), `resultat_stocke` est dans `construire_rapport`. Aucune ancre fausse. (Dépend de la correction d'ACAL831 pour la forme de `exemple_enregistre`.)

### ACAL835 — OK
`BE/services/autoconsommation.py:168-239` (`bilan_autoconsommation`, `taux_couverture` COUV-AUTO), `chaine_pertes.py:901-984` (série persistée : `p_ac_kw`, `charge_kwh`, `tronquee`), `tasks.py:251` (`balayer_calepinage`), `test_conso_couv_auto.py:32` (`CouvAutoTest`), ACAL470 construit. (Voir OPTIONNEL 3.)

### ACAL836 — CORRIGER
Trois trous qui font échouer le « fini quand » tel qu'écrit : (1) l'exemple (3 mois en kWh, sans `classe`) lève 409 : `_depuis_factures` appelle `_classe_saisie(corps)` (`BE/services/consommation.py:1088-1089`, 1018-1033 « jamais supposée »), pour des kWh qui n'ont pas besoin de barème. (2) `_publier_kwh` (l.240-298) réécrit `ligne['kwh']` de CHAQUE mois depuis `facture_mad` : les kWh saisis seraient remis à `None`. (3) `proposer_consommation` ne rend que `{consumption, kwh_annuel, courbe24, saisons, avertissements}` (l.1246-1248) : `mois[]` n'est pas servi (il reste dans le `profil` interne), et `proposer_consommation` n'est pas dans l'Emplacement. Un corps mêlant MAD et kWh n'a pas de règle.
Correction : ajouter à « Given … Then » : « `classe` n'est exigée que si au moins un mois est en MAD ; les mois en kWh gardent leur valeur (la conversion `_publier_kwh` ne s'applique qu'aux mois MAD) ; un corps qui mêle MAD et kWh convertit d'abord les MAD en kWh, puis interpole sur les kWh » ; ajouter à l'Emplacement `backend/django_core/apps/calepinage/services/consommation.py::proposer_consommation` (publication de `mois`, ≈ 10 l.) et au test un cas « kWh seuls sans classe : 200 ». Les chiffres d'exemple sont justes (300→500 en 6 pas de 33,3 ; 500→400 en 3 pas ; 400→300 en 3 pas).

### ACAL837 — OK
`apps/web/src/scripts/roofPro11/consumption.ts:129` (`rp9-bill`), :607-612 (`proposerConsommation`, `jeton`), :692-773 (`monterProposition`, `data-cons-*`), `types.ts:121` (option), `apps/web/tests/roofPro11QuoteFirstSizing.test.ts:174-339` (cas ACAL311) ; les pages publiques n'injectent pas l'option (test « `proposerConsommation: null` »).

### ACAL839 — CORRIGER
(a) `Files:` oublie ce que l'Emplacement fait modifier : `backend/django_core/apps/crm/services.py` (ligne de façade + `__all__`) — fichier d'une autre app (`docs/ownership.yml:466`), surface « façade » (`crm/services.py:23-63`) ; et le test qui garde les façades est cité mais pas listé. (b) Ajouter la clé `lireFactureConsommation` change le nombre de clés extraites : `frontend/src/api/calepinageApi.golden.test.mjs:41` (`NOMBRE_CLES_EXTRAITES = 124`, annoté tâche par tâche ; assertions l.170, 176, 200) deviendrait rouge ; le fichier n'est pas dans `Files:` (« régénérer le golden » ne le corrige pas, la constante est écrite à la main).
Correction : ajouter à `Files:` `backend/django_core/apps/crm/services.py` et `frontend/src/api/calepinageApi.golden.test.mjs`, et à « Assertions existantes » : « `calepinageApi.golden.test.mjs` : `NOMBRE_CLES_EXTRAITES` 124 → 125 (+1 `calepinages.lireFactureConsommation`) ». Vérifié : `views/consommation.py:107-111` (patron `proposer_consommation`), `PeutLireOuEcrireCalepinage` existe (`permissions.py:87`), `crm/tests_services_facade_pure.py` existe, `lire_photo_facture` = ACAL838 (lead), absent comme attendu.

### ACAL840 — OK
`apps/web/src/scripts/roofPro11/types.ts:121`, `consumption.ts:607-773`, `frontend/src/pages/ventes/ToitureDesign.jsx:339`, `frontend/src/features/calepinage/atelier/useAtelierBoot.js:70-72` (`proposerPourAtelier`) ; la clé API relève d'ACAL839 (`@after` correct).

### ACAL842 — CORRIGER
Le nom de champ du refus est faux : « refusée en nommant `zones[i].existant.anneeMiseEnService` ». ACAL573 (la tâche qui pose le contrat) définit deux clés SŒURS : `zones[].existant` (booléen) et `zones[].anneeMiseEnService` ; il n'y a pas de sous-objet. « ACAL841 » (cité en Contrat partagé) n'existe pas dans l'index : la tâche porteuse est ACAL573. Vérifié : `etapes/vieillissement.py:111-174,251` (`tableau_pluriannuel`, `_facteurs`, « année = un rang »), `simulation.py:200-232` (`_plans_du_contexte` sans ancienneté), appel l.1461 ; la formule `f(âge + N) ÷ f(1)` suppose de calculer `_facteurs` sur `horizon + âge` années (à dire).
Correction : remplacer `zones[i].existant.anneeMiseEnService` par `zones[i].anneeMiseEnService` ; remplacer « (ACAL841, clé `existant`) » par « (ACAL573, clés `existant` et `anneeMiseEnService`) » ; ajouter « `_facteurs` est évalué sur `horizon + âge` rangs ».

### ACAL843 — OK
`chaine_pertes.py:1382-1418` (`production.total`, `mensuel`, `par_pan`), `simulation.py` (`_somme_des_series`, `_plans_du_contexte`), `calepinage_resultat.json` (`exemple_ecart_devis` existe, patron valide), `_m0_en_attente.py` existe ; clé `existant` pas encore au schéma (ACAL573 pose).

### ACAL846 — CORRIGER
(a) Même défaut qu'ACAL839 : la clé `ecartMesures` ajoutée à `frontend/src/api/calepinage/projet.js` (fragment lu par `lireSourceCalepinageApi`) change `NOMBRE_CLES_EXTRAITES` (`calepinageApi.golden.test.mjs:41`, 124) ; le fichier n'est pas dans `Files:`. (b) La consommation simulée `consommation.profil_mensuel` est la somme de tous les pas de la FENÊTRE météo (`courbe_charge.py:775-783,892`), non ramenée à l'année moyenne (alors que `autoconsommation.par_mois` l'est : `etapes/autoconsommation.py:198-226`, `annees_de_la_fenetre`) ; avec une fenêtre de N > 1 ans (mode série, réglage société `fenetre_annees`) l'écart en % serait faux de ×N. En mode TMY par défaut N = 1, donc le défaut ne se voit pas à la recette.
Correction : ajouter `Files:` `frontend/src/api/calepinageApi.golden.test.mjs` (`NOMBRE_CLES_EXTRAITES` 124 → 125) ; ajouter à « Given … Then » : « `simule_kwh` = `profil_mensuel[mois].kwh` ÷ `annees_de_la_fenetre` (année moyenne, comme `autoconsommation.par_mois`) ; test avec une fenêtre de 2 ans ». Vérifié : `asbuilt.py` (`ecarts_du_calepinage` l.244, pas de `ecart_mesures_du_calepinage` : fonction à créer), `views/asbuilt.py:83-135`, `PeutApprouverCalepinage` (`permissions.py:105`), garde `test_acal_garde_routes_verrou.py` (liste figée) ; `ReleveCompteurEquipement` avec `Type.KWH`/`M3` (`sav/models.py:581-595`), ACAL845 absent comme attendu.

### ACAL847 — OK
`FE/atelier/PoseReelle.jsx` (+ 2 tests), `atelier/onglets.js:88`, `Approbation.jsx:61` (`useHasPermission('calepinage_approuver')`), onglet « pose-reelle » dans l'étape Documents (`parcoursGuide.js:26`).

### ACAL848 — CORRIGER
`TotalKpis` n'existe plus : `FE/production/PanneauProduction.jsx:366` rend `<ResultatHeros total=… />` (`ResultatHeros.jsx:13`, props `total, simule, motif, avertissements`) ; seul le « Constat » le dit, l'Emplacement (« à côté de `<TotalKpis>` ») et « Appelants » (« `TotalKpis` ← `PanneauProduction.jsx` (1 site) ») sont périmés.
Correction : remplacer `<TotalKpis>` par `<ResultatHeros>` dans l'Emplacement (« à côté de `<ResultatHeros>`, l.366 ») et « Appelants : `ResultatHeros` ← `PanneauProduction.jsx` (1 site, ne reçoit que `total`) ». `TableauParPan` l.269 et `PanneauProduction.test.jsx` existent.

## OPTIONNEL (5 lignes)
1. ACAL820/821 : « `appoint_variateur` / `pompes_variateur` absent sans … » — le test `test_agr125_parite_devis.py:141` compare `set(donnees)` à `set(exemple)` sur un POST sans ces champs ; servir la clé à `null` plutôt que l'omettre évite de contourner ce test.
2. ACAL828 : à pas ≠ 60 min, le bloc `autoconsommation` entier est omis dès qu'une plage est saisie ; n'omettre que les plages garderait taux et écrêtage de base.
3. ACAL835 : « production × N ÷ N0 » appliqué à `p_ac_kw` (déjà écrêtée par l'onduleur) surestime la production d'un champ plus petit non écrêté ; dire l'écrêtage dans `hypothese`.
4. ACAL822 : « écran = ACAL825 » et « ACAL823 » visent des tâches absentes de l'index (ACAL823/825/826) ; reformuler en « écran non planifié ».
5. ACAL824 : prévoir une horloge injectable (`aujourd_hui`) pour tester « il y a 400 jours » dans `GabaritManquantTest` (test pur).

## Non vérifié
ACAL820 : le cas « 11 modules, 400 V ⇒ `vmp_sous_bus` » dépend du module d'essai d'ACAL818 (autre plan) ; avec le module du jeu AGR125 (Vmp 40 V, `test_agr125_parite_devis.py:80`) 11 modules font 440 V — à confirmer à la construction. Nombre exact d'appelants de `gabarit_publie` (ACAL822) non recompté. Maquettes `docs/audits/l5-calepinage/maquettes/*.dc.html` absentes de l5-verif (non lues).
