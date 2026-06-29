"""Vues de la Gestion de projet (toutes scopées société, admin-gated).

L'accès est réservé au palier Administrateur/Responsable
(``IsResponsableOrAdmin``). Les viewsets filtrent par ``request.user.company``
(TenantMixin) et posent la société côté serveur ; le ``responsable`` reçu est
validé comme appartenant à la même société.
"""
from datetime import date as _date

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import selectors, services
from .models import (
    AffectationRessource,
    BaselinePlanning,
    CalendrierProjet,
    DependanceTache,
    Equipe,
    Indisponibilite,
    Jalon,
    JourFerie,
    PhaseProjet,
    Projet,
    ProjetActivity,
    ProjetChantier,
    ProjetLien,
    RessourceProfil,
    Tache,
)
from .serializers import (
    AffectationRessourceSerializer,
    BaselinePlanningSerializer,
    CalendrierProjetSerializer,
    DependanceTacheSerializer,
    EquipeSerializer,
    IndisponibiliteSerializer,
    JalonSerializer,
    JourFerieSerializer,
    PhaseProjetSerializer,
    ProjetActivitySerializer,
    ProjetChantierSerializer,
    ProjetLienSerializer,
    ProjetSerializer,
    RessourceProfilSerializer,
    TacheSerializer,
)


def _parse_date_param(value):
    """Parse une date ``YYYY-MM-DD`` issue de la query-string, ou ``None``.

    Renvoie ``None`` si ``value`` est vide ou n'est pas une date ISO valide.
    """
    if value in (None, ''):
        return None
    try:
        return _date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


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

    @action(detail=True, methods=['post'], url_path='baseline')
    def baseline(self, request, pk=None):
        """Fige une BASELINE du planning courant du projet (plan vs réel).

        Corps optionnel : ``libelle``. La société est garantie par
        ``get_object`` (queryset scopé société) ; ``auteur`` est posé côté
        serveur. Délègue au service ``creer_baseline`` (snapshot atomique de
        toutes les tâches). Renvoie la baseline créée.
        """
        projet = self.get_object()
        libelle = request.data.get('libelle', '') or ''
        baseline = services.creer_baseline(
            projet, libelle=libelle, auteur=request.user)
        return Response(
            BaselinePlanningSerializer(baseline).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='baselines')
    def baselines(self, request, pk=None):
        """Baselines du projet (plus récentes d'abord, lecture seule)."""
        projet = self.get_object()
        return Response(
            BaselinePlanningSerializer(
                selectors.baselines_for_projet(projet), many=True).data)

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

    @action(detail=True, methods=['get'], url_path='retards')
    def retards(self, request, pk=None):
        """Tâches et jalons EN RETARD ou À RISQUE du projet (PROJ14).

        Paramètre optionnel ``?seuil_jours=N`` (entier positif, défaut 7) :
        horizon du radar « à risque » — une tâche/un jalon dont la fin prévue
        tombe dans les N prochains jours est signalée « à risque ».

        La société est garantie par ``get_object`` (queryset scopé société) :
        un projet d'une autre société → 404. Délègue au sélecteur
        ``retards_projet`` (lecture seule, aucune écriture). Le paramètre
        ``seuil_jours`` invalide (non entier / négatif) est silencieusement
        remplacé par la valeur par défaut (7 jours).
        """
        projet = self.get_object()
        seuil_raw = request.query_params.get('seuil_jours')
        seuil = None
        if seuil_raw is not None:
            try:
                seuil = max(0, int(seuil_raw))
            except (ValueError, TypeError):
                seuil = None
        return Response(selectors.retards_projet(projet, seuil_jours=seuil))


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


class CalendrierProjetViewSet(_GestionProjetBaseViewSet):
    """Calendrier ouvré d'un projet (jours travaillés + fériés) — CRUD scopé.

    ``company`` est posée côté serveur (TenantMixin) ; le ``projet`` reçu est
    validé même-société par le sérialiseur (un seul calendrier par projet).
    Filtre optionnel ``?projet=<id>``. Les jours fériés sont exposés imbriqués
    en lecture ; ils se créent via ``jours-feries/``.
    """
    queryset = CalendrierProjet.objects.select_related('projet').all()
    serializer_class = CalendrierProjetSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs


