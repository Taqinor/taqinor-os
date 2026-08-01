"""Socle de ViewSets du module Appels d'offres (``apps.ao``) — AOF3.

Constat corrigé ici : les 8 ViewSets AO héritaient de ``_ComptaBaseViewSet``
(``TenantMixin`` + ``ModelViewSet`` + ``IsResponsableOrAdmin``). Deux
conséquences : ``scripts/check_platform.py`` refuse tout NOUVEAU ``ModelViewSet``
non basé sur ``CompanyScopedModelViewSet`` (SCA4), et surtout tout le palier
Responsable voyait l'intégralité d'un dossier d'appel d'offres alors qu'aucune
permission ``ao_*`` n'existait (régression de confidentialité, cf. AOF2).

``AoBaseViewSet`` = ``core.viewsets.CompanyScopedModelViewSet`` (scoping
``request.user.company`` + ``company`` forcée côté serveur, détection
automatique par le sweep d'isolation multi-tenant) + le chatter générique
``records`` (``ChatterViewSetMixin``, ARC8 — jamais une classe ``*Activity``
maison), gardé par ``ao_voir`` (lecture) / ``ao_gerer`` (écriture).

Composition des permissions
---------------------------
``ScopedPermission`` s'applique TOUJOURS (elle porte ``ao_voir``/``ao_gerer``),
et une ``@action`` qui déclare sa PROPRE garde la voit AJOUTÉE, jamais
substituée. C'est volontaire : les actions de chatter héritées de ``records``
déclarent ``IsAnyRole``/``IsResponsableOrAdmin``, or ces gardes-là
ROUVRIRAIENT sur le chatter d'un AO exactement la fuite que AOF2 ferme (un
Commercial lirait la timeline d'un dossier qu'il n'a pas le droit de voir). En
cumulant, la garde du domaine AO reste le plancher et la garde déclarée par
l'action reste un plafond supplémentaire — aucune déclaration n'est perdue en
silence (cf. ``core.permissions.declared_action_permissions``).
"""
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.settings import api_settings

from apps.records.views import ChatterViewSetMixin
from core.documents import TransitionRefusee
from core.permissions import ScopedPermission, declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet

from . import services
from .models import DossierAO, PieceDossierAO
from .permissions import AO_GERER, AO_VOIR
from .serializers import DossierAOSerializer, PieceDossierAOSerializer

__all__ = ['AoBaseViewSet', 'DossierAOViewSet', 'PieceDossierAOViewSet']


class AoBaseViewSet(ChatterViewSetMixin, CompanyScopedModelViewSet):
    """Base UNIQUE des ViewSets du domaine Appels d'offres.

    * société scopée + ``company`` posée côté serveur (jamais lue du corps) ;
    * lecture gardée par ``ao_voir``, écriture par ``ao_gerer`` ;
    * chatter générique ``records`` (``chatter/historique``, ``chatter/noter``).
    """

    read_permission = AO_VOIR
    write_permission = AO_GERER

    def get_permissions(self):
        permissions = [ScopedPermission()]
        declared = declared_action_permissions(self)
        if declared is not None:
            # CUMUL (jamais substitution) — voir le docstring du module.
            permissions.extend(declared)
        return permissions


# ── AOF115 — Dossier de dépôt (kit ``core/documents.py``) ──────────────────

class DossierAOViewSet(AoBaseViewSet):
    """Dossiers de dépôt d'AO (AOF115) — statut GARDÉ par la table du kit.

    ``perform_create`` attribue la référence ``AODOS-YYYYMM-0001`` via
    ``core.numbering`` (jamais ``count()+1``). Le chatter générique
    ``records`` est hérité d'``AoBaseViewSet`` : AUCUNE classe ``*Activity``
    maison n'est créée pour ce document.
    """
    queryset = DossierAO.objects.prefetch_related('pieces').all()
    serializer_class = DossierAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'statut']

    def get_queryset(self):
        qs = super().get_queryset()
        for champ in ('appel_offre', 'statut'):
            valeur = self.request.query_params.get(champ)
            if valeur not in (None, ''):
                qs = qs.filter(**{champ: valeur})
        return qs

    def perform_create(self, serializer):
        """Société posée côté serveur + référence ``AODOS`` race-safe (ARC6)."""
        company = self.request.user.company
        services.creer_dossier_ao(
            company,
            save_fn=lambda reference: serializer.save(
                company=company, reference=reference))

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Fait avancer le dossier — refus 400 motivé si la porte est fermée."""
        dossier = self.get_object()
        cible = (request.data.get('statut') or '').strip()
        motif = (request.data.get('motif') or '').strip()
        try:
            services.changer_statut_dossier(
                dossier, cible, user=request.user, motif=motif)
        except TransitionRefusee as exc:
            return Response(
                {api_settings.NON_FIELD_ERRORS_KEY: [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            donnees = getattr(exc, 'message_dict', None) or {
                api_settings.NON_FIELD_ERRORS_KEY: exc.messages}
            return Response(donnees, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(dossier).data)

    @action(detail=True, methods=['get'], url_path='completude')
    def completude(self, request, pk=None):
        """Complétude DÉRIVÉE + motifs de refus, en français."""
        dossier = self.get_object()
        manquantes = dossier.pieces_obligatoires_manquantes()
        return Response({
            'complet': dossier.complet,
            'taux_completude': str(dossier.taux_completude),
            'pieces_manquantes': [
                {'code': p.code, 'libelle': p.libelle} for p in manquantes],
            'raisons_de_non_depot': dossier.raisons_de_non_depot(),
        })


class PieceDossierAOViewSet(AoBaseViewSet):
    """Pièces d'un dossier de dépôt (AOF115)."""
    queryset = PieceDossierAO.objects.all()
    serializer_class = PieceDossierAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'code']

    def get_queryset(self):
        qs = super().get_queryset()
        for champ in ('dossier', 'visibilite', 'type_piece', 'obligatoire'):
            valeur = self.request.query_params.get(champ)
            if valeur not in (None, ''):
                qs = qs.filter(**{champ: valeur})
        return qs
