# D4 — Simulation, ombrage, pertes, résultats et rapport d'étude : capacités consolidées (tour 1, 21/11/2026)

Juge de consolidation, lecture seule du worktree `calpinage-module-enhance-04bba5` (base `5a75a182b`). Rien exécuté (aucun test,
aucune simulation, aucun docker). Chaque verdict ci-dessous repose sur un grep ou une lecture faits dans CETTE session, sauf mention
« non vérifié ». Les propositions des onze lanes ont été rassemblées par deux extractions (B1 lue par moi ; B2-B5fr et B5en-B7 par deux
lecteurs sonnet qui ont rendu ids, comptes, URL et numéros de ligne) ; les comptes de preuves sont ceux que chaque lane écrit.

Abréviations : `SV` = `backend/django_core/apps/calepinage/services` · `ET` = `SV/etapes` · `CC` = `backend/django_core/core/calepinage`
· `FE` = `frontend/src/features/calepinage` · `RP` = `apps/web/src/scripts/roofPro11` · `LIB` = `apps/web/src/lib`
· `FT` = `backend/django_core/apps/stock/models_fiche_technique.py`. Lanes : B1 PVsyst/PV*SOL, B2 Aurora/OpenSolar, B3 outils de conception,
B4 voix des utilisateurs, B5de/B5fr/B5en/B5es/B5nl forums, B6 notes de version, B7 demandes d'utilisateurs.

Propriété des fichiers (vérifiée par `python scripts/check_ownership.py --owner-of`) : `SV/chaine_pertes.py`, `SV/rapport/__init__.py`,
`CC/soleil.py`, `CC/garde_fous.py`, `RP/shadingUi.ts`, `LIB/shadingEngine.ts`, `LIB/roofPro2.ts`, `FE/production/DiagrammePertes.jsx`,
`FE/production/PanneauProduction.jsx`, `FE/production/TapisHoraire.jsx`, `SV/photos.py`, `backend/.../apps/stock/importers/fiche_pan_ond.py`,
**`FT` (models_fiche_technique.py)**, `backend/.../apps/calepinage/data/profil_depart.json`, `management/commands/` → **calepinage** ;
`frontend/src/api/calepinage/simulation.js` → calepinage (surface append-only) ; `backend/.../apps/stock/migrations/*` → **stock (surface
append-only)** ; `apps/stock/models.py` → stock ; `apps/ventes/quote_engine/generate_devis_premium.py` → moteur.
⇒ Un champ de fiche technique se code chez calepinage ; seule la MIGRATION vit dans un fichier stock en ajout seul (à router vers le plan
stock si la règle d'ajout seul ne suffit pas).

---

## 1. Synthèse classée

Score = preuves (lanes distinctes, pondérées forum > notes de version > page commerciale) × adéquation (1-3) ÷ effort (S=1, M=2, L=3).
Les capacités « PRÉSENT SANS ÉCRAN » sont mises en tête quel que soit leur score.

| Rang | CAP | Titre | Verdict | Tâches | Effort | Score |
|---|---|---|---|---|---|---|
| 1 | CAP-D4-01 | Écart du moteur contre PVGIS à l'écran : « quel chiffre croire » | PRÉSENT SANS ÉCRAN | 2 | S | 21 |
| 2 | CAP-D4-02 | Ombre partielle expliquée chaîne par chaîne, avec la parade | PRÉSENT SANS ÉCRAN (bornes) + PARTIEL | 3 | M | 13,5 |
| 3 | CAP-D4-03 | Tableau de vieillissement sur 25 ans et courbe de garantie | PRÉSENT SANS ÉCRAN | 2 | S | 12 |
| 4 | CAP-D4-04 | Verdict d'ombrage en une phrase + « retirer les modules sous X » à seuil société | PRÉSENT SANS ÉCRAN dans l'ERP | 3 | S | 12 |
| 5 | CAP-D4-05 | Perte due à la tension de démarrage de l'onduleur | PRÉSENT SANS ÉCRAN (compte d'heures) + PARTIEL | 2 | S | 9 |
| 6 | CAP-D4-06 | Export CSV : colonnes et pas choisis, ombrage par module et par heure | PRÉSENT SANS ÉCRAN (colonnes) + ABSENT (par module) | 3 | S | 5 |
| 7 | CAP-D4-07 | Fiche INTERNE « les pertes expliquées au client en 6 postes » | ABSENT | 2 | S | 12 |
| 8 | CAP-D4-08 | Écrêtage DC/AC en histogramme, distribution de puissance, courbe entrée/sortie du jour | PARTIEL (données servies, aucun graphe) | 3 | S | 10 |
| 9 | CAP-D4-09 | Liste « ce que cette simulation ne modélise pas » | PARTIEL | 2 | S | 8 |
| 10 | CAP-D4-10 | Déclassement thermique de l'onduleur (chaleur) | ABSENT | 3 | M | 7,5 |
| 11 | CAP-D4-11 | Salissure : fréquence de nettoyage et inclinaison minimale d'autonettoyage | ABSENT | 2 | M | 7,5 |
| 12 | CAP-D4-12 | Plage « normale » de chaque perte et garde-fous de vraisemblance des entrées | PARTIEL | 4 | M | 7,5 |
| 13 | CAP-D4-13 | Deuxième source météo gratuite et écart annoncé (SARAH3 / ERA5 / NASA POWER) | PARTIEL | 3 | M | 6 |
| 14 | CAP-D4-14 | Courbe « % de direct perdu » heure par heure sur une journée choisie | ABSENT | 1 | S | 6 |
| 15 | CAP-D4-15 | Heure légale contre heure solaire sur la course du soleil | PARTIEL | 2 | S | 6 |
| 16 | CAP-D4-16 | Diodes de dérivation : modèle par sous-chaînes (portrait / paysage) | ABSENT (étape déclarée, toujours omise) | 3 | L | 6 |
| 17 | CAP-D4-17 | Production mesurée contre simulée, par chantier livré | ABSENT | 3 | M | 5 |
| 18 | CAP-D4-18 | Rapport d'étude : pages manquantes (synthèse, modèles, autoconso/batterie, IAM, photos) | PARTIEL | 5 | M | 5 |
| 19 | CAP-D4-19 | Schéma « où va l'énergie » (Sankey) | ABSENT | 2 | M | 4,5 |
| 20 | CAP-D4-20 | Perte de l'optimiseur et optimiseur posé seulement sur les modules ombrés | PARTIEL | 3 | M | 4 |
| 21 | CAP-D4-21 | Rapport d'ombrage capturé tout seul, échelle fixe 0-100 %, une image par pan | PARTIEL | 2 | M | 4 |
| 22 | CAP-D4-22 | Albédo par type de surface et par saison | PARTIEL | 2 | S | 4 |
| 23 | CAP-D4-23 | Pans triés par accès solaire et valeurs au survol des éléments dessinés | PARTIEL | 2 | S | 4 |
| 24 | CAP-D4-24 | Pertes depuis l'irradiation horizontale et tableau mensuel complet | PARTIEL (+ DÉJÀ PLANIFIÉ partiel) | 3 | M | 3 |
| 25 | CAP-D4-25 | Rapport d'étude éditable : variables de texte et export DOCX | ABSENT | 2 | M | 3 |
| 26 | CAP-D4-26 | Calepinages d'exemple prêts à ouvrir | ABSENT | 2 | M | 3 |
| 27 | CAP-D4-27 | Contrôle qualité d'un fichier météo déposé et diagnostic nommé | PARTIEL | 2 | M | 2 |
| 28 | CAP-D4-28 | Feuille de vérification (formules écrites en texte) | ABSENT | 1 | S | 2 |
| 29 | CAP-D4-29 | Ombre de cadre, de pinces ou de différence de hauteur de châssis | ABSENT | 1 | S | 2 |
| 30 | CAP-D4-30 | Bilan carbone | ABSENT — GATED (facteur réseau sourcé) | 1 | S | — |

Total : 30 fiches, 71 tâches.

