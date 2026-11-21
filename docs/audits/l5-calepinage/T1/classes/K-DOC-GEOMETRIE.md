# Fiche d'invariant — classe `K-DOC-GEOMETRIE` (un document se dessine de la géométrie de l'écran)

- **Invariant** : « Planche A3, DXF, plan de câblage, nomenclature de pose et devis lisent la MÊME géométrie que l'atelier
  (orientation portrait/paysage, azimut, surfaces retenues, unités et conventions d'angle) ; l'échelle imprimée est
  l'échelle dessinée ; une surface n'est comptée qu'une fois. »
- **Née de** : T1-F1-020, T1-F1-031, T1-F1-021, T1-F1-030 (P0), T1-F1-028 ; rejeu : REJEU-NEW-1 (« 180 = sud » lu 270°).
  Classe 3 du rejeu.
- **Où il peut être violé** — greps sur `da49cb55b` :
  - `git grep -n -E "module_m\[0\]|module_m_pan\[0\]" da49cb55b -- backend/django_core/apps/calepinage/services` → 3 :
    `planche.py::_dessin_des_modules`, `export_dxf.py::_document_dxf/_rectangle`, `documents/plan_cablage.py::_coins` ;
  - `git grep -n -E "180 = sud" da49cb55b -- frontend/src apps/web/src` → `ModeTerrain.jsx` (rowAzimuthDeg), `Ombriere.jsx`
    (flowAzimuthDeg) ; serveur : `apps/ventes/domain/geometrie.py::pans_du_document` (FACE = rowAzimuthDeg + 90) ;
  - `apps/ventes/domain/geometrie.py::pans_du_document` additionne pans + `poseSurfaces` (lu par le rejeu et DG).
  | Endroit | Viole ? | Garde ? |
  |---|---|---|
  | `services/planche.py::_dessin_des_modules` (long côté en X) | oui (F1-020) | non |
  | `services/planche.py::_echelle_nommee` (arrondi au rang supérieur, non redessiné) | oui (F1-020) | non |
  | `services/planche.py::_etendue` (cotes = toit + obstacles hors pan) | oui (F1-021) | non |
  | `services/export_dxf.py::_rectangle` + contour TOITURE en double | oui (F1-031) | non |
  | `services/documents/plan_cablage.py::_coins` | probable (jumeau, non rejoué) | non |
  | `services/fixation.py`, `services/export_tableur.py` (lisent `geometrie_de_planche`) | à vérifier | non |
  | `apps/ventes/domain/geometrie.py::pans_du_document` — somme zone + champ au sol sans question | oui (F1-030, /proposal 218 panneaux) | non |
  | `pans_du_document` — rowAzimuthDeg + 90 vs libellé « 180 = sud » | oui (REJEU-NEW-1) | non |
  | `Ombriere.jsx` flowAzimuthDeg « 180 = sud » | à vérifier (jumeau) | non |
  | `roofPro11/poseSurfaces.ts::saisirSurface` (3 modèles d'un champ au sol) | oui (F1-028) | non |
- **Matrice** :
  | Document | portrait | paysage | pan azimut ≠ 180 | obstacle hors pan | toit + champ au sol | rangées 180 saisies |
  |---|---|---|---|---|---|---|
  | planche A3 | casse (F1-020) | ? | ? | casse (F1-021) | ? | ? |
  | DXF | casse (F1-031) | ? | ? | ? | ? | ? |
  | plan de câblage | probable casse | ? | ? | ? | ? | ? |
  | devis / /proposal | n/a | n/a | ? | ? | casse (F1-030) | casse (NEW-1) |
- **Garde** : UNE fonction d'emprise orientée partagée (planche, DXF, câblage) + un test dans le module de test existant des
  sorties (`apps/calepinage/tests/test_cal175_sorties.py`) qui, pour un golden portrait et un paysage, mesure dans le PDF et le
  DXF : aucun recouvrement de modules, échelle mesurée = échelle imprimée, une surface comptée une fois. Rouge attendu sur
  `da49cb55b` (mesures du rejeu `T1/rejeu/mesure_docs.py`) — non exécuté.
- **Cible du tour suivant** : oui.
- **Propriétaire** : calepinage (tous les fichiers listés, `geometrie.py` compris).
- **Ce qu'elle ne couvre pas** : les blocs nommés par chaîne du DXF (CAP-D2-19 / CAP-D3-20).
- **Question de sortie** : non → D7-09, D7-10, D7-11.