class JourFerieViewSet(_GestionProjetBaseViewSet):
    """Jours fériés (chômés) d'un calendrier de projet — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; le ``calendrier`` reçu est
    validé même-société par le sérialiseur. Filtres optionnels :
    ``?calendrier=<id>``, ``?projet=<id>``. Tri par défaut ``date`` puis ``id``.
    """
    queryset = JourFerie.objects.select_related('calendrier').all()
    serializer_class = JourFerieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        calendrier = self.request.query_params.get('calendrier')
        if calendrier:
            qs = qs.filter(calendrier_id=calendrier)
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(calendrier__projet_id=projet)
        return qs


class BaselinePlanningViewSet(_GestionProjetBaseViewSet):
    """Baselines de planning d'un projet (snapshots plan vs réel) — scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; le ``projet`` reçu est
    validé même-société par le sérialiseur ; ``auteur`` est posé côté serveur.
    Une baseline se prend de préférence via ``projets/<id>/baseline/`` (snapshot
    complet) ; ce viewset gère la lecture, l'édition du libellé et la suppression.
    Filtre optionnel ``?projet=<id>``. L'action ``comparer/`` renvoie l'écart
    plan vs réel ligne à ligne.
    """
    queryset = BaselinePlanning.objects.select_related(
        'projet', 'auteur').all()
    serializer_class = BaselinePlanningSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'id']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, auteur=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs

    @action(detail=True, methods=['get'], url_path='comparer')
    def comparer(self, request, pk=None):
        """Compare la baseline au planning COURANT (plan vs réel, lecture seule).

        La société est garantie par ``get_object`` (queryset scopé société) :
        une baseline d'une autre société → 404. Délègue au sélecteur
        ``comparer_baseline`` (écarts de début/fin en jours, dérive de charge,
        glissement maximal de fin).
        """
        baseline = self.get_object()
        return Response(selectors.comparer_baseline(baseline))


