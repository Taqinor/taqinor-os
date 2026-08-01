"""Vues du module Appels d'offres (``apps.ao``).

AOF1 — le CORPS des 8 ViewSets AO vit désormais ICI (il vivait encore dans
``apps.compta.views`` malgré la sortie ODX11 des modèles). ``apps.compta.views``
porte maintenant un shim de ré-export **INVERSE** (``from apps.ao.views import
…``) pour que ni les routes ``/api/django/compta/…`` ni les imports historiques
ne cassent.

ODX22 (`docs/PLAN.md`) reste OUVERT et n'est PAS atterri ici : il demande le
RETRAIT des shims transitoires — AOF1 en a seulement INVERSÉ le sens (compta →
ao devient ao → compta), ce qui est à prendre en compte le jour de son
déblocage.

Socle (AOF3) : les 8 ViewSets héritent de ``apps.ao.viewsets.AoBaseViewSet`` =
``core.viewsets.CompanyScopedModelViewSet`` (scoping ``request.user.company`` +
``company`` forcée côté serveur, détection par le sweep d'isolation
multi-tenant) + chatter générique ``records``, gardé par ``ao_voir`` (lecture)
et ``ao_gerer`` (écriture). L'ancienne garde grossière ``IsResponsableOrAdmin``
héritée de ``_ComptaBaseViewSet`` est ABANDONNÉE : elle ouvrait tout le dossier
d'appel d'offres au palier Responsable (cf. AOF2).
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from core.permissions import ScopedPermission

from . import services
from .permissions import AO_GERER, AO_VOIR
from .models import (
    AppelOffre,
    BatimentAO,
    BordereauPrix,
    CautionSoumission,
    ChaineCotes,
    DossierSoumission,
    EcheanceAO,
    ExigenceCPS,
    KitCalepinage,
    LigneBordereau,
    ObstacleAO,
    PieceConsultation,
    PieceSoumission,
    PlanSource,
    PresetCalepinage,
    ReleveAO,
    QuestionAO,
    ResultatAO,
    SerieQuestions,
    ToitureAO,
    VarianteCalepinage,
)
from .serializers import (
    AppelOffreSerializer,
    BatimentAOSerializer,
    BordereauPrixSerializer,
    CautionSoumissionSerializer,
    ChaineCotesSerializer,
    DossierSoumissionSerializer,
    EcheanceAOSerializer,
    ExigenceCPSSerializer,
    KitCalepinageSerializer,
    LigneBordereauSerializer,
    ObstacleAOSerializer,
    PieceConsultationSerializer,
    PieceSoumissionSerializer,
    PlanSourceSerializer,
    PresetCalepinageSerializer,
    ReleveAOSerializer,
    QuestionAOSerializer,
    ResultatAOSerializer,
    SerieQuestionsSerializer,
    ToitureAOSerializer,
    VarianteCalepinageSerializer,
)
from .viewsets import AoBaseViewSet


def _filtres_exacts(queryset, params, champs):
    """Applique les filtres d'égalité ``?champ=valeur`` présents dans l'URL.

    ``DjangoFilterBackend`` n'est PAS monté dans ce projet : le filtrage des
    listes AO se fait explicitement, avec les mêmes noms que les champs du
    modèle (voir le contrat d'API publié par AOF31).
    """
    for champ in champs:
        valeur = params.get(champ)
        if valeur in (None, ''):
            continue
        queryset = queryset.filter(**{champ: valeur})
    return queryset


# ── AOF31 — Contrat d'API PUBLIÉ ───────────────────────────────────────────
#
# Le contrat n'est pas une page de documentation qu'on oublie de mettre à jour :
# il est DÉRIVÉ du routeur au moment de la requête. Une ressource ajoutée sans
# être décrite apparaît quand même ; une ressource retirée disparaît. C'est ce
# qui permet aux lanes frontend et fabrique de coder contre quelque chose de
# vrai plutôt que contre une liste recopiée à la main.

class ContratApiAO(APIView):
    """``GET /api/django/ao/contrat/`` — les ressources AO et leurs filtres.

    Gardé par ``ao_voir`` comme le reste du domaine : le contrat décrit un
    périmètre métier, il n'a pas à être plus public que les données.
    """
    permission_classes = [ScopedPermission]
    read_permission = AO_VOIR
    write_permission = AO_GERER

    def get(self, request):
        from .urls import router

        ressources = []
        for prefixe, viewset, basename in router.registry:
            modele = getattr(viewset, 'queryset', None)
            actions = sorted(
                nom for nom in dir(viewset)
                if getattr(getattr(viewset, nom, None), 'mapping', None)
            )
            ressources.append({
                'prefixe': prefixe,
                'basename': basename,
                'modele': (modele.model._meta.label_lower
                           if modele is not None else None),
                'recherche': list(getattr(viewset, 'search_fields', []) or []),
                'tri': list(getattr(viewset, 'ordering_fields', []) or []),
                'actions': actions,
            })
        return Response({
            'prefixe': '/api/django/ao/',
            'permissions': {'lecture': AO_VOIR, 'ecriture': AO_GERER},
            'pagination': {
                'style': 'page',
                'parametres': ['page', 'page_size'],
                'taille_par_defaut': api_settings.PAGE_SIZE,
            },
            'ressources': sorted(ressources, key=lambda r: r['prefixe']),
        })


# ── FG222 — Gestion des appels d'offres ────────────────────────────────────

class AppelOffreViewSet(AoBaseViewSet):
    """Objets appels d'offres public/privé (FG222)."""
    queryset = AppelOffre.objects.all()
    serializer_class = AppelOffreSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'reference_acheteur', 'objet', 'acheteur',
                     'maitre_ouvrage', 'soumissionnaire', 'reference_cps',
                     'lot']
    ordering_fields = ['date_creation', 'date_limite', 'date_ouverture_plis',
                       'statut']
    #: AOF12 — filtres d'égalité exposés en paramètres de requête.
    FILTRES_EXACTS = ('statut', 'type_marche', 'mode_passation')

    def get_queryset(self):
        params = self.request.query_params
        qs = _filtres_exacts(
            super().get_queryset(), params, self.FILTRES_EXACTS)
        groupement = params.get('groupement')
        if groupement not in (None, ''):
            qs = qs.filter(
                groupement=groupement.lower() in ('1', 'true', 'vrai', 'oui'))
        # AOF17 — ``?lead=<id>`` : les AO d'un lead. ``lead_id`` reste un
        # ENTIER OPAQUE (jamais une FK vers crm.Lead — contrat import-linter
        # ``ao-models-decoupled``), donc le filtre est une simple égalité.
        lead = params.get('lead')
        if lead not in (None, ''):
            qs = qs.filter(lead_id=lead) if str(lead).isdigit() \
                else qs.none()
        return qs

    @action(detail=True, methods=['get'], url_path='lead')
    def lead(self, request, pk=None):
        """AOF17 — fiche-carte du lead lié (lecture seule), ou ``null``.

        Passe par ``apps.crm.selectors`` — ``ao`` n'importe JAMAIS
        ``apps.crm.models``.
        """
        from . import selectors

        return Response({
            'lead_id': self.get_object().lead_id,
            'fiche': selectors.fiche_lead_de_l_ao(self.get_object()),
        })

    @action(detail=True, methods=['post'], url_path='rattacher-lead')
    def rattacher_lead(self, request, pk=None):
        """AOF17 — rattache/détache un lead, en validant l'appartenance."""
        appel_offre = self.get_object()
        try:
            services.rattacher_ao_au_lead(
                appel_offre, request.data.get('lead'), user=request.user)
        except DjangoValidationError as exc:
            return Response(exc.message_dict if hasattr(exc, 'message_dict')
                            else {'lead': exc.messages},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(appel_offre).data)

    def perform_create(self, serializer):
        """AOF5 — référence auto ``AO-YYYYMM-0001`` quand elle n'est pas fournie.

        La société reste posée CÔTÉ SERVEUR dans les deux branches (jamais lue
        du corps de requête) : ``super()`` pour la branche « référence
        fournie », ``serializer.save(company=…)`` dans la fabrique de référence
        pour l'autre.
        """
        if (serializer.validated_data.get('reference') or '').strip():
            return super().perform_create(serializer)
        societe = self.request.user.company
        services.creer_appel_offre_avec_reference(
            societe,
            lambda reference: serializer.save(
                company=societe, reference=reference),
        )

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """AOF13 — SEUL chemin HTTP de mutation du statut d'un AO.

        Une transition interdite par ``services.TRANSITIONS_AO`` répond 400
        avec un message en français listant les statuts atteignables.
        """
        appel_offre = self.get_object()
        try:
            services.changer_statut_ao(
                appel_offre, request.data.get('statut'), user=request.user,
                motif=(request.data.get('motif') or ''))
        except DjangoValidationError as exc:
            return Response(exc.message_dict if hasattr(exc, 'message_dict')
                            else {'statut': exc.messages},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(appel_offre).data)

    @action(detail=True, methods=['get'], url_path='points-a-lever')
    def points_a_lever(self, request, pk=None):
        """AOF24 — « à confirmer à l'exécution », DÉRIVÉ (jamais saisi).

        La liste vient des cotes ``A_CONFIRMER`` et des obstacles non
        engageables ; ``mention_cartouche`` donne la base opposable du dossier.
        """
        from . import selectors

        appel_offre = self.get_object()
        return Response({
            'mention_cartouche': selectors.mention_cartouche(appel_offre),
            'points': selectors.points_a_lever(appel_offre),
        })

    @action(detail=True, methods=['get'], url_path='transitions')
    def transitions(self, request, pk=None):
        """Statuts atteignables depuis l'état courant (pilote l'UI)."""
        appel_offre = self.get_object()
        libelles = dict(AppelOffre.Statut.choices)
        cibles = services.transitions_possibles(appel_offre.statut)
        return Response({
            'statut': appel_offre.statut,
            'statut_display': libelles.get(appel_offre.statut, ''),
            'transitions': [
                {'valeur': s, 'libelle': libelles[s]} for s in cibles
            ],
        })