**Les « présent sans écran » trouvés** (le calcul est fait, il manque l'affichage) :
1. `resultat['validation']` — écart contre PVGIS PVcalc (`SV/validation.py::ecart_vs_pvcalc`, appelé dans `SV/simulation.py`) : aucun lecteur
   dans `FE/` (grep `validation` dans `FE/production` : 0) ni dans `SV/rapport/` (ACAL475 l'imprimera au rapport, jamais à l'écran).
2. `production.projection` — tableau pluriannuel (`ET/vieillissement.py::tableau_pluriannuel`, posé par `SV/simulation.py`) : grep
   `projection` dans `FE/` et `SV/rapport/` : aucun lecteur de ce bloc.
3. Bornes d'ombrage électrique (`ET/mismatch_ombrage.py::appliquer` : `bornes`, `ecart_bornes_pct`) : ACAL462 les imprime au rapport
   seulement ; aucun écran.
4. `heures_sous_demarrage` (`ET/mppt.py`) : 0 lecteur nommé en `FE/` et en rapport.
5. Colonnes choisies de l'export horaire (`SV/export_csv.py`, CALX313, paramètre `colonnes` documenté par `views/export_csv.py`) : l'appel
   `frontend/src/api/calepinage/simulation.js::exportCsv(id, quoi)` ne transmet jamais `colonnes`.
6. Accès solaire chiffré + proposition « Retirer ces modules » (`RP/shadingUi.ts::ensureAccessBlock`, `LIB/shadingEngine.ts::proposeShadedRemoval`) :
   créés seulement si `#rp9-heatmap-toggle` existe, ce que l'atelier ERP ne monte pas (grep `rp9-solar-access|rp9-heatmap` dans `FE/` : 0) —
   ACAL436 le branchera.
7. `performance.pr_corrige_temperature` (`SV/performance.py`) : 0 lecteur en `FE/` et rapport.
8. Série horaire persistée avec `p_dc_kw`, `p_ac_kw`, `ecretage_kw`, `batterie_soc_pct`, `reseau_import_kwh`, `reseau_export_kwh`
   (`SV/chaine_pertes.py::COLONNES_SERIE_PERSISTEE`) : de quoi tracer l'histogramme d'écrêtage et la courbe entrée/sortie, aucun graphe ne le fait.

---

## 2. Fiches

### CAP-D4-01 — Écart du moteur contre PVGIS à l'écran : « quel chiffre croire »
- Besoin : « deux logiciels me donnent 3-5 % et 11-12 %, lequel croire ? » ; « simulé contre PVGIS, qui a raison ? ».
- Preuves : B5fr #3 (14 sources) ; B5en groupe 11 (7 fils) ; B5es K03 (10 fils) ; B4 §5 P14, P19 ; B3 ligne 66 ; B5de K14 (8 fils / 9 voix) ;
  B7 grappe 12 — 7 lanes, forums réels. URL : https://www.energeticambiente.it/threads/31639/ ·
  https://github.com/pvlib/pvlib-python/discussions/2654 · https://forum.valentin-software.com/topic/447-maximum-feed-in-power-clipping/
- Qui le fait : HelioScope publie un écart à PVsyst ; PVsyst publie ses validations ; aucun ne montre l'écart DU projet ouvert.
- Chez nous : PRÉSENT SANS ÉCRAN — `SV/validation.py::ecart_vs_pvcalc` rend `resultat['validation']` (écart annuel et mensuel, tolérance
  SAISIE `tolerance_validation_pct`, verdict seulement si tolérance) ; aucun lecteur écran. ACAL474 (banc 4 sites) et ACAL475 (note au rapport)
  sont DÉJÀ PLANIFIÉS mais ne couvrent pas l'écran.
- Plus petite version : sous le chiffre héros de l'onglet Production (ACAL443), une ligne « PVGIS seul donne x kWh (écart y %) — l'écart
  vient surtout de : <poste de la cascade le plus grand qui n'existe pas dans PVGIS> » ; sans tolérance saisie : écart affiché, aucun verdict ;
  sans réponse PVGIS : la ligne nomme le motif servi. Rien de calculé de neuf : lecture de `validation` et de `cascade`.
- Simplicité : étape Résultats, essentiel (une ligne) ; le détail mensuel sous « Mode expert ».
- Tâches :
  1. Afficher l'écart contre PVGIS sous le chiffre héros ; fini quand l'exemple `calepinage_simulation.json` rend « écart y % » et qu'un bloc
     sans réponse affiche le motif — `FE/production/PanneauProduction.jsx` (calepinage) ; dépend d'ACAL443.
  2. Nommer le poste qui explique le mieux l'écart (plus grande étape de la cascade absente du `loss` PVGIS) ; fini quand la phrase cite un nom
     d'étape servi et que la règle est un test — `SV/validation.py` (calepinage).
- Score : 7 × 3 / 1 = 21 — rang 1.

### CAP-D4-02 — Ombre partielle expliquée chaîne par chaîne, avec la parade
- Besoin : « une cheminée ombre deux modules, le string s'effondre ? » ; « faut-il un optimiseur sur ces deux-là ou une chaîne à part ? ».
- Preuves : B1 C07 ; B2 O27 ; B4 r11, §5 P4 ; B5de K01 (15 fils / 24 voix), K12 ; B5fr #19 (6), prop 9 ; B5es K02 (11 fils), prop 2 (14) ;
  B6 K26, R47 ; B7 grappe 18 (17 lignes / 19 votes), U10 ; B5en ligne #165 (~15 commentaires) — 10 lanes. URL :
  https://www.solarweb.net/forosolar/ (fil 60435 « sombra chimenea desplome del string ») · https://www.energeticambiente.it/threads/53277/ ·
  https://www.pvsyst.com/help/project-design/shadings/electrical-shadings-module-layout/index.html
- Qui le fait : PVsyst publie deux bornes (linéaire / chaînes) ; PV*SOL ombre au niveau des brins ; aucun ne dit la parade en une phrase.
- Chez nous : PRÉSENT SANS ÉCRAN pour les bornes (`ET/mismatch_ombrage.py::appliquer` : borne basse « module dérivé », borne haute « courant
  série », `ecart_bornes_pct`) ; ACAL462 = rapport seulement ; PARTIEL pour l'explication (aucune phrase, aucune parade, aucune hypothèse
  portrait/paysage nommée).
- Plus petite version : pour chaque chaîne dont l'écart de bornes > 0 : « Chaîne 2 : 3 modules ombrés le matin → perte entre a % et b %. Parades
  possibles : chaîne séparée, optimiseur sur ces 3 modules, déplacer » (parades = liste fixe de gestes, sans chiffre de gain sauf s'il est
  re-simulé par une variante) ; l'hypothèse « paysage : l'ombre d'un bas de rangée ne coupe qu'une sous-chaîne ; portrait : toutes » est écrite
  comme HYPOTHÈSE NOMMÉE (B5fr prop 9, B7 U10), jamais comme un chiffre.
- Simplicité : étape Électrique, une carte par chaîne touchée, rien à saisir ; masquée quand aucune chaîne n'est touchée.
- Tâches :
  1. Servir par chaîne `{bornes, ecart, modules_ombres, heures}` dans le bloc ombrage des chaînes ; fini quand le contrat porte la clé et que le
     cas multi-pans ne recopie plus le premier pan — `SV/ombrage_chaines.py`, `SV/chaine_pertes.py::cascade_de_la_somme` (calepinage) ;
     complète ACAL462.
  2. Afficher la carte « chaîne touchée par l'ombre » avec les parades — `FE/electrique/` (calepinage).
  3. Écrire l'hypothèse portrait/paysage comme mention de l'étape `mismatch_ombrage` ; fini quand la mention suit l'orientation réelle des
     modules du document — `ET/mismatch_ombrage.py`.
- Score : 9 × 3 / 2 = 13,5 — rang 2.

### CAP-D4-03 — Tableau de vieillissement sur 25 ans et courbe de garantie
- Besoin : « production de l'année 10 et de l'année 25 ? » ; « la garantie de 80 % à 25 ans est-elle tenue ? ».
- Preuves : B1 C16, V319, §6.3 (« page MANQUANTE, la donnée existe ») ; B4 souhait #12 ; B5en groupe 18 (5) ; B5de K35 ; B6 K34 ; B7 grappe 26
  (5 lignes / 11 votes) — 6 lanes. URL : https://www.pvsyst.com/help/project-design/array-and-system-losses/ageing-pv-modules-degradation/index.html
- Qui le fait : PVsyst « Aging tool » (E_Grid et PR par année) ; PV*SOL courbe de dégradation par surface.
- Chez nous : PRÉSENT SANS ÉCRAN — `ET/vieillissement.py::tableau_pluriannuel` → `production.projection` (`SV/simulation.py`), horizon lu dans
  `annees_exploitation` ou déduit de `garantie_production_mois` ; aucun lecteur écran ni rapport. Omis avec motif quand la fiche n'a pas sa
  dégradation.
- Plus petite version : un tableau année / kWh / % de l'année 1, et la courbe de la garantie fabricant (`garantie_pct_a_10_ans`,
  `garantie_pct_a_25_ans` déjà publiés par la fiche) sur le même graphe ; sans dégradation en fiche : le motif servi, rien d'autre.
- Simplicité : étape Résultats, replié « Sur 25 ans » ; une phrase « Année 25 : x kWh (garantie fabricant : y %) ».
- Tâches :
  1. Tracer `production.projection` et la garantie dans l'onglet Production — `FE/production/` (calepinage).
  2. Imprimer le tableau au rapport d'étude (section production) — `SV/rapport/production.py` (calepinage).
- Score : 6 × 2 / 1 = 12 — rang 3.

### CAP-D4-04 — Verdict d'ombrage en une phrase + « retirer les modules sous X » à seuil société
- Besoin : « dites-moi juste si l'ombre est grave et quoi enlever ».
- Preuves : B3 N7, lignes 96-97, 266 ; B6 R40 (Scanifly, Aurora, OpenSolar) ; B2 X02 (Reonic note 0-10) ; B5de K11 (10 fils) — 4 lanes. URL :
  https://docs.reonic.com/docs/en/offers-plan-pv-heatmap · https://help-center.helioscope.com/hc/en-us/articles/7835499970707-Optimize-shaded-modules