class RessourceProfilViewSet(_GestionProjetBaseViewSet):
    """Profils ressources internes (personnes / rôles) — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; ``user`` optionnel reçu
    validé même-société par le sérialiseur (cible d'une autre société → 400).
    Filtres optionnels : ``?actif=1`` (actifs uniquement), ``?role=<role>``.
    Recherche par nom/rôle ; tri par défaut ``nom`` puis ``id``.

    ``cout_horaire`` est INTERNE : visible sur cet écran de pilotage mais ne
    doit jamais figurer dans un PDF client.
    """
    queryset = RessourceProfil.objects.select_related(
        'company', 'user').all()
    serializer_class = RessourceProfilSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'role', 'competences']
    ordering_fields = ['nom', 'role', 'actif', 'id']

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        elif actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role__icontains=role)
        return qs

    @action(detail=False, methods=['get'], url_path='plan-de-charge')
    def plan_de_charge(self, request):
        """Plan de charge société : capacité vs affecté par ressource (PROJ18).

        Paramètres de requête :
            ``?debut=YYYY-MM-DD&fin=YYYY-MM-DD`` (OBLIGATOIRES) — fenêtre
            INCLUSIVE des deux côtés. ``fin`` antérieure à ``debut`` → 400.
            ``?heures_par_jour=N`` (optionnel, défaut 8) — heures d'un jour
            ouvré ; valeur invalide → 400.
            ``?ressource=<id>`` (optionnel) — restreindre à une ressource.

        Lecture seule. La société est imposée côté serveur
        (``request.user.company``) — jamais lue du corps de requête. Délègue au
        sélecteur ``plan_de_charge`` (capacité = jours ouvrés L-V moins
        indisponibilités × heures/jour ; affecté = somme proratée des
        affectations chevauchant la fenêtre ; ``surcharge`` quand
        affecté > capacité ; garde anti-division-par-zéro sur capacité nulle).
        """
        debut = _parse_date_param(request.query_params.get('debut'))
        fin = _parse_date_param(request.query_params.get('fin'))
        if debut is None or fin is None:
            return Response(
                {'detail': 'Les paramètres debut et fin (YYYY-MM-DD) sont '
                           'obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        if fin < debut:
            return Response(
                {'detail': 'La date de fin ne peut pas être antérieure à la '
                           'date de début.'},
                status=status.HTTP_400_BAD_REQUEST)

        heures_raw = request.query_params.get('heures_par_jour')
        heures_par_jour = 8
        if heures_raw is not None:
            try:
                heures_par_jour = float(heures_raw)
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'heures_par_jour doit être un nombre.'},
                    status=status.HTTP_400_BAD_REQUEST)
            if heures_par_jour < 0:
                return Response(
                    {'detail': 'heures_par_jour doit être positif.'},
                    status=status.HTTP_400_BAD_REQUEST)

        ressource_id = None
        ressource_raw = request.query_params.get('ressource')
        if ressource_raw:
            try:
                ressource_id = int(ressource_raw)
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'ressource doit être un identifiant entier.'},
                    status=status.HTTP_400_BAD_REQUEST)

        return Response(selectors.plan_de_charge(
            request.user.company, debut, fin,
            heures_par_jour=heures_par_jour, ressource_id=ressource_id))

    @action(detail=False, methods=['get'], url_path='conflits-affectation')
    def conflits_affectation(self, request):
        """Conflits de double-affectation des ressources société (PROJ19).

        Paramètres de requête :
            ``?debut=YYYY-MM-DD&fin=YYYY-MM-DD`` (OBLIGATOIRES) — fenêtre
            INCLUSIVE des deux côtés. ``fin`` antérieure à ``debut`` → 400.

        Lecture seule. La société est imposée côté serveur
        (``request.user.company``) — jamais lue du corps de requête. Délègue au
        sélecteur ``conflits_affectation`` : pour chaque ressource, les couples
        d'affectations (directes ET via une équipe dont elle est membre) dont
        les fenêtres se chevauchent — une ressource double-bookée — plus, en
        bonus, les affectations posées alors qu'elle est indisponible. Les
        affectations d'actif matériel ne sont pas comptées.
        """
        debut = _parse_date_param(request.query_params.get('debut'))
        fin = _parse_date_param(request.query_params.get('fin'))
        if debut is None or fin is None:
            return Response(
                {'detail': 'Les paramètres debut et fin (YYYY-MM-DD) sont '
                           'obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        if fin < debut:
            return Response(
                {'detail': 'La date de fin ne peut pas être antérieure à la '
                           'date de début.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(selectors.conflits_affectation(
            request.user.company, debut, fin))

    @action(detail=False, methods=['get'], url_path='nivellement-charge')
    def nivellement_charge(self, request):
        """Nivellement de charge : propose un rééquilibrage des ressources (PROJ20).

        Paramètres de requête :
            ``?debut=YYYY-MM-DD&fin=YYYY-MM-DD`` (OBLIGATOIRES) — fenêtre
            INCLUSIVE des deux côtés. ``fin`` antérieure à ``debut`` → 400.
            ``?heures_par_jour=N`` (optionnel, défaut 8) — heures d'un jour
            ouvré ; valeur invalide → 400.

        Lecture seule, NE MUTE RIEN : la société est imposée côté serveur
        (``request.user.company``) — jamais lue du corps de requête. S'appuie sur
        le plan de charge (PROJ18) pour classer les ressources SUR-CHARGÉES /
        SOUS-CHARGÉES, puis propose de déplacer les affectations directes en
        excès vers les ressources sous-chargées qui ont assez de marge SANS créer
        de conflit de double-booking (PROJ19). Délègue au sélecteur
        ``nivellement_charge`` (proposition pure, aucune écriture).
        """
        debut = _parse_date_param(request.query_params.get('debut'))
        fin = _parse_date_param(request.query_params.get('fin'))
        if debut is None or fin is None:
            return Response(
                {'detail': 'Les paramètres debut et fin (YYYY-MM-DD) sont '
                           'obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        if fin < debut:
            return Response(
                {'detail': 'La date de fin ne peut pas être antérieure à la '
                           'date de début.'},
                status=status.HTTP_400_BAD_REQUEST)

        heures_raw = request.query_params.get('heures_par_jour')
        heures_par_jour = 8
        if heures_raw is not None:
            try:
                heures_par_jour = float(heures_raw)
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'heures_par_jour doit être un nombre.'},
                    status=status.HTTP_400_BAD_REQUEST)
            if heures_par_jour < 0:
                return Response(
                    {'detail': 'heures_par_jour doit être positif.'},
                    status=status.HTTP_400_BAD_REQUEST)

        return Response(selectors.nivellement_charge(
            request.user.company, debut, fin,
            heures_par_jour=heures_par_jour))


class EquipeViewSet(_GestionProjetBaseViewSet):
    """Équipes de ressources pour le planning — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; les ``membres`` reçus
    sont validés comme appartenant à la société de l'utilisateur par le
    sérialiseur. Filtre optionnel ``?membre=<id>`` (équipes contenant ce
    membre). Recherche par nom ; tri par défaut ``nom`` puis ``id``.
    """
    queryset = Equipe.objects.prefetch_related('membres').all()
    serializer_class = EquipeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'id']

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def get_queryset(self):
        qs = super().get_queryset()
        membre = self.request.query_params.get('membre')
        if membre:
            qs = qs.filter(membres__id=membre)
        return qs


class AffectationRessourceViewSet(_GestionProjetBaseViewSet):
    """Affectations de ressources sur les taches de projet (PROJ16).

    Alloue une ressource (profil, equipe ou actif materiel) a une tache sur
    une periode donnee. ``company`` est posee cote serveur (TenantMixin) ; les
    FK recus (``tache``, ``ressource``, ``equipe``) sont valides meme-societe
    par le serialiseur, qui refuse en plus plusieurs vecteurs simultanement.

    Filtres optionnels : ``?tache=<id>``, ``?projet=<id>`` (via la tache),
    ``?ressource=<id>``, ``?equipe=<id>``.
    Recherche par note ; tri par defaut ``tache``, ``date_debut``.
    """
    queryset = AffectationRessource.objects.select_related(
        'tache', 'ressource', 'equipe').all()
    serializer_class = AffectationRessourceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['note']
    ordering_fields = ['date_debut', 'date_fin', 'tache', 'id']

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def get_queryset(self):
        qs = super().get_queryset()
        tache = self.request.query_params.get('tache')
        if tache:
            qs = qs.filter(tache_id=tache)
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(tache__projet_id=projet)
        ressource = self.request.query_params.get('ressource')
        if ressource:
            qs = qs.filter(ressource_id=ressource)
        equipe = self.request.query_params.get('equipe')
        if equipe:
            qs = qs.filter(equipe_id=equipe)
        return qs


class IndisponibiliteViewSet(_GestionProjetBaseViewSet):
    """Indisponibilites des ressources de projet (PROJ17).

    Modelise les fenetres ou une ``RessourceProfil`` n'est pas mobilisable
    (conge / formation / arret), pour que la planification exclue une ressource
    indisponible sur une periode. ``company`` est posee cote serveur
    (TenantMixin) ; la ``ressource`` recue est validee meme-societe par le
    serialiseur.

    Filtres optionnels :
        ``?ressource=<id>``, ``?type=<conge|formation|arret>``,
        ``?debut=YYYY-MM-DD&fin=YYYY-MM-DD`` (indispos chevauchant la fenetre).
    Recherche par motif ; tri par defaut ``ressource``, ``date_debut``.
    """
    queryset = Indisponibilite.objects.select_related(
        'ressource', 'company').all()
    serializer_class = IndisponibiliteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['motif']
    ordering_fields = ['date_debut', 'date_fin', 'ressource', 'id']

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def get_queryset(self):
        qs = super().get_queryset()
        ressource = self.request.query_params.get('ressource')
        if ressource:
            qs = qs.filter(ressource_id=ressource)
        type_indispo = self.request.query_params.get('type')
        if type_indispo:
            qs = qs.filter(type_indispo=type_indispo)
        debut = self.request.query_params.get('debut')
        fin = self.request.query_params.get('fin')
        if debut and fin:
            # Chevauchement avec [debut, fin] (bornes inclusives).
            qs = qs.filter(date_debut__lte=fin, date_fin__gte=debut)
        return qs
