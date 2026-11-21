# D3 — Électrique : chaînes, onduleurs, câbles, protections, schéma — consolidation des capacités (21/11/2026)

Juge de consolidation D3. Dépôt lu en LECTURE seule (worktree `calpinage-module-enhance-04bba5`, HEAD 5a75a182b), aucun test ni docker lancé. Toutes les preuves ci-dessous sont des `fichier::symbole` relus dans cette session (grep + lecture ciblée). Abréviations : `CE/` = `backend/django_core/core/electrique/`, `SV/` = `backend/django_core/apps/calepinage/services/`, `ET/` = `SV/etapes/`, `FE/` = `frontend/src/features/calepinage/`, `ST/` = `backend/django_core/apps/stock/`.

Propriété vérifiée par `python scripts/check_ownership.py --owner-of` (lancé ici) : tout `CE/`, `SV/`, `FE/`, `apps/calepinage/views/`, `apps/calepinage/selectors.py`, **ainsi que `ST/models_fiche_technique.py`, `ST/importers/fiche_pan_ond.py`, `ST/views/fiche_technique.py` et `apps/ventes/commissioning.py` → calepinage** (`docs/ownership.yml`, bloc `calepinage:` l.197, entrées l.282-292). Autres propriétaires rencontrés : `frontend/src/pages/stock/ProduitForm.jsx` et `ProduitDetail.jsx`, `ST/selectors.py` → **stock** (`docs/plans/PLAN_AUDIT_STOCK.md`) ; `ST/migrations/*` → stock, surface append-only ; `apps/installations/models_chantier.py`, `services.py`, `serializers_commissioning.py`, `frontend/src/pages/installations/ChantierGateTimeline.jsx` → **chantiers** (`docs/plans/PLAN_AUDIT_CHANTIERS.md`) ; `apps/ventes/compatibilites.py` → **devis** (`docs/plans/PLAN_AUDIT_DEVIS.md`).

Barème : **P** = preuves (lanes distinctes, pondérées : forum réel > notes de version > page commerciale), 1-5 · **A** = adéquation à CET utilisateur (résidentiel, toits-terrasses lestés, C&I, sol agricole, pompage, réseau faible, chaleur, non-ingénieures, équipe de pose), 1-3 · **E** = effort S=1, M=2, L=3 · **score = P × A ÷ E**. Les capacités PRÉSENT SANS ÉCRAN passent en tête, quel que soit leur score.

---

## Fiches (classées)

### CAP-D3-01 — Essayer un autre onduleur ou module avant d'appliquer, et comparer 2-3 configurations côte à côte
- **Besoin** : « Je veux voir si un onduleur de plus, de moins, ou mono/bi-MPPT est mieux, sans refaire le projet » ; « essayer un module de remplacement sur les chaînes avant de l'appliquer ».
- **Preuves** : B1 C10 + S066 (PV*SOL « Calculate Inverter Configuration ») ; B3 N31 (SMA « Compare alternatives ») ; B6 R26 (PVcase GM 2.62, Pylon 11/2026, OpenSolar 3.3) et R29 (3 outils) ; B7 U6 (11 lignes, 24 votes, 6 sources) ; B5-de K28 (3 fils) ; B5-fr grappe 22 (6 fils) ; B4 6.1 #10 (VF1096). **7 lanes**. URL : https://help.valentin-software.com/pvsol/en/pages/inverters/configuration/ ; https://manuals.sma.de/SDesign/en-US/14365264011.html ; https://electronics.stackexchange.com/questions/182043/multiple-charge-controllers-on-the-same-solar-panel
- **Qui le fait** : PV*SOL propose plusieurs configurations calculées dans un tableau à comparer ; SMA Sunny Design rend 2-3 alternatives avec ratio et alertes, puis « Appliquer ».
- **Chez nous** : **PRÉSENT SANS ÉCRAN (côté service)** — `SV/electrique.py::evaluation_electrique(calepinage, *, entree=None, layout=None, materiel=None)` évalue « à chaud », sans rien écrire, un matériel AUTRE que celui retenu (prouvé par `apps/calepinage/tests/test_elec_bloquants_onduleur.py` et `test_calx217_incident_isc_regimes.py`, qui passent `materiel=`) ; mais la vue `apps/calepinage/views/electrique.py::evaluer_electrique` ne transmet que `entree` et `layout` — `materiel` n'est jamais lu du corps HTTP. Le dimensionnement ne rend qu'UNE proposition (`CE/onduleurs.py::dimensionner_onduleurs`). Comparer = dupliquer une variante (`SV/variantes.py`).
- **Plus petite version crédible** : l'écran Électrique envoie `materiel` (module, onduleur, optimiseur choisis dans le stock) à `evaluer-electrique` ; le serveur rend le même verdict que pour le matériel retenu (chaînes, bloquants, ratio DC/AC, Pdc max de fiche, écrêtage si simulé) ; une variante « 3 cartes » est générée par le serveur à partir des onduleurs du stock de la société (un onduleur de plus, un de moins, micro si une fiche micro existe), **sans prix** (l'argent reste dans `apps/ventes`). Entrées : fiches du stock (`apps.stock.selectors.specs_for_produit`) ; fiche incomplète ⇒ la carte dit « indéterminé » et nomme le champ.
- **Simplicité** : étape **Électrique**, « essentiel » : un bouton « Comparer d'autres onduleurs » ; le choix par défaut reste automatique ; « Appliquer » écrit le matériel.
- **Tâches** :
  1. Transmettre `materiel` du corps de `POST calepinages/<pk>/evaluer-electrique/` à `evaluation_electrique` ; fini quand un onduleur absent du calepinage rend son propre verdict et que rien n'est persisté (relecture du calepinage inchangée). Fichiers : `apps/calepinage/views/electrique.py`, test dans `apps/calepinage/tests/test_elec_bloquants_onduleur.py`.
  2. Servir 2-3 configurations candidates (`GET calepinages/<pk>/configurations-onduleur/`) tirées des onduleurs du stock de la société ; fini quand chaque candidate porte nombre d'onduleurs, ratio DC/AC, MPPT utilisés, bloquants nommés. Fichiers : `SV/electrique.py`, `CE/onduleurs.py`, contrat `apps/calepinage/contract_samples/` (PACT10 : contrat seul d'abord).
  3. Afficher les cartes et « Appliquer » dans l'étape Électrique ; fini quand appliquer une carte change `materiel` et relance le verdict. Fichiers : `FE/electrique/MaterielElectrique.jsx`. Dépend d'**ACAL395** (écran Électrique unique) ; recoupe **ACAL477** (balayage DC/AC) sans le doubler.
- **Score** : P 5 × A 3 ÷ E 2 = **7,5** — rang **1**

