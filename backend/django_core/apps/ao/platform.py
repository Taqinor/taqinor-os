"""ARC28/ARC30 — Manifeste plateforme du module Appels d'offres
(« déclarer une fois »).

Déclare ce que AO expose aux surfaces transverses (voir ``core.platform``).
ARC30 fait basculer la source de ``records.ALLOWED_TARGETS`` d'un ``set``
littéral figé vers l'union paresseuse des manifestes ``record_targets`` — ce
manifeste porte la cible chatter/records historique (``ao.appeloffre``, ARC26
— pièces jointes génériques).

AOF165 — RÈGLE D'HONNÊTETÉ (ARC41), appliquée à la lettre
--------------------------------------------------------
``core/platform_coverage.py`` fait rougir la CI sur toute surface DÉCLARÉE et
non câblée. Ce manifeste ne déclare donc **que** ce dont le câblage existe
réellement dans le dépôt aujourd'hui :

* ``import_specs`` — câblé par ARC32 (``apps.dataimport.services.TARGETS``,
  union paresseuse) ET par les spécifications réelles d'AOF30
  (``apps.ao.imports.FIELD_MAPS_AO`` : ``obstacles`` et ``chaines``). Ces deux
  clés ne sont pas des intentions : elles ouvrent l'import d'un relevé de
  toiture saisi sur tableur, hors ligne, par un technicien sans tablette.
* ``automation_state_fields`` — le STATUT de l'appel d'offres, et lui seul.

Et **ce qui n'est PAS déclaré, avec sa raison** (une surface vide qui porte sa
raison n'est pas un oubli) :

* ``searchable_models`` reste VIDE. La recherche globale n'est pilotée par le
  registre qu'à moitié : ``apps/reporting/search.py`` n'itère que les clés
  présentes À LA FOIS dans ``platform.searchable_models`` **et** dans son
  registre local ``_SEARCH_SPECS`` (« une clé ici sans manifeste, ou un
  manifeste sans spec ici, ne produit rien »). Aucune spec AO n'y existe.
  Déclarer ``ao.appeloffre`` cherchable rendrait donc une surface VIDE tout en
  périmant l'entrée de baseline ``('ao.appeloffre', 'chatter_sans_recherche')``
  de ``core/platform_coverage.py`` — CI rouge des deux côtés, pour une
  fonctionnalité qui n'existerait pas. Le câblage manquant est dans une app
  transverse (``apps/reporting``), hors du périmètre de cette tâche.
* ``record_targets`` reste à sa seule cible historique. Ajouter un modèle ici
  SANS le rendre cherchable crée mécaniquement une dérive
  ``chatter_sans_recherche`` NOUVELLE (hors baseline) — donc rouge. Les deux
  surfaces avancent ENSEMBLE ou pas du tout : c'est exactement la cohérence
  qu'ARC41 existe pour défendre.
* ``customfield_models`` reste VIDE. Le chargeur central ARC31 enregistre bien
  la clé, mais la LECTURE/ÉCRITURE des valeurs passe par
  ``apps.customfields.serializers._module_model(...)`` puis par un champ
  ``custom_data`` (``JSONField``) porté PAR LE MODÈLE CIBLE — c'est ainsi que
  ``contrats.Contrat`` et ``flotte.Vehicule``, les deux pilotes, sont câblés.
  Aucun modèle d'``apps/ao/models.py`` ne porte ce champ aujourd'hui.
  Déclarer la surface sans lui donnerait un écran de champs personnalisés qui
  accepte la saisie et la jette en silence — pire qu'une surface vide.
  Débloquer = ajouter ``custom_data`` (+ sa migration additive) sur
  ``AppelOffre`` et ``BatimentAO``, puis déclarer ici DANS LE MÊME COMMIT.
* ``agent_actions_module`` est rempli par AOF167, quand son module existe — pas
  avant. (``kpi_providers`` l'a été par AOF166 : ``apps.ao.kpis.kpi_ao``.)
"""
from __future__ import annotations

PLATFORM = {
    'module': 'ao',
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    # Voir le docstring : cette liste n'avance qu'avec ``searchable_models``.
    'record_targets': ['ao.appeloffre'],
    # Voir le docstring : VIDE À DESSEIN tant qu'aucune spec AO n'existe dans
    # ``apps/reporting/search.py``. Une déclaration ici serait un mensonge.
    'searchable_models': [],
    # Voir le docstring : VIDE À DESSEIN tant qu'aucun modèle AO ne porte le
    # champ ``custom_data`` par lequel les valeurs sont stockées.
    'customfield_models': [],
    # AOF165/AOF30/ARC32 — les DEUX spécifications d'import réellement
    # implémentées par ``apps/ao/imports.py`` (relevé de toiture saisi sur
    # tableur) : obstacles et chaînes de cotes. Les clés sont EXACTEMENT celles
    # de ``FIELD_MAPS_AO`` — un test le vérifie, sinon la déclaration
    # promettrait une cible d'import qui n'existe pas.
    'import_specs': ['obstacles', 'chaines'],
    'agent_actions_module': '',
    # AOF15/ARC34 — le statut d'un AO est automatisable par une règle no-code
    # ``RECORD_STATE_CHANGE``. La surface est RÉELLEMENT câblée (règle
    # d'honnêteté ARC41) : ``apps.ao.services.changer_statut_ao`` — le SEUL
    # point de mutation du statut — appelle
    # ``emettre_changement_statut_automation`` après chaque transition réussie,
    # sur le même précédent que ``contrats``/``gestion_projet``. Le statut visé
    # est celui du DOMAINE AO, jamais une étape STAGES.py (règle #2).
    #
    # AOF165 — la DATE LIMITE de remise n'est délibérément PAS déclarée ici :
    # ce n'est pas un champ d'ÉTAT. Un couperet de calendrier est traité par
    # ``EcheanceAO`` + le beat ``ao.rappeler_echeances`` (AOF15) ; le loger
    # dans une surface de transition d'état ferait croire à une automatisation
    # no-code qui n'existe pas.
    'automation_state_fields': [
        {'model': 'ao.appeloffre', 'field': 'statut'},
    ],
    # AOF166/ARC40 — provider KPI du domaine AO : un CALLABLE dotted résolu à
    # l'exécution par ``apps/reporting/reports.py::kpi_federes``, appelé
    # ``provider(company)``. Réellement câblé (règle d'honnêteté ARC41) :
    # ``apps.ao.kpis.kpi_ao`` existe et rend des tuiles normalisées
    # ``{id, label, valeur, unite?}``. Aucun coût, aucune marge n'y transite.
    'kpi_providers': ['apps.ao.kpis.kpi_ao'],
}
