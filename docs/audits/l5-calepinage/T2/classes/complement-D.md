# Complément du lot D aux classes du tour 1 (documents, parcours, liste)

Sept classes du tour 1 sont encore violées sur le lot D. Les endroits et les cases de matrice s'ajoutent aux fiches
`T1/classes/K-*.md` ; aucune classe n'est dupliquée. La classe neuve du lot est `K-TEXTE-HORS-FEUILLE`
(`T2/classes/K-TEXTE-HORS-FEUILLE.md`). Statut des causes : lue / probable, comme dans le registre.

## K-IMPASSE
| Endroit | Viole ? | Tâche |
|---|---|---|
| `backend/django_core/apps/calepinage/services/pret_a_envoyer.py` (`CIBLE_MATERIEL`, `CIBLE_OBSTACLES`, `CIBLE_PERTES` : clés absentes de `onglets.js`) | oui (DOCS-a-001, PARCOURS-012) | ACAL1703 |
| `services/pret_a_envoyer.py` (contrôle `materiel_designe` : « non désigné » pour une fiche incomplète) | oui (PARCOURS-011, -016) | ACAL1704 |
| `frontend/src/features/calepinage/BoutonDevis.jsx` (carte « Devis créé » invisible, « Devis lié » sans lien) | oui, probable (PARCOURS-015) | ACAL1705 |
| `frontend/src/features/calepinage/production/ResultatIncomplet.jsx::DemarrageRapideBloc` (mauvaise page, mauvais compte) | oui (PARCOURS-009) | ACAL1708 |
| `apps/web/src/scripts/roofPro11/zones.ts::motifAlleeSansLargeur` et `HeureLegale.jsx` (« Réglages › Site » sans ancre) | oui (PARCOURS-018) | ACAL1737 |
Matrice : ligne « bouton Régler » × condition « onglet cible absent du registre » : casse (trois cibles) ; garde : toute
`cible.onglet` servie par `pret-a-envoyer/` est une clé de `onglets.js` (test dans `tests/test_pret_a_envoyer.py`, ACAL1703).

## K-GRANDEUR-UNIQUE
| Endroit | Viole ? | Tâche |
|---|---|---|
| `services/rapport/synthese.py::html_de_section` (productible sans la réserve du P50) | oui (DOCS-a-005) | ACAL1701 |
| dossier client : proposition, rapport, atelier, Résultats (quatre chiffres) | oui (DOCS-a-008) | ACAL1755 (GATED D-ACAL-85) |
| `services/documents/__init__.py::_etat_du_document` (carte rapport sans production) | oui, probable (DOCS-a-006) | ACAL1702 |
| `services/pret_a_envoyer.py::controle_un_seul_chiffre` (ligne grise sans geste) | oui (PARCOURS-017) | ACAL1709 |
| production du moteur de devis (14 620) contre atelier (11 611) | oui (ACAL853, F2-CONSO-003) | ACAL1611 (lot C) |
| `services/variantes_modules.py::_variante_pour_module` (production d'un autre module recopiée) | oui (ACAL594) | ACAL1710 |
Matrice : ligne « production annuelle » × conditions « rapport, devis, atelier, variante » : casse sur les quatre.

## K-ACTION-ENFOUIE
| Endroit | Viole ? | Tâche |
|---|---|---|
| `frontend/src/features/calepinage/atelier/Rail.jsx::ouvrir` (onglet ouvert en Expert hors de la vue) | oui, probable (DOCS-a-009, DOCS-b-006, ACAL600) | ACAL1714 |
| `apps/web/src/scripts/roofPro11/formesToit.ts` (forme choisie avant le toit, refusée en silence) | oui (PARCOURS-002, -003) | ACAL1706 |

## K-JARGON
| Endroit | Viole ? | Tâche |
|---|---|---|
| `services/rapport/__init__.py::_motif_html` (chemins bruts dans le PDF client) | oui (DOCS-a-007) | ACAL1716 |
| `frontend/src/features/calepinage/equipements/FichesIncompletes.jsx` (noct_c, vmp_v…) | oui (PARCOURS-025) | ACAL1740 |
| `frontend/src/features/calepinage/electrique/CheminementCables.jsx` (« electrical.cheminements — ») | oui (RATT-1-002) | ACAL1743 |
| `services/explications.py` et `data/explications.json` (« non publiée kWh », nom de champ interne) | oui, probable (PARCOURS-b-002, -004, RATT-1-004) | ACAL1741 |
| `services/rapport/hors_reseau.py::_mois` (mois en 1…12) | oui (RATT-2-002) | ACAL1744 |
| `frontend/src/features/calepinage/reglages/ReglagesSimulation.jsx` (JSON brut) | oui (PARCOURS-014) | ACAL1736 |

## K-DEFAUT-CHOIX
| Endroit | Viole ? | Tâche |
|---|---|---|
| `frontend/src/features/calepinage/atelier/parcoursGuide.js::etapeActive` (réouverture toujours sur l'étape 3) | oui (PARCOURS-005) | ACAL1731 |
| `apps/web/src/scripts/roofPro11/formesToit.ts` (la découpe repave tout le toit) | oui, probable (PARCOURS-004) | ACAL1707 |
| `frontend/src/features/calepinage/atelier/coque/BarreProjet.jsx` (titre = « Calepinage N — ville ») | oui (PARCOURS-021) | ACAL1730 |
| `services/reglementaire.py::GENRES_FRANCE` (aucun dossier marocain) | oui (PARCOURS-023) | ACAL1756 (GATED D-ACAL-86) |

## K-DOC-GEOMETRIE
| Endroit | Viole ? | Tâche |
|---|---|---|
| `apps/web/src/scripts/roofPro11/numerotation.ts::creerRegistre` (numéros 6…83 sur la feuille) | oui, probable (DOCS-a-002) | ACAL1720 |
| `services/planche_pan.py::_portee_jusqu_au_contour` (cotes de rive 0,00 quand le champ touche une rive) | oui (ACAL591) | ACAL1712 |
| `services/documents/plan_cablage.py::_fleche_de_chaine` (flèche invisible sur les modules de sa couleur) | oui (ACAL590, ACAL643) | ACAL1719 |
Matrice : ligne « cotes aux rives » × conditions « champ en retrait / champ au contact d'une rive » : tient / casse ;
ligne « numéros » × « première pose / repavage complet » : tient / casse.

## K-RETOUR-FAUX
| Endroit | Viole ? | Tâche |
|---|---|---|
| `services/export_dxf.py::exporter_dxf` (la carte promet numéro, pan, chaîne ; le DXF n'en a aucun) | oui (DOCS-a-004) | ACAL1721 |
| `frontend/src/features/calepinage/documents/cartesGuide.js` (la carte « Schéma électrique » livre le plan de câblage) | oui (DOCS-b-002) | ACAL1723 |
| `services/garde_montants.py::MOTS_D_ARGENT` (« marge » refuse tout le plan de pose) | oui (DOCS-b-004) | ACAL1711 |
| `services/chaine_pertes.py::_refuser_irradiance_horizontale` (l'option « année type » refuse toute simulation) | oui (RATT-2-006) | ACAL1715 |
