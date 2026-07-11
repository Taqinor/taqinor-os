"""XFSM19 — Rapprochement des encaissements terrain par technicien.

Endpoints :
  GET    /ventes/remises-encaissement/               list (par société)
  POST   /ventes/remises-encaissement/                create (déclaration)
  GET    /ventes/remises-encaissement/{id}/           retrieve
  POST   /ventes/remises-encaissement/{id}/cloturer/  clôture (responsable)
  GET    /ventes/remises-encaissement/{id}/pdf/       bordereau PDF

Le technicien déclare sa collecte du jour (des Paiement déjà encaissés,
espèces/chèque) ; le responsable la clôture avec un bordereau PDF. L'écart
(déclaré vs somme des lignes) est calculé et exposé, jamais masqué."""
from django.utils import timezone
from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet  # ARC5
from ..models import Paiement, RemiseEncaissement, LigneRemiseEncaissement
from ..serializers import RemiseEncaissementSerializer

READ_ACTIONS = ['list', 'retrieve']


class RemiseEncaissementViewSet(CompanyScopedModelViewSet):
    # ARC5 — sweep TenantMixin : base transverse unique. get_queryset /
    # perform_create / get_permissions SURCHARGENT la base (scoping direct sur
    # `company`) : scoping et matrice 401/403/404 INCHANGÉS (règle #4).
    queryset = RemiseEncaissement.objects.select_related(
        'technicien', 'created_by', 'cloture_par'
    ).prefetch_related('lignes').all()
    serializer_class = RemiseEncaissementSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['pdf']:
            return [IsAnyRole()]
        elif self.action in ['cloturer', 'valider']:
            return [IsResponsableOrAdmin()]
        return [IsAnyRole()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        technicien_id = self.request.query_params.get('technicien')
        if technicien_id:
            qs = qs.filter(technicien_id=technicien_id)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        lignes = self.request.data.get('lignes') or []
        technicien = serializer.validated_data.get(
            'technicien') or self.request.user

        from ..utils.references import create_with_reference

        def _save(ref):
            return serializer.save(
                company=company, reference=ref, technicien=technicien,
                created_by=self.request.user)

        instance = create_with_reference(
            RemiseEncaissement, 'REM', company, _save,
            padding=4, period='monthly')

        for ligne in lignes:
            paiement_id = (ligne or {}).get('paiement')
            if not paiement_id:
                continue
            try:
                paiement = Paiement.objects.get(
                    id=paiement_id, company=company)
            except Paiement.DoesNotExist:
                continue
            LigneRemiseEncaissement.objects.get_or_create(
                remise=instance, paiement=paiement)

    @action(detail=True, methods=['post'], url_path='cloturer')
    def cloturer(self, request, pk=None):
        """Clôture la remise (responsable/admin) : verrouille les lignes,
        calcule l'écart, génère le bordereau PDF. Alerte (dans la réponse)
        si l'écart ≠ 0 — sans jamais bloquer la clôture."""
        remise = self.get_object()
        if remise.statut != RemiseEncaissement.Statut.OUVERTE:
            raise ValidationError(
                {'detail': 'Seule une remise ouverte peut être clôturée.'})
        remise.statut = RemiseEncaissement.Statut.CLOTUREE
        remise.cloture_par = request.user
        remise.date_cloture = timezone.now()
        remise.save(update_fields=['statut', 'cloture_par', 'date_cloture'])
        try:
            from ..utils.pdf import generate_bordereau_remise_pdf
            generate_bordereau_remise_pdf(remise.id)
            remise.refresh_from_db()
        except Exception:  # noqa: BLE001 — best-effort, la clôture reste valide
            pass
        return Response({
            **RemiseEncaissementSerializer(remise).data,
            'ecart_non_nul': remise.ecart != 0,
        })

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        remise = self.get_object()
        from ..utils.pdf import generate_bordereau_remise_pdf
        pdf_bytes = generate_bordereau_remise_pdf(remise.id)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{remise.reference or remise.id}.pdf"')
        return response
