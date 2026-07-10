"""
XFSM23 — vues géolocalisation temps réel + géofencing techniciens.

  * ``GpsConsentRecordViewSet`` — lecture/écriture réservée responsable/admin
    (le technicien ne pose ni ne révoque jamais son propre consentement — la
    trace est établie une fois, en amont, par un rôle habilité).
  * ``PositionTechnicienViewSet`` — le technicien POSTe sa position live via
    l'action ``ping`` ; les superviseurs LISENT la liste/``carte-live``, scopée
    à leur équipe (``core.scoping.scope_queryset``, même patron que F/E).
  * ``GeofenceAlertViewSet`` — lecture (+ acquittement) responsable/admin des
    alertes géofence, jamais générées depuis l'API (seulement par le service).

Toutes multi-tenant via ``TenantMixin`` ; société posée côté serveur, jamais
depuis le corps."""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet
from django.utils import timezone

from .. import gps_tracking_service
from ..models import GeofenceAlert, GpsConsentRecord, Intervention, PositionTechnicien
from ..serializers import (
    GeofenceAlertSerializer, GpsConsentRecordSerializer,
    PositionTechnicienSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class GpsConsentRecordViewSet(CompanyScopedModelViewSet):
    """XFSM23 — trace du consentement GPS déjà obtenu. Lecture/écriture
    réservées responsable/admin : un technicien ne peut ni poser ni révoquer
    son propre consentement via l'API — c'est une décision RH, pas un
    interrupteur mobile."""
    queryset = GpsConsentRecord.objects.select_related(
        'technicien', 'recorded_by').all()
    serializer_class = GpsConsentRecordSerializer

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        technicien = self.request.query_params.get('technicien')
        if technicien:
            qs = qs.filter(technicien_id=technicien)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, recorded_by=self.request.user)

    @action(detail=True, methods=['post'])
    def revoquer(self, request, pk=None):
        """Révocation explicite (responsable/admin uniquement) — motif
        optionnel dans le corps (`reason`)."""
        record = self.get_object()
        record.revoked_at = timezone.now()
        record.revoked_reason = (request.data.get('reason') or '').strip() or None
        record.save(update_fields=['revoked_at', 'revoked_reason'])
        return Response(self.get_serializer(record).data)


class PositionTechnicienViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """XFSM23 — positions live. Lecture scopée équipe (superviseur voit son
    équipe, pas toute la société sauf portée 'all') ; l'écriture passe
    exclusivement par l'action ``ping`` (jamais un POST générique — la
    distance/le géofencing sont calculés serveur, jamais fournis par le
    client)."""
    queryset = PositionTechnicien.objects.select_related(
        'technicien', 'intervention').all()
    serializer_class = PositionTechnicienSerializer

    def get_permissions(self):
        return [IsAnyRole()]

    def get_queryset(self):
        from core.scoping import scope_queryset
        qs = super().get_queryset()
        qs = scope_queryset(qs, self.request.user, ['technicien'])
        intervention = self.request.query_params.get('intervention')
        technicien = self.request.query_params.get('technicien')
        if intervention:
            qs = qs.filter(intervention_id=intervention)
        if technicien:
            qs = qs.filter(technicien_id=technicien)
        return qs

    @action(detail=False, methods=['post'], permission_classes=[IsAnyRole])
    def ping(self, request):
        """XFSM23 — le technicien poste sa position live. Corps :
        ``{"lat": <num>, "lng": <num>, "intervention": <id?>,
        "accuracy_m": <num?>}``. Le tracking est OBLIGATOIRE (pas un
        opt-out) pendant une intervention active du technicien
        (``Intervention.gps_tracking_required``) — cet endpoint ne referme
        jamais la porte, il enregistre simplement le ping ; c'est le CLIENT
        mobile qui doit appeler périodiquement tant que le statut le requiert.
        Consentement requis : un technicien sans consentement actif est
        refusé (403)."""
        company = request.user.company
        if not gps_tracking_service.has_active_consent(company, request.user):
            raise PermissionDenied(
                'Aucun consentement GPS actif enregistré pour cet employé.')
        lat, lng = request.data.get('lat'), request.data.get('lng')
        if lat in (None, '') or lng in (None, ''):
            raise ValidationError({'lat': 'lat et lng sont requis.'})
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            raise ValidationError({'lat': 'Coordonnées invalides.'})
        accuracy_m = request.data.get('accuracy_m')
        try:
            accuracy_m = float(accuracy_m) if accuracy_m not in (None, '') else None
        except (TypeError, ValueError):
            accuracy_m = None
        intervention = None
        intervention_id = request.data.get('intervention')
        if intervention_id:
            intervention = Intervention.objects.filter(
                id=intervention_id, company=company).first()
            if intervention is None:
                raise ValidationError({'intervention': 'Intervention inconnue.'})
        position, alert = gps_tracking_service.enregistrer_position(
            company, request.user, lat, lng, intervention=intervention,
            accuracy_m=accuracy_m)
        data = PositionTechnicienSerializer(position).data
        data['geofence_alert'] = (
            GeofenceAlertSerializer(alert).data if alert else None)
        return Response(data, status=201)

    @action(detail=False, methods=['get'], url_path='carte-live')
    def carte_live(self, request):
        """XFSM23 — dernière position connue par technicien (vue superviseur
        carte temps réel), scopée à l'équipe visible de l'appelant."""
        from core.scoping import visible_user_ids
        company = request.user.company
        ids = visible_user_ids(request.user)
        techniciens = None
        if ids is not None:
            from authentication.models import CustomUser
            techniciens = CustomUser.objects.filter(id__in=ids)
        positions = gps_tracking_service.dernieres_positions_par_technicien(
            company, techniciens=techniciens)
        return Response(PositionTechnicienSerializer(positions, many=True).data)


class GeofenceAlertViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """XFSM23 — alertes géofence (lecture + acquittement responsable/admin)."""
    queryset = GeofenceAlert.objects.select_related(
        'intervention', 'technicien', 'position').all()
    serializer_class = GeofenceAlertSerializer

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        intervention = self.request.query_params.get('intervention')
        if intervention:
            qs = qs.filter(intervention_id=intervention)
        return qs

    @action(detail=True, methods=['post'])
    def acquitter(self, request, pk=None):
        alert = self.get_object()
        alert.acquittee = True
        alert.acquittee_par = request.user
        alert.acquittee_le = timezone.now()
        alert.save(update_fields=['acquittee', 'acquittee_par', 'acquittee_le'])
        return Response(self.get_serializer(alert).data)
