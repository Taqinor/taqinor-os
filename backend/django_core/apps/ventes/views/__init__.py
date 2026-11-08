"""Vues de l'app Ventes — surface d'import publique.

L'ancien ``views.py`` monolithe a été éclaté en un module par ressource pour
que plusieurs vues puissent évoluer en parallèle sans se gêner. Ce package
ré-exporte toutes les classes/fonctions publiques pour que
``from apps.ventes.views import …`` (et ``urls.py``) continuent de fonctionner à
l'identique. Aucun changement de comportement ni d'endpoint."""
from .devis import DevisViewSet
from .ligne_devis import LigneDevisViewSet
from .bon_commande import BonCommandeViewSet
from .avoir import AvoirViewSet, NoteDebitViewSet  # ZFAC4
from .email import email_config
from .credit_warning import client_credit_warning
from .releve_import import releve_dry_run, releve_commit
from .roof_config import roof_config
from .preset import DevisPresetViewSet  # QJ16-wiring
from .regulatory import (  # FG268-FG271
    RegulatoryDossierViewSet,
    DossierChecklistItemViewSet,
    DossierExchangeViewSet,
    SubventionDossierViewSet,
    Regularisation8221ViewSet,
)
from .commissioning import (  # FG274-FG278, FG287
    CommissioningTestViewSet,
    IVCurveCaptureViewSet,
    AsBuiltPackViewSet,
    AttestationConformiteViewSet,
    TestPerformanceReceptionViewSet,
    AttestationREViewSet,
)
from .remise_encaissement import RemiseEncaissementViewSet  # XFSM19
from .liste_prix import ListePrixViewSet, prix_applicable_view  # XSAL1-3
from .parametres_gammes import ParametresGammesView  # PVMRQ
from .plan_commission import PlanCommissionViewSet  # WIR281/XSAL6

__all__ = [
    'DevisViewSet', 'LigneDevisViewSet', 'BonCommandeViewSet', 'FactureViewSet', 'AvoirViewSet',
    'NoteDebitViewSet', 'PaiementViewSet', 'LigneFactureViewSet', 'email_config',
    'client_credit_warning', 'releve_dry_run', 'releve_commit', 'roof_config', 'DevisPresetViewSet',
    'RegulatoryDossierViewSet', 'DossierChecklistItemViewSet', 'DossierExchangeViewSet',
    'SubventionDossierViewSet', 'Regularisation8221ViewSet', 'CommissioningTestViewSet',
    'IVCurveCaptureViewSet', 'AsBuiltPackViewSet', 'AttestationConformiteViewSet',
    'TestPerformanceReceptionViewSet', 'AttestationREViewSet', 'RemiseEncaissementViewSet',
    'ListePrixViewSet', 'prix_applicable_view', 'ParametresGammesView', 'PlanCommissionViewSet',
    '_economie_action', '_economie_pompage_action', '_economie_ci_action',
]
# CALX288 — rattache l'action ``economie`` au ``DevisViewSet`` (import DERNIER,
# exécuté avant ``router.register`` puisque ``urls.py`` importe ce paquet).
from . import economie as _economie_action
# AGR206 — rattache l'action ``economie_pompage`` au ``DevisViewSet`` (même
# patron : import DERNIER, avant ``router.register``).
from . import economie_pompage as _economie_pompage_action
# CIQ210 — rattache l'action ``economie_ci`` au ``DevisViewSet`` (même
# patron : import DERNIER, avant ``router.register``).
from . import economie_ci as _economie_ci_action


# ODX18 — les ViewSets de facturation vivent dans ``apps.facturation.views``
# (déplacés tels quels) ; ``from apps.ventes.views import FactureViewSet`` (et
# ``urls.py``) continuent de renvoyer les MÊMES classes. Résolution PARESSEUSE
# (PEP 562) : ``apps.facturation.views`` importe le sous-module
# ``apps.ventes.views.openapi_docs``, donc un import en tête ici formerait un
# cycle quand facturation est chargée la première.
_NOMS_FACTURATION = frozenset({
    'FactureViewSet', 'PaiementViewSet', 'LigneFactureViewSet',
})


def __getattr__(nom):
    if nom in _NOMS_FACTURATION:
        from apps.facturation import views as vues_facturation
        return getattr(vues_facturation, nom)
    raise AttributeError(f"module {__name__!r} has no attribute {nom!r}")