# ── AOF18 — Bâtiments et toitures ──────────────────────────────────────────

class BatimentAOViewSet(AoBaseViewSet):
    """Bâtiments d'un projet d'appel d'offres (AOF18)."""
    queryset = BatimentAO.objects.prefetch_related('toitures').all()
    serializer_class = BatimentAOSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'designation']
    ordering_fields = ['ordre', 'code']

    def get_queryset(self):
        return _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('appel_offre',))


class ToitureAOViewSet(AoBaseViewSet):
    """Toitures d'un bâtiment, en repère LOCAL MÉTRIQUE (AOF18).

    ``surface_m2`` est RECALCULÉE côté serveur à chaque écriture : une surface
    saisie à la main diverge du contour dès la première correction de relevé.
    """
    queryset = ToitureAO.objects.all()
    serializer_class = ToitureAOSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code_document', 'designation']
    ordering_fields = ['code_document', 'niveau']

    def get_queryset(self):
        qs = _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('batiment', 'forme', 'type_couverture'))
        appel_offre = self.request.query_params.get('appel_offre')
        if appel_offre not in (None, ''):
            qs = qs.filter(batiment__appel_offre_id=appel_offre) \
                if str(appel_offre).isdigit() else qs.none()
        return qs

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._recalculer(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._recalculer(serializer.instance)

    @staticmethod
    def _recalculer(toiture):
        toiture.recalculer_surface()
        toiture.save(update_fields=['surface_m2', 'updated_at'])

    @action(detail=True, methods=['post'], url_path='appliquer-preset')
    def appliquer_preset(self, request, pk=None):
        """AOF27 — applique un preset à cette toiture EN UN APPEL."""
        toiture = self.get_object()
        preset = PresetCalepinage.objects.filter(
            pk=request.data.get('preset'),
            company=request.user.company).first()
        if preset is None:
            return Response(
                {'preset': "Ce preset n'existe pas dans votre société."},
                status=status.HTTP_400_BAD_REQUEST)
        services.appliquer_preset(preset, toiture, user=request.user)
        return Response(self.get_serializer(toiture).data)


class SerieQuestionsViewSet(AoBaseViewSet):
    """Séries de questions chiffrées sur documents annotés (AOF25)."""
    queryset = SerieQuestions.objects.prefetch_related('questions').all()
    serializer_class = SerieQuestionsSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['numero', 'date_envoi']

    def get_queryset(self):
        return _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('appel_offre', 'canal'))


