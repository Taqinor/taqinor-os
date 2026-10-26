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
depuis le corps.

Revue chantier 26/10/2026 (loi 09-08 / CNDP 17-2014) : le technicien lit la
notice et en accuse réception lui-même (``mon-consentement``), consulte ses
propres positions (``mes-positions``, droit d'accès) ; le ping exige l'accusé
de réception, une intervention dont il est membre et un statut en route / sur
site ; il accepte un lot de rattrapage hors-ligne ; la carte live écarte les
positions trop vieilles ; la liste rend le tracé d'une journée ; la présence
d'une intervention est calculée serveur (``interventions/<pk>/presence/``)."""
from datetime import timedelta

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.conflit_etat import ConflitEtat
from core.permissions import ScopedPermission, declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .. import gps_tracking_service
from ..models import GeofenceAlert, GpsConsentRecord, Intervention, PositionTechnicien
from ..models_gps_tracking import GPS_TRACKING_REQUIRED_STATUTS, notice_geoloc
from ..serializers import (
    GeofenceAlertSerializer, GpsConsentRecordSerializer,
    PositionTechnicienSerializer,
)
from . import _openapi as oa

READ_ACTIONS = ['list', 'retrieve']

#: Actions du viewset consentement ouvertes au technicien LUI-MÊME.
ACTIONS_TECHNICIEN = ('mon_consentement', 'mon_consentement_accepter')

#: Âge maximal par défaut (minutes) d'une position montrée sur la carte live.
CARTE_LIVE_AGE_MAX_MIN = 15

#: Plafond du tracé d'une journée (≈ 1 ping/min sur 24 h = 1 440).
TRAJET_MAX_LIGNES = 2000

#: Tolérance d'horloge du client : un ``captured_at`` plus de 5 min dans le
#: futur est refusé ; un relevé de plus de 7 jours aussi (rien à rattraper).
HORLOGE_FUTUR_MAX = timedelta(minutes=5)
RATTRAPAGE_MAX = timedelta(days=7)


def _mon_consentement_payload(record):
    """Réponse de ``mon-consentement`` (contrat
    ``contract_samples/gps_mon_consentement.json``)."""
    return {
        'existe': record is not None,
        'actif': bool(record is not None and record.is_active),
        'statut': gps_tracking_service.statut_consentement(record),
        'accepte_le': record.accepte_le if record is not None else None,
        'notice': notice_geoloc(record.recepisse_cndp if record else None),
    }


def _point_valide(brut, nom='positions'):
    """Valide un point ``{lat, lng, accuracy_m?, captured_at?}`` → dict
    normalisé (``captured_at`` aware, ``None`` si absent). 400 nommant le
    champ fautif — jamais un 500 (ENF11)."""
    if not isinstance(brut, dict):
        raise ValidationError({nom: 'Chaque position doit être un objet.'})
    lat, lng = brut.get('lat'), brut.get('lng')
    if lat in (None, '') or lng in (None, ''):
        raise ValidationError({'lat': 'lat et lng sont requis.'})
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        raise ValidationError({'lat': 'Coordonnées invalides.'})
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):  # NaN compris (comparaison fausse)
        raise ValidationError({'lat': 'Coordonnées hors plage (lat ±90, lng ±180).'})
    accuracy_m = brut.get('accuracy_m')
    try:
        accuracy_m = float(accuracy_m) if accuracy_m not in (None, '') else None
    except (TypeError, ValueError):
        accuracy_m = None
    if accuracy_m is not None and not 0 <= accuracy_m <= 999999.99:
        raise ValidationError({'accuracy_m': 'Précision hors plage (0 à 999999.99 m).'})
    captured_at = brut.get('captured_at')
    if captured_at in (None, ''):
        captured_at = None
    else:
        try:
            captured_at = parse_datetime(str(captured_at))
        except ValueError:
            captured_at = None
        if captured_at is None:
            raise ValidationError({'captured_at': 'Date-heure ISO 8601 attendue.'})
        if timezone.is_naive(captured_at):
            captured_at = timezone.make_aware(captured_at)
        maintenant = timezone.now()
        if captured_at > maintenant + HORLOGE_FUTUR_MAX:
            raise ValidationError({'captured_at': 'Relevé daté dans le futur.'})
        if captured_at < maintenant - RATTRAPAGE_MAX:
            raise ValidationError({'captured_at': 'Relevé trop ancien (plus de 7 jours).'})
    return {'lat': lat, 'lng': lng, 'accuracy_m': accuracy_m,
            'captured_at': captured_at}


