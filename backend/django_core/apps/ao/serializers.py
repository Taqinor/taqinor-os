"""Serializers du module Appels d'offres (``apps.ao``).

ODX11 — ré-export TRANSITOIRE des serializers AO qui vivent encore dans
``apps.compta.serializers`` (interleavés avec les serializers comptables). Ce
module expose ``apps.ao.serializers`` pour les ViewSets AO et les nouvelles
routes ``/api/django/ao/…`` ; ODX22 re-logera leur corps ici.
"""

from apps.compta.serializers import (  # noqa: F401
    AppelOffreSerializer,
    BordereauPrixSerializer,
    CautionSoumissionSerializer,
    DossierSoumissionSerializer,
    EcheanceAOSerializer,
    LigneBordereauSerializer,
    PieceSoumissionSerializer,
    ResultatAOSerializer,
)
