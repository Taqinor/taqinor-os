"""PVMRQ — Réglages « offre à deux gammes » par société (fondateur 18/08/2026).

Endpoint singleton (GET/PATCH), même patron que
``apps.compta.views.ParametresTresorerieView`` : société scopée, posée côté
serveur, créée avec ses valeurs par défaut à la première lecture (aucune
régression sur la composition automatique tant que rien n'est réglé).
"""
from rest_framework import generics

from authentication.permissions import IsResponsableOrAdmin
from ..serializers import ParametresGammesSerializer
from .. import services


class ParametresGammesView(generics.RetrieveUpdateAPIView):
    """Réglages « gammes » de la société (PVMRQ), singleton auto-créé.

    ``GET`` renvoie le réglage (créé avec les valeurs par défaut à la
    première lecture) ; ``PATCH`` le met à jour. Société scopée, posée côté
    serveur ; Admin/Responsable — comme ``ParametresTresorerieView``.
    """
    http_method_names = ['get', 'patch', 'head', 'options']
    serializer_class = ParametresGammesSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_object(self):
        return services.get_parametres_gammes(self.request.user.company)
