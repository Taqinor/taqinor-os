"""ARC28 — Manifeste plateforme du module « Veille appels d'offres » (VAO13).

Déclare ce que cette app expose aux 7 surfaces transverses.
``core.platform.collect_platform_manifests`` le collecte GÉNÉRIQUEMENT (aucun
import de ``core`` vers l'app) ; un module désactivé pour une société
disparaît alors de TOUTES les surfaces d'un coup.

RÈGLE D'HONNÊTETÉ (ARC41), appliquée à la lettre
------------------------------------------------
``core/platform_coverage.py`` fait rougir la CI sur toute surface DÉCLARÉE et
non câblée. Ce manifeste ne déclare donc **que** ce dont le câblage existe
réellement dans le dépôt aujourd'hui :

* ``record_targets`` — ``veille_ao.avismarche``. Le chatter d'un avis passe
  par ``records.Activity`` (ARC8), **jamais par une classe ``*Activity``
  maison** : les 13 chatters hand-rollés sont le premier poste de dette
  mesuré du dépôt. ``records.ALLOWED_TARGETS`` est l'union PARESSEUSE des
  ``record_targets`` de tous les manifestes (ARC30) — déclarer la clé ici
  SUFFIT à ouvrir le chatter, il n'y a rien à modifier dans ``apps/records``.
  C'est ce qui rend opérationnel le journal de transitions de VAO14.

* ``searchable_models`` — ``veille_ao.avismarche``. Les deux surfaces
  avancent ENSEMBLE ou pas du tout : déclarer le chatter SANS la recherche
  crée mécaniquement une dérive ``chatter_sans_recherche`` NOUVELLE (hors
  baseline), donc rouge — et l'inverse aussi. La recherche globale n'étant
  pilotée par le registre QU'À MOITIÉ (``apps/reporting/search.py`` n'itère
  que les clés présentes À LA FOIS dans ``searchable_models`` et dans son
  registre local ``_SEARCH_SPECS``), la spec correspondante est câblée dans
  le même lot : sans elle, cette ligne serait une surface VIDE, c'est-à-dire
  exactement le « mensonge » qu'ARC41 existe pour attraper.

Et **ce qui n'est PAS déclaré, avec sa raison** (une surface vide qui porte
sa raison n'est pas un oubli) :

* ``import_specs`` — ``avis_veille``, CÂBLÉE par VAO28
  (``apps/veille_ao/imports.py`` : lecture par
  ``apps.dataimport.parsing.iter_rows``, carte d'en-têtes locale
  ``FIELD_MAPS_VEILLE``, validations et rejets propres). Cible « à lecteur
  propre » — comme ``obstacles``/``chaines``/``avis`` côté ``apps.ao`` : elle
  apparaît dans ``dataimport.TARGETS`` (l'union paresseuse du registre) mais
  PAS dans ``dataimport.FIELD_MAPS``, puisque son écriture passe par les
  modèles de la veille et non par l'import générique. La clé est déclarée ici
  dans le commit MÊME qui la câble, jamais avant (règle d'honnêteté ARC41).
  Elle alimente le SAS, jamais des affaires : la création d'``AppelOffre``
  depuis un fichier est l'autre chemin (AOF169) et les deux ne fusionnent
  pas.
* ``customfield_models`` reste VIDE. La lecture/écriture des valeurs passe
  par un champ ``custom_data`` (``JSONField``) porté PAR LE MODÈLE CIBLE ;
  aucun modèle de cette app n'en a. Déclarer la surface donnerait un écran
  de champs personnalisés qui accepte la saisie et la jette en silence —
  pire qu'une surface vide.
* ``agent_actions_module`` reste VIDE : aucun module ``agent_actions`` ici.
* ``automation_state_fields`` reste VIDE. Le statut d'un avis est piloté par
  le service unique de transition (VAO14) ; l'ouvrir aux automatisations
  temporelles contournerait ce point de passage.
* ``kpi_providers`` reste VIDE : aucun fournisseur de KPI dans cette app.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'veille_ao',

    # Cherchable ET chatter-isé — les deux ensemble, jamais l'un sans l'autre.
    'searchable_models': ['veille_ao.avismarche'],
    'record_targets': ['veille_ao.avismarche'],

    # VAO28 — import de fichier d'avis DANS LE SAS (cible à lecteur propre).
    'import_specs': ['avis_veille'],

    # Surfaces non câblées : vides, avec leur raison dans le docstring.
    'customfield_models': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
