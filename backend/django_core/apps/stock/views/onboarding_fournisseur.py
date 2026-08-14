"""NTP2P7 — Onboarding fournisseur : dossier + pièces légales.

Le dossier (``DossierOnboardingFournisseur``) et ses pièces
(``DocumentFournisseur``) sont exposés en CRUD scopé société ; le FICHIER lui
même transite par MinIO via ``apps.records.storage`` (aucun ``FileField``,
clé préfixée par la société) et n'est servi que par l'action ``telecharger``.

Le ``Fournisseur.statut`` n'est jamais touché ici : c'est le flag société
``AchatsParametres.onboarding_fournisseur_obligatoire`` qui décide si un
dossier non VALIDÉ bloque la création d'un bon de commande (garde posée dans
``views/bon_commande_fournisseur.py``).
"""
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .. import selectors
from ..models import DocumentFournisseur, DossierOnboardingFournisseur


class DocumentFournisseurSerializer(serializers.ModelSerializer):
    type_document_display = serializers.CharField(
        source='get_type_document_display', read_only=True, default=None)
    est_valide = serializers.SerializerMethodField()

    class Meta:
        model = DocumentFournisseur
        fields = [
            'id', 'dossier', 'type_document', 'type_document_display',
            'filename', 'mime', 'taille', 'reference', 'date_emission',
            'date_expiration', 'note', 'est_valide', 'date_creation',
        ]
        # `file_key` n'est JAMAIS sérialisé : la clé de stockage reste
        # serveur, le fichier se récupère par l'action `telecharger`.
        read_only_fields = ['filename', 'mime', 'taille', 'date_creation']

    def get_est_valide(self, obj):
        return obj.est_valide()


class DossierOnboardingFournisseurSerializer(serializers.ModelSerializer):
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    documents = DocumentFournisseurSerializer(many=True, read_only=True)
    progression = serializers.SerializerMethodField()

    class Meta:
        model = DossierOnboardingFournisseur
        fields = [
            'id', 'fournisseur', 'fournisseur_nom', 'statut', 'statut_display',
            'motif_rejet', 'valide_par', 'date_decision', 'note', 'documents',
            'progression', 'date_creation',
        ]
        # Le statut n'avance QUE par les actions (jamais écrit librement).
        read_only_fields = [
            'statut', 'motif_rejet', 'valide_par', 'date_decision',
            'date_creation',
        ]

    def get_progression(self, obj):
        return selectors.progression_onboarding(obj)


