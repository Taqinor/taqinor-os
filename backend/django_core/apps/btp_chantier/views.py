"""Vues du vertical BTP/EPC (Groupe NTCON) — scopées société (TenantMixin) +
lecture/écriture fine-grainée (``WriteScopedPermissionMixin``)."""
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    action, api_view, permission_classes, throttle_classes,
)
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from core.permissions import ScopedPermission, WriteScopedPermissionMixin
from core.viewsets import CompanyScopedModelViewSet

from . import selectors, services
from .models import (
    AvenantChantier, DecompteGeneral, DiffusionPlan, JournalChantier, RFI,
    ReserveChantier, VisaDocument,
)
from .serializers import (
    AvenantChantierPublicSerializer, AvenantChantierSerializer,
    DecompteGeneralSerializer, DiffusionPlanSerializer,
    JournalChantierSerializer, ReserveChantierSerializer, RFISerializer,
    SignatureBtpSerializer, VisaDocumentSerializer,
)


class BtpPublicLinkRateThrottle(SimpleRateThrottle):
    """Limite le débit des liens publics BTP par IP + jeton (cache-based) —
    pattern ``ventes.public_views.PublicLinkRateThrottle`` répliqué SANS
    import cross-app (jamais de dépendance externe)."""
    scope = 'btp_public_link'
    rate = '30/minute'

    def get_rate(self):
        # Repli sur ``self.rate`` : pas de réglage ``DEFAULT_THROTTLE_RATES``
        # nécessaire (contrairement à ``SimpleRateThrottle.get_rate`` par
        # défaut qui lève ``ImproperlyConfigured`` sans entrée settings).
        try:
            from django.conf import settings
            rates = (settings.REST_FRAMEWORK or {}).get(
                'DEFAULT_THROTTLE_RATES', {})
            return rates.get(self.scope) or self.rate
        except Exception:  # noqa: BLE001
            return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '') if view else ''
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope, 'ident': f'{ident}:{token}',
        }


def _chantier_model():
    """Classe ``installations.Installation`` résolue via la FK déjà déclarée
    sur ``JournalChantier`` — aucun import cross-app statique."""
    return JournalChantier._meta.get_field('chantier').related_model