class QuestionAOViewSet(AoBaseViewSet):
    """Questions chiffrées (AOF25).

    ``trancher`` APPLIQUE la décision : l'objet lié est mis à jour (obstacle
    écarté/confirmé, cote requalifiée) et les variantes de calepinage
    dépendantes basculent ``PERIME``. Une décision qui ne modifierait rien ne
    servirait à rien.
    """
    queryset = QuestionAO.objects.all()
    serializer_class = QuestionAOSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['repere', 'texte']
    ordering_fields = ['repere', 'statut']

    def get_queryset(self):
        qs = _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('serie', 'statut', 'obstacle', 'chaine'))
        appel_offre = self.request.query_params.get('appel_offre')
        if appel_offre not in (None, ''):
            qs = qs.filter(serie__appel_offre_id=appel_offre) \
                if str(appel_offre).isdigit() else qs.none()
        return qs

    @action(detail=True, methods=['post'], url_path='trancher')
    def trancher(self, request, pk=None):
        decision = (request.data.get('decision') or '').strip()
        if not decision:
            return Response(
                {'decision': 'Trancher une question exige une décision '
                             'écrite.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            question, perimees = services.trancher_question(
                self.get_object(), decision=decision,
                action=(request.data.get('action') or 'aucune'),
                statut_cote=request.data.get('statut_cote'),
                provenance=request.data.get('provenance'),
                user=request.user)
        except DjangoValidationError as exc:
            return Response(exc.message_dict if hasattr(exc, 'message_dict')
                            else {'action': exc.messages},
                            status=status.HTTP_400_BAD_REQUEST)
        donnees = self.get_serializer(question).data
        donnees['variantes_perimees'] = perimees
        return Response(donnees)


class ReleveAOViewSet(AoBaseViewSet):
    """Visites de relevé (AOF24) — la base opposable du dossier."""
    queryset = ReleveAO.objects.prefetch_related('toitures', 'photos').all()
    serializer_class = ReleveAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_visite']

    def get_queryset(self):
        return _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('appel_offre', 'contradictoire'))


