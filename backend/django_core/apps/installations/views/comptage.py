"""Vues FG324 — sessions de comptage tournant (cycle count ABC).

``SessionComptageViewSet`` : CRUD des sessions ; référence anti-collision posée
serveur ; action ``ajouter-ligne`` qui ajoute un SKU avec sa quantité théorique
SNAPSHOTÉE serveur (lue via ``stock.selectors`` — jamais d'import du modèle
stock) ; cycle ``demarrer`` / ``terminer``. ``ComptageLigneViewSet`` : saisie de
la quantité comptée (cochage `compte`). Lecture tout rôle, écriture
responsable/admin. Multi-tenant via ``TenantMixin``.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference

from ..models import SessionComptage, ComptageLigne
from ..serializers import (
    SessionComptageSerializer, ComptageLigneSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class SessionComptageViewSet(CompanyScopedModelViewSet):
    """FG324 — sessions de comptage tournant. Lecture tout rôle, écriture
    responsable/admin. Filtrable par `statut`, `classe_abc`, `emplacement`."""
    queryset = SessionComptage.objects.select_related(
        'emplacement', 'created_by').prefetch_related('lignes').all()
    serializer_class = SessionComptageSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        classe = params.get('classe_abc')
        if classe:
            qs = qs.filter(classe_abc=classe)
        emplacement = params.get('emplacement')
        if emplacement:
            qs = qs.filter(emplacement_id=emplacement)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        emplacement = serializer.validated_data.get('emplacement')
        if emplacement is not None and getattr(
                emplacement, 'company_id', None) != cid:
            raise ValidationError(
                {'emplacement': 'Emplacement inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(SessionComptage, 'CYC', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='ajouter-ligne')
    def ajouter_ligne(self, request, pk=None):
        """FG324 — ajoute un SKU à compter ; la quantité théorique est
        snapshotée serveur (lecture via stock.selectors). Body : `produit`."""
        session = self.get_object()
        company = request.user.company
        produit_id = request.data.get('produit')
        if not produit_id:
            return Response(
                {'produit': 'Paramètre `produit` requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        from apps.stock import selectors as stock_selectors
        try:
            produit = stock_selectors.get_produit_scoped(company, produit_id)
        except (ValueError, TypeError):
            produit = None
        if produit is None:
            return Response(
                {'produit': 'Produit inconnu pour cette société.'},
                status=status.HTTP_400_BAD_REQUEST)
        ligne = ComptageLigne.objects.create(
            session=session, produit=produit,
            designation=getattr(produit, 'nom', None),
            quantite_theorique=getattr(produit, 'quantite_stock', 0) or 0)
        return Response(
            ComptageLigneSerializer(ligne).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def demarrer(self, request, pk=None):
        """FG324 — passe la session en cours."""
        session = self.get_object()
        session.statut = SessionComptage.Statut.EN_COURS
        session.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(session).data)

    @action(detail=True, methods=['post'])
    def terminer(self, request, pk=None):
        """FG324/YSTCK1 — clôture la session (→ terminé) ET poste l'écart
        constaté en `MouvementStock` AJUSTEMENT (couche de CONSTAT → le
        stock canonique s'aligne enfin sur le compté). IDEMPOTENTE : une
        session déjà TERMINE ne re-poste jamais."""
        session = self.get_object()
        deja_terminee = session.statut == SessionComptage.Statut.TERMINE
        session.statut = SessionComptage.Statut.TERMINE
        session.save(update_fields=['statut', 'date_modification'])
        if not deja_terminee:
            from apps.stock.services import appliquer_ecarts_comptage
            appliquer_ecarts_comptage(
                company=request.user.company,
                lignes=list(session.lignes.all()),
                user=request.user, reference=session.reference)
        return Response(self.get_serializer(session).data)


class ComptageLigneViewSet(viewsets.ModelViewSet):
    """FG324 — lignes de comptage. Pas de `company` propre : scope via la
    session parente. Filtrable par `session`. Lecture tout rôle, écriture
    responsable/admin (saisie de `quantite_comptee` / `compte`)."""
    queryset = ComptageLigne.objects.select_related('session', 'produit').all()
    serializer_class = ComptageLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(session__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        session = self.request.query_params.get('session')
        if session:
            qs = qs.filter(session_id=session)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        session = serializer.validated_data.get('session')
        if session is not None and getattr(
                session, 'company_id', None) != cid:
            raise ValidationError(
                {'session': 'Session inconnue pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()
