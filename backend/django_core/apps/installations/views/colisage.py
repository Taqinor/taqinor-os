"""Vues FG322 — colisage / préparation (pack).

``ColisViewSet`` : CRUD des colis ; référence anti-collision posée serveur ;
cycle ``controler`` (→ contrôlé, pose `controle_par`/date) / ``expedier``
(→ expédié). ``ColisLigneViewSet`` : articles emballés (cochage `controle_ok`).
Lecture tout rôle, écriture responsable/admin. Multi-tenant via ``TenantMixin`` ;
chantier validé tenant. Cross-app : ``stock`` en string-FK.
"""
from django.utils import timezone

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference

from ..models import Colis, ColisLigne
from ..serializers import ColisSerializer, ColisLigneSerializer

READ_ACTIONS = ['list', 'retrieve']


class ColisViewSet(CompanyScopedModelViewSet):
    """FG322 — colis de préparation. Lecture tout rôle, écriture
    responsable/admin. Référence/société/`created_by` posés serveur. Filtrable
    par `installation`, `statut`."""
    queryset = Colis.objects.select_related(
        'installation', 'controle_par', 'created_by'
    ).prefetch_related('lignes').all()
    serializer_class = ColisSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        installation = params.get('installation')
        if installation:
            qs = qs.filter(installation_id=installation)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        installation = serializer.validated_data.get('installation')
        if installation is not None and getattr(
                installation, 'company_id', None) != cid:
            raise ValidationError(
                {'installation': 'Chantier inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(Colis, 'COL', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def controler(self, request, pk=None):
        """FG322 — contrôle le colis (→ contrôlé, pose `controle_par`/date)."""
        colis = self.get_object()
        colis.statut = Colis.Statut.CONTROLE
        colis.controle_par = request.user
        colis.date_controle = timezone.now()
        colis.save(update_fields=[
            'statut', 'controle_par', 'date_controle', 'date_modification'])
        return Response(self.get_serializer(colis).data)

    @action(detail=True, methods=['post'])
    def expedier(self, request, pk=None):
        """FG322 — expédie le colis (→ expédié)."""
        colis = self.get_object()
        colis.statut = Colis.Statut.EXPEDIE
        colis.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(colis).data)

    @action(detail=True, methods=['get'])
    def etiquette(self, request, pk=None):
        """ZSTK5 — étiquette de colis (contenu + code-barres colis) : le
        moteur d'étiquettes N20 (`apps.stock.labels`) encode `PRODUIT:`/
        `SYSTEME:`/`INTERVENTION:`/`EQUIP:` mais pas le colis — on ajoute le
        jeton `COLIS:<id>` (résolu par `apps.stock.views.produit.resolve`) et
        on rend une étiquette (réutilise `_label_card`/la planche du moteur
        N20) avec le n° de colis, le chantier/livraison et la liste condensée
        du contenu (désignation + qté SEULEMENT — jamais de prix). Renvoie du
        HTML prêt WeasyPrint, sur le patron des étiquettes FG85/XMFG7."""
        from django.http import HttpResponse as HR

        from apps.stock.labels import colis_token, render_labels_html

        colis = self.get_object()
        lignes = colis.lignes.all()
        contenu = ', '.join(
            f'{ligne.quantite}× '
            f'{ligne.designation or (ligne.produit.nom if ligne.produit_id else "?")}'
            for ligne in lignes
        ) or 'Colis vide'
        chantier = colis.installation.reference if colis.installation_id else ''
        sous_titre = f'{chantier} — {contenu}' if chantier else contenu
        items = [{
            'token': colis_token(colis.id),
            'titre': colis.reference,
            'sous_titre': sous_titre,
        }]
        symbology = request.query_params.get('symbology', 'qr')
        html = render_labels_html(items, symbology=symbology)
        return HR(html, content_type='text/html; charset=utf-8')


class ColisLigneViewSet(viewsets.ModelViewSet):
    """FG322 — lignes de colis. Pas de `company` propre : scope via le colis
    parent. Filtrable par `colis`. Lecture tout rôle, écriture
    responsable/admin."""
    queryset = ColisLigne.objects.select_related('colis', 'produit').all()
    serializer_class = ColisLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(colis__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        colis = self.request.query_params.get('colis')
        if colis:
            qs = qs.filter(colis_id=colis)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        colis = serializer.validated_data.get('colis')
        if colis is not None and getattr(colis, 'company_id', None) != cid:
            raise ValidationError(
                {'colis': 'Colis inconnu pour cette société.'})
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(
                produit, 'company_id', None) != cid:
            raise ValidationError(
                {'produit': 'Produit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()
