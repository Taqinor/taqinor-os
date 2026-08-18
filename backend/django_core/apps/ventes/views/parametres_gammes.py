"""PVMRQ — Réglages « offre à deux gammes » par société (fondateur 18/08/2026).

Endpoint singleton (GET/PATCH), même patron que
``apps.compta.views.ParametresTresorerieView`` : société scopée, posée côté
serveur, créée avec ses valeurs par défaut à la première lecture (aucune
régression sur la composition automatique tant que rien n'est réglé).
"""
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from authentication.permissions import IsResponsableOrAdmin
from ..serializers import ParametresGammesSerializer
from .. import services


class ParametresGammesView(generics.RetrieveUpdateAPIView):
    """Réglages « gammes » de la société (PVMRQ), singleton auto-créé.

    ``GET`` renvoie le réglage (créé avec les valeurs par défaut à la
    première lecture) ; ``PATCH`` le met à jour. Société scopée, posée côté
    serveur. LECTURE ouverte à tout utilisateur authentifié de la société :
    l'épinglage de marque doit s'appliquer aux devis de TOUS les commerciaux
    (fondateur 18/08 — un GET réservé au responsable faisait retomber leurs
    compositions en « aucune préférence » en silence). ÉCRITURE réservée
    Admin/Responsable, comme ``ParametresTresorerieView``.
    """
    http_method_names = ['get', 'patch', 'head', 'options']
    serializer_class = ParametresGammesSerializer

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticated()]
        return [IsResponsableOrAdmin()]

    def get_object(self):
        return services.get_parametres_gammes(self.request.user.company)
