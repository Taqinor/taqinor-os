# backend/parked/core_calepinage/ — rendu matplotlib AO, rives et étude (ACAL328)

## Ce que c'est

Les modules du noyau `core/calepinage/` qui n'avaient **aucun importeur de
production** (seuls leurs tests les importaient), parqués par ACAL328
(C-ACAL-141, décision D-ACAL-16 : **parquer, jamais supprimer**) :

| Ici | Venait de | Rôle |
|---|---|---|
| `rendu/` (arc, bandeau, cartouche, couleurs, feuille, metadata, notes, planche, profils) | `backend/django_core/core/calepinage/rendu/` | planches A3 matplotlib de la réponse à appel d'offres |
| `rives.py` | `core/calepinage/rives.py` | les 4 rives nommées (bornes latérales / d'extrémité) |
| `etude.py` | `core/calepinage/etude.py` | étude économique AO (optimum + marges + sensibilité batterie) |
| `tests/` | `core/tests/test_calepinage_{bandeau,cartouche,couleurs,etude,notes,planche,profils,rendu_arc,rendu_feuille}.py` + la classe `QuatreRivesTesteesSeparement` de `test_calepinage_zones.py` (→ `tests/test_calepinage_rives.py`) | leurs tests, contenu inchangé |

Déplacement par `git mv` (contenu inchangé, historique conservé :
`git log --follow`). La planche SERVIE au client n'a jamais été celle-ci :
c'est `apps/calepinage/services/planche.py` (SVG → `render_pdf`), inchangée.

Ce qui **reste** dans `core/calepinage/` : `echelle.py`, `sensibilites.py` et
`tiroirs.py` (importés par `backend/parked/ao/calepinage_service.py`).

Hors PYTHONPATH, hors image Docker, hors flake8 (`--exclude=parked`), hors
tests CI — comme le reste de `backend/parked/`.

## Recette de retour

1. Remettre le code :
   ```
   cp -r backend/parked/core_calepinage/rendu backend/django_core/core/calepinage/
   cp backend/parked/core_calepinage/rives.py backend/parked/core_calepinage/etude.py backend/django_core/core/calepinage/
   cp backend/parked/core_calepinage/tests/test_calepinage_*.py backend/django_core/core/tests/
   ```
   (la classe de `test_calepinage_rives.py` peut aussi rejoindre
   `core/tests/test_calepinage_zones.py`, d'où elle vient).
2. Remettre l'exemption matplotlib du noyau pur dans
   `backend/django_core/core/tests/test_calepinage_purete.py` :
   `SOUS_PAQUET_RENDU = "rendu"`, `DEPENDANCES_RENDU = frozenset({"matplotlib"})`
   et le saut `dans_rendu and racine in DEPENDANCES_RENDU` dans
   `test_aucun_import_hors_liste_blanche` (le contrat import-linter
   `calepinage-est-un-noyau-pur` de `backend/django_core/.importlinter` ne
   nomme pas matplotlib : rien à y remettre).
3. Donner un importeur de PRODUCTION aux modules revenus — ou les inscrire
   avec leur raison dans l'`ALLOWLISTE` de
   `core/tests/test_acal_core_calepinage_orphelins.py`, sinon ce test rougit.
4. Re-lancer les 10 fichiers de tests revenus, `lint-imports`, `flake8`,
   `compileall`, puis la CI.
