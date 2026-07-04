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
    ActionProjet,
    AffectationRessource,
    BaselinePlanning,
    ChronoEnCours,
    ClotureProjet,
    CommentaireProjet,
    CompteRenduReunion,
    DocumentProjet,
    BudgetProjet,
    CalendrierProjet,
    DependanceTache,
    Equipe,
    EvaluationProjet,
    Indisponibilite,
    ItemChecklistTache,
    Jalon,
    JourFerie,
    PointAvancement,
    LigneBudgetProjet,
    ModeleProjet,
    ModeleTache,
    PeriodeVerrouilleeTemps,
    PhaseProjet,
    PortailProjetToken,
    Projet,
    ProjetActivity,
    ProjetChantier,
    ProjetLien,
    RecurrenceTache,
    RessourceProfil,
    Risque,
    SituationTravaux,
    LigneSituation,
    SousTraitant,
    LotSousTraitance,
    Tache,
    Timesheet,
    VersionDocument,
)
from .serializers import (
    ActionProjetSerializer,
    AffectationRessourceSerializer,
    BaselinePlanningSerializer,
    ChronoEnCoursSerializer,
    ClotureProjetSerializer,
    CommentaireProjetSerializer,
    CompteRenduReunionSerializer,
    DocumentProjetSerializer,
    LigneSituationSerializer,
    LotSousTraitanceSerializer,
    SituationTravauxSerializer,
    SousTraitantSerializer,
    VersionDocumentSerializer,
    BudgetProjetSerializer,
    CalendrierProjetSerializer,
    DependanceTacheSerializer,
    EquipeSerializer,
    IndisponibiliteSerializer,
    ItemChecklistTacheSerializer,
    JalonSerializer,
    PointAvancementSerializer,
    JourFerieSerializer,
    LigneBudgetProjetSerializer,
    ModeleProjetSerializer,
    ModeleTacheSerializer,
    PeriodeVerrouilleeTempsSerializer,
    PhaseProjetSerializer,
    PortailProjetTokenSerializer,
    ProjetActivitySerializer,
    ProjetChantierSerializer,
    ProjetLienSerializer,
    ProjetSerializer,
    RecurrenceTacheSerializer,
    ReglageTempsSerializer,
    RessourceProfilSerializer,
    RisqueSerializer,
    TacheSerializer,
    TimesheetSerializer,
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

    @action(detail=False, methods=['post'], url_path='depuis-devis')
    def depuis_devis(self, request):
        """Crée un projet depuis un devis ACCEPTÉ (XPRJ21) — action explicite.

        Corps : ``devis_id`` (obligatoire). Crée le ``Projet`` (client résolu,
        code via numérotation SÛRE), le ``ProjetLien`` vers le devis, et un
        ``BudgetProjet`` v1 pré-ventilé matériel/main-d'œuvre depuis les
        lignes du devis (lu via ``apps.ventes.selectors.devis_pour_projet`` —
        jamais un import de ``ventes.models``). JAMAIS automatique sur
        ``devis_accepted`` (le chantier auto existe déjà côté
        ``installations``) : action UTILISATEUR uniquement.

        Un devis d'une autre société, inexistant, ou non ACCEPTÉ → 404. Un
        re-run sur le même devis (déjà lié) → 400.
        """
        from apps.ventes.selectors import devis_pour_projet

        devis_id = request.data.get('devis_id')
        if not devis_id:
            return Response(
                {'devis_id': 'devis_id est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        devis_data = devis_pour_projet(devis_id, request.user.company)
        if devis_data is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            resultat = services.creer_projet_depuis_devis(
                devis_data, company=request.user.company, user=request.user)
        except services.DevisVersProjetError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ProjetSerializer(resultat['projet']).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='generer-plan-ia')
    def generer_plan_ia(self, request, pk=None):
        """Propose un brouillon de WBS via l'IA depuis un devis lié (XPRJ29).

        Corps : ``devis_id`` (obligatoire), ``type_installation`` (optionnel,
        défaut ``residentiel``). Key-gated sur la clé LLM existante
        (``GROQ_API_KEY``/provider) — SANS clé, réponse 503 propre (aucune
        écriture). Ne matérialise RIEN : renvoie la PROPOSITION JSON, à
        matérialiser via ``confirmer-plan-ia`` après relecture utilisateur.
        La société est garantie par ``get_object`` (queryset scopé société) :
        un projet d'une autre société → 404. Un devis d'une autre société,
        inexistant ou non ACCEPTÉ → 404.
        """
        from apps.ventes.selectors import devis_pour_projet

        projet = self.get_object()
        devis_id = request.data.get('devis_id')
        if not devis_id:
            return Response(
                {'devis_id': 'devis_id est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        devis_data = devis_pour_projet(devis_id, projet.company)
        if devis_data is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        type_installation = request.data.get(
            'type_installation', 'residentiel')
        try:
            plan = services.proposer_plan_taches_ia(
                devis_data, type_installation, user=request.user)
        except services.PlanTachesIAIndisponible as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except services.PlanTachesIAError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(plan)

    @action(detail=True, methods=['post'], url_path='confirmer-plan-ia')
    def confirmer_plan_ia(self, request, pk=None):
        """Matérialise un plan de tâches PROPOSÉ après confirmation (XPRJ29).

        Corps : ``taches`` (liste, forme ``{code, libelle, phase,
        duree_jours, dependances_fs}`` — celle renvoyée par
        ``generer-plan-ia``, éventuellement éditée par l'utilisateur avant
        confirmation). Action EXPLICITE utilisateur : jamais automatique.
        Crée phases/tâches/dépendances (voir ``services.
        materialiser_plan_taches``). La société est garantie par
        ``get_object`` : un projet d'une autre société → 404.
        """
        projet = self.get_object()
        taches = request.data.get('taches')
        if not isinstance(taches, list) or not taches:
            return Response(
                {'taches': 'Une liste de tâches non vide est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            creees = services.materialiser_plan_taches(
                projet, {'taches': taches})
        except services.PlanTachesIAError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            TacheSerializer(creees, many=True).data,
            status=status.HTTP_201_CREATED)

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
            cible_type=ProjetActivity.CibleType.PROJET,
            cible_id=projet.id,
            old_value=old,
            new_value=target,
            auteur=request.user,
        )
        services.notifier_transition_projet(
            projet, ancien_statut=old, nouveau_statut=target,
            user=request.user)
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
        ``?export=xlsx`` télécharge le plan de tâches à PLAT (XPRJ24 : code
        WBS, libellé, parent, dates, charge, statut, assigné, dépendances) au
        lieu de l'arbre JSON (le pattern DRF ``?format=`` réservé est évité).
        """
        projet = self.get_object()
        if request.query_params.get('export') == 'xlsx':
            from apps.records.xlsx import build_xlsx_response

            lignes = services.exporter_taches(projet)
            rows = [
                [ligne[champ] for champ in services.EXPORT_TACHES_ENTETES]
                for ligne in lignes
            ]
            return build_xlsx_response(
                f'plan_taches_{projet.code}.xlsx',
                services.EXPORT_TACHES_ENTETES, rows,
                sheet_title='Plan de tâches')
        return Response(selectors.arbre_taches(projet))

    @action(detail=True, methods=['post'], url_path='importer-taches')
    def importer_taches(self, request, pk=None):
        """Importe un plan de tâches (WBS) CSV/xlsx (XPRJ24).

        Corps : ``lignes`` (liste de dicts suivant
        ``services.EXPORT_TACHES_ENTETES`` — le frontend parse le
        CSV/xlsx et poste le tableau). DRY-RUN par DÉFAUT (``?confirm=1``
        pour écrire, transaction atomique) : les lignes invalides sont
        rapportées SANS RIEN écrire. La société est garantie par
        ``get_object`` : un projet d'une autre société → 404.
        """
        projet = self.get_object()
        lignes = request.data.get('lignes')
        if not isinstance(lignes, list) or not lignes:
            return Response(
                {'lignes': 'Une liste de lignes non vide est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        confirm = request.query_params.get('confirm') in ('1', 'true', 'True')
        try:
            resultat = services.importer_taches(
                projet, lignes, confirm=confirm)
        except services.ImportTachesError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultat)

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

    @action(detail=True, methods=['get'], url_path='penalites-retard')
    def penalites_retard(self, request, pk=None):
        """Exposition COURANTE aux pénalités de retard d'un marché public
        (XPRJ27) — donnée INTERNE de pilotage, jamais dans un document client.

        La société est garantie par ``get_object`` (queryset scopé société) :
        un projet d'une autre société → 404. Délègue au sélecteur
        ``penalites_retard`` (lecture seule) : avant le délai contractuel →
        exposition nulle ; un projet PRIVÉ (champs marché-public absents) →
        ``applicable=False`` sans erreur.
        """
        projet = self.get_object()
        return Response(selectors.penalites_retard(projet))

    @action(detail=True, methods=['post'], url_path='lien-evaluation')
    def lien_evaluation(self, request, pk=None):
        """Crée/renvoie le lien tokenisé d'évaluation CSAT du projet (ZPRJ7).

        IDEMPOTENT (relation 1–1 — ``get_or_create``) : un second appel
        renvoie le MÊME lien (jamais de nouveau jeton, jamais de doublon). À
        envoyer au client à la CLÔTURE du projet. La société est garantie par
        ``get_object`` : un projet d'une autre société → 404.
        """
        projet = self.get_object()
        evaluation, _ = EvaluationProjet.objects.get_or_create(
            company=projet.company, projet=projet)
        return Response({
            'projet_id': projet.id,
            'token': evaluation.token,
            'deja_soumis': evaluation.soumis_le is not None,
        })

    @action(detail=True, methods=['get'], url_path='matrice-risques')
    def matrice_risques(self, request, pk=None):
        """Matrice des risques P × I (heatmap 5×5) du projet (ZPRJ8).

        La société est garantie par ``get_object`` (queryset scopé société) :
        un projet d'une autre société → 404. Délègue au sélecteur
        ``matrice_risques`` (lecture seule) : seuls les risques
        ouverts/surveillés comptent dans la grille, les clos/maîtrisés sont
        exclus ; un projet sans risque actif renvoie une grille vide propre.
        Réservé aux données internes (responsable/admin).
        """
        projet = self.get_object()
        return Response(selectors.matrice_risques(projet))

    @action(detail=True, methods=['get'], url_path='couts-engages-reels')
    def couts_engages_reels(self, request, pk=None):
        """Coûts ENGAGÉS/RÉELS vs BUDGET (PROJ21) par catégorie (PROJ22).

        Pour chaque catégorie (matériel / main-d'œuvre / sous-traitance /
        divers) : budget prévisionnel, réel engagé, écart (budget − réel) et
        écart % (None si budget == 0 — garde division-par-zéro), plus une note
        quand une source de réel n'est pas disponible. Le réel de la
        main-d'œuvre vient des affectations internes ; les factures
        fournisseur/achats (matériel/sous-traitance) sont rattachées via
        ``ProjetLien`` et DÉGRADENT proprement (réel à 0 + note) tant qu'aucune
        app cible n'expose un sélecteur de montant — jamais d'import d'un modèle
        d'une autre app (frontière cross-app).

        La société est garantie par ``get_object`` (queryset scopé société) :
        un projet d'une autre société → 404. Lecture seule.
        """
        projet = self.get_object()
        data = selectors.couts_engages_vs_reels(
            request.user.company, projet)
        return Response({
            'budget_id': data['budget_id'],
            'budget_version': data['budget_version'],
            'budget_statut': data['budget_statut'],
            'nb_liens_depense': data['nb_liens_depense'],
            'par_categorie': [
                {
                    'categorie': ligne['categorie'],
                    'budget': str(ligne['budget']),
                    'reel': str(ligne['reel']),
                    'ecart': str(ligne['ecart']),
                    'ecart_pct': (
                        str(ligne['ecart_pct'])
                        if ligne['ecart_pct'] is not None else None),
                    'note': ligne['note'],
                }
                for ligne in data['par_categorie']
            ],
            'total': {
                'budget': str(data['total']['budget']),
                'reel': str(data['total']['reel']),
                'ecart': str(data['total']['ecart']),
                'ecart_pct': (
                    str(data['total']['ecart_pct'])
                    if data['total']['ecart_pct'] is not None else None),
            },
        })

    @action(detail=True, methods=['get'], url_path='alertes-budget')
    def alertes_budget(self, request, pk=None):
        """Alertes de DÉPASSEMENT budgétaire du projet (PROJ23).

        Paramètre optionnel ``?seuil_pct=N`` (0–100, défaut 90) : seuil de
        consommation à partir duquel une catégorie / le total est signalé en
        ``alerte`` (et en ``depassement`` au-delà de 100 %). Un seuil invalide
        (non numérique / hors borne) est ramené au défaut / borné.

        La société est garantie par ``get_object`` (queryset scopé société) :
        un projet d'une autre société → 404. Lecture seule. Délègue au sélecteur
        ``alertes_depassement_budgetaire`` (s'appuie sur PROJ22).
        """
        projet = self.get_object()
        seuil_raw = request.query_params.get('seuil_pct')
        seuil = None
        if seuil_raw is not None:
            try:
                seuil = float(seuil_raw)
            except (TypeError, ValueError):
                seuil = None
        data = selectors.alertes_depassement_budgetaire(
            request.user.company, projet, seuil_pct=seuil)

        def _num(value):
            return str(value) if value is not None else None

        return Response({
            'budget_id': data['budget_id'],
            'budget_version': data['budget_version'],
            'budget_statut': data['budget_statut'],
            'seuil_pct': str(data['seuil_pct']),
            'en_depassement': data['en_depassement'],
            'nb_alertes': data['nb_alertes'],
            'total': {
                'budget': str(data['total']['budget']),
                'reel': str(data['total']['reel']),
                'depassement': str(data['total']['depassement']),
                'consommation_pct': _num(data['total']['consommation_pct']),
                'niveau': data['total']['niveau'],
            },
            'alertes': [
                {
                    'portee': a['portee'],
                    'categorie': a['categorie'],
                    'budget': str(a['budget']),
                    'reel': str(a['reel']),
                    'depassement': str(a['depassement']),
                    'consommation_pct': _num(a['consommation_pct']),
                    'niveau': a['niveau'],
                }
                for a in data['alertes']
            ],
        })

    @action(detail=True, methods=['get'], url_path='synthese-temps')
    def synthese_temps(self, request, pk=None):
        """Synthèse des temps imputés au projet (PROJ24) — lecture seule.

        Total heures + coût INTERNE figé, ventilé par ressource et par tâche.
        La société est garantie par ``get_object`` (queryset scopé société) :
        un projet d'une autre société → 404. Délègue au sélecteur
        ``synthese_temps_projet``. Le coût est INTERNE — jamais exposé au client.
        """
        projet = self.get_object()
        data = selectors.synthese_temps_projet(projet)
        return Response({
            'total_heures': str(data['total_heures']),
            'total_cout': str(data['total_cout']),
            'heures_facturables': str(data['heures_facturables']),
            'heures_non_facturables': str(data['heures_non_facturables']),
            'nb_saisies': data['nb_saisies'],
            'par_ressource': [
                {
                    'ressource_id': r['ressource_id'],
                    'ressource_nom': r['ressource_nom'],
                    'heures': str(r['heures']),
                    'cout': str(r['cout']),
                    'heures_facturables': str(r['heures_facturables']),
                }
                for r in data['par_ressource']
            ],
            'par_tache': [
                {
                    'tache_id': t['tache_id'],
                    'tache_libelle': t['tache_libelle'],
                    'heures': str(t['heures']),
                    'cout': str(t['cout']),
                }
                for t in data['par_tache']
            ],
            'par_activite': [
                {
                    'type_activite': a['type_activite'],
                    'type_activite_display': a['type_activite_display'],
                    'heures': str(a['heures']),
                    'heures_facturables': str(a['heures_facturables']),
                }
                for a in data['par_activite']
            ],
        })

    @action(detail=True, methods=['post'], url_path='facturer-temps')
    def facturer_temps(self, request, pk=None):
        """XPRJ3 — Facture en régie (T&M) les temps approuvés d'une période.

        Corps : ``debut`` et ``fin`` (``YYYY-MM-DD``, obligatoires, bornes
        inclusives). Ne sélectionne que les timesheets APPROUVÉES + facturables
        + non encore facturées (``facture_id`` nul) — un re-run sur la même
        période est IDEMPOTENT (0 ligne re-facturée). La société est garantie
        par ``get_object`` (queryset scopé société) : un projet d'une autre
        société → 404. Délègue à ``services.facturer_temps_projet`` (écritures
        atomiques, création de la ``Facture`` via ``ventes.services``).
        """
        projet = self.get_object()
        debut = _parse_date_param(request.data.get('debut'))
        fin = _parse_date_param(request.data.get('fin'))
        if debut is None or fin is None:
            return Response(
                {'detail': 'Les dates « debut » et « fin » (YYYY-MM-DD) sont '
                           'obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        if fin < debut:
            return Response(
                {'detail': 'La date de fin ne peut pas précéder la date de '
                           'début.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = services.facturer_temps_projet(
                projet, debut=debut, fin=fin, user=request.user)
        except services.FacturationRegieError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        facture = resultat['facture']
        return Response({
            'facture_id': facture.id,
            'facture_reference': facture.reference,
            'montant_ht': str(resultat['montant_ht']),
            'nb_lignes': resultat['nb_lignes'],
            'groupes': [
                {
                    'tache_id': g['tache_id'],
                    'tache_libelle': g['tache_libelle'],
                    'type_activite': g['type_activite'],
                    'heures': str(g['heures']),
                    'montant': str(g['montant']),
                }
                for g in resultat['groupes']
            ],
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='consommation-matiere')
    def consommation_matiere(self, request, pk=None):
        """Consommation matière RÉELLE vs BoM prévisionnelle (PROJ25).

        BoM prévisionnelle = lignes de budget « matériel » du budget de
        référence ; consommé agrégé via les apps cibles (chantiers/achats) —
        dégrade proprement à 0 + note tant qu'aucun sélecteur cross-app n'expose
        ce montant (frontière cross-app). La société est garantie par
        ``get_object`` (queryset scopé société) : un projet d'une autre société
        → 404. Lecture seule.
        """
        projet = self.get_object()
        data = selectors.consommation_matiere_vs_bom(projet)
        return Response({
            'budget_id': data['budget_id'],
            'budget_version': data['budget_version'],
            'bom_prevu': str(data['bom_prevu']),
            'consomme': str(data['consomme']),
            'ecart': str(data['ecart']),
            'ecart_pct': (
                str(data['ecart_pct'])
                if data['ecart_pct'] is not None else None),
            'source': data['source'],
            'note': data['note'],
        })

    @action(detail=True, methods=['get'], url_path='pnl')
    def pnl(self, request, pk=None):
        """Compte de résultat (P&L) CONSOLIDÉ du projet (PROJ26 — interne).

        Revenu (devis/factures rattachés, dégradé cross-app) − coûts (budget
        prévisionnel + réel consolidé affectations + timesheets), marges prév. /
        réelle et marge % réelle (None si revenu nul). Donnée 100 % INTERNE de
        pilotage — JAMAIS exposée au client. La société est garantie par
        ``get_object`` (queryset scopé société) : un projet d'une autre société
        → 404. Lecture seule.
        """
        projet = self.get_object()
        data = selectors.pnl_projet(request.user.company, projet)
        return Response({
            'revenu': str(data['revenu']),
            'note_revenu': data['note_revenu'],
            'cout_budget': str(data['cout_budget']),
            'cout_reel': str(data['cout_reel']),
            'cout_reel_affectations': str(data['cout_reel_affectations']),
            'cout_reel_timesheets': str(data['cout_reel_timesheets']),
            'marge_prev': str(data['marge_prev']),
            'marge_reelle': str(data['marge_reelle']),
            'marge_pct_reelle': (
                str(data['marge_pct_reelle'])
                if data['marge_pct_reelle'] is not None else None),
            'budget_id': data['budget_id'],
            'budget_version': data['budget_version'],
            'couts_par_categorie': [
                {
                    'categorie': ligne['categorie'],
                    'budget': str(ligne['budget']),
                    'reel': str(ligne['reel']),
                }
                for ligne in data['couts_par_categorie']
            ],
        })

    @action(detail=True, methods=['get'], url_path='jalons-facturables')
    def jalons_facturables(self, request, pk=None):
        """Jalons de facturation déclenchables par l'avancement (PROJ27).

        Liste les jalons du projet avec leur ``facturation_pct``, leur statut,
        s'ils sont ATTEINTS et donc FACTURABLES, et le montant théorique
        (% × budget interne). La société est garantie par ``get_object``
        (queryset scopé société) : un projet d'une autre société → 404. Lecture
        seule. Le déclenchement effectif se fait via ``jalons/<id>/facturer/``.
        """
        projet = self.get_object()
        data = selectors.jalons_facturables(projet)
        return Response({
            'base_montant': str(data['base_montant']),
            'total_pct_facture': str(data['total_pct_facture']),
            'jalons': [
                {
                    'id': j['id'],
                    'libelle': j['libelle'],
                    'facturation_pct': str(j['facturation_pct']),
                    'statut': j['statut'],
                    'atteint': j['atteint'],
                    'facturable': j['facturable'],
                    'montant': str(j['montant']),
                }
                for j in data['jalons']
            ],
        })

    @action(detail=True, methods=['get'], url_path='avancement-vs-facture')
    def avancement_vs_facture(self, request, pk=None):
        """Compare l'avancement physique au % facturé du projet (PROJ28).

        Avancement = roll-up pondéré par charge (PROJ9) ; facturé = somme des
        ``facturation_pct`` des jalons atteints (bornée à 100). L'écart signale
        une sous-facturation (> 0) ou une facturation d'avance (< 0). La société
        est garantie par ``get_object`` (queryset scopé société) : un projet
        d'une autre société → 404. Lecture seule.
        """
        projet = self.get_object()
        data = selectors.avancement_vs_facture(projet)
        return Response({
            'avancement_pct': str(data['avancement_pct']),
            'facture_pct': str(data['facture_pct']),
            'ecart_pct': str(data['ecart_pct']),
            'base_montant': str(data['base_montant']),
            'montant_facture': str(data['montant_facture']),
            'montant_avancement': str(data['montant_avancement']),
        })

    @action(detail=False, methods=['get'], url_path='portefeuille')
    def portefeuille(self, request):
        """Tableau de bord PORTEFEUILLE de la société (PROJ36) — interne/admin.

        Une ligne par projet (avancement / retards / risques / marge réelle /
        charge) + totaux portefeuille. Filtres : ``?statut=<statut>``,
        ``?seuil_jours=N`` (horizon « à risque », défaut 7). La société est
        imposée côté serveur (``request.user.company``) — jamais lue du corps.
        Donnée 100 % INTERNE de pilotage. Lecture seule.
        """
        statut = request.query_params.get('statut') or None
        seuil_raw = request.query_params.get('seuil_jours')
        seuil = None
        if seuil_raw is not None:
            try:
                seuil = max(0, int(seuil_raw))
            except (ValueError, TypeError):
                seuil = None
        data = selectors.tableau_portefeuille(
            request.user.company, statut=statut, seuil_jours=seuil)
        return Response({
            'nb_projets': data['nb_projets'],
            'total_marge_reelle': str(data['total_marge_reelle']),
            'total_charge': str(data['total_charge']),
            'total_retards': data['total_retards'],
            'total_risques': data['total_risques'],
            'projets': [
                {
                    'projet_id': p['projet_id'],
                    'code': p['code'],
                    'nom': p['nom'],
                    'statut': p['statut'],
                    'avancement_pct': p['avancement_pct'],
                    'nb_retards': p['nb_retards'],
                    'nb_risques': p['nb_risques'],
                    'marge_reelle': str(p['marge_reelle']),
                    'charge_totale': str(p['charge_totale']),
                    'derniere_sante': p['derniere_sante'],
                }
                for p in data['projets']
            ],
        })

    @action(detail=True, methods=['get'], url_path='evm')
    def evm(self, request, pk=None):
        """Valeur acquise (EVM) LÉGER du projet (PROJ29) — interne/admin.

        BAC / EV / AC / PV + CV / SV / CPI / SPI. PV s'appuie sur la fraction de
        calendrier écoulée entre ``date_debut`` et ``date_fin_prevue`` à la
        ``?date=YYYY-MM-DD`` (défaut aujourd'hui) ; sans dates de projet, PV et
        SV/SPI sont None. Donnée 100 % INTERNE de pilotage. La société est
        garantie par ``get_object`` (queryset scopé société) : un projet d'une
        autre société → 404. Lecture seule.
        """
        projet = self.get_object()
        date_ref = _parse_date_param(request.query_params.get('date'))
        data = selectors.evm_projet(
            request.user.company, projet, date_reference=date_ref)

        def _num(value):
            return str(value) if value is not None else None

        return Response({
            'bac': str(data['bac']),
            'ev': str(data['ev']),
            'ac': str(data['ac']),
            'pv': _num(data['pv']),
            'avancement_pct': str(data['avancement_pct']),
            'fraction_ecoulee_pct': _num(data['fraction_ecoulee_pct']),
            'cv': str(data['cv']),
            'sv': _num(data['sv']),
            'cpi': _num(data['cpi']),
            'spi': _num(data['spi']),
            'date_reference': data['date_reference'].isoformat(),
        })

    @action(detail=True, methods=['get'], url_path='prevision-fin')
    def prevision_fin(self, request, pk=None):
        """Prévision fin de projet — ETC/EAC par catégorie (XPRJ16).

        Par catégorie de budget (PROJ21) : ETC ajusté du CPI courant (EVM
        PROJ29, garde CPI nul/absent), EAC = réel + ETC, écart EAC vs budget +
        %. Donnée 100 % INTERNE de pilotage — jamais dans le portail client.
        La société est garantie par ``get_object`` : un projet d'une autre
        société → 404.
        """
        projet = self.get_object()
        date_ref = _parse_date_param(request.query_params.get('date'))
        data = selectors.prevision_fin_projet(projet, date_reference=date_ref)

        def _num(value):
            return str(value) if value is not None else None

        return Response({
            'cpi': _num(data['cpi']),
            'budget_total': str(data['budget_total']),
            'reel_total': str(data['reel_total']),
            'etc_total': str(data['etc_total']),
            'eac_total': str(data['eac_total']),
            'ecart_eac_budget_total': str(data['ecart_eac_budget_total']),
            'ecart_eac_budget_total_pct': _num(
                data['ecart_eac_budget_total_pct']),
            'par_categorie': [
                {
                    'categorie': ligne['categorie'],
                    'budget': str(ligne['budget']),
                    'reel': str(ligne['reel']),
                    'etc': str(ligne['etc']),
                    'eac': str(ligne['eac']),
                    'ecart_eac_budget': str(ligne['ecart_eac_budget']),
                    'ecart_eac_budget_pct': _num(
                        ligne['ecart_eac_budget_pct']),
                }
                for ligne in data['par_categorie']
            ],
        })

    @action(detail=True, methods=['get'], url_path='burndown')
    def burndown(self, request, pk=None):
        """Burndown du projet — charge restante vs ligne idéale (XPRJ17).

        Corps : ``?debut=&fin=`` (YYYY-MM-DD, obligatoires). Série HEBDOMADAIRE
        de charge restante (reconstituée depuis ``date_fin_reelle``) vs ligne
        idéale + heures loguées cumulées. Un projet sans charge estimée →
        réponse vide propre (``points`` = []). La société est garantie par
        ``get_object`` : un projet d'une autre société → 404.
        """
        projet = self.get_object()
        debut = _parse_date_param(request.query_params.get('debut'))
        fin = _parse_date_param(request.query_params.get('fin'))
        if debut is None or fin is None or fin < debut:
            return Response(
                {'detail': 'debut et fin (YYYY-MM-DD, fin >= debut) sont '
                           'obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        data = selectors.burndown(projet, debut, fin)
        return Response({
            'charge_totale': str(data['charge_totale']),
            'points': [
                {
                    'date': p['date'],
                    'charge_restante': str(p['charge_restante']),
                    'charge_ideale': str(p['charge_ideale']),
                    'heures_loguees_cumulees': str(
                        p['heures_loguees_cumulees']),
                }
                for p in data['points']
            ],
        })

    @action(detail=True, methods=['get'], url_path='rapport-avancement-pdf')
    def rapport_avancement_pdf(self, request, pk=None):
        """PDF INTERNE « Point d'avancement projet » (ZPRJ9).

        Rendu via le pipeline PDF legacy (WeasyPrint) — PAS le moteur premium
        ``/proposal`` réservé aux devis client (règle #4) : ce document est
        strictement interne (peut exposer budget/coûts) et n'est jamais
        transmis au client par ce chemin. La société est garantie par
        ``get_object`` : un projet d'une autre société → 404. Un projet sans
        jalon/risque/temps produit un PDF dégradé propre (pas de crash).
        """
        from django.http import HttpResponse

        from . import reports
        projet = self.get_object()
        pdf_bytes = reports.rapport_avancement_pdf(projet)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="avancement-projet-{projet.id}.pdf"')
        return resp

    @action(detail=True, methods=['post'], url_path='cloturer')
    def cloturer(self, request, pk=None):
        """Clôture le projet + enregistre le RETOUR D'EXPÉRIENCE (PROJ38).

        Corps : ``date_cloture`` (obligatoire, YYYY-MM-DD), ``date_reception``
        (optionnelle), ``points_positifs`` / ``points_amelioration`` /
        ``recommandations`` (REX). Crée/maj la clôture 1–1 et passe le projet à
        TERMINÉ (transition journalisée). Un projet ANNULÉ → 400. ``cloture_par``
        est posé côté serveur. La société est garantie par ``get_object``
        (queryset scopé société) : un projet d'une autre société → 404.
        """
        projet = self.get_object()
        date_cloture = _parse_date_param(request.data.get('date_cloture'))
        if date_cloture is None:
            return Response(
                {'date_cloture': 'La date de clôture (YYYY-MM-DD) est '
                                 'obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        date_reception = _parse_date_param(request.data.get('date_reception'))
        try:
            cloture = services.cloturer_projet(
                projet,
                date_cloture=date_cloture,
                date_reception=date_reception,
                points_positifs=request.data.get('points_positifs', '') or '',
                points_amelioration=request.data.get(
                    'points_amelioration', '') or '',
                recommandations=request.data.get('recommandations', '') or '',
                auteur=request.user)
        except services.ClotureError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ClotureProjetSerializer(cloture).data,
            status=status.HTTP_201_CREATED)


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

    def perform_update(self, serializer):
        """Émet ``PROJET_PHASE_CHANGE`` (XPRJ23) au changement de ``statut``.

        Best-effort ABSOLU (voir ``services.notifier_transition_phase``) : la
        mise à jour de la phase n'est JAMAIS bloquée par une règle
        d'automatisation en erreur.
        """
        instance = serializer.instance
        ancien_statut = instance.statut
        nouveau_statut = serializer.validated_data.get(
            'statut', ancien_statut)
        phase = serializer.save()
        services.notifier_transition_phase(
            phase, ancien_statut=ancien_statut,
            nouveau_statut=nouveau_statut, user=self.request.user)


class TacheViewSet(_GestionProjetBaseViewSet):
    """Tâches & sous-tâches (WBS) d'un projet — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; les FK reçus (``projet``,
    ``phase``, ``parent``) sont validés même-société par le sérialiseur (cible
    d'une autre société → 400). Filtres optionnels : ``?projet=<id>``,
    ``?parent=<id>`` (sous-tâches directes), ``?racines=1`` (tâches sans
    parent), ``?statut=<statut>``, ``?assigne=<id>``, ``?priorite=<priorite>``,
    ``?etiquette=<tag>`` (XPRJ10 — correspondance CSV, insensible à la casse).
    Recherche par libellé / code WBS ; tri par défaut ``ordre`` puis ``id``.
    L'arborescence complète est servie par ``projets/<id>/taches/``.
    """
    queryset = Tache.objects.select_related(
        'projet', 'phase', 'parent', 'assigne').all()
    serializer_class = TacheSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'code_wbs']
    ordering_fields = ['ordre', 'code_wbs', 'statut', 'priorite', 'id']

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
        assigne = self.request.query_params.get('assigne')
        if assigne:
            qs = qs.filter(assigne_id=assigne)
        priorite = self.request.query_params.get('priorite')
        if priorite:
            qs = qs.filter(priorite=priorite)
        etiquette = self.request.query_params.get('etiquette')
        if etiquette:
            qs = qs.filter(etiquettes__icontains=etiquette)
        return qs

    def perform_update(self, serializer):
        """Pose ``date_fin_reelle`` côté serveur au passage à TERMINE (XPRJ17)
        et journalise les champs sensibles modifiés (XPRJ26).

        Réinitialisée si le statut repasse à un état non-terminé (correction
        d'une clôture erronée). Base du burndown (charge restante reconstituée
        à chaque date). Capture les valeurs AVANT sauvegarde pour
        ``services.journaliser_modification_tache`` (statut, dates prévues,
        charge, assigné) — une entrée ``ProjetActivity`` par champ RÉELLEMENT
        changé, auteur posé côté serveur.
        """
        instance = serializer.instance
        anciennes_valeurs = {
            champ: getattr(instance, champ)
            for champ in services.TACHE_CHAMPS_SUIVIS}
        nouveau_statut = serializer.validated_data.get(
            'statut', instance.statut)
        if nouveau_statut == Tache.Statut.TERMINE \
                and instance.statut != Tache.Statut.TERMINE:
            from datetime import date as _date
            serializer.save(date_fin_reelle=_date.today())
        elif nouveau_statut != Tache.Statut.TERMINE \
                and instance.date_fin_reelle is not None:
            serializer.save(date_fin_reelle=None)
        else:
            serializer.save()
        services.journaliser_modification_tache(
            serializer.instance, anciennes_valeurs, auteur=self.request.user)

    @action(detail=False, methods=['get'], url_path='mes-taches')
    def mes_taches(self, request):
        """Tâches non terminées de l'utilisateur courant, tri par urgence.

        Transverse à TOUS les projets de la société (XPRJ12) : tâches où
        l'utilisateur est ``assigne`` (XPRJ10) ou affecté (directement ou via
        une équipe, ``AffectationRessource``). Isolation garantie côté
        sélecteur (toujours scopé à ``request.user.company``) — un utilisateur
        ne voit jamais les tâches d'un autre.
        """
        return Response(selectors.mes_taches(request.user))

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

    @action(detail=True, methods=['post'], url_path='demarrer-chrono')
    def demarrer_chrono(self, request, pk=None):
        """Démarre un chrono sur cette tâche pour l'utilisateur courant (XPRJ5).

        Un seul chrono actif par utilisateur : démarrer ici arrête
        implicitement un chrono déjà en cours sur une autre tâche. La société
        est garantie par ``get_object`` : une tâche d'une autre société → 404.
        """
        tache = self.get_object()
        chrono = services.demarrer_chrono(tache, request.user)
        return Response(
            ChronoEnCoursSerializer(chrono).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='arreter-chrono')
    def arreter_chrono(self, request, pk=None):
        """Arrête le chrono actif de l'utilisateur et crée la timesheet (XPRJ5).

        Par DÉFAUT, la durée est arrondie selon le réglage temps de la
        société (``ReglageTemps`` — ZPRJ1, pas/mode paramétrables via
        ``reglages-temps/``) ; un ``pas_minutes`` explicite dans le corps de
        requête reste supporté (override ponctuel, arrondi au SUPÉRIEUR de ce
        pas — compatibilité). Refuse (400) si l'utilisateur n'a aucun chrono
        actif ou aucun profil ressource lié.
        """
        pas_minutes_raw = request.data.get('pas_minutes')
        pas_minutes = None
        if pas_minutes_raw is not None:
            try:
                pas_minutes = int(pas_minutes_raw)
            except (TypeError, ValueError):
                pas_minutes = None
        try:
            timesheet = services.arreter_chrono(
                request.user, pas_minutes=pas_minutes)
        except services.ChronoError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TimesheetSerializer(timesheet).data)


class ChronoActifViewSet(viewsets.ViewSet):
    """Chrono actif GLOBAL de l'utilisateur courant (XPRJ5) — lecture seule.

    Indicateur transverse (hors ``Tache``) : ``GET /chrono-actif/`` renvoie le
    chrono en cours de l'utilisateur (n'importe quelle tâche), ou 204 si aucun.
    Toujours scopé à l'utilisateur COURANT (jamais un autre — pas de paramètre
    d'utilisateur en entrée).
    """
    permission_classes = [IsResponsableOrAdmin]

    def list(self, request):
        chrono = ChronoEnCours.objects.select_related(
            'tache', 'tache__projet').filter(user=request.user).first()
        if chrono is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(ChronoEnCoursSerializer(chrono).data)


class ReglageTempsViewSet(viewsets.ViewSet):
    """Réglages société d'encodage des temps (ZPRJ1) — singleton par société.

    ``GET reglages-temps/mon-reglage/`` / ``PATCH reglages-temps/mon-reglage/``
    lisent/éditent le réglage de l'appelant (créé à la demande — ``get_or_
    create``, jamais plusieurs fois pour une même société). ``company`` posée
    CÔTÉ SERVEUR, jamais lue du corps de requête. Consommé par ``services.
    arrondir_duree`` (chrono XPRJ5) et par les sélecteurs ``plan_de_charge``/
    ``nivellement_charge`` (``heures_par_jour``). Même motif que
    ``apps.rh.views.ReglageRHViewSet`` (« mon-reglage »).
    """
    permission_classes = [IsResponsableOrAdmin]

    @action(detail=False, methods=['get', 'patch'], url_path='mon-reglage')
    def mon_reglage(self, request):
        reglage = services.get_or_create_reglage_temps(request.user.company)
        if request.method == 'PATCH':
            ser = ReglageTempsSerializer(
                reglage, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        return Response(ReglageTempsSerializer(reglage).data)


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

    def perform_update(self, serializer):
        """Journalise les champs sensibles modifiés d'un jalon (XPRJ26).

        Capture les valeurs AVANT sauvegarde pour
        ``services.journaliser_modification_jalon`` (date prévue, statut,
        facturation_pct) — une entrée ``ProjetActivity`` par champ RÉELLEMENT
        changé, auteur posé côté serveur. Comportement de sauvegarde inchangé.
        """
        instance = serializer.instance
        anciennes_valeurs = {
            champ: getattr(instance, champ)
            for champ in services.JALON_CHAMPS_SUIVIS}
        serializer.save()
        services.journaliser_modification_jalon(
            serializer.instance, anciennes_valeurs, auteur=self.request.user)

    @action(detail=True, methods=['post'], url_path='facturer')
    def facturer(self, request, pk=None):
        """Déclenche la facturation liée à ce jalon ATTEINT (PROJ27).

        Le jalon doit être ATTEINT et porter un ``facturation_pct`` > 0 (sinon
        400). L'écriture de la facture client passe par ``ventes.services``
        (frontière cross-app) ; tant qu'aucune entrée dédiée n'y existe, on
        renvoie une PROPOSITION (montant calculé, aucune facture créée). La
        société est garantie par ``get_object`` (queryset scopé société) : un
        jalon d'une autre société → 404.
        """
        jalon = self.get_object()
        try:
            data = services.declencher_facturation_jalon(jalon)
        except services.FacturationJalonError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'jalon_id': data['jalon_id'],
            'facturation_pct': str(data['facturation_pct']),
            'montant': str(data['montant']),
            'facture_creee': data['facture_creee'],
            'note': data['note'],
        })


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

    @action(detail=True, methods=['post'], url_path='seed-feries')
    def seed_feries(self, request, pk=None):
        """Pré-remplit les jours fériés marocains depuis ``core/calendar.py``.

        Corps/query ``?annee=`` (obligatoire). IDEMPOTENT : jamais de doublon
        (``unique (calendrier, date)``). Renvoie les dates créées + le nombre
        déjà présentes. Si l'année n'a pas de jeu de fêtes MOBILES codé, le
        champ ``fetes_mobiles_manquantes`` signale qu'elles restent à saisir
        manuellement (Aïd, 1 Moharram, Mawlid). La société est garantie par
        ``get_object`` : un calendrier d'une autre société → 404.
        """
        calendrier = self.get_object()
        annee_raw = (
            request.query_params.get('annee') or request.data.get('annee'))
        try:
            annee = int(annee_raw)
        except (TypeError, ValueError):
            return Response(
                {'annee': 'Le paramètre « annee » (entier) est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        resultat = services.seeder_feries_calendrier(calendrier, annee)
        return Response({
            'crees': [d.isoformat() for d in resultat['crees']],
            'nb_crees': len(resultat['crees']),
            'nb_deja_presents': resultat['nb_deja_presents'],
            'fetes_mobiles_manquantes': resultat['fetes_mobiles_manquantes'],
        })


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

    @action(detail=False, methods=['post'], url_path='publier')
    def publier(self, request):
        """Publie un lot d'affectations BROUILLON (ZPRJ2) et notifie chaque
        ressource concernée UNE FOIS.

        Corps : soit ``ids`` (liste d'identifiants), soit ``ressource`` +
        ``debut``/``fin`` (``YYYY-MM-DD``, période). IDEMPOTENT : une
        affectation déjà publiée est ignorée sans erreur (comptée dans
        ``nb_deja_publiees``). ``company`` est TOUJOURS celle de l'appelant.
        """
        ids = request.data.get('ids')
        ressource_id = request.data.get('ressource')
        debut = _parse_date_param(request.data.get('debut'))
        fin = _parse_date_param(request.data.get('fin'))

        if not ids and not (ressource_id and debut and fin):
            return Response(
                {'detail': (
                    "Fournir soit 'ids' (liste), soit 'ressource' + 'debut' "
                    "+ 'fin'.")},
                status=status.HTTP_400_BAD_REQUEST)

        resultat = services.publier_affectations(
            request.user.company, ids=ids, ressource_id=ressource_id,
            debut=debut, fin=fin, auteur=request.user)
        return Response(resultat)

    @action(detail=False, methods=['post'], url_path='copier-semaine')
    def copier_semaine(self, request):
        """Copie le plan de ressources d'une semaine SOURCE vers une semaine
        CIBLE (ZPRJ3) — équivalent « Copy previous week ».

        Corps : ``semaine_source``/``semaine_cible`` (``YYYY-MM-DD``,
        obligatoires — débuts des deux fenêtres de 7 jours), ``ressource``
        ou ``equipe`` (optionnels, filtrent la copie). Saute toute copie qui
        tomberait sur une indisponibilité ou un conflit (rapport détaillé).
        Les nouvelles affectations sont créées en statut BROUILLON (ZPRJ2).
        """
        semaine_source = _parse_date_param(
            request.data.get('semaine_source'))
        semaine_cible = _parse_date_param(request.data.get('semaine_cible'))
        if semaine_source is None or semaine_cible is None:
            return Response(
                {'detail': (
                    "'semaine_source' et 'semaine_cible' (YYYY-MM-DD) sont "
                    "obligatoires.")},
                status=status.HTTP_400_BAD_REQUEST)
        resultat = services.copier_semaine_precedente(
            request.user.company,
            semaine_source=semaine_source, semaine_cible=semaine_cible,
            ressource_id=request.data.get('ressource'),
            equipe_id=request.data.get('equipe'))
        return Response(resultat)

    @action(detail=False, methods=['post'], url_path='auto-affecter')
    def auto_affecter(self, request):
        """Applique (ou simule) l'auto-affectation des tâches en excès (ZPRJ4)
        — équivalent Odoo Planning « Auto Plan ».

        Corps : ``debut``/``fin`` (``YYYY-MM-DD``, obligatoires). Query
        ``?simuler=1`` (PAR DÉFAUT) : ne mute rien, renvoie le plan proposé.
        ``?confirm=1`` : applique réellement (déplace les affectations
        sur-chargées vers les moins chargées disponibles, crée des
        affectations pour les tâches sans affectation), toujours en statut
        BROUILLON (ZPRJ2).
        """
        debut = _parse_date_param(request.data.get('debut'))
        fin = _parse_date_param(request.data.get('fin'))
        if debut is None or fin is None:
            return Response(
                {'detail': "'debut' et 'fin' (YYYY-MM-DD) sont obligatoires."},
                status=status.HTTP_400_BAD_REQUEST)
        confirmer = request.query_params.get('confirm') in (
            '1', 'true', 'True')
        resultat = services.auto_affecter(
            request.user.company, debut, fin, confirmer=confirmer)
        return Response(resultat)


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


class BudgetProjetViewSet(_GestionProjetBaseViewSet):
    """Budgets prévisionnels d'un projet — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; le ``projet`` reçu est
    validé même-société par le sérialiseur (cible d'une autre société → 400).
    Filtres optionnels : ``?projet=<id>``, ``?statut=<statut>``. L'action
    ``total`` renvoie le total prévisionnel ventilé par catégorie (sélecteur
    ``budget_total``). Le budget est INTERNE — jamais exposé au client final.
    """
    queryset = BudgetProjet.objects.select_related('projet').all()
    serializer_class = BudgetProjetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle']
    ordering_fields = ['version', 'statut', 'date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @action(detail=True, methods=['get'])
    def total(self, request, pk=None):
        """Total prévisionnel du budget ventilé par catégorie.

        La société est garantie par ``get_object`` (queryset scopé société) :
        une cible d'une autre société → 404.
        """
        budget = self.get_object()
        agg = selectors.budget_total(budget)
        return Response({
            'total': str(agg['total']),
            'par_categorie': {
                cat: str(montant)
                for cat, montant in agg['par_categorie'].items()
            },
            'nb_lignes': agg['nb_lignes'],
        })


class LigneBudgetProjetViewSet(_GestionProjetBaseViewSet):
    """Lignes d'un budget projet (ventilées par catégorie) — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; le ``budget`` reçu est
    validé même-société par le sérialiseur (cible d'une autre société → 400).
    Filtres optionnels : ``?budget=<id>``, ``?categorie=<categorie>``.
    """
    queryset = LigneBudgetProjet.objects.select_related('budget').all()
    serializer_class = LigneBudgetProjetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle']
    ordering_fields = ['categorie', 'montant_prevu', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        budget = self.request.query_params.get('budget')
        if budget:
            qs = qs.filter(budget_id=budget)
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        return qs


class TimesheetViewSet(_GestionProjetBaseViewSet):
    """Feuilles de temps internes imputées aux projets (PROJ24) — CRUD scopé.

    ``company`` est posée côté serveur (TenantMixin) ; les FK reçus (``projet``,
    ``tache``, ``phase``, ``ressource``) sont validés même-société par le
    sérialiseur (cible d'une autre société → 400). Le ``cout`` est FIGÉ côté
    serveur à la création/édition (``heures`` × coût horaire interne de la
    ressource) — jamais lu du corps de requête, jamais exposé au client.
    Filtres optionnels : ``?projet=<id>``, ``?tache=<id>``, ``?ressource=<id>``,
    ``?debut=YYYY-MM-DD&fin=YYYY-MM-DD`` (saisies dans la fenêtre inclusive).

    XPRJ1 — cycle de vie + verrouillage de période : ``saisi_par`` est posé côté
    serveur à la création ; création/édition/suppression sont REFUSÉES (400) si
    la ``date`` (ou la date CIBLE en cas d'édition) tombe dans une période
    verrouillée (``PeriodeVerrouilleeTemps``) — sauf pour un utilisateur ADMIN
    (``request.user.is_admin_role``). Une timesheet déjà APPROUVÉE ne peut plus
    être éditée ni supprimée (même hors période verrouillée).
    """
    queryset = Timesheet.objects.select_related(
        'projet', 'tache', 'phase', 'ressource').all()
    serializer_class = TimesheetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['commentaire']
    ordering_fields = ['date', 'heures', 'cout', 'id']

    def _est_admin(self):
        return bool(getattr(self.request.user, 'is_admin_role', False))

    def create(self, request, *args, **kwargs):
        date_val = _parse_date_param(request.data.get('date'))
        if date_val is not None:
            try:
                services.verifier_periode_ouverte(
                    request.user.company, date_val, admin=self._est_admin())
            except services.PeriodeVerrouilleeError as exc:
                return Response(
                    {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.statut == Timesheet.Statut.APPROUVEE:
            return Response(
                {'detail': 'Une feuille de temps approuvée ne peut plus être '
                           'modifiée.'},
                status=status.HTTP_400_BAD_REQUEST)
        date_val = _parse_date_param(
            request.data.get('date')) or instance.date
        try:
            services.verifier_periode_ouverte(
                instance.company, date_val, admin=self._est_admin())
            services.verifier_periode_ouverte(
                instance.company, instance.date, admin=self._est_admin())
        except services.PeriodeVerrouilleeError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.statut == Timesheet.Statut.APPROUVEE:
            return Response(
                {'detail': 'Une feuille de temps approuvée ne peut plus être '
                           'supprimée.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            services.verifier_periode_ouverte(
                instance.company, instance.date, admin=self._est_admin())
        except services.PeriodeVerrouilleeError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        ressource = serializer.validated_data.get('ressource')
        heures = serializer.validated_data.get('heures')
        serializer.save(
            company=self.request.user.company,
            saisi_par=self.request.user,
            cout=services.cout_timesheet(ressource, heures))

    def perform_update(self, serializer):
        instance = serializer.instance
        ressource = serializer.validated_data.get('ressource', instance.ressource)
        heures = serializer.validated_data.get('heures', instance.heures)
        serializer.save(cout=services.cout_timesheet(ressource, heures))

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        tache = self.request.query_params.get('tache')
        if tache:
            qs = qs.filter(tache_id=tache)
        ressource = self.request.query_params.get('ressource')
        if ressource:
            qs = qs.filter(ressource_id=ressource)
        debut = self.request.query_params.get('debut')
        fin = self.request.query_params.get('fin')
        if debut and fin:
            qs = qs.filter(date__gte=debut, date__lte=fin)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @action(detail=True, methods=['post'], url_path='soumettre')
    def soumettre(self, request, pk=None):
        """brouillon → soumise."""
        timesheet = self.get_object()
        try:
            services.soumettre_timesheet(timesheet)
        except services.TimesheetTransitionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TimesheetSerializer(timesheet).data)

    @action(detail=True, methods=['post'], url_path='approuver')
    def approuver(self, request, pk=None):
        """soumise → approuvee (palier Responsable/Admin — déjà gardé en vue)."""
        timesheet = self.get_object()
        try:
            services.approuver_timesheet(timesheet, request.user)
        except services.TimesheetTransitionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TimesheetSerializer(timesheet).data)

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        """soumise → rejetee (palier Responsable/Admin — déjà gardé en vue)."""
        timesheet = self.get_object()
        motif = request.data.get('motif', '') or request.data.get(
            'motif_rejet', '')
        try:
            services.rejeter_timesheet(timesheet, request.user, motif=motif)
        except services.TimesheetTransitionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TimesheetSerializer(timesheet).data)

    @action(detail=False, methods=['get'], url_path='manquants')
    def manquants(self, request):
        """Jours SANS saisie de temps par ressource sur une période (XPRJ7).

        Query params ``?debut=YYYY-MM-DD&fin=YYYY-MM-DD`` (obligatoires).
        Délègue à ``selectors.temps_manquants`` (jours ouvrés attendus moins
        indisponibilités, comparés aux jours réellement saisis). Toujours
        scopé société (``request.user.company``).
        """
        debut = _parse_date_param(request.query_params.get('debut'))
        fin = _parse_date_param(request.query_params.get('fin'))
        if debut is None or fin is None:
            return Response(
                {'detail': 'Les paramètres « debut » et « fin » '
                           '(YYYY-MM-DD) sont obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        data = selectors.temps_manquants(
            request.user.company, debut, fin)
        return Response({
            'debut': str(data['debut']),
            'fin': str(data['fin']),
            'lignes': [
                {
                    'ressource_id': ligne['ressource_id'],
                    'ressource_nom': ligne['ressource_nom'],
                    'user_id': ligne['user_id'],
                    'jours_attendus': ligne['jours_attendus'],
                    'jours_saisis': ligne['jours_saisis'],
                    'jours_manquants': [
                        str(j) for j in ligne['jours_manquants']],
                }
                for ligne in data['lignes']
            ],
        })

    @action(detail=False, methods=['get'], url_path='heures-attendues')
    def heures_attendues(self, request):
        """Écart heures attendues vs saisies pour UNE ressource (ZPRJ5).

        Query params ``?ressource=<id>&debut=YYYY-MM-DD&fin=YYYY-MM-DD``
        (obligatoires). Délègue à ``selectors.heures_attendues_vs_saisies``
        (jours ouvrés attendus, moins indisponibilités, comparés aux heures
        RÉELLEMENT saisies — distinct de ``manquants``/XPRJ7 qui ne regarde
        que les jours SANS AUCUNE saisie). ``ressource`` doit appartenir à la
        société de l'appelant (sinon 404) ; sans ``user`` lié, réponse vide
        propre plutôt qu'une erreur.
        """
        ressource_id = request.query_params.get('ressource')
        debut = _parse_date_param(request.query_params.get('debut'))
        fin = _parse_date_param(request.query_params.get('fin'))
        if not ressource_id or debut is None or fin is None:
            return Response(
                {'detail': 'Les paramètres « ressource », « debut » et '
                           '« fin » (YYYY-MM-DD) sont obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        ressource = RessourceProfil.objects.filter(
            id=ressource_id, company=request.user.company).first()
        if ressource is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        data = selectors.heures_attendues_vs_saisies(
            request.user.company, ressource, debut, fin)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='classement')
    def classement(self, request):
        """Classement de saisie des temps — leaderboard interne (ZPRJ6).

        Query params ``?debut=YYYY-MM-DD&fin=YYYY-MM-DD`` (obligatoires).
        Délègue à ``selectors.classement_temps`` (trié complétude puis
        heures). AUCUN montant/coût interne exposé — seulement heures et
        complétude. Toujours scopé société.
        """
        debut = _parse_date_param(request.query_params.get('debut'))
        fin = _parse_date_param(request.query_params.get('fin'))
        if debut is None or fin is None:
            return Response(
                {'detail': 'Les paramètres « debut » et « fin » '
                           '(YYYY-MM-DD) sont obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        data = selectors.classement_temps(request.user.company, debut, fin)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='rapprochement')
    def rapprochement(self, request):
        """Rapprochement pointages RH ↔ temps projet, par employé/jour (XPRJ8).

        Query params ``?debut=YYYY-MM-DD&fin=YYYY-MM-DD`` (obligatoires),
        ``?seuil=<heures>`` (optionnel, défaut 0.5 h). Délègue à
        ``selectors.rapprochement_pointages`` (dégrade proprement si aucun
        pointage RH n'est exposé). Toujours scopé société.
        """
        debut = _parse_date_param(request.query_params.get('debut'))
        fin = _parse_date_param(request.query_params.get('fin'))
        if debut is None or fin is None:
            return Response(
                {'detail': 'Les paramètres « debut » et « fin » '
                           '(YYYY-MM-DD) sont obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        seuil_raw = request.query_params.get('seuil')
        try:
            from decimal import Decimal as _Decimal
            seuil = _Decimal(seuil_raw) if seuil_raw else _Decimal('0.5')
        except Exception:
            seuil = None
        if seuil is None:
            return Response(
                {'detail': 'Le paramètre « seuil » doit être un nombre.'},
                status=status.HTTP_400_BAD_REQUEST)
        data = selectors.rapprochement_pointages(
            request.user.company, debut, fin, seuil_heures=seuil)
        return Response({
            'debut': str(data['debut']),
            'fin': str(data['fin']),
            'ecarts': [
                {
                    'ressource_id': e['ressource_id'],
                    'ressource_nom': e['ressource_nom'],
                    'date': str(e['date']),
                    'type_ecart': e['type_ecart'],
                    'heures_pointees': str(e['heures_pointees']),
                    'heures_imputees': str(e['heures_imputees']),
                }
                for e in data['ecarts']
            ],
        })

    @action(detail=False, methods=['get'], url_path='rapport')
    def rapport(self, request):
        """Rapport des temps MULTI-DIMENSIONS (XPRJ18) — interne/admin.

        Corps : ``?debut=&fin=`` (obligatoires, YYYY-MM-DD),
        ``?group_by=ressource|projet|tache|phase|type_activite|semaine|mois``
        (défaut ``ressource``). Agrège les heures (et facturables) par
        dimension, avec le comparatif heures loguées vs ``charge_estimee`` par
        tâche impliquée (dépassement flaggé). ``?export=xlsx`` télécharge le
        classeur (le pattern DRF ``?format=`` réservé est évité). AUCUN
        ``cout`` interne dans l'export. La société est imposée côté serveur.
        """
        debut = _parse_date_param(request.query_params.get('debut'))
        fin = _parse_date_param(request.query_params.get('fin'))
        if debut is None or fin is None or fin < debut:
            return Response(
                {'detail': 'debut et fin (YYYY-MM-DD, fin >= debut) sont '
                           'obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        group_by = request.query_params.get('group_by', 'ressource')
        data = selectors.rapport_temps(
            request.user.company, debut, fin, group_by=group_by)

        if request.query_params.get('export') == 'xlsx':
            from apps.records.xlsx import build_xlsx_response

            headers = [
                data['group_by'].capitalize(), 'Heures',
                'Heures facturables',
            ]
            rows = [
                [ligne['libelle'], ligne['heures'],
                 ligne['heures_facturables']]
                for ligne in data['lignes']
            ]
            return build_xlsx_response(
                'rapport_temps.xlsx', headers, rows,
                sheet_title='Rapport des temps')

        return Response({
            'group_by': data['group_by'],
            'total_heures': str(data['total_heures']),
            'total_heures_facturables': str(
                data['total_heures_facturables']),
            'lignes': [
                {
                    'cle': ligne['cle'],
                    'libelle': ligne['libelle'],
                    'heures': str(ligne['heures']),
                    'heures_facturables': str(ligne['heures_facturables']),
                }
                for ligne in data['lignes']
            ],
            'par_tache': [
                {
                    'tache_id': t['tache_id'],
                    'libelle': t['libelle'],
                    'heures_loguees': str(t['heures_loguees']),
                    'charge_estimee_heures': (
                        str(t['charge_estimee_heures'])
                        if t['charge_estimee_heures'] is not None else None),
                    'depassement': t['depassement'],
                }
                for t in data['par_tache']
            ],
        })


class PeriodeVerrouilleeTempsViewSet(_GestionProjetBaseViewSet):
    """Verrous de période (mois) sur les feuilles de temps (XPRJ1) — CRUD scopé.

    ``company`` est posée côté serveur (TenantMixin) ; ``verrouille_par`` est
    posé côté serveur à la création. Réservé au palier Administrateur/
    Responsable (``IsResponsableOrAdmin``, base commune) — le déverrouillage
    (suppression) reste ouvert au même palier (journalisé par l'historique
    applicatif standard des requêtes DRF/serveur).
    """
    queryset = PeriodeVerrouilleeTemps.objects.select_related(
        'verrouille_par').all()
    serializer_class = PeriodeVerrouilleeTempsSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['mois', 'id']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            verrouille_par=self.request.user)


class RisqueViewSet(_GestionProjetBaseViewSet):
    """Registre des risques d'un projet (PROJ30) — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; le ``projet`` et le
    ``proprietaire`` reçus sont validés même-société. La ``criticite`` est
    FIGÉE côté serveur (probabilité × impact) — jamais lue du corps de requête.
    Filtres optionnels : ``?projet=<id>``, ``?statut=<statut>``,
    ``?categorie=<categorie>``, ``?criticite_min=<n>`` (criticité ≥ n).
    Recherche par libellé / description ; tri par défaut criticité décroissante.
    """
    queryset = Risque.objects.select_related('projet', 'proprietaire').all()
    serializer_class = RisqueSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'description', 'mitigation']
    ordering_fields = ['criticite', 'probabilite', 'impact', 'statut', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        criticite_min = self.request.query_params.get('criticite_min')
        if criticite_min:
            try:
                qs = qs.filter(criticite__gte=int(criticite_min))
            except (TypeError, ValueError):
                pass
        return qs


class ActionProjetViewSet(_GestionProjetBaseViewSet):
    """Registre d'actions d'un projet (PROJ31) — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; le ``projet``, le
    ``risque`` (optionnel) et le ``responsable`` (optionnel) reçus sont validés
    même-société. Filtres optionnels : ``?projet=<id>``, ``?statut=<statut>``,
    ``?priorite=<priorite>``, ``?risque=<id>``, ``?ouvertes=1`` (statut à faire /
    en cours). Recherche par libellé / description ; tri par défaut statut puis
    échéance.
    """
    queryset = ActionProjet.objects.select_related(
        'projet', 'risque', 'responsable').all()
    serializer_class = ActionProjetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'description']
    ordering_fields = ['statut', 'priorite', 'echeance', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        priorite = self.request.query_params.get('priorite')
        if priorite:
            qs = qs.filter(priorite=priorite)
        risque = self.request.query_params.get('risque')
        if risque:
            qs = qs.filter(risque_id=risque)
        if self.request.query_params.get('ouvertes') in ('1', 'true', 'True'):
            qs = qs.filter(statut__in=[
                ActionProjet.Statut.A_FAIRE, ActionProjet.Statut.EN_COURS])
        return qs


class CompteRenduReunionViewSet(_GestionProjetBaseViewSet):
    """Comptes-rendus de réunion de chantier (PROJ32) — CRUD scopé société.

    ``company`` et ``redacteur`` sont posés côté serveur ; le ``projet`` reçu est
    validé même-société. Filtres optionnels : ``?projet=<id>``,
    ``?chantier=<id>``, ``?debut=YYYY-MM-DD&fin=YYYY-MM-DD`` (réunions dans la
    fenêtre inclusive). Recherche par titre / décisions ; tri par défaut date de
    réunion décroissante.
    """
    queryset = CompteRenduReunion.objects.select_related(
        'projet', 'redacteur').all()
    serializer_class = CompteRenduReunionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['titre', 'decisions', 'ordre_du_jour', 'participants']
    ordering_fields = ['date_reunion', 'id']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, redacteur=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        chantier = self.request.query_params.get('chantier')
        if chantier:
            qs = qs.filter(chantier_id=chantier)
        debut = self.request.query_params.get('debut')
        fin = self.request.query_params.get('fin')
        if debut and fin:
            qs = qs.filter(date_reunion__gte=debut, date_reunion__lte=fin)
        return qs


class DocumentProjetViewSet(_GestionProjetBaseViewSet):
    """Documents & plans VERSIONNÉS d'un projet (PROJ33) — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; le ``projet`` reçu est
    validé même-société. Le dépôt d'une nouvelle révision se fait via l'action
    ``documents/<id>/deposer/`` (multipart, champ ``fichier`` + ``commentaire``
    optionnel) : le numéro de version et l'``auteur`` sont posés CÔTÉ SERVEUR
    (jamais du corps). Filtres optionnels : ``?projet=<id>``,
    ``?type_doc=<type>``. Recherche par nom / description.
    """
    queryset = DocumentProjet.objects.select_related('projet').prefetch_related(
        'versions').all()
    serializer_class = DocumentProjetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'type_doc', 'derniere_version', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        type_doc = self.request.query_params.get('type_doc')
        if type_doc:
            qs = qs.filter(type_doc=type_doc)
        return qs

    @action(detail=True, methods=['post'], url_path='deposer')
    def deposer(self, request, pk=None):
        """Dépose une NOUVELLE version (révision) du document (PROJ33).

        Corps multipart : ``fichier`` (obligatoire) + ``commentaire`` (optionnel).
        Le numéro de version (``derniere_version`` + 1) et l'``auteur`` sont posés
        côté serveur — jamais lus du corps. La société est garantie par
        ``get_object`` (queryset scopé société) : un document d'une autre société
        → 404. Renvoie la version créée (201).
        """
        document = self.get_object()
        fichier = request.data.get('fichier')
        if not fichier:
            return Response(
                {'fichier': 'Un fichier est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        commentaire = request.data.get('commentaire', '') or ''
        version = services.deposer_version_document(
            document, fichier, commentaire=commentaire, auteur=request.user)
        return Response(
            VersionDocumentSerializer(version).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='versions')
    def versions(self, request, pk=None):
        """Historique des versions du document (plus récentes d'abord)."""
        document = self.get_object()
        qs = VersionDocument.objects.filter(
            document=document, company=document.company).select_related(
                'auteur').order_by('-version', '-id')
        return Response(VersionDocumentSerializer(qs, many=True).data)


class CommentaireProjetViewSet(_GestionProjetBaseViewSet):
    """Commentaires & @mentions sur les objets d'un projet (PROJ34) — CRUD scopé.

    ``company`` et ``auteur`` sont posés côté serveur ; le ``projet`` reçu est
    validé même-société et les ``mentions`` restreintes à la même société.
    Filtres optionnels : ``?projet=<id>``, ``?cible_type=<type>``,
    ``?cible_id=<id>`` (fil d'un objet précis), ``?mention=<user_id>``
    (commentaires me mentionnant). Recherche par texte ; tri par défaut date
    décroissante.
    """
    queryset = CommentaireProjet.objects.select_related(
        'projet', 'auteur').prefetch_related('mentions').all()
    serializer_class = CommentaireProjetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['texte']
    ordering_fields = ['date_creation', 'id']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, auteur=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        cible_type = self.request.query_params.get('cible_type')
        if cible_type:
            qs = qs.filter(cible_type=cible_type)
        cible_id = self.request.query_params.get('cible_id')
        if cible_id:
            qs = qs.filter(cible_id=cible_id)
        mention = self.request.query_params.get('mention')
        if mention:
            qs = qs.filter(mentions__id=mention)
        return qs


class ModeleProjetViewSet(_GestionProjetBaseViewSet):
    """Modèles (templates) de projet par type d'installation (PROJ35).

    ``company`` est posée côté serveur (TenantMixin). Filtres optionnels :
    ``?type_installation=<type>``, ``?actif=1``. Recherche par nom / description.
    L'action ``modeles/<id>/instancier/`` applique le modèle à un projet (corps :
    ``projet``) — crée phases + tâches (additif). Les tâches-types se gèrent via
    ``modele-taches/``.
    """
    queryset = ModeleProjet.objects.prefetch_related('taches').all()
    serializer_class = ModeleProjetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'type_installation', 'id']

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def get_queryset(self):
        qs = super().get_queryset()
        type_installation = self.request.query_params.get('type_installation')
        if type_installation:
            qs = qs.filter(type_installation=type_installation)
        actif = self.request.query_params.get('actif')
        if actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        elif actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        return qs

    @action(detail=True, methods=['post'], url_path='instancier')
    def instancier(self, request, pk=None):
        """Applique le modèle à un PROJET : crée phases + tâches (PROJ35).

        Corps : ``projet`` (id, obligatoire). Le projet doit appartenir à la
        société de l'utilisateur (sinon 400) — la société du modèle est garantie
        par ``get_object`` (queryset scopé société). Opération ADDITIVE : aucune
        phase/tâche existante n'est écrasée. Renvoie les tâches créées (201).
        """
        modele = self.get_object()
        projet_id = request.data.get('projet')
        if not projet_id:
            return Response(
                {'projet': 'Le projet est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        projet = Projet.objects.filter(
            id=projet_id, company=request.user.company).first()
        if projet is None:
            return Response(
                {'projet': 'Projet inconnu.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            taches = services.instancier_modele(modele, projet)
        except services.ModeleProjetError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            TacheSerializer(taches, many=True).data,
            status=status.HTTP_201_CREATED)


class ModeleTacheViewSet(_GestionProjetBaseViewSet):
    """Tâches-types d'un modèle de projet (PROJ35) — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; le ``modele`` reçu est
    validé même-société. Filtres optionnels : ``?modele=<id>``,
    ``?type_phase=<type>``. Tri par défaut ``ordre`` puis ``id``.
    """
    queryset = ModeleTache.objects.select_related('modele').all()
    serializer_class = ModeleTacheSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'type_phase', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        modele = self.request.query_params.get('modele')
        if modele:
            qs = qs.filter(modele_id=modele)
        type_phase = self.request.query_params.get('type_phase')
        if type_phase:
            qs = qs.filter(type_phase=type_phase)
        return qs


class PortailProjetTokenViewSet(_GestionProjetBaseViewSet):
    """Jetons d'accès au portail d'avancement client (PROJ37) — CRUD scopé.

    Côté ADMIN/Responsable : crée/révoque le lien public d'un projet. ``company``
    est posée côté serveur ; le ``token`` est généré côté serveur ; le ``projet``
    reçu est validé même-société (un seul jeton par projet). Filtre optionnel
    ``?projet=<id>``. Le portail PUBLIC (non authentifié) est servi ailleurs
    (``public_views.portail_avancement``) et n'expose AUCUN coût/marge.
    """
    queryset = PortailProjetToken.objects.select_related('projet').all()
    serializer_class = PortailProjetTokenSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs


class SousTraitantViewSet(_GestionProjetBaseViewSet):
    """Carnet d'adresses des sous-traitants (PROJ38) — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin). Filtres optionnels :
    ``?actif=1``, ``?specialite=<txt>``. Recherche par nom / spécialité /
    contact. Données INTERNES — jamais exposées au client.
    """
    queryset = SousTraitant.objects.all()
    serializer_class = SousTraitantSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'specialite', 'contact', 'email']
    ordering_fields = ['nom', 'specialite', 'actif', 'id']

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        elif actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        specialite = self.request.query_params.get('specialite')
        if specialite:
            qs = qs.filter(specialite__icontains=specialite)
        return qs


class LotSousTraitanceViewSet(_GestionProjetBaseViewSet):
    """Lots de sous-traitance d'un projet (PROJ38) — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; le ``projet`` et le
    ``sous_traitant`` reçus sont validés même-société. Le ``montant`` est un coût
    INTERNE — jamais exposé au client. Filtres optionnels : ``?projet=<id>``,
    ``?sous_traitant=<id>``, ``?statut=<statut>``. Recherche par libellé.
    """
    queryset = LotSousTraitance.objects.select_related(
        'projet', 'sous_traitant').all()
    serializer_class = LotSousTraitanceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'description']
    ordering_fields = ['statut', 'montant', 'date_debut', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        sous_traitant = self.request.query_params.get('sous_traitant')
        if sous_traitant:
            qs = qs.filter(sous_traitant_id=sous_traitant)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs


class ClotureProjetViewSet(_GestionProjetBaseViewSet):
    """Clôtures de projet + retour d'expérience (PROJ38) — scopé société.

    ``company`` et ``cloture_par`` sont posés côté serveur ; le ``projet`` reçu
    est validé même-société. La clôture se prend de préférence via l'action
    ``projets/<id>/cloturer/`` (transition serveur + REX) ; ce viewset gère la
    lecture et l'édition du REX. Filtre optionnel ``?projet=<id>``.
    """
    queryset = ClotureProjet.objects.select_related(
        'projet', 'cloture_par').all()
    serializer_class = ClotureProjetSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_cloture', 'id']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, cloture_par=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs


class SituationTravauxViewSet(_GestionProjetBaseViewSet):
    """Situations de travaux (décomptes progressifs BTP) — CRUD scopé (XPRJ4).

    ``company`` est posée côté serveur (TenantMixin) ; le ``projet`` reçu est
    validé même-société. Le ``numero`` est posé côté serveur à la CRÉATION
    (jamais lu du corps — voir ``perform_create`` → ``services.creer_
    situation``, incrémental par projet, jamais ``count()+1``). Le ``statut``
    et ``facture_id`` sont pilotés par l'action ``valider``. Filtre optionnel
    ``?projet=<id>``.
    """
    queryset = SituationTravaux.objects.select_related('projet').all()
    serializer_class = SituationTravauxSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['numero', 'periode', 'id']

    def perform_create(self, serializer):
        projet = serializer.validated_data['projet']
        numero = services.prochain_numero_situation(projet)
        serializer.save(company=self.request.user.company, numero=numero)

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs

    @action(detail=True, methods=['post'], url_path='ajouter-ligne')
    def ajouter_ligne(self, request, pk=None):
        """Ajoute une ligne à la situation, montants CALCULÉS côté serveur.

        Corps : ``libelle``, ``montant_marche_ht``, ``avancement_cumule_pct``.
        La société est garantie par ``get_object`` : une situation d'une autre
        société → 404. Refuse (400) sur une situation déjà VALIDÉE/FACTURÉE.
        """
        situation = self.get_object()
        libelle = request.data.get('libelle')
        montant_marche_ht = request.data.get('montant_marche_ht')
        avancement_cumule_pct = request.data.get('avancement_cumule_pct')
        if not libelle or montant_marche_ht is None \
                or avancement_cumule_pct is None:
            return Response(
                {'detail': 'libelle, montant_marche_ht et '
                           'avancement_cumule_pct sont obligatoires.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ligne = services.ajouter_ligne_situation(
                situation, libelle=libelle,
                montant_marche_ht=montant_marche_ht,
                avancement_cumule_pct=avancement_cumule_pct)
        except services.SituationTravauxError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            LigneSituationSerializer(ligne).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valide la situation et génère la facture d'acompte (une seule fois).

        La société est garantie par ``get_object`` : une situation d'une autre
        société → 404. Refuse (400) une situation déjà VALIDÉE/FACTURÉE ou sans
        ligne, ou si le client du projet ne peut être résolu.
        """
        situation = self.get_object()
        try:
            services.valider_situation(situation, user=request.user)
        except services.SituationTravauxError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SituationTravauxSerializer(situation).data)


class LigneSituationViewSet(_GestionProjetBaseViewSet):
    """Lignes de situations de travaux (XPRJ4) — lecture/édition scopée.

    ``company`` est posée côté serveur ; la ``situation`` reçue est validée
    même-société. Créer une ligne via ce viewset direct n'exécute PAS le calcul
    serveur (``montant_cumule``/``montant_periode`` restent à leur défaut 0) —
    préférer ``situations/<id>/ajouter-ligne/`` qui délègue à
    ``services.ajouter_ligne_situation``. Filtre optionnel ``?situation=<id>``.
    """
    queryset = LigneSituation.objects.select_related('situation').all()
    serializer_class = LigneSituationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def get_queryset(self):
        qs = super().get_queryset()
        situation = self.request.query_params.get('situation')
        if situation:
            qs = qs.filter(situation_id=situation)
        return qs


class RecurrenceTacheViewSet(_GestionProjetBaseViewSet):
    """Gabarits de tâches récurrentes (XPRJ13) — CRUD scopé société.

    ``company`` est posée côté serveur (TenantMixin) ; les FK reçus
    (``projet``, ``phase``, ``assigne``) sont validés même-société par le
    sérialiseur. Filtre optionnel ``?projet=<id>``. La génération effective
    des tâches se fait via ``manage.py generer_taches_recurrentes``
    (idempotente), jamais via ce viewset.
    """
    queryset = RecurrenceTache.objects.select_related(
        'projet', 'phase', 'assigne').all()
    serializer_class = RecurrenceTacheSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['prochaine_echeance', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs


class ItemChecklistTacheViewSet(_GestionProjetBaseViewSet):
    """Items de checklist d'une tâche (XPRJ14) — CRUD scopé société.

    ``company`` posée côté serveur ; la ``tache`` reçue est validée
    même-société. Filtre optionnel ``?tache=<id>``. Le bascule ``fait``
    passe de préférence par l'action ``toggle`` (pose ``fait_par``/``fait_le``
    côté serveur).
    """
    queryset = ItemChecklistTache.objects.select_related(
        'tache', 'fait_par').all()
    serializer_class = ItemChecklistTacheSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        tache = self.request.query_params.get('tache')
        if tache:
            qs = qs.filter(tache_id=tache)
        return qs

    @action(detail=True, methods=['post'], url_path='toggle')
    def toggle(self, request, pk=None):
        """Inverse ``fait`` et pose ``fait_par``/``fait_le`` côté serveur.

        La société est garantie par ``get_object`` (queryset scopé société) :
        un item d'une autre société → 404. Repasser à ``False`` réinitialise
        ``fait_par``/``fait_le``.
        """
        from django.utils import timezone

        item = self.get_object()
        item.fait = not item.fait
        if item.fait:
            item.fait_par = request.user
            item.fait_le = timezone.now()
        else:
            item.fait_par = None
            item.fait_le = None
        item.save(update_fields=['fait', 'fait_par', 'fait_le'])
        return Response(ItemChecklistTacheSerializer(item).data)


class PointAvancementViewSet(_GestionProjetBaseViewSet):
    """Points d'avancement périodiques — statut RAG (XPRJ15).

    ``company`` et ``auteur`` posés côté serveur (TenantMixin) ; le ``projet``
    reçu est validé même-société. Filtre ``?projet=<id>`` (historique par
    projet, tri par défaut du plus récent au plus ancien). Le DERNIER point
    d'un projet alimente ``portefeuille`` (PROJ36) — voir
    ``selectors.tableau_portefeuille``.
    """
    queryset = PointAvancement.objects.select_related(
        'projet', 'auteur').all()
    serializer_class = PointAvancementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_point', 'id']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, auteur=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs
