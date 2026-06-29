"""FG291 — vues du Programme / Projet multi-chantiers.

  * ``ProjetViewSet`` : CRUD du programme + actions de rattachement
    (``attacher_chantier`` / ``attacher_devis`` / ``attacher_ticket``) qui
    regroupent chantiers + devis + tickets sous un même dossier.
  * ``ProjetChantierViewSet`` / ``ProjetDevisViewSet`` / ``ProjetTicketViewSet`` :
    gestion fine des tables de liaison.

Toutes les vues sont multi-tenant via ``TenantMixin`` : le queryset est filtré
sur la société de l'utilisateur et la société est posée côté serveur dans
``perform_create`` (jamais lue du corps). La référence du programme est
générée via le numéroteur anti-collision partagé (jamais ``count()+1``). Les
objets cross-app (devis ``ventes`` / ticket ``sav``) sont référencés par
string-FK et validés tenant via l'objet résolu par DRF — leurs modèles ne sont
JAMAIS importés, et leurs statuts ne sont JAMAIS touchés."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from apps.ventes.utils.references import create_with_reference

from ..models import (
    Projet, ProjetChantier, ProjetDevis, ProjetTicket,
)
from ..serializers import (
    ProjetSerializer, ProjetChantierSerializer,
    ProjetDevisSerializer, ProjetTicketSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


def _check_tenant(serializer, company, field):
    """Tenant safety : l'objet lié (chantier/devis/ticket) doit appartenir à la
    société du user. L'objet est déjà résolu par DRF (PrimaryKeyRelatedField),
    donc on lit `company_id` sans importer le modèle de l'autre app."""
    cid = getattr(company, 'id', None)
    obj = serializer.validated_data.get(field)
    if obj is not None and getattr(obj, 'company_id', None) != cid:
        raise ValidationError({field: 'Objet inconnu pour cette société.'})


def _check_projet_tenant(serializer, company):
    """Le programme ciblé doit appartenir à la société du user."""
    _check_tenant(serializer, company, 'projet')


class ProjetViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG291 — programme/projet multi-chantiers (ferme à 4 forages, toiture par
    tranches). Lecture tout rôle, écriture responsable/admin. Référence et
    société posées côté serveur. Filtrable par `statut` et `client`."""
    queryset = Projet.objects.prefetch_related(
        'chantiers', 'chantiers__installation',
        'devis', 'devis__devis',
        'tickets', 'tickets__ticket',
    ).select_related('client', 'responsable').all()
    serializer_class = ProjetSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        client = self.request.query_params.get('client')
        if client:
            qs = qs.filter(client_id=client)
        return qs

    def perform_create(self, serializer):
        """Référence anti-collision (jamais count()+1), société + créateur posés
        côté serveur. Le client (optionnel) doit appartenir à la société."""
        company = self.request.user.company
        _check_tenant(serializer, company, 'client')

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(Projet, 'PRG', company, _save)

    def perform_update(self, serializer):
        _check_tenant(serializer, self.request.user.company, 'client')
        serializer.save(company=self.request.user.company)

    # ── Actions de regroupement ──────────────────────────────────────────────
    def _attach(self, request, link_model, field, serializer_class):
        projet = self.get_object()
        target_id = request.data.get(field)
        if not target_id:
            return Response(
                {'detail': f"Le champ « {field} » est requis."},
                status=status.HTTP_400_BAD_REQUEST)
        company = request.user.company
        # Résout l'objet cible (chantier/devis/ticket) via la métadonnée du FK
        # string — jamais d'import des modèles d'une autre app. Tenant-check :
        # il doit appartenir à la société du user.
        target_model = link_model._meta.get_field(field).related_model
        target = (target_model.objects
                  .filter(pk=target_id, company=company).first())
        if target is None:
            return Response(
                {field: 'Objet inconnu pour cette société.'},
                status=status.HTTP_400_BAD_REQUEST)
        # Idempotent : ne duplique pas un rattachement déjà présent (on ne passe
        # PAS par la validation du serializer, qui rejetterait le doublon via le
        # contrôle d'unicité — get_or_create EST le comportement idempotent voulu).
        obj, created = link_model.objects.get_or_create(
            projet=projet, **{f'{field}_id': target_id},
            defaults={'company': company})
        return Response(
            serializer_class(obj).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def attacher_chantier(self, request, pk=None):
        """FG291 — rattache un chantier (`installation`) au programme."""
        return self._attach(
            request, ProjetChantier, 'installation', ProjetChantierSerializer)

    @action(detail=True, methods=['post'])
    def attacher_devis(self, request, pk=None):
        """FG291 — rattache un devis (`devis`) au programme (statut intact)."""
        return self._attach(
            request, ProjetDevis, 'devis', ProjetDevisSerializer)

    @action(detail=True, methods=['post'])
    def attacher_ticket(self, request, pk=None):
        """FG291 — rattache un ticket SAV (`ticket`) au programme (statut
        intact)."""
        return self._attach(
            request, ProjetTicket, 'ticket', ProjetTicketSerializer)


class ProjetChantierViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG291 — rattachements chantier↔programme. Filtrable par `projet`."""
    queryset = ProjetChantier.objects.select_related(
        'projet', 'installation').all()
    serializer_class = ProjetChantierSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_projet_tenant(serializer, company)
        _check_tenant(serializer, company, 'installation')
        serializer.save(company=company)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_projet_tenant(serializer, company)
        _check_tenant(serializer, company, 'installation')
        serializer.save(company=company)


class ProjetDevisViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG291 — rattachements devis↔programme (string-FK, statut intact)."""
    queryset = ProjetDevis.objects.select_related('projet', 'devis').all()
    serializer_class = ProjetDevisSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_projet_tenant(serializer, company)
        _check_tenant(serializer, company, 'devis')
        serializer.save(company=company)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_projet_tenant(serializer, company)
        _check_tenant(serializer, company, 'devis')
        serializer.save(company=company)


class ProjetTicketViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG291 — rattachements ticket SAV↔programme (string-FK, statut intact)."""
    queryset = ProjetTicket.objects.select_related('projet', 'ticket').all()
    serializer_class = ProjetTicketSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_projet_tenant(serializer, company)
        _check_tenant(serializer, company, 'ticket')
        serializer.save(company=company)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_projet_tenant(serializer, company)
        _check_tenant(serializer, company, 'ticket')
        serializer.save(company=company)
