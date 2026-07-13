"""Vue FG317 — réceptionné-non-facturé (GR/IR), dette latente provisionnée.

``ReceptionNonFactureeViewSet`` : CRUD des provisions de dette latente
(marchandise reçue, facture non encore reçue) + action ``lettrer`` qui solde la
provision à l'arrivée de la facture fournisseur. Lecture & écriture
responsable/admin (montants INTERNES). Multi-tenant via ``TenantMixin`` : société
+ ``created_by`` posés côté serveur ; les FK liées sont validées tenant.
Cross-app : ``stock`` en string-FK.
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.utils import timezone

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import ReceptionNonFacturee
from ..serializers import ReceptionNonFactureeSerializer


def _check_tenant(serializer, company, field):
    cid = getattr(company, 'id', None)
    obj = serializer.validated_data.get(field)
    if obj is not None and getattr(obj, 'company_id', None) != cid:
        raise ValidationError({field: 'Objet inconnu pour cette société.'})


class ReceptionNonFactureeViewSet(CompanyScopedModelViewSet):
    """FG317 — provisions GR/IR. Lecture & écriture responsable/admin (montants
    INTERNES). Société + `created_by` posés serveur ; reception/bon_commande
    validés tenant. Filtrable par `lettre`, `bon_commande`. Lettrage via
    l'action `lettrer`."""
    queryset = ReceptionNonFacturee.objects.select_related(
        'reception', 'bon_commande', 'facture', 'created_by').all()
    serializer_class = ReceptionNonFactureeSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        lettre = params.get('lettre')
        if lettre is not None and lettre != '':
            qs = qs.filter(lettre=lettre.lower() in ('1', 'true', 'vrai',
                                                     'oui'))
        bcf = params.get('bon_commande')
        if bcf:
            qs = qs.filter(bon_commande_id=bcf)
        return qs

    def _check_all_tenant(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'reception')
        _check_tenant(serializer, company, 'bon_commande')

    def perform_create(self, serializer):
        self._check_all_tenant(serializer)
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_all_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def lettrer(self, request, pk=None):
        """FG317 — solde la provision à l'arrivée de la facture : pose
        `lettre=True` + date de lettrage et, optionnellement, la `facture`
        fournisseur (validée tenant). Idempotent."""
        prov = self.get_object()
        facture_id = request.data.get('facture')
        if facture_id:
            from django.apps import apps as django_apps
            facture_model = django_apps.get_model('achats', 'FactureFournisseur')
            facture = facture_model.objects.filter(
                id=facture_id, company=request.user.company).first()
            if facture is None:
                return Response(
                    {'facture': 'Facture inconnue pour cette société.'},
                    status=status.HTTP_400_BAD_REQUEST)
            prov.facture = facture
        fields = ['date_modification']
        if not prov.lettre:
            prov.lettre = True
            prov.date_lettrage = timezone.now().date()
            fields += ['lettre', 'date_lettrage']
        if facture_id:
            fields.append('facture')
        prov.save(update_fields=fields)
        return Response(self.get_serializer(prov).data,
                        status=status.HTTP_200_OK)