def _intervention_du_ping(request):
    """L'intervention d'un ping, contrôlée : présente (400), de la société
    (400 « inconnue »), dont l'appelant est membre (403) et en route / sur
    site (409). Le suivi ne s'applique QUE pendant le temps de travail
    terrain effectif — jamais hors intervention."""
    intervention_id = request.data.get('intervention')
    if intervention_id in (None, ''):
        raise ValidationError({
            'intervention': "Intervention requise : la position n'est relevée "
                            "que pendant une intervention."})
    try:
        intervention_id = oa.id_entier(intervention_id, 'intervention')
    except ValidationError:
        raise ValidationError({'intervention': 'Intervention inconnue.'})
    intervention = (Intervention.objects
                    .select_related('installation', 'installation__technicien_responsable',
                                    'created_by', 'technicien', 'equipe_ref')
                    .filter(id=intervention_id, company=request.user.company).first())
    if intervention is None:
        raise ValidationError({'intervention': 'Intervention inconnue.'})
    if not gps_tracking_service.membre_de_l_intervention(intervention, request.user):
        raise PermissionDenied(
            "Vous n'êtes ni le technicien ni un membre de l'équipe de cette intervention.")
    if intervention.annulee or intervention.statut not in GPS_TRACKING_REQUIRED_STATUTS:
        raise ConflitEtat(
            "Le suivi de position ne s'applique qu'aux interventions « en route » "
            "ou « sur site ».")
    return intervention


@oa.listing(p0=oa.qi('technicien'))
class GpsConsentRecordViewSet(oa.JsonOnlyMixin, CompanyScopedModelViewSet):
    """XFSM23 — trace du consentement GPS déjà obtenu. Lecture/écriture
    réservées responsable/admin : un technicien ne peut ni poser ni révoquer
    son propre consentement via l'API — c'est une décision RH, pas un
    interrupteur mobile."""
    queryset = GpsConsentRecord.objects.select_related(
        'technicien', 'recorded_by').all()
    serializer_class = GpsConsentRecordSerializer

    def get_permissions(self):
        # Revue chantier 26/10/2026 — seules les deux actions « mon
        # consentement » (lecture de la notice + accusé de réception) sont
        # ouvertes au technicien, et elles ne lisent/écrivent QUE sa propre
        # ligne. Poser/révoquer reste responsable/admin.
        if getattr(self, 'action', None) in ACTIONS_TECHNICIEN:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @oa.extend_schema(responses={200: oa.OBJ})
    @action(detail=False, methods=['get'], url_path='mon-consentement',
            pagination_class=None)
    def mon_consentement(self, request):
        """Le consentement du technicien CONNECTÉ et la notice d'information
        à lire (loi 09-08 art. 5 : responsable, finalités, données,
        destinataires, conservation, droits, n° de récépissé CNDP).
        Contrat : ``contract_samples/gps_mon_consentement.json``."""
        record = gps_tracking_service.consentement_de(
            request.user.company, request.user)
        return Response(_mon_consentement_payload(record))

    @oa.extend_schema(request=None, responses={200: oa.OBJ, 404: oa.OBJ})
    @action(detail=False, methods=['post'], url_path='mon-consentement/accepter',
            pagination_class=None)
    def mon_consentement_accepter(self, request):
        """Accusé de réception de la notice par le technicien LUI-MÊME
        (horodatage + adresse IP). 404 s'il n'a aucun consentement actif :
        c'est au responsable de l'établir d'abord. Idempotent."""
        from core.throttling import ip_de_requete
        record = gps_tracking_service.accepter_consentement(
            request.user.company, request.user, ip=ip_de_requete(request))
        if record is None:
            raise NotFound(
                "Aucun suivi de position n'a été mis en place pour vous par un "
                "responsable.")
        return Response(_mon_consentement_payload(record))

    def get_queryset(self):
        qs = super().get_queryset()
        technicien = self.request.query_params.get('technicien')
        if technicien:
            qs = qs.filter(technicien_id=technicien)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, recorded_by=self.request.user)

    @oa.extend_schema(request=oa.body('RevoquerConsentementRequete', reason=oa.s()))
    @action(detail=True, methods=['post'])
    def revoquer(self, request, pk=None):
        """Révocation explicite (responsable/admin uniquement) — motif
        optionnel dans le corps (`reason`)."""
        record = self.get_object()
        record.revoked_at = timezone.now()
        record.revoked_reason = (request.data.get('reason') or '').strip() or None
        record.save(update_fields=['revoked_at', 'revoked_reason'])
        return Response(self.get_serializer(record).data)


