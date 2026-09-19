"""NTOBS27 — API publique LECTURE SEULE « Fiabilité », sous /api/public/v1/.

Trois endpoints authentifiés par clé d'API (scope ``fiabilite:lecture``),
scopés à la société DE LA CLÉ (jamais un paramètre client), pour qu'un client
grand-compte branche son propre dashboard de gouvernance fournisseur :

* ``GET /api/public/v1/fiabilite/sauvegardes/`` — dernière sauvegarde + dernier
  drill de restauration, AU FORMAT NTOBS5 (``core.backup.resume_sauvegardes``
  réutilisée telle quelle : même dict que l'écran self-service interne, aucun
  second calcul, aucun champ recalculé ici) ;
* ``GET /api/public/v1/fiabilite/sla/{periode}/`` — le rapport SLA mensuel
  NTOBS3 de la période ``YYYY-MM`` (``core.sla.SlaSnapshotSerializer``
  réutilisé), 404 quand aucun rapport n'existe pour ce mois ;
* ``GET /api/public/v1/fiabilite/usage/`` — le résumé « Limites & usage »
  NTOBS8 (``core.usage_limits.usage_summary`` réutilisée).

AUCUN NOUVEAU MOTEUR, AUCUN NOUVEAU QUOTA : les trois vues appellent les
sélecteurs/serializers EXISTANTS de ``core``, et le quota/débit passe par
``ApiKeyRateThrottle`` — donc par l'infra ``ApiUsagePlan``/``ApiUsageRecord``
(FG398) déjà en place.

CE QUI N'EST PAS EXPOSÉ. Le résumé sauvegardes NTOBS5 ne rend, pour les runs
SYSTÈME-WIDE (dump complet + drill, ``company=None``), que date + statut —
jamais l'artefact, la clé d'objet MinIO, la taille ou le manifeste interne :
c'est déjà la forme produite par ``resume_sauvegardes``, et on ne l'élargit
pas pour un consommateur EXTERNE. Le rapport SLA expose la disponibilité, la
latence P95 et le crédit DÛ (les chiffres que le client lit dans son contrat),
jamais la vue cross-tenant NTOBS4 des crédits dus de toutes les sociétés.
``latence_p95_ms`` et ``credit_du_montant`` peuvent valoir ``null`` : c'est
« non mesuré / inconnu » — jamais un chiffre de remplissage.
"""
from datetime import datetime

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.backup import resume_sauvegardes
from core.sla import SlaSnapshot, SlaSnapshotSerializer
from core.usage_limits import usage_summary

from .auth import PUBLIC_AUTHENTICATION_CLASSES, ApiKeyRateThrottle, HasApiScope
from .constants import SCOPE_READ_FIABILITE
from .public_response import PublicApiResponseMixin

_RUN_RESUME_SHAPE = inline_serializer('FiabiliteRunResumePublic', {
    'date': drf_serializers.DateTimeField(),
    'statut': drf_serializers.CharField(),
}, allow_null=True)


class PublicFiabiliteBaseView(PublicApiResponseMixin, APIView):
    """Socle commun : clé d'API + scope ``fiabilite:lecture`` + throttle."""

    authentication_classes = PUBLIC_AUTHENTICATION_CLASSES
    permission_classes = [HasApiScope]
    throttle_classes = [ApiKeyRateThrottle]
    required_scope = SCOPE_READ_FIABILITE


class PublicFiabiliteSauvegardesView(PublicFiabiliteBaseView):
    """``GET /api/public/v1/fiabilite/sauvegardes/`` — format NTOBS5."""

    @extend_schema(responses=inline_serializer('FiabiliteSauvegardesPublic', {
        'derniere_sauvegarde': _RUN_RESUME_SHAPE,
        'dernier_drill': _RUN_RESUME_SHAPE,
        'rpo_planifie': drf_serializers.CharField(allow_null=True),
        'rto_annonce_heures': drf_serializers.IntegerField(allow_null=True),
    }))
    def get(self, request):
        return Response(resume_sauvegardes(request.auth.company))


class PublicFiabiliteSlaView(PublicFiabiliteBaseView):
    """``GET /api/public/v1/fiabilite/sla/{periode}/`` — rapport NTOBS3.

    ``periode`` au format ``YYYY-MM`` (même convention que l'export PDF interne
    ``/api/django/core/sla/<periode>/export-pdf/``). Un format invalide rend
    400 en NOMMANT le format attendu ; une période sans rapport rend 404 —
    jamais un objet vide qui laisserait croire à une disponibilité de 0 %.
    """

    @extend_schema(responses=SlaSnapshotSerializer)
    def get(self, request, periode):
        try:
            annee_str, mois_str = str(periode).split('-')
            periode_date = datetime(int(annee_str), int(mois_str), 1).date()
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Format de période invalide (attendu YYYY-MM).'},
                status=status.HTTP_400_BAD_REQUEST)

        snapshot = SlaSnapshot.objects.filter(
            company=request.auth.company, periode=periode_date).first()
        if snapshot is None:
            return Response(
                {'detail': 'Aucun rapport SLA pour cette période.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response(SlaSnapshotSerializer(snapshot).data)


class PublicFiabiliteUsageView(PublicFiabiliteBaseView):
    """``GET /api/public/v1/fiabilite/usage/`` — résumé NTOBS8."""

    @extend_schema(responses=inline_serializer('FiabiliteUsagePublic', {
        'ressources': drf_serializers.ListField(
            child=drf_serializers.DictField()),
        'genere_le': drf_serializers.DateTimeField(),
    }))
    def get(self, request):
        return Response(usage_summary(request.auth.company))
