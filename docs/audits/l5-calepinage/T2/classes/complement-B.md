# Complément du lot B aux classes du tour 1 (pose des panneaux et électrique)

Six classes du tour 1 sont encore violées sur le lot B. Les endroits et les cases de matrice s'ajoutent aux fiches
`T1/classes/K-*.md` ; aucune classe n'est dupliquée. Statut des causes : lue / probable, comme dans le registre.

## K-GRANDEUR-UNIQUE
Endroits neufs (même invariant : une grandeur, une fonction source) :
| Endroit | Viole ? | Tâche |
|---|---|---|
| `apps/web/src/scripts/roofPro11/hydratation.ts::appliquerHydratationAuCtx` (facteur d'ombrage rejoué avant PVGIS) | oui, probable (POSE-a-001, -008, -010) | ACAL1501 |
| `apps/web/src/scripts/roofPro11/layoutEditor.ts::renderLayoutPanel` (3,60 kWc contre 3,55 kWc de la pastille) | oui, probable (POSE-a-014) | ACAL1520 |
| `backend/django_core/apps/calepinage/services/electrique.py::_bloc_ratio_dc_ac` + `pret_a_envoyer.py::_ratio_dc_ac` (trois jugements du même ratio) | oui (ELEC-a-005) | ACAL1538 |
| `services/parcours_guide.py::regrouper_manque` + `pret_a_envoyer.py::_verdict_electrique` (rail 4, pastille 3, dossier 10) | oui (ELEC-a-006) | ACAL1539 |
| `views/raccordement.py::raccordement` (phases de Saisies électriques non lues) | oui (ELEC-b-003) | ACAL1512 |
| `plan/AffectationChaines.jsx` (résumé lu sur `verdict`, pas sur `etat`) | oui (ACAL935) | ACAL1535 |
Matrice : ligne « production annuelle » × condition « rouvrir un dossier avec obstacle haut » : casse (POSE-a-008) ; ligne
« verdict électrique » × condition « plan CSV valide importé » : casse (ACAL935) ; ligne « phases » × « écran Raccordement » :
casse (ELEC-b-003).

## K-RETOUR-FAUX
| Endroit | Viole ? | Tâche |
|---|---|---|
| `core/electrique/chaines.py::_verdicts_courant` (conseil « répartir » avec une seule chaîne) | oui (ELEC-a-004) | ACAL1537 |
| `plan/AffectationChaines.jsx::BarreRaccordement` (200 sans chaîne, aucun mot) | oui (ELEC-a-007) | ACAL1536 |
| `views/schema.py` / `EtapeSchema.jsx::Telechargements` (le PDF « du schéma » est le plan de câblage) | oui (ELEC-a-001) | ACAL1507, ACAL1508 |
| `services/chaines.py::verdict_affectation` (ligne du fichier absente, renvoi à l'onglet où l'on est) | oui (ELEC-a-011) | ACAL1542 |
| `plan/AffectationChaines.jsx` « Les équiper » (verdict bloquant créé par le clic) | oui (ELEC-b-002) | ACAL1509 |
| `SaisiesElectriques.helpers.js::propositionTemperatures` ; `DossiersReglementaires.jsx` (ligne « Vérifié le ») | oui (ELEC-b-005, -004) | ACAL1549, ACAL1548 |
| `EtapePanneaux.jsx::CombienDePanneaux` (recommandation irréalisable) ; `optimizer.ts::syncNeedControl` (note périmée) | oui (POSE-b-005, -003) | ACAL1502, ACAL1526 |

## K-SAISIE-PERDUE
| Endroit | Viole ? | Tâche |
|---|---|---|
| `roof-tool-pro11.ts::applyDevisHydration` (pose de 60 rouverte à 5, enregistrement qui écrit 5) | oui, S1, probable (POSE-a-009) | ACAL1552 (GATED D-ACAL-75) |
| `electrique/ParcoursDuPan.jsx::ParcoursDuPan` (point de collecte non relu) | oui (ELEC-b-001) | ACAL1547 |
Matrice : ligne « pose » × condition « rechargement » : casse (POSE-a-009) ; ligne « point de collecte » × « rechargement » :
casse (ELEC-b-001).

## K-IMPASSE
| Endroit | Viole ? | Tâche |
|---|---|---|
| `services/pret_a_envoyer.py::_elec` (« Régler » vers un écran où rien ne se saisit) | oui (ELEC-a-002) | ACAL1506 |
| `electrique/DecisionsElectriques.jsx` (question « arrêt rapide » sans champ) | oui (ELEC-b-006) | ACAL1550 |
| « Proposer le tracé » (extrémité sans position : aucune position d'onduleur enregistrée, D-ACAL-70) | oui, non tâché | voir lot-B.md |

## K-JARGON
`services/electrique.py` (clé `core.electrique.onduleurs`, avertissement de norme ×3 : ELEC-a-008, ACAL1540),
`plan/ImportAffectation.jsx` (« Choose File », ELEC-a-009, ACAL1541) ; S4 optionnels : accords « 1 chaînes », « 1 modules »,
message « provenance » du champ Dispositif (ELEC-a-013, ELEC-b-007).

## K-ACTION-ENFOUIE
`layoutEditor.ts::setLayoutMode` : châssis, coupures et pieds montés dans `#rp9-layout-panel`, visibles seulement après
« Déplacer les panneaux » (POSE-a-013, ACAL1522) ; endroit voisin à greper : les autres champs montés dans ce panneau.

## K-STYLE
Le jeton de l'état désactivé (`frontend/src/styles/roofbuilder.css`, ACAL574 : le bouton refusé a l'aspect du bouton actif,
ACAL1524) ; la largeur des blocs est une classe À PART : `K-COLONNE-ETROITE`.