class ChaineCotesViewSet(AoBaseViewSet):
    """Chaînes de cotes et fermetures (AOF23).

    ``deduire`` applique la règle métier gravée : la cote DÉDUITE d'une
    fermeture exacte prime sur la valeur annoncée et bascule en
    ``A_CONFIRMER``. ``compensation`` PROPOSE une répartition au prorata sans
    RIEN appliquer — une compensation silencieuse transformerait un écart de
    relevé en fausse précision.
    """
    queryset = ChaineCotes.objects.all()
    serializer_class = ChaineCotesSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle']
    ordering_fields = ['libelle', 'axe', 'verdict']

    def get_queryset(self):
        return _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('toiture', 'axe', 'verdict'))

    def perform_create(self, serializer):
        super().perform_create(serializer)
        services.recalculer_chaine(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        services.recalculer_chaine(serializer.instance)

    @action(detail=True, methods=['post'], url_path='deduire')
    def deduire(self, request, pk=None):
        try:
            index = int(request.data.get('index'))
        except (TypeError, ValueError):
            return Response({'index': 'Index de segment requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            chaine = services.deduire_segment(
                self.get_object(), index, user=request.user)
        except DjangoValidationError as exc:
            return Response(exc.message_dict if hasattr(exc, 'message_dict')
                            else {'segments': exc.messages},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(chaine).data)

    @action(detail=True, methods=['get'], url_path='compensation')
    def compensation(self, request, pk=None):
        """PROPOSE la compensation au prorata — n'applique RIEN."""
        return Response(
            services.proposer_compensation_prorata(self.get_object()))


class ObstacleAOViewSet(AoBaseViewSet):
    """Obstacles de toiture (AOF22) — provenance de premier rang.

    ``?provenance=ECARTE`` renvoie les obstacles ÉCARTÉS **avec leur
    géométrie** : sans cette requête, la marche correspondante de l'échelle de
    décomposition serait irreproductible. Le dégagement est recalculé côté
    serveur à chaque écriture, sauf surcharge motivée.
    """
    queryset = ObstacleAO.objects.all()
    serializer_class = ObstacleAOSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['repere', 'designation']
    ordering_fields = ['repere', 'nature', 'provenance']

    def get_queryset(self):
        qs = _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('toiture', 'nature', 'provenance', 'actif', 'hors_zone_pv'))
        appel_offre = self.request.query_params.get('appel_offre')
        if appel_offre not in (None, ''):
            qs = qs.filter(
                toiture__batiment__appel_offre_id=appel_offre) \
                if str(appel_offre).isdigit() else qs.none()
        return qs

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._appliquer(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._appliquer(serializer.instance)

    @staticmethod
    def _appliquer(obstacle):
        obstacle.appliquer_degagement()
        obstacle.save(update_fields=[
            'degagement_m', 'regle_degagement', 'updated_at'])

    @action(detail=True, methods=['post'], url_path='ecarter')
    def ecarter(self, request, pk=None):
        """Écarte l'obstacle SANS le supprimer (géométrie conservée)."""
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response(
                {'motif': "Écarter un obstacle exige un motif : c'est ce qui "
                          'rend le retour arrière défendable.'},
                status=status.HTTP_400_BAD_REQUEST)
        obstacle = services.ecarter_obstacle(
            self.get_object(), motif=motif, user=request.user)
        return Response(self.get_serializer(obstacle).data)

    @action(detail=True, methods=['post'], url_path='reintegrer')
    def reintegrer(self, request, pk=None):
        """Retour arrière : l'obstacle écarté redevient actif."""
        provenance = request.data.get('provenance') \
            or ObstacleAO.Provenance.MESURE
        if provenance not in dict(ObstacleAO.Provenance.choices):
            return Response({'provenance': 'Provenance inconnue.'},
                            status=status.HTTP_400_BAD_REQUEST)
        obstacle = services.reintegrer_obstacle(
            self.get_object(), provenance, user=request.user,
            motif=(request.data.get('motif') or ''))
        return Response(self.get_serializer(obstacle).data)


class PlanSourceViewSet(AoBaseViewSet):
    """Supports de plan d'une toiture (AOF20) — les 3 portes d'entrée.

    Un même toit peut cumuler PLUSIEURS supports : un plan fourni calibré ET
    des tracés manuels additifs. L'échelle est TOUJOURS recalculée côté serveur
    à chaque écriture d'un point de calibration.
    """
    queryset = PlanSource.objects.all()
    serializer_class = PlanSourceSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'etat']

    def get_queryset(self):
        return _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('toiture', 'batiment', 'origine', 'etat', 'type_fichier'))

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._recalibrer(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._recalibrer(serializer.instance)

    @staticmethod
    def _recalibrer(plan_source):
        plan_source.recalculer_echelle()
        plan_source.save(update_fields=[
            'echelle_m_par_px', 'etat', 'updated_at'])


# ── AOF21 — Pièces du dossier de consultation reçues ───────────────────────

class PieceConsultationViewSet(AoBaseViewSet):
    """Le DCE REÇU de l'acheteur (CPS, règlement, plans, cadres vierges).

    L'action ``additif`` enregistre un erratum ET marque « à revérifier » les
    clauses qui dérivent de la pièce modifiée.
    """
    queryset = PieceConsultation.objects.all()
    serializer_class = PieceConsultationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'version']
    ordering_fields = ['date_reception', 'type_piece']

    def get_queryset(self):
        return _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('appel_offre', 'type_piece'))

    @action(detail=True, methods=['post'], url_path='additif')
    def additif(self, request, pk=None):
        piece = self.get_object()
        _, marquees = services.enregistrer_additif(
            piece.appel_offre, piece_modifiee=piece,
            reference=(request.data.get('reference') or ''),
            version=(request.data.get('version') or ''),
            user=request.user)
        return Response({'exigences_a_reverifier': marquees},
                        status=status.HTTP_201_CREATED)