@oa.listing(p0=oa.qi('intervention'), p1=oa.qi('technicien'), p2=oa.qd('date'))
class PositionTechnicienViewSet(oa.JsonOnlyMixin, TenantMixin, viewsets.ReadOnlyModelViewSet):
    """XFSM23 — positions live. Lecture scopée équipe (superviseur voit son
    équipe, pas toute la société sauf portée 'all') ; l'écriture passe
    exclusivement par l'action ``ping`` (jamais un POST générique — la
    distance/le géofencing sont calculés serveur, jamais fournis par le
    client).

    Revue chantier 26/10/2026 : la lecture des positions des AUTRES
    (liste, détail, carte live) est réservée responsable/admin — un
    technicien ne lit plus les positions de ses collègues ; il lit les
    siennes via ``mes-positions`` (droit d'accès, loi 09-08 art. 7).
    ``?technicien=&date=`` rend le tracé de la journée, chronologique et
    non paginé (≤ 2 000 lignes)."""
    queryset = PositionTechnicien.objects.select_related(
        'technicien', 'intervention').all()
    serializer_class = PositionTechnicienSerializer

    def get_permissions(self):
        declared = declared_action_permissions(self)
        if declared is not None:
            return declared  # la garde de l'@action PRIME (ping, ping-lot)
        if getattr(self, 'action', None) == 'mes_positions':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def _jour(self):
        return oa.date_ou_400(self.request.query_params.get('date'), 'date')

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
        if getattr(self, 'action', None) == 'list':
            jour = self._jour()
            if jour is not None:
                qs = qs.filter(captured_at__date=jour)
        return qs

    def _mode_trace(self):
        """Tracé d'une journée : liste + ``technicien`` + ``date``."""
        params = self.request.query_params
        return (getattr(self, 'action', None) == 'list'
                and bool(params.get('technicien')) and bool(params.get('date')))

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        if self._mode_trace():
            # Chronologique et borné (≈ 1 ping/min sur 24 h = 1 440 lignes).
            qs = qs.order_by('captured_at', 'id')[:TRAJET_MAX_LIGNES]
        return qs

    def paginate_queryset(self, queryset):
        # Le tracé d'une journée se dessine d'un bloc : jamais paginé.
        if self._mode_trace():
            return None
        return super().paginate_queryset(queryset)

    @oa.extend_schema(
        request=oa.body(
            'PingGpsRequete',
            # ENF11 (nocturne 15/10) — bornes PUBLIÉES = bornes appliquées : un
            # degré hors plage débordait la colonne decimal(9,6) (500).
            lat=oa.f(True, min_value=-90, max_value=90),
            lng=oa.f(True, min_value=-180, max_value=180),
            accuracy_m=oa.f(null=True, min_value=0, max_value=999999.99),
            captured_at=oa.dt(null=True),
            intervention=oa.idf(required=True),
        ),
        responses={201: oa.OBJ, 400: oa.OBJ, 403: oa.OBJ, 409: oa.OBJ},
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAnyRole])
    def ping(self, request):
        """XFSM23 — le technicien poste sa position live. Corps :
        ``{"intervention": <id>, "lat", "lng", "accuracy_m"?,
        "captured_at"?}`` → 201 ``{position…, geofence_alert}``.

        Gardes (revue chantier 26/10/2026) : 403 sans consentement actif
        ACCEPTÉ par le technicien (notice lue dans l'application) ; 400 sans
        intervention ; 403 si l'appelant n'est ni le technicien ni un membre
        de l'équipe ; 409 si l'intervention n'est pas en route / sur site."""
        oa.corps_objet(request)
        company = request.user.company
        self._garde_consentement(company, request.user)
        point = _point_valide(request.data)
        intervention = _intervention_du_ping(request)
        position, alert = gps_tracking_service.enregistrer_position(
            company, request.user, point['lat'], point['lng'],
            intervention=intervention, accuracy_m=point['accuracy_m'],
            captured_at=point['captured_at'])
        data = PositionTechnicienSerializer(position).data
        data['geofence_alert'] = (
            GeofenceAlertSerializer(alert).data if alert else None)
        return Response(data, status=201)

    @staticmethod
    def _garde_consentement(company, user):
        if not gps_tracking_service.has_active_consent(company, user):
            raise PermissionDenied(
                'Aucun consentement GPS actif enregistré pour cet employé.')
        if not gps_tracking_service.has_acknowledged_consent(company, user):
            raise PermissionDenied(
                "Lisez et acceptez la notice de géolocalisation dans « Ma journée » "
                "avant tout suivi de position.")

    @oa.extend_schema(
        request=oa.body(
            'PingGpsLotRequete',
            intervention=oa.idf(required=True),
            positions=oa.lst(
                child=oa.body(
                    'PingGpsPoint',
                    lat=oa.f(True, min_value=-90, max_value=90),
                    lng=oa.f(True, min_value=-180, max_value=180),
                    accuracy_m=oa.f(null=True, min_value=0, max_value=999999.99),
                    captured_at=oa.dt(True),
                ),
                required=True, min_length=1,
                max_length=gps_tracking_service.LOT_MAX_POSITIONS),
        ),
        responses={201: oa.OBJ, 400: oa.OBJ, 403: oa.OBJ, 409: oa.OBJ},
    )
    @action(detail=False, methods=['post'], url_path='ping-lot',
            permission_classes=[IsAnyRole])
    def ping_lot(self, request):
        """Rattrapage hors-ligne : jusqu'à 20 positions bufferisées par le
        client pendant une coupure réseau, en UN appel. Corps :
        ``{"intervention": <id>, "positions": [{lat, lng, accuracy_m?,
        captured_at}]}`` → 201 ``{enregistrees, doublons, positions,
        geofence_alerts}``. Un point déjà reçu (même intervention + même
        ``captured_at``) est ignoré et compté dans ``doublons``. Mêmes gardes
        que ``ping``."""
        oa.corps_objet(request)
        company = request.user.company
        self._garde_consentement(company, request.user)
        lot = request.data.get('positions')
        if not isinstance(lot, list) or not (
                1 <= len(lot) <= gps_tracking_service.LOT_MAX_POSITIONS):
            raise ValidationError({'positions': (
                f'Liste de 1 à {gps_tracking_service.LOT_MAX_POSITIONS} '
                'positions attendue.')})
        points = [_point_valide(p) for p in lot]
        if any(p['captured_at'] is None for p in points):
            raise ValidationError({
                'captured_at': 'Chaque position du lot doit porter son heure de relevé.'})
        intervention = _intervention_du_ping(request)
        creees, alertes, doublons = gps_tracking_service.enregistrer_lot_positions(
            company, request.user, intervention, points)
        return Response({
            'enregistrees': len(creees),
            'doublons': doublons,
            'positions': PositionTechnicienSerializer(creees, many=True).data,
            'geofence_alerts': GeofenceAlertSerializer(alertes, many=True).data,
        }, status=201)

    @oa.extend_schema(parameters=[oa.qdv('date')],
                      responses=PositionTechnicienSerializer(many=True))
    @action(pagination_class=None, detail=False, methods=['get'], url_path='mes-positions')
    def mes_positions(self, request):
        """Droit d'accès (loi 09-08 art. 7) : les positions du technicien
        CONNECTÉ pour un jour (``?date=``, défaut aujourd'hui), dans l'ordre
        chronologique — jamais celles d'un collègue."""
        jour = self._jour() or timezone.localdate()
        positions = gps_tracking_service.trajet_du_jour(
            request.user.company, request.user.id, jour, limite=TRAJET_MAX_LIGNES)
        return Response(PositionTechnicienSerializer(positions, many=True).data)

    @oa.extend_schema(
        parameters=[oa.qnombre('max_age_min', mini=1, maxi=1440)],
        responses=PositionTechnicienSerializer(many=True))
    @action(pagination_class=None, detail=False, methods=['get'], url_path='carte-live')
    def carte_live(self, request):
        """XFSM23 — dernière position connue par technicien (vue superviseur
        carte temps réel), scopée à l'équipe visible de l'appelant. Revue
        chantier 26/10/2026 : seules les positions de moins de
        ``max_age_min`` minutes (défaut 15) — une position de la veille
        n'est pas « live »."""
        from core.scoping import visible_user_ids
        age_max = oa.nombre_requete(
            request, 'max_age_min', defaut=CARTE_LIVE_AGE_MAX_MIN, mini=1, maxi=1440)
        company = request.user.company
        ids = visible_user_ids(request.user)
        techniciens = None
        if ids is not None:
            from authentication.models import CustomUser
            techniciens = CustomUser.objects.filter(id__in=ids)
        positions = gps_tracking_service.dernieres_positions_par_technicien(
            company, techniciens=techniciens,
            depuis=timezone.now() - timedelta(minutes=age_max))
        return Response(PositionTechnicienSerializer(positions, many=True).data)


