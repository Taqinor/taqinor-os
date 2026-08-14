"""Groupe NTWMS — vues de la couche ENTREPÔT (vagues de prélèvement, unités
logistiques, quais, expéditions, comptage tournant).

Toutes les vues héritent de ``CompanyScopedModelViewSet`` (scoping société +
``perform_create`` côté serveur) — jamais un ``ModelViewSet`` nu.
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet
from authentication.permissions import (
    IsAnyRole, IsAdminRole, IsResponsableOrAdmin,
)

from ..models_wms import UniteLogistique, VaguePicking
from ..serializers_wms import UniteLogistiqueSerializer, VaguePickingSerializer

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class VaguePickingViewSet(CompanyScopedModelViewSet):
    """NTWMS4 — vagues de prélèvement MULTI-SOURCE.

    Lecture tout rôle (le magasinier doit voir sa tournée) ; création/lancement
    responsable ou admin ; suppression admin. La création se fait par
    ``POST vagues-picking/`` avec ``{besoins: [...], installations: [...]}`` —
    la référence est posée côté serveur.
    """
    queryset = VaguePicking.objects.prefetch_related(
        'lignes__produit', 'lignes__bin', 'lignes__lot',
    ).select_related('cree_par').all()
    serializer_class = VaguePickingSerializer
    ordering = ['-created_at']

    def get_permissions(self):
        # `get_permissions` prime sur le `permission_classes` d'une @action :
        # chaque action est donc listée explicitement ici.
        if self.action in READ_ACTIONS + ['lignes']:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + ['lancer', 'prelever']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        """Crée la vague à partir des besoins fournis (multi-source) — le
        service pose la référence, résout les casiers et TRIE par parcours."""
        from ..services import creer_vague_depuis_besoins
        try:
            vague = creer_vague_depuis_besoins(
                company=request.user.company, user=request.user,
                besoins=request.data.get('besoins'),
                installations=request.data.get('installations'),
                note=request.data.get('note') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(vague).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='lancer')
    def lancer(self, request, pk=None):
        """Passe la vague en LANCÉE (idempotent)."""
        from ..services import lancer_vague
        vague = self.get_object()
        try:
            lancer_vague(vague)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        vague.refresh_from_db()
        return Response(self.get_serializer(vague).data)

    @action(detail=True, methods=['post'],
            url_path=r'lignes/(?P<ligne_id>[0-9]+)/prelever')
    def prelever(self, request, pk=None, ligne_id=None):
        """Enregistre un prélèvement sur une ligne de CETTE vague
        (``{quantite: n}``). Refuse un dépassement du reste à prélever et
        clôture la vague quand tout est servi."""
        from ..services import prelever_ligne_picking
        vague = self.get_object()
        ligne = vague.lignes.filter(id=ligne_id).first()
        if ligne is None:
            return Response({'detail': 'Ligne introuvable dans cette vague.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            prelever_ligne_picking(
                ligne=ligne, quantite=request.data.get('quantite'),
                user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        vague.refresh_from_db()
        return Response(self.get_serializer(vague).data)


class UniteLogistiqueViewSet(CompanyScopedModelViewSet):
    """NTWMS6 — colis et palettes adressables (SSCC GS1).

    Le SSCC est attribué côté serveur à la création (jamais accepté du corps
    de requête). ``{id}/sceller/`` fige le contenu ; ``{id}/etiquette-pdf/``
    imprime l'étiquette SSCC scannable.
    """
    queryset = UniteLogistique.objects.prefetch_related(
        'lignes__produit', 'lignes__lot', 'enfants',
    ).select_related('parent', 'vague', 'scelle_par').all()
    serializer_class = UniteLogistiqueSerializer
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['etiquette_pdf']:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + ['sceller', 'ajouter_ligne']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        type_unite = params.get('type_unite')
        if type_unite:
            qs = qs.filter(type_unite=type_unite)
        return qs

    def create(self, request, *args, **kwargs):
        from ..services import creer_unite_logistique
        company = request.user.company
        parent = None
        if request.data.get('parent'):
            parent = UniteLogistique.objects.filter(
                id=request.data.get('parent'), company=company).first()
            if parent is None:
                return Response(
                    {'detail': 'Palette introuvable dans cette société.'},
                    status=status.HTTP_400_BAD_REQUEST)
        vague = None
        if request.data.get('vague'):
            vague = VaguePicking.objects.filter(
                id=request.data.get('vague'), company=company).first()
        try:
            unite = creer_unite_logistique(
                company=company,
                type_unite=request.data.get('type_unite') or 'colis',
                parent=parent, vague=vague,
                poids_kg=request.data.get('poids_kg') or None,
                dimensions=request.data.get('dimensions') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(unite).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='lignes')
    def ajouter_ligne(self, request, pk=None):
        """Ajoute une ligne de contenu (``{produit, quantite, lot?}``).
        Refusée si l'unité est déjà scellée."""
        from ..models import LotEntrepot, Produit
        from ..services import ajouter_ligne_unite_logistique
        unite = self.get_object()
        company = request.user.company
        produit = Produit.objects.filter(
            id=request.data.get('produit'), company=company).first()
        lot = None
        if request.data.get('lot'):
            lot = LotEntrepot.objects.filter(
                id=request.data.get('lot'), company=company).first()
        try:
            ajouter_ligne_unite_logistique(
                company=company, unite=unite, produit=produit,
                quantite=request.data.get('quantite'), lot=lot)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        unite.refresh_from_db()
        return Response(self.get_serializer(unite).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='sceller')
    def sceller(self, request, pk=None):
        """Fige le contenu de l'unité et rend son étiquette imprimable."""
        from ..services import sceller_unite_logistique
        unite = self.get_object()
        try:
            sceller_unite_logistique(unite=unite, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        unite.refresh_from_db()
        return Response(self.get_serializer(unite).data)

    @action(detail=True, methods=['get'], url_path='etiquette-pdf')
    def etiquette_pdf(self, request, pk=None):
        """Étiquette SSCC scannable (GS1-128 ``(00)<sscc>``) en PDF.
        ``?sortie=html`` renvoie le HTML (debug/impression navigateur)."""
        from django.http import HttpResponse
        from .. import labels
        from apps.ventes.utils.pdf import _html_to_pdf

        unite = self.get_object()
        contenu = ', '.join(
            f'{ligne.produit.nom} × {ligne.quantite}'
            for ligne in unite.lignes.select_related('produit')[:4]) or 'Vide'
        html = labels.render_etiquettes_sscc_html([{
            'sscc': unite.sscc,
            'titre': f'{unite.get_type_unite_display()} {unite.sscc}',
            'sous_titre': contenu,
        }])
        if request.query_params.get('sortie') == 'html':
            return HttpResponse(html, content_type='text/html; charset=utf-8')
        response = HttpResponse(_html_to_pdf(html),
                                content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="sscc-{unite.sscc}.pdf"')
        return response
