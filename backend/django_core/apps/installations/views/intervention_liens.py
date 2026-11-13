"""APUB6 — coupure du lien public du compte-rendu d'intervention, sortie de
``intervention.py`` (fichier ≥ 2 000 lignes, C20)."""
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.roles.permissions import DroitDeLaGrille
from authentication.permissions import IsResponsableOrAdmin

from . import _openapi as oa


class CouperLienRapportMixin:
    @oa.extend_schema(request=None, responses=oa.OBJ)
    @action(detail=True, methods=['post'], url_path='couper-lien-rapport',
            permission_classes=[IsResponsableOrAdmin, DroitDeLaGrille('intervention_gerer')])  # ADRG79
    def couper_lien_rapport(self, request, pk=None):
        """APUB6 — coupe le lien public du compte-rendu : page, PDF et photos
        rendent 404 sur l'ancien jeton ; ``lien-rapport`` en pose un neuf."""
        interv = self.get_object()
        interv.couper_lien_rapport()
        return Response({'coupe': True})


def devis_de_reserve(reserve, interv, user):
    """XFSM18/ACNC34 — devis de réparation d'une réserve, garde jugée sur la
    réserve relue SOUS VERROU (deux clics croisés : un seul devis). Renvoie
    ``(réserve relue, devis neuf)`` ou ``(réserve relue, None)`` si elle porte
    déjà son devis ; le ``ValueError`` du service ventes remonte."""
    from django.db import transaction
    from apps.ventes.services import create_devis_from_reserve
    with transaction.atomic():
        reserve = type(reserve).objects.select_for_update().get(pk=reserve.pk, intervention=interv)
        if reserve.devis_repare_id:
            return reserve, None
        devis = create_devis_from_reserve(reserve=reserve, user=user)
        reserve.devis_repare_id = devis.id
        reserve.save(update_fields=['devis_repare_id'])
    return reserve, devis
