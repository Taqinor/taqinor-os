"""Vues QHSE (scopées société, accès Administrateur/Responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; la non-conformité enregistre aussi son signaleur
(``signale_par``) côté serveur.
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from apps.ventes.utils.references import create_with_reference

from .models import (
    ActionCorrectivePreventive, Audit, ConsignationLoto, ContactUrgence,
    CritereAudit, EvaluationRisque, GrilleAudit, InductionSecurite,
    ItemNotation, LigneEvaluationRisque, NonConformite, NotationFinChantier,
    PermisTravail, PlanInspectionChantier, PlanInspectionModele, PlanUrgence,
    PointControleModele, ProcedureQualite, QhseChatterEntry, ReleveControle,
    ReleveCourbeIV, ReponseCritere, RetourClientQualite, Secouriste,
)
from .serializers import (
    ActionCorrectivePreventiveSerializer, AuditSerializer,
    ConsignationLotoSerializer, ContactUrgenceSerializer,
    CritereAuditSerializer,
    EvaluationRisqueSerializer, GrilleAuditSerializer,
    InductionSecuriteSerializer, ItemNotationSerializer,
    LigneEvaluationRisqueSerializer,
    NonConformiteSerializer, NotationFinChantierSerializer,
    PermisTravailSerializer, PlanInspectionChantierSerializer,
    PlanInspectionModeleSerializer, PlanUrgenceSerializer,
    PointControleModeleSerializer,
    ProcedureQualiteSerializer, QhseChatterEntrySerializer,
    ReleveControleSerializer, ReleveCourbeIVSerializer,
    ReponseCritereSerializer, RetourClientQualiteSerializer,
    SecouristeSerializer,
)
from . import chatter
from .selectors import (
    capa_en_retard, chantier_peut_cloturer, courbes_iv_for_chantier,
    criticite_summary, document_unique_valide, hold_points_status,
    iso9001_readiness, permis_travail_expirant, photos_controle_par_phase,
    procedure_qualite_courante, procedure_qualite_versions,
    procedures_qualite_courantes, satisfaction_moyenne,
)
from .services import (
    activer_procedure, calculer_score_audit, calculer_score_notation,
    cloturer_ncr, creer_ncr_depuis_reserve, instancier_plan_chantier,
    lever_ncr_audit, nouvelle_version_procedure, relancer_capa_en_retard,
    verifier_efficacite_capa,
)


class _QhseBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class _ChatterMixin:
    """QHSE14 — chatter (historique style Odoo) sur une entité QHSE.

    Ajoute deux actions détail :

    * ``GET …/<id>/historique/`` — l'historique de l'objet (le plus récent
      d'abord), scopé société ;
    * ``POST …/<id>/noter/`` — ajoute une note manuelle (``body`` requis).

    Trace aussi automatiquement la création (``perform_create``) et les
    changements des champs déclarés dans ``CHATTER_FIELDS`` (``perform_update``).
    """
    # {nom_attribut: libellé} des champs suivis automatiquement.
    CHATTER_FIELDS = {}

    def perform_create(self, serializer):
        obj = serializer.save(company=self.request.user.company)
        chatter.log_creation(obj, self.request.user)
        return obj

    def perform_update(self, serializer):
        before = {
            field: getattr(serializer.instance, field)
            for field in self.CHATTER_FIELDS
        }
        obj = serializer.save()
        for field, label in self.CHATTER_FIELDS.items():
            chatter.log_field_change(
                obj, self.request.user, field,
                before.get(field), getattr(obj, field), label=label)
        return obj

    @action(detail=True, methods=['get'])
    def historique(self, request, pk=None):
        obj = self.get_object()
        entries = chatter.chatter_for(
            request.user.company,
            chatter.cible_type_for(obj),
            obj.id)
        return Response(QhseChatterEntrySerializer(entries, many=True).data)

    @action(detail=True, methods=['post'])
    def noter(self, request, pk=None):
        obj = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response(
                {'detail': 'body est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        entry = chatter.log_note(obj, request.user, body)
        return Response(
            QhseChatterEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED)


class NonConformiteViewSet(_ChatterMixin, _QhseBaseViewSet):
    """Fiches de non-conformité (QHSE9). Recherche par référence/titre/origine."""
    queryset = NonConformite.objects.all()
    serializer_class = NonConformiteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'titre', 'origine']
    ordering_fields = ['id', 'date_detection', 'date_creation']
    # QHSE14 — champs suivis dans le chatter de la NCR.
    CHATTER_FIELDS = {
        'statut': 'Statut',
        'gravite': 'Gravité',
        'titre': 'Titre',
    }

    def perform_create(self, serializer):
        obj = serializer.save(
            company=self.request.user.company,
            signale_par=self.request.user)
        chatter.log_creation(obj, self.request.user)
        return obj

    @action(detail=False, methods=['post'], url_path='depuis-reserve')
    def depuis_reserve(self, request):
        """Crée une NCR à partir d'une réserve de chantier (QHSE11).

        Corps : ``reserve`` (id de la ``installations.Reserve``), ``gravite``
        optionnelle. La réserve est lue via le sélecteur d'``installations``
        (scopé société) ; ``signale_par`` et ``company`` sont posés côté serveur.
        Idempotent : une seule NCR par réserve. 404 si la réserve n'appartient
        pas à la société.
        """
        reserve_id = request.data.get('reserve')
        if reserve_id in (None, ''):
            return Response(
                {'detail': 'reserve est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ncr, created = creer_ncr_depuis_reserve(
                reserve_id=reserve_id,
                company=request.user.company,
                signale_par=request.user,
                gravite=request.data.get('gravite') or None,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(self.get_serializer(ncr).data, status=code)

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """Clôture une NCR — conditionnée à l'efficacité des CAPA (QHSE13).

        Refuse (400) tant qu'une CAPA n'est pas vérifiée efficace. ``get_object``
        scopé société (404 hors société). Idempotent si déjà clôturée.
        """
        ncr = self.get_object()
        try:
            cloturer_ncr(ncr)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(ncr).data)


class ActionCorrectivePreventiveViewSet(_ChatterMixin, _QhseBaseViewSet):
    """Actions correctives / préventives (CAPA — QHSE10)."""
    queryset = ActionCorrectivePreventive.objects.select_related(
        'non_conformite').all()
    serializer_class = ActionCorrectivePreventiveSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'cause_racine']
    ordering_fields = ['id', 'echeance', 'date_creation']
    # QHSE14 — champs suivis dans le chatter de la CAPA.
    CHATTER_FIELDS = {
        'statut': 'Statut',
        'echeance': 'Échéance',
    }

    @action(detail=False, methods=['get'], url_path='en-retard')
    def en_retard(self, request):
        """CAPA en retard de la société (échéance passée, non résolue — QHSE12).

        Lecture seule, scopée société via le sélecteur ``capa_en_retard``.
        """
        qs = capa_en_retard(request.user.company)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='relancer-retards')
    def relancer_retards(self, request):
        """Relance les CAPA en retard : notifie chaque responsable + digest.

        Notifications best-effort (in-app) ; ne mute aucune CAPA. Renvoie le
        digest (total / notifiées / sans responsable / items). Scopé société.
        """
        digest = relancer_capa_en_retard(request.user.company)
        return Response(digest)

    @action(detail=True, methods=['post'], url_path='verifier-efficacite')
    def verifier_efficacite(self, request, pk=None):
        """Vérifie l'efficacité d'une CAPA réalisée (QHSE13).

        Corps : ``efficace`` (bool requis), ``commentaire`` optionnel.
        ``efficace=True`` → statut VÉRIFIÉE ; ``False`` → repasse EN COURS.
        Refuse (400) si la CAPA n'est pas encore réalisée. ``verifiee_par`` posé
        côté serveur. ``get_object`` scopé société.
        """
        capa = self.get_object()
        efficace = request.data.get('efficace')
        if efficace is None:
            return Response(
                {'detail': 'efficace est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            verifier_efficacite_capa(
                capa,
                efficace=bool(efficace),
                verifiee_par=request.user,
                commentaire=request.data.get('commentaire', ''))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(capa).data)


class PlanInspectionModeleViewSet(_QhseBaseViewSet):
    """Modèles de plan d'inspection (ITP — QHSE2). Recherche par code/nom."""
    queryset = PlanInspectionModele.objects.all()
    serializer_class = PlanInspectionModeleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom', 'description']
    ordering_fields = ['id', 'nom', 'date_creation']


class PointControleModeleViewSet(_QhseBaseViewSet):
    """Points de contrôle d'un modèle de plan d'inspection (ITP — QHSE2)."""
    queryset = PointControleModele.objects.select_related('plan').all()
    serializer_class = PointControleModeleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['intitule', 'phase', 'description']
    ordering_fields = ['id', 'ordre', 'date_creation']


class PlanInspectionChantierViewSet(_QhseBaseViewSet):
    """Plans d'inspection appliqués à un chantier (ITP instancié — QHSE4).

    ``POST instancier`` ouvre un plan à partir d'un modèle + un ``chantier_id``
    et matérialise un relevé par point du modèle (idempotent).
    """
    queryset = PlanInspectionChantier.objects.select_related('modele').all()
    serializer_class = PlanInspectionChantierSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_ouverture', 'date_creation']

    @action(detail=False, methods=['post'])
    def instancier(self, request):
        """Ouvre un plan chantier depuis un modèle ITP + un chantier_id.

        Société posée côté serveur ; le modèle doit appartenir à la société
        de l'utilisateur (sinon 404). Idempotent.
        """
        company = request.user.company
        modele_id = request.data.get('modele')
        chantier_id = request.data.get('chantier_id')
        if not modele_id or chantier_id in (None, ''):
            return Response(
                {'detail': 'modele et chantier_id sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        # Scopé société : un modèle d'une autre société renvoie 404.
        modele = get_object_or_404(
            PlanInspectionModele, pk=modele_id, company=company)
        plan = instancier_plan_chantier(
            modele=modele,
            chantier_id=chantier_id,
            company=company,
            date_ouverture=request.data.get('date_ouverture') or None,
        )
        data = self.get_serializer(plan).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='hold-points')
    def hold_points(self, request, pk=None):
        """État de gating des points d'arrêt (QHSE6) du plan chantier.

        Renvoie ``peut_avancer`` et la liste des points d'arrêt bloquants (relevé
        absent ou non conforme). ``get_object`` est scopé société (TenantMixin),
        donc un plan d'une autre société renvoie 404. Lecture seule : ne mute
        jamais l'état du chantier — c'est une porte que l'appelant consulte.
        """
        plan = self.get_object()
        return Response(hold_points_status(plan))


class ReleveControleViewSet(_QhseBaseViewSet):
    """Relevés de contrôle d'un plan d'inspection chantier (QHSE4).

    À la création/maj d'un relevé, ``releve_par`` est posé côté serveur.
    """
    queryset = ReleveControle.objects.select_related(
        'plan_chantier', 'point').all()
    serializer_class = ReleveControleSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_releve', 'date_creation']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            releve_par=self.request.user)

    @action(detail=True, methods=['get'])
    def photos(self, request, pk=None):
        """Photos de contrôle d'un relevé, regroupées par phase (QHSE8).

        Renvoie ``{'avant': [...], 'pendant': [...], 'apres': [...],
        'autres': [...]}``. Les pièces jointes sont des ``records.Attachment``
        ciblant ce relevé ; l'upload se fait via l'API records standard
        (``POST /api/django/records/attachments/`` avec ``model=qhse.relevecontrole``
        + ``phase``). ``get_object`` est scopé société (TenantMixin) — un relevé
        d'une autre société renvoie 404. Lecture seule.
        """
        from apps.records.serializers import AttachmentSerializer
        releve = self.get_object()
        groupes = photos_controle_par_phase(releve)
        return Response({
            phase: AttachmentSerializer(atts, many=True).data
            for phase, atts in groupes.items()
        })


class ReleveCourbeIVViewSet(_QhseBaseViewSet):
    """Relevés de courbe I-V par string PV à la mise en service (QHSE7).

    À la création, ``releve_par`` est posé côté serveur. Filtre optionnel par
    ``?chantier_id=`` (référence lâche au chantier). ``releves`` (action) liste
    les courbes I-V d'un chantier donné via le sélecteur dédié, scopé société.
    """
    queryset = ReleveCourbeIV.objects.select_related('plan_chantier').all()
    serializer_class = ReleveCourbeIVSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['string_id', 'notes']
    ordering_fields = ['id', 'string_id', 'date_releve', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            releve_par=self.request.user)

    @action(detail=False, methods=['get'], url_path='par-chantier')
    def par_chantier(self, request):
        """Courbes I-V d'un chantier (``?chantier_id=``), scopées société.

        Lecture seule : délègue au sélecteur ``courbes_iv_for_chantier`` qui ne
        renvoie que les relevés de la société de l'utilisateur.
        """
        chantier_id = request.query_params.get('chantier_id')
        if chantier_id in (None, ''):
            return Response(
                {'detail': 'chantier_id est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        qs = courbes_iv_for_chantier(request.user.company, chantier_id)
        return Response(self.get_serializer(qs, many=True).data)


class GrilleAuditViewSet(_QhseBaseViewSet):
    """Grilles d'audit pondérées (QHSE15). Recherche par code/nom."""
    queryset = GrilleAudit.objects.all()
    serializer_class = GrilleAuditSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom', 'description']
    ordering_fields = ['id', 'nom', 'date_creation']


class CritereAuditViewSet(_QhseBaseViewSet):
    """Critères pondérés d'une grille d'audit (QHSE15).

    Filtre optionnel par ``?grille=``. La société est posée côté serveur ; la
    grille référencée est validée même-société par le sérialiseur.
    """
    queryset = CritereAudit.objects.select_related('grille').all()
    serializer_class = CritereAuditSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['intitule', 'categorie', 'description']
    ordering_fields = ['id', 'ordre', 'poids', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        grille = self.request.query_params.get('grille')
        if grille not in (None, ''):
            qs = qs.filter(grille_id=grille)
        return qs


class AuditViewSet(_QhseBaseViewSet):
    """Audits (sessions d'exécution d'une grille — QHSE16).

    ``POST …/<id>/calculer-score/`` — calcule et stocke le score pondéré.
    ``POST …/<id>/lever-ncr/`` — lève une NCR pour chaque réponse non conforme
    (idempotent : ne duplique pas une NCR déjà existante).
    """
    queryset = Audit.objects.select_related('grille', 'auditeur').all()
    serializer_class = AuditSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['grille__nom', 'notes']
    ordering_fields = ['id', 'date_audit', 'date_creation', 'score']

    def get_queryset(self):
        qs = super().get_queryset()
        grille = self.request.query_params.get('grille')
        if grille not in (None, ''):
            qs = qs.filter(grille_id=grille)
        return qs

    @action(detail=True, methods=['post'], url_path='calculer-score')
    def calculer_score(self, request, pk=None):
        """Calcule et stocke le score pondéré de l'audit (% conforme).

        Retourne l'audit mis à jour avec le champ ``score`` renseigné. Les
        critères ``NA`` sont exclus du calcul. ``get_object`` est scopé société.
        """
        audit = self.get_object()
        calculer_score_audit(audit)
        return Response(self.get_serializer(audit).data)

    @action(detail=True, methods=['post'], url_path='lever-ncr')
    def lever_ncr(self, request, pk=None):
        """Lève une NCR pour chaque réponse non conforme (QHSE16 → NCR).

        Idempotent : une ``ReponseCritere`` ayant déjà un ``ncr_id`` n'est pas
        dupliquée. ``signale_par`` est posé côté serveur. ``get_object`` est
        scopé société. Retourne ``{'creees': [...], 'existantes': [...]}``.
        """
        audit = self.get_object()
        result = lever_ncr_audit(audit, signale_par=request.user)
        return Response(result, status=status.HTTP_200_OK)


class ReponseCritereViewSet(_QhseBaseViewSet):
    """Réponses aux critères d'audit (QHSE16).

    Filtre optionnel par ``?audit=``. La société est posée côté serveur ; les
    FKs ``audit`` et ``critere`` sont validés même-société par le sérialiseur.
    Un seul enregistrement par (audit, critère) — l'unicité est gérée par la
    contrainte DB (unique_together) et une réponse peut être mise à jour (PATCH).
    """
    queryset = ReponseCritere.objects.select_related(
        'audit', 'critere').all()
    serializer_class = ReponseCritereSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'critere__ordre', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        audit = self.request.query_params.get('audit')
        if audit not in (None, ''):
            qs = qs.filter(audit_id=audit)
        return qs


class QhseChatterEntryViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Chatter QHSE en lecture seule (QHSE14).

    Filtre par ``?cible_type=`` (ncr/capa/incident/audit) + ``?cible_id=``. Les
    écritures passent par les actions ``noter`` / le log auto des viewsets NCR et
    CAPA — jamais par cet endpoint. Scopé société (TenantMixin), palier
    Responsable/Admin.
    """
    permission_classes = [IsResponsableOrAdmin]
    queryset = QhseChatterEntry.objects.select_related('user').all()
    serializer_class = QhseChatterEntrySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        cible_type = self.request.query_params.get('cible_type')
        cible_id = self.request.query_params.get('cible_id')
        if cible_type:
            qs = qs.filter(cible_type=cible_type)
        if cible_id not in (None, ''):
            qs = qs.filter(cible_id=cible_id)
        return qs


# ── QHSE17 — Notation fin de chantier (gate clôture) ────────────────────────

class NotationFinChantierViewSet(_QhseBaseViewSet):
    """Notations fin de chantier — gate advisory de clôture (QHSE17).

    À la création, ``auteur`` est posé côté serveur. Filtre optionnel par
    ``?chantier_id=``. L'action ``calculer`` (POST) recalcule le score pondéré et
    le verdict (passe/échec) à partir des ``ItemNotation`` de la notation.

    L'action ``peut-cloturer`` (GET) expose le verdict advisory du sélecteur
    ``chantier_peut_cloturer`` pour un chantier donné (``?chantier_id=``).
    """
    queryset = NotationFinChantier.objects.select_related('auteur').all()
    serializer_class = NotationFinChantierSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_notation', 'score', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            auteur=self.request.user)

    @action(detail=True, methods=['post'])
    def calculer(self, request, pk=None):
        """Calcule et stocke le score pondéré + verdict de la notation.

        Retourne la notation mise à jour. ``get_object`` est scopé société.
        """
        notation = self.get_object()
        calculer_score_notation(notation)
        return Response(self.get_serializer(notation).data)

    @action(detail=False, methods=['get'], url_path='peut-cloturer')
    def peut_cloturer(self, request):
        """Gate advisory : le chantier peut-il clôturer ?

        Paramètre obligatoire ``?chantier_id=``. Renvoie
        ``{'chantier_id': …, 'peut_cloturer': bool}``. Scopé société.
        """
        chantier_id = request.query_params.get('chantier_id')
        if chantier_id in (None, ''):
            return Response(
                {'detail': 'chantier_id est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            chantier_id = int(chantier_id)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'chantier_id doit être un entier.'},
                status=status.HTTP_400_BAD_REQUEST)
        peut = chantier_peut_cloturer(chantier_id, request.user.company)
        return Response({'chantier_id': chantier_id, 'peut_cloturer': peut})


class ItemNotationViewSet(_QhseBaseViewSet):
    """Items de notation fin de chantier (QHSE17).

    Filtre optionnel par ``?notation=``. La société est posée côté serveur ; la
    notation référencée est validée même-société par le sérialiseur.
    """
    queryset = ItemNotation.objects.select_related('notation').all()
    serializer_class = ItemNotationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'ordre', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        notation = self.request.query_params.get('notation')
        if notation not in (None, ''):
            qs = qs.filter(notation_id=notation)
        return qs


# ── QHSE18 — Procédure qualité versionnée (docs qualité GED) ────────────────

class ProcedureQualiteViewSet(_QhseBaseViewSet):
    """Procédures qualité versionnées (QHSE18).

    Une procédure est identifiée par sa ``reference`` et historisée par
    ``version`` : la création route par le service ``nouvelle_version_procedure``
    qui calcule la version suivante côté serveur (jamais ``count()+1``), donc
    poster deux fois la même ``reference`` empile v1, v2… sans rien écraser.
    ``version`` et ``statut`` ne sont jamais lus du corps de requête ;
    ``company`` et ``auteur`` sont posés côté serveur.

    Filtres optionnels : ``?reference=`` (toutes les versions d'une référence),
    ``?courantes=1`` (uniquement la version courante de chaque référence).

    Actions :
    * ``POST …/<id>/activer/`` — met cette version en vigueur et rend les autres
      versions de la référence obsolètes ;
    * ``GET …/courante/?reference=`` — version courante d'une référence ;
    * ``GET …/<id>/versions/`` — toutes les versions de la référence de l'objet.
    """
    queryset = ProcedureQualite.objects.select_related('auteur').all()
    serializer_class = ProcedureQualiteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'titre', 'contenu']
    ordering_fields = ['id', 'reference', 'version', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        reference = self.request.query_params.get('reference')
        if reference not in (None, ''):
            qs = qs.filter(reference=reference)
        if self.request.query_params.get('courantes') in ('1', 'true', 'True'):
            ids = [
                p.id
                for p in procedures_qualite_courantes(self.request.user.company)
            ]
            qs = qs.filter(id__in=ids)
        return qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        return nouvelle_version_procedure(
            company=self.request.user.company,
            reference=data['reference'],
            titre=data['titre'],
            contenu=data.get('contenu', ''),
            document_id=data.get('document_id'),
            auteur=self.request.user,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        procedure = self.perform_create(serializer)
        out = self.get_serializer(procedure)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def activer(self, request, pk=None):
        """Met cette version en vigueur ; les autres versions deviennent obsolètes.

        ``get_object`` est scopé société (404 hors société). ``date_application``
        optionnelle (défaut : aujourd'hui).
        """
        procedure = self.get_object()
        activer_procedure(
            procedure, date_application=request.data.get('date_application'))
        return Response(self.get_serializer(procedure).data)

    @action(detail=False, methods=['get'])
    def courante(self, request):
        """Version courante d'une procédure (``?reference=``), scopée société.

        La version courante est celle en vigueur, à défaut la plus haute. 400 si
        ``reference`` absente, 404 si aucune version pour cette référence.
        """
        reference = request.query_params.get('reference')
        if reference in (None, ''):
            return Response(
                {'detail': 'reference est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        procedure = procedure_qualite_courante(request.user.company, reference)
        if procedure is None:
            return Response(
                {'detail': 'Aucune procédure pour cette référence.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(procedure).data)

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Toutes les versions de la référence de cette procédure (récent d'abord).

        ``get_object`` est scopé société. Lecture seule.
        """
        procedure = self.get_object()
        qs = procedure_qualite_versions(
            request.user.company, procedure.reference)
        return Response(self.get_serializer(qs, many=True).data)


class RetourClientQualiteViewSet(_QhseBaseViewSet):
    """Retours client de satisfaction qualité (QHSE19).

    CRUD scopé société. ``company`` posée côté serveur (jamais lue du corps).
    Liens cross-app par référence lâche (``chantier_id`` / ``client_id``).
    Filtres optionnels : ``?chantier_id=`` / ``?traite=1|0``. Recherche par
    commentaire/canal, tri par date/note.

    Action ``GET …/moyenne/`` — note de satisfaction moyenne de la société,
    optionnellement filtrée par ``?chantier_id=``.
    """
    queryset = RetourClientQualite.objects.all()
    serializer_class = RetourClientQualiteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['commentaire', 'canal']
    ordering_fields = ['id', 'date_retour', 'note_satisfaction',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        traite = self.request.query_params.get('traite')
        if traite in ('1', 'true', 'True'):
            qs = qs.filter(traite=True)
        elif traite in ('0', 'false', 'False'):
            qs = qs.filter(traite=False)
        return qs

    @action(detail=False, methods=['get'])
    def moyenne(self, request):
        """Note de satisfaction moyenne de la société (``?chantier_id=`` opt.).

        Renvoie ``{'moyenne': float|null, 'total': int}``. Scopé société.
        """
        chantier_id = request.query_params.get('chantier_id') or None
        qs = self.get_queryset()
        if chantier_id is not None:
            qs = qs.filter(chantier_id=chantier_id)
        return Response({
            'moyenne': satisfaction_moyenne(
                request.user.company, chantier_id=chantier_id),
            'total': qs.count(),
        })


# ── QHSE20 — Tableau de bord « ISO 9001 readiness » ─────────────────────────

class Iso9001ReadinessViewSet(viewsets.ViewSet):
    """Tableau de bord « ISO 9001 readiness » en lecture seule (QHSE20).

    ``GET …/iso9001-readiness/`` renvoie un score global de préparation ISO 9001
    et une ventilation par critère (NCR clôturées, CAPA dans les délais, audits
    réalisés, procédures publiées, couverture ITP, satisfaction client), chacun
    rattaché à sa clause ISO 9001:2015. Agrégation PURE des données QHSE
    existantes — aucun modèle, aucune mutation. Scopé société : le sélecteur ne
    lit que les données de ``request.user.company``. Palier Responsable/Admin.
    """
    permission_classes = [IsResponsableOrAdmin]

    def list(self, request):
        return Response(iso9001_readiness(request.user.company))


# ── QHSE21 — Évaluation des risques (document unique) ───────────────────────

class EvaluationRisqueViewSet(_QhseBaseViewSet):
    """Évaluations des risques — document unique (QHSE21).

    CRUD scopé société. ``company`` et ``evaluateur`` sont posés côté serveur
    (jamais lus du corps). La ``reference`` est attribuée côté serveur via
    ``create_with_reference`` (plus haut numéro utilisé + 1, race-safe — jamais
    count()+1). Filtres optionnels : ``?statut=`` / ``?chantier_id=``. Recherche
    par référence/titre, tri par date/référence.

    Action ``GET …/<id>/criticite/`` — résumé de criticité (nb lignes, max,
    moyenne avec garde-fou division par zéro, répartition par bande).
    """
    queryset = EvaluationRisque.objects.select_related(
        'evaluateur').prefetch_related('lignes').all()
    serializer_class = EvaluationRisqueSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'titre', 'notes']
    ordering_fields = ['id', 'reference', 'date_evaluation', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        return create_with_reference(
            EvaluationRisque, 'DUER', company,
            lambda reference: serializer.save(
                company=company,
                evaluateur=self.request.user,
                reference=reference),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        evaluation = self.perform_create(serializer)
        out = self.get_serializer(evaluation)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def criticite(self, request, pk=None):
        """Résumé de criticité de l'évaluation (``get_object`` scopé société).

        Renvoie ``{nb_lignes, criticite_max, criticite_moyenne, par_niveau}``.
        ``criticite_moyenne`` est ``None`` si aucune ligne (pas de division par
        zéro).
        """
        evaluation = self.get_object()
        return Response(criticite_summary(evaluation))

    @action(detail=False, methods=['get'], url_path='document-unique-statut')
    def document_unique_statut(self, request):
        """État du « document unique requis avant pose » d'un chantier (QHSE22).

        Gate advisory en lecture seule. Paramètre obligatoire ``?chantier_id=``
        (entier). Renvoie le dict de ``document_unique_valide`` :
        ``{chantier_id, valide, evaluation_id, reference, nb_validees,
        nb_validees_avec_lignes, motif}``. Scopé société. ``installations`` peut
        s'appuyer dessus (ou sur le service ``exiger_document_unique``) pour
        GATER la transition vers la pose — l'enforcement reste côté appelant.
        """
        chantier_id = request.query_params.get('chantier_id')
        if chantier_id in (None, ''):
            return Response(
                {'detail': 'chantier_id est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            chantier_id = int(chantier_id)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'chantier_id doit être un entier.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            document_unique_valide(request.user.company, chantier_id))


class LigneEvaluationRisqueViewSet(_QhseBaseViewSet):
    """Lignes d'une évaluation des risques (QHSE21).

    CRUD scopé société. ``company`` posée côté serveur ; le FK ``evaluation``
    est validé même-société par le sérialiseur. La ``criticite`` est calculée et
    stockée côté serveur (gravité × probabilité) — jamais lue du corps. Filtre
    optionnel par ``?evaluation=``. Tri par ordre/criticité.
    """
    queryset = LigneEvaluationRisque.objects.select_related(
        'evaluation').all()
    serializer_class = LigneEvaluationRisqueSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['danger', 'poste', 'activite']
    ordering_fields = ['id', 'ordre', 'criticite', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        evaluation = self.request.query_params.get('evaluation')
        if evaluation not in (None, ''):
            qs = qs.filter(evaluation_id=evaluation)
        return qs


class PermisTravailViewSet(_QhseBaseViewSet):
    """Permis de travail — autorisations préalables aux travaux à risque (QHSE23).

    CRUD scopé société. ``company`` est posée côté serveur (jamais lue du corps).
    La ``reference`` est attribuée côté serveur via ``create_with_reference``
    (plus haut numéro utilisé + 1, race-safe — jamais count()+1). Filtres
    optionnels : ``?type_permis=`` / ``?statut=`` / ``?chantier_id=``. Recherche
    par référence/titre/délivreur, tri par date/référence.

    Le ``statut`` est en lecture seule au CRUD et n'est piloté que par deux
    actions détail :

    * ``POST …/<id>/valider/`` — passe ``brouillon`` → ``valide`` (refuse si déjà
      clôturé/expiré) ;
    * ``POST …/<id>/cloturer/`` — passe ``valide``/``brouillon`` → ``cloture``.
    """
    queryset = PermisTravail.objects.all()
    serializer_class = PermisTravailSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'titre', 'delivre_par', 'valide_par']
    ordering_fields = [
        'id', 'reference', 'date_debut', 'date_fin', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        type_permis = self.request.query_params.get('type_permis')
        if type_permis not in (None, ''):
            qs = qs.filter(type_permis=type_permis)
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        return create_with_reference(
            PermisTravail, 'PT', company,
            lambda reference: serializer.save(
                company=company, reference=reference),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permis = self.perform_create(serializer)
        out = self.get_serializer(permis)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valide le permis (``brouillon`` → ``valide``), scopé société.

        Refuse si le permis est déjà clôturé ou expiré. ``valide_par`` peut être
        fourni au corps (chaîne libre) pour tracer le valideur ; sinon le nom de
        l'utilisateur courant est posé côté serveur.
        """
        permis = self.get_object()
        if permis.statut in (
                PermisTravail.Statut.CLOTURE, PermisTravail.Statut.EXPIRE):
            return Response(
                {'detail': 'Un permis clôturé ou expiré ne peut être validé.'},
                status=status.HTTP_400_BAD_REQUEST)
        valide_par = (request.data.get('valide_par')
                      or request.user.username or '')
        permis.statut = PermisTravail.Statut.VALIDE
        permis.valide_par = valide_par
        permis.save(update_fields=['statut', 'valide_par'])
        return Response(self.get_serializer(permis).data)

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """Clôture le permis (``brouillon``/``valide`` → ``cloture``), scopé société.

        Refuse si le permis est déjà clôturé.
        """
        permis = self.get_object()
        if permis.statut == PermisTravail.Statut.CLOTURE:
            return Response(
                {'detail': 'Permis déjà clôturé.'},
                status=status.HTTP_400_BAD_REQUEST)
        permis.statut = PermisTravail.Statut.CLOTURE
        permis.save(update_fields=['statut'])
        return Response(self.get_serializer(permis).data)

    @action(detail=False, methods=['get'])
    def expirant(self, request):
        """Permis de travail qui expirent bientôt ou sont déjà expirés (QHSE25).

        Alerte de renouvellement / clôture : ``?expire_within=N`` (défaut 30)
        fixe la fenêtre en jours ; ``?inclure_expires=0`` ne garde que les
        échéances encore à venir (par défaut on inclut aussi les permis dont la
        fin de validité — ``date_fin`` — est déjà passée, qui sont précisément
        ceux à solder). Les permis clôturés et ceux sans ``date_fin`` sont
        exclus. S'appuie sur ``selectors.permis_travail_expirant`` — scopé
        société.
        """
        within = request.query_params.get('expire_within', 30)
        inclure = request.query_params.get('inclure_expires') \
            not in ('0', 'false', 'False')
        qs = permis_travail_expirant(
            request.user.company, within_days=within,
            inclure_expires=inclure)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class ConsignationLotoViewSet(_QhseBaseViewSet):
    """Consignation électrique (LOTO) rattachée à un permis (QHSE24).

    CRUD scopé société. ``company`` est posée côté serveur (jamais lue du
    corps). La ``reference`` est attribuée côté serveur via
    ``create_with_reference`` (plus haut numéro utilisé + 1, race-safe — jamais
    count()+1). Filtres optionnels : ``?permis=`` / ``?statut=``. Recherche par
    référence/équipement/point de consignation/consignateur.

    Le ``statut`` et la ``date_deconsignation`` sont en lecture seule au CRUD et
    ne sont pilotés que par une action détail :

    * ``POST …/<id>/deconsigner/`` — passe ``consignee`` → ``deconsignee`` et
      enregistre ``date_deconsignation`` (refuse si déjà déconsignée).
    """
    queryset = ConsignationLoto.objects.all()
    serializer_class = ConsignationLotoSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'equipement', 'point_consignation', 'consignateur']
    ordering_fields = [
        'id', 'reference', 'date_consignation', 'date_deconsignation',
        'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        permis = self.request.query_params.get('permis')
        if permis not in (None, ''):
            qs = qs.filter(permis_id=permis)
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        return create_with_reference(
            ConsignationLoto, 'LOTO', company,
            lambda reference: serializer.save(
                company=company, reference=reference),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consignation = self.perform_create(serializer)
        out = self.get_serializer(consignation)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def deconsigner(self, request, pk=None):
        """Déconsigne (``consignee`` → ``deconsignee``), scopé société.

        Enregistre ``date_deconsignation`` (maintenant côté serveur, sauf si
        une date ISO est fournie au corps via ``date_deconsignation``) et bascule
        le ``statut``. Refuse si la consignation est déjà déconsignée.
        ``consignateur`` peut être complété au corps si vide.
        """
        consignation = self.get_object()
        if consignation.statut == ConsignationLoto.Statut.DECONSIGNEE:
            return Response(
                {'detail': 'Consignation déjà déconsignée.'},
                status=status.HTTP_400_BAD_REQUEST)
        date_deconsignation = (
            request.data.get('date_deconsignation') or timezone.now())
        consignation.date_deconsignation = date_deconsignation
        consignation.statut = ConsignationLoto.Statut.DECONSIGNEE
        consignation.save(
            update_fields=['statut', 'date_deconsignation'])
        return Response(self.get_serializer(consignation).data)


class InductionSecuriteViewSet(_QhseBaseViewSet):
    """Accueil / induction sécurité préalable à l'accès au site (QHSE26).

    CRUD scopé société. ``company`` est posée côté serveur (jamais lue du
    corps). Couvre les salariés ET les sous-traitants externes : ``personne_nom``
    est libre, et un externe est tracé par ``est_sous_traitant`` +
    ``entreprise_externe`` (un salarié interne peut en plus être relié par
    ``employe``, FK-chaîne vers ``rh.DossierEmploye``). Filtres optionnels :
    ``?chantier_id=`` / ``?est_sous_traitant=`` / ``?employe=``. Recherche par
    personne/entreprise/animateur/thèmes, tri par date.

    L'``acquittement_le`` est en lecture seule au CRUD et n'est posé que par une
    action détail :

    * ``POST …/<id>/acquitter/`` — passe ``acquittement`` à vrai et horodate
      ``acquittement_le`` (date ISO optionnelle au corps via ``acquittement_le``).
    """
    queryset = InductionSecurite.objects.all()
    serializer_class = InductionSecuriteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'personne_nom', 'entreprise_externe', 'anime_par', 'themes']
    ordering_fields = ['id', 'date_induction', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        est_sous_traitant = self.request.query_params.get('est_sous_traitant')
        if est_sous_traitant not in (None, ''):
            qs = qs.filter(
                est_sous_traitant=est_sous_traitant in ('1', 'true', 'True'))
        employe = self.request.query_params.get('employe')
        if employe not in (None, ''):
            qs = qs.filter(employe_id=employe)
        return qs

    @action(detail=True, methods=['post'])
    def acquitter(self, request, pk=None):
        """Enregistre l'acquittement / signature de l'accueil, scopé société.

        Passe ``acquittement`` à vrai et horodate ``acquittement_le`` (maintenant
        côté serveur, sauf si une date ISO est fournie au corps via
        ``acquittement_le``).
        """
        induction = self.get_object()
        acquittement_le = (
            request.data.get('acquittement_le') or timezone.now())
        induction.acquittement = True
        induction.acquittement_le = acquittement_le
        induction.save(update_fields=['acquittement', 'acquittement_le'])
        return Response(self.get_serializer(induction).data)


class PlanUrgenceViewSet(_QhseBaseViewSet):
    """Plans d'urgence / premiers secours par chantier/site (QHSE28).

    CRUD scopé société. ``company`` est posée côté serveur (jamais lue du
    corps). Regroupe le point de rassemblement, l'hôpital le plus proche
    optionnel, les contacts d'urgence et les secouristes désignés (enfants
    imbriqués en lecture). Filtres optionnels : ``?chantier_id=`` / ``?statut=``.
    Recherche par titre/point de rassemblement/hôpital, tri par date.
    """
    queryset = PlanUrgence.objects.prefetch_related(
        'contacts', 'secouristes').all()
    serializer_class = PlanUrgenceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['titre', 'point_rassemblement', 'hopital_proche']
    ordering_fields = ['id', 'date_revision', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        return qs


class ContactUrgenceViewSet(_QhseBaseViewSet):
    """Contacts d'urgence d'un plan d'urgence (QHSE28).

    CRUD scopé société. ``company`` posée côté serveur ; le FK ``plan`` est
    validé même-société par le sérialiseur. Filtres optionnels : ``?plan=`` /
    ``?type_contact=``. Recherche par nom/téléphone, tri par ordre.
    """
    queryset = ContactUrgence.objects.select_related('plan').all()
    serializer_class = ContactUrgenceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'telephone']
    ordering_fields = ['id', 'ordre', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        if plan not in (None, ''):
            qs = qs.filter(plan_id=plan)
        type_contact = self.request.query_params.get('type_contact')
        if type_contact not in (None, ''):
            qs = qs.filter(type_contact=type_contact)
        return qs


class SecouristeViewSet(_QhseBaseViewSet):
    """Secouristes désignés d'un plan d'urgence (QHSE28).

    CRUD scopé société. ``company`` posée côté serveur ; les FK ``plan`` et
    ``secouriste`` (salarié interne optionnel) sont validés même-société par le
    sérialiseur. Filtres optionnels : ``?plan=`` / ``?secouriste=``. Recherche
    par nom/certification, tri par ordre.
    """
    queryset = Secouriste.objects.select_related('plan', 'secouriste').all()
    serializer_class = SecouristeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'certification']
    ordering_fields = ['id', 'ordre', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        if plan not in (None, ''):
            qs = qs.filter(plan_id=plan)
        secouriste = self.request.query_params.get('secouriste')
        if secouriste not in (None, ''):
            qs = qs.filter(secouriste_id=secouriste)
        return qs