- Qui le fait : Reonic (< 5 % excellent, 5-10 % courant, > 10 % important), HelioScope « Optimize shaded modules ».
- Chez nous : PRÉSENT SANS ÉCRAN dans l'ERP — `RP/shadingUi.ts` publie moyenne/min/max et `proposeShadedRemoval` avec le bouton « Retirer ces
  modules », mais seulement si `#rp9-heatmap-toggle` est monté ; l'ERP ne le monte pas (ACAL436 DÉJÀ PLANIFIÉ le branchera). Le seuil
  `LIB/shadingEngine.ts::SOLAR_ACCESS_LOW = 0.75` est codé en dur (« perte d'un quart », sans source publiée) ; aucune phrase de verdict.
- Plus petite version : (a) le seuil devient un réglage société sourcé (clé nouvelle, vide ⇒ aucune proposition, la carte reste) ; (b) une
  phrase « Ombrage du pan : x % de l'énergie (perte annuelle de la cascade) ; n modules sous le seuil de la société » — AUCUNE étiquette
  « excellent/courant » tant que la société n'a pas saisi ses bornes de lecture (les seuils de Reonic sont cités, jamais préremplis).
- Simplicité : étape Panneaux, automatique après une ombre saisie.
- Tâches :
  1. Remplacer `SOLAR_ACCESS_LOW` par le réglage société lu au boot (absence ⇒ pas de proposition) — `LIB/shadingEngine.ts`, `RP/shadingUi.ts`,
     `SV/parametres_cles.py` (calepinage) ; dépend d'ACAL436.
  2. Publier la phrase de verdict sous l'accès solaire — `RP/shadingUi.ts`.
  3. Ajouter les bornes de lecture société (« courant », « important ») au registre, sans valeur — `SV/parametres_cles.py`.
- Score : 4 × 3 / 1 = 12 — rang 4.

### CAP-D4-05 — Perte due à la tension de démarrage de l'onduleur
- Besoin : « en passant de Huawei à Deye je perds 4-5 kWh par jour le matin ».
- Preuves : B5es K05 (13 fils), prop 11 ; B6 R3 (5 outils) ; B3 ligne 231 — 3 lanes. URL :
  https://www.solarweb.net/forosolar/ (fil 60635 « perdida kw al cambiar huawei deye ») · https://www.energeticambiente.it/threads/78071/
- Qui le fait : PVsyst et PVcase comptent la perte sous tension de démarrage / hors fenêtre MPPT.
- Chez nous : PRÉSENT SANS ÉCRAN + PARTIEL — `ET/mppt.py` compte `heures_sous_demarrage` avec `FT::ond_v_demarrage_v` « sans commander le
  retrait » : ni énergie retirée, ni ligne affichée.
- Plus petite version : une ligne d'information dans la cascade « x heures/an sous la tension de démarrage (≈ y kWh produits par le champ à ces
  heures) » ; le retrait de l'énergie reste une décision (voir « non vérifié »).
- Simplicité : automatique dès que la fiche porte la tension ; ligne du diagramme de pertes.
- Tâches :
  1. Publier l'énergie DC des heures sous démarrage dans l'entrée de l'étape `mppt` — `ET/mppt.py`.
  2. L'afficher dans la ligne dépliée du diagramme (ACAL444) — `FE/production/DiagrammePertes.jsx` ; dépend d'ACAL444.
- Score : 3 × 3 / 1 = 9 — rang 5.

### CAP-D4-06 — Export CSV : colonnes et pas choisis, ombrage par module et par heure
- Besoin : « exporter l'ombrage module par module et heure par heure » ; « choisir mes colonnes ».
- Preuves : B6 R21 (4 outils), K51 ; B5en prop 19, groupe I (VF9082) ; B4 (HelioScope CSV module) ; B3 lignes 61, 151 ; B7 grappe 48 — 5 lanes.
  URL : https://forum.valentin-software.com/topic/9082-export-of-shading-data/ ·
  https://help-center.helioscope.com/hc/en-us/articles/8536799301523-Hourly-Production-Report-CSV