# ── AOF14 — Exigences du CPS ───────────────────────────────────────────────

class ExigenceCPSViewSet(AoBaseViewSet):
    """Clauses chiffrées du CPS d'un AO (AOF14). Aucune exigence d'ASSURANCE
    ici : elles vivent dans ``apps.assurances`` (``ExigenceAssuranceMarche``,
    rattachée par sa string-FK ``marche_ref``)."""
    queryset = ExigenceCPS.objects.all()
    serializer_class = ExigenceCPSSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle', 'valeur_texte']
    ordering_fields = ['code', 'type_exigence', 'bloquant']

    def get_queryset(self):
        return _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('appel_offre', 'type_exigence', 'bloquant', 'a_reverifier',
             'piece_consultation'))


class VarianteCalepinageViewSet(AoBaseViewSet):
    """Variantes de calepinage (AOF28) — l'écran de comparaison est UNE requête.

    ``publier`` refuse (400) tant que la PREUVE ne tient pas ; ``retenir``
    désigne l'unique variante retenue de la toiture.
    """
    queryset = VarianteCalepinage.objects.all()
    serializer_class = VarianteCalepinageSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'justification']
    ordering_fields = ['role', 'score', 'statut']

    def get_queryset(self):
        return _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('toiture', 'appel_offre', 'role', 'statut', 'est_retenue',
             'est_recommandee', 'parent'))

    @action(detail=True, methods=['post'], url_path='publier')
    def publier(self, request, pk=None):
        try:
            variante = services.publier_variante(self.get_object())
        except DjangoValidationError as exc:
            return Response(exc.message_dict if hasattr(exc, 'message_dict')
                            else {'preuve': exc.messages},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(variante).data)

    @action(detail=True, methods=['post'], url_path='retenir')
    def retenir(self, request, pk=None):
        variante = services.retenir_variante(self.get_object())
        return Response(self.get_serializer(variante).data)


