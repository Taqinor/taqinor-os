"""T16 — service : génération à la lecture des tickets SAV préventifs dus.

Aucun planificateur : on matérialise les visites dues quand l'utilisateur
consulte la liste « à venir » / déclenche la génération. Idempotent — on avance
`derniere_visite` à la date de la visite générée pour ne pas dupliquer.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from apps.ventes.utils.references import create_with_reference
from .models import ContratMaintenance, Ticket
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

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

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