### CAP-D3-02 — Remplir une fiche module/onduleur depuis un fichier PVsyst .PAN/.OND (le parseur existe déjà)
- **Besoin** : « saisir les fiches à la main est une douleur récurrente » ; « où trouver le PAN, quel coefficient de température ? ».
- **Preuves** : B1 V211/V212 ; B3 #62 ; B4 r4 + r15 (FP66690, FP36152, VF10024) ; B5-en groupe 5 (12 fils) ; B5-fr grappe 15 (7 fils) ; B5-de K31 (21 fils) ; B5-nl 16 ; B6 K54 (8 outils) ; B7 U1 (26 lignes, 56 votes, 12 sources). **9 lanes**. URL : https://help.valentin-software.com/pvsol/en/databases/import-pan-files/ ; https://github.com/pvlib/pvlib-python/issues/2504 ; https://help-center.helioscope.com/hc/en-us/articles/8536512814739-SKU-vs-Component-Characterization
- **Qui le fait** : PV*SOL importe des .PAN/.OND par lot et signale les champs non couverts ; HelioScope accepte les PAN comme caractérisation.
- **Chez nous** : **PRÉSENT SANS ÉCRAN** — `ST/importers/fiche_pan_ond.py::parse_pan_ond_bytes`, `::propose_mapping`, `::champs_a_ecrire` (CAL117, commit 2ab55ec4a) + action `ST/views/fiche_technique.py::importer_datasheet` (`POST …/importer-datasheet`, aperçu puis `confirmer=true`, jamais d'écrasement) marquée `# headless: D-ENF15-STOCK-22` ; `grep "importer-datasheet\|datasheet" frontend/src` : aucun appelant. Couverture PARTIELLE : `MODULE_FIELD_MAP` = 8 clés (PNom, Voc, Isc, Vmpp, Impp, Weight, Width, Height), `ONDULEUR_FIELD_MAP` = 6 clés ; coefficients de température volontairement non mappés (unité mV/°C ↔ %/°C). Tests sur un texte synthétique (`ST/test_cal_import_pan_ond.py`, `_upload(…, nom='fixture.pan')`), pas sur des fichiers réels.
- **Plus petite version crédible** : brancher l'existant ; prouver le parseur sur les deux fichiers publics du dépôt pvlib (BSD-3, décision n°6 du 21/11) ; convertir les coefficients mV/°C → %/°C avec le Voc/Isc du MÊME fichier (conversion exacte, aucun chiffre ajouté) en la NOMMANT dans l'aperçu ; ajouter les contrôles de cohérence de U1 (Pmax ≈ Vmp × Imp ; Voc > Vmp ; Isc > Imp) avec refus nommé. Rien d'inventé : une clé non reconnue reste listée.
- **Simplicité** : invisible pour la commerciale ; le responsable catalogue dépose le fichier sur la fiche produit et valide un aperçu en trois listes.
- **Tâches** :
  1. **Réécrire CALX339 et CALX356** (`docs/PLAN2.md:692,710`) : leur constat « aucun parseur » est périmé et CALX356 demande de créer `apps/stock/services_import_pan_ond.py` — ce serait un DOUBLON de `ST/importers/fiche_pan_ond.py`. Nouveau but : étendre l'existant ; fini quand les deux fichiers pvlib publics passent l'aperçu avec la liste des clés non reconnues. Fichiers : `ST/importers/fiche_pan_ond.py`, `ST/test_cal_import_pan_ond.py` (calepinage).
  2. Mapper les coefficients de température par conversion exacte depuis le fichier et le dire ; fini quand `muVocSpec` d'un fichier réel donne `temp_coeff_voc_pct_c` égal à muVocSpec/Voc×100 et que l'aperçu nomme la conversion. Mêmes fichiers.
  3. Contrôles de cohérence de fiche (U1) dans l'aperçu ; fini quand un fichier où Vmp ≥ Voc est refusé en nommant les deux clés. Mêmes fichiers.
  4. Dépôt du fichier depuis le formulaire produit = **CALX357** (déjà planifié) — `frontend/src/pages/stock/ProduitForm.jsx` appartient à **stock** : à router vers `PLAN_AUDIT_STOCK.md` si CALX357 n'est pas drainé depuis PLAN2.
- **Score** : P 5 × A 2 ÷ E 2 = **5** — rang **2**

### CAP-D3-03 — Motif de chaînage (rangée, U, serpentin) pour l'affectation ET le câble ; sens marqué sur le plan
- **Besoin** : « choisir comment la chaîne court sur la rangée, et que la longueur de câble suive ».
- **Preuves** : B3 N11 + #127/#270 (PVcase Stringing : single-row, U, snake, custom ; GM « Smart Stringing ») ; B6 K02 (PVcase 1.54, 7 lignes) ; B1 V087 (PVsyst « attribution automatique : une rangée, en U, 3-5 rangées ») ; décision n°8 de PLAN2 (`docs/PLAN2.md:111`, « défaut le long de la rangée avec retour »). **3 lanes + 1 décision**. URL : https://help.pvcase.com/hc/en-us/articles/44169203196179 ; https://help.pvcase.com/hc/en-us/articles/35594909729043-Fixed-tilt-Stringing
- **Qui le fait** : PVcase propose 4 motifs + motif personnalisé sur une zone ; PVsyst répartit les modules selon une stratégie nommée.
- **Chez nous** : moitié **PRÉSENT SANS ÉCRAN** — `SV/cables.py::course_de_chaine(chaine, panneaux, motif, …)` (CALX218, motifs `MOTIFS_PARCOURS = ('le_long_de_la_rangee', 'aller_retour')`) est lu par `SV/electrique.py` sous `cheminement.pans.<pan>.motif_parcours`, mais `grep "motif_parcours\|le_long_de_la_rangee" frontend/src apps/web/src` = 0 : aucun écran ne le saisit, donc le défaut décidé n'est jamais choisi. Moitié **ABSENT** — l'affectation des modules aux chaînes suit l'ordre du document (`SV/chaines.py::affectation`, `::_rangs_par_groupe` : « ses rangs 1…N dans l'ordre du document ») ; aucun motif de répartition. Le serpentin n'existe que pour NUMÉROTER (`apps/web/src/scripts/roofPro11/numerotation.ts::SensNumerotation`).
- **Plus petite version crédible** : (a) un sélecteur « parcours du câble » par pan dans le cheminement (défaut = décision n°8, écrit dans le document) ; (b) un motif d'affectation par pan (`rangee` / `en_u` / `serpentin`) qui ordonne les modules par leurs centres (`geometry.panels`) avant de remplir les chaînes ; la longueur de câble de CALX218 suit le même ordre. Aucun nombre ajouté.
- **Simplicité** : automatique (défaut décidé) ; le choix des motifs est « expert » dans l'étape Électrique.
- **Tâches** :
  1. Saisir `motif_parcours` par pan dans `FE/electrique/CheminementCables.jsx` ; fini quand choisir « aller-retour » change la longueur publiée du tronçon de chaîne. Fichiers : `FE/electrique/CheminementCables.jsx`, `FE/electrique/entreeElectrique.js`.
  2. Ordonner l'affectation selon un motif par pan ; fini quand, sur un pan 2 × 10, le motif « en U » met les modules 1-10 puis 20-11 dans la même chaîne et que le défaut reproduit l'ordre d'aujourd'hui octet pour octet. Fichiers : `SV/chaines.py`, test dans `apps/calepinage/tests/` (module existant des chaînes).
  3. Dessiner le sens départ/retour sur `plan-cablage.pdf/.dxf` ; fini quand chaque chaîne porte une flèche de départ. Fichier : `SV/documents/plan_cablage.py`.
- **Score** : P 3 × A 2 ÷ E 2 = **3** — rang **3**

### CAP-D3-04 — Optimiseur seulement sur les modules ombrés (et limite d'entrée de l'optimiseur multi-modules)
- **Besoin** : « équiper 2 ou 6 modules ombrés (lucarne, garage) et voir le gain, pas tout le projet » ; « ne pas dépasser la limite d'entrée (2 modules sur 300 W, 15 A) ».
- **Preuves** : B5-de P4 / K12 (28 fils, 45 voix, passe 2 +37 lignes) ; B5-es #2, #24, K37 (7 fils) ; B3 #88, #266 (Reonic) ; B5-nl 8 ; B7 U10 (17 lignes, 19 votes) ; B6 K65 (7 outils). **6 lanes**. URL : https://forum.valentin-software.com/topic/9208-optimierer-an-einzelmodulen-tigo/ ; https://www.plcforum.it/f/topic/310609-inverter-fronius-con-errore-306-e-307-dopo-installazione-ottimizzatori-tigo-mm-2es50-con-sole-il-forte/ ; https://docs.reonic.com/docs/en/offers-plan-pv-heatmap
- **Qui le fait** : Huawei (optimiseurs seulement là où il y a de l'ombre), Reonic (optimiseur par panneau au clic), PV*SOL (contournement par surfaces séparées).
- **Chez nous** : **PRÉSENT SANS ÉCRAN pour le consommateur, ABSENT pour le producteur** — `ET/mismatch_ombrage.py` exempte déjà une chaîne dont UNE ligne d'affectation porte `optimiseur`/`micro_onduleur` (`CHAMPS_SANS_CONTRAINTE`, lu ligne par ligne), mais rien ne pose ce drapeau : `SV/chaines.py::CLES_IMPOSEE = ('module', 'chaine', 'mppt', 'onduleur')`, et l'optimiseur est déclaré pour tout le document (`::_optimiseur_du_document`). Limites d'entrée : **PRÉSENT** pour UN module (`SV/electrique.py::_regle_de_chaine` compare `voc_v`/`isc_a`/`pmax_wc` à `v_in_max`/`i_in_max_a`/`pmax_in_w`) ; **ABSENT** pour un optimiseur à plusieurs modules (aucune multiplication par `modules_par_optimiseur` dans ce contrôle). Compatibilité optimiseur ↔ onduleur : **ABSENT partout** (`grep optimiseur apps/ventes/compatibilites.py` = 0 ; la lane B5-de §10 se trompait).
- **Plus petite version crédible** : un drapeau `optimiseur` par module dans l'affectation imposée ; la carte d'accès solaire propose les modules sous un seuil SAISI par la société (réglage, valeur + source ; sans seuil, aucune proposition) ; le comptage CALX212 ne compte que les modules marqués quand le marquage existe ; le contrôle d'entrée multiplie par `modules_par_optimiseur` publié (sinon « non vérifiable », comme aujourd'hui).
- **Simplicité** : étape **Électrique**, phrase automatique « 6 modules ombrés pourraient recevoir un optimiseur » + un bouton ; rien à saisir.
- **Tâches** :
  1. Accepter la clé `optimiseur` par module dans `normaliser_affectation_imposee` et la recopier dans `affectation` ; fini quand une chaîne avec 2 modules marqués sort de l'étape mismatch comme exemptée. Fichiers : `SV/chaines.py`, `ET/mismatch_ombrage.py` (lecture déjà là).
  2. Compter les optimiseurs sur les seuls modules marqués ; fini quand 6 modules marqués à 1 par optimiseur rendent 6. Fichier : `SV/electrique.py` (bloc CALX212).
  3. Contrôle d'entrée × `modules_par_optimiseur` ; fini quand deux modules de 220 Wc sur une entrée de 400 W sortent « AU-DESSUS ». Fichier : `SV/electrique.py::_regle_de_chaine`.
  4. Proposer les modules candidats sous un seuil société et les marquer au clic ; fini quand, seuil vide, aucune proposition n'apparaît. Fichiers : `FE/plan/AffectationChaines.jsx`, `SV/parametres_cles.py`.
  - Hors domaine : le gain d'énergie affiché vient de la chaîne de pertes (D4) ; la compatibilité de marque optimiseur ↔ onduleur passe par CAP-D3-06 (champ de fiche).
- **Score** : P 5 × A 2 ÷ E 2 = **5** — rang **4**

