"""Viewsets DRF du module ``apps.sante``.

Tous les viewsets héritent de ``core.viewsets.CompanyScopedModelViewSet`` :
queryset filtré par ``request.user.company``, ``company`` forcée côté serveur
en création (jamais lue du corps de requête). Le grain RBAC fin (nouveaux
rôles ``secretaire_medicale``/``praticien``/``caissier_sante``) est posé par
NTSAN17 — en attendant, le défaut « authentifié suffit » de
``CompanyScopedModelViewSet`` s'applique.
"""
from core.viewsets import CompanyScopedModelViewSet

from .models import Praticien, Salle
from .serializers import PraticienSerializer, SalleSerializer


class PraticienViewSet(CompanyScopedModelViewSet):
    queryset = Praticien.objects.select_related('user').all()
    serializer_class = PraticienSerializer


class SalleViewSet(CompanyScopedModelViewSet):
    queryset = Salle.objects.all()
    serializer_class = SalleSerializer