@oa.listing(p0=oa.qi('chantier'), p1=oa.qi('intervention'), p2=oa.qs('type_franchissement'))
class GeofenceAlertViewSet(oa.JsonOnlyMixin, TenantMixin, viewsets.ReadOnlyModelViewSet):
    """XFSM23/NTMOB9 — franchissements du rayon chantier (lecture +
    acquittement responsable/admin). Filtrable par ``intervention``, par
    ``chantier`` et par ``type_franchissement`` (``entree``/``sortie``) : c'est
    la lecture qui alimente l'historique de présence par chantier (NTMOB9)."""
    queryset = GeofenceAlert.objects.select_related(
        'intervention', 'technicien', 'position').all()
    serializer_class = GeofenceAlertSerializer

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        intervention = params.get('intervention')
        if intervention:
            qs = qs.filter(intervention_id=intervention)
        chantier = params.get('chantier')
        if chantier:
            qs = qs.filter(intervention__installation_id=chantier)
        type_franchissement = params.get('type_franchissement')
        if type_franchissement in GeofenceAlert.TypeFranchissement.values:
            qs = qs.filter(type_franchissement=type_franchissement)
        return qs

    @oa.extend_schema(request=None)
    @action(detail=True, methods=['post'])
    def acquitter(self, request, pk=None):
        alert = self.get_object()
        alert.acquittee = True
        alert.acquittee_par = request.user
        alert.acquittee_le = timezone.now()
        alert.save(update_fields=['acquittee', 'acquittee_par', 'acquittee_le'])
        return Response(self.get_serializer(alert).data)


