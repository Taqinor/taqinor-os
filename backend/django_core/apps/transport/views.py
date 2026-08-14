"""Vues (ViewSets) de l'app `apps.transport` — toutes scopées société via
`core.viewsets.CompanyScopedModelViewSet` (jamais un `ModelViewSet` nu,
SCA4)."""
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet
from apps.records.views import ChatterViewSetMixin

from . import services
from .models import (
    CoutFretReel, EtapeTransport, LigneOrdreTransport, LitigeTransport,
    OrdreTransport, ReserveReception,
)
from .serializers import (
    CoutFretReelSerializer, EtapeTransportSerializer,
    LigneOrdreTransportSerializer, LitigeTransportSerializer,
    OrdreTransportSerializer, ReserveReceptionSerializer,
)


def _check_same_company(request, **fields):
    """Refuse (400) toute FK référençant un objet d'une AUTRE société — une
    `PrimaryKeyRelatedField` DRF n'est, par défaut, PAS scopée société ; sans
    ce garde un id valide d'une autre société serait accepté (IDOR)."""
    company = request.user.company
    cid = getattr(company, 'id', None)
    for name, obj in fields.items():
        if obj is not None and getattr(obj, 'company_id', None) != cid:
            raise ValidationError({name: 'Référence inconnue pour cette société.'})


class OrdreTransportViewSet(ChatterViewSetMixin, CompanyScopedModelViewSet):
    """NTLOG1 — ordre de transport. Filtrable par `?statut=`. `numero` posé
    côté serveur à la création (`services.attribuer_numero`, anti-collision,
    ARC6). Le chatter générique (`chatter/historique`/`chatter/noter`,
    ``ChatterViewSetMixin``) porte l'historique NTLOG8 (statut de l'ordre ET
    de ses étapes — voir ``services.log_activite_ordre``)."""

    queryset = OrdreTransport.objects.select_related(
        'created_by').prefetch_related('lignes', 'etapes').all()
    serializer_class = OrdreTransportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        conducteur = data.get('conducteur')
        erreur = services.valider_mode_transport_champs(
            data.get('mode_transport', OrdreTransport.ModeTransport.AFFRETEMENT),
            flotte_actif_id=data.get('flotte_actif_id'),
            conducteur_id=getattr(conducteur, 'id', None),
            installations_transporteur_id=data.get('installations_transporteur_id'),
        )
        if erreur:
            raise ValidationError({'mode_transport': erreur})
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)
        services.attribuer_numero(serializer.instance)

    def perform_update(self, serializer):
        instance = serializer.instance
        data = serializer.validated_data
        mode_transport = data.get('mode_transport', instance.mode_transport)
        conducteur = data.get('conducteur', instance.conducteur)
        flotte_actif_id = data.get('flotte_actif_id', instance.flotte_actif_id)
        installations_transporteur_id = data.get(
            'installations_transporteur_id',
            instance.installations_transporteur_id)
        erreur = services.valider_mode_transport_champs(
            mode_transport,
            flotte_actif_id=flotte_actif_id,
            conducteur_id=getattr(conducteur, 'id', None),
            installations_transporteur_id=installations_transporteur_id,
        )
        if erreur:
            raise ValidationError({'mode_transport': erreur})
        super().perform_update(serializer)

    # ── NTLOG3 — lecture imbriquée des étapes ────────────────────────────
    @action(detail=True, methods=['get'], url_path='etapes')
    def etapes_action(self, request, pk=None):
        ordre = self.get_object()
        return Response(
            EtapeTransportSerializer(ordre.etapes.all(), many=True).data)

    # ── NTLOG7 — comparateur de coûts d'affrètement ──────────────────────
    @action(detail=True, methods=['get'], url_path='comparer-transporteurs')
    def comparer_transporteurs(self, request, pk=None):
        ordre = self.get_object()
        from . import selectors
        return Response(
            selectors.comparer_transporteurs(
                ordre.id, company=request.user.company))


class LigneOrdreTransportViewSet(CompanyScopedModelViewSet):
    """NTLOG2 — marchandises d'un ordre. Filtrable par `?ordre=`."""

    queryset = LigneOrdreTransport.objects.select_related('ordre').all()
    serializer_class = LigneOrdreTransportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ordre = self.request.query_params.get('ordre')
        if ordre:
            qs = qs.filter(ordre_id=ordre)
        return qs

    def perform_create(self, serializer):
        _check_same_company(
            self.request, ordre=serializer.validated_data.get('ordre'))
        serializer.save(company=self.request.user.company)


