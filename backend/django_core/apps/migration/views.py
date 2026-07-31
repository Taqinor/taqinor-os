"""Viewsets DRF du groupe NTMIG.

Accès réservé au palier Administrateur/Directeur (``menu_tier == 'admin'`` —
les deux rôles système y sont mappés, le superuser aussi). ``company`` est
TOUJOURS forcée côté serveur (``CompanyScopedModelViewSet``) ; ``cree_par``
est posé côté serveur en création, jamais lu du corps de requête.
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from authentication.models import CustomUser
from core.viewsets import CompanyScopedModelViewSet

from . import services
from .models import LotMigration, ProjetMigration
from .serializers import (
    LotMigrationSerializer, ProjetMigrationSerializer,
    RapportReconciliationSerializer)


def _fichier_de(request):
    """Récupère le fichier téléversé (multipart) → (octets, nom)."""
    fichier = request.FILES.get('fichier') or request.FILES.get('file')
    if fichier is None:
        raise ValidationError({'fichier': 'Fichier source requis.'})
    return fichier.read(), fichier.name


class IsDirecteurOuAdmin(BasePermission):
    """Palier Administrateur OU Directeur uniquement.

    Les deux rôles système sont mappés au palier ``admin`` (``menu_tier``, qui
    renvoie déjà ``admin`` pour un superuser) ; le Responsable et
    l'Utilisateur limité sont exclus. Une migration réécrit des données
    métier en masse : ce n'est pas une action d'utilisateur courant.
    """

    message = 'Action réservée aux Administrateurs et Directeurs.'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated
            and getattr(user, 'menu_tier', None) == CustomUser.ROLE_ADMIN)


class ProjetMigrationViewSet(CompanyScopedModelViewSet):
    """Conteneur d'une migration : CRUD + clôture gardée (NTMIG5)."""

    queryset = ProjetMigration.objects.select_related('cree_par').all()
    serializer_class = ProjetMigrationSerializer
    permission_classes = [IsDirecteurOuAdmin]

    @action(detail=True, methods=['get'], url_path='rapport')
    def rapport(self, request, pk=None):
        """NTMIG19 — PV de migration en PDF (synthèse par lot).

        ``get_object()`` applique le queryset scopé société : un projet d'une
        autre société renvoie 404, jamais son PV.
        """
        from django.http import HttpResponse

        from .pdf_rapport import render_rapport_migration_pdf

        projet = self.get_object()
        pdf = render_rapport_migration_pdf(projet)
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="pv-migration-{projet.pk}.pdf"')
        return resp

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            cree_par=self.request.user)

    @action(detail=True, methods=['post'], url_path='terminer')
    def terminer(self, request, pk=None):
        """NTMIG5 — clôture gardée.

        400 + la liste des écarts bloquants (par lot) si un lot n'est pas
        réconcilié conforme ou dérogé ; le projet reste alors intact.
        """
        projet = self.get_object()
        try:
            services.terminer_projet(projet, user=request.user)
        except services.ReconcileBloque as exc:
            return Response(
                {'detail': str(exc), 'ecarts': exc.ecarts},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(ProjetMigrationSerializer(projet).data)


class LotMigrationViewSet(CompanyScopedModelViewSet):
    """Un lot par entité : analyse → chargement → réconciliation → clôture."""

    queryset = LotMigration.objects.select_related(
        'projet', 'derogation_par').all()
    serializer_class = LotMigrationSerializer
    permission_classes = [IsDirecteurOuAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs

    def perform_create(self, serializer):
        projet = serializer.validated_data['projet']
        # Le projet cité doit appartenir à la société de l'appelant : sans ce
        # contrôle, un lot d'une société pourrait se greffer sur le projet
        # d'une autre (le queryset scopé ne protège que la lecture).
        if projet.company_id != self.request.user.company_id:
            raise ValidationError({'projet': 'Projet introuvable.'})
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='analyser')
    def analyser(self, request, pk=None):
        """Analyse DRY-RUN du fichier source : rien n'est écrit en cible.

        Renvoie l'aperçu ``dataimport`` (mapping, comptages, et surtout les
        ``conflits``/``ecrasements_*`` : ce que le fichier toucherait sur des
        fiches déjà remplies) et pose les comptages source sur le lot.
        """
        lot = self.get_object()
        file_bytes, filename = _fichier_de(request)
        try:
            apercu = services.analyser_lot(
                lot, file_bytes, filename,
                mapping_name=request.data.get('mapping_name') or None)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(apercu)

    @action(detail=True, methods=['post'], url_path='charger')
    def charger(self, request, pk=None):
        """NTMIG15 — chargement délégué à ``dataimport``.

        ``external_system`` = ``migration:<source>`` (rejeu idempotent) et
        REMPLISSAGE SEUL : l'API n'expose délibérément aucun interrupteur
        d'écrasement — une migration n'efface jamais une valeur déjà saisie.
        """
        lot = self.get_object()
        file_bytes, filename = _fichier_de(request)
        try:
            result = services.charger_lot(
                lot, file_bytes, filename,
                mode=request.data.get('mode') or 'upsert',
                mapping_name=request.data.get('mapping_name') or None,
                user=request.user)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response({
            'lot': LotMigrationSerializer(lot).data, 'resultat': result})

    @action(detail=True, methods=['post'], url_path='charger-odoo')
    def charger_odoo(self, request, pk=None):
        """NTMIG9 — chargement via le connecteur Odoo JSON-2 (gated).

        Sans connecteur configuré : 400 explicite proposant l'import fichier.
        Le connecteur, quand il existe, est appelé en LECTURE SEULE ; aucune
        écriture n'est jamais faite côté Odoo (règle #1).
        """
        lot = self.get_object()
        try:
            services.charger_depuis_odoo_api(lot, params=request.data)
        except services.ConnecteurNonConfigure as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(LotMigrationSerializer(lot).data)

    @action(detail=True, methods=['post'], url_path='reconcilier')
    def reconcilier(self, request, pk=None):
        """Produit le rapport de réconciliation du lot (source vs cible)."""
        lot = self.get_object()
        rapport = services.reconcilier_lot(lot)
        return Response(RapportReconciliationSerializer(rapport).data)

    @action(detail=True, methods=['post'], url_path='deroger')
    def deroger(self, request, pk=None):
        """NTMIG5 — dérogation motivée : autorise la clôture d'un lot non
        conforme, en laissant une trace attribuée (qui/quand/pourquoi)."""
        lot = self.get_object()
        try:
            services.deroger_reconcile(
                lot, request.data.get('motif', ''), request.user)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(LotMigrationSerializer(lot).data)

    @action(detail=True, methods=['post'], url_path='terminer')
    def terminer(self, request, pk=None):
        """NTMIG5 — passe CE lot en ``reconcilie``, ou 400 + écarts."""
        lot = self.get_object()
        try:
            services.marquer_lot_termine(lot, user=request.user)
        except services.ReconcileBloque as exc:
            return Response(
                {'detail': str(exc), 'ecarts': exc.ecarts},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(LotMigrationSerializer(lot).data)