- Chez nous : PRÉSENT SANS ÉCRAN — `SV/export_csv.py` (CALX313) accepte `colonnes` (sous-ensemble de `COLONNES_HORAIRE`) et `pas`
  (`horaire`, `15min` refusé avec motif) ; `frontend/src/api/calepinage/simulation.js::exportCsv(id, quoi)` ne les passe jamais. ABSENT :
  export par module (`EXPORTS = ('horaire', 'mensuel', 'ombrage')`, l'ombrage étant la matrice 12×24 du pan) et agrégat journalier.
- Plus petite version : cases à cocher des colonnes dans `PanneauSeries.jsx` ; un export `ombrage_modules` long (module, mois, heure, facteur)
  lu dans `ET/acces_module.py` ; un pas `jour` (agrégat déjà codé : `chaine_pertes.py::_agreger_au_jour`).
- Simplicité : « Mode expert » seulement (outil d'ingénieur).
- Tâches :
  1. Passer `colonnes` depuis l'écran — `simulation.js` (append-only), `FE/atelier/PanneauSeries.jsx`.
  2. Ajouter l'export `ombrage_modules` — `SV/export_csv.py`.
  3. Ajouter le pas `jour` à l'export horaire — `SV/export_csv.py`.
- Score : 5 × 1 / 1 = 5 — rang 6 (en tête par la règle « sans écran »).

### CAP-D4-07 — Fiche INTERNE « les pertes expliquées au client en 6 postes »
- Besoin : « mes clients ne comprennent pas les graphiques ; donnez-moi six phrases ».
- Preuves : B4 r2 (VF1094) ; B6 R39, K92 (SolarEdge, PVsyst, PVcase) ; B5es K35 (11 fils) ; B5fr #8 (9) — 4 lanes. URL :
  https://forum.valentin-software.com/topic/1094 (B4 « VF1094 ») · https://www.solarweb.net/forosolar/ (fil 60435)
- Chez nous : ABSENT — la cascade (`SV/chaine_pertes.py::ORDRE_ETAPES`, 25 étapes) n'a aucun regroupement en postes lisibles.
- Plus petite version : six postes FIXES regroupant les étapes servies (Ombre ; Chaleur ; Saleté et neige ; Câbles et conversion ; Optique ;
  Arrêts) ; chaque poste = somme des étapes servies + une phrase-gabarit ; étape omise ⇒ « non compté (motif) ». Feuille interne en
  `Documents`, HORS `/proposal` (règle #4).
- Simplicité : étape Documents, un bouton.
- Tâches :
  1. Servir le regroupement en 6 postes depuis la cascade (table de correspondance étape → poste, testée sur ORDRE_ETAPES) — `SV/diagramme_pertes.py`.
  2. Rendre la feuille PDF interne — `SV/documents/` (calepinage).
- Score : 4 × 3 / 1 = 12 — rang 7 (après les « sans écran »).

### CAP-D4-08 — Écrêtage DC/AC en histogramme, distribution de puissance, courbe entrée/sortie du jour
- Besoin : « 154 % de DC/AC, est-ce normal ? combien je perds ? » ; « voir où l'onduleur écrête ».
- Preuves : B1 C11, §6.1 p. 9 ; B6 R30 ; B4 §5 P9, P10, « adoré » PV*SOL éditeur de diagrammes ; B3 ligne 227 ; B5es K18 (9) — 5 lanes. URL :
  https://www.pvsyst.com/help/project-design/grid-connected-system-definition/inverter-array-sizing.html ·
  https://forum.pvsyst.com/topic/3160-clipping-loss/
- Chez nous : PARTIEL — `ET/ecretage.py` calcule l'écrêtage horaire ; la série persistée porte `p_dc_kw`, `p_ac_kw`, `ecretage_kw`
  (`SV/chaine_pertes.py::COLONNES_SERIE_PERSISTEE`) ; aucun histogramme (grep `histogram|distribution_puissance` : 0). La journée type par mois
  existe (`FE/production/TapisHoraire.jsx`).
- Plus petite version : histogramme énergie par classe de puissance (classes de 5 % de Pnom AC) avec la ligne Pnom, et phrase « x % de
  l'énergie DC écrêtée à ce ratio » ; courbe jour P_DC contre P_AC dans la journée type existante.
- Simplicité : « Mode expert » (étape Électrique, carte DC/AC).
- Tâches :
  1. Servir l'histogramme depuis la série persistée — `SV/chaine_pertes.py` ou module neuf `SV/distribution.py`.
  2. Le tracer — `FE/production/` (calepinage).
  3. Ajouter P_DC/P_AC à la journée type — `FE/production/TapisHoraire.jsx`.
- Score : 5 × 2 / 1 = 10 — rang 8.

### CAP-D4-09 — Liste « ce que cette simulation ne modélise pas »
- Besoin : « pourquoi ce n'est pas modélisé (bifacial vertical, MPPT local) ? dites-le ».
- Preuves : B4 r16 ; B5en prop 14 (4 fils) ; B7 U22 (15 lignes, IEA T13) ; B5de K36, P7 — 4 lanes. URL :
  https://iea-pvps.org/wp-content/uploads/2020/01/Uncertainties_in_PV_System_Yield_Predictions_and_Assessments_by_Task_13.pdf ·
  https://forum.valentin-software.com/topic/585-considering-snow-in-the-calculation/
- Chez nous : PARTIEL — `SV/chaine_pertes.py::TOUJOURS_OMISES` (spectral, diodes, neige) et `SV/rapport/pertes.py` imprime chaque étape omise
  avec son motif ; manque la liste de ce qui n'entre dans AUCUNE étape (ombrage du diffus avant ACAL461, sous-horaire, suiveurs, I-V cellule,
  vent/neige normatifs).
- Plus petite version : une constante `HORS_MODELE` (texte, sans chiffre) + les étapes omises, en un encadré « Limites connues » en bas de
  l'onglet Pertes et de l'annexe hypothèses.
- Tâches :
  1. Déclarer et servir `limites_connues` — `SV/chaine_pertes.py`.
  2. L'afficher (écran) et l'imprimer (annexe) — `FE/production/DiagrammePertes.jsx`, `SV/rapport/annexe_hypotheses.py`.
- Score : 4 × 2 / 1 = 8 — rang 9.

### CAP-D4-10 — Déclassement thermique de l'onduleur (chaleur)
- Besoin : « à 45 °C mon onduleur plafonne, le logiciel ne le voit pas ».
- Preuves : B1 C03, C21 ; B5fr #21, prop 6 (6) ; B6 K64 ; B7 grappe 66, U29 (3 lignes / 7 votes) ; B5en P2.2 « Chaleur » — 5 lanes. URL :
  https://github.com/pvlib/pvlib-python/issues/2360 · https://www.pvsyst.com/help/component-database/grid-inverters/grid-inverters-main-interface/index.html
- Chez nous : ABSENT — grep `derat|déclass` dans `ET/onduleur.py`, `ET/ecretage.py` : 0 ; la borne d'écrêtage est `puissance_ac_kw` constante.
  `FT` n'a aucun champ de déclassement.
- Plus petite version : deux champs optionnels de fiche (température de début, pente %/°C ou point Pmax à T), lus par `ET/ecretage.py` avec
  `t2m_c` servi ; vide ⇒ mention « déclassement thermique non modélisé — fiche incomplète » ; jamais demandé au commercial. Remplissable par
  l'import .OND (CALX339/356 ouvertes).
- Tâches :
  1. Ajouter les deux champs — `FT` (calepinage) + migration `apps/stock/migrations/` (stock, ajout seul ⇒ à router si refusé).
  2. Appliquer la borne horaire déclassée — `ET/ecretage.py`.
  3. Lire ces champs à l'import .OND si le fichier les porte — `apps/stock/importers/fiche_pan_ond.py` (calepinage) ; dépend de CALX356.
- Score : 5 × 3 / 2 = 7,5 — rang 10.

### CAP-D4-11 — Salissure : fréquence de nettoyage et inclinaison minimale d'autonettoyage
- Besoin : « poussière : je nettoie tous les mois, combien je gagne ? » ; « à 5° la pluie ne lave plus ».
- Preuves : B5nl prop 6, cluster 19 ; B7 U20, grappe 41 ; B5es K28, prop 18 ; B5fr #27, § 3 (thèse de Rabat) ; B5en groupe 31 (MDPI Amman) —
  5 lanes. URL : https://fritts.nl/zonnepanelen-oost-west-plat-dak/ · https://www.mdpi.com/1996-1073/18/22/5876
- Chez nous : ABSENT — `ET/salissure.py` lit 12 valeurs `salissure_mensuelle_pct` (omise sans source) ; grep `nettoyage` : 0 ; aucune
  dépendance à l'inclinaison.
- Plus petite version : (a) champ optionnel « nettoyages par an » rangé avec sa source, AFFICHÉ à côté de la salissure, sans aucun calcul
  tant qu'aucun taux d'accumulation sourcé n'est saisi (règle CALX161) ; (b) avertissement non bloquant quand l'inclinaison d'un pan est
  sous le seuil société « inclinaison d'autonettoyage » (clé sans valeur).
- Tâches :
  1. Ajouter les deux clés (fréquence, seuil d'inclinaison) au registre — `SV/parametres_cles.py`.
  2. Publier l'avertissement d'inclinaison et la fréquence dans l'entrée de l'étape — `ET/salissure.py`.
- Score : 5 × 3 / 2 = 7,5 — rang 11.

### CAP-D4-12 — Plage « normale » de chaque perte et garde-fous de vraisemblance des entrées
- Besoin : « 3,9 % d'ombrage proche, c'est acceptable ? » ; « j'ai tapé 60° au lieu de 60 % ».
- Preuves : B3 N30 ; B7 U14 (9 lignes / 5 votes), U27, grappe 60 ; B5fr #23, prop 7 ; B5de K09, P1 (13 fils) ; B6 K57 — 5 lanes. URL :
  https://help-center.helioscope.com/hc/en-us/articles/8198852043027-Typical-Loss-Factors · https://forum-photovoltaique.fr/viewtopic.php?t=30516
- Chez nous : PARTIEL — `SV/chaine_pertes.py::RENDEMENT_SPECIFIQUE_PLAUSIBLE_KWH_KWC = (600.0, 2400.0)` avertit sur le rendement spécifique
  (borne citée au plan ACAL54/C-ACAL-079, pas à une page publiée) ; `CC/garde_fous.py` = contrôles géométriques ; aucune plage par étape,
  aucun contrôle latitude/longitude inversées ni azimut aberrant.
- Plus petite version : une table `plages_usuelles` par étape, chaque bande copiée d'une page publiée (HelioScope Typical Loss Factors, PVsyst)
  avec URL ; une étape hors bande ⇒ pastille « inhabituel » + la page source ; une étape sans bande sourcée ⇒ rien. Cinq règles d'entrée
  déterministes (inclinaison > 60° signalée, lat/long hors Maroc, etc.) en avertissement, jamais en blocage.
- Tâches :
  1. Compiler `plages_usuelles` (données sourcées, comme ACAL404) — `SV/` données (calepinage).
  2. Publier la pastille par étape — `SV/chaine_pertes.py`.
  3. Afficher la pastille — `FE/production/DiagrammePertes.jsx` ; dépend d'ACAL444.
  4. Ajouter les règles d'entrée — `CC/garde_fous.py`.
- Score : 5 × 3 / 2 = 7,5 — rang 12.

### CAP-D4-13 — Deuxième source météo gratuite et écart annoncé (SARAH3 / ERA5 / NASA POWER)
- Besoin : « PVGIS, Meteonorm, PVsyst divergent : de combien est-on sûr ? ».
- Preuves : B1 C06 ; B6 R1 (7 outils), K31 (41 lignes, socle « table stakes ») ; B7 U3 (13 lignes / 26 votes), grappe 7 ; B5es K12 (7) ;
  B5fr #13, #26 ; B5de K45 — 6 lanes. URL : https://www.pvsyst.com/help/meteo-database/compare-meteo-data/index.html ·
  https://github.com/pvlib/pvlib-python/issues/2453
- Chez nous : PARTIEL — `SV/pvgis_serie.py::BASES_RAYONNEMENT = ('PVGIS-SARAH3', 'PVGIS-ERA5')` : ERA5 est ADMIS (choix explicite), jamais
  comparé ; NASA POWER : grep 0 ; la clé `sigma_biais_meteo_pct` existe, sans valeur.
- Plus petite version : 2e appel PVGIS en cache sur l'autre base, même plan ; écart annuel et mensuel publiés dans le bloc météo et à
  l'annexe hypothèses ; AUCUN seuil, aucune substitution silencieuse. NASA POWER (gratuit, sans compte — à confirmer) en 3e source plus tard.
- Tâches :
  1. Simuler sur la base alternative et servir l'écart — `SV/pvgis_serie.py`, `SV/chaine_pertes.py::_bloc_meteo_publie`.
  2. Afficher la ligne sous le bandeau de provenance — `FE/production/BandeauProvenanceProduction.jsx`.
  3. Client NASA POWER (série horaire) — module neuf `SV/` ; dépend d'ACAL454-455 (lecture d'une série horizontale + transposition).
- Score : 6 × 2 / 2 = 6 — rang 13.

### CAP-D4-14 — Courbe « % de direct perdu » heure par heure sur une journée choisie
- Besoin : « le 21 décembre, entre 9 h et 11 h, combien je perds ? ».
- Preuves : B1 C09 ; B4 (PV*SOL ombrage par module moyenné à l'heure) ; B5es K01 (9 fils) — 3 lanes. URL :
  https://www.pvsyst.com/help/project-design/shadings/near-shadings-3d-construction/view-tools/shadows-drawing.html
- Chez nous : ABSENT — la matrice 12×24 (`ET/ombrage_proche.py`) et l'animation (`RP/soleilPlay.ts`) existent ; aucune courbe.
- Plus petite version : sous la barre du soleil (ACAL434), une courbe 24 points lue dans la matrice du mois choisi + une phrase.
- Tâches : 1. Tracer la courbe sous la barre du soleil — `RP/` (calepinage) ; dépend d'ACAL434.
- Score : 3 × 2 / 1 = 6 — rang 14.

### CAP-D4-15 — Heure légale contre heure solaire sur la course du soleil
- Besoin : « la position du soleil est fausse de 12° » (heure d'été) ; au Maroc l'heure légale change pendant le Ramadan.
- Preuves : B4 r12, §5 S4 ; B5es K29, prop 8 ; B6 R57, K83 — 3 lanes. URL : https://forum.valentin-software.com/topic/8531 (VF8531) ·
  https://www.solarweb.net/forosolar/ (fil 3099)
- Chez nous : PARTIEL — le serveur calcule en UTC avec l'équation du temps (`CC/soleil.py::position_solaire`) ; l'atelier utilise l'heure
  SOLAIRE pure, sans le dire (`LIB/roofPro2.ts::sunDirection` : angle horaire H = 15° × (heure − 12), ni équation du temps, ni longitude).
- Plus petite version : le curseur d'heure affiche les deux (« 12 h solaire = 13 h 2x heure légale ») d'après le fuseau du site
  (`FE/reglages/ReglagesSite.jsx`) et `CC/soleil.py`.
- Tâches :
  1. Servir la correspondance solaire → légale du jour choisi — `CC/soleil.py` / vue existante.
  2. L'afficher sur le curseur et le diagramme — `FE/SunDiagram.jsx`, `RP/` ; dépend d'ACAL434.
- Score : 3 × 2 / 1 = 6 — rang 15.

### CAP-D4-16 — Diodes de dérivation : modèle par sous-chaînes (portrait / paysage)
- Besoin : identique à CAP-D4-02, quand il faut un chiffre et pas seulement des bornes.
- Preuves : mêmes lanes que CAP-D4-02 (B1 C07, B6 R47 : PVsyst 8.0.6, SAM 2017).
- Chez nous : ABSENT — étape `diodes` déclarée dans `ORDRE_ETAPES` et toujours omise (`TOUJOURS_OMISES['diodes']`) ; aucun champ « nombre de
  sous-chaînes » dans `FT` (grep `diode` : 0).
- Plus petite version : champ de fiche « sous-chaînes par module » ; chaque module vu comme n bandes dont l'accès solaire est pris dans la
  grille de cellules déjà calculée par l'atelier ; résultat borné par les bornes de CAP-D4-02 ; vide ⇒ étape omise comme aujourd'hui.
- Tâches :
  1. Champ de fiche — `FT` + migration stock (ajout seul).
  2. Servir l'accès solaire par bande de module — `LIB/shadingEngine.ts` (calepinage).
  3. Calculer l'étape `diodes` — `ET/` neuf (calepinage) ; dépend de 1-2.
- Score : 9 × 2 / 3 = 6 — rang 16.

### CAP-D4-17 — Production mesurée contre simulée, par chantier livré
- Besoin : « 12 mois après, le client me dit qu'il produit moins : qui a tort ? ».
- Preuves : B1 C08 ; B5fr prop 2 (7) ; B7 U5 (27 lignes / 6 votes), grappe 42 ; B4 §5 P19 ; B5en lignes #466, #756 — 5 lanes. URL :
  https://github.com/NatLabRockies/SAM/issues/1775 · https://www.pvsyst.com/help/measured-data/index.html
- Chez nous : ABSENT — `SV/asbuilt.py` compare le POSÉ au prévu, pas l'énergie.
- Plus petite version : saisir 12 valeurs mensuelles (relevé onduleur) sur l'as-built ; écart en % au P50 ; option : simuler l'année
  observée (PVGIS seriescalc de cette année) pour séparer météo et installation. Aucun engagement de garantie (CIQ646).
- Tâches :
  1. Ranger les 12 valeurs mesurées avec leur source — `SV/asbuilt.py` (+ migration calepinage).
  2. Servir l'écart au P50 et à l'année observée — `SV/` (calepinage).
  3. Écran « Livré contre prévu » dans `FE/atelier/PoseReelle.jsx`.
- Score : 5 × 2 / 2 = 5 — rang 17.

### CAP-D4-18 — Rapport d'étude : pages manquantes (synthèse, modèles, autoconso/batterie, IAM, photos)
- Besoin : « la page que le gérant lit d'abord » ; « mes photos de visite dans le dossier ».
- Preuves : B1 C04, §6.3 ; B6 R28 (3 outils), R49 ; B4 r13, souhait #6 ; B3 ligne 190 (archelios) ; B5en groupe 8 (9 fils) — 5 lanes. URL :
  https://www.spiritenergy.co.uk/hubfs/Solar%20Consultation%20Advanced%20Modelling%20-%20PVSol.pdf (rapport réel PV*SOL)
- Chez nous : PARTIEL — `contract_samples/rapport_etude.json` : 10 sections (`garde, site_meteo, systeme, pertes, production, ombrage,
  electrique, nomenclature, preuve, hypotheses`) ; pas de synthèse, pas d'autoconsommation/batterie (servies, non imprimées), pas de table IAM
  (la loi vit dans `ET/iam.py`), aucune photo (grep `photo` dans `SV/rapport/` : 0, alors que `SV/photos.py` existe).
- Plus petite version : 4 rédacteurs découverts par nom (comme `MODULES_DE_SECTION`), chacun lisant des blocs servis.
- Tâches :
  1. Section `synthese` en 1 page — `SV/rapport/synthese.py` (neuf, calepinage).
  2. Section `autoconsommation` (et batterie) — `SV/rapport/` ; dépend d'ACAL445.
  3. Table IAM (angle → facteur du modèle retenu) — `ET/iam.py` (servir la table) + `SV/rapport/pertes.py`.
  4. Section photos du site — `SV/rapport/` lisant `SV/photos.py`.
  5. Paramètres généraux nommant les modèles (transposition, diffus, thermique, IAM) — `SV/rapport/site.py` ; complète ACAL455.
- Score : 5 × 2 / 2 = 5 — rang 18.

### CAP-D4-19 — Schéma « où va l'énergie » (Sankey)
- Besoin : « montrer d'un coup production → maison, batterie, réseau, pertes ».
- Preuves : B1 C01 ; B6 R46 (PV*SOL 2025, PVsyst, SAM) ; B7 U30, grappe 78 — 3 lanes. URL :
  https://valentin-software.com/en/product-news-blog-en/pvsol-premium-2025-available-now/
- Chez nous : ABSENT — le diagramme est une cascade en barres (`FE/production/DiagrammePertes.jsx`) ; le genre d'image `sankey` est refusé
  « aucun lecteur » (`SV/images_document.py::GENRES_IMAGE`, ACAL224).
- Plus petite version : SVG serveur alimenté par `cascade`, `autoconsommation`, `batterie` déjà servis ; un flux omis reste visible et nommé.
- Tâches : 1. SVG serveur — `SV/diagramme_pertes.py`. 2. Affichage Résultats + impression rapport — `FE/production/`, `SV/rapport/`.
- Score : 3 × 3 / 2 = 4,5 — rang 19.

### CAP-D4-20 — Perte de l'optimiseur et optimiseur posé seulement sur les modules ombrés
- Besoin : « l'optimiseur ne vaut que sur les 3 modules à l'ombre ».
- Preuves : B1 C17, V303 ; B5de K12 (6 fils / 8 voix), P4 ; B5nl cluster 8 ; B3 ligne 266 — 4 lanes. URL :
  https://www.photovoltaikforum.com/thread/266117 · https://www.pvsyst.com/help/project-design/array-and-system-losses/index.html
- Chez nous : PARTIEL — `FT::opt_rendement_pct` existe mais aucun service ne le lit (grep `opt_rendement` dans `SV/` : 0) ; une ligne
  d'affectation peut porter `optimiseur` (`ET/mismatch_ombrage.py::CHAMPS_SANS_CONTRAINTE`) mais exempte alors TOUTE la chaîne
  (`_chaines_sans_contrainte`) ; aucun écran ne pose ce drapeau (grep `optimiseur` dans `FE/plan/` : 0).
- Plus petite version : étape « optimiseur » qui applique le rendement de fiche aux seuls modules équipés ; drapeau par module dans
  l'affectation ; la chaîne n'est exemptée que si tous ses modules ombrés sont équipés.
- Tâches : 1. Étape rendement optimiseur — `ET/` + `SV/chaine_pertes.py`. 2. Exemption par module — `ET/mismatch_ombrage.py`.
  3. Drapeau par module à l'écran d'affectation — `FE/plan/AffectationChaines.jsx`.
- Score : 4 × 2 / 2 = 4 — rang 20.

### CAP-D4-21 — Rapport d'ombrage capturé tout seul, échelle fixe 0-100 %, une image par pan
- Besoin : « l'échelle de couleur se lit comme absolue (70 % lu, 9,91 % réel) » ; « sans capture manuelle ».
- Preuves : B4 r10, souhait #11 ; B5de K11 (10 fils) ; B5en groupe 27, groupe F (VF9912) ; B6 K25 (11 outils) — 4 lanes. URL :
  https://forum.valentin-software.com/topic/9912 (VF9912) · https://help-center.helioscope.com/hc/en-us/articles/8198878093971-Shade-Reports
- Chez nous : PARTIEL — `SV/rapport_ombrage.py::html_carte_de_chaleur` imprime la DERNIÈRE image déposée par le navigateur
  (`FE/documents/deposerImage.js`, geste manuel, genre `ombrage`) ; la teinte vient de `LIB/shadingEngine.ts::solarAccessColorRGB` (domaine
  0-1 fixe) ; légende graphique = ACAL441 (DÉJÀ PLANIFIÉ, écran seulement).
- Plus petite version : à la génération du rapport, capture automatique d'une vue de dessus par pan avec la légende 0-100 % imprimée.
- Tâches : 1. Capture par pan à la demande du rapport — `RP/`, `FE/documents/`. 2. Légende imprimée dans `SV/rapport_ombrage.py` ; dépend d'ACAL441.
- Score : 4 × 2 / 2 = 4 — rang 21.

### CAP-D4-22 — Albédo par type de surface et par saison
- Besoin : « gravier, béton clair, sable : quel albédo ? » (toits-terrasses, bifacial au sol).
- Preuves : B7 U9 (20 lignes), grappe 68 ; B1 V145, V206, P10 — 2 lanes. URL :
  https://www.pvsyst.com/help/physical-models-used/irradiation-models/albedo-usual-coefficients.html · https://github.com/pvlib/pvlib-python/issues/421
- Chez nous : PARTIEL — clé `albedo_mensuel` (table mensuelle, `SV/parametres_cles.py`) lue par `SV/chaine_pertes.py::_albedo_face_avant` ;
  `SV/bifacial.py::gain_bifacial` prend UN albédo saisi ; aucun choix par type de surface.
- Plus petite version : liste de surfaces dont la valeur est imprimée par une page (PVsyst « usual coefficients » : valeurs UNIQUES seulement,
  jamais le milieu d'une fourchette) ; choisir une surface remplit `albedo_mensuel` avec sa source.
- Tâches : 1. Données sourcées des surfaces — `SV/` données. 2. Sélecteur dans Réglages simulation — `FE/reglages/ReglagesSimulation.jsx`.
- Score : 2 × 2 / 1 = 4 — rang 22.

### CAP-D4-23 — Pans triés par accès solaire et valeurs au survol des éléments dessinés
- Preuves : B6 R24 (Scanifly TSRF, OpenSolar, PVsyst), R23 (4 outils) ; B3 ligne 298 — 2 lanes.
- Chez nous : PARTIEL — accès par module servi (`SV/ombrage_chaines.py::acces_par_module`) ; aucun tri (grep `sort.*acces` : 0) ; survol
  seulement pour l'ombrage (`RP/infoBulleOmbrage.ts`).
- Tâches : 1. Liste des pans triée par accès moyen dans l'étape Panneaux — `FE/`. 2. Info-bulle module (accès, kWh/an, chaîne) — `RP/`.
- Score : 2 × 2 / 1 = 4 — rang 23.

### CAP-D4-24 — Pertes depuis l'irradiation horizontale et tableau mensuel complet
- Besoin : voir le « gain d'inclinaison » et un tableau GlobHor / plan / effectif / T amb / PR par mois.
- Preuves : B1 C05, §6.3 ; B6 K85 ; B7 grappe 28 — 3 lanes. URL : https://www.pvsyst.com/help/project-design/results/loss-diagram.html
- Chez nous : PARTIEL — mensuel = `p50_kwh` seul (`SV/chaine_pertes.py::_bloc_production`) ; DÉJÀ PLANIFIÉ : irradiation incidente mensuelle
  (ACAL451) et sa colonne au rapport (ACAL452). Restent : horizontale (requête PVGIS à 0°), T amb mensuelle (`t2m_c` déjà en série), PR
  mensuel, `pr_corrige_temperature` (servi, non lu).
- Tâches : 1. Servir GHI mensuel + T amb + PR mensuel — `SV/chaine_pertes.py`. 2. Premier poste « gain d'inclinaison » — `SV/diagramme_pertes.py`.
  3. Colonnes à l'écran et au rapport — `FE/production/`, `SV/rapport/production.py` ; dépend d'ACAL451/452.
- Score : 3 × 2 / 2 = 3 — rang 24.

### CAP-D4-25 — Rapport d'étude éditable : variables de texte et export DOCX
- Preuves : B1 C19 ; B5de K23 (4 fils / 13 voix), P19 ; B5es K10, prop 12 ; B7 U26 ; B6 K49 ; B5en groupe 8 — 6 lanes (adéquation faible :
  document interne).
- Chez nous : ABSENT — grep `docx` : 0 ; aucune variable `{{…}}` dans `SV/rapport/mise_en_page.py` (seul `SV/documents/manuel_proprietaire.py`
  en porte) ; langues FR/EN.
- Tâches : 1. Variables dans les textes société du rapport — `SV/rapport/sections_societe.py`. 2. Export DOCX interne — seulement si Reda le
  demande (dépendance nouvelle `python-docx` à signaler).
- Score : 6 × 1 / 2 = 3 — rang 25.

### CAP-D4-26 — Calepinages d'exemple prêts à ouvrir
- Preuves : B1 C18 ; B6 R52, K69 ; B7 U4 (14 lignes) — 3 lanes. Chez nous : ABSENT — `management/commands/` ne contient aucune commande de
  semence d'exemple. Plus petite version : maison, toit plat C&I, pompage, tirés des goldens d'ACAL382.
- Tâches : 1. Commande `seed_calepinages_exemple` — `management/commands/` (calepinage) ; dépend d'ACAL382. 2. Bouton « Essayer avec un
  exemple » sur la liste vide — `FE/`.
- Score : 3 × 2 / 2 = 3 — rang 26.

### CAP-D4-27 — Contrôle qualité d'un fichier météo déposé et diagnostic nommé
- Preuves : B1 C15 ; B6 R27, K32 ; B7 U11 (13 lignes), grappe 22 ; B5en prop 6 (5 fils) — 4 lanes.
- Chez nous : PARTIEL — `SV/meteo_fichier.py` refuse en nommant ligne et colonne (`_cellule_numerique`, `_verifier_calendrier`,
  `MOTIF_HORIZONTAL_SEUL`, `MOTIF_SANS_FUSEAU`) ; aucun contrôle de décalage horaire (lever mesuré contre `CC/soleil.py`) ni de valeur
  au-dessus du soleil au zénith. Formats EPW/horizontal = ACAL454-456 (DÉJÀ PLANIFIÉS).
- Tâches : 1. Rapport de qualité 4 lignes (trous, décalage, négatifs, dépassement de l'extraterrestre) — `SV/meteo_fichier.py`.
  2. L'afficher à l'import — `FE/atelier/PanneauSeries.jsx`.
- Score : 4 × 1 / 2 = 2 — rang 27.

### CAP-D4-28 — Feuille de vérification (formules écrites en texte)
- Preuves : B5es prop 4 (6), K09 ; B5de P14 — 2 lanes. Chez nous : ABSENT — `SV/export_tableur.py` neutralise les formules (sécurité) ; aucun
  onglet qui ÉCRIT la formule en texte. Tâche : 1. Onglet « Vérification » (formules en texte + valeurs) — `SV/export_tableur.py`.
- Score : 2 × 1 / 1 = 2 — rang 28.

### CAP-D4-29 — Ombre de cadre, de pinces ou de différence de hauteur de châssis
- Preuves : B5es K30 (3 fils), prop 13 — 1 lane (adéquation : toits-terrasses à châssis lestés).
- Chez nous : ABSENT — grep `hauteur_cadre|frame_height` : 0. Tâche : 1. Avertissement entre deux fiches voisines de hauteur de cadre
  différente, sans chiffre — `CC/garde_fous.py`.
- Score : 1 × 2 / 1 = 2 — rang 29.

### CAP-D4-30 — Bilan carbone (GATED)
- Preuves : B1 C20 ; B6 K68 — 2 lanes. Chez nous : ABSENT (grep `carbone|co2` : 0). GATED tant que Reda ne fournit pas un facteur réseau
  marocain daté et sourcé. Tâche : 1. production × facteur, source imprimée — `SV/` (une ligne en Production).

---

## 3. Profil de départ : les valeurs publiées de B1 § 8.3

Préfixes : `H:` = https://www.pvsyst.com/help/ · `S:` = https://help.valentin-software.com/pvsol/en/ . Clés vérifiées dans
`SV/parametres_cles.py::CLES_SIMULATION` et `::CLES_ELECTRIQUE_SOCIETE`. « Sûr » = la page imprime une valeur UNIQUE (pas une fourchette),
présentée comme défaut ou valeur usuelle, applicable au Maroc, et la clé a la bonne forme. Toute copie reste conditionnée à la RELECTURE de
la page par ACAL404.

| id | Grandeur | Valeur imprimée | URL | Clé | Proposable ? |
|---|---|---|---|---|---|
| P01 | LID | « suggested default is 2% » (p-type) | H:project-design/array-and-system-losses/lid-loss.html | `lid_par_techno` | SÛR, pour le p-type seulement |
| P02 | Qualité module | règle « one-quarter of the difference » | H:…/module-quality-losses.html | `regle_qualite_module` (= `quart_pvsyst`) | SÛR |
| P03 | Mismatch fabricant | 2 % (> 3 modules en série) … 0 % (1) | H:…/array-mismatch-losses/index.html | `mismatch_fabricant_pct` | SÛR pour chaînes > 3 modules (clé = un seul %) |
| P04 | Mismatch tension entre chaînes | 0-0,15 % selon chaînes/MPPT | idem | — | non : aucune clé |
| P05 | IAM | Fresnel par défaut ; ASHRAE b0 = 0,05 | H:…/array-incidence-loss-iam.html | `modele_iam`, `b0_iam` | SÛR (b0 seulement si `ashrae`) |
| P06 | Câblage DC | 1,5 % à STC | H:…/ohmic-losses/array-ohmic-wiring-loss.html | — | non : calculé sur longueurs |
| P07 | Transformateur fer | 0,1 % de Pnom | H:…/external-transformer-losses.html | — | non : aucune clé |
| P08 | Coefficients U | libre 29/0 ; dos isolé 15/0 ; défaut 20/0 | H:…/array-thermal-losses/u-value-measurement.html | `thermique_par_pose` | SÛR (par type de pose) |
| P09 | Absorptivité | 0,9 | H:…/steady-state-thermal-model.html | — | non : non utilisée |
| P10 | Albédos usuels | tuiles rouges 0,33 ; herbe fraîche 0,26 ; acier galvanisé neuf 0,35 ; aluminium 0,85 ; asphalte mouillé 0,18 ; le reste en fourchettes | H:physical-models-used/irradiation-models/albedo-usual-coefficients.html | `albedo_mensuel` | SOUS CONDITION : valeurs uniques seulement, par surface choisie (CAP-D4-22) |
| P11 | Albédo typique | 0,2 (Hay) | H:…/the-hay-transposition-model.html | `albedo_mensuel` | SÛR avec P29 (deux outils, mention « valeur typique ») |
| P12 | Dégradation | partage Imp 80 % ; taux non chiffré | H:…/module-performance-degradation.html | `modele_degradation` | non : aucun taux |
| P13 | Températures de conception | 20/60/50 °C, Voc à −10 °C | H:…/design-temperatures.html | — | non : températures TMY du site |
| P14 | Ratio DC:AC | « default PNom ratio of 1.25 » ; seuils 3 % / 4 % de perte | H:…/grid-connected-system-definition/index.html ; …/inverter-array-sizing.html | `borne_usuelle_dc_ac` ; (`seuil_alerte_dc_ac` = autre grandeur) | SOUS CONDITION : 1,25 pour `borne_usuelle_dc_ac` si son sens est confirmé ; 3 %/4 % non |
| P15 | Salissure | ordres de grandeur, aucun défaut | H:…/soiling-loss.html | `salissure_mensuelle_pct` | non |
| P16 | Mismatch face arrière | « Defaults to 10% » | H:project-design/bifacial-systems/index.html | `bifacial_mismatch_arriere_pct` | SOUS CONDITION : la référence de la clé dit « cité en aide, jamais prérempli » (CALX177) — à trancher contre D-ACAL-31 |
| P17 | Horizon | ignoré sous 2° ; albédo atténué jusqu'à 20° | H:project-design/shadings/far-shadings-horizon/index.html | `attenuation_horizon` | non : la clé est un booléen |
| P18 | Rangées | angle limite 18-22° (conseil) | H:…/shed-optimization.html | — | non |
| P19 | Pompage | 6 h équivalentes, rendements | H:…/pumping-system-sizing.html | — | hors D4 (D5) |
| P20 | Autonome | 4 jours, C3/C1 | H:…/stand-alone-system-procedure.html | — | hors D4 (D5) |
| P21 | Seuils contrôleur | « does not use these exact values as defaults » | H:…/controller-operating-thresholds.html | — | non |
| P22 | Courbe onduleur auto | 3,0 ; 60 % ; 0,5 % | H:physical-models-used/grid-inverter/inverter-model-efficiency.html | — | non : aucune clé |
| P23 | Carbone | dégradation 1 % ; ACV 46 gCO₂/kWh | H:project-design/carbon-balance-tool/index.html | — | non (CAP-D4-30 gated) |
| P24 | Modèles PVsyst | Perez, ENGERER2 | H:…/transposition-model.html | — | non (PVGIS transpose) |
| P25 | Bas éclairement | Rshunt… | H:…/parameters-besides-datasheets.html | — | non (ACAL464 GATED) |
| P26 | σ météo | « typically 3–4% » | H:project-design/p50-p90-evaluations.html | `sigma_meteo_saisi_pct` | non : fourchette, et σ mesuré sur la fenêtre |
| P27 | ΔT PV*SOL | 29 / 28 / 22 K… | S:calculation/pv-modules/module-temperature/ | `thermique_par_pose` | non : ΔT ≠ Uc, conversion non publiée |
| P28 | Bilan PV*SOL | mismatch « estimated 2% » ; diodes 0,5 % | S:pages/results/energy-balance/ | `mismatch_fabricant_pct` | SÛR (confirme P03) ; diodes : aucune clé |
| P29 | Options PV*SOL | albédo « about 20% » ; mismatch 1-5 % | S:options/ | `albedo_mensuel` | SÛR pour 0,20 (avec P11) |
| P30 | Contrôle de configuration | facteur « at least 100% » | S:pages/inverters/configuration-check/ | `seuil_bas_dc_ac` | SOUS CONDITION : 1,00 si la clé désigne bien ce plancher |
| P31 | Polystring | 4 % / 10 % | S:pages/inverters/polystring-connection/ | `tolerance_polystring_*` | SOUS CONDITION : même note « jamais préremplie » que P16 (hors D4, D3) |
| P32 | Câbles | ρ cuivre 1,75·10⁻² | S:calculation/cables/ | — | non (UTE C 15-105 déjà retenue) |
| P33 | Bifacial | BF 0,7-0,8 | S:calculation/pv-modules/bifacial-modules/ | — | non : fiche fabricant |
| P34-P35 | Hors réseau, climatisation | — | S:… | — | hors D4 |
| P36 | Modèles PV*SOL | Hofmann, Hay & Davies | S:calculation/irradiation/… | — | non |
| P37 | Variabilité | 4,5 % (Europe centrale) | S:pages/financial-analysis/bankability/ | `sigma_meteo_saisi_pct` | non : pas le Maroc |
| P38 | COP PAC | — | S:calculation/thermal-system/ | — | hors périmètre |

Compte : 38 lignes ; 19 ont une clé existante ; **6 sûres** (P01, P02, P03+P28, P05, P08, P11+P29), **5 sous condition** (P10, P14, P16,
P30, P31), le reste non proposable ou hors D4. Clés du registre sans AUCUNE valeur publiée trouvée : `salissure_mensuelle_pct`,
`modele_degradation` (taux), `sigma_*`, `tolerance_validation_pct`, `indisponibilite_fenetres`, `auxiliaires_*`, `bifacial_hauteur_pose_m`,
`bifacial_taux_occupation`, `bifacial_pas_rangee_m`, `seuil_derivation_acces`, `fenetre_annees`, `mode_meteo`, `resolution_minutes`,
`annees_exploitation` (dérivée de la garantie), `plafond_modules_simules` (décision).

---

## 4. Les chiffres de la simulation qui demandent un « pourquoi » (pour D6)

P50 annuel et mensuel ; P75 / P90 / P95 et la variabilité interannuelle σ (et sa source) ; PR (et PR corrigé en température) ; rendement
spécifique kWh/kWc et l'avertissement 600-2400 ; perte totale % ; chaque étape de la cascade (horizon, ombrage proche, accès module,
inter-rangées, gain bifacial, IAM, salissure, neige, niveau d'irradiance, thermique et T cellule, qualité module, LID, mismatch fabricant,
mismatch d'ombrage et ses deux bornes, ohmique DC, MPPT et heures sous démarrage, rendement onduleur, écrêtage, ohmique AC, transformateur,
auxiliaires, indisponibilité) ; « borne haute — n pertes non renseignées » ; accès solaire moyen/min/max d'un pan et le seuil « fortement
ombragé » ; TOF/TSRF ; irradiation incidente ; écart contre PVGIS et sa tolérance ; écart au devis (`ecart_devis`) ; projection de l'année N
et la garantie ; énergie écrêtée et ratio DC/AC ; écart SARAH3/ERA5 (à venir) ; écart mesuré/simulé (à venir).

---

## 5. Correspondance id d'origine → sort

| Ids d'origine | Sort |
|---|---|
| B5fr #3 ; B5en g11 ; B5es K03 ; B4 P14, P19 ; B3 l.66 ; B5de K14 (part écart) ; B7 g12 (part validation) | CAP-D4-01 (+ ACAL474/475 planifiées) |
| B1 C07 ; B2 O27 ; B4 r11, P4 ; B5de K01 (part électrique), K12 (part chaîne) ; B5fr #19, prop 9 ; B5es K02, K14, prop 2, prop 5 ; B6 K26, R47 ; B7 g18, g44, U10 ; B5en #165, #193 | CAP-D4-02 et CAP-D4-16 |
| B1 C16, V319 ; B4 souhait #12 ; B5en g18 ; B5de K35 ; B6 K34 ; B7 g26 | CAP-D4-03 |
| B3 N7, l.96-97, l.266, l.34 ; B6 R40 ; B2 X02 ; B5de K11 (part verdict) | CAP-D4-04 (+ ACAL436) |
| B5es K05, prop 11 ; B6 R3 ; B3 l.231 | CAP-D4-05 |
| B6 R21, K51 ; B5en prop 19, groupe I, #421 ; B3 l.61, l.151, l.133 ; B7 g48 ; B2 O49 | CAP-D4-06 |
| B4 r2 ; B6 R39, K92 ; B5es K35 ; B5fr #8 | CAP-D4-07 |
| B1 C11 ; B6 R30, K28 ; B4 P9, P10 ; B3 l.227 ; B5es K18, prop 14 (part graphe) ; B7 g17 | CAP-D4-08 |
| B4 r16 ; B5en prop 14 ; B7 U22 ; B5de K36, P7 | CAP-D4-09 |
| B1 C03, C21 (part onduleur) ; B5fr #21, prop 6 ; B6 K64 ; B7 g66, U29 ; B5en P2.2 chaleur | CAP-D4-10 |
| B5nl prop 6, cl. 19 ; B7 U20, g41 ; B5es K28, prop 18 ; B5fr #27 ; B5en g31, P2.2 poussière, #978 | CAP-D4-11 |
| B3 N30 ; B7 U14, U27, g60 ; B5fr #23, prop 7 ; B5de K09 ; B6 K57 ; B5de P1 et B4 r1 (part plausibilité) | CAP-D4-12 (le « pourquoi » → D6) |
| B1 C06 ; B6 R1, K31 ; B7 U3, g7 ; B5es K12 ; B5fr #13, #26 ; B5de K45 | CAP-D4-13 |
| B1 C09 ; B4 (PV*SOL ombrage horaire) ; B5es K01 | CAP-D4-14 (+ ACAL434) |
| B4 r12, S4 ; B5es K29, prop 8 ; B6 R57, K83 | CAP-D4-15 |
| B1 C08 ; B5fr prop 2 ; B7 U5, g42 ; B5en #466, #756 | CAP-D4-17 |
| B1 C04, §6.3 ; B6 R28, R49, R51 (part synthèse) ; B4 r13, souhait #6 ; B3 l.190, l.107 ; B5en g8 (part photos) | CAP-D4-18 |
| B1 C01 ; B6 R46 ; B7 U30, g78 ; B3 l.250 | CAP-D4-19 |
| B1 C17, V303 ; B5de K12, P4 ; B5nl cl. 8 ; B3 l.266 | CAP-D4-20 |
| B4 r10, souhait #11 ; B5de K11 ; B5en g27, g F ; B6 K25 ; B3 l.46, l.298-299 ; B2 O28, X17, X20 | CAP-D4-21 (+ ACAL441) |
| B7 U9, g68 ; B1 V145, V206, P10 | CAP-D4-22 |
| B6 R24, R23 ; B3 l.298 | CAP-D4-23 |
| B1 C05 ; B6 K85 ; B7 g28 | CAP-D4-24 (+ ACAL451/452) |
| B1 C19 ; B5de K23, P19 ; B5es K10, K41, prop 12 ; B7 U26 ; B6 K49 ; B5en g8 ; B5nl prop 8 (arabe) | CAP-D4-25 |
| B1 C18 ; B6 R52, K69 ; B7 U4 | CAP-D4-26 |
| B1 C15 ; B6 R27, K32 ; B7 U11, g22 ; B5en prop 6, g28, #580 | CAP-D4-27 (+ ACAL454-456) |
| B5es prop 4, K09 ; B5de P14 | CAP-D4-28 |
| B5es K30, prop 13 | CAP-D4-29 |
| B1 C20 ; B6 K68 | CAP-D4-30 (GATED) |
| B5de K01 (diffus, facteur de vue) ; B7 g61 ; B2 X19 ; B4 §6.1 #5 ; B5en g27 (table) | DÉJÀ PLANIFIÉ : ACAL449, ACAL459, ACAL460, ACAL461, ACAL467 |
| B5de K14 (bifacial) ; B6 K29, R20 ; B7 g16 ; B5fr #31 ; B5en g34 ; B3 l.50 | DÉJÀ PLANIFIÉ : ACAL465 (horaire pvlib) ; vertical E-O → écarté |
| B5de K21 ; B7 g28 (édition) ; B2 A22 ; B4 « adoré » diagramme | DÉJÀ PLANIFIÉ : ACAL396, ACAL444 ; profil sourcé ACAL387/403/404/405 ; B5fr #28, prop 11 → ACAL404 |
| B7 g54 ; B6 K33 (neige) ; B2 A21 | DÉJÀ PLANIFIÉ : ACAL463 |
| B5en g33 ; B5nl cl. 20 ; B3 l.49 ; B6 K30 ; B2 A23 ; B4 P18 | DÉJÀ PLANIFIÉ : ACAL443 (P50 héros, P75/P90/P95 repliés) ; P99 écarté |
| B2 A24, O30 | DÉJÀ PLANIFIÉ : ACAL398, ACAL401 (barre de totaux) |
| B3 l.47, l.237 ; B7 g22 ; B5en g28 | DÉJÀ PLANIFIÉ : ACAL454-456 |
| B5de K25, P2 ; B5fr #11, prop 4 ; B7 U12 ; B2 rang 18 ; B5en prop 5 ; B5es K25, prop 17 ; B5en prop 4 ; B5fr #1, prop 5 ; B5nl cl. 24, prop 5 | HORS D4 → D1 (horizon et obstacles relevés) ; ACAL458 pour l'import de fichier |
| B1 C02, C23 ; B6 R13 ; B5fr #32, prop 15 ; B5es K50 ; B5en g32 ; B2 A18 | HORS D4 → D2 (balayage ACAL468/469) |
| B1 C10 ; B6 R29 ; B5fr prop 3 ; B5es K14 (part MPPT) | HORS D4 → D3 |
| B1 C14, C22, C24, C25, C26 ; B5es prop 26 ; B5nl cl. 14 | HORS D4 → D5 |
| B4 r1 ; B5es prop 1 ; B5en prop 1, g3 ; B5fr prop 1 ; B7 U19, g32 ; B3 N29 ; B5de P1, K02 (part « pourquoi ») | HORS D4 → D6 (liste des chiffres au § 4) |
| B2 A15, A17, A20, O26, X03 ; B5fr #25 ; B7 g39, g57 ; B5nl cl. 5, 6, 7, 17 ; B3 l.95, l.132, l.181, l.204, l.233, l.235, l.238, l.247 ; B6 K62, K63, K89 ; B5es K01 (part carte), K04, K34 ; B5en g2, g45 | PRÉSENT ET VISIBLE (rien à faire en D4) |

## 6. Écarté

| Proposition | Raison |
|---|---|
| Pas sous-horaire (B6 K27, B7 non proposé, B5nl cl. 14 part) ; séries 15 min (B5de K19 part) | décision : pas de sous-horaire (le refus `15min` d'`export_csv.py` reste) |
| Sources météo payantes (Meteonorm, Solcast, SolarGIS) | D-CALX-PAYANT |
| Rapport d'ombrage « bancable » (B2 A19) ; garantie de PR (B1 § 5) | décision « pas de bancable » ; CIQ646 parque la garantie |
| P99 (B3 l.49, B6 K30) | D-ACAL-34 = b |
| Correction spectrale (B3 l.232, B7 g33) | choix du 20/11 : aucune donnée gratuite d'eau précipitable ; reste omise avec motif |
| Bifacial vertical est-ouest (B5fr #31, B4 §2) | marché étroit ; dit dans la liste des limites (CAP-D4-09) |
| Modèle thermique transitoire, température cellule mesurée (B7 g19) | non proposé par B7 ; outil d'ingénieur |
| Éblouissement (B5en g40) | 1 voix, hors marché, aucune donnée |
| Garantie fabricant qui interdit l'ombre (B5en g42) | demanderait une table par marque non sourcée (fiche produit, hors D4) |
| Heures de fonctionnement contre heures de soleil (B3 l.234) | une voix, sans besoin d'utilisateur |
| Courbe de loi P50-P95 (B1 § 6.3, mineur) | ACAL443 suffit ; graphe sans demande d'utilisateur |
| Soleil animé côté client (B2 O36) ; image sur la photo envoyée au client (B5es prop 19, B5fr prop 18, B1 C12) | règle #4 / ACAL487 GATED ; la photo interne relève de D1/D2 |
| Choisir les graphes du rapport un par un (B6 R49, adéquation 1) | aucun utilisateur de ce marché ne le demande ; sections déjà choisies |

## 7. Contradictions entre lanes, tranchées par le code

1. **ERA5 « non branché »** (B6 K31, R1) — FAUX : `SV/pvgis_serie.py::BASES_RAYONNEMENT = ('PVGIS-SARAH3', 'PVGIS-ERA5')` l'admet ; B1 C06 avait
   raison (admis, jamais comparé). NASA POWER : absent (grep 0), B6 juste sur ce point.
2. **« export_csv : une série horaire fixe »** (B6 R21) — FAUX côté serveur (CALX313 : `colonnes`, `pas`) ; JUSTE côté utilisateur, l'écran ne
   passe jamais `colonnes` (`simulation.js::exportCsv(id, quoi)`).
3. **Neige** : « aucune étape » (B7 g54) contre « poste mensuel saisi » (B6 K33) — les deux à moitié : `neige` est dans `ORDRE_ETAPES` et toujours
   omise par `TOUJOURS_OMISES['neige']` tant qu'aucune valeur n'est saisie ; le calcul est ACAL463.
4. **Champs de fiche « à router vers le plan stock »** (B1 C03, C07, C21 ; B7 U29) — FAUX : `apps/stock/models_fiche_technique.py` appartient à
   calepinage ; seule la migration (`apps/stock/migrations/`, stock, ajout seul) est hors propriétaire.
5. **Sankey** : l'en-tête de `FE/production/DiagrammePertes.jsx` dit « Sankey/cascade » et `SV/chaine_pertes.py` parle de « deux Sankey » —
   commentaires seulement ; le composant dessine des barres et le genre d'image `sankey` est refusé (`SV/images_document.py`). B1/B6/B7 « absent » justes.
6. **Verdict d'ombrage et « retirer les modules »** « présents » (B3 N7, B2 A17) — vrai sur la page publique seulement ; dans l'ERP, non monté
   (grep `rp9-heatmap|rp9-solar-access` dans `FE/` : 0). B3 incomplet ; ACAL436 juste.
7. **Course du soleil « présente »** (B2 A20, B5fr #25, B7 g39) contre « heure légale/solaire manquante » (B4, B5es, B6) — l'atelier calcule en heure
   solaire pure sans l'écrire (`LIB/roofPro2.ts::sunDirection`), le serveur en UTC + équation du temps (`CC/soleil.py`) : les deux camps ont raison
   sur des moitiés différentes.
8. **Optimiseur « pour tout le document seulement »** (B5de K12) — partiellement faux : une ligne d'affectation peut le porter
   (`CHAMPS_SANS_CONTRAINTE`), mais elle exempte toute la chaîne et aucun écran ne la pose ; `opt_rendement_pct` n'est lu nulle part (B1 C17 juste).
9. **« Aucune plage de plausibilité »** (B3 l.229) — partiellement faux : `RENDEMENT_SPECIFIQUE_PLAUSIBLE_KWH_KWC = (600.0, 2400.0)` avertit sur le
   rendement ; aucune plage par étape (B3 juste pour les pertes). Cette borne est citée au plan (C-ACAL-079), pas à une page publiée : à
   revoir au regard de « zéro chiffre inventé ».
10. **Vieillissement « servi, non imprimé »** (B1 § 6.3) — vrai et pire : aucun écran ne le lit non plus.
11. **`SOLAR_ACCESS_LOW = 0.75`** codé en dur (« quart de l'irradiation ») — B6 R40 juste : seuil d'affichage sans source publiée, à transformer en
   réglage société (CAP-D4-04).

## 8. Non vérifié

- Aucun test, aucune simulation, aucun écran regardé : « sans écran » = 0 lecteur trouvé par grep dans `FE/` et `SV/rapport/` ; la table repliée
  du diagramme de pertes pourrait afficher des champs bruts de l'entrée d'étape (dont `heures_sous_demarrage`) — non lu.
- Retirer ou non l'énergie sous la tension de démarrage (CAP-D4-05) : `ET/mppt.py` dit « sans commander le retrait » par choix ; la raison de ce
  choix n'a pas été lue.
- NASA POWER « gratuit, sans compte » : non vérifié en ligne cette session.
- Les URL des lanes n'ont pas été rouvertes ; les valeurs du § 3 sont celles que B1 a recopiées (B1 § 8.6 dit qu'ACAL404 doit relire chaque page).
- Annexes des forums (B5de 434 lignes, B5es, B5nl, B6 par outil, B7 annexe) lues seulement par mots-clés par les deux lecteurs : un item présent
  seulement en annexe peut manquer.
- Sens exact de `borne_usuelle_dc_ac` et `seuil_bas_dc_ac` (P14, P30) : seul le libellé du registre a été lu.
- Si la règle « ajout seul » de `apps/stock/migrations/` admet une migration écrite par une lane calepinage : non vérifié dans `docs/ownership.yml`.
- Contenu exact de la journée type (`FE/production/TapisHoraire.jsx`) : seul l'en-tête a été lu.
