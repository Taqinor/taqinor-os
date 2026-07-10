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
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference

from ..models import (
    Projet, ProjetTache, ProjetChantier, ProjetDevis, ProjetTicket,
    BudgetProjet, BudgetEngagement,
)
from ..selectors import budget_projet_synthese, projet_pnl
from ..serializers import (
    ProjetSerializer, ProjetTacheSerializer, ProjetChantierSerializer,
    ProjetDevisSerializer, ProjetTicketSerializer,
    BudgetProjetSerializer, BudgetEngagementSerializer,
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


class ProjetViewSet(CompanyScopedModelViewSet):
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

    @action(detail=True, methods=['get'],
            permission_classes=[IsResponsableOrAdmin])
    def pnl(self, request, pk=None):
        """FG295 — P&L de projet CONSOLIDÉ : revenu (factures client des devis
        du programme) − coûts (matériel/sous-traitance/imports + main-d'œuvre)
        → marge brute + marge %, sur TOUS les chantiers. Réservé
        responsable/admin (expose des coûts d'achat), via le sélecteur
        `projet_pnl` (lectures cross-app sans import de modèle)."""
        projet = self.get_object()
        return Response(projet_pnl(projet))


class ProjetChantierViewSet(CompanyScopedModelViewSet):
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


class ProjetDevisViewSet(CompanyScopedModelViewSet):
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


class ProjetTicketViewSet(CompanyScopedModelViewSet):
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


def _check_assigne_tenant(serializer, company):
    """L'utilisateur assigné (s'il y en a un) doit appartenir à la société du
    user. L'objet user n'a pas de `company_id` exposé comme les autres FK : on
    lit sa société résolue par DRF sans importer le modèle d'auth."""
    cid = getattr(company, 'id', None)
    user = serializer.validated_data.get('assigne')
    if user is not None and getattr(user, 'company_id', None) != cid:
        raise ValidationError({'assigne': 'Utilisateur inconnu pour cette société.'})


def _check_tache_links_same_projet(serializer, instance=None):
    """`parent` et `predecesseur` doivent appartenir au MÊME programme que la
    tâche, et la garde anti-cycle du modèle (``clean``) doit passer."""
    data = serializer.validated_data
    projet = data.get('projet') or getattr(instance, 'projet', None)
    for field in ('parent', 'predecesseur'):
        linked = data.get(field)
        if linked is not None and projet is not None \
                and linked.projet_id != projet.id:
            raise ValidationError(
                {field: 'Doit appartenir au même programme.'})


class ProjetTacheViewSet(CompanyScopedModelViewSet):
    """FG292 — tâches & sous-tâches de programme avec dépendances. Lecture tout
    rôle, écriture responsable/admin. Société posée côté serveur. Le programme,
    le parent, le prédécesseur et l'assigné sont validés tenant. Les cycles
    (parent/prédécesseur) sont refusés via la validation du modèle. Filtrable
    par `projet`, `statut`, `parent` et `assigne`."""
    queryset = ProjetTache.objects.select_related(
        'projet', 'parent', 'predecesseur', 'assigne').all()
    serializer_class = ProjetTacheSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        parent = self.request.query_params.get('parent')
        if parent is not None:
            if parent in ('', 'null', 'none'):
                qs = qs.filter(parent__isnull=True)
            else:
                qs = qs.filter(parent_id=parent)
        assigne = self.request.query_params.get('assigne')
        if assigne:
            qs = qs.filter(assigne_id=assigne)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_projet_tenant(serializer, company)
        _check_tenant(serializer, company, 'parent')
        _check_tenant(serializer, company, 'predecesseur')
        _check_assigne_tenant(serializer, company)
        _check_tache_links_same_projet(serializer)
        self._save_no_cycle(serializer, company)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_projet_tenant(serializer, company)
        _check_tenant(serializer, company, 'parent')
        _check_tenant(serializer, company, 'predecesseur')
        _check_assigne_tenant(serializer, company)
        _check_tache_links_same_projet(serializer, serializer.instance)
        self._save_no_cycle(serializer, company)

    @staticmethod
    def _save_no_cycle(serializer, company):
        """Sauvegarde puis valide la garde anti-cycle (``clean``) dans une même
        transaction : si une boucle parent/prédécesseur est détectée, tout est
        annulé (rollback) et une 400 est renvoyée — rien n'est persisté."""
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.db import transaction
        with transaction.atomic():
            instance = serializer.save(company=company)
            try:
                instance.clean()
            except DjangoValidationError as exc:
                transaction.set_rollback(True)
                raise ValidationError(
                    getattr(exc, 'message_dict', {'detail': exc.messages}))


# ── FG294 — Budget projet vs réel (engagé / dépensé) ──────────────────────────

class BudgetProjetViewSet(CompanyScopedModelViewSet):
    """FG294 — budget d'un programme + synthèse vs réel.

    CRUD du budget (enveloppes par catégorie, tarif main-d'œuvre, seuil
    d'alerte) — INTERNE : ce budget compare des coûts d'achat, donc réservé
    responsable/admin. La société et `created_by` sont posés côté serveur ; le
    `projet` est validé tenant. L'action `synthese` agrège le RÉEL (devis du
    programme + BCF/factures fournisseur rattachés + main-d'œuvre des chantiers)
    et le compare au budget avec un drapeau de dépassement, via le sélecteur
    `budget_projet_synthese` (lectures cross-app sans import de modèle).
    Filtrable par `projet`."""
    queryset = BudgetProjet.objects.select_related(
        'projet', 'company').prefetch_related('engagements').all()
    serializer_class = BudgetProjetSerializer

    def get_permissions(self):
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
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_projet_tenant(serializer, company)
        serializer.save(company=company)

    @action(detail=True, methods=['get'])
    def synthese(self, request, pk=None):
        """FG294 — budget vs réel (engagé/dépensé) + alerte de dépassement."""
        budget = self.get_object()
        return Response(budget_projet_synthese(budget))


class BudgetEngagementViewSet(CompanyScopedModelViewSet):
    """FG294 — rattachement d'un coût fournisseur (BCF ou facture fournisseur)
    à un budget de programme. INTERNE (responsable/admin). La société est posée
    côté serveur ; le budget et l'objet stock rattaché sont validés tenant. Les
    modèles stock ne sont JAMAIS importés : l'objet lié est résolu par DRF et on
    lit son `company_id`. Filtrable par `budget`."""
    queryset = BudgetEngagement.objects.select_related(
        'budget', 'bon_commande', 'facture').all()
    serializer_class = BudgetEngagementSerializer

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        budget = self.request.query_params.get('budget')
        if budget:
            qs = qs.filter(budget_id=budget)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'budget')
        _check_tenant(serializer, company, 'bon_commande')
        _check_tenant(serializer, company, 'facture')
        serializer.save(company=company)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'budget')
        _check_tenant(serializer, company, 'bon_commande')
        _check_tenant(serializer, company, 'facture')
        serializer.save(company=company)