def _iso(valeur):
    return valeur.isoformat() if valeur is not None else None


class InterventionPresenceView(oa.JsonOnlyMixin, APIView):
    """Revue chantier 26/10/2026 — ``GET interventions/<pk>/presence/`` :
    première entrée, dernière sortie, temps passé sur site, nombre de relevés
    et dernière position d'une intervention, calculés SERVEUR
    (``gps_tracking_service.presence_intervention``). Contrat :
    ``contract_samples/intervention_presence.json``.

    Même permission que le détail de l'intervention : ``ScopedPermission``
    (authentifié interne) + l'intervention doit être dans la portée de
    visibilité de l'appelant (``selectors.interventions_visibles``) et de sa
    société — sinon 404, jamais une fuite d'existence."""
    permission_classes = [ScopedPermission]

    @oa.extend_schema(responses={200: oa.OBJ, 404: oa.OBJ})
    def get(self, request, pk):
        from ..selectors import interventions_visibles
        if not 1 <= int(pk) <= oa.ID_MAX:  # id hors bigint : 404, jamais un 500 ORM
            raise NotFound('Intervention introuvable.')
        intervention = interventions_visibles(request.user).filter(pk=pk).first()
        if intervention is None:
            raise NotFound('Intervention introuvable.')
        presence = gps_tracking_service.presence_intervention(intervention)
        derniere = presence['derniere_position']
        return Response({
            'intervention': presence['intervention'],
            'premiere_entree': _iso(presence['premiere_entree']),
            'derniere_sortie': _iso(presence['derniere_sortie']),
            'duree_sur_site_min': presence['duree_sur_site_min'],
            'nb_positions': presence['nb_positions'],
            'source_debut': presence['source_debut'],
            'derniere_position': ({
                'lat': float(derniere['lat']),
                'lng': float(derniere['lng']),
                'captured_at': _iso(derniere['captured_at']),
            } if derniere else None),
        })