def _client_ip(request):
    """IP client (preuve de signature) — pattern ``contrats.views._client_ip``."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '') or ''
    return ip[:45]


def _photos_pour(instance, phase=None):
    """Pièces jointes ``records.Attachment`` ciblant ``instance`` (app de
    fondation — import direct autorisé, pas de frontière cross-app)."""
    from apps.records.models import Attachment
    qs = Attachment.objects.filter(
        company=instance.company,
        content_type=ContentType.objects.get_for_model(instance.__class__),
        object_id=instance.pk,
    )
    if phase:
        qs = qs.filter(phase=phase)
    return qs


class ReserveChantierViewSet(
        WriteScopedPermissionMixin, CompanyScopedModelViewSet):
    """Réserves de chantier (punch-list géo-localisée sur plan) — NTCON1/2.

    Filtres liste : ``?lot=&statut=&gravite=&chantier=``. Actions
    ``lever/`` (photo « après » obligatoire + signature) et ``contester/``
    (réouvre une réserve levée avec motif) sont posées par ``services.py``.
    """
    queryset = ReserveChantier.objects.select_related(
        'chantier', 'responsable_leve', 'leve_par', 'created_by').all()
    serializer_class = ReserveChantierSerializer
    read_permission = 'btp_voir'
    write_permission = 'btp_gerer'

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        return selectors.reserves_filtrees(
            qs, lot=p.get('lot'), statut=p.get('statut'),
            gravite=p.get('gravite'), chantier_id=p.get('chantier'))

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)
        services.enregistrer_creation_reserve(
            serializer.instance, created_by=self.request.user)

    @action(detail=True, methods=['get'],
            permission_classes=[ScopedPermission])
    def photos(self, request, pk=None):
        """Photos avant/pendant/après de la réserve (``records.Attachment``)."""
        from apps.records.serializers import AttachmentSerializer
        reserve = self.get_object()
        return Response(
            AttachmentSerializer(_photos_pour(reserve), many=True).data)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def lever(self, request, pk=None):
        """NTCON2 — lève la réserve. Requiert une photo « après » existante
        (400 sinon) et un ``signataire_nom`` (loi 53-05, 400 sinon)."""
        reserve = self.get_object()
        signataire_nom = (request.data.get('signataire_nom') or '').strip()
        if not signataire_nom:
            return Response(
                {'detail': 'signataire_nom est requis (loi 53-05).'},
                status=status.HTTP_400_BAD_REQUEST)
        if not _photos_pour(reserve, phase='apres').exists():
            return Response(
                {'detail': (
                    'Une photo « après » (records.Attachment phase=apres) '
                    'est requise avant de lever la réserve.')},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            signature = services.lever_reserve(
                reserve, user=request.user, signature_nom=signataire_nom,
                ip_adresse=_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''))
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        reserve.refresh_from_db()
        return Response({
            'reserve': ReserveChantierSerializer(reserve).data,
            'signature': SignatureBtpSerializer(signature).data,
        })

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def contester(self, request, pk=None):
        """NTCON2 — réouvre une réserve levée (statut → contestee + motif)."""
        reserve = self.get_object()
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response(
                {'detail': 'motif est requis pour contester.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            services.contester_reserve(reserve, user=request.user, motif=motif)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        reserve.refresh_from_db()
        return Response(ReserveChantierSerializer(reserve).data)


class RFIViewSet(WriteScopedPermissionMixin, CompanyScopedModelViewSet):
    """RFI (Request For Information) — NTCON3.

    Filtres liste : ``?chantier=&statut=``. Triée par échéance dépassée en
    premier (``RFI.Meta.ordering``). Actions ``repondre/`` et ``clore/``.
    """
    queryset = RFI.objects.select_related(
        'chantier', 'pose_par', 'destinataire_user').prefetch_related(
            'reponses').all()
    serializer_class = RFISerializer
    read_permission = 'btp_voir'
    write_permission = 'btp_gerer'

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        return selectors.rfi_filtres(
            qs, chantier_id=p.get('chantier'), statut=p.get('statut'))

    def perform_create(self, serializer):
        rfi = services.creer_rfi(
            company=self.request.user.company,
            chantier=serializer.validated_data['chantier'],
            pose_par=self.request.user,
            delai_jours=serializer.validated_data.get('delai_jours', 5),
            question=serializer.validated_data['question'],
            destinataire_texte=serializer.validated_data.get(
                'destinataire_texte', ''),
            destinataire_user=serializer.validated_data.get(
                'destinataire_user'),
            impact_cout=serializer.validated_data.get('impact_cout', False),
            impact_delai_jours=serializer.validated_data.get(
                'impact_delai_jours'),
        )
        serializer.instance = rfi

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def repondre(self, request, pk=None):
        rfi = self.get_object()
        texte = (request.data.get('texte') or '').strip()
        if not texte:
            return Response(
                {'detail': 'texte est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            services.repondre_rfi(rfi, auteur=request.user, texte=texte)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        rfi.refresh_from_db()
        return Response(RFISerializer(rfi).data)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def clore(self, request, pk=None):
        rfi = self.get_object()
        try:
            services.clore_rfi(rfi, user=request.user)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        rfi.refresh_from_db()
        return Response(RFISerializer(rfi).data)


class VisaDocumentViewSet(
        WriteScopedPermissionMixin, CompanyScopedModelViewSet):
    """Visas de documents techniques — NTCON5 (soumission→observations→
    approbation, state machine stricte)."""
    queryset = VisaDocument.objects.select_related(
        'chantier', 'soumis_par', 'revu_par').all()
    serializer_class = VisaDocumentSerializer
    read_permission = 'btp_voir'
    write_permission = 'btp_gerer'

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        chantier_id = p.get('chantier')
        statut = p.get('statut')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        visa = services.soumettre_visa(
            company=self.request.user.company,
            chantier=serializer.validated_data['chantier'],
            document_ged_id=serializer.validated_data['document_ged_id'],
            soumis_par=self.request.user,
            type_visa=serializer.validated_data.get(
                'type_visa', VisaDocument.TypeVisa.AUTRE),
            delai_revue_jours=serializer.validated_data.get(
                'delai_revue_jours', 10),
        )
        serializer.instance = visa

    @action(detail=True, methods=['post'], url_path='soumettre-observations',
            permission_classes=[ScopedPermission])
    def soumettre_observations(self, request, pk=None):
        visa = self.get_object()
        observations = (request.data.get('observations') or '').strip()
        try:
            services.soumettre_observations_visa(
                visa, user=request.user, observations=observations)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        visa.refresh_from_db()
        return Response(VisaDocumentSerializer(visa).data)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def approuver(self, request, pk=None):
        visa = self.get_object()
        avec_observations = bool(request.data.get('avec_observations'))
        observations = (request.data.get('observations') or '').strip()
        try:
            services.approuver_visa(
                visa, user=request.user,
                avec_observations=avec_observations,
                observations=observations)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        visa.refresh_from_db()
        return Response(VisaDocumentSerializer(visa).data)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def refuser(self, request, pk=None):
        visa = self.get_object()
        observations = (request.data.get('observations') or '').strip()
        try:
            services.refuser_visa(
                visa, user=request.user, observations=observations)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        visa.refresh_from_db()
        return Response(VisaDocumentSerializer(visa).data)


class JournalChantierViewSet(
        WriteScopedPermissionMixin, CompanyScopedModelViewSet):
    """Journal de chantier quotidien — NTCON6.

    Filtres liste : ``?chantier=&du=&au=``. Une entrée par jour par chantier
    (contrainte unique en base — un doublon renvoie 400). Export PDF
    hebdomadaire/mensuel via ``export-pdf/``.
    """
    queryset = JournalChantier.objects.select_related(
        'chantier', 'redacteur').all()
    serializer_class = JournalChantierSerializer
    read_permission = 'btp_voir'
    write_permission = 'btp_gerer'

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        chantier_id = p.get('chantier')
        du = p.get('du')
        au = p.get('au')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        if du not in (None, ''):
            qs = qs.filter(date__gte=du)
        if au not in (None, ''):
            qs = qs.filter(date__lte=au)
        return qs

    def perform_create(self, serializer):
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError

        try:
            serializer.save(
                company=self.request.user.company,
                redacteur=self.request.user)
        except IntegrityError:
            raise ValidationError({
                'date': (
                    'Une entrée de journal existe déjà pour ce chantier à '
                    'cette date.'),
            })

    @action(detail=False, methods=['get'], url_path='export-pdf',
            permission_classes=[ScopedPermission])
    def export_pdf(self, request):
        """PDF interne (WeasyPrint) du journal sur ``?chantier=&du=&au=``."""
        from django.http import HttpResponse

        from .pdf import render_journal_chantier_pdf

        chantier_id = request.query_params.get('chantier')
        if not chantier_id:
            return Response(
                {'detail': 'chantier est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        chantier = get_object_or_404(
            _chantier_model(), pk=chantier_id, company=request.user.company)
        entries = self.get_queryset().filter(
            chantier_id=chantier_id).order_by('date')
        pdf_bytes = render_journal_chantier_pdf(chantier, entries)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="journal-chantier-{chantier_id}.pdf"')
        return response


# ── NTCON7/NTCON8 — Avenant de chantier ─────────────────────────────────────

class AvenantChantierViewSet(
        WriteScopedPermissionMixin, CompanyScopedModelViewSet):
    """Avenants de chantier (chiffrage + approbation) — NTCON7/NTCON8.

    Filtres liste : ``?chantier=&statut=``. Actions ``faire-approuver/``
    (génère/renouvelle le lien public client), ``approuver/``/``refuser/``
    (décision INTERNE, sans passer par le lien public).
    """
    queryset = AvenantChantier.objects.select_related(
        'chantier', 'cree_par', 'approuve_par').all()
    serializer_class = AvenantChantierSerializer
    read_permission = 'btp_voir'
    write_permission = 'btp_gerer'

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        chantier_id = p.get('chantier')
        statut = p.get('statut')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        avenant = services.creer_avenant_chantier(
            company=self.request.user.company,
            chantier=serializer.validated_data['chantier'],
            cree_par=self.request.user,
            description=serializer.validated_data['description'],
            montant_ht=serializer.validated_data['montant_ht'],
            impact_delai_jours=serializer.validated_data.get(
                'impact_delai_jours'),
            impact_budget=serializer.validated_data.get(
                'impact_budget', False),
            avenant_contrat_id=serializer.validated_data.get(
                'avenant_contrat_id'),
            lignes=serializer.validated_data.get('lignes'),
        )
        serializer.instance = avenant

    @action(detail=True, methods=['post'], url_path='faire-approuver',
            permission_classes=[ScopedPermission])
    def faire_approuver(self, request, pk=None):
        """NTCON8 — passe en « soumis au client » + (re)génère le lien
        public tokenisé (loi 53-05)."""
        avenant = self.get_object()
        try:
            services.soumettre_client_avenant(avenant, user=request.user)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        avenant.refresh_from_db()
        return Response({
            'avenant': AvenantChantierSerializer(avenant).data,
            'lien_public': f'/btp/avenants/public/{avenant.token}/',
        })

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def approuver(self, request, pk=None):
        """Décision INTERNE (sans lien public) — même service que NTCON8."""
        avenant = self.get_object()
        try:
            services.approuver_avenant(avenant, user=request.user)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        avenant.refresh_from_db()
        return Response(AvenantChantierSerializer(avenant).data)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def refuser(self, request, pk=None):
        avenant = self.get_object()
        motif = (request.data.get('motif') or '').strip()
        try:
            services.refuser_avenant(avenant, user=request.user, motif=motif)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        avenant.refresh_from_db()
        return Response(AvenantChantierSerializer(avenant).data)


def _client_ip_public(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '') or ''
    return ip[:45]


def _resolve_avenant_token(token):
    """NTCON8 — résout un avenant par jeton public : jeton inconnu OU
    expiré → 404 (jamais de fuite distinguant les deux cas)."""
    avenant = AvenantChantier.objects.filter(token=token).first()
    if avenant is None:
        return None
    if avenant.token_expires_at and avenant.token_expires_at < timezone.now():
        return None
    return avenant


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([BtpPublicLinkRateThrottle])
def avenant_public_detail(request, token):
    """NTCON8 — chiffrage de l'avenant en lecture publique (lien tokenisé,
    jamais de coût interne)."""
    avenant = _resolve_avenant_token(token)
    if avenant is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(AvenantChantierPublicSerializer(avenant).data)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([BtpPublicLinkRateThrottle])
def avenant_public_approuver(request, token):
    """NTCON8 — approbation CLIENT (signature typée loi 53-05, IP/UA
    serveur). Idempotent : un avenant déjà décidé renvoie 400."""
    avenant = _resolve_avenant_token(token)
    if avenant is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    signataire_nom = (request.data.get('signataire_nom') or '').strip()
    if not signataire_nom:
        return Response(
            {'detail': 'signataire_nom est requis (loi 53-05).'},
            status=status.HTTP_400_BAD_REQUEST)
    try:
        services.approuver_avenant_public(
            avenant, signataire_nom=signataire_nom,
            ip_adresse=_client_ip_public(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''))
    except services.TransitionInvalide as exc:
        return Response(
            {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    avenant.refresh_from_db()
    return Response(AvenantChantierPublicSerializer(avenant).data)


# ── NTCON9/NTCON10 — DGD (Décompte Général et Définitif) ───────────────────

class DecompteGeneralViewSet(
        WriteScopedPermissionMixin, CompanyScopedModelViewSet):
    """DGD (Décompte Général et Définitif) — NTCON9/NTCON10.

    Un DGD ``definitif`` est VERROUILLÉ (403 sur toute écriture) sauf via
    l'action ``deverrouiller/`` (admin only, journalisée).
    """
    queryset = DecompteGeneral.objects.select_related(
        'chantier', 'cree_par', 'finalise_par').all()
    serializer_class = DecompteGeneralSerializer
    read_permission = 'btp_voir'
    write_permission = 'btp_gerer'

    def get_queryset(self):
        qs = super().get_queryset()
        chantier_id = self.request.query_params.get('chantier')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    def perform_create(self, serializer):
        dgd = services.creer_decompte_general(
            company=self.request.user.company,
            chantier=serializer.validated_data['chantier'],
            cree_par=self.request.user,
            montant_marche_initial_ht=serializer.validated_data.get(
                'montant_marche_initial_ht', 0),
            situations_incluses=serializer.validated_data.get(
                'situations_incluses'),
            retenue_garantie_id=serializer.validated_data.get(
                'retenue_garantie_id'),
        )
        serializer.instance = dgd

    def _refuser_si_verrouille(self, instance):
        if instance.statut == DecompteGeneral.Statut.DEFINITIF:
            raise PermissionDenied(
                f'DGD {instance.reference} : définitif — verrouillé en '
                'lecture seule (déverrouillage admin requis).')

    def perform_update(self, serializer):
        self._refuser_si_verrouille(self.get_object())
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._refuser_si_verrouille(instance)
        super().perform_destroy(instance)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def notifier(self, request, pk=None):
        dgd = self.get_object()
        try:
            services.notifier_dgd(dgd, user=request.user)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        dgd.refresh_from_db()
        return Response(DecompteGeneralSerializer(dgd).data)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def contester(self, request, pk=None):
        dgd = self.get_object()
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response(
                {'detail': 'motif est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            services.contester_dgd(
                dgd, user=request.user, motif=motif,
                montant_conteste=request.data.get('montant_conteste'))
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        dgd.refresh_from_db()
        return Response(DecompteGeneralSerializer(dgd).data)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def finaliser(self, request, pk=None):
        dgd = self.get_object()
        try:
            services.finaliser_dgd(dgd, user=request.user)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        dgd.refresh_from_db()
        return Response(DecompteGeneralSerializer(dgd).data)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def deverrouiller(self, request, pk=None):
        """NTCON10 — déverrouillage ADMIN ONLY, journalisé."""
        if not getattr(request.user, 'is_admin_role', False):
            return Response(
                {'detail': 'Réservé aux administrateurs.'},
                status=status.HTTP_403_FORBIDDEN)
        dgd = self.get_object()
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response(
                {'detail': 'motif est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            services.deverrouiller_dgd(dgd, user=request.user, motif=motif)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        dgd.refresh_from_db()
        return Response(DecompteGeneralSerializer(dgd).data)

    @action(detail=True, methods=['get'], url_path='export-pdf',
            permission_classes=[ScopedPermission])
    def export_pdf(self, request, pk=None):
        from django.http import HttpResponse

        from .pdf import render_dgd_pdf

        dgd = self.get_object()
        pdf_bytes = render_dgd_pdf(dgd)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="dgd-{dgd.reference}.pdf"')
        return response


# ── NTCON11 — Comparatif déboursé sec vs facturé (admin/responsable only) ──

class ChantierDebourseVsFactureView(APIView):
    """NTCON11 — ``chantiers/<id>/debourse-vs-facture/``. Admin/responsable
    only : ``read_permission`` posé au niveau ``btp_gerer`` (exigé même en
    LECTURE — jamais un coût dans une sortie client)."""
    permission_classes = [ScopedPermission]
    read_permission = 'btp_gerer'
    write_permission = 'btp_gerer'

    def get(self, request, chantier_id):
        chantier = get_object_or_404(
            _chantier_model(), pk=chantier_id, company=request.user.company)
        return Response(selectors.debourse_sec_vs_facture(chantier))


# ── NTCON12/NTCON13 — Diffusion contrôlée de plans ──────────────────────────

class DiffusionPlanViewSet(
        WriteScopedPermissionMixin, CompanyScopedModelViewSet):
    """Diffusion contrôlée de plans — NTCON12/NTCON13.

    Filtres liste : ``?chantier=&document=``. Action ``diffuser/`` crée le
    partage GED externe (si destinataires externes) + notifie les internes.
    """
    queryset = DiffusionPlan.objects.select_related('chantier', 'cree_par').all()
    serializer_class = DiffusionPlanSerializer
    read_permission = 'btp_voir'
    write_permission = 'btp_gerer'

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        chantier_id = p.get('chantier')
        document_id = p.get('document')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        if document_id not in (None, ''):
            qs = qs.filter(document_ged_id=document_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, cree_par=self.request.user)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def diffuser(self, request, pk=None):
        diffusion = self.get_object()
        services.diffuser_plan(diffusion, user=request.user)
        diffusion.refresh_from_db()
        return Response(DiffusionPlanSerializer(diffusion).data)

    @action(detail=False, methods=['get'], url_path='plans-perimes',
            permission_classes=[ScopedPermission])
    def plans_perimes(self, request):
        chantier_id = request.query_params.get('chantier')
        if not chantier_id:
            return Response(
                {'detail': 'chantier est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        chantier = get_object_or_404(
            _chantier_model(), pk=chantier_id, company=request.user.company)
        return Response(selectors.plans_perimes_sur_chantier(chantier))


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([BtpPublicLinkRateThrottle])
def diffusion_public_ouvrir(request, token):
    """NTCON12 — accusé de réception : marque ``?destinataire=`` (email ou
    ID utilisateur) comme ayant OUVERT cette diffusion. 404 si jeton inconnu
    (jamais de fuite)."""
    diffusion = DiffusionPlan.objects.filter(token=token).first()
    if diffusion is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    destinataire = request.query_params.get('destinataire', '') or 'anonyme'
    services.marquer_diffusion_lue(diffusion, cle_destinataire=destinataire)
    return Response({
        'document_ged_id': diffusion.document_ged_id,
        'version_diffusee': diffusion.version_diffusee,
    })
