"""Vues de la Gestion de projet (toutes scopées société, admin-gated).

L'accès est réservé au palier Administrateur/Responsable
(``IsResponsableOrAdmin``). Les viewsets filtrent par ``request.user.company``
(TenantMixin) et posent la société côté serveur ; le ``responsable`` reçu est
validé comme appartenant à la même société.
"""
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import selectors
from .models import Projet, ProjetActivity, ProjetChantier, ProjetLien
from .serializers import (
    ProjetActivitySerializer,
    ProjetChantierSerializer,
    ProjetLienSerializer,
    ProjetSerializer,
)


class _GestionProjetBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class ProjetViewSet(_GestionProjetBaseViewSet):
    """Projets multi-chantier de la société. Recherche par code/nom.

    ``company`` est posée côté serveur par le ``TenantMixin`` ; le
    ``responsable`` provient du corps validé du sérialiseur.

    Cycle de vie ``statut`` — machine à états PROPRE au projet, appliquée côté
    serveur (totalement distincte du tunnel CRM de ``STAGES.py``, règle #2) :

        brouillon ─planifier→ planifie ─demarrer→ en_cours ─terminer→ termine
            │                    │            │   ↕                     ▲
            │                    │            │  en_pause ─reprendre────┘
            └──── annuler ───────┴────────────┴──→ annule

    Le ``statut`` n'est JAMAIS modifiable par PATCH direct (read-only au
    sérialiseur) : seules les actions ``planifier`` / ``demarrer`` /
    ``mettre-en-pause`` / ``reprendre`` / ``terminer`` / ``annuler`` le
    déplacent, chacune validant l'état courant et refusant (400) une transition
    illégale. ``termine`` et ``annule`` sont terminaux. Chaque transition
    journalise une entrée ``ProjetActivity`` (ancien → nouveau statut, auteur et
    société posés côté serveur).
    """
    queryset = Projet.objects.select_related('responsable').all()
    serializer_class = ProjetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom', 'description']
    ordering_fields = ['code', 'nom', 'statut', 'date_debut', 'id']

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @action(detail=True, methods=['get'])
    def liens(self, request, pk=None):
        """Liens du projet ENRICHIS via les sélecteurs des apps cibles.

        Pour chaque lien : libellé frais quand l'app cible expose un sélecteur
        (``source='live'``), sinon le libellé stocké (``source='stored'``). La
        société est garantie par ``get_object`` (queryset scopé société).
        """
        projet = self.get_object()
        return Response(selectors.liens_enrichis(projet))

    # ── Machine à états (PROPRE au projet, jamais STAGES.py) ─────────────────
    def _transition(self, request, *, allowed_from, target):
        """Applique une transition de statut si elle est légale, sinon 400.

        Journalise le changement dans ``ProjetActivity`` (auteur et société
        posés côté serveur). La société est garantie par ``get_object``
        (queryset scopé société) : une cible d'une autre société → 404.
        """
        projet = self.get_object()
        if projet.statut not in allowed_from:
            return Response(
                {'statut': (
                    f"Transition invalide depuis « "
                    f"{projet.get_statut_display()} » vers « "
                    f"{Projet.Statut(target).label} ».")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        old = projet.statut
        projet.statut = target
        projet.save(update_fields=['statut'])
        ProjetActivity.objects.create(
            company=request.user.company,
            projet=projet,
            old_value=old,
            new_value=target,
            auteur=request.user,
        )
        return Response(ProjetSerializer(projet).data)

    @action(detail=True, methods=['post'], url_path='planifier')
    def planifier(self, request, pk=None):
        """brouillon → planifie."""
        return self._transition(
            request,
            allowed_from={Projet.Statut.BROUILLON},
            target=Projet.Statut.PLANIFIE,
        )

    @action(detail=True, methods=['post'], url_path='demarrer')
    def demarrer(self, request, pk=None):
        """planifie | en_pause → en_cours."""
        return self._transition(
            request,
            allowed_from={Projet.Statut.PLANIFIE, Projet.Statut.EN_PAUSE},
            target=Projet.Statut.EN_COURS,
        )

    @action(detail=True, methods=['post'], url_path='mettre-en-pause')
    def mettre_en_pause(self, request, pk=None):
        """en_cours → en_pause."""
        return self._transition(
            request,
            allowed_from={Projet.Statut.EN_COURS},
            target=Projet.Statut.EN_PAUSE,
        )

    @action(detail=True, methods=['post'], url_path='reprendre')
    def reprendre(self, request, pk=None):
        """en_pause → en_cours."""
        return self._transition(
            request,
            allowed_from={Projet.Statut.EN_PAUSE},
            target=Projet.Statut.EN_COURS,
        )

    @action(detail=True, methods=['post'], url_path='terminer')
    def terminer(self, request, pk=None):
        """en_cours → termine."""
        return self._transition(
            request,
            allowed_from={Projet.Statut.EN_COURS},
            target=Projet.Statut.TERMINE,
        )

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """brouillon | planifie | en_cours | en_pause → annule."""
        return self._transition(
            request,
            allowed_from={
                Projet.Statut.BROUILLON,
                Projet.Statut.PLANIFIE,
                Projet.Statut.EN_COURS,
                Projet.Statut.EN_PAUSE,
            },
            target=Projet.Statut.ANNULE,
        )

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """Journal des transitions de statut (du plus récent au plus ancien)."""
        projet = self.get_object()
        return Response(
            ProjetActivitySerializer(
                projet.activites.all(), many=True).data)


class ProjetChantierViewSet(_GestionProjetBaseViewSet):
    """Rattachements chantier ↔ projet (liens lâches)."""
    queryset = ProjetChantier.objects.select_related('projet').all()
    serializer_class = ProjetChantierSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs


class ProjetLienViewSet(_GestionProjetBaseViewSet):
    """Liens projet → devis / facture / ticket / achat (références lâches).

    ``company`` est posée côté serveur (TenantMixin) ; le ``projet`` reçu est
    validé même-société par le sérialiseur. Filtre optionnel ``?projet=<id>`` et
    ``?type_cible=<type>``.
    """
    queryset = ProjetLien.objects.select_related('projet').all()
    serializer_class = ProjetLienSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        type_cible = self.request.query_params.get('type_cible')
        if type_cible:
            qs = qs.filter(type_cible=type_cible)
        return qs
