# Production annuelle d'une pose : un chiffre ou plusieurs ? (lot 10, couloir production-un-chiffre)

Règle du fondateur : « un moteur, un chiffre par valeur, le plus réaliste ». Constat : non, la même pose
peut aujourd'hui afficher deux, voire trois productions annuelles. Tout ci-dessous est lu dans le code
(branche `dev-lot10`) ; aucun chiffre n'a été calculé sur une base de données.

Niveau de règles courant du code : `REGLES_COURANTES = REGLES_SENSIBILITES_1911 = 14`
(`apps/ventes/domain/regles_calcul.py`). Le niveau 15 (`REGLES_POSE_REELLE_2111`, la pose réelle) est
déclaré mais PAS courant : tant qu'il ne l'est pas, `conception/moteur.py::pose_reelle` rend `None` et
`horaire/productible_pose.py::diagnostic_base_de_production` rend « règles d'avant le 21/11 ».

## 1. Où la production annuelle est CALCULÉE

| # | Calcul | Panneaux comptés | Rendement / ombrage | Rangé où |
|---|---|---|---|---|
| C1 | Simulation du calepinage — `apps/calepinage/services/simulation.py` (l. 729-737 `plans_raccordes`, l. 822 kWc, l. 1319 `hors_chaine`) | RACCORDÉS seulement dès qu'une table d'affectation existe (`agregation_electrique.py::plans_raccordes` retire les modules à `chaine` vide) ; sans table (avant l'étape électrique) : TOUS les posés | Simulation horaire PVGIS + ombrage + pertes du serveur | Résultat rangé du calepinage (`production.total.p50_kwh`, `production.hors_chaine.modules`) |
| C2 | Moteur unique de conception — `apps/ventes/conception/valeurs.py::valeurs/_bilan` → `domain/chiffrage_conception.py::_depuis_conception` | Niveau 14 : la taille que le moteur dimensionne lui-même (la pose n'impose rien). Niveau 15 : `calepinage/services/pose_pour_moteur.py::pose_servie` impose `nb = mesures_du_document(layout)['modules']` = TOUS les posés, raccordés ou non | Niveau 14 : rendement de la ville (`standard_ville`). Niveau 15 : kWh/kWc de C1 (`selectors_devis.py::contrat_depuis_servi`, `kwh_kwc_annuel = p50 / kWc raccordé`) × kWc de TOUS les posés ; si kWc raccordé et kWc du document s'écartent de plus de 2 % (`TOLERANCES['kwc_calepinage_ratio']`) : simulation dite périmée → rendement de la ville | Conception rangée du lead → bloc `chiffrage.production_annuelle_kwh` servi |
| C3 | Devis / PDF — `apps/ventes/horaire/productible_pose.py::base_de_production` puis l'étude horaire du devis | kWc des LIGNES du devis (tous les panneaux vendus) | Niveau 14 : ville. Niveau 15 brouillon : rendement de C1 si kWc du devis à ±2 % du kWc simulé RACCORDÉ, sinon ville. Devis envoyé : base gelée (`_base_rangee`) | `etude_params.etude_horaire` du devis |
| C4 | Carte de la pose (outil de toit) — `apps/web/src/scripts/roofPro11/optimizer.ts::renderConfig` (l. 707) et gagnants (l. 871, 1366, 1445) | Panneaux posés du pan actif | `/api/roof-yield` (PVGIS) × kWc, × `facteurDerateAnnuel(ctx)` (ombrage tracé × horizon) | Aucun (affichage) |
| C5 | Fenêtre « Production estimée » (site public) — `roofPro11/prodWindow.ts::renderProdWindow` | `ctx.prodPanels` | `/api/roof-production` × kWc (`rescaleByPanels`), SANS `facteurDerateAnnuel` (aucune lecture de `shadeFactors` ni `horizonFactors` dans le module, contrairement à l'en-tête de `shadingUi.ts`) | Aucun (affichage) |

## 2. Où elle est AFFICHÉE ou IMPRIMÉE

| Écran / document | Chiffre lu |
|---|---|
| Atelier ERP, carte de la pose `#rp9-reco-prod` et pastille « Production · conception » (`EtapePanneaux.jsx::PuceResume`, via `constructeur.js::lireFigures`) | C2, seulement si son kWc égale la pose (`affichageErp.ts::productionServie`), sinon la raison |
| Atelier ERP, onglet « Production » (`frontend/src/features/calepinage/production/PanneauProduction.jsx`) | C1 (`total.p50_kwh`, raccordés) |
| Atelier ERP, étape Résultats (`EtapeResultats.jsx` l. 93, 190, 200) | C2, et la production rangée du devis envoyé |
| Fiche lead, carte Conception (`frontend/src/features/crm/workspace/CarteConception.jsx` l. 36) | C2 |
| Générateur de devis (`ApercuSimulation.jsx` l. 448-464, `DevisOffresTailles.jsx` l. 240) | C2 / C3 |
| PDF du devis (D-ACAL-36 / 44) | C3 (le moteur `quote_engine/` rend, il ne recalcule pas) |
| Rapport du calepinage (`calepinage/services/rapport/production.py`) | C1, avec l'écart au devis (`_meme_chiffre`) |
| Site public : carte de la pose / fenêtre de production | C4 / C5 |

## 3. Ce qui peut différer pour la même pose

- **C1 contre C2/C3 (ERP)** : deux causes qui s'additionnent. (a) Niveau 14 : rendement de la ville contre
  simulation ombrée. (b) Pose partiellement câblée : C1 ne compte que les raccordés, C2 (niveau 15) et C3
  comptent tous les panneaux posés/vendus. Exemple symbolique : 20 panneaux posés, 14 raccordés, même
  rendement Y et même puissance P → onglet Production = Y × 14 × P, carte = Y × 20 × P, rapport 20/14 = 1,43.
  Valeurs en kWh : **non calculées** (il faut la base).
- **C4 contre C5 (site public)** : même pose, la carte est réduite par l'ombrage et l'horizon, la fenêtre
  ne l'est pas ; en plus, les deux lisent deux routes (`/api/roof-yield` et `/api/roof-production`).

## 4. Panneaux non raccordés : quand, et ce que le PDF imprime

- **Avant l'étape électrique** : aucune table d'affectation, `plans_raccordes` rend les plans tels quels :
  tous les panneaux comptent partout (pas de non raccordés au sens du serveur).
- **Après un câblage partiel** : les modules à `chaine` vide sortent de C1 (`hors_chaine.modules`, phrase
  `phrase_non_raccordes` « ne sont pas comptés dans la production ») ; l'atelier le dit (ACAL1914,
  `sources.js::simulationIncomplete`).
- **PDF** : niveau 14, rendement de la ville × kWc des lignes, le câblage n'y change rien. Niveau 15
  brouillon : si l'écart de kWc dépasse 2 %, ville × kWc des lignes (tous les panneaux) ; sous 2 %, rendement
  raccordé × kWc de tous les panneaux. Le PDF ne dit jamais que des panneaux ne sont pas raccordés.

## 5. Ce que ce couloir corrige, et ce qu'il ne corrige pas

- **Corrigé (affichage seul, aucun chiffre rangé ni imprimé)** : la fenêtre C5 applique le même
  `facteurDerateAnnuel(ctx)` que la carte C4.
- **Non corrigé (change C2/C3, donc le devis et le PDF)** : compter les seuls raccordés dans la conception.
  Plus petit changement correct : dans `pose_pour_moteur.py::pose_servie`, servir aussi le kWc RACCORDÉ
  (déjà connu de C1 : `hors_chaine.modules`), et faire porter la production de C2 sur ce kWc tant que des
  panneaux sont hors chaîne — ou ne pas servir de production (`etat` non servi, motif « n panneaux non
  raccordés ») plutôt qu'un chiffre qui les compte. Le nombre de panneaux VENDUS ne change pas. À poser
  derrière un niveau de règles neuf (16 est pris par les hybrides HT : 17) ou une coupure « nouveaux rendus
  seulement » (`regles_calcul.py::_ouvert_aux_nouveaux_rendus`, comme `COUPURE_SCHEMA_ELECTRIQUE`), et
  seulement après le passage du niveau 15 en courant. Décision du fondateur requise (laquelle des deux
  options).
- **Non corrigé** : l'écart de rendement C4/C5 (deux routes PVGIS) et l'écart ville/simulation du niveau 14
  (c'est l'objet du niveau 15).
