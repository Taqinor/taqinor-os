"""Vues QHSE (scopées société, accès Administrateur/Responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; la non-conformité enregistre aussi son signaleur
(``signale_par``) côté serveur.
"""
from django.shortcuts import get_object_or_404
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import (
    ActionCorrectivePreventive, Audit, CritereAudit, GrilleAudit,
    ItemNotation, NonConformite, NotationFinChantier,
    PlanInspectionChantier, PlanInspectionModele,
    PointControleModele, QhseChatterEntry, ReleveControle, ReleveCourbeIV,
    ReponseCritere,
)
from .serializers import (
    ActionCorrectivePreventiveSerializer, AuditSerializer,
    CritereAuditSerializer, GrilleAuditSerializer,
    ItemNotationSerializer, NonConformiteSerializer,
    NotationFinChantierSerializer,
    PlanInspectionChantierSerializer, PlanInspectionModeleSerializer,
    PointControleModeleSerializer, QhseChatterEntrySerializer,
    ReleveControleSerializer, ReleveCourbeIVSerializer,
    ReponseCritereSerializer,
)
from . import chatter
from .selectors import (
    capa_en_retard, chantier_peut_cloturer, courbes_iv_for_chantier,
    hold_points_status, photos_controle_par_phase,
)
from .services import (
    calculer_score_audit, calculer_score_notation, cloturer_ncr,
    creer_ncr_depuis_reserve, instancier_plan_chantier, lever_ncr_audit,
    relancer_capa_en_retard, verifier_efficacite_capa,
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
