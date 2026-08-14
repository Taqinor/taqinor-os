"""NTWMS34 — plans d'échantillonnage à réception (CRUD) + saisie du verdict.

Le CRUD est un référentiel de PARAMÉTRAGE : lecture pour tout rôle (le
magasinier doit savoir ce qu'il devra contrôler), écriture responsable/admin.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from core.viewsets import CompanyScopedModelViewSet

from ..models import ControleReception, PlanEchantillonnage

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class PlanEchantillonnageSerializer(serializers.ModelSerializer):
    categorie_nom = serializers.CharField(
        source='categorie.nom', read_only=True, default='')

    class Meta:
        model = PlanEchantillonnage
        fields = [
            'id', 'categorie', 'categorie_nom', 'taux_echantillon_pct',
            'actif', 'note', 'created_at', 'updated_at',
        ]
        # `company` n'est JAMAIS acceptée du corps : le viewset la force.
        read_only_fields = ['created_at', 'updated_at']

    def validate_taux_echantillon_pct(self, value):
        if value is None:
            return 0
        if value > 100:
            raise serializers.ValidationError(
                "Le taux d'échantillonnage ne peut pas dépasser 100 %.")
        return value


class ControleReceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControleReception
        fields = [
            'id', 'reception', 'resultat', 'unites_controlees',
            'unites_attendues', 'observation', 'controle_par', 'created_at',
        ]
        read_only_fields = fields


class PlanEchantillonnageViewSet(CompanyScopedModelViewSet):
    """NTWMS34 — référentiel des plans d'échantillonnage à réception.

    Un plan sans catégorie est le plan PAR DÉFAUT de la société (un seul,
    contrainte unique partielle). Aucune société n'a de plan par défaut à
    l'installation : sans plan créé, la confirmation de réception reste
    exactement ce qu'elle était.
    """
    queryset = PlanEchantillonnage.objects.select_related('categorie').all()
    serializer_class = PlanEchantillonnageSerializer
    ordering = ['categorie_id', 'id']

    def get_permissions(self):
        # `get_permissions` prime sur le `permission_classes` d'une @action :
        # chaque action est listée explicitement ici.
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        # `filterset_fields` est un no-op ici (aucun DjangoFilterBackend) :
        # le filtrage est manuel, comme partout dans cette app.
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie_id=categorie)
        actif = self.request.query_params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        return qs


# ── Actions montées sur ReceptionFournisseurViewSet (voir mixin ci-dessous) ─

class ControleReceptionActionsMixin:
    """Mixin des deux actions NTWMS34 du viewset de réception.

    Vit ici pour que le fichier ``reception_fournisseur.py`` n'enfle pas ;
    les gardes de rôle sont déclarées dans le ``get_permissions`` du viewset
    hôte (piège connu : `get_permissions` écrase le `permission_classes` de
    l'@action).
    """

    @extend_schema(request=None, responses={
        200: inline_serializer('StockReceptionEchantillon', {
            'echantillon_requis': serializers.BooleanField(),
            'unites_attendues': serializers.IntegerField(),
            'controle': ControleReceptionSerializer(allow_null=True),
        }),
    })
    @action(detail=True, methods=['get'], url_path='echantillonnage',
            permission_classes=[IsAnyRole])
    def echantillonnage(self, request, pk=None):
        """NTWMS34 — le plan s'applique-t-il à cette réception, et où en est
        le contrôle ? Lecture seule."""
        from ..services_qualite_reception import (
            controle_de_reception, echantillon_attendu_reception,
            echantillon_requis_pour_reception,
        )

        reception = self.get_object()
        controle = controle_de_reception(reception)
        return Response({
            'echantillon_requis': echantillon_requis_pour_reception(reception),
            'unites_attendues': echantillon_attendu_reception(reception),
            'controle': (ControleReceptionSerializer(controle).data
                         if controle else None),
        })

    @extend_schema(request=None, responses={
        200: ControleReceptionSerializer,
    })
    @action(detail=True, methods=['post'], url_path='controle-qualite',
            permission_classes=[IsResponsableOrAdmin])
    def controle_qualite(self, request, pk=None):
        """NTWMS34 — saisit le verdict (``{resultat, unites_controlees?,
        observation?}``). Sans lui, une réception soumise à un plan ne peut
        pas être confirmée. NON CONFORME route vers la quarantaine."""
        from ..services_qualite_reception import enregistrer_controle_reception

        reception = self.get_object()
        try:
            controle = enregistrer_controle_reception(
                reception=reception, user=request.user,
                resultat=request.data.get('resultat'),
                unites_controlees=request.data.get('unites_controlees') or 0,
                observation=request.data.get('observation') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(ControleReceptionSerializer(controle).data)
