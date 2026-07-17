"""Vues du moteur de territoires (NTCRM1). Réservé Administrateur/Directeur —
même RBAC simple que le reste du CRM (``authentication.permissions``), pas de
nouveau code de permission fine (pas de rôle 'territoire_*' à enregistrer)."""
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import Territoire, TerritoireMembre, TerritoireRegle
from .selectors import previsualiser_territoire
from .serializers import (
    TerritoireMembreSerializer, TerritoireRegleSerializer, TerritoireSerializer,
)


class TerritoireViewSet(CompanyScopedModelViewSet):
    queryset = Territoire.objects.all()
    serializer_class = TerritoireSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'resoudre'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=True, methods=['get'], url_path='resoudre')
    def resoudre(self, request, pk=None):
        """NTCRM1 — Résout ce territoire+assigné pour un lead réel
        (``?lead_id=``) ou pour une simulation d'adresse/type
        (``?ville=&type_installation=&montant_estime=&canal=``, NTCRM3),
        SANS MUTER aucun état (ni le lead, ni le compteur de rotation)."""
        territoire = self.get_object()
        lead_id = request.query_params.get('lead_id')
        if lead_id:
            # Lecture cross-app : Lead est détenu par apps.crm, on passe donc
            # par SON sélecteur (jamais un import direct de apps.crm.models).
            from apps.crm.selectors import lead_criteria_for_territoire
            criteres = lead_criteria_for_territoire(request.user.company, lead_id)
            if criteres is None:
                return Response({'detail': 'Lead introuvable.'}, status=404)
        else:
            criteres = {
                'ville': request.query_params.get('ville'),
                'type_installation': request.query_params.get('type_installation'),
                'montant_estime': request.query_params.get('montant_estime'),
                'canal': request.query_params.get('canal'),
            }
        matched, membre = previsualiser_territoire(territoire, criteres)
        return Response({
            'territoire_id': territoire.id,
            'territoire_nom': territoire.nom,
            'matched': matched,
            'assigne_id': membre.utilisateur_id if membre else None,
            'assigne_nom': getattr(membre.utilisateur, 'username', None) if membre else None,
        })


class TerritoireRegleViewSet(CompanyScopedModelViewSet):
    queryset = TerritoireRegle.objects.select_related('territoire')
    serializer_class = TerritoireRegleSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return super().get_queryset().filter(
            territoire__company=self.request.user.company)

    def perform_create(self, serializer):
        # TerritoireRegle n'a pas de FK company directe (elle vit sur son
        # territoire parent) — TenantMixin.perform_create ne s'applique donc
        # pas ici ; la scoping est garantie par get_queryset ci-dessus +
        # le territoire choisi par le client (déjà scopé côté liste).
        serializer.save()


class TerritoireMembreViewSet(CompanyScopedModelViewSet):
    queryset = TerritoireMembre.objects.select_related('territoire', 'utilisateur')
    serializer_class = TerritoireMembreSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return super().get_queryset().filter(
            territoire__company=self.request.user.company)

    def perform_create(self, serializer):
        serializer.save()