class PresetCalepinageViewSet(AoBaseViewSet):
    """Presets de calepinage (AOF27) — jeux de paramètres NOMMÉS."""
    queryset = PresetCalepinage.objects.all()
    serializer_class = PresetCalepinageSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'portee']

    def get_queryset(self):
        return _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('portee', 'par_defaut'))


# ── AOF26 — Kits de calepinage ─────────────────────────────────────────────

class KitCalepinageViewSet(AoBaseViewSet):
    """Catalogue des kits de pose (AOF26). L'emprise est TOUJOURS recalculée
    côté serveur : dérivée par défaut, mesurée quand elle est figée, écart
    tracé dans les deux cas."""
    queryset = KitCalepinage.objects.all()
    serializer_class = KitCalepinageSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle']
    ordering_fields = ['code', 'modules_par_kit']

    def get_queryset(self):
        return _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('mode', 'actif', 'orientation_modules'))

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._appliquer(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._appliquer(serializer.instance)

    @staticmethod
    def _appliquer(kit):
        kit.appliquer_emprise()
        kit.save(update_fields=[
            'emprise_transversale_m', 'ecart_emprise_m', 'updated_at'])


# ── FG223 — Bordereau des prix (BOQ) ───────────────────────────────────────

class BordereauPrixViewSet(AoBaseViewSet):
    """Bordereaux des prix (BOQ) d'AO (FG223), séparés du devis client."""
    queryset = BordereauPrix.objects.prefetch_related('lignes').all()
    serializer_class = BordereauPrixSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']


class LigneBordereauViewSet(AoBaseViewSet):
    """Lignes chiffrées d'un BOQ (FG223)."""
    queryset = LigneBordereau.objects.all()
    serializer_class = LigneBordereauSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['numero']


# ── FG224 — Cautions & garanties de soumission ─────────────────────────────

class CautionSoumissionViewSet(AoBaseViewSet):
    """Cautions de soumission (provisoires/définitives) d'AO (FG224)."""
    queryset = CautionSoumission.objects.all()
    serializer_class = CautionSoumissionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'date_echeance', 'statut']


# ── FG225 — Dossier de soumission (pièces administratives) ─────────────────

class DossierSoumissionViewSet(AoBaseViewSet):
    """Dossiers de soumission d'AO (FG225) : checklist des pièces."""
    queryset = DossierSoumission.objects.prefetch_related('pieces').all()
    serializer_class = DossierSoumissionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']


class PieceSoumissionViewSet(AoBaseViewSet):
    """Pièces administratives d'un dossier de soumission (FG225)."""
    queryset = PieceSoumission.objects.all()
    serializer_class = PieceSoumissionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['libelle']


# ── FG226 — Échéancier & alertes de deadline d'AO ──────────────────────────

class EcheanceAOViewSet(AoBaseViewSet):
    """Dates clés d'un AO avec rappels (FG226). L'action ``dues`` liste les
    échéances dont le rappel est échu et non traité."""
    queryset = EcheanceAO.objects.all()
    serializer_class = EcheanceAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_echeance', 'date_creation']

    @action(detail=False, methods=['get'])
    def dues(self, request):
        dues = services.echeances_ao_dues(request.user.company)
        return Response(EcheanceAOSerializer(dues, many=True).data)


# ── FG227 — Analyse gagné/perdu des appels d'offres ────────────────────────

class ResultatAOViewSet(AoBaseViewSet):
    """Résultats d'AO pour l'analyse gagné/perdu (FG227). L'action ``stats``
    renvoie le taux de réussite consolidé."""
    queryset = ResultatAO.objects.all()
    serializer_class = ResultatAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'date_resultat']

    @action(detail=False, methods=['get'])
    def stats(self, request):
        return Response(services.taux_reussite_ao(request.user.company))
