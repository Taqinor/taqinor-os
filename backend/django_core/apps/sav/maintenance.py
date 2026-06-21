"""T16 — service : génération à la lecture des tickets SAV préventifs dus.

Aucun planificateur : on matérialise les visites dues quand l'utilisateur
consulte la liste « à venir » / déclenche la génération. Idempotent — on avance
`derniere_visite` à la date de la visite générée pour ne pas dupliquer.
"""
from datetime import date as _date

from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from apps.ventes.utils.references import create_with_reference
from .models import ContratMaintenance, Ticket
from .pdf import rapport_maintenance_pdf
from .serializers_maintenance import ContratMaintenanceSerializer


def generer_visites_dues(company, user):
    """Crée un ticket SAV préventif pour chaque contrat actif dont la visite est
    due, et avance la date de dernière visite. Renvoie le nombre généré."""
    genere = 0
    for contrat in ContratMaintenance.objects.filter(company=company, actif=True):
        if not contrat.is_due():
            continue
        due = contrat.prochaine_visite()

        def _save(ref, c=contrat, d=due):
            return Ticket.objects.create(
                reference=ref, company=company, client=c.client,
                installation=c.installation, type=Ticket.Type.PREVENTIF,
                statut=Ticket.Statut.NOUVEAU, date_ouverture=d,
                description=f'Visite de maintenance préventive (contrat #{c.pk}).',
                created_by=user)

        create_with_reference(Ticket, 'SAV', company, _save)
        contrat.derniere_visite = due
        contrat.save(update_fields=['derniere_visite'])
        genere += 1
    return genere


class ContratMaintenanceViewSet(TenantMixin, viewsets.ModelViewSet):
    """Contrats de maintenance (T16). Lecture tout rôle, écriture responsable/
    admin. ?due=1 → seulement les contrats dont la visite est due."""
    queryset = ContratMaintenance.objects.select_related(
        'client', 'installation').all()
    serializer_class = ContratMaintenanceSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'a_venir'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def _check_tenant(self, serializer):
        """Tenant safety : le client et le chantier ciblés (FK inscriptibles)
        doivent appartenir à la société du user — sinon un contrat lierait les
        enregistrements d'une autre société (et la visite/PDF générés
        fuiteraient le chantier étranger)."""
        from rest_framework.exceptions import ValidationError
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        client = serializer.validated_data.get('client')
        installation = serializer.validated_data.get('installation')
        if client is not None and client.company_id != cid:
            raise ValidationError({'client': 'Client inconnu.'})
        if installation is not None and installation.company_id != cid:
            raise ValidationError({'installation': 'Chantier inconnu.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('due') in ('1', 'true'):
            ids = [c.id for c in qs if c.is_due()]
            qs = qs.filter(id__in=ids)
        return qs

    @action(detail=False, methods=['post'], url_path='generer-dus',
            permission_classes=[IsResponsableOrAdmin])
    def generer_dus(self, request):
        """Matérialise (à la demande, sans planificateur) les tickets préventifs
        des contrats dont la visite est due."""
        n = generer_visites_dues(request.user.company, request.user)
        return Response({'ok': True, 'tickets_generes': n},
                        status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='facturer',
            permission_classes=[IsResponsableOrAdmin])
    def facturer(self, request, pk=None):
        """FG40 — Émet une facture de maintenance récurrente pour ce contrat.

        POST /sav/contrats-maintenance/{id}/facturer/

        Crée une Facture (statut=EMISE) via ventes.services.creer_facture_contrat
        et avance `derniere_facturation`. La facturation doit être activée
        (`facturation_active=True`) et un prix doit être renseigné sur le contrat.

        Réponse 201 : {ok: true, facture_reference: str, facture_id: int}
        """
        contrat = self.get_object()
        try:
            from apps.ventes.services import creer_facture_contrat
            facture = creer_facture_contrat(
                contrat=contrat,
                user=request.user,
                company=request.user.company,
            )
        except ValueError as exc:
            return Response({'ok': False, 'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                'facturer: erreur inattendue (contrat #%s)', pk, exc_info=True)
            return Response(
                {'ok': False, 'detail': 'Erreur inattendue lors de la facturation.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(
            {
                'ok': True,
                'facture_reference': facture.reference,
                'facture_id': facture.id,
            },
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='rapport-pdf',
            permission_classes=[IsResponsableOrAdmin])
    def rapport_pdf(self, request, pk=None):
        """N47 — rapport court de visite de maintenance (PDF, client-facing).

        Sans prix d'achat. ?date=AAAA-MM-JJ pour la date de visite (défaut :
        dernière visite enregistrée)."""
        contrat = self.get_object()
        raw = (request.query_params.get('date') or '').strip()
        try:
            visite = _date.fromisoformat(raw) if raw else None
        except ValueError:
            visite = None
        pdf_bytes = rapport_maintenance_pdf(contrat, visite)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="maintenance-contrat-{contrat.pk}.pdf"')
        return resp
