# Rapport de vérification — lot D3-a (27 tâches) — code lu dans l5-verif

Racine code : `C:\dev\taqinor-os\.claude\worktrees\l5-verif\` (R). Backend calepinage = `R/backend/django_core/apps/calepinage` (BC).

### ACAL611 — CORRIGER
Un contrat posé SEUL sans moitié cliente fait rougir la CI : `R/scripts/check_contrats_calepinage_deux_moities.py` (l.80-90 : le NOM du fichier JSON doit être cité dans `frontend/src/**`; « un échantillon NEUF n'a jamais droit au passif », `contrats_calepinage_allow.txt`). `grep calepinage_evaluation_electrique` dans frontend = 0. ACAL614 l'a prévu (commentaire dans `calepinageApi.js`), pas ACAL611.
Correction : ajouter à `Files:` `frontend/src/api/calepinageApi.js` et à « Emplacement » : « une ligne de commentaire en fin de fichier `// ACAL611 — contrat calepinage_evaluation_electrique.json (M0)` (comme `calepinageApi.js:441-449`) ».
Le reste est vrai : route `evaluer-electrique` existe (`BC/views/electrique.py:199`), `publication` = `None` si `layout` ou `entree` (l.240-242), motifs à quatre clés (`services/electrique.py:2570`), `SANS_PRODUCTEUR_PUR` et `test_chaque_echantillon_est_declare_ici` existent (`tests/test_cal223_contrats.py:84,546`). Voir aussi ACAL612 (vocabulaire à trancher avant d'écrire `etat`).

### ACAL612 — DOUBLON (avec ACAL934, lot D7)
ACAL934 (`@after: -`, M1) sert déjà « un état à trois valeurs du dossier électrique » (`pret` / `a_completer` / `bloquant`, clés `etat` + `points`, module neuf `etat_dossier_electrique.py`, sans changer `publiable`) dans `verdict_publiable`, `verdict_de_conception`, `evaluation_electrique`, `_bloc_electrique` ; ACAL858 (D6) en dépend. ACAL612 sert le MÊME état avec un AUTRE vocabulaire (`publiable_avec_reserves` / `reserves`, plus `titre`, `phrase`). Deux tâches, deux vocabulaires pour une seule vérité = le défaut PACT10 que la campagne cherche à éviter.
Correction : fusionner. Garder UN vocabulaire (celui d'ACAL934, déjà consommé par ACAL858) ; ACAL612 devient « ajouter `titre` et `phrase` composés serveur à `publication`, à partir de `etat`/`points` d'ACAL934 » avec `@after: ACAL934`, et ACAL611/613/620 reprennent `etat` ∈ {pret, a_completer, bloquant} et `points`. Sinon supprimer ACAL612 et laisser ACAL934 + ajouter `titre`/`phrase` à ACAL934.
(Prémisse vérifiée : `_rapport_publication` ne ferme `publiable` que sur bloquant/sans_source, `services/electrique.py:2857` ; `FormeDuRapportTest` fige deux clés, `tests/test_calx248_verdict_publiable.py:117-129`.)

### ACAL613 — OK
Lignes 350-359 de `frontend/src/features/calepinage/electrique/VerdictElectrique.jsx` écrivent bien « Publiable » en `tone='success'` et « Aucun motif bloquant… » ; `Badge` a un ton `warning` (`frontend/src/ui/Badge.jsx:14`) ; `verdict-electrique` est dans `ESSENTIELS` (`atelier/parcoursGuide.js:30`). Dépend de la décision de vocabulaire d'ACAL612/934 (lire `etat` du serveur, sans le recoder).

### ACAL614 — OK
`calepinage_configurations_onduleur.json` n'existe pas ; `POSES_AVANT_LEUR_ROUTE` existe (`test_cal223_contrats.py:439`) ; commentaire de citation en fin de `calepinageApi.js` existe comme patron (l.440-449) ; `forme_serveur` est une clé connue des échantillons (`calepinage_balayage.json` etc.) ; aucun prix.

### ACAL615 — OK
Confirmé : `_valider_produits_designes` (`services/electrique.py:731-751`, `introuvable=True`) n'est appelé que par `enregistrer_entree` (l.1118) ; `evaluer_electrique` fusionne `entree` dans `donnees` (`conception_du_calepinage` l.1498-1506) puis `resoudre_materiel` appelle `get_produit_scoped(company, identifiant)` sans garde ; la vue répond toujours 400 sur `EntreeInvalide` (l.244-246) alors que `entree-electrique` mappe `introuvable` → 404 (l.182-186). `OracleInterSocietesTest._paire`, `test_acal_entree_electrique_validation.py`, `test_structure_urls.py:525` existent.

### ACAL616 — OK
`evaluer_onduleurs`, `specs_onduleur`, `concevoir_par_pan`, `produits_par_type_fiche_qs` (`apps/stock/selectors.py:3677`), `specs_for_produit`, `forme_du_contrat`, `ElectriqueActionsMixin` existent ; `VerdictUnique._produit` existe (`tests/test_acal_verdict_unique.py:55`). Aucune route `configurations-onduleur` avant (grep = 0).

### ACAL617 — OK
`MaterielElectrique.jsx` (172 l.) a `ROLES`, `enregistrer`, `lire` ; `calepinageApi.golden.json` + test `CALEPINAGE_GOLDEN_ECRIRE` existent ; `exempleContrat` existe (`frontend/src/test/fixtures/contractSamples.js:63`).
Note (mineur, voir OPTIONNEL) : « ACAL395 la montera… sans la reconstruire » est périmé — ACAL395 est livré (`electrique/EtapeElectrique.jsx`, `materiel-electrique` déjà section).

### ACAL618 — CORRIGER
Le décorateur `forme_reponse('CalepinageEvaluationElectrique', …)` de `views/electrique.py:187-190` change → l'instantané `docs/openapi-schema.yml` change (ACAL616/627 le disent, pas ACAL618) ; CI rouge sinon.
Correction : ajouter à « Listes figées » : « `docs/openapi-schema.yml` (régénéré par `scripts/check_openapi_schema.py --write`, hors `Files:`) ». Prémisses vraies : `Chaine.voc_froid_v/vmp_chaud_v/isc_a` (`core/electrique/chaines.py:~760`), `affectation` (`services/chaines.py:1022`), `SOURCE_AUTO/SOURCE_MANUELLE` (l.1370-1371), `bloquants_nommes`, `_verdicts_tension` (`core/electrique/chaines.py:789`), `_Calepinage`/`_materiel` dans `test_elec_bloquants_onduleur.py:34,49`. Calcul Voc(−5 °C) = 49,6 × 1,081 recalculable.

### ACAL619 — CORRIGER
Prémisse de placement fausse : la bulle va dans `AffectationChaines.jsx`, or l'onglet `affectation` est sous l'étape **Panneaux** (`atelier/parcoursGuide.js:19`), pas Électrique ; seul le tableau « Tension par temps froid » est dans l'étape Électrique (`verdict-electrique`, l.21). Texte : « Étape Électrique, niveau essentiel » est vrai pour le tableau, faux pour la bulle.
Correction : remplacer par « bulle : onglet `affectation` (étape Panneaux, niveau expert) ; tableau : section Verdict de l'étape Électrique ». Reste OK (`git grep voc_froid frontend` = 0 vérifié ; fichiers/tests existent).

### ACAL620 — OK
Étend le JSON posé par ACAL611 ; `test_chaque_echantillon_est_complet` existe (`test_cal223_contrats.py:538`). (Le nom `exemple_indetermine` est créé ici, pas dans ACAL611 : cohérent.) Pas de nouvelle moitié cliente requise (ACAL611 corrigée la porte).

### ACAL626 — CORRIGER
Deux CI rouges : (1) `CheminDeclareTest.test_chaque_chemin_du_module_existe_dans_les_sources` cherche le segment `controle-chaine` dans `urls.py`/vues (`test_cal223_contrats.py:699-724`) → absent (grep = 0) ; sans entrée dans `POSES_AVANT_LEUR_ROUTE` il rougit (ACAL614 le fait, pas ACAL626) ; (2) moitié cliente absente (`check_contrats_calepinage_deux_moities.py`).
Correction : « Emplacement » ajoute « déclarer le nom dans `POSES_AVANT_LEUR_ROUTE` vers `ACAL627` » + `frontend/src/api/calepinageApi.js` (commentaire de citation) dans `Files:` ; ACAL627 retire l'entrée.

### ACAL627 — CORRIGER
Le « Test rouge d'abord » met 400 (température absente), 404 (produit d'une autre société) et 200 dans `tests/test_elec_bloquants_onduleur.py`, qui n'a que des `SimpleTestCase` sans base (l.59-171). Les cas 400/404 exigent des produits et une société en base (cf. `BaseApiCalepinage`, `OracleInterSocietesTest`).
Correction : garder la classe `ControleChaineSansDessinTest` sans base pour le calcul du noyau (22 × 49,5 V à −5 °C ⇒ 1 177 V, vérifié : 49,5 × (1 + 0,0027×30) × 22 = 1 177,2) et ajouter les cas route (400, 404 identique à id absent, rien écrit) à `tests/test_acal_oracle_inter_societes.py` (ajouter à `Files:`). Préciser aussi d'où vient « courant » : `fenetre_admissible` (`core/electrique/chaines.py:318`) ne rend que les 4 bornes de longueur, pas de contrôle de courant — soit citer la fonction du noyau qui juge `i_max_mppt`, soit retirer « courant » de ACAL626/627/628.

### ACAL628 — CORRIGER
Un onglet neuf ne se monte pas par `onglets.js` seul : (a) `atelier/parcoursGuide.js::ETAPES` doit le ranger sous `electrique` (sinon invisible du rail guidé et `Rail.test.jsx:250-254` « total des onglets = `ONGLETS.length` » rougit) ; (b) `electrique/EtapeElectrique.jsx::SECTIONS_ELECTRIQUES` (7 sections en dur) doit l'ajouter, sinon absent de l'écran Électrique d'ACAL395 (livré) ; (c) `commun/glossaireOnglets.js` : le test `Rail.test.jsx:518` exige une entrée par onglet ; (d) décompte figé `Rail.test.jsx:272` (`toHaveLength(40)`) à réaligner. Aucun n'est dans `Files:`.
Correction : ajouter à `Files:` `frontend/src/features/calepinage/atelier/parcoursGuide.js`, `frontend/src/features/calepinage/electrique/EtapeElectrique.jsx`, `frontend/src/features/calepinage/commun/glossaireOnglets.js`, `frontend/src/features/calepinage/atelier/Rail.test.jsx` ; remplacer « ACAL395 (ouverte) fera de cet onglet une section » par « ajouter `controle-chaine` à `SECTIONS_ELECTRIQUES` ». Ne pas le mettre dans `ESSENTIELS` (niveau expert voulu).

### ACAL629 — CORRIGER
Même défaut qu'ACAL626 : pas d'`endpoint` dans le « Given » (le test exige `endpoint`, `test_cal223_contrats.py:538-544`), pas d'entrée `POSES_AVANT_LEUR_ROUTE` (la route `importer-affectation` n'existe pas, grep = 0), pas de moitié cliente.
Correction : écrire `endpoint` « POST /api/django/calepinage/calepinages/<int:pk>/importer-affectation/ » (celui d'ACAL630) ; déclarer `POSES_AVANT_LEUR_ROUTE` vers `ACAL630` ; ajouter `frontend/src/api/calepinageApi.js` (citation) à `Files:`.

### ACAL630 — CORRIGER
« passer tel quel au verdict existant, chaque refus nommant la ligne » : `normaliser_affectation_imposee` (`services/chaines.py:1385`) lève `AffectationInvalide` avec un seul message, sans ligne ni colonne, à la première erreur ; le message réel pour « abc » est « …doit être un entier (reçu : str) » (l.1436-1440), pas « La chaîne doit être un entier strictement positif ». Le contrat d'ACAL629 exige `{ligne, colonne, message}` et plusieurs refus.
Correction : « le module `import_affectation.py` valide chaque ligne du CSV lui-même (colonnes, entier strictement positif, module en double entre lignes) et produit `refus[]` ; seules les lignes sans refus passent à `normaliser_affectation_imposee`/`verdict_affectation` » ; ou ajouter `services/chaines.py` à `Files:` (`AffectationInvalide` porte `colonne`). Fixer le texte du message attendu en conséquence. Préciser la garde de l'action (lecture : `PeutVoirCalepinage`, rien n'est écrit).

### ACAL631 — CORRIGER (mineur)
« étape Électrique, niveau expert » : `AffectationChaines` est dans l'étape **Panneaux** (`parcoursGuide.js:19`). Remplacer par « étape Panneaux, niveau expert ». Attention de coordination : ACAL647 et ACAL725 (D4) éditent aussi `AffectationChaines.jsx` (609 l.) — fixer l'ordre des `@after`.

### ACAL632 — CORRIGER
Prémisse fausse : « quand les pans dépassent les entrées MPPT d'un onduleur, les modules en trop restent hors chaîne ». Dans `core/electrique/chaines.py:687-697, 566-581`, plus de pans que d'entrées ⇒ les pans PARTAGENT une entrée (alerte `CH_PANS_PARTAGENT_UNE_ENTREE`) et toutes leurs chaînes sont construites ; `reste` (l.736) = modules non divisibles en chaînes égales dans la fenêtre de tension, et `n_mppt` n'y joue que via la surcharge de courant d'entrée (`_surcharge_mppt`, l.420-432). Le cas annoncé (46 modules, 3 pans, onduleur 2 MPPT) rendrait donc `nombre` = 1 si `reste` = 0, alors que les pans partagent une entrée.
Correction : définir le critère à partir des signaux réels : « le plus petit k tel que, à `n_mppt × k` entrées : aucun `CH_PANS_PARTAGENT_UNE_ENTREE`, aucune surcharge de courant, `reste` = 0 » ; réécrire le « Constat » (supprimer « les modules en trop restent hors chaîne ») et le « Given » avec un cas calculé réellement (3 pans > 2 entrées ⇒ alerte de partage). Ajouter à « Listes figées » `docs/openapi-schema.yml` si le décorateur de `views/electrique.py` est étendu à `onduleurs_suggeres` (comme ACAL618).

### ACAL633 — CORRIGER
(1) `champs_entree.py::corps_entree_resserre` (l.95-130) lève `RuntimeError` si une clé de `CHAMPS_ENTREE` n'a pas de forme publiée : ajouter `nombre_onduleurs` à `CHAMPS_ENTREE` sans éditer `champs_entree.py` casse la génération du schéma. Fichier absent de `Files:`. (2) Incohérence : `affectation` lit `evaluer_onduleurs(conception).nombre` (`services/chaines.py:1022-1050`, plafond de dossier) ; accepter « 2 onduleurs » sans que `evaluer_onduleurs`/`dimensionner_onduleurs` (`core/electrique/onduleurs.py:223`) et `raccordement.py` lisent le même nombre publie « onduleur 1, 2 » tout en calculant ratio DC/AC et puissance injectée pour 1 onduleur.
Correction : ajouter `backend/django_core/apps/calepinage/champs_entree.py` à `Files:` (forme `{'type': 'integer', 'minimum': 1, 'maximum': …}` à justifier — borne = nombre de pans ×… ou valeur technique sans chiffre inventé) ; dire que `evaluer_onduleurs` honore `nombre_onduleurs` (ou publier une alerte tant que les deux nombres diffèrent) ; régénérer `docs/openapi-schema.yml`.

### ACAL634 — OK
`EquipementsElectriques.jsx` (174 l.) et son test existent, section `equipements-electriques` déjà dans l'étape Électrique. Dépend d'ACAL632/633 corrigées.

### ACAL635 — CORRIGER
« citer cette température dans la note de calcul ; fini quand … la note la cite » : `services/note_calcul.py` ne lit ni tronçons ni `regle_source` (grep = 0) ; la phrase qui cite la résistivité est `regle_source` de `services/troncons.py::_regle_source` (l.343, 470). Le test (« `regle_source` cite … ») le dit, mais le titre et le « fini quand » parlent d'une « note » inexistante.
Correction : remplacer « la note de calcul » par « la `regle_source` du tronçon (publiée par `GET troncons/`) » dans le titre, le « fini quand » et « Hors périmètre ». Le reste est vrai : `RHO_CUIVRE_20C` (`core/electrique/cables.py:119`), `proposer_section` sans `rho` (l.250), 1 appel dans `troncons.py:456`, registre `CLES_ELECTRIQUE_SOCIETE` (`parametres_cles.py:156`) qui pilote l'écran de réglages (pas de chiffre par défaut ; α = 0,00393 et θ = 70 sont des valeurs de test saisies). Pense à passer `rho` aussi aux deux appels internes de `chute_tension_pct` dans `proposer_section`.

### ACAL636 — OK
Barème `AMPACITE_H1Z2Z2K` : 6 mm² = 70 A, 10 mm² = 98 A (`core/electrique/cables.py:53`) ; 0,8×70 = 56 < 60 ⇒ 10 mm² ; facteur = réglage société sans défaut ; `dimensionner_branches_ac` existe (l.345).

### ACAL641 — CORRIGER
Le défaut est mal attribué : la décision n°8 de `docs/PLAN2.md:111` dit « défaut “le long de la rangée avec retour” » (≈ `aller_retour`), la tâche écrit « défaut : le long de la rangée » ; et SANS motif saisi, le code mesure « la distance du module le plus éloigné au point de collecte » (`services/cables.py:DETAIL_SANS_MOTIF`, `course_de_chaine`), qui n'est aucun des deux motifs. Afficher « Le long de la rangée » comme défaut sans l'envoyer = l'écran dit une chose, la longueur publiée en mesure une autre.
Correction : « aucun motif n'est présélectionné ; tant que rien n'est choisi l'écran affiche le détail publié (`longueur_detail`, « aucun motif de parcours saisi… ») ; choisir un motif l'envoie » (ou demander au fondateur si le défaut 8 doit être `aller_retour` et l'envoyer d'office). `grep motif_parcours|point_collecte frontend/src apps/web/src` = 0 : vrai.

### ACAL642 — CORRIGER
`Files:` incomplète. Le motif par pan se saisit dans `cheminement.pans.<clé>` : (a) son refus 400 `…motif_affectation` se fait dans `services/electrique.py` (validation de `cheminement`, l.690-725, où vit déjà `motif_parcours`) ; (b) `affectation(conception)` n'a accès ni à l'entrée ni aux centres : `PanPose` (`services/chaines.py:98`) n'a pas de centres, il faut les lire dans `_pans_poses(layout)` et passer le motif depuis `conception_du_calepinage` (`electrique.py:1484`).
Correction : ajouter `backend/django_core/apps/calepinage/services/electrique.py` à `Files:` (≤ 15 l. : validation + passage du motif à `concevoir_par_pan`) ; préciser « le motif et les centres sont portés par `PanPose` (champs en fin) ». Appelants de `affectation` : 5 sites, aucun ne change.

### ACAL643 — CORRIGER
« flèche du premier module (n° le plus bas) vers le dernier… repère + au départ et − à l'arrivée » : l'ordre à l'intérieur d'une chaîne n'est pas un câblage publié — `affectation` donne un numéro de chaîne par module, pas une suite électrique (`services/chaines.py:1022-1083`, `_appliquer_imposee` l.1117 ; avec affectation manuelle ou le motif U d'ACAL642, « le plus bas » n'est pas le départ). Imprimer « + / − » sur un plan d'exécution est un fait technique non sourcé.
Correction : « flèche dans le sens de numérotation des modules de la chaîne (du plus petit au plus grand numéro), légende « sens de numérotation — la polarité se vérifie sur site » ; pas de repères + / − » ; ou reporter les repères après ACAL642/ACAL647 quand l'ordre est une donnée. `plan_cablage.py` (fonctions `_plan_de_cablage` l.166, `_forme_de_module` l.309), `PlanDeCablageTest` (`test_calx310_plan_cablage.py:118`) existent.

### ACAL644 — DOUBLON (avec ACAL733, lot D4) + défaut de fond
Même tâche qu'ACAL733 (« accepter et conserver un drapeau optimiseur PAR MODULE dans l'affectation manuelle, servi dans la table », mêmes fonctions `CLES_IMPOSEE`/`normaliser_affectation_imposee`/`_appliquer_imposee`) ; ACAL725 (D4, écran) recoupe ACAL647 (D3). Deux lanes différentes éditeraient `chaines.py` aux mêmes lignes.
Correction : fusionner dans ACAL644 (M1, D3) et supprimer ACAL733, ACAL725 `@after: ACAL644` ; ou l'inverse.
Défaut de fond à corriger dans la tâche gardée : `mismatch_ombrage.py::_chaines_sans_contrainte` (l.412-431) exempte TOUTE la chaîne dès qu'UNE ligne porte `optimiseur` ; or la tâche (et ACAL647) marque seulement les modules ombrés — une chaîne dont 2 modules sur 12 sont optimisés serait exemptée de la contrainte de courant. ACAL724 (D4) prévoit de corriger ça mais n'est pas `@after` de 644. Le « fini quand » (« deux modules d'une chaîne exemptent la chaîne ») consacre l'erreur. Remplacer par « fini quand une chaîne dont TOUS les modules portent un optimiseur est exemptée, et une chaîne partiellement marquée ne l'est pas » + `mismatch_ombrage.py` à `Files:` (ou renvoyer explicitement à ACAL724).

### ACAL645 — CORRIGER
`services/electrique.py::_optimiseurs_du_calepinage` (l.3285) appelle `affectation(conception)` SANS `imposee` (l.3320) : les marques posées par ACAL644 ne sont jamais vues, `ligne.get('optimiseur')` serait toujours vide. Son unique appelant (`resultat_calepinage`, l.1821) connaît l'affectation imposée.
Correction : « passer l'affectation imposée normalisée à `_optimiseurs_du_calepinage` (nouveau paramètre `imposee=()`) puis `affectation(conception, imposee=imposee)` » (≤ 20 l. nettes au lieu de 15). Le reste est vrai (ratio `modules_par_optimiseur`, `CLE_MODULES_PAR_OPTIMISEUR` l.3263, classes de tests citées existent).

### ACAL646 — OK
`_regle_de_chaine` (`services/electrique.py:3650`) compare bien `pmax_wc` d'UN module à `pmax_in_w` (l.3686-3688, code `optimiseur_pmax_in_w`) ; classes `FicheCompleteTest`/`FichePartielleTest` existent (`test_calx211_optimiseur_longueur.py:71,108`) ; le ratio est lu par `CLE_MODULES_PAR_OPTIMISEUR`.

## OPTIONNEL (5 lignes)
- ACAL617 : retirer « ACAL395 … la montera … » (déjà livré, `EtapeElectrique.jsx`), idem ACAL628 « ACAL395 (ouverte) ».
- ACAL611/612 : `synthese_de_publication(None)` doit rendre `None` (publication nulle à chaud).
- ACAL616 : dire si les micro-onduleurs du stock sont exclus de la liste des voisins.
- ACAL611 « Jumeaux » : `assistant.py::_bloc_electrique` lit `verdict_de_conception`, pas `verdict_publiable` (`services/assistant.py:147-155`).
- ACAL641 : `atelier/onglets.js` est dans `Files:` sans modification (aucune entrée nouvelle) — le retirer.
