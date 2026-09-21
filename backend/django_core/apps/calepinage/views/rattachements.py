"""CALX2 — une ligne par action rattachée, ajoutée EN FIN, jamais réordonnée.

Ce module ne contient AUCUNE logique : il ne fait qu'IMPORTER, dans l'ordre
historique, les sous-modules de ``apps/calepinage/views/`` qui posent une
``@action`` sur le ``CalepinageViewSet`` par affectation d'attribut de classe.
Importer le sous-module SUFFIT à rattacher son action : c'est l'exécution du
module qui fait ``CalepinageViewSet.<action> = <fonction>``.

POURQUOI CE FICHIER EXISTE (décision D-CALX 13, 21/09/2026)
------------------------------------------------------------
Avant CALX2, ces imports vivaient dans ``urls.py``. Conséquence mesurée sur le
groupe CALX : chaque tâche qui ajoutait une action devait déclarer ``urls.py``
dans son ``Files:``, donc ``scripts/plan_lanes.py`` unionnait toutes ces tâches
dans UNE seule lane (337 tâches sur 353) — et la clé de pairage PACT11 faisait
refuser les moitiés frontend. ``urls.py`` n'est désormais rouvert QUE par
CALX2 ; tout le reste passe par ce fichier, déclaré APPEND-ONLY dans
``scripts/plan_lanes.py`` (``_APPEND_ONLY_SUFFIXES``), donc deux tâches qui
l'écrivent ne fondent plus leurs lanes.

LA RÈGLE, ET ELLE EST STRICTE
------------------------------
* UNE ligne d'import par action rattachée, précédée de son commentaire
  ``# CALX<id> — …`` ;
* elle s'ajoute **EN FIN** de la liste ci-dessous, jamais au milieu ;
* l'ordre existant n'est **JAMAIS** réordonné (deux tâches qui trient ce
  fichier chacune à leur façon, c'est le conflit de fusion garanti que la
  règle append-only évite) ;
* aucune autre instruction n'entre ici : pas de ``path()``, pas de
  ``router.register``, pas de vue — ils restent dans ``urls.py`` et dans les
  sous-modules.

``urls.py`` importe ce SEUL module, **AVANT** ``router.register(...)`` : DRF
inspecte les attributs de la classe au moment de l'enregistrement
(``get_extra_actions()``), donc une action rattachée après coup ne serait
jamais routée.

Aucun couplage ``apps.ao`` / ``apps.ged`` n'entre ici (décision D-CALX 2).
"""
from __future__ import annotations

# CAL243 — rattache l'action ``equipements`` au ``CalepinageViewSet`` par
# import (affectation d'attribut de classe, voir la docstring du module) ;
# doit s'exécuter AVANT ``router.register`` pour que le routeur la découvre.
from . import equipements as _equipements_action  # noqa: F401
# CAL92/93 — même patron : rattache l'action ``horizon`` (profil d'horizon
# PVGIS ``printhorizon``, contrat CAL92).
from . import horizon as _horizon_action  # noqa: F401
# CAL144 — même forme pour l'export CSV (``calepinages/<pk>/export-csv/``) :
# code dans un fichier neuf, enregistrement en une ligne additive.
from . import export_csv as _export_csv_action  # noqa: F401
# CAL246 — même patron : rattache l'action ``modeles`` (bibliothèque).
from . import bibliotheque as _bibliotheque_action  # noqa: F401
# CAL207 — même patron : rattache l'action ``deverrouiller``.
from . import verrou as _verrou_action  # noqa: F401
# CAL208 — même patron : rattache ``archiver``/``restaurer-corbeille``.
from . import archivage as _archivage_action  # noqa: F401
# CAL216 — même patron : rattache ``export-layout``/``import-layout``.
from . import io_layout as _io_layout_action  # noqa: F401
# CAL159 — même discipline pour l'action ``pompage`` (dimensionnement du
# pompage solaire, services CAL155-CAL158) : code dans son propre fichier,
# rattachement par cet import, AVANT ``router.register``.
from . import pompage as _pompage_action  # noqa: F401
# CAL139 — même patron : rattache ``pertes``/``enregistrer-pertes``.
from . import simulation as _simulation_actions  # noqa: F401
# CAL191 — même patron : rattache ``dossiers-reglementaires`` (contrat CAL247).
from . import reglementaire as _reglementaire_action  # noqa: F401
# CALX39 — même patron : rattache ``importer-plan`` (analyse d'un plan DXF /
# PDF vectoriel déposé, service CAL62). Aucune écriture : la porte rend le
# contour, elle ne pose aucun ``roof_layout``.
from . import import_plan as _import_plan_action  # noqa: F401
# ↑ AJOUTER LA LIGNE SUIVANTE ICI, EN FIN — jamais au milieu, jamais de tri.

#: Les sous-modules de vues rattachés ci-dessus, dans leur ordre d'import.
#: Documentaire et TESTABLE (``tests/test_calx2_rattachements.py`` compare
#: cette liste aux actions réellement découvertes par le routeur) : une ligne
#: d'import ajoutée sans sa ligne ici — ou l'inverse — rougit.
MODULES_RATTACHES = (
    'equipements',
    'horizon',
    'export_csv',
    'bibliotheque',
    'verrou',
    'archivage',
    'io_layout',
    'pompage',
    'simulation',
    'reglementaire',
    'import_plan',  # CALX39
)

__all__ = ['MODULES_RATTACHES']