class EtapeTransportViewSet(CompanyScopedModelViewSet):
    """NTLOG3 — étapes enlèvement/transit/livraison. Filtrable par
    `?ordre=`. Toute écriture de `statut_etape` déclenche l'avancement
    automatique du statut de l'ordre parent
    (`services.apres_changement_statut_etape`)."""

    queryset = EtapeTransport.objects.select_related('ordre').all()
    serializer_class = EtapeTransportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ordre = self.request.query_params.get('ordre')
        if ordre:
            qs = qs.filter(ordre_id=ordre)
        return qs

    def perform_create(self, serializer):
        _check_same_company(
            self.request, ordre=serializer.validated_data.get('ordre'))
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        ancien_statut = serializer.instance.statut_etape
        super().perform_update(serializer)
        services.apres_changement_statut_etape(
            serializer.instance, ancien_statut, user=self.request.user)

    # ── NTLOG9 — preuve de livraison (POD), réutilise records.Attachment ──
    @action(detail=True, methods=['post'], url_path='livrer')
    def livrer(self, request, pk=None):
        """Exige AU MOINS une pièce jointe (`records.Attachment`, photo ou
        signature) déjà déposée sur cette étape avant de la clôturer
        « fait » — sinon 400."""
        etape = self.get_object()
        from apps.records.models import Attachment
        ct = ContentType.objects.get_for_model(EtapeTransport)
        a_une_piece = Attachment.objects.filter(
            content_type=ct, object_id=etape.id).exists()
        if not a_une_piece:
            return Response(
                {'detail': (
                    'Photo ou signature requise avant de clôturer la '
                    'livraison.')},
                status=status.HTTP_400_BAD_REQUEST)
        ancien_statut = etape.statut_etape
        etape.statut_etape = EtapeTransport.StatutEtape.FAIT
        etape.save(update_fields=['statut_etape'])
        services.apres_changement_statut_etape(
            etape, ancien_statut, user=request.user)
        return Response(EtapeTransportSerializer(etape).data)


class CoutFretReelViewSet(CompanyScopedModelViewSet):
    """NTLOG16 — coûts de fret réels. Filtrable par `?ordre_transport=`."""

    queryset = CoutFretReel.objects.select_related('ordre_transport').all()
    serializer_class = CoutFretReelSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ordre = self.request.query_params.get('ordre_transport')
        if ordre:
            qs = qs.filter(ordre_transport_id=ordre)
        return qs

    def perform_create(self, serializer):
        _check_same_company(
            self.request,
            ordre_transport=serializer.validated_data.get('ordre_transport'))
        serializer.save(company=self.request.user.company)


class LitigeTransportViewSet(CompanyScopedModelViewSet):
    """NTLOG17 — litiges transport, machine à états calquée sur
    `litiges.Reclamation` (LITIGE2) : ouvert → en_traitement → résolu, ou
    rejeté depuis ouvert/en_traitement. Transition illégale → 400."""

    queryset = LitigeTransport.objects.select_related(
        'ordre_transport', 'created_by').all()
    serializer_class = LitigeTransportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ordre = self.request.query_params.get('ordre_transport')
        if ordre:
            qs = qs.filter(ordre_transport_id=ordre)
        return qs

    def perform_create(self, serializer):
        _check_same_company(
            self.request,
            ordre_transport=serializer.validated_data.get('ordre_transport'))
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    def _transition(self, request, *, allowed_from, target):
        litige = self.get_object()
        if litige.statut not in allowed_from:
            return Response(
                {'statut': (
                    f"Transition invalide depuis « "
                    f"{litige.get_statut_display()} » vers « "
                    f"{LitigeTransport.Statut(target).label} ».")},
                status=status.HTTP_400_BAD_REQUEST)
        ancien = litige.statut
        litige.statut = target
        litige.save(update_fields=['statut'])
        services.log_activite_ordre(
            litige.ordre_transport, user=request.user,
            field='litige_statut', field_label=f'Litige #{litige.id}',
            old_value=ancien, new_value=target)
        return Response(LitigeTransportSerializer(litige).data)

    @action(detail=True, methods=['post'], url_path='prendre-en-charge')
    def prendre_en_charge(self, request, pk=None):
        return self._transition(
            request, allowed_from={LitigeTransport.Statut.OUVERT},
            target=LitigeTransport.Statut.EN_TRAITEMENT)

    @action(detail=True, methods=['post'], url_path='resoudre')
    def resoudre(self, request, pk=None):
        return self._transition(
            request, allowed_from={LitigeTransport.Statut.EN_TRAITEMENT},
            target=LitigeTransport.Statut.RESOLU)

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        return self._transition(
            request,
            allowed_from={
                LitigeTransport.Statut.OUVERT,
                LitigeTransport.Statut.EN_TRAITEMENT,
            },
            target=LitigeTransport.Statut.REJETE)

    # ── NTLOG19 — réclamation transporteur chiffrée (PDF) ────────────────
    @action(detail=True, methods=['post'], url_path='reclamer-transporteur')
    def reclamer_transporteur(self, request, pk=None):
        litige = self.get_object()
        from . import selectors
        from .reclamation_pdf import render_reclamation_transporteur_pdf

        destinataire = selectors.transporteur_nom_pour_ordre(
            litige.ordre_transport)
        pdf_bytes = render_reclamation_transporteur_pdf(litige)
        services.envoyer_reclamation_transporteur(
            litige, destinataire=destinataire)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        nom_fichier = (
            f'reclamation-transporteur-'
            f'{litige.ordre_transport.numero or litige.id}.pdf')
        resp['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
        return resp


class ReserveReceptionViewSet(CompanyScopedModelViewSet):
    """NTLOG18 — réserve à réception, capturable depuis l'écran POD. Sa
    création fait automatiquement naître un `LitigeTransport` ouvert
    (`services.creer_litige_depuis_reserve`)."""

    queryset = ReserveReception.objects.select_related('etape', 'litige').all()
    serializer_class = ReserveReceptionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        etape = self.request.query_params.get('etape')
        if etape:
            qs = qs.filter(etape_id=etape)
        return qs

    def perform_create(self, serializer):
        _check_same_company(
            self.request, etape=serializer.validated_data.get('etape'))
        serializer.save(company=self.request.user.company)
        services.creer_litige_depuis_reserve(
            serializer.instance, user=self.request.user)