class DossierOnboardingFournisseurViewSet(CompanyScopedModelViewSet):
    """NTP2P7 — dossiers d'entrée en relation fournisseur.

    Lecture tout rôle, écriture responsable/admin. Société posée serveur ;
    le fournisseur est validé tenant. Filtres : ``?fournisseur=``, ``?statut=``.
    """
    queryset = DossierOnboardingFournisseur.objects.select_related(
        'fournisseur', 'valide_par').prefetch_related('documents').all()
    serializer_class = DossierOnboardingFournisseurSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        fournisseur = params.get('fournisseur')
        if fournisseur:
            qs = qs.filter(fournisseur_id=fournisseur)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _check_tenant(self, serializer):
        fournisseur = serializer.validated_data.get('fournisseur')
        company = self.request.user.company
        if fournisseur is not None and getattr(
                fournisseur, 'company_id', None) != getattr(company, 'id', None):
            raise ValidationError(
                {'fournisseur': 'Fournisseur inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        super().perform_update(serializer)

    @action(detail=True, methods=['post'], url_path='valider-dossier')
    def valider_dossier(self, request, pk=None):
        """NTP2P7 — valide (ou rejette) le dossier.

        Corps : ``{"valider": true|false, "motif_rejet": "…"}``. Une
        validation exige que TOUTES les pièces requises soient présentes et
        non expirées (400 explicite sinon)."""
        dossier = self.get_object()
        valider = request.data.get('valider')
        valider = True if valider is None else bool(valider)
        if valider:
            detail = selectors.progression_onboarding(dossier)
            if not detail['complet']:
                return Response(
                    {'detail': 'Dossier incomplet : pièces manquantes ou '
                               'expirées — '
                               f'{", ".join(detail["manquants"]) or "aucune"} '
                               f'({detail["progression_pct"]}%).',
                     'progression': detail},
                    status=status.HTTP_400_BAD_REQUEST)
            dossier.statut = DossierOnboardingFournisseur.Statut.VALIDE
            dossier.motif_rejet = ''
        else:
            dossier.statut = DossierOnboardingFournisseur.Statut.REJETE
            dossier.motif_rejet = (
                request.data.get('motif_rejet') or '').strip()
        dossier.valide_par = request.user
        dossier.date_decision = timezone.now()
        dossier.save(update_fields=['statut', 'motif_rejet', 'valide_par',
                                    'date_decision', 'updated_at'])
        return Response(self.get_serializer(dossier).data)

    @action(detail=True, methods=['get'])
    def progression(self, request, pk=None):
        """NTP2P29 — avancement du wizard (pièces reçues / requises)."""
        return Response(
            selectors.progression_onboarding(self.get_object()))


class DocumentFournisseurViewSet(CompanyScopedModelViewSet):
    """NTP2P7 — pièces légales d'un dossier d'onboarding.

    Le fichier se téléverse par ``POST .../{id}/televerser/`` (multipart) et se
    récupère par ``GET .../{id}/telecharger/`` — jamais par une URL publique.
    """
    queryset = DocumentFournisseur.objects.select_related('dossier').all()
    serializer_class = DocumentFournisseurSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'telecharger'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        dossier = params.get('dossier')
        if dossier:
            qs = qs.filter(dossier_id=dossier)
        type_document = params.get('type_document')
        if type_document:
            qs = qs.filter(type_document=type_document)
        return qs

    def _check_tenant(self, serializer):
        dossier = serializer.validated_data.get('dossier')
        company = self.request.user.company
        if dossier is not None and getattr(
                dossier, 'company_id', None) != getattr(company, 'id', None):
            raise ValidationError(
                {'dossier': 'Dossier inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company,
                        televerse_par=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        super().perform_update(serializer)

    @action(detail=True, methods=['post'])
    def televerser(self, request, pk=None):
        """NTP2P7 — attache le fichier de la pièce (MinIO, clé par société).

        Le dossier passe automatiquement à ``documents_recus`` dès la première
        pièce reçue (jamais à ``valide`` — la validation reste un acte humain).
        """
        from apps.records.storage import store_attachment

        document = self.get_object()
        fichier = request.FILES.get('file') or request.FILES.get('fichier')
        if fichier is None:
            return Response({'detail': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        infos, erreur = store_attachment(
            fichier, company=request.user.company)
        if erreur:
            return Response({'detail': erreur},
                            status=status.HTTP_400_BAD_REQUEST)
        document.file_key = infos['file_key']
        document.filename = infos['filename']
        document.mime = infos['mime']
        document.taille = infos['size']
        document.televerse_par = request.user
        document.save(update_fields=['file_key', 'filename', 'mime', 'taille',
                                     'televerse_par', 'updated_at'])
        dossier = document.dossier
        if dossier.statut == DossierOnboardingFournisseur.Statut.EN_ATTENTE:
            dossier.statut = (
                DossierOnboardingFournisseur.Statut.DOCUMENTS_RECUS)
            dossier.save(update_fields=['statut', 'updated_at'])
        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['get'])
    def telecharger(self, request, pk=None):
        """NTP2P7 — sert le fichier depuis MinIO (même origine, scopé société)."""
        from django.http import HttpResponse

        from apps.records.storage import fetch_attachment

        document = self.get_object()
        if not document.file_key:
            return Response({'detail': 'Aucun fichier attaché.'},
                            status=status.HTTP_404_NOT_FOUND)
        contenu = fetch_attachment(document.file_key)
        reponse = HttpResponse(
            contenu, content_type=document.mime or 'application/octet-stream')
        reponse['Content-Disposition'] = (
            f'attachment; filename="{document.filename or "document"}"')
        return reponse
