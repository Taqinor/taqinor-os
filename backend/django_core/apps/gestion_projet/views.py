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

from . import selectors, services
from .models import (
    DependanceTache,
    Jalon,
    PhaseProjet,
    Projet,
    ProjetActivity,
    ProjetChantier,
    ProjetLien,
    Tache,
)
from .serializers import (
    DependanceTacheSerializer,
    JalonSerializer,
    PhaseProjetSerializer,
    ProjetActivitySerializer,
    ProjetChantierSerializer,
    ProjetLienSerializer,
    ProjetSerializer,
    TacheSerializer,
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

    @action(detail=True, methods=['post'], url_path='instancier-phases')
    def instancier_phases(self, request, pk=None):
        """Crée les 5 phases standard du projet (idempotent).

        La société est garantie par ``get_object`` (queryset scopé société). Un
        second appel ne duplique rien. Renvoie la liste complète des phases.
        """
        projet = self.get_object()
        phases = services.instancier_phases_standard(projet)
        return Response(PhaseProjetSerializer(phases, many=True).data)

    @action(detail=True, methods=['get'], url_path='taches')
    def taches(self, request, pk=None):
        """Arborescence WBS des tâches du projet (racines → sous-tâches).

        La société est garantie par ``get_object`` (queryset scopé société) :
        chaque dict porte ses ``sous_taches`` (profondeur arbitraire).
        """
        projet = self.get_object()
        return Response(selectors.arbre_taches(projet))

    @action(detail=True, methods=['get'], url_path='gantt')
    def gantt(self, request, pk=None):
        """Planning Gantt du projet : barres + liens de dépendance (lecture seule).

        La société est garantie par ``get_object`` (queryset scopé société) :
        un projet d'une autre société → 404. Délègue au sélecteur
        ``planning_gantt`` (barres datées via ``projet.date_debut``, marges,
        drapeau critique, liens prédécesseur→successeur).
        """
        projet = self.get_object()
        return Response(selectors.planning_gantt(projet))

    @action(detail=True, methods=['get'], url_path='avancement')
    def avancement(self, request, pk=None):
        """Roll-up d'avancement pondéré par charge du projet (lecture seule).

        La société est garantie par ``get_object`` (queryset scopé société) :
        un projet d'une autre société → 404. Délègue au sélecteur
        ``rollup_avancement`` (avancement global + arbre WBS recalculé).
        """
        projet = self.get_object()
        return Response(selectors.rollup_avancement(projet))

    @action(detail=True, methods=['get'], url_path='chemin-critique')
    def chemin_critique(self, request, pk=None):
        """Chemin critique (CPM) + marges du projet (lecture seule).

        La société est garantie par ``get_object`` (queryset scopé société) :
        un projet d'une autre société → 404. Délègue au sélecteur
        ``chemin_critique`` (durées dérivées, ES/EF/LS/LF, marges
        totale/libre, ensemble des tâches critiques).
        """
        projet = self.get_object()
        return Response(selectors.chemin_critique(projet))

    @action(detail=True, methods=['get'], url_path='jalons')
    def jalons(self, request, pk=None):
        """Jalons du projet, ordonnés par date prévue (lecture seule).

        La société est garantie par ``get_object`` (queryset scopé société) :
        un projet d'une autre société → 404. Délègue au sélecteur
        ``jalons_for_projet``.
        """
        projet = self.get_object()
        return Response(
            JalonSerializer(
                selectors.jalons_for_projet(projet), many=True).data)


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


class PhaseProjetViewSet(_GestionProjetBaseViewSet):
    """Phases (WBS) d'un projet : étude / appro / pose / MES / réception.

    ``company`` est posée côté serveur (TenantMixin) ; le ``projet`` reçu est
    validé même-société par le sérialiseur (cible d'une autre société → 400).
    Filtre optionnel ``?projet=<id>`` ; tri par défaut ``ordre`` puis ``id``.
    """
    queryset = PhaseProjet.objects.select_related('projet').all()
    serializer_class = PhaseProjetSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'type_phase', 'statut', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs


class TacheViewSet(_GestionProjetBaseViewSet):
    """Tâches & sous-tâches (WBS) d'un projet — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; les FK reçus (``projet``,
    ``phase``, ``parent``) sont validés même-société par le sérialiseur (cible
    d'une autre société → 400). Filtres optionnels : ``?projet=<id>``,
    ``?parent=<id>`` (sous-tâches directes), ``?racines=1`` (tâches sans
    parent), ``?statut=<statut>``. Recherche par libellé / code WBS ; tri par
    défaut ``ordre`` puis ``id``. L'arborescence complète est servie par
    ``projets/<id>/taches/``.
    """
    queryset = Tache.objects.select_related('projet', 'phase', 'parent').all()
    serializer_class = TacheSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'code_wbs']
    ordering_fields = ['ordre', 'code_wbs', 'statut', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        parent = self.request.query_params.get('parent')
        if parent:
            qs = qs.filter(parent_id=parent)
        if self.request.query_params.get('racines') in ('1', 'true', 'True'):
            qs = qs.filter(parent__isnull=True)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @action(detail=True, methods=['get'], url_path='dependances')
    def dependances(self, request, pk=None):
        """Prédécesseurs & successeurs directs d'une tâche (lecture seule).

        La société est garantie par ``get_object`` (queryset scopé société) :
        une tâche d'une autre société → 404. Délègue au sélecteur
        ``dependances_de_tache`` (deux dicts ``predecesseurs``/``successeurs``).
        """
        tache = self.get_object()
        return Response(selectors.dependances_de_tache(tache))

    @action(detail=True, methods=['post'], url_path='reprogrammer')
    def reprogrammer(self, request, pk=None):
        """Déplace la tâche (drag) et POUSSE ses successeurs en cascade.

        Corps : ``date_debut`` (obligatoire, ``YYYY-MM-DD``) et ``date_fin``
        (optionnelle ; à défaut la durée courante est conservée). La société est
        garantie par ``get_object`` (queryset scopé société) : une tâche d'une
        autre société → 404. Délègue au service ``reprogrammer_tache`` (écritures
        atomiques). Renvoie la liste des tâches modifiées (tâche déplacée +
        successeurs décalés) ; une date incohérente ou un cycle → 400.
        """
        from datetime import date as _date

        tache = self.get_object()
        debut_raw = request.data.get('date_debut')
        fin_raw = request.data.get('date_fin')
        if not debut_raw:
            return Response(
                {'date_debut': 'La date de début est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)

        def _parse(value, champ):
            if value in (None, ''):
                return None
            if isinstance(value, _date):
                return value
            try:
                return _date.fromisoformat(value)
            except (ValueError, TypeError):
                raise ValueError(champ)

        try:
            debut = _parse(debut_raw, 'date_debut')
            fin = _parse(fin_raw, 'date_fin')
        except ValueError as exc:
            return Response(
                {str(exc): 'Date invalide (format attendu : YYYY-MM-DD).'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            modifies = services.reprogrammer_tache(tache, debut, fin)
        except services.RescheduleError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TacheSerializer(modifies, many=True).data)


class DependanceTacheViewSet(_GestionProjetBaseViewSet):
    """Dépendances de planning entre tâches (FS/SS/FF/SF + lag) — CRUD scopé.

    ``company`` est posée côté serveur (TenantMixin) ; les FK reçus
    (``predecesseur``, ``successeur``) sont validés même-société par le
    sérialiseur, qui refuse en plus l'auto-dépendance, une dépendance
    inter-projets et un cycle direct (l'arête inverse existe déjà) → 400.
    Filtres optionnels : ``?projet=<id>`` (toutes les arêtes du projet),
    ``?predecesseur=<id>``, ``?successeur=<id>``, ``?type_dependance=<type>``.
    """
    queryset = DependanceTache.objects.select_related(
        'predecesseur', 'successeur').all()
    serializer_class = DependanceTacheSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'type_dependance']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(predecesseur__projet_id=projet)
        predecesseur = self.request.query_params.get('predecesseur')
        if predecesseur:
            qs = qs.filter(predecesseur_id=predecesseur)
        successeur = self.request.query_params.get('successeur')
        if successeur:
            qs = qs.filter(successeur_id=successeur)
        type_dependance = self.request.query_params.get('type_dependance')
        if type_dependance:
            qs = qs.filter(type_dependance=type_dependance)
        return qs


class JalonViewSet(_GestionProjetBaseViewSet):
    """Jalons (milestones) d'un projet — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; les FK reçus (``projet``,
    ``phase``, ``tache``) sont validés même-société par le sérialiseur (cible
    d'une autre société → 400), qui borne en plus ``facturation_pct`` à
    [0, 100]. Filtres optionnels : ``?projet=<id>``, ``?statut=<statut>``,
    ``?facturation=1`` (jalons de facturation, ``facturation_pct`` > 0).
    Recherche par libellé ; tri par défaut ``date_prevue`` puis ``id``.
    L'échéancier complet d'un projet est servi par ``projets/<id>/jalons/``.
    """
    queryset = Jalon.objects.select_related(
        'projet', 'phase', 'tache').all()
    serializer_class = JalonSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'description']
    ordering_fields = ['date_prevue', 'date_reelle', 'statut',
                       'facturation_pct', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        facturation = self.request.query_params.get('facturation')
        if facturation in ('1', 'true', 'True'):
            qs = qs.filter(facturation_pct__gt=0)
        return qs
