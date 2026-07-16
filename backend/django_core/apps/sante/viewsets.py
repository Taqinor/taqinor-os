"""Viewsets DRF du module ``apps.sante``.

Tous les viewsets héritent de ``core.viewsets.CompanyScopedModelViewSet`` :
queryset filtré par ``request.user.company``, ``company`` forcée côté serveur
en création (jamais lue du corps de requête). Le grain RBAC fin (nouveaux
rôles ``secretaire_medicale``/``praticien``/``caissier_sante``) est posé par
NTSAN17 — en attendant, le défaut « authentifié suffit » de
``CompanyScopedModelViewSet`` s'applique.
"""
from core.viewsets import CompanyScopedModelViewSet

from .models import Patient, Praticien, Salle
from .serializers import PatientSerializer, PraticienSerializer, SalleSerializer


class PraticienViewSet(CompanyScopedModelViewSet):
    queryset = Praticien.objects.select_related('user').all()
    serializer_class = PraticienSerializer


class SalleViewSet(CompanyScopedModelViewSet):
    queryset = Salle.objects.all()
    serializer_class = SalleSerializer


class PatientViewSet(CompanyScopedModelViewSet):
    """NTSAN3 — dossier administratif patient. ``numero_dossier`` est
    attribué côté serveur à la création (anti-collision, jamais un
    ``count()+1``)."""

    queryset = Patient.objects.select_related('client').all()
    serializer_class = PatientSerializer

    def perform_create(self, serializer):
        super().perform_create(serializer)
        from .services import attribuer_numero_dossier
        attribuer_numero_dossier(serializer.instance)
