# Fiche d'invariant — classe `K-TEXTE-HORS-FEUILLE` (un texte long d'un document dessiné se replie dans sa feuille)

- **Invariant** : « Dans un document du calepinage rendu en SVG ou en PDF (planche, plan de pose, plan de câblage, schéma
  unifilaire, feuille de pan), aucune ligne de texte — titre, bandeau, consigne de société, source d'une quantité, repère —
  ne dépasse le bord de sa feuille ni de son cadre : un texte plus long que la largeur disponible passe à la ligne
  (`textwrap`) ou est mesuré avant d'être posé ; chaque repère imprimé fait 9 pt au moins. »
- **Née de** (tour 2, lot D) : T2-F2-DOCS-a-003 (titre du cartouche « … Villa Essaou »), reprise d'ACAL889 (consigne de
  société « …sous tension dès c »), reprise d'ACAL580 (source des pieds et repères P1…P12 en 7 pt), reprise d'ACAL686 et
  T2-F2-DOCS-b-001 (bandeau du schéma « Côté alternatif non de »). Voisine, pas identique, de K-COLONNE-ETROITE (lot B : une
  grille d'écran) et de K-DOC-GEOMETRIE (tour 1 : la géométrie dessinée) : ici c'est le TEXTE des PDF.
- **Où il peut être violé** — greps lancés sur la tête de cette session (`77c8c0128`) :
  - `git grep -n -E "<text x=" -- backend/django_core/apps/calepinage/services/planche.py backend/django_core/apps/calepinage/services/planche_pan.py backend/django_core/apps/calepinage/services/documents/plan_cablage.py backend/django_core/core/electrique/schema.py`
    (les `<text>` écrits d'un seul tenant) ; `git grep -n "textwrap" -- <mêmes fichiers>` (ceux qui replient).
  | Endroit | Viole aujourd'hui ? | Couvert par la garde ? |
  |---|---|---|
  | `backend/django_core/apps/calepinage/services/planche.py::_bandeau_svg` (titre 5 pt, sous-titre, lignes du bandeau : consigne, onduleurs, pieds) | oui (DOCS-a-003, ACAL889, ACAL580) | non — ACAL1717 |
  | `backend/django_core/core/electrique/schema.py::_bandeau_svg` (bandeau d'omission) | oui (ACAL686, DOCS-b-001) | non — ACAL1713 |
  | `backend/django_core/core/electrique/schema.py::_cartouche` (Client, référence : valeurs longues) | probable | non — ACAL1713 |
  | `backend/django_core/apps/calepinage/services/planche_pan.py::_pied_a4` (pied de feuille de pan, lignes brutes) | probable | non |
  | `backend/django_core/apps/calepinage/services/planche_pan.py::_reperes_de_chantier` (repères de poteau 7 pt à cheval sur le contour) | oui (ACAL580) | non — ACAL1718 |
  | `backend/django_core/apps/calepinage/services/planche.py::_legende_svg` (repli à `CARACTERES_PAR_LIGNE_LEGENDE`) | non | oui (modèle à suivre) |
  | `backend/django_core/apps/calepinage/services/documents/plan_cablage.py::_lignes_de_legende` (consigne repliée à 44) | non | oui (modèle à suivre) |
  | les rapports HTML (`services/rapport/*.py`) | non (le HTML se replie seul) | n/a |
- **Matrice champ × condition** :
  | Texte | nom de projet de 28 caractères | consigne de société de 150 caractères | phrase servie de 240 caractères | A4 (feuille de pan) | A3 (planche) |
  |---|---|---|---|---|---|
  | titre du cartouche | casse (DOCS-a-003) | n/a | n/a | ? | casse |
  | consigne DC | n/a | casse (ACAL889, plan de pose) ; tient (plan de câblage) | n/a | ? | casse |
  | bandeau d'omission du schéma | n/a | n/a | casse (ACAL686) | n/a | casse |
  | source des pieds | n/a | n/a | casse (ACAL580) | casse | casse |
  | repère de poteau | n/a | n/a | n/a | casse (7 pt) | n/a |
- **Garde** (UNE par classe, famille existante) : un test de rendu qui mesure, dans le SVG produit, l'extrémité de chaque
  `<text>` (x + largeur estimée) contre la largeur de la feuille, dans `backend/django_core/apps/calepinage/tests/test_cal211_plan_pose.py`
  (module existant du plan de pose) étendu d'une assertion par ligne du tableau ci-dessus ; écrite par le rédacteur des tests
  premiers, pas par la lane qui corrige. Rouge attendu : retirer le repli de `_bandeau_svg`.
- **Cible du tour suivant** : oui — donnée aux relecteurs de documents : mesurer au PDF (PyMuPDF) le x1 de chaque ligne.
- **Propriétaire** : calepinage (`backend/django_core/apps/calepinage/services/`, `backend/django_core/core/electrique/`).
- **Ce qu'elle ne couvre pas** : la géométrie dessinée (K-DOC-GEOMETRIE), les grilles d'écran (K-COLONNE-ETROITE).
- **Question de sortie** : « le système l'attraperait-il tout seul la prochaine fois ? » — oui, par l'assertion de mesure
  ajoutée au test du plan de pose une fois ACAL1717 construite.