### CAP-D3-05 — Valeurs attendues par chaîne (Voc, Isc, Pmax) servies à la fiche de recette, et seuil d'isolement saisi par la société
- **Besoin** : « donner au poseur la Voc, l'Isc et la Pmax attendues par chaîne et rapprocher la mesure » ; « un procès-verbal de réception où l'écart sort en rouge sans calcul ».
- **Preuves** : B5-es #10 (7 fils) + §5.1 (Riso 20→15 MΩ, 1,43 MΩ) + K22 ; B5-de P22 / K51 (12 fils, passe 2) ; B5-de K51 passe 1 (strings inversés, rapport de contrôle faux). **2 lanes, forum réel**. URL : https://www.energeticambiente.it/forum/fonti-di-energia-rinnovabile/fotovoltaico/tecnica-componentistica-e-installazione/17270-tensioni-sballate-sulle-stringhe ; https://www.energeticambiente.it/threads/60149/
- **Qui le fait** : aucun outil lu ne livre les valeurs attendues par chaîne (B5-es K22 : « aucun outil ») ; les installateurs les calculent à la main.
- **Chez nous** : **PARTIEL** — la fiche de recette EXISTE côté chantiers (la lane B5-de « aucune fiche » se trompait : elle n'a cherché que dans le calepinage) : `apps/installations/models_chantier.py::CommissioningRecord` (IEC 62446-1 : `isolement_mohm`, `isolement_ok`, `continuite_terre_ohm`, `polarite_ok`…) et `::CommissioningIVReading` (`voc_attendu_v`, `isc_attendu_a`, `pmax_attendu_w`, `ecart_pmax_pct` jugé contre le seuil SAISI `recette_ecart_pmax_pct`), écran `frontend/src/pages/installations/ChantierGateTimeline.jsx` (champs « Voc attendu (V) »…). Manques : les valeurs attendues se TAPENT à la main — aucun sélecteur de `apps/calepinage/selectors.py` ne les sert ; `isolement_ok` est un booléen saisi, aucun seuil d'isolement société (grep `seuil_isolement` = 0).
- **Plus petite version crédible** : un sélecteur calepinage rend, par chaîne du calepinage retenu, N modules, Voc et Isc STC × N, Pmax STC × N, et — si le technicien saisit la température et l'éclairement — les mêmes corrigées par les coefficients de la fiche (Isc corrigé seulement quand le coefficient Isc existe, cf. CAP-D3-06 ; sinon « non corrigé » nommé). La fiche de recette se pré-remplit ; un seuil d'isolement saisi par la société (valeur + source) juge `isolement_ok`.
- **Simplicité** : rien pour la commerciale ; le technicien ne tape que la mesure.
- **Tâches** :
  1. Servir `valeurs_attendues_par_chaine(installation)` ; fini quand une chaîne de 10 modules à Voc 49,5 V rend 495 V STC et nomme ses sources. Fichiers : `apps/calepinage/selectors.py`, `SV/chaines.py` (calepinage).
  2. Pré-remplir les `CommissioningIVReading` depuis ce sélecteur — **à router vers `PLAN_AUDIT_CHANTIERS.md`** (`apps/installations/services.py`, `serializers_commissioning.py`, `ChantierGateTimeline.jsx`, propriétaire chantiers) ; dépend de la tâche 1 (`@after`).
  3. Seuil d'isolement saisi par la société et `isolement_ok` calculé — **chantiers** (même plan).
- **Score** : P 3 × A 3 ÷ E 2 = **4,5** — rang **12**

### CAP-D3-06 — Champs de fiche dont les modèles électriques ont besoin
- **Besoin** : pouvoir modéliser diodes, déclassement, MPPT réellement indépendants, compatibilité optimiseur/onduleur, Isc corrigé — sans jamais inventer.
- **Preuves** : B1 C21 (+ C03, C07, C17), V210, V212 ; B5-nl #3 (« entrées MPPT indépendantes ? ») et 1b ; B5-fr R6 ; B7 U29, U1 ; B5-de §10 (compatibilité optimiseur/onduleur). **5 lanes**. URL : https://www.pvsyst.com/help/component-database/photovoltaics-modules/pv-modules-main-interface/pv-modules-additional-data/index.html ; https://www.zonstraal.be/forum/viewtopic.php?t=20222
- **Qui le fait** : PVsyst (« Additional data » : diodes, cellules ; onduleur « Output parameters » Pnom(T)) ; PV*SOL (cellules, diodes, adaptation MPP).
- **Chez nous** : **ABSENT** — `ST/models_fiche_technique.py::FicheTechnique` porte `temp_coeff_voc_pct_c`, `temp_coeff_pmax_pct_c`, `noct_c`, `ond_n_mppt`, `ond_entrees_par_mppt`, `ond_v_demarrage_v`, `ond_dc_max_kwc`, `ond_s_max_kva`, `opt_*`… mais `grep -i "diode|cellule|derat|déclass"` ne rend que `techno_cellule` (texte) : ni nombre de diodes, ni cellules en série, ni coefficient Isc, ni Pnom(T), ni rendement d'adaptation MPP, ni drapeau « entrées MPPT indépendantes », ni liste d'onduleurs compatibles d'un optimiseur. **DÉJÀ PLANIFIÉ en partie** : ACAL464 (GATED) attend coefficient Isc + cellules en série ; **sa raison de gel (« à router vers le plan stock ») est fausse** : le modèle appartient au calepinage (`docs/ownership.yml` l.283) ; seule la migration (stock, append-only) et le formulaire (`ProduitForm.jsx`, stock) sortent du domaine.
- **Plus petite version crédible** : 7 champs optionnels (`diodes_derivation`, `cellules_serie`, `temp_coeff_isc_pct_c`, `ond_pnom_reduite_debut_c` + `ond_pnom_pente_pct_c` (ou une courbe JSON), `ond_rendement_mpp_pct`, `ond_mppt_independants` booléen, `opt_onduleurs_compatibles` JSON de références) ; vide = étape ou contrôle omis avec motif ; servis par `selectors_fiche_technique`.
- **Simplicité** : invisible de la commerciale ; rempli à l'import PAN/OND (CAP-D3-02) ou par le responsable catalogue.
- **Tâches** :
  1. Ajouter les champs au modèle + sérialiseur + sélecteur ; fini quand `specs_for_produit` les rend et qu'une fiche vide les rend `null`. Fichiers : `ST/models_fiche_technique.py`, `ST/serializers_fiche_technique.py`, `ST/selectors_fiche_technique.py` (calepinage) + migration `ST/migrations/` (append-only stock).
  2. Lire `ond_mppt_independants = faux` dans le chaînage : les entrées traitées comme une seule, alerte nommée ; fini quand un onduleur 2 MPPT non indépendants reçoit les deux orientations sur une seule entrée logique. Fichiers : `SV/chaines.py::_verdict_mppt`, `CE/chaines.py::_allouer_mppt`.
  3. Contrôler `opt_onduleurs_compatibles` ; fini quand un optimiseur dont la liste ne contient pas l'onduleur retenu rend un bloquant nommé, et liste vide = « non vérifiable ». Fichier : `SV/electrique.py`.
  4. Saisie dans le formulaire produit — **à router vers `PLAN_AUDIT_STOCK.md`** (`ProduitForm.jsx`).
  5. Corriger le libellé de gel d'ACAL464 (raison de propriété fausse) — docs.
- **Score** : P 4 × A 2 ÷ E 2 = **4** — rang **7**

### CAP-D3-07 — Le plus petit nombre d'onduleurs qui câble tous les modules, et quel onduleur reçoit quelle chaîne
- **Besoin** : « proposer le plus petit nombre d'onduleurs de la société dont les entrées câblent tout » ; « savoir quelles chaînes vont sur quel onduleur ».
- **Preuves** : B2 #14 et A35 (Aurora AutoStringer, programmation en nombres entiers) ; B3 #41 (HelioScope zones de câblage) ; B7 grappe 72 ; B5-en groupe 29/H (SolarQuotes ≈ 15 commentaires sur les MPPT ; PV*SOL sélection auto). **4 lanes**. URL : https://aurorasolar.com/?p=13829 ; https://help-center.helioscope.com/hc/en-us/articles/8198405358227
- **Qui le fait** : Aurora choisit onduleurs et chaînes en une passe ; HelioScope compte les onduleurs pour viser un ratio.
- **Chez nous** : **ABSENT** — `CE/onduleurs.py::nombre_onduleurs` ne connaît que le plafond de DOSSIER (« Sans plafond, un seul onduleur ») ; les modules en trop restent « hors chaîne » (`chainage.reste`, `SV/export_tableur.py::_table_chaines`) ; quand il y a plusieurs onduleurs, `SV/chaines.py::affectation` met `onduleur = None` (« le noyau ne dit PAS lequel reçoit quelle chaîne »).
- **Plus petite version crédible** : partir de 1 onduleur du modèle retenu et monter jusqu'à ce que `chainage.reste` = 0 sans bloquant (borne : nombre de pans × MPPT) ; numéroter les onduleurs et répartir les chaînes en remplissant les MPPT dans l'ordre des pans. Aucun coût (règle argent).
- **Simplicité** : automatique ; une phrase « 2 onduleurs sont nécessaires pour câbler les 46 modules » à accepter.
- **Tâches** :
  1. Calculer le nombre minimal d'onduleurs du modèle retenu ; fini quand 46 modules qui laissent 6 hors chaîne avec 1 onduleur en laissent 0 avec 2. Fichiers : `CE/onduleurs.py`, `SV/chaines.py::evaluer_onduleurs`.
  2. Numéroter l'onduleur de chaque chaîne ; fini quand `affectation[].onduleur` n'est plus `null` avec 2 onduleurs. Fichier : `SV/chaines.py`.
  3. Afficher la suggestion et l'accepter ; fini quand accepter écrit le nombre dans l'entrée électrique. Fichier : `FE/electrique/EquipementsElectriques.jsx`.
- **Score** : P 3 × A 3 ÷ E 2 = **4,5** — rang **13**

### CAP-D3-08 — Les chaînes survivent à un retrait de module, un changement de module/onduleur ou de pas, et se ré-ancrent
- **Besoin** : « retirer un module ou changer la pente efface le câblage » (PV*SOL, demandé 2023→2026) ; « remplacer 300 modules 430→440 W sans refaire ».
- **Preuves** : B4 r3 + S12 (VF6842, VF1096, VF10692) ; B5-en #2 et #17 + groupe C (VF2901, VF1505, VF7917) ; B5-de K16 (6 fils) et K33 ; B6 R26 (en partie) ; B2 #16 / B6 K13 (dupliquer un bloc câblé : la part « chaînes copiées »). **5 lanes**. URL : https://forum.valentin-software.com/topic/6842-modul-entfernen-ohne-verschaltung-und-kabelpl%C3%A4ne-zu-verlieren/ ; https://forum.valentin-software.com/topic/1505-changing-module-mounting-inclination-on-existing-simulation/
- **Chez nous** : **PARTIEL** — l'affectation automatique est recalculée à chaque lecture ; l'affectation manuelle est indexée par la clé stable `SV/chaines.py::PanPose.cle_module` (`<clé du pan>#<n>`, numéros `panels[].n` quand le document est numéroté, sinon le RANG) et les lignes orphelines sont publiées, jamais effacées (`::_affectation_obsolete`, ACAL265). Non prouvé : (a) document NON numéroté + retrait au milieu ⇒ les rangs glissent et l'affectation manuelle se décale EN SILENCE ; (b) changement de pas/inclinaison qui régénère les panneaux et leurs numéros. Rien ne copie les chaînes avec un bloc dupliqué.
- **Plus petite version crédible** : test d'abord ; puis, quand une clé manuelle ne retrouve pas son module, ré-ancrer par le centre le plus proche (position) au lieu du numéro, et nommer chaque ligne ré-ancrée ou retombée dans un message.
- **Simplicité** : aucun écran ; un message « 3 modules ont changé de chaîne, voir Affectation ».
- **Tâches** :
  1. Écrire les deux tests de comportement (retrait au milieu non numéroté ; pas changé) ; fini quand ils échouent ou passent en le disant. Fichier : module de test existant des chaînes (`apps/calepinage/tests/`).
  2. Ré-ancrer par position ; fini quand le retrait du module 3 sur 10 garde les modules 4-10 dans leur chaîne manuelle. Fichier : `SV/chaines.py`.
  3. Copier les affectations avec un bloc dupliqué (part D3 de B2 #16 ; la duplication elle-même est D2). Fichiers : `SV/chaines.py`, constructeur D2.
- **Score** : P 4 × A 2 ÷ E 2 = **4** — rang **14**

### CAP-D3-09 — Déclassement thermique de l'onduleur (pays chaud) — part fiche et contrôle
- **Besoin** : « savoir ce que la chaleur coûte à l'onduleur ou au micro » ; « −20 % de puissance à 45 °C dans le désert marocain ».
- **Preuves** : B1 C03 + V099 ; B5-fr R6 + grappe 21 (6 fils, référentiel tunisien) ; B6 K64 ; B7 U29 + grappe 66 ; B5-en P2.2 (chaleur, bornes à 90 °C). **5 lanes**. URL : https://forum-photovoltaique.fr/viewtopic.php?t=78567 ; https://github.com/pvlib/pvlib-python/issues/2360
- **Chez nous** : **ABSENT** — aucun champ (`grep derat|déclass` sur la fiche = 0) ; `ET/onduleur.py` ne lit aucune température ; l'écrêtage compare à une puissance AC constante (`ET/ecretage.py`).
- **Plus petite version crédible** : avec les champs de CAP-D3-06 (début de réduction + pente, publiés par le fabricant), un verdict « puissance disponible à la température maximale du site » (la température du site existe déjà, `SV/temperatures_tmy.py`) ; sans champs : « déclassement non modélisé — fiche incomplète ». L'application heure par heure dans l'écrêtage est **D4**.
- **Simplicité** : automatique ; jamais une saisie demandée à la commerciale.
- **Tâches** : 1. Verdict de puissance à Tmax du site ; fini quand une fiche « −2 %/°C au-delà de 45 °C » et un site à 50 °C rendent 90 % de Pnom nommés. Fichiers : `CE/onduleurs.py`, `SV/electrique.py`. Dépend de CAP-D3-06 t1. 2. (D4) étape horaire dans `ET/ecretage.py`.
- **Score** : P 4 × A 3 ÷ E 2 = **6** — rang **8** (juste après son prérequis CAP-D3-06).

### CAP-D3-10 — Contrôle rapide d'une chaîne sans dessin
- **Besoin** : module + onduleur + N modules + température mini → verdict Voc à froid, plage MPPT, courant, DC/AC, avant tout calepinage.
- **Preuves** : B5-nl #4 (3 fils elektroda) ; B7 U7 (15 lignes, 38 votes, 4 sources) ; B7 grappe 14. **2 lanes**. URL : https://www.elektroda.pl/rtvforum/topic4112334.html ; https://diy.stackexchange.com/questions/305415/what-can-cause-a-24-volt-solar-panel-to-output-40-volt
- **Chez nous** : **PARTIEL** — `apps/ventes/compatibilites.py::verdict_panneau_onduleur` (propriétaire devis) balaie les longueurs plausibles d'un couple et s'affiche dans `frontend/src/pages/stock/ProduitDetail.jsx` (`stockApi.getCompatibilites`), mais avec des températures FIXES (`_TEMPERATURES_DIMENSIONNEMENT` ← `apps/ventes/solar_design.py::DEFAULT_COLD_TEMP_C = -5.0`), sans N choisi ni température du site. Le noyau `CE/chaines.py::fenetre_admissible` est pur et suffit.
- **Plus petite version crédible** : un mini-formulaire (module, onduleur, N, ville ou température saisie) qui appelle `fenetre_admissible` + les verdicts de tension/courant ; la température vient du site quand un lead est choisi (TMY déjà servi), sinon saisie obligatoire nommée.
- **Simplicité** : accessible depuis la fiche équipement et l'étape Électrique, « essentiel ».
- **Tâches** : 1. Endpoint `POST calepinage/controle-chaine/` sur le noyau ; fini quand 22 modules Voc 49,5 V à −5 °C sur 1 000 V sortent rouge avec la borne nommée. Fichiers : `apps/calepinage/views/electrique.py`, `CE/chaines.py`. 2. Formulaire. Fichier : `FE/electrique/` (nouveau composant dans le dossier existant). 3. (optionnel, plan DEVIS) faire lire la température du site par `compatibilites.py`.
- **Score** : P 3 × A 2 ÷ E 1 = **6** — rang **9**

### CAP-D3-11 — Plan de câblage pour l'électricien : tension DC max par chaîne, consignes DC, repères + / −, couleur par MPPT
- **Besoin** : « afficher sur le plan la tension DC max à froid de chaque chaîne, ‘sous tension dès qu'éclairé', l'ordre AC puis DC » ; « repères + / − et sens départ/retour » ; « couleur par MPPT ».
- **Preuves** : B5-es #7 (7 fils) + K21 (16 fils, sécurité) ; B5-de P5 (part polarité) + K51 ; B6 R43 (OpenSolar 3.8, PVcase 1.50). **3 lanes**. URL : https://www.solarweb.net/forosolar/fotovoltaica-sistemas-conectados-red/42669-nueva-instalacion-autoconsumo-conectada-red-novato-muchas-dudas.html ; https://www.photovoltaikforum.com/thread/266185-stringplanung-ost-west-31-module/
- **Chez nous** : **ABSENT** — `grep -i "voc|tension" SV/documents/plan_cablage.py` = 0 ; la Voc à froid par chaîne est pourtant calculée (`CE/chaines.py::_verdicts_tension`) ; teinte par chaîne seulement (`SV/chaines.py::PALETTE_CHAINES`).
- **Plus petite version crédible** : légende de `plan-cablage.pdf` : par chaîne, N modules, Voc à froid (température citée), Isc ; texte de consigne SAISI par la société (comme `SV/documents/manuel_proprietaire.py`) ; famille de teintes par MPPT.
- **Simplicité** : ajouté d'office au plan ; rien à saisir sauf le texte société une fois.
- **Tâches** : 1. Légende tension/courant par chaîne ; fini quand chaque chaîne du plan porte sa Voc à froid et sa température. Fichier : `SV/documents/plan_cablage.py`. 2. Consigne DC société (réglage valeur + source) imprimée. Fichiers : `SV/parametres_cles.py`, `plan_cablage.py`. 3. Teinte par MPPT. Fichier : `SV/chaines.py::_colorer`.
- **Score** : P 3 × A 3 ÷ E 1 = **9** — rang **5**

### CAP-D3-12 — Boucles DC : surface mesurée et retour accolé
- **Besoin** : « un plan qui évite les grandes boucles et prévient quand elles sont larges » ; polarité anti-induction.
- **Preuves** : B5-de P12 / K10 (37 fils, 58 voix) ; B3 N12 + #129 (PVcase « sans boucles d'induction, polarité ») ; B6 K07/R60. **3 lanes**. URL : https://www.photovoltaikforum.com/thread/247114-pvsol-und-leiterschleifen/ ; https://help.pvcase.com/hc/en-us/articles/44231655047443
- **Chez nous** : **ABSENT** — `grep -i "boucle|induction" CE SV` : seulement des boucles de programme ; la seule règle est la longueur critique du parafoudre (`CE/protections.py::LONGUEUR_DC_SANS_PARAFOUDRE_M`). **DÉJÀ PLANIFIÉ** : le tracé proposé = ACAL472 (la polarité et la surface n'y sont pas).
- **Plus petite version crédible** : après ACAL472, surface de boucle de chaque chaîne = aire entre aller (ordre des modules) et retour (cheminement) ; avertissement au-delà d'un seuil SAISI par la société avec sa source ; option « retour accolé à l'aller ».
- **Tâches** : 1. Surface de boucle par chaîne publiée ; fini quand une rangée aller-retour accolée rend ≈ 0 et un retour par l'autre rive rend largeur × longueur. Fichiers : `SV/troncons.py`, `SV/cables.py`. 2. Seuil société + alerte. 3. Option polarité dans le tracé (extension d'**ACAL472**).
- **Score** : P 3 × A 2 ÷ E 2 = **3** — rang **15**

### CAP-D3-13 — Résistivité du cuivre à la température de service et facteur de regroupement
- **Besoin** : « calculer la chute avec la résistivité à 70 ou 90 °C (jusqu'à 28 % d'écart) et un facteur de groupement quand plusieurs circuits partagent un conduit ».
- **Preuves** : B5-es #6 (4 fils) + K06 (11 fils) ; B6 K06 (réserve) ; B7 grappe 25. **3 lanes**. URL : https://www.solarweb.net/forosolar/fotovoltaica-sistemas-conectados-red/9615-seccion-del-cableado-fotovoltaico.html ; https://www.solarweb.net/forosolar/fotovoltaica-sistemas-conectados-red/56610-dimensionado-cables-protecciones-cc.html
- **Chez nous** : **ABSENT** — `CE/cables.py::chute_tension_v(…, rho=RHO_CUIVRE_20C)` avec `RHO_CUIVRE_20C = 0.01851` seulement ; la docstring du module dit que regroupement et ambiance chaude « relèvent de l'étude d'exécution, hors moteur ». (B5-en P2.2 citait `cables.py:23` comme PRÉSENT : c'est cette phrase d'exclusion.)
- **Plus petite version crédible** : ρ(θ) = ρ20 × (1 + α (θ − 20)) avec α et θ SAISIS ou lus dans `SV/norme.py::coefficients_publies` (source obligatoire) ; facteur de regroupement saisi par la société (valeur + source) appliqué à Iz ; la note de calcul cite la température retenue ; sans saisie, comportement d'aujourd'hui et mention « résistivité à 20 °C ».
- **Tâches** : 1. Paramètre ρ(θ) sourcé ; fini quand θ = 70 °C saisi avec source change la chute publiée et que la note la cite. Fichiers : `CE/cables.py`, `SV/norme.py`, `SV/cables.py`. 2. Facteur de regroupement saisi appliqué à Iz. Mêmes fichiers.
- **Score** : P 3 × A 3 ÷ E 1 = **9** — rang **6**

### CAP-D3-14 — Une chaîne qui court sur deux pans de même orientation
- **Besoin** : toits plats C&I découpés par des obstacles en plusieurs zones identiques ; ne pas perdre de modules au reliquat.
- **Preuves** : B6 R9 (PVcase GM 2.53, SolarEdge 2020, PVsyst 7.1.0 — 3 outils) ; B5-de K20 (en partie). **2 lanes, notes de version**. URL : https://help.pvcase.com/hc/en-us/articles/35594909729043-Fixed-tilt-Stringing
- **Chez nous** : **ABSENT (refusé)** — `SV/chaines.py::_groupes_electriques` (« UN groupe par pan, jamais deux mélangés ») et `::verdict_affectation` refuse « Chaîne n : elle traverse les pans … — une chaîne reste sur UN pan », même à orientation identique.
- **Plus petite version crédible** : fusionner deux pans en un groupe électrique quand azimut ET inclinaison sont égaux à une tolérance SAISIE par la société et que leur `source_orientation` est connue (la règle de prudence d'aujourd'hui reste pour une orientation inconnue).
- **Tâches** : 1. Groupe multi-pans à même orientation ; fini quand deux zones de 7 modules en chaînes de 14 laissent 0 hors chaîne. Fichiers : `SV/chaines.py`, `CE/chaines.py`. 2. Lever le refus de `verdict_affectation` dans ce seul cas.
- **Score** : P 2 × A 3 ÷ E 2 = **3** — rang **16**

### CAP-D3-15 — Schéma de secours (îlotage) dans le schéma unifilaire
- **Besoin** : « ajouter la branche de secours (inverseur, séparation du compteur, protection du circuit secouru) et la liste des appareils secourus ».
- **Preuves** : B5-de P21 / K53 (22 fils, 31 lignes, passe 2). **1 lane, forum réel** ; adéquation réseau faible (coupures au Maroc). URL : voir B5-de §8 code BACKUP (board 220 Notstrom de photovoltaikforum.com).
- **Chez nous** : **ABSENT** — stratégie `backup` dans `SV/batterie.py` (D5) ; `grep -i "secours|backup|inverseur" SV/sld.py CE/schema.py` = 0 (seules des « bascules » de format de planche).
- **Plus petite version crédible** : un bloc « Secours » dans `CE/schema.py` dessiné seulement quand la stratégie `backup` est retenue ; temps de bascule et sortie secourue lus sur la fiche onduleur (omis et nommés si absents) ; liste des charges secourues = celles déjà saisies en D5.
- **Tâches** : 1. Bloc secours ; fini quand un calepinage `backup` montre l'organe de bascule et un départ « circuits secourus ». Fichiers : `CE/schema.py`, `SV/sld.py`. Part D5 : la liste et la durée des charges.
- **Score** : P 2 × A 3 ÷ E 2 = **3** — rang **17**

### CAP-D3-16 — Verdict « chaîne, micro-onduleur ou optimiseur » selon le toit, seuils de la société
- **Preuves** : B5-nl #1 (3 pages) + 8 ; B4 P8 (FP27653, FP68814) ; B5-fr grappe 17 (7 fils) ; B5-de K12. **4 lanes**. URL : https://zelfopwekken.nl/kennisbank/omvormers/omvormers-meerdere-dakvlakken
- **Chez nous** : **ABSENT** — `SV/micro_onduleurs.py` dimensionne des branches AC (CALX209) mais aucune recommandation ; `ET/mismatch_ombrage.py` publie déjà les bornes de perte par chaîne (entrée utilisable).
- **Plus petite version crédible** : une ligne « plutôt chaîne / micro / optimiseur » à partir de : nombre d'orientations distinctes, pire perte d'ombrage électrique de chaîne (déjà calculée), nombre de modules ; les SEUILS sont saisis par la société (vides = aucun verdict, la ligne dit pourquoi). La perte mesurée vient de D4.
- **Tâches** : 1. Verdict + seuils société ; fini quand, seuils vides, la ligne nomme les seuils manquants. Fichiers : `SV/electrique.py`, `SV/parametres_cles.py`.
- **Score** : P 3 × A 2 ÷ E 2 = **3** — rang **18**

### CAP-D3-17 — Micro-onduleurs ≠ injection zéro, et place/sens de la pince de mesure (CT)
- **Besoin** : « les micro-onduleurs ne limitent pas l'export » ; « pince CT posée à l'envers, sur les mauvaises bornes ou oubliée ».
- **Preuves** : B5-fr R12 (4 fils) + grappe 10 (8 fils) ; B5-es #25 (6 fils). **2 lanes**. URL : https://forum-photovoltaique.fr/viewtopic.php?t=82112 ; https://www.energeticambiente.it/threads/inverter-ibrido-6kw-deye-modalita-zero-immmmissione-tramite-ct.2266832/
- **Chez nous** : **ABSENT** — aucun avertissement micro + plafond (`grep -i "micro.*injection|passerelle"` sur `SV/raccordement.py`, `SV/micro_onduleurs.py`, `SV/autoconsommation.py` = 0) ; le schéma ne dessine un « Limiteur d'injection » que sur le chemin C&I MT (`CE/schema.py`, bloc `limiteur_injection`), sans pince ni sens. Fiche : `ond_limitation_export`, `ond_compteurs_compatibles` existent (lisibles).
- **Plus petite version crédible** : stratégie « plafond » ou « zéro » + régime micro sans dispositif de limitation déclaré ⇒ verdict « limite non garantie » nommant la cause ; dès que la limitation est choisie, le schéma dessine la mesure juste après le compteur avec une flèche de sens, et la nomenclature ajoute la ligne « capteur de mesure (fiche : `ond_compteurs_compatibles`) ».
- **Tâches** : 1. Verdict micro/plafond ; fini quand micro + zéro injection sans limiteur rend une alerte nommée. Fichier : `SV/raccordement.py`. 2. Pince CT au schéma + nomenclature. Fichiers : `CE/schema.py`, `CE/nomenclature.py`. (La limite elle-même est D5.)
- **Score** : P 2 × A 3 ÷ E 1 = **6** — rang **10**

### CAP-D3-18 — Schéma unifilaire : modèle par distributeur et édition libre (ajouter, tourner un organe, légende)
- **Preuves** : B3 N21 + #91/#92 (Reonic) ; B5-de P9 / K15 (5 fils, passe 2 : 48 lignes dossier) ; B6 R19 (Pylon, OpenSolar, PVcase) et R34 ; B5-es #3 (21 fils, part schéma) ; B1 S077. **5 lanes**. URL : https://docs.reonic.com/docs/en/offers-plan-circuit-plan-templates ; https://forum.valentin-software.com/topic/10077-kabel-schaltplan-vnb-w%C3%BCnsche/
- **Chez nous** : **PARTIEL** — gabarit par PAYS `SV/sld.py::gabarit_de_schema` (`fr` / `societe` / `neutre`, CALX237) ; édition limitée aux `RUBRIQUES = ('libelles', 'reperes', 'positions')` d'organes existants (`::edition_sld`, `::_valider_edition`) ; « typique de 10 » présent. Absents : modèle par distributeur (ONEE, régies, SRM), ajout/rotation d'un organe, légende éditable.
- **Plus petite version crédible** : un gabarit SOCIÉTÉ nommé par distributeur (organes en plus, mentions, cartouche) SAISI par la société — aucune exigence marocaine inventée ; distributeur proposé depuis l'adresse du lead ; rubrique `ajouts` (organe du catalogue de symboles existant + position).
- **Tâches** : 1. Gabarit par distributeur ; fini quand deux distributeurs saisis donnent deux planches différentes pour le même calepinage. Fichiers : `SV/sld.py`, `SV/gabarits.py`. 2. Rubrique `ajouts` (organe + position, refus nommé hors planche). Fichiers : `SV/sld.py`, `FE/SchemaUnifilairePanel.jsx`. La liste des pièces du dossier par distributeur relève du domaine Documents.
- **Score** : P 4 × A 2 ÷ E 3 = **2,7** — rang **24**

### CAP-D3-19 — Feuille « vérification des chaînes » dans le classeur XLSX, formules écrites en texte
- **Preuves** : B5-es #4 (6 fils). **1 lane**. URL : https://www.solarweb.net/forosolar/fotovoltaica-sistemas-conectados-red/2407-pros-contras-pvsyst-pvsol.html
- **Chez nous** : **ABSENT** — `SV/export_tableur.py::_table_chaines` rend des valeurs seules (modules, par chaîne, nombre, reste, onduleurs, MPPT) ; les formules vives sont neutralisées (`neutralize_rows`).
- **Plus petite version crédible** : feuille `verification` : une ligne par contrôle (Voc à froid, longueur max, Vmp à chaud, Isc par MPPT, DC/AC) avec valeur, borne, température et la formule en TEXTE (« = N × Voc × (1 + β (Tmin − 25)) »).
- **Tâches** : 1. Feuille ; fini quand chaque verdict de `bloc_electrique` a sa ligne et sa formule texte, et qu'aucune cellule ne commence par « = » interprétable. Fichier : `SV/export_tableur.py`.
- **Score** : P 1 × A 2 ÷ E 1 = **2** — rang **25**

### CAP-D3-20 — DXF : modules en blocs nommés par chaîne et onduleur
- **Preuves** : B3 N20 + #59, #190 (HelioScope, archelios) ; B6 R33 (3 outils) + K52. **2 lanes**. URL : https://help-center.helioscope.com/hc/en-us/articles/8536954019603-CAD-Export-Blocks-and-Layers
- **Chez nous** : **PARTIEL** — `SV/export_dxf.py` écrit des polylignes sur calques nommés, dont `CALQUE_CHAINES` (CALX310) ; aucun bloc (`grep -i block` : seulement le MTEXT de provenance).
- **Plus petite version crédible** : un bloc `MODULE` défini une fois, inséré par module avec attributs `CHAINE`, `MPPT`, `ONDULEUR`, `N`.
- **Tâches** : 1. Blocs + attributs ; fini quand le DXF relu par ezdxf compte autant d'INSERT que de modules posés et que chaque attribut `CHAINE` égale l'affectation. Fichier : `SV/export_dxf.py`.
- **Score** : P 2 × A 1 ÷ E 1 = **2** — rang **26**

### CAP-D3-21 — Aide en direct pendant le chaînage (et ligne par chaîne : Voc froid, Vmp chaud, démarrage)
- **Preuves** : B3 N18 + #194 (Pylon « live stringing tooltip ») ; B6 R23 (4 outils) et R3 (5 outils : démarrage par chaîne) ; B5-de §10 (démarrage). **3 lanes**. URL : https://getpylon.com/ie/solar-design/
- **Chez nous** : **PARTIEL** — `FE/plan/AffectationChaines.jsx` appelle `evaluerElectrique` après anti-rebond (`setTimeout`) et affiche les refus serveur ; mais l'écran « ne calcule NI une longueur admissible, NI une tension » (`AffectationChaines.helpers.js`) et n'affiche pas la Voc de la chaîne en cours. La tension de démarrage est contrôlée (`CE/chaines.py::fenetre_admissible`, `min_par_demarrage`) et les heures sous démarrage sont comptées (`ET/mppt.py`, clé `heures_sous_demarrage`) — `grep heures_sous_demarrage frontend/src` = 0 (présent sans écran nommé).
- **Plus petite version crédible** : pendant le glisser, une bulle « Chaîne 3 : 12 modules — Voc à froid 594 V / 1 000 V, Vmp chaud 410 V ≥ démarrage 200 V » lue dans la réponse d'`evaluer-electrique` (le serveur la rend déjà par chaîne via les verdicts) ; un tableau par chaîne dans le Verdict.
- **Tâches** : 1. Servir les tensions par chaîne dans la réponse à chaud ; fini quand chaque chaîne porte Voc froid, Vmp chaud et démarrage. Fichier : `SV/electrique.py`. 2. Bulle et tableau. Fichiers : `FE/plan/AffectationChaines.jsx`, `FE/electrique/VerdictElectrique.jsx`. Recoupe « Pourquoi ce chiffre ? » (D6) pour le texte.
- **Score** : P 3 × A 2 ÷ E 2 = **3** — rang **19**

### CAP-D3-22 — Importer un plan de chaînes (CSV module → chaîne)
- **Preuves** : B4 r8 (VF10527, FP75652) ; B5-de P8 (5 fils, FAQ éditeur) ; B7 U28 (2 sources). **3 lanes**. URL : https://forum.valentin-software.com/topic/10420-wie-%C3%BCbertrage-ich-einen-bereits-fertigen-strangplan-handgezeichnet-oder-aus-einer-anderen-planungssoftware/
- **Chez nous** : **ABSENT** — l'affectation manuelle a déjà sa forme normalisée (`SV/chaines.py::normaliser_affectation_imposee`, clés `module, chaine, mppt, onduleur`) : un CSV n'est qu'un autre chemin d'entrée.
- **Plus petite version crédible** : CSV `module;chaine;mppt;onduleur` passé tel quel au verdict existant (`verdict_affectation`) ; les refus nomment la ligne du fichier.
- **Tâches** : 1. Import CSV → affectation imposée ; fini quand une ligne fausse est refusée en nommant sa ligne et sa contrainte. Fichiers : `apps/calepinage/views/electrique.py`, `SV/chaines.py`, `FE/plan/AffectationChaines.jsx`.
- **Score** : P 3 × A 1 ÷ E 1 = **3** — rang **20**

### CAP-D3-23 — Réserver une entrée MPPT et des modules pour une extension future
- **Preuves** : B5-es #16 (2 fils). **1 lane**. URL : https://www.solarweb.net/forosolar/fotovoltaica-sistemas-conectados-red/60589-nueva-instalacion-fotovoltaica-deye-10kw.html
- **Chez nous** : **ABSENT** — aucun champ de réserve (`grep -i "réserv.*extension|mppt_reserv"` = 0).
- **Plus petite version crédible** : saisie « garder n entrées MPPT libres » et « N modules réservés » : le chaînage s'interdit ces entrées et le contrôle DC/AC est aussi rendu « avec extension ».
- **Tâches** : 1. Entrées réservées dans l'allocation ; fini quand 1 entrée réservée sur 2 force toutes les chaînes sur l'autre. Fichiers : `CE/chaines.py::_allouer_mppt`, `SV/electrique.py`.
- **Score** : P 1 × A 2 ÷ E 1 = **2** — rang **27**

### CAP-D3-24 — Interrupteur pompier / coupure d'urgence et distance de séparation foudre (questions, jamais une norme inventée)
- **Preuves** : B5-nl #2 (3 pages) ; B5-de P17 / K48 (17 fils en passe 2, 24 lignes) ; B5-es K21. **3 lanes**. URL : https://www.gramwzielone.pl/energia-sloneczna/103977/ochrona-instalacji-fotowoltaicznej-na-szostke ; https://www.photovoltaikforum.com/thread/266033-pv-planung-f%C3%BCr-neubau-mit-ca-30-kwp-diy-m%C3%B6glichst-bis-ende-2026/
- **Chez nous** : **ABSENT** — `grep -i "pompier|arrêt rapide|paratonnerre|distance de séparation"` sur `CE/` et `SV/` = 0 ; parafoudres, sectionneur DC, fusibles PRÉSENTS (`CE/protections.py::concevoir_protections`, `SV/protections.py::checklist_protections`).
- **Plus petite version crédible** : deux lignes de la check-list des protections : « coupure d'urgence DC / arrêt rapide exigé ? » (oui/non saisi par la société ou le dossier, organe ajouté si oui) ; « paratonnerre présent ? » → si oui, distance de séparation SAISIE et comparée à une valeur saisie par la société (source obligatoire).
- **Tâches** : 1. Lignes de check-list + organe ; fini quand « oui » ajoute l'organe au schéma et à la nomenclature, et « non renseigné » apparaît comme tel. Fichiers : `SV/protections.py`, `CE/protections.py`, `CE/schema.py`.
- **Score** : P 3 × A 2 ÷ E 1 = **6** — rang **11**

### CAP-D3-25 — Garde kVA / kWc dans la déclaration de raccordement (part électrique)
- **Preuves** : B5-de P16 / K47 (43 fils en passe 2, surtout dossier). **1 lane**. URL : https://www.energiesparhaus.at/forum-pv-planung-erste-schritte/86023
- **Chez nous** : **PARTIEL** — `SV/raccordement.py::_puissance_injectee_kva` calcule les kVA injectés (fiche `s_max_kva` × cos φ saisi) ; aucun seuil réglementaire comparé (rien de codé — correct).
- **Plus petite version crédible** : kWc et kVA côte à côte dans la synthèse électrique ; alerte au-delà d'un seuil SAISI par la société avec sa source (le seuil 82-21 est à confirmer par le fondateur, jamais codé). Le plafond lui-même est **D5**.
- **Tâches** : 1. Ligne + seuil société ; fini quand, seuil vide, la ligne affiche kWc et kVA sans verdict. Fichier : `SV/raccordement.py`.
- **Score** : P 1 × A 3 ÷ E 1 = **3** — rang **21**

### CAP-D3-26 — Orientations mélangées sur un MPPT : la perte affichée
- **Preuves** : B5-fr R3 + grappe 4 (12 fils) ; B5-en groupe H (SolarQuotes « ce qui est perdu ») ; B4 S6 (VF10850). **3 lanes**. URL : https://forum-photovoltaique.fr/viewtopic.php?t=30516
- **Chez nous** : **PARTIEL** — `SV/polystring.py::grouper_polystring` (CALX206) et `::ecart_de_groupe` (écart de PUISSANCE contre tolérances société, CALX207), écran `FE/electrique/DecisionsElectriques.jsx` ; aucune énergie perdue publiée pour le partage d'une entrée.
- **Plus petite version crédible** : énergie de la variante « une entrée par orientation » contre « entrée partagée », lue dans `SV/agregation_electrique.py` (énergie par chaîne/MPPT) ; si le modèle ne sait pas la calculer, la ligne le dit (aucun pourcentage forfaitaire).
- **Tâches** : 1. Écart d'énergie publié par groupe polystring ; fini quand un groupe E+O sur une entrée publie un kWh/an d'écart ou un motif d'omission. Fichiers : `SV/polystring.py`, `SV/agregation_electrique.py`. La physique du mismatch relève de D4.
- **Score** : P 3 × A 2 ÷ E 2 = **3** — rang **22**

### CAP-D3-27 — Graphe du ratio DC/AC : énergie par classe de puissance et part écrêtée
- **Preuves** : B1 C11 + V094/V095 ; B6 R30 (3 outils) ; B4 P9 (FP16494). **3 lanes**. URL : https://www.pvsyst.com/help/project-design/grid-connected-system-definition/inverter-array-sizing.html
- **Chez nous** : **PARTIEL** — ratio + paliers société `CE/onduleurs.py::ratios`/`::bornes_dc_ac`, écrêtage horaire `ET/ecretage.py` ; aucun graphe. **DÉJÀ PLANIFIÉ en partie** : ACAL477 (axe DC/AC du balayage : énergie et écrêtage par ratio) — pas l'histogramme.
- **Tâches** : 1. Histogramme énergie/classe de puissance lu dans la série horaire persistée, ligne Pnom ; fini quand la somme des classes égale l'énergie DC du bilan. Fichiers : `SV/electrique.py`, `FE/electrique/VerdictElectrique.jsx` (« expert »). L'explication du ratio est D6.
- **Score** : P 3 × A 1 ÷ E 1 = **3** — rang **23**

---

## Table de synthèse

| Rang | CAP | Titre | Verdict | Tâches | Effort |
|---|---|---|---|---|---|
| 1 | CAP-D3-01 | Essayer un autre onduleur/module, comparer 2-3 configurations | PRÉSENT SANS ÉCRAN (service) | 3 | M |
| 2 | CAP-D3-02 | Import .PAN/.OND visible et prouvé sur fichiers publics | PRÉSENT SANS ÉCRAN | 4 (dont CALX357 existante) | M |
| 3 | CAP-D3-03 | Motif de chaînage (affectation + câble) | PRÉSENT SANS ÉCRAN (câble) / ABSENT (affectation) | 3 | M |
| 4 | CAP-D3-04 | Optimiseur sur les seuls modules ombrés, limite multi-modules | PRÉSENT SANS ÉCRAN (consommateur) / ABSENT (producteur) | 4 | M |
| 5 | CAP-D3-11 | Plan de câblage pour l'électricien (tension, consignes, MPPT) | ABSENT | 3 | S |
| 6 | CAP-D3-13 | Résistivité à chaud, regroupement | ABSENT | 2 | S |
| 7 | CAP-D3-06 | Champs de fiche manquants | ABSENT (ACAL464 en partie, gel mal motivé) | 5 (1 routée STOCK) | M |
| 8 | CAP-D3-09 | Déclassement thermique onduleur (fiche + verdict) | ABSENT | 2 (1 en D4) | S-M |
| 9 | CAP-D3-10 | Contrôle rapide sans dessin | PARTIEL | 3 | S |
| 10 | CAP-D3-17 | Micro ≠ injection zéro ; pince CT | ABSENT | 2 | S |
| 11 | CAP-D3-24 | Coupure d'urgence, distance foudre | ABSENT | 1 | S |
| 12 | CAP-D3-05 | Valeurs attendues par chaîne → recette, seuil d'isolement | PARTIEL | 3 (2 routées CHANTIERS) | M |
| 13 | CAP-D3-07 | Nombre minimal d'onduleurs, onduleur de chaque chaîne | ABSENT | 3 | M |
| 14 | CAP-D3-08 | Chaînes qui survivent et se ré-ancrent | PARTIEL | 3 | M |
| 15 | CAP-D3-12 | Boucles DC : surface, retour accolé | ABSENT (tracé = ACAL472) | 3 | M |
| 16 | CAP-D3-14 | Chaîne sur deux pans de même orientation | ABSENT (refusé) | 2 | M |
| 17 | CAP-D3-15 | Schéma de secours | ABSENT | 1 | M |
| 18 | CAP-D3-16 | Verdict chaîne / micro / optimiseur | ABSENT | 1 | M |
| 19 | CAP-D3-21 | Aide en direct pendant le chaînage | PARTIEL | 2 | M |
| 20 | CAP-D3-22 | Import CSV d'un plan de chaînes | ABSENT | 1 | S |
| 21 | CAP-D3-25 | Garde kVA/kWc (part électrique) | PARTIEL | 1 | S |
| 22 | CAP-D3-26 | Perte d'un MPPT partagé | PARTIEL | 1 | M |
| 23 | CAP-D3-27 | Graphe DC/AC | PARTIEL (ACAL477 en partie) | 1 | S |
| 24 | CAP-D3-18 | Schéma : modèle par distributeur, édition libre | PARTIEL | 2 | M-L |
| 25 | CAP-D3-19 | Feuille XLSX de vérification à formules texte | ABSENT | 1 | S |
| 26 | CAP-D3-20 | DXF à blocs nommés | PARTIEL | 1 | S |
| 27 | CAP-D3-23 | Réserver une entrée MPPT | ABSENT | 1 | S |

Règle de classement appliquée : les PRÉSENT SANS ÉCRAN d'abord (rangs 1-4), puis le score décroissant ; à score égal, l'effort le plus petit ; un prérequis remonte juste devant ce qu'il débloque (CAP-D3-06 devant CAP-D3-09). Les ids CAP restent stables (ils ne suivent pas le rang).

## Présents et visibles (aucune fiche : rien à construire, noté pour éviter le doublon)
- Chaînage automatique contre les vraies limites de l'onduleur (Voc à froid, fenêtre MPPT, démarrage, Isc, températures du site) : `CE/chaines.py::fenetre_admissible`, `::concevoir_chaines`, `SV/chaines.py::concevoir_par_pan` — B4 6.1 #7, B5-de K02 (131 fils), B5-fr grappe 2, B5-es K05, B6 K01/K03, B7 grappe 14.
- Pdc maximale par modèle (B5-es #14, « limite DC publiée par modèle ») : **PRÉSENT** `CE/onduleurs.py::_verdict_dc_max` (bloquant sur `ond_dc_max_kwc`, CALX213) et `::_verdict_s_max`. La lane B5-es avait tort.
- Affectation manuelle module par module : `FE/plan/AffectationChaines.jsx` + `SV/chaines.py::verdict_affectation` (CAL234).
- Plusieurs orientations sur une entrée MPPT, jamais dans une chaîne : `SV/polystring.py::grouper_polystring`, `REGLE_UNE_ORIENTATION_PAR_CHAINE`.
- Longueurs de câble mesurées tronçon par tronçon, section et chute par tronçon, cibles UTE sourcées : `SV/troncons.py`, `CE/cables.py::proposer_section`, `SV/norme.py::COEFFICIENTS` (CALX224-228).
- Parafoudres, fusibles gPV, sectionneur DC, DDR, citations de règle : `CE/protections.py::concevoir_protections`, `SV/protections.py::checklist_protections`.
- Schéma unifilaire généré, positions/libellés éditables, SVG/DXF/PNG, « typique de N » : `SV/sld.py`, `SV/sld_export.py`, `FE/SchemaUnifilairePanel.jsx`.
- Micro-onduleurs en branches AC calibrées : `SV/micro_onduleurs.py` (CALX209/210). Optimiseurs : longueur fermée par la sortie régulée (CALX211), comptage (CALX212).
- Fiche de recette IEC 62446-1 avec relevés I-V par chaîne : `apps/installations/models_chantier.py::CommissioningRecord`, `::CommissioningIVReading` (chantiers).
- Verdict de publication électrique : `SV/electrique.py::verdict_publiable` (servi sous la clé `publication` d'`evaluer-electrique`).

## Déjà planifié (aucune fiche)
- « Prêt à envoyer ? » électrique (B3 N6, B4 r6, B6 R15/K57, B5-de P20) : les lignes électriques existent déjà (`verdict_publiable`) ; le panneau unique = ACAL392 + ACAL397 (+ ACAL426) — motif transversal **D6**. Seule part D3 : chaque fiche ci-dessus doit publier son verdict dans `verdict_publiable` pour y figurer.
- Écran Électrique unique : ACAL395 (prérequis de CAP-01, 21).
- Tracé automatique des câbles (B3 N12/#129/#130, B6 K07/R60) : ACAL472 (la polarité et les boucles = CAP-D3-12).
- Balayage DC/AC : ACAL477. Bornes d'ombrage électrique au rapport : ACAL462. Modèle à une diode : ACAL464 (gel à re-motiver, CAP-D3-06).
- Import .PAN/.OND : CALX339/356/357 (à réécrire, CAP-D3-02).

## Écarté (une ligne chacun)
- Export DWG (B6 K52, Solarius) : l'écriture DWG exige un convertisseur tiers fermé (ODA) — le DXF suffit à tous les CAO ; non vérifié dans le dépôt qu'aucun lecteur ne l'exige.
- Proposition SolarEdge automatique / règles propres à une marque d'optimiseur (B1 S072, B6 K65 part marque) : marque spécifique ; remplacé par le champ « onduleurs compatibles » (CAP-06).
- « AI Circuit Plan » / Ask AI pour retoucher le schéma (B2 X05, B3) : coût d'IA par retouche, risque électrique ; CAP-18 rend le service sans IA.
- Courbes I-V pédagogiques, caractéristique inverse (B1 §5, B7 grappe 44) : outils d'ingénieur.
- Règle des 120 % du jeu de barres (B7 grappe 40) : norme américaine, sans objet au Maroc.
- Compteur de production recommandé par onduleur (B6 K94) : 1 outil, faible intérêt.
- Plus de 2 chaînes par MPPT Huawei (B1 V098) : déjà borné par la fiche (`ond_chaines_max_par_mppt`).
- Hauteur de cadre et étriers dans l'ombre (B5-es #13) : relève de D2/D4, preuve mince.
- Optimisation de tension d'un champ couplé à tension fixe, réseaux DC (B1 §5) : hors marché.
- Numéros de série posés par chaîne (B7 U17) : chantier/SAV, hors calepinage — à proposer au domaine chantiers.

## Renvoyé à un autre domaine (part D3 gardée ci-dessus)
- Diodes de dérivation / ombrage au niveau sous-chaîne (B1 C07, B4 r11, B6 K26/R47, B5-fr grappe 19, B5-es K02, B7 grappe 18) → **D4** ; D3 garde le champ de fiche (CAP-06).
- Poste « perte optimiseur » (B1 C17) et « perte de démarrage » dans la cascade (B5-es #11) → **D4** ; D3 note que `heures_sous_demarrage` est déjà compté (`ET/mppt.py`).
- Pompage hybride sur bus DC (B5-es #20), plafond de soutirage / fenêtres de bridage / limite en ampères (B4 r9, B5-en #10/#18, B7 U18) → **D5**.
- Extension d'une installation existante (B4 r7, B5-en #3, B5-es #9 / K19, B6 R31, B7 U21) → **D2/D5** (pan « existant ») ; D3 en garde la réserve d'entrée (CAP-23) et le contrôle des limites de l'onduleur existant via CAP-01.
- Dupliquer un bloc câblé (B2 #16, B6 K13, B3 #159) → **D2** pour la duplication ; la copie des chaînes est CAP-08 t3.
- Placement 3D des organes électriques (B6 K87/R62) → **D2**.
- Fiche de pose A4 par pan avec chaînes colorées (B3 N9), cotes du plan de pose (B5-de P5) → **D2** ; les repères + / − sont CAP-11.
- « Pourquoi ce chiffre ? » sur Voc froid / DC/AC (B4 r1, B5-en #1, B5-es #1, B5-de P1) → **D6** ; CAP-21 fournit les nombres.

## Contradictions entre lanes tranchées par le code
1. **Import PAN/OND** : B7 grappe 2 (« lecture PAN/OND ABSENTE, git grep = 0 ») et le constat de CALX339/356 (« aucun parseur ») ont TORT ; B5-en groupe 5, B5-fr grappe 15 et B5-nl ont raison : `ST/importers/fiche_pan_ond.py` + `ST/views/fiche_technique.py::importer_datasheet` existent (CAL117). Personne n'avait relevé que l'action est headless (`# headless: D-ENF15-STOCK-22`, aucun appelant front) ni que CALX356 ferait un doublon.
2. **Limite DC par modèle** : B5-es #14 (« seule l'alerte générique du ratio ») a tort — `CE/onduleurs.py::_verdict_dc_max` bloque sur `dc_max_kwc` (CALX213).
3. **Facteurs de câble à chaud et regroupement** : B5-en P2.2 (« PRÉSENT, `cables.py:23` ») a tort — la ligne citée dit qu'ils sont HORS moteur ; B5-es #6 a raison.
4. **Compatibilité optimiseur ↔ onduleur** : B5-de §10 (« traitée côté ventes `apps/ventes/compatibilites.py` ») a tort — ce fichier ne traite que panneau↔onduleur et batterie↔onduleur (`grep optimiseur` = 0).
5. **Fiche de mesures de réception** : B5-de §10/P22 (« aucune fiche trouvée ») a tort — `CommissioningRecord` / `CommissioningIVReading` existent côté chantiers avec écran (`ChantierGateTimeline.jsx`) ; le vrai manque est le pré-remplissage depuis le calepinage (B5-es #10 avait le bon diagnostic).
6. **Tension de démarrage** : B5-de §3 passe 1 (« non simulée ») corrigé par sa propre passe 2 ; confirmé : `fenetre_admissible` (`min_par_demarrage`) et `ET/mppt.py` (`heures_sous_demarrage`).
7. **Motif de parcours** : B1 V087 (« PRÉSENT — motif de parcours CALX218 ») est à moitié juste : le motif ne règle que la LONGUEUR de câble, pas l'affectation des modules, et il n'a aucun écran ; B3 N11 / B6 K02 (« un seul motif ») ont raison pour l'affectation.
8. **Survie des chaînes** : B5-de K16 (« PRÉSENT par construction ») est trop optimiste ; B5-en (« partiel, non prouvé ») a raison : la clé manuelle retombe sur le RANG quand le document n'est pas numéroté (`PanPose.cle_module`).
9. **Propriété des champs de fiche** : B1 C21/C03 et ACAL464 disent « à router vers le plan stock » — faux pour le modèle : `docs/ownership.yml` met `ST/models_fiche_technique.py` chez **calepinage** ; seuls `ProduitForm.jsx` (stock) et la migration (stock, append-only) sortent du domaine.

## Non vérifié (dit tel quel)
- Rien n'a été exécuté (ni tests, ni atelier, ni docker) : chaque « PRÉSENT » veut dire « le code existe à cet endroit », pas « je l'ai vu marcher ».
- Si la cascade affiche de façon générique le détail de l'étape `mppt` (donc `heures_sous_demarrage`) : seul le grep par nom a été fait (0 occurrence front).
- Le comportement réel de l'affectation manuelle après retrait d'un module ou changement de pas (CAP-08) : déduit de la lecture de `cle_module`, non rejoué.
- Les noms exacts des clés PVsyst pour diodes, cellules et Pnom(T) dans les fichiers pvlib publics (CAP-02/06) : non lus ; la tâche doit les lire sur les fichiers, jamais les deviner.
- Si le contrôle d'entrée d'optimiseur tourne aussi dans le régime « micro seul » (`concevoir_par_pan` rend `resultat=None`) : non suivi.
- Que `ProduitDetail.jsx` affiche bien le verdict de `compatibilites_du_produit` (seul l'appel API a été vu).
- B5-de §8 (1 189 lignes de la passe 2) n'a été lu que par ses §9-§12 (clusters, re-vérification, propositions) ; les URL de P21/P22 n'ont pas été recopiées faute de les avoir ouvertes.

## Correspondance id d'origine → sort
| Lane | Ids | Sort |
|---|---|---|
| B1 | C10, S066 | CAP-01 |
| B1 | C21 | CAP-06 |
| B1 | C03, V099 | CAP-09 (+ D4 étape) |
| B1 | C11, V094, V095, S067 | CAP-27 (+ ACAL477) |
| B1 | C07 | D4 (champ → CAP-06) |
| B1 | C17 | D4 |
| B1 | V087 | CAP-03 |
| B1 | V211, V212 | CAP-02 |
| B1 | V098 | écarté (borné par fiche) |
| B1 | S070 | CAP-26 (série de sous-chaînes : écarté, rare) |
| B1 | S072 | écarté |
| B1 | S077 | CAP-18 |
| B1 | S079, V105, S073-S076, S078, V091-V093, V096, V097 | présents |
| B2 | #14, A35 | CAP-07 |
| B2 | #16, X16 | D2 + CAP-08 t3 |
| B2 | A38 | CAP-04 (multi-entrées) |
| B2 | O22, O23, O24, O25, A36, A37, X04, X11, X18 | présents |
| B2 | O27 | D4 |
| B2 | X05 | écarté |
| B2 | A29 | non vérifié (comptage unique de l'hybride) |
| B3 | N6 | déjà planifié (ACAL392/397, D6) |
| B3 | N9 | D2 (+ CAP-11) |
| B3 | N11, #127, #270 | CAP-03 |
| B3 | N12, #129, #130 | ACAL472 + CAP-12 |
| B3 | N18, #194 | CAP-21 |
| B3 | N20, #59, #190 | CAP-20 |
| B3 | N21, #91, #92 | CAP-18 |
| B3 | N31 | CAP-01 |
| B3 | #41 | CAP-07 |
| B3 | #88, #266 | CAP-04 |
| B3 | #186 | CAP-08 |
| B3 | #220 | présent (`chainage.reste`) |
| B3 | #224 | présent (`SV/troncons.py` descente mixte) |
| B3 | #226 | CAP-04 (modules AC/sous-chaînes : non vérifié) |
| B3 | #227 | D4 |
| B3 | #267 | CAP-15 (une batterie par onduleur : non retenu seul) |
| B3 | #271 | D2 (placement des appareils) |
| B3 | #39, #40, #42-#45, #86, #87, #89, #90, #93, #125, #126, #128, #131, #139, #147, #148, #157, #179, #180, #187, #195, #205, #222, #223, #225, #231 | présents |
| B3 | #62 | CAP-02 |
| B4 | r3, S12 | CAP-08 |
| B4 | r4, r15, P13 | CAP-02 |
| B4 | r6 | déjà planifié (D6) |
| B4 | r8 | CAP-22 |
| B4 | r11, P4 | D4 |
| B4 | P7, S6 | présent / CAP-26 |
| B4 | P8 | CAP-16 |
| B4 | P9 | CAP-27 |
| B4 | r7 | D2/D5 |
| B4 | r9 | D5 |
| B5-de | P4, K12 | CAP-04 |
| B5-de | P5 (polarité) | CAP-11 (cotes → D2) |
| B5-de | P8 | CAP-22 |
| B5-de | P9, K15 | CAP-18 |
| B5-de | P12, K10 | CAP-12 |
| B5-de | P16, K47 | CAP-25 (+ D5) |
| B5-de | P17, K48 | CAP-24 |
| B5-de | P20 | déjà planifié (D6) |
| B5-de | P21, K53 | CAP-15 |
| B5-de | P22, K51 | CAP-05 |
| B5-de | K02, K20 | présents (+ CAP-14 pour K20 multi-zones) |
| B5-de | K16, K33 | CAP-08 |
| B5-de | K28 | CAP-01 |
| B5-de | K31 | CAP-02 |
| B5-de | P1 | D6 |
| B5-en | #2, #17, groupe C | CAP-08 |
| B5-en | groupe 5 | CAP-02 |
| B5-en | groupe 29 / H | CAP-07 / présent |
| B5-en | groupe 6, 10, 12, B | présents |
| B5-en | groupe G (DC/AC) | CAP-27 ; limite en A → D5 |
| B5-en | #1 | D6 |
| B5-en | #3 | D2/D5 |
| B5-en | #10, #18 | D5 |
| B5-en | #19 | D4 |
| B5-es | #2, #24, K37 | CAP-04 |
| B5-es | #3 | CAP-18 (schéma) ; pièces du dossier → Documents |
| B5-es | #4 | CAP-19 |
| B5-es | #6, K06 | CAP-13 |
| B5-es | #7, K21 | CAP-11 (+ CAP-24) |
| B5-es | #9, K19 | D2/D5 |
| B5-es | #10, K22, §5.1 | CAP-05 |
| B5-es | #11 | D4 (compte déjà présent) |
| B5-es | #13 | écarté |
| B5-es | #14 | présent (contradiction 2) |
| B5-es | #16 | CAP-23 |
| B5-es | #20 | D5 |
| B5-es | #25 | CAP-17 |
| B5-es | #1 | D6 |
| B5-es | K05, K14, K18, K23 | présents |
| B5-fr | R3, grappe 4 | CAP-26 |
| B5-fr | R6, grappe 21 | CAP-09 |
| B5-fr | R9, grappe 19 | D4 |
| B5-fr | R12, grappe 10 | CAP-17 |
| B5-fr | grappe 15 | CAP-02 |
| B5-fr | grappe 17 | CAP-16 |
| B5-fr | grappe 22 | CAP-01 |
| B5-fr | grappes 2, 5, 14 | présents |
| B5-fr | R17, grappe 34 (sheds) | D2 |
| B5-nl | #1, 8 | CAP-16 |
| B5-nl | #2 | CAP-24 |
| B5-nl | #3, 1b | CAP-06 |
| B5-nl | #4 | CAP-10 |
| B5-nl | 3b (relecture d'un schéma déjà dessiné) | écarté (aucun schéma tiers importé ; preuve : 0 hit, 1 page) |
| B5-nl | 16 | CAP-02 |
| B6 | K01, K03, K04, K05, K73 | présents |
| B6 | K02 | CAP-03 |
| B6 | K06 | CAP-13 |
| B6 | K07, R60 | ACAL472 / CAP-12 |
| B6 | K13 | D2 + CAP-08 t3 |
| B6 | K26, R47 | D4 |
| B6 | K52 | CAP-20 (DWG écarté) |
| B6 | K54 | CAP-02 |
| B6 | K57, R15 | déjà planifié (D6) |
| B6 | K61, R43 | présent / CAP-11 |
| B6 | K64 | CAP-09 / CAP-27 |
| B6 | K65 | CAP-04 / CAP-06 (règles de marque écartées) |
| B6 | K87, R62 | D2 |
| B6 | K94 | écarté |
| B6 | R3, R23 | CAP-21 |
| B6 | R9 | CAP-14 |
| B6 | R19, R34 | CAP-18 |
| B6 | R26, R29 | CAP-01 |
| B6 | R30 | CAP-27 |
| B6 | R33 | CAP-20 |
| B6 | K38 | D5 |
| B7 | U1 | CAP-02 |
| B7 | U6 | CAP-01 |
| B7 | U7 | CAP-10 |
| B7 | U10 | CAP-04 (+ D4 pour l'explication) |
| B7 | U17 | écarté (chantier/SAV) |
| B7 | U28 | CAP-22 |
| B7 | U29, grappe 66 | CAP-09 |
| B7 | grappes 2 | CAP-02 |
| B7 | grappes 13, 14, 17, 24, 25, 67 | présents |
| B7 | grappe 18 | D4 |
| B7 | grappe 40 | présent (120 % écarté) |
| B7 | grappe 44 | écarté |
| B7 | grappe 64 | CAP-22 |
| B7 | grappe 72 | CAP-07 |
