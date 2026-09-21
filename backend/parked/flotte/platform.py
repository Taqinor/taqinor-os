"""ARC28/ARC30/ARC31 — Manifeste plateforme du module Flotte
(« déclarer une fois »).

Déclare ce que Flotte expose aux surfaces transverses (voir ``core.platform``).
ARC30 fait basculer la source de ``records.ALLOWED_TARGETS`` d'un ``set``
littéral figé vers l'union paresseuse des manifestes ``record_targets`` — ce
manifeste porte la cible chatter/records historique (``flotte.vehicule``,
ARC8 — le véhicule reçoit le chatter générique via ChatterViewSetMixin, son
journal maison ``ActiviteFlotte`` reste intact en parallèle).

ARC31 — Vehicule est déclaré cible customfieldable ICI (``customfield_models``)
au lieu d'un appel explicite ``customfields.registry.register(...)`` dans
``FlotteConfig.ready()`` — la SOURCE de peuplement du registre bascule vers un
chargeur central unique (``apps/customfields/apps.py``) qui lit ce manifeste ;
l'API ``registry.register``/``get_model`` reste inchangée.

ARC32 — cible d'import ``vehicules`` (parc flotte, XFLT22) déclarée ici :
l'écriture reste DÉLÉGUÉE à ``apps.flotte.services.creer_vehicule_import`` et le
mapping d'en-têtes à ``dataimport.services.FIELD_MAPS`` ; seule la LISTE des
cibles importables bascule sur ce manifeste.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'flotte',
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    'record_targets': ['flotte.vehicule'],
    'searchable_models': [],
    # ARC31 — cible customfieldable (pilote historique ARC14 ; source
    # basculée depuis FlotteConfig.ready() vers ce manifeste).
    'customfield_models': ['vehicule'],
    # ARC32 — cible d'import Véhicules (XFLT22, écriture déléguée aux services).
    'import_specs': ['vehicules'],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
