"""Vues (ViewSets) de l'app `apps.transport` — toutes scopées société via
`core.viewsets.CompanyScopedModelViewSet` (jamais un `ModelViewSet` nu,
SCA4)."""
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from core.permissions import ScopedPermission
from core.viewsets import CompanyScopedModelViewSet
from apps.records.views import ChatterViewSetMixin

from . import services
from .models import (
    CoutFretReel, EtapeTransport, FacteurEmissionCO2, LigneOrdreTransport,
    LitigeTransport, OrdreTransport, ReserveReception,
)
from .serializers import (
    CoutFretReelSerializer, EtapeTransportSerializer,
    FacteurEmissionCO2Serializer, LigneOrdreTransportSerializer,
    LitigeTransportSerializer, OrdreTransportSerializer,
    ReserveReceptionSerializer,
)


class _ExportFormatContentNegotiation(DefaultContentNegotiation):
    """NTLOG27/31 — sur les actions d'export, ``?format=`` désigne le format
    D'EXPORT (xlsx/pdf/csv), PAS le renderer DRF — motif
    ``apps.douane.views._ExportFormatContentNegotiation`` (elle-même motif
    ``apps.compta.views._BankFormatContentNegotiation``). Sans cette
    surcharge, DRF traite ``?format=xlsx``/``?format=pdf`` comme un override
    de renderer (``URL_FORMAT_OVERRIDE``) : aucun renderer enregistré ne
    porte ces formats → ``Http404`` AVANT même d'exécuter la vue. On neutralise
    donc l'override par query param et on négocie toujours sur le renderer
    JSON (la vue renvoie elle-même une ``HttpResponse``/``build_xlsx_response``
    manuelle, jamais via ce renderer)."""

    def select_renderer(self, request, renderers, format_suffix=None):
        for renderer in renderers:
            if renderer.format == 'json':
                return renderer, renderer.media_type
        return renderers[0], renderers[0].media_type


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
    # YRBAC4 — gardes DÉCLARÉES sur les 3 lectures de ce viewset.
    # ``ScopedPermission`` (GET → ``read_permission``, ici None) exprime le
    # tier réel « authentifié INTERNE de la société », identique au défaut de
    # classe : consultation d'étapes, comparatif transporteurs et bilan CO2
    # sont des lectures d'exploitation ouvertes à tout le personnel interne.
    # Ni ce viewset ni ses bases (ChatterViewSetMixin /
    # CompanyScopedModelViewSet / TenantMixin) ne définissent de
    # ``get_permissions`` — les déclarations ne sont donc pas neutralisées.
    @action(detail=True, methods=['get'], url_path='etapes',
            permission_classes=[ScopedPermission])
    def etapes_action(self, request, pk=None):
        ordre = self.get_object()
        return Response(
            EtapeTransportSerializer(ordre.etapes.all(), many=True).data)

    # ── NTLOG7 — comparateur de coûts d'affrètement ──────────────────────
    @action(detail=True, methods=['get'], url_path='comparer-transporteurs',
            permission_classes=[ScopedPermission])
    def comparer_transporteurs(self, request, pk=None):
        ordre = self.get_object()
        from . import selectors
        return Response(
            selectors.comparer_transporteurs(
                ordre.id, company=request.user.company))

    # ── NTLOG20 — estimation CO2 (affichée sur le détail de l'ordre) ─────
    @action(detail=True, methods=['get'], url_path='co2',
            permission_classes=[ScopedPermission])
    def co2(self, request, pk=None):
        ordre = self.get_object()
        from . import selectors
        return Response(
            selectors.estimer_co2_transport(
                ordre.id, company=request.user.company))

    # ── NTLOG24 — tableau de bord logistique ──────────────────────────────
    # PACT7 — sans cette déclaration, le schéma OpenAPI publierait cet
    # agrégat avec `OrdreTransportSerializer` (le `serializer_class` de ce
    # ViewSet) alors qu'il renvoie une forme entièrement différente (motif
    # `apps.flotte.views.FlotteViewSet.tableau_bord`).
    @extend_schema(responses=inline_serializer('TransportTableauBordLogistique', {
        'periode': drf_serializers.CharField(allow_null=True),
        'nb_ordres': drf_serializers.IntegerField(),
        'nb_livres': drf_serializers.IntegerField(),
        'total_fret_ht': drf_serializers.DecimalField(max_digits=14, decimal_places=2),
        'poids_livre_kg': drf_serializers.DecimalField(max_digits=12, decimal_places=2),
        'cout_par_kg_transporte': drf_serializers.DecimalField(
            max_digits=16, decimal_places=6, allow_null=True),
        'taux_service_pct': drf_serializers.FloatField(allow_null=True),
        'litiges_ouverts_count': drf_serializers.IntegerField(),
        'litiges_ouverts_montant_conteste': drf_serializers.DecimalField(
            max_digits=14, decimal_places=2),
        'repartition_mode_transport': drf_serializers.DictField(
            child=drf_serializers.IntegerField()),
        'co2_total_estime_kg': drf_serializers.DecimalField(
            max_digits=16, decimal_places=3),
    }))
    @action(detail=False, methods=['get'], url_path='tableau-bord-logistique',
            permission_classes=[ScopedPermission])
    def tableau_bord_logistique(self, request):
        """NTLOG24 — cartes KPI + répartition transporteurs du dashboard
        logistique. Lecture seule (tout rôle interne), filtrable
        ``?periode=YYYY-MM``."""
        from . import selectors
        return Response(
            selectors.tableau_bord_logistique(
                request.user.company,
                periode=request.query_params.get('periode')))


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
    # YRBAC4 — garde DÉCLARÉE, RESSERREMENT réel : ce viewset ne pose ni
    # ``read_permission`` ni ``write_permission``, donc le défaut
    # ``ScopedPermission`` se réduisait à « authentifié interne suffit » —
    # tout compte pouvait acter une livraison, ce qui fait avancer le statut
    # de l'ordre parent (``services.apres_changement_statut_etape``). Acter
    # une preuve de livraison exige désormais un porteur de rôle. Aucun
    # ``get_permissions`` sur ce viewset ni ses bases → garde effective.
    @action(detail=True, methods=['post'], url_path='livrer',
            permission_classes=[IsResponsableOrAdmin])
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

    # ── NTLOG27 — export comptable des coûts de fret ─────────────────────
    # YRBAC4 — garde DÉCLARÉE. GET = méthode sûre, ouverte à tout utilisateur
    # authentifié de la société (motif `DossierExportViewSet.export`,
    # NTLOG47 — rapprochement comptable, pas une décision qui engage
    # l'entreprise).
    @action(detail=False, methods=['get'], url_path='export',
            permission_classes=[ScopedPermission],
            content_negotiation_class=_ExportFormatContentNegotiation)
    def export(self, request):
        """NTLOG27 — ``couts-fret/export/?periode=YYYY-MM`` génère un .xlsx
        listant les coûts de fret par ordre/BCF/période (réutilise le
        pattern ``export=xlsx`` de ``apps.douane.views``/``reporting``) pour
        rapprochement comptable manuel avant intégration éventuelle dans
        ``compta``. Filtre par ``created_at`` — EXACTEMENT le même filtre que
        `selectors.tableau_bord_logistique` (NTLOG24) : le total exporté ici
        correspond au dernier chiffre près au total affiché sur son
        dashboard pour la même période (critère d'acceptation)."""
        from . import selectors

        periode = request.query_params.get('periode')
        qs = selectors._filtre_periode(
            self.get_queryset().order_by('ordre_transport_id', 'id'),
            periode)

        headers = [
            'Ordre de transport', 'BCF (stock.BonCommandeFournisseur)',
            'Type de coût', 'Montant HT', 'Devise', 'Date',
        ]
        rows = [
            [
                c.ordre_transport.numero or f'#{c.ordre_transport_id}',
                c.stock_boncommandefournisseur_id or '',
                c.get_type_cout_display(),
                c.montant_ht,
                c.devise,
                c.created_at.date().isoformat(),
            ]
            for c in qs
        ]

        from apps.records.xlsx import build_xlsx_response
        return build_xlsx_response(
            'couts-fret-transport.xlsx', headers, rows,
            sheet_title='Coûts de fret')


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

    # YRBAC4 — gardes DÉCLARÉES sur les 4 écritures de ce viewset, et
    # RESSERREMENT réel (même motif que ``EtapeTransportViewSet.livrer``) :
    # sans ``write_permission``, tout compte authentifié pouvait faire
    # avancer la machine à états d'un litige (prise en charge, résolution,
    # REJET) ou émettre une réclamation transporteur. Ces décisions engagent
    # la société : elles exigent désormais un porteur de rôle. Aucun
    # ``get_permissions`` sur ce viewset ni ses bases → gardes effectives.
    @action(detail=True, methods=['post'], url_path='prendre-en-charge',
            permission_classes=[IsResponsableOrAdmin])
    def prendre_en_charge(self, request, pk=None):
        return self._transition(
            request, allowed_from={LitigeTransport.Statut.OUVERT},
            target=LitigeTransport.Statut.EN_TRAITEMENT)

    @action(detail=True, methods=['post'], url_path='resoudre',
            permission_classes=[IsResponsableOrAdmin])
    def resoudre(self, request, pk=None):
        return self._transition(
            request, allowed_from={LitigeTransport.Statut.EN_TRAITEMENT},
            target=LitigeTransport.Statut.RESOLU)

    @action(detail=True, methods=['post'], url_path='rejeter',
            permission_classes=[IsResponsableOrAdmin])
    def rejeter(self, request, pk=None):
        return self._transition(
            request,
            allowed_from={
                LitigeTransport.Statut.OUVERT,
                LitigeTransport.Statut.EN_TRAITEMENT,
            },
            target=LitigeTransport.Statut.REJETE)

    # ── NTLOG19 — réclamation transporteur chiffrée (PDF) ────────────────
    @action(detail=True, methods=['post'], url_path='reclamer-transporteur',
            permission_classes=[IsResponsableOrAdmin])
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


class FacteurEmissionCO2ViewSet(CompanyScopedModelViewSet):
    """NTLOG20 — facteur d'émission CO2, éditable en Paramètres."""

    queryset = FacteurEmissionCO2.objects.all()
    serializer_class = FacteurEmissionCO2Serializer
