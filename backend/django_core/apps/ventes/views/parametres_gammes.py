"""PVMRQ — Réglages « offre à deux gammes » par société (fondateur 18/08/2026).

Endpoint singleton (GET/PATCH), patron maison des réglages société : société
scopée, posée côté serveur, créée avec ses valeurs par défaut à la première
lecture (aucune régression sur la composition automatique tant que rien n'est
réglé).
"""
from rest_framework import generics
from rest_framework.parsers import JSONParser

from authentication.permissions import (
    HasPermissionOrLegacy, IsAuthenticatedInterne, IsResponsableOrAdmin,
)
from ..serializers import ParametresGammesSerializer
from .. import services


class ParametresGammesView(generics.RetrieveUpdateAPIView):
    """Réglages « gammes » de la société (PVMRQ), singleton auto-créé.

    ``GET`` renvoie le réglage (créé avec les valeurs par défaut à la
    première lecture) ; ``PATCH`` le met à jour. Société scopée, posée côté
    serveur. LECTURE ouverte à tout utilisateur authentifié de la société :
    l'épinglage de marque doit s'appliquer aux devis de TOUS les commerciaux
    (fondateur 18/08 — un GET réservé au responsable faisait retomber leurs
    compositions en « aucune préférence » en silence). ÉCRITURE :
    ``parametres_modifier`` (ADRG11), sauf ``ordre_lignes`` seul (palier ventes).
    """
    http_method_names = ['get', 'patch', 'head', 'options']
    parser_classes = [JSONParser]  # ENF5/D2 : aucun envoi de fichier
    serializer_class = ParametresGammesSerializer

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticatedInterne()]
        # ADRG11 (D-ADRG-5) — l'ordre des lignes réglé depuis le générateur
        # reste au palier ventes ; tout autre champ (épinglage de marque,
        # gammes) est un réglage société : ``parametres_modifier``.
        donnees = self.request.data if isinstance(self.request.data, dict) else {}
        if donnees and set(donnees) <= {'ordre_lignes'}:
            return [IsResponsableOrAdmin()]
        return [IsAuthenticatedInterne(), HasPermissionOrLegacy('parametres_modifier')()]

    def get_object(self):
        return services.get_parametres_gammes(self.request.user.company)
