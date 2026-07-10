"""Vue FG307 — attestations & assurances obligatoires des sous-traitants.

``AttestationSousTraitantViewSet`` : CRUD des pièces administratives d'un
sous-traitant (CNSS, RC décennale, agrément…), plus une action ``affectabilite``
qui répond si le sous-traitant est affectable (actif + aucune pièce obligatoire
expirée) à une date donnée. Lecture tout rôle, écriture responsable/admin.
Multi-tenant via ``TenantMixin`` : société + ``created_by`` posés côté serveur ;
le ``sous_traitant`` ciblé est validé tenant.
"""
from datetime import date

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.stock import selectors as stock_selectors

from ..models import AttestationSousTraitant
from ..serializers import AttestationSousTraitantSerializer
from .. import selectors

READ_ACTIONS = ['list', 'retrieve', 'affectabilite']


class AttestationSousTraitantViewSet(CompanyScopedModelViewSet):
    """FG307 — attestations sous-traitant. Lecture tout rôle, écriture
    responsable/admin. Société + `created_by` posés serveur ; `sous_traitant`
    validé tenant. Filtrable par `sous_traitant` et `type_piece`."""
    queryset = AttestationSousTraitant.objects.select_related(
        'sous_traitant', 'created_by').all()
    serializer_class = AttestationSousTraitantSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        st = params.get('sous_traitant')
        if st:
            qs = qs.filter(sous_traitant_id=st)
        type_piece = params.get('type_piece')
        if type_piece:
            qs = qs.filter(type_piece=type_piece)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        st = serializer.validated_data.get('sous_traitant')
        if st is not None and getattr(st, 'company_id', None) != getattr(
                company, 'id', None):
            raise ValidationError(
                {'sous_traitant': 'Sous-traitant inconnu pour cette société.'})
        # DC34 — le sous-traitant est un stock.Fournisseur de type « service ».
        if st is not None and getattr(st, 'type', None) != 'service':
            raise ValidationError(
                {'sous_traitant': 'Ce fournisseur n\'est pas un sous-traitant '
                                  '(type service).'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'])
    def affectabilite(self, request):
        """FG307 — un sous-traitant est-il affectable (actif + aucune pièce
        obligatoire expirée) ? Param `sous_traitant` requis ; `date` optionnelle
        (YYYY-MM-DD, sinon aujourd'hui). Lecture seule."""
        st_id = request.query_params.get('sous_traitant')
        if not st_id:
            return Response(
                {'detail': 'Paramètre `sous_traitant` requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        # DC34 — le sous-traitant est un stock.Fournisseur(type='service') lu via
        # le sélecteur stock (jamais d'import de apps.stock.models).
        st = stock_selectors.get_sous_traitant(request.user.company, st_id)
        if st is None:
            return Response(
                {'detail': 'Sous-traitant inconnu pour cette société.'},
                status=status.HTTP_404_NOT_FOUND)
        a_la_date = None
        raw = request.query_params.get('date')
        if raw:
            try:
                a_la_date = date.fromisoformat(raw)
            except ValueError:
                return Response(
                    {'date': 'Date invalide (attendu YYYY-MM-DD).'},
                    status=status.HTTP_400_BAD_REQUEST)
        manquantes = selectors.sous_traitant_attestations_manquantes(
            st, a_la_date)
        return Response({
            'sous_traitant': st.id,
            'affectable': selectors.sous_traitant_affectable(st, a_la_date),
            'actif': stock_selectors.sous_traitant_est_actif(st),
            'pieces_expirees': manquantes,
        })
