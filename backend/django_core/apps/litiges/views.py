"""Vues des Réclamations & litiges (scopées société, accès admin/responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société + le créateur côté serveur (jamais du corps de requête).

Cycle de vie d'une réclamation — machine à états appliquée côté serveur :

    ouverte ─prendre_en_charge→ en_traitement ─resoudre→ resolue
       │                              │
       └──────── rejeter ─────────────┴──→ rejetee

Règles : on ne peut prendre en charge qu'une réclamation ``ouverte`` ; on ne
résout qu'une réclamation ``en_traitement`` ; on rejette une réclamation
``ouverte`` ou ``en_traitement``. Une réclamation déjà ``resolue`` ou
``rejetee`` est terminale — toute transition est refusée (400). Chaque
transition journalise automatiquement une entrée de chatter (ancien → nouveau
statut, auteur côté serveur).
"""
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from core.permissions import WriteScopedPermissionMixin
from apps.core.destroy_mixins import UsageGuardedDestroyMixin

from .models import Reclamation, ReclamationActivity
from .serializers import ReclamationActivitySerializer, ReclamationSerializer


class _LitigesBaseViewSet(
        WriteScopedPermissionMixin, TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + lecture/écriture fine-grainées (YRBAC3).

    ``litige_voir`` gate les méthodes sûres (GET/HEAD/OPTIONS), ``litige_gerer``
    gate l'écriture (POST/PUT/PATCH/DELETE + actions custom). Comptes légacy
    sans rôle fin : repli historique Administrateur/Responsable préservé
    (``ScopedPermission`` → ``_user_has_or_legacy``).
    """
    read_permission = 'litige_voir'
    write_permission = 'litige_gerer'


class ReclamationViewSet(UsageGuardedDestroyMixin, _LitigesBaseViewSet):
    """Réclamations & litiges. Recherche par référence/objet/description.
    VX241(b) — AUCUN garde ni ligne AuditLog n'existait avant sur ce
    `destroy()` : un dossier légal (contentieux/recouvrement) pouvait être
    supprimé sans trace, y compris déjà pris en charge ou avec un historique
    de chatter. UsageGuardedDestroyMixin bloque (409 FR) tout litige qui n'est
    plus « ouvert » ou qui porte déjà une activité, et journalise la
    suppression effective des dossiers vraiment vierges."""
    queryset = Reclamation.objects.select_related('created_by').all()
    serializer_class = ReclamationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'objet', 'description']
    ordering_fields = ['id', 'gravite', 'date_creation']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    def destroy_guard_message(self, reclamation):
        if reclamation.statut != Reclamation.Statut.OUVERTE:
            return (
                "Ce litige a été pris en charge (statut « "
                f"{reclamation.get_statut_display()} ») — dossier légal, il "
                "ne peut plus être supprimé.")
        if reclamation.activites.exists():
            return ("Ce litige a un historique enregistré — dossier légal, "
                    "il ne peut plus être supprimé.")
        return None

    # ── Tableau de bord (LITIGE6) ────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='tableau-bord')
    def tableau_bord(self, request):
        """Indicateurs litiges : ouverts, montant contesté, délai de résolution.

        Lecture seule, scopée société. Fenêtre optionnelle via les paramètres
        ``debut`` / ``fin`` (``YYYY-MM-DD``, bornes inclusives sur la date de
        création). Le palier de permission est celui du viewset
        (Administrateur/Responsable) — un rôle limité reçoit donc 403.
        """
        from . import selectors

        data = selectors.tableau_bord_litiges(
            request.user.company,
            debut=request.query_params.get('debut'),
            fin=request.query_params.get('fin'),
        )
        return Response(data)

    # ── Analyse concurrents sur deals perdus (LITIGE5) ───────────────────────
    @action(detail=False, methods=['get'], url_path='analyse-concurrents')
    def analyse_concurrents(self, request):
        """Intelligence concurrentielle : qui nous bat, à quel prix, sur quel
        motif (litiges portant un concurrent gagnant saisi).

        Lecture seule, scopée société. Palier de permission du viewset
        (Administrateur/Responsable) — un rôle limité reçoit donc 403.
        """
        from . import selectors

        data = selectors.analyse_concurrents_perte(request.user.company)
        return Response(data)

    # ── Machine à états + chatter ────────────────────────────────────────────
    def _transition(self, request, *, allowed_from, target):
        """Applique une transition de statut si elle est légale, sinon 400.

        Journalise automatiquement le changement dans le chatter (auteur et
        société posés côté serveur).
        """
        reclamation = self.get_object()
        if reclamation.statut not in allowed_from:
            return Response(
                {'statut': (
                    f"Transition invalide depuis « "
                    f"{reclamation.get_statut_display()} » vers « "
                    f"{Reclamation.Statut(target).label} ».")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        old = reclamation.statut
        reclamation.statut = target
        reclamation.save(update_fields=['statut'])
        ReclamationActivity.objects.create(
            company=request.user.company,
            reclamation=reclamation,
            type=ReclamationActivity.Kind.LOG,
            old_value=old,
            new_value=target,
            auteur=request.user,
        )
        return Response(ReclamationSerializer(reclamation).data)

    @action(detail=True, methods=['post'], url_path='prendre-en-charge')
    def prendre_en_charge(self, request, pk=None):
        """ouverte → en_traitement."""
        return self._transition(
            request,
            allowed_from={Reclamation.Statut.OUVERTE},
            target=Reclamation.Statut.EN_TRAITEMENT,
        )

    @action(detail=True, methods=['post'], url_path='resoudre')
    def resoudre(self, request, pk=None):
        """en_traitement → resolue."""
        return self._transition(
            request,
            allowed_from={Reclamation.Statut.EN_TRAITEMENT},
            target=Reclamation.Statut.RESOLUE,
        )

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        """ouverte | en_traitement → rejetee."""
        return self._transition(
            request,
            allowed_from={
                Reclamation.Statut.OUVERTE,
                Reclamation.Statut.EN_TRAITEMENT,
            },
            target=Reclamation.Statut.REJETEE,
        )

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """Timeline chatter (auto + notes), du plus récent au plus ancien."""
        reclamation = self.get_object()
        return Response(
            ReclamationActivitySerializer(
                reclamation.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter')
    def noter(self, request, pk=None):
        """Note manuelle libre — auteur et société posés côté serveur."""
        reclamation = self.get_object()
        message = (request.data.get('message') or '').strip()
        if not message:
            return Response(
                {'message': 'Note vide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        act = ReclamationActivity.objects.create(
            company=request.user.company,
            reclamation=reclamation,
            type=ReclamationActivity.Kind.NOTE,
            message=message,
            auteur=request.user,
        )
        return Response(
            ReclamationActivitySerializer(act).data,
            status=status.HTTP_201_CREATED,
        )
