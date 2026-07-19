"""Vues QHSE (scopées société, accès Administrateur/Responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; la non-conformité enregistre aussi son signaleur
(``signale_par``) côté serveur.
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import (
    action, api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from authentication.mixins import TenantMixin
from authentication.permissions import HasPermissionOrLegacy
from core.permissions import WriteScopedPermissionMixin

from apps.ventes.utils.references import create_with_reference

from .models import (
    ActionCorrectivePreventive, AnalyseIncident, AspectEnvironnemental, Audit,
    BilanCarbone, BordereauSuiviDechet, CauseIncident,
    CodeDefaut,
    ConformiteEnvironnementale, ConsignationLoto, ContactUrgence,
    ControleReception,
    CritereAudit, Dechet, DeclarationCnss, DemandeChangement, Derogation,
    EtapeDeclarationAt,
    EvaluationRisque, ExerciceUrgence, GrilleAudit,
    Incident, IndicateurESG,
    InductionSecurite, InspectionSecurite,
    ItemNotation, LienSignalementPublic, LigneBilanCarbone,
    LigneEvaluationRisque, NonConformite, NotationFinChantier,
    ObservationSecurite,
    PermisTravail, PlanControleReception, PlanInspectionChantier,
    PlanInspectionModele, PlanUrgence,
    PointControleModele, PointControleReception, ProcedureQualite,
    QhseChatterEntry,
    RecyclageModule, ReleveConsommation, ReleveControle,
    ReleveCourbeIV, ReponseCritere, RetourClientQualite,
    RevueVeilleReglementaire, Secouriste,
    SignalementPublic, VeilleReglementaire,
    CheckinSecurite, DemandeActionFournisseur,
)
from .serializers import (
    ActionCorrectivePreventiveSerializer, AnalyseIncidentSerializer,
    AspectEnvironnementalSerializer,
    AuditSerializer, BilanCarboneSerializer, BordereauSuiviDechetSerializer,
    CauseIncidentSerializer,
    CodeDefautSerializer,
    ConformiteEnvironnementaleSerializer,
    ConsignationLotoSerializer, ContactUrgenceSerializer,
    ControleReceptionSerializer,
    CritereAuditSerializer, DechetSerializer, DeclarationCnssSerializer,
    DemandeChangementSerializer,
    DerogationSerializer, EtapeDeclarationAtSerializer,
    EvaluationRisqueSerializer, ExerciceUrgenceSerializer, GrilleAuditSerializer,
    IncidentSerializer,
    IndicateurESGSerializer,
    InductionSecuriteSerializer, InspectionSecuriteSerializer,
    ItemNotationSerializer,
    LienSignalementPublicSerializer,
    LigneBilanCarboneSerializer,
    LigneEvaluationRisqueSerializer,
    NonConformiteSerializer, NotationFinChantierSerializer,
    ObservationSecuriteSerializer,
    PermisTravailSerializer, PlanControleReceptionSerializer,
    PlanInspectionChantierSerializer,
    PlanInspectionModeleSerializer, PlanUrgenceSerializer,
    PointControleModeleSerializer, PointControleReceptionSerializer,
    ProcedureQualiteSerializer, QhseChatterEntrySerializer,
    RecyclageModuleSerializer,
    ReleveConsommationSerializer, ReleveControleSerializer,
    ReleveCourbeIVSerializer,
    ReponseCritereSerializer, RetourClientQualiteSerializer,
    RevueVeilleReglementaireSerializer,
    SecouristeSerializer, SignalementPublicSerializer,
    VeilleReglementaireSerializer,
    CheckinSecuriteSerializer, DemandeActionFournisseurSerializer,
)
from . import chatter
from .selectors import (
    aspects_environnementaux_a_revoir,
    calendrier_qhse,
    capa_en_retard, chantier_peut_cloturer, conformites_a_relancer,
    cout_non_qualite,
    courbes_iv_for_chantier,
    criticite_summary, declarations_cnss_a_echeance, document_unique_valide,
    export_esg,
    hold_points_status,
    heures_travaillees_chantiers,
    iso9001_readiness, pareto_defauts, permis_travail_expirant,
    photos_controle_par_phase,
    procedure_qualite_courante, procedure_qualite_versions,
    procedures_qualite_courantes, satisfaction_moyenne, statistiques_tf_tg,
    taux_conformite_premier_passage, taux_defaillance_par_produit,
)
from .services import (
    activer_procedure, calculer_score_audit, calculer_score_notation,
    cloturer_incident, cloturer_ncr, compteurs_observations_securite,
    conclure_revue_veille,
    creer_capa_mise_en_oeuvre_moc,
    creer_intervention_depuis_ncr, creer_ncr_depuis_reserve,
    creer_ncr_depuis_ticket,
    convertir_observation_en_capa, convertir_observation_en_ncr,
    creer_capa_depuis_ecart_exercice,
    demandes_changement_a_reverser,
    generer_capa_depuis_analyse, generer_lignes_bilan,
    generer_revues_veille_dues,
    creer_signalement_public, generer_qr_signalement,
    incidents_notification_en_retard, initialiser_prochaine_revue,
    instancier_plan_chantier,
    lever_ncr_audit, lever_ncr_inspection, nouvelle_version_procedure,
    plans_exercices_dus, poser_disposition,
    realiser_exercice_urgence,
    relancer_capa_en_retard, relancer_conformites, relancer_demandes_changement,
    relancer_exercices_urgence,
    relancer_notifications_environnement,
    resolve_lien_signalement_public,
    statuer_controle_reception,
    suggerer_analyse_capa, suggerer_classification_incident,
    transitionner_demande_changement,
    SIGNALEMENT_OK,
    verifier_efficacite_capa,
)


class _QhseBaseViewSet(
        WriteScopedPermissionMixin, TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + lecture/écriture fine-grainées (YRBAC3).

    ``qhse_voir`` gate les méthodes sûres (GET/HEAD/OPTIONS), ``qhse_gerer``
    gate l'écriture (POST/PUT/PATCH/DELETE + actions custom). Comptes légacy
    sans rôle fin : repli historique Administrateur/Responsable préservé.
    """
    read_permission = 'qhse_voir'
    write_permission = 'qhse_gerer'


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

    @action(detail=False, methods=['post'], url_path='depuis-ticket-sav')
    def depuis_ticket_sav(self, request):
        """XQHS23 — crée une NCR à partir d'un ticket SAV (pont ticket→NCR).

        Corps : ``ticket`` (id du ``sav.Ticket``), ``gravite`` optionnelle.
        Idempotent : une seule NCR par ticket. 404 si le ticket n'appartient
        pas à la société."""
        ticket_id = request.data.get('ticket')
        if ticket_id in (None, ''):
            return Response(
                {'detail': 'ticket est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ncr, created = creer_ncr_depuis_ticket(
                ticket_id, request.user.company,
                signale_par=request.user,
                gravite=request.data.get('gravite') or None)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(self.get_serializer(ncr).data, status=code)

    @action(detail=True, methods=['post'], url_path='creer-intervention')
    def creer_intervention(self, request, pk=None):
        """XQHS23 — ouvre une intervention corrective SAV depuis cette NCR
        (pont inverse NCR→ticket). 400 si la NCR n'a pas de chantier
        rattaché."""
        ncr = self.get_object()
        try:
            ticket, created = creer_intervention_depuis_ncr(
                ncr, description=request.data.get('description'))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'ticket_id': ticket.pk, 'ticket_reference': ticket.reference,
             'created': created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

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

    @action(detail=False, methods=['get'], url_path='taux-defaillance-produit')
    def taux_defaillance_produit(self, request):
        """XQHS23 — taux de défaillance par produit (NCR d'origine SAV,
        cockpit qualité)."""
        return Response(taux_defaillance_par_produit(request.user.company))

    @action(detail=True, methods=['post'], url_path='poser-disposition')
    def poser_disposition_action(self, request, pk=None):
        """Pose la disposition d'une NCR (XQHS2).

        Corps : ``disposition`` (requis, une des valeurs de
        ``NonConformite.Disposition``), ``cout_disposition`` optionnel,
        ``fournisseur`` (requis si ``retour_fournisseur``),
        ``creer_capa_retouche`` (bool, si ``retouche``). ``disposition_par``
        posé côté serveur (jamais lu du corps).
        """
        ncr = self.get_object()
        disposition = request.data.get('disposition')
        if not disposition:
            return Response(
                {'detail': 'disposition est requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        fournisseur = None
        fournisseur_id = request.data.get('fournisseur')
        if fournisseur_id not in (None, ''):
            from apps.stock.selectors import get_fournisseur_by_id
            fournisseur = get_fournisseur_by_id(
                request.user.company, fournisseur_id)
            if fournisseur is None:
                return Response(
                    {'detail': 'Fournisseur introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
        try:
            poser_disposition(
                ncr, disposition,
                disposition_par=request.user,
                cout_disposition=request.data.get('cout_disposition'),
                fournisseur=fournisseur,
                creer_capa_retouche=bool(
                    request.data.get('creer_capa_retouche')),
                capa_description=request.data.get('capa_description', ''),
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(ncr).data)


class DerogationViewSet(_QhseBaseViewSet):
    """Dérogations (acceptation en l'état bornée) liées à une NCR (XQHS2).

    CRUD scopé société. Filtre optionnel ``?non_conformite=``.
    """
    queryset = Derogation.objects.select_related('non_conformite').all()
    serializer_class = DerogationSerializer
    ordering_fields = ['id', 'date_expiration', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        ncr = self.request.query_params.get('non_conformite')
        if ncr not in (None, ''):
            qs = qs.filter(non_conformite_id=ncr)
        return qs


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
    permission_classes = [HasPermissionOrLegacy('qhse_voir')]
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
    permission_classes = [HasPermissionOrLegacy('qhse_voir')]

    def list(self, request):
        return Response(iso9001_readiness(request.user.company))


# ── QHSE35 — Digest / calendrier QHSE (inspections + permis) ────────────────

class CalendrierQhseViewSet(viewsets.ViewSet):
    """Digest / calendrier QHSE unifié des échéances à venir (QHSE35).

    ``GET …/calendrier/`` agrège, sur une fenêtre ``?within_days=N`` (défaut
    30), les inspections sécurité planifiées (QHSE33), les permis de travail
    expirant/expirés (QHSE25) et les déclarations CNSS à échéance (QHSE30) en
    une liste homogène d'événements de calendrier triés par date, avec un
    drapeau ``en_retard`` par échéance passée. Agrégation PURE des sélecteurs
    QHSE existants — aucune mutation. Scopé société. Palier Responsable/Admin.
    """
    permission_classes = [HasPermissionOrLegacy('qhse_voir')]

    def list(self, request):
        within = request.query_params.get('within_days', 30)
        return Response(
            calendrier_qhse(request.user.company, within_days=within))


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
    search_fields = [
        'reference', 'titre', 'delivre_par__username', 'valide_par__username']
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

        Refuse si le permis est déjà clôturé ou expiré. WIR128 — ``valide_par``
        peut être fourni au corps (id d'utilisateur de la société) pour tracer
        le valideur ; sinon l'utilisateur courant est posé côté serveur (lien
        auditable, jamais du texte libre).
        """
        permis = self.get_object()
        if permis.statut in (
                PermisTravail.Statut.CLOTURE, PermisTravail.Statut.EXPIRE):
            return Response(
                {'detail': 'Un permis clôturé ou expiré ne peut être validé.'},
                status=status.HTTP_400_BAD_REQUEST)
        valideur = request.user
        raw_id = request.data.get('valide_par')
        if raw_id not in (None, ''):
            # Un id explicite doit désigner un utilisateur de la même société.
            candidat = type(request.user).objects.filter(
                pk=raw_id, company=request.user.company).first()
            if candidat is None:
                return Response(
                    {'valide_par': "Utilisateur inconnu pour cette société."},
                    status=status.HTTP_400_BAD_REQUEST)
            valideur = candidat
        permis.statut = PermisTravail.Statut.VALIDE
        permis.valide_par = valideur
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

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        """XQHS27 — PDF INTERNE imprimable (FR/AR), scopé société.

        ``?lang=fr`` (défaut) ou ``?lang=ar`` (gabarit RTL, police arabe
        embarquée). JAMAIS ``/proposal`` — aucun prix, document terrain."""
        from django.http import HttpResponse

        from .pdf_terrain import render_permis_travail_pdf

        permis = self.get_object()
        lang = request.query_params.get('lang', 'fr')
        pdf_bytes = render_permis_travail_pdf(permis, lang=lang)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="permis-travail-{permis.pk}-{lang}.pdf"')
        return response


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

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        """XQHS27 — PDF INTERNE imprimable (FR/AR), scopé société.

        ``?lang=fr`` (défaut) ou ``?lang=ar`` (gabarit RTL, police arabe
        embarquée). JAMAIS ``/proposal`` — aucun prix, document terrain."""
        from django.http import HttpResponse

        from .pdf_terrain import render_induction_securite_pdf

        induction = self.get_object()
        lang = request.query_params.get('lang', 'fr')
        pdf_bytes = render_induction_securite_pdf(induction, lang=lang)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="induction-securite-{induction.pk}-{lang}.pdf"')
        return response


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


class IncidentViewSet(_QhseBaseViewSet):
    """Registre des incidents HSE — accident / presqu'accident / incident (QHSE29).

    CRUD scopé société. ``company`` et ``declare_par`` sont posés côté serveur
    (jamais lus du corps). La ``reference`` est attribuée côté serveur via
    ``create_with_reference`` (plus haut numéro utilisé + 1, race-safe — jamais
    count()+1). Filtres optionnels : ``?type_incident=`` / ``?statut=`` /
    ``?chantier_id=``. Recherche par référence/titre/description, tri par
    date/référence.

    Registre QHSE distinct du volet RH (``rh.AccidentTravail`` /
    ``rh.PresquAccident`` — détail CNSS/blessure/salarié) : aucun import croisé.
    """
    queryset = Incident.objects.select_related('declare_par').all()
    serializer_class = IncidentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'titre', 'description']
    ordering_fields = [
        'id', 'reference', 'date_incident', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        type_incident = self.request.query_params.get('type_incident')
        if type_incident not in (None, ''):
            qs = qs.filter(type_incident=type_incident)
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        incident = create_with_reference(
            Incident, 'INC', company,
            lambda reference: serializer.save(
                company=company,
                declare_par=self.request.user,
                reference=reference),
        )
        # QHSE32 — émet l'événement métier incident_declared sur le signal
        # LOCAL qhse (même patron que ventes→crm) pour que QHSE escalade les
        # incidents critiques. Émission SYNCHRONE ; best-effort côté abonné, donc
        # ne casse jamais la création.
        from .receivers import incident_declared
        incident_declared.send(
            sender=Incident, incident=incident, company=company,
            user=self.request.user, gravite=incident.gravite)
        # ARC38 — RAPATRIE le signal sur le bus core.events (visible cross-app,
        # contrairement au signal local ci-dessus). DOUBLE ÉMISSION assumée
        # pendant la transition (voir docstring core/events.py) : le retrait
        # du signal local est un pas ultérieur distinct.
        from core.events import incident_declared as incident_declared_bus
        incident_declared_bus.send(
            sender=Incident, incident=incident, company=company,
            user=self.request.user, gravite=incident.gravite)
        return incident

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incident = self.perform_create(serializer)
        out = self.get_serializer(incident)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='statistiques-tf-tg')
    def statistiques_tf_tg(self, request):
        """Statistiques TF / TG des accidents du travail (QHSE34).

        TF = (accidents avec arrêt × 1 000 000) / heures travaillées ;
        TG = (jours d'arrêt × 1 000) / heures travaillées.

        Heures travaillées : ``?heures=`` (nombre) OU ``?chantier_ids=1,2,3``
        (sommées depuis RH via le sélecteur ``labour_hours_for_installation``).
        ``?jours_perdus=`` (défaut 0), ``?date_debut=`` / ``?date_fin=``
        (AAAA-MM-JJ) bornent la période. Le compte d'accidents vient du registre
        QHSE (``Incident`` de type ``accident``), scopé société.
        """
        company = request.user.company

        chantier_ids_raw = request.query_params.get('chantier_ids')
        heures_raw = request.query_params.get('heures')
        if heures_raw not in (None, ''):
            heures = heures_raw
        elif chantier_ids_raw not in (None, ''):
            chantier_ids = [
                c.strip() for c in chantier_ids_raw.split(',') if c.strip()]
            heures = heures_travaillees_chantiers(chantier_ids, company=company)
        else:
            heures = 0

        stats = statistiques_tf_tg(
            company,
            heures_travaillees=heures,
            date_debut=request.query_params.get('date_debut') or None,
            date_fin=request.query_params.get('date_fin') or None,
            jours_perdus=request.query_params.get('jours_perdus'),
        )
        # Sérialise les Decimal en chaînes pour un JSON stable.
        stats['heures_travaillees'] = str(stats['heures_travaillees'])
        stats['tf'] = None if stats['tf'] is None else str(stats['tf'])
        stats['tg'] = None if stats['tg'] is None else str(stats['tg'])
        return Response(stats)

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """XQHS19 — clôture un incident (gate : notification requise faite)."""
        incident = self.get_object()
        try:
            incident = cloturer_incident(incident)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(IncidentSerializer(incident).data)

    @action(detail=False, methods=['get'], url_path='notifications-en-retard')
    def notifications_en_retard(self, request):
        incidents = incidents_notification_en_retard(request.user.company)
        return Response(IncidentSerializer(incidents, many=True).data)

    @action(detail=False, methods=['post'], url_path='relancer-notifications')
    def relancer_notifications(self, request):
        incidents = relancer_notifications_environnement(request.user.company)
        return Response({'relances': len(incidents)})


class DeclarationCnssViewSet(_QhseBaseViewSet):
    """Déclarations CNSS d'accident du travail + échéance légale (QHSE30).

    CRUD scopé société. ``company`` est posée côté serveur (jamais lue du
    corps) ; la ``date_limite`` et le ``statut`` sont calculés côté serveur
    (``date_accident`` + ``delai_jours`` / ``statut_calcule``) — jamais lus du
    corps. Le FK ``accident_travail`` pointe vers ``rh.AccidentTravail``
    (FK-chaîne) et est validé même-société par le sérialiseur. Filtres
    optionnels : ``?statut=`` / ``?accident_travail=``. Recherche par
    numéro/notes, tri par échéance/date.

    Action ``GET …/a-echeance/`` — déclarations NON transmises qui approchent
    de l'échéance ou sont déjà hors délai (``?within_days=N``, défaut = délai
    légal), via ``selectors.declarations_cnss_a_echeance``, scopée société.
    """
    queryset = DeclarationCnss.objects.select_related('accident_travail').all()
    serializer_class = DeclarationCnssSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_declaration', 'notes']
    ordering_fields = [
        'id', 'date_limite', 'date_accident', 'date_declaration',
        'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        accident = self.request.query_params.get('accident_travail')
        if accident not in (None, ''):
            qs = qs.filter(accident_travail_id=accident)
        return qs

    @action(detail=False, methods=['get'], url_path='a-echeance')
    def a_echeance(self, request):
        """Déclarations CNSS à échéance ou hors délai (QHSE30).

        Alerte de conformité : ``?within_days=N`` (défaut = délai légal CNSS)
        fixe la fenêtre en jours ; retient les déclarations non transmises dont
        l'échéance tombe au plus tard dans la fenêtre, y compris celles déjà hors
        délai (qui sont précisément à régulariser). S'appuie sur
        ``selectors.declarations_cnss_a_echeance`` — scopé société.
        """
        within = request.query_params.get(
            'within_days', DeclarationCnss.DELAI_LEGAL_JOURS)
        qs = declarations_cnss_a_echeance(
            request.user.company, within_days=within)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        """Crée la déclaration puis instancie sa checklist d'étapes légales
        (XQHS1) — best-effort, ne bloque jamais la création de la déclaration."""
        declaration = serializer.save(company=self.request.user.company)
        try:
            from apps.qhse.services import instancier_etapes_at
            instancier_etapes_at(declaration)
        except Exception:  # pragma: no cover - défensif
            pass
        return declaration

    @action(detail=True, methods=['post'], url_path='generer-etapes')
    def generer_etapes(self, request, pk=None):
        """(Ré)instancie la checklist des étapes légales AT/MP (XQHS1).

        Idempotent — utile si la ``conciliation_statut`` a été activée après
        coup (l'étape conciliation manque alors à l'appel initial).
        """
        from apps.qhse.services import instancier_etapes_at
        declaration = self.get_object()
        etapes = instancier_etapes_at(declaration)
        serializer = EtapeDeclarationAtSerializer(etapes, many=True)
        return Response(serializer.data)


class EtapeDeclarationAtViewSet(_QhseBaseViewSet):
    """Étapes légales datées de la chaîne AT/MP (loi 18-12, XQHS1).

    CRUD scopé société (surtout utilisé en lecture — la création passe par
    ``instancier_etapes_at``). Filtre optionnel ``?declaration=``.

    Action ``POST …/<id>/marquer-fait/`` — marque l'étape réalisée
    (``fait_le`` posé côté serveur, jamais lu du corps).
    """
    queryset = EtapeDeclarationAt.objects.select_related(
        'declaration', 'declaration__accident_travail').all()
    serializer_class = EtapeDeclarationAtSerializer
    ordering_fields = ['id', 'echeance', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        declaration = self.request.query_params.get('declaration')
        if declaration not in (None, ''):
            qs = qs.filter(declaration_id=declaration)
        return qs

    @action(detail=True, methods=['post'], url_path='marquer-fait')
    def marquer_fait(self, request, pk=None):
        from apps.qhse.services import marquer_etape_faite
        etape = self.get_object()
        marquer_etape_faite(etape)
        serializer = self.get_serializer(etape)
        return Response(serializer.data)


class AnalyseIncidentViewSet(_QhseBaseViewSet):
    """Analyses d'incident — arbre des causes → CAPA (QHSE31).

    CRUD scopé société. ``company`` et ``analyste`` sont posés côté serveur
    (jamais lus du corps). Le FK ``incident`` est validé même-société (une seule
    analyse par incident). ``non_conformite`` (NCR-pont vers les CAPA) est piloté
    côté serveur. Filtres optionnels : ``?statut=`` / ``?incident=``.

    Action ``POST …/<id>/generer-capa/`` — génère une CAPA depuis l'analyse
    (``generer_capa_depuis_analyse`` : NCR-pont depuis l'incident + CAPA, mirroir
    du linkage NCR→CAPA existant). Corps optionnel : ``description``,
    ``type_action``, ``echeance``.
    """
    queryset = AnalyseIncident.objects.select_related(
        'incident', 'analyste', 'non_conformite').prefetch_related(
        'causes').all()
    serializer_class = AnalyseIncidentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'synthese']
    ordering_fields = ['id', 'date_analyse', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        incident = self.request.query_params.get('incident')
        if incident not in (None, ''):
            qs = qs.filter(incident_id=incident)
        return qs

    def perform_create(self, serializer):
        return serializer.save(
            company=self.request.user.company,
            analyste=self.request.user)

    @action(detail=True, methods=['post'], url_path='generer-capa')
    def generer_capa(self, request, pk=None):
        """Génère une CAPA à partir de l'analyse (QHSE31).

        ``get_object`` scopé société (404 hors société). NCR-pont créée à la
        première génération puis réutilisée. Renvoie la CAPA créée.
        """
        analyse = self.get_object()
        echeance = request.data.get('echeance') or None
        capa = generer_capa_depuis_analyse(
            analyse,
            description=request.data.get('description') or None,
            type_action=request.data.get('type_action') or None,
            echeance=echeance,
        )
        return Response(
            ActionCorrectivePreventiveSerializer(capa).data,
            status=status.HTTP_201_CREATED)


class CauseIncidentViewSet(_QhseBaseViewSet):
    """Causes (arbre des causes) d'une analyse d'incident (QHSE31).

    CRUD scopé société. ``company`` posée côté serveur ; les FK ``analyse`` /
    ``parent`` sont validés même-société par le sérialiseur, et ``parent`` doit
    appartenir à la même analyse (hiérarchie de l'arbre). Filtres optionnels :
    ``?analyse=`` / ``?parent=`` / ``?type_cause=``.
    """
    queryset = CauseIncident.objects.select_related(
        'analyse', 'parent').all()
    serializer_class = CauseIncidentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle']
    ordering_fields = ['id', 'ordre', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        analyse = self.request.query_params.get('analyse')
        if analyse not in (None, ''):
            qs = qs.filter(analyse_id=analyse)
        parent = self.request.query_params.get('parent')
        if parent not in (None, ''):
            qs = qs.filter(parent_id=parent)
        type_cause = self.request.query_params.get('type_cause')
        if type_cause not in (None, ''):
            qs = qs.filter(type_cause=type_cause)
        return qs


class InspectionSecuriteViewSet(_QhseBaseViewSet):
    """Inspections sécurité planifiées → NCR (QHSE33).

    CRUD scopé société. ``company`` / ``inspecteur`` posés côté serveur (jamais
    lus du corps). La ``reference`` est attribuée côté serveur via
    ``create_with_reference`` (plus haut numéro utilisé + 1, race-safe — jamais
    count()+1). Filtres optionnels : ``?statut=`` / ``?resultat=`` /
    ``?chantier_id=``. Recherche par référence/titre/observations.

    Action détail ``POST …/<id>/lever-ncr/`` — lève une non-conformité (QHSE9)
    depuis une inspection NON CONFORME (idempotent : une seule NCR par
    inspection ; ``gravite`` optionnelle au corps). 400 si l'inspection n'est
    pas non conforme.
    """
    queryset = InspectionSecurite.objects.select_related(
        'inspecteur', 'ncr').all()
    serializer_class = InspectionSecuriteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'titre', 'observations']
    ordering_fields = [
        'id', 'reference', 'date_prevue', 'date_realisee', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        resultat = self.request.query_params.get('resultat')
        if resultat not in (None, ''):
            qs = qs.filter(resultat=resultat)
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        return create_with_reference(
            InspectionSecurite, 'INSP', company,
            lambda reference: serializer.save(
                company=company,
                inspecteur=self.request.user,
                reference=reference),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inspection = self.perform_create(serializer)
        out = self.get_serializer(inspection)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='lever-ncr')
    def lever_ncr(self, request, pk=None):
        """Lève une NCR depuis une inspection NON CONFORME (QHSE33).

        Idempotent : une seule NCR par inspection. ``gravite`` optionnelle au
        corps. 400 si l'inspection n'est pas non conforme.
        """
        inspection = self.get_object()
        try:
            ncr, created = lever_ncr_inspection(
                inspection,
                gravite=request.data.get('gravite') or None,
                signale_par=request.user,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        from .serializers import NonConformiteSerializer
        return Response(NonConformiteSerializer(ncr).data, status=code)


class DechetViewSet(_QhseBaseViewSet):
    """Référentiel des déchets (QHSE36, loi 28-00).

    CRUD scopé société. ``company`` posée côté serveur. Filtres optionnels :
    ``?categorie=`` / ``?actif=``. Recherche par libellé/code.
    """
    queryset = Dechet.objects.all()
    serializer_class = DechetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'code']
    ordering_fields = ['id', 'libelle', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        categorie = self.request.query_params.get('categorie')
        if categorie not in (None, ''):
            qs = qs.filter(categorie=categorie)
        actif = self.request.query_params.get('actif')
        if actif not in (None, ''):
            qs = qs.filter(actif=actif in ('1', 'true', 'True'))
        return qs


class BordereauSuiviDechetViewSet(_QhseBaseViewSet):
    """Bordereaux de suivi des déchets (BSD — QHSE36, loi 28-00).

    CRUD scopé société. ``company`` / ``reference`` posées côté serveur (jamais
    lues du corps). La loi 28-00 réserve le BSD aux déchets DANGEREUX : la
    création d'un bordereau sur un déchet NON dangereux est refusée (400).
    Filtres optionnels : ``?statut=`` / ``?dechet=`` / ``?chantier_id=``.

    Le ``statut`` est piloté par deux actions détail :

    * ``POST …/<id>/enlever/`` — ``emis`` → ``enleve`` (prise en charge
      transporteur) ;
    * ``POST …/<id>/traiter/`` — ``enleve``/``emis`` → ``traite`` (bordereau
      soldé).
    """
    queryset = BordereauSuiviDechet.objects.select_related('dechet').all()
    serializer_class = BordereauSuiviDechetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'producteur', 'transporteur', 'eliminateur']
    ordering_fields = [
        'id', 'reference', 'date_emission', 'date_traitement', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        dechet = self.request.query_params.get('dechet')
        if dechet not in (None, ''):
            qs = qs.filter(dechet_id=dechet)
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        dechet = serializer.validated_data.get('dechet')
        # Loi 28-00 : le BSD est réservé aux déchets DANGEREUX.
        if dechet is not None and not dechet.dangereux:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                {'dechet': 'Le bordereau de suivi (BSD, loi 28-00) est '
                           'réservé aux déchets dangereux.'})
        return create_with_reference(
            BordereauSuiviDechet, 'BSD', company,
            lambda reference: serializer.save(
                company=company, reference=reference),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bsd = self.perform_create(serializer)
        out = self.get_serializer(bsd)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def enlever(self, request, pk=None):
        """Marque le bordereau enlevé (``emis`` → ``enleve``), scopé société.

        Refuse si le bordereau est déjà traité ou annulé. ``date_enlevement``
        optionnelle au corps (sinon aujourd'hui).
        """
        bsd = self.get_object()
        if bsd.statut in (
                BordereauSuiviDechet.Statut.TRAITE,
                BordereauSuiviDechet.Statut.ANNULE):
            return Response(
                {'detail': 'Bordereau déjà traité ou annulé.'},
                status=status.HTTP_400_BAD_REQUEST)
        bsd.statut = BordereauSuiviDechet.Statut.ENLEVE
        bsd.date_enlevement = (
            request.data.get('date_enlevement') or timezone.localdate())
        bsd.save(update_fields=['statut', 'date_enlevement'])
        return Response(self.get_serializer(bsd).data)

    @action(detail=True, methods=['post'])
    def traiter(self, request, pk=None):
        """Marque le bordereau traité (→ ``traite``), scopé société.

        Refuse si le bordereau est déjà traité ou annulé. ``date_traitement``
        optionnelle au corps (sinon aujourd'hui).
        """
        bsd = self.get_object()
        if bsd.statut in (
                BordereauSuiviDechet.Statut.TRAITE,
                BordereauSuiviDechet.Statut.ANNULE):
            return Response(
                {'detail': 'Bordereau déjà traité ou annulé.'},
                status=status.HTTP_400_BAD_REQUEST)
        bsd.statut = BordereauSuiviDechet.Statut.TRAITE
        bsd.date_traitement = (
            request.data.get('date_traitement') or timezone.localdate())
        bsd.save(update_fields=['statut', 'date_traitement'])
        return Response(self.get_serializer(bsd).data)


class RecyclageModuleViewSet(_QhseBaseViewSet):
    """Recyclage / fin de vie des modules PV (QHSE37).

    CRUD scopé société. ``company`` / ``reference`` posées côté serveur (jamais
    lues du corps). Le FK ``bordereau`` (BSD QHSE36) est validé même-société.
    Filtres optionnels : ``?statut=`` / ``?motif=`` / ``?chantier_id=``.
    Recherche par référence/marque/modèle/filière.

    Le ``statut`` est piloté par deux actions détail :

    * ``POST …/<id>/transporter/`` — ``collecte`` → ``transporte`` ;
    * ``POST …/<id>/recycler/`` — ``transporte``/``collecte`` → ``recycle``
      (lot soldé, ``date_recyclage`` posée).
    """
    queryset = RecyclageModule.objects.select_related('bordereau').all()
    serializer_class = RecyclageModuleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'marque', 'modele', 'filiere']
    ordering_fields = [
        'id', 'reference', 'date_collecte', 'date_recyclage', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        motif = self.request.query_params.get('motif')
        if motif not in (None, ''):
            qs = qs.filter(motif=motif)
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        return create_with_reference(
            RecyclageModule, 'REC', company,
            lambda reference: serializer.save(
                company=company, reference=reference),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rec = self.perform_create(serializer)
        out = self.get_serializer(rec)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def transporter(self, request, pk=None):
        """Marque le lot transporté (``collecte`` → ``transporte``).

        Refuse si déjà recyclé ou annulé.
        """
        rec = self.get_object()
        if rec.statut in (
                RecyclageModule.Statut.RECYCLE,
                RecyclageModule.Statut.ANNULE):
            return Response(
                {'detail': 'Lot déjà recyclé ou annulé.'},
                status=status.HTTP_400_BAD_REQUEST)
        rec.statut = RecyclageModule.Statut.TRANSPORTE
        rec.save(update_fields=['statut'])
        return Response(self.get_serializer(rec).data)

    @action(detail=True, methods=['post'])
    def recycler(self, request, pk=None):
        """Marque le lot recyclé (→ ``recycle``), ``date_recyclage`` posée.

        Refuse si déjà recyclé ou annulé. ``date_recyclage`` optionnelle au
        corps (sinon aujourd'hui).
        """
        rec = self.get_object()
        if rec.statut in (
                RecyclageModule.Statut.RECYCLE,
                RecyclageModule.Statut.ANNULE):
            return Response(
                {'detail': 'Lot déjà recyclé ou annulé.'},
                status=status.HTTP_400_BAD_REQUEST)
        rec.statut = RecyclageModule.Statut.RECYCLE
        rec.date_recyclage = (
            request.data.get('date_recyclage') or timezone.localdate())
        rec.save(update_fields=['statut', 'date_recyclage'])
        return Response(self.get_serializer(rec).data)


class ConformiteEnvironnementaleViewSet(_QhseBaseViewSet):
    """Conformités environnementales + relances (QHSE38).

    CRUD scopé société. ``company`` posée côté serveur. Le FK ``responsable``
    est validé même-société. Filtres optionnels : ``?statut=`` /
    ``?type_conformite=`` / ``?chantier_id=``. Recherche par
    intitulé/autorité/référence dossier.

    Actions :

    * ``GET …/a-relancer/`` — conformités à renouveler ou expirées
      (``selectors.conformites_a_relancer``), scopé société ;
    * ``POST …/relancer/`` — notifie les responsables des conformités à
      renouveler et renvoie le digest (``services.relancer_conformites``).
    """
    queryset = ConformiteEnvironnementale.objects.select_related(
        'responsable').all()
    serializer_class = ConformiteEnvironnementaleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['intitule', 'autorite', 'reference_dossier']
    ordering_fields = [
        'id', 'date_expiration', 'date_obtention', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        type_conformite = self.request.query_params.get('type_conformite')
        if type_conformite not in (None, ''):
            qs = qs.filter(type_conformite=type_conformite)
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    @action(detail=False, methods=['get'], url_path='a-relancer')
    def a_relancer(self, request):
        """Conformités environnementales à renouveler ou expirées (QHSE38)."""
        confs = conformites_a_relancer(request.user.company)
        page = self.paginate_queryset(confs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(confs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def relancer(self, request):
        """Relance les conformités à renouveler : notifie + digest (QHSE38)."""
        digest = relancer_conformites(request.user.company)
        return Response(digest)


class BilanCarboneViewSet(_QhseBaseViewSet):
    """Bilans carbone internes (scopes 1/2/3 — QHSE39).

    CRUD scopé société. ``company`` posée côté serveur. Les totaux par scope et
    le total global sont dérivés des lignes (lecture seule). Filtres optionnels :
    ``?annee=`` / ``?statut=``. Recherche par libellé/périmètre.
    """
    queryset = BilanCarbone.objects.all()
    serializer_class = BilanCarboneSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'perimetre']
    ordering_fields = ['id', 'annee', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        annee = self.request.query_params.get('annee')
        if annee not in (None, ''):
            qs = qs.filter(annee=annee)
        statut = self.request.query_params.get('statut')
        if statut not in (None, ''):
            qs = qs.filter(statut=statut)
        return qs

    @action(detail=True, methods=['post'], url_path='generer-lignes-bilan')
    def generer_lignes_bilan_action(self, request, pk=None):
        """XQHS21 — pré-remplit les lignes du bilan depuis les relevés QHSE +
        le carburant flotte de l'année du bilan (idempotent, éditable)."""
        bilan = self.get_object()
        lignes = generer_lignes_bilan(bilan, bilan.annee)
        return Response(LigneBilanCarboneSerializer(lignes, many=True).data)


class LigneBilanCarboneViewSet(_QhseBaseViewSet):
    """Lignes d'émission d'un bilan carbone (QHSE39).

    CRUD scopé société. ``company`` posée côté serveur ; le FK ``bilan`` est
    validé même-société. ``tco2e`` (quantité × facteur) est dérivé (lecture
    seule). Filtres optionnels : ``?bilan=`` / ``?scope=``.
    """
    queryset = LigneBilanCarbone.objects.select_related('bilan').all()
    serializer_class = LigneBilanCarboneSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'categorie']
    ordering_fields = ['id', 'scope', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        bilan = self.request.query_params.get('bilan')
        if bilan not in (None, ''):
            qs = qs.filter(bilan_id=bilan)
        scope = self.request.query_params.get('scope')
        if scope not in (None, ''):
            qs = qs.filter(scope=scope)
        return qs


class IndicateurESGViewSet(_QhseBaseViewSet):
    """Indicateurs ESG + export reporting (QHSE40).

    CRUD scopé société. ``company`` posée côté serveur. Le FK ``bilan_carbone``
    (QHSE39) est validé même-société. ``atteinte_cible`` est dérivé (lecture
    seule). Filtres optionnels : ``?pilier=`` / ``?annee=``. Recherche par
    code/libellé.

    Action ``GET …/export/`` — export reporting groupé par pilier ESG
    (``?annee=`` optionnel), via ``selectors.export_esg``, scopé société.
    """
    queryset = IndicateurESG.objects.select_related('bilan_carbone').all()
    serializer_class = IndicateurESGSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle']
    ordering_fields = ['id', 'pilier', 'annee', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        pilier = self.request.query_params.get('pilier')
        if pilier not in (None, ''):
            qs = qs.filter(pilier=pilier)
        annee = self.request.query_params.get('annee')
        if annee not in (None, ''):
            qs = qs.filter(annee=annee)
        return qs

    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export reporting ESG groupé par pilier (QHSE40).

        ``?annee=N`` borne la période. Agrège les indicateurs ESG de la société
        en un export plat + par pilier (nb / cibles atteintes / lignes).
        """
        annee = request.query_params.get('annee') or None
        return Response(export_esg(request.user.company, annee=annee))


# ── XQHS3 — Contrôle qualité à la réception fournisseur ─────────────────────

class PlanControleReceptionViewSet(_QhseBaseViewSet):
    """Plans de contrôle qualité à la réception fournisseur (XQHS3).

    CRUD scopé société. ``company`` posée côté serveur. Filtres optionnels
    ``?produit=`` / ``?categorie=`` / ``?actif=``.
    """
    queryset = PlanControleReception.objects.select_related(
        'produit', 'categorie').prefetch_related('points').all()
    serializer_class = PlanControleReceptionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['id', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        produit = self.request.query_params.get('produit')
        if produit not in (None, ''):
            qs = qs.filter(produit_id=produit)
        categorie = self.request.query_params.get('categorie')
        if categorie not in (None, ''):
            qs = qs.filter(categorie_id=categorie)
        actif = self.request.query_params.get('actif')
        if actif not in (None, ''):
            qs = qs.filter(actif=actif.lower() in ('1', 'true'))
        return qs


class PointControleReceptionViewSet(_QhseBaseViewSet):
    """Points de contrôle d'un plan de contrôle réception (XQHS3)."""
    queryset = PointControleReception.objects.select_related('plan').all()
    serializer_class = PointControleReceptionSerializer
    ordering_fields = ['id', 'ordre', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        if plan not in (None, ''):
            qs = qs.filter(plan_id=plan)
        return qs


class ControleReceptionViewSet(_QhseBaseViewSet):
    """Contrôles qualité exécutés à la réception fournisseur (XQHS3).

    CRUD scopé société (surtout en lecture — l'ouverture passe par
    ``instancier_controles_reception``, déclenchée par l'événement de
    confirmation de réception côté ``stock``). Filtres optionnels
    ``?reception_id=`` / ``?verdict=``.

    Action ``POST …/<id>/statuer/`` — pose le verdict (``accepte`` /
    ``refuse`` / ``quarantaine``). Un verdict ``refuse`` lève automatiquement
    une NCR pré-remplie (pont XQHS3→XQHS2).
    """
    queryset = ControleReception.objects.select_related(
        'plan', 'controleur', 'non_conformite').all()
    serializer_class = ControleReceptionSerializer
    ordering_fields = ['id', 'date_controle', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        reception_id = self.request.query_params.get('reception_id')
        if reception_id not in (None, ''):
            qs = qs.filter(reception_id=reception_id)
        verdict = self.request.query_params.get('verdict')
        if verdict not in (None, ''):
            qs = qs.filter(verdict=verdict)
        return qs

    @action(detail=True, methods=['post'])
    def statuer(self, request, pk=None):
        """Pose le verdict d'un contrôle réception (XQHS3).

        Corps : ``verdict`` (requis), ``notes`` optionnelles. ``controleur``
        posé côté serveur (jamais lu du corps).
        """
        controle = self.get_object()
        verdict = request.data.get('verdict')
        if not verdict:
            return Response(
                {'detail': 'verdict est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            statuer_controle_reception(
                controle, verdict, controleur=request.user,
                notes=request.data.get('notes', ''))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(controle).data)


# ── XQHS4 — Catalogue de codes de défauts + Pareto qualité ──────────────────

class CodeDefautViewSet(_QhseBaseViewSet):
    """Référentiel des codes de défaut (XQHS4). CRUD scopé société.

    Filtres optionnels ``?famille=`` / ``?actif=``.
    """
    queryset = CodeDefaut.objects.all()
    serializer_class = CodeDefautSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle']
    ordering_fields = ['id', 'famille', 'code']

    def get_queryset(self):
        qs = super().get_queryset()
        famille = self.request.query_params.get('famille')
        if famille not in (None, ''):
            qs = qs.filter(famille=famille)
        actif = self.request.query_params.get('actif')
        if actif not in (None, ''):
            qs = qs.filter(actif=actif.lower() in ('1', 'true'))
        return qs


class ParetoDefautsViewSet(viewsets.ViewSet):
    """Pareto qualité en lecture seule (XQHS4).

    ``GET …/pareto-defauts/?periode=YYYY-MM&chantier=<id>&famille=<f>``
    agrège les codes de défaut posés sur NCR / relevés en échec / incidents en
    un Pareto (comptes + % cumulé) et expose le taux de conformité
    premier-passage des relevés (mêmes filtres période/chantier). Agrégation
    PURE — aucune mutation. Scopé société. Palier Responsable/Admin.
    """
    permission_classes = [HasPermissionOrLegacy('qhse_voir')]

    def list(self, request):
        periode = request.query_params.get('periode') or None
        chantier = request.query_params.get('chantier') or None
        famille = request.query_params.get('famille') or None
        return Response({
            'pareto': pareto_defauts(
                request.user.company, periode=periode,
                chantier_id=chantier, famille=famille),
            'premier_passage': taux_conformite_premier_passage(
                request.user.company, chantier_id=chantier),
        })


# ── XQHS16 — Signalement QR public sans compte (danger/incident chantier) ──

class LienSignalementPublicViewSet(_QhseBaseViewSet):
    """CRUD (Responsable/Admin) des liens publics tokenisés par chantier.

    ``token`` est posé côté serveur (défaut du modèle) — jamais accepté en
    écriture. L'action ``qr`` sert le PNG du QR à imprimer.
    """
    queryset = LienSignalementPublic.objects.all()
    serializer_class = LienSignalementPublicSerializer

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def qr(self, request, pk=None):
        lien = self.get_object()
        base_url = request.build_absolute_uri('/').rstrip('/')
        png = generer_qr_signalement(lien, base_url=base_url)
        if png is None:
            return Response(
                {'detail': 'Génération QR indisponible (dépendance manquante).'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        from django.http import HttpResponse
        resp = HttpResponse(png, content_type='image/png')
        resp['Content-Disposition'] = (
            f'attachment; filename="signalement-qr-{lien.token[:8]}.png"')
        return resp


class SignalementPublicViewSet(viewsets.ReadOnlyModelViewSet):
    """Lecture interne (Responsable/Admin) des signalements reçus (XQHS16).

    Scopé société. La création publique passe EXCLUSIVEMENT par la vue
    tokenisée ``public_signalement`` (jamais par ce viewset authentifié).
    """
    queryset = SignalementPublic.objects.all()
    serializer_class = SignalementPublicSerializer
    permission_classes = [HasPermissionOrLegacy('qhse_voir')]

    def get_queryset(self):
        return super().get_queryset().filter(
            company=self.request.user.company)


class PublicSignalementRateThrottle(SimpleRateThrottle):
    """Limite le débit du signalement public par IP + jeton (cache-based).

    Même motif que ``ventes.public_views.PublicLinkRateThrottle`` / GED20 :
    décourage l'abus/spam sans jamais bloquer un signalement légitime."""
    scope = 'public_qhse_signalement'
    rate = '20/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (getattr(view, 'kwargs', None) or {}).get('token', '')
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicSignalementRateThrottle])
def public_signalement(request, token):
    """XQHS16 — Signalement PUBLIC (sans login) via QR chantier.

    `GET /api/django/qhse/public/signalement/<token>/` : vérifie la validité
    du lien (pour l'UI publique, sans exposer de données internes).
    `POST` avec `{"type_signalement": "danger"|"incident", "description": str,
    "photo_url"?: str, "nom"?: str, "telephone"?: str}` — nom/téléphone
    facultatifs (anonyme si absents).

    Codes : 404 (jeton inconnu ou lien révoqué — indistinct, pas de fuite) ;
    400 (description manquante) ; 200/201 sinon. La société est TOUJOURS
    résolue depuis le jeton, jamais depuis le corps de requête."""
    statut, lien = resolve_lien_signalement_public(token)
    if statut != SIGNALEMENT_OK:
        return Response(
            {'detail': 'Ce lien de signalement est introuvable ou a été révoqué.'},
            status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response({'valide': True, 'libelle': lien.libelle})

    description = (request.data.get('description') or '').strip()
    if not description:
        return Response(
            {'description': 'La description est requise.'},
            status=status.HTTP_400_BAD_REQUEST)
    type_signalement = request.data.get('type_signalement') or \
        SignalementPublic.Type.DANGER
    if type_signalement not in SignalementPublic.Type.values:
        type_signalement = SignalementPublic.Type.DANGER

    signalement = creer_signalement_public(
        lien,
        type_signalement=type_signalement,
        description=description,
        photo_url=(request.data.get('photo_url') or '').strip(),
        nom=request.data.get('nom') or '',
        telephone=request.data.get('telephone') or '',
    )
    return Response(
        {'detail': 'Signalement envoyé avec succès.', 'id': signalement.pk},
        status=status.HTTP_201_CREATED)


# ── XQHS17 — Observations sécurité comportementales (BBS) ──────────────────

class ObservationSecuriteViewSet(_QhseBaseViewSet):
    """CRUD + conversion en un clic (CAPA/NCR) des observations BBS.

    ``company``/``observateur`` posés côté serveur. Filtres optionnels
    ``?type_observation=`` / ``?chantier=``.
    """
    queryset = ObservationSecurite.objects.all()
    serializer_class = ObservationSecuriteSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_observation', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        type_observation = self.request.query_params.get('type_observation')
        if type_observation:
            qs = qs.filter(type_observation=type_observation)
        chantier = self.request.query_params.get('chantier')
        if chantier:
            qs = qs.filter(chantier_id=chantier)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            observateur=self.request.user)

    @action(detail=True, methods=['post'], url_path='convertir-capa')
    def convertir_capa(self, request, pk=None):
        observation = self.get_object()
        try:
            capa, created = convertir_observation_en_capa(
                observation,
                description=request.data.get('description'),
                responsable_id=request.data.get('responsable'),
                echeance=request.data.get('echeance'))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ActionCorrectivePreventiveSerializer(capa).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='convertir-ncr')
    def convertir_ncr(self, request, pk=None):
        observation = self.get_object()
        try:
            ncr, created = convertir_observation_en_ncr(
                observation, gravite=request.data.get('gravite'))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            NonConformiteSerializer(ncr).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def compteurs(self, request):
        chantier = request.query_params.get('chantier') or None
        return Response(compteurs_observations_securite(
            request.user.company, chantier_id=chantier))


# ── XQHS18 — Exercices d'urgence (drills) rattachés aux plans d'urgence ────

class ExerciceUrgenceViewSet(_QhseBaseViewSet):
    """CRUD des exercices d'urgence + actions ``realiser``/``creer-capa``.

    ``company`` posée côté serveur. ``GET …/dus/`` liste les plans en retard
    de leur prochain exercice (pattern relance QHSE38/QHSE12).
    """
    queryset = ExerciceUrgence.objects.all()
    serializer_class = ExerciceUrgenceSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_prevue', 'date_realisee']

    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        if plan:
            qs = qs.filter(plan_id=plan)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def realiser(self, request, pk=None):
        exercice = self.get_object()
        exercice = realiser_exercice_urgence(
            exercice,
            date_realisee=request.data.get('date_realisee'),
            duree_evacuation_secondes=request.data.get(
                'duree_evacuation_secondes'),
            nb_participants=request.data.get('nb_participants'),
            participants_libre=request.data.get('participants_libre', ''),
            observations=request.data.get('observations', ''))
        return Response(ExerciceUrgenceSerializer(exercice).data)

    @action(detail=True, methods=['post'], url_path='creer-capa')
    def creer_capa(self, request, pk=None):
        exercice = self.get_object()
        try:
            capa, created = creer_capa_depuis_ecart_exercice(
                exercice, description=request.data.get('description'))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ActionCorrectivePreventiveSerializer(capa).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def dus(self, request):
        plans = plans_exercices_dus(request.user.company)
        return Response(PlanUrgenceSerializer(plans, many=True).data)

    @action(detail=False, methods=['post'])
    def relancer(self, request):
        plans = relancer_exercices_urgence(request.user.company)
        return Response({'relances': len(plans)})


# ── XQHS20 — Registre des aspects & impacts environnementaux (ISO 14001) ──

class AspectEnvironnementalViewSet(_QhseBaseViewSet):
    """CRUD du registre des aspects environnementaux. ``company`` posée côté
    serveur. ``GET …/a-revoir/`` liste les aspects en retard de revue."""
    queryset = AspectEnvironnemental.objects.all()
    serializer_class = AspectEnvironnementalSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['activite', 'aspect', 'impact']
    ordering_fields = ['id', 'date_revue', 'date_creation']

    def get_queryset(self):
        from django.db.models import F

        qs = super().get_queryset().annotate(
            _criticite=F('frequence') * F('gravite'))
        significatif = self.request.query_params.get('significatif')
        if significatif in ('1', 'true', 'True'):
            qs = qs.filter(_criticite__gte=F('seuil_significativite'))
        elif significatif in ('0', 'false', 'False'):
            qs = qs.filter(_criticite__lt=F('seuil_significativite'))
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'], url_path='a-revoir')
    def a_revoir(self, request):
        aspects = aspects_environnementaux_a_revoir(request.user.company)
        return Response(AspectEnvironnementalSerializer(aspects, many=True).data)


# ── XQHS21 — Relevés de consommation par site (élec/eau/carburant) ────────

class ReleveConsommationViewSet(_QhseBaseViewSet):
    """CRUD des relevés mensuels de consommation par site. ``company`` posée
    côté serveur. Filtres optionnels ``?type_energie=`` / ``?annee=``."""
    queryset = ReleveConsommation.objects.all()
    serializer_class = ReleveConsommationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['site_libelle']
    ordering_fields = ['id', 'periode']

    def get_queryset(self):
        qs = super().get_queryset()
        type_energie = self.request.query_params.get('type_energie')
        if type_energie:
            qs = qs.filter(type_energie=type_energie)
        annee = self.request.query_params.get('annee')
        if annee:
            qs = qs.filter(periode__year=annee)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


# ── XQHS22 — Coût de la non-qualité (CoQ) — interne uniquement ────────────

class CoutNonQualiteViewSet(viewsets.ViewSet):
    """Rollup du coût de la non-qualité en lecture seule (XQHS22).

    ``GET …/cout-non-qualite/?annee=YYYY``. Palier Responsable/Admin ; les
    MONTANTS sont en plus gardés par la permission ``cout_non_qualite_voir``
    (même palier que ``marge_voir``/``prix_achat_voir``) — sans la
    permission, les montants reviennent ``None`` (structure identique,
    jamais d'erreur, jamais de fuite dans un rendu client)."""
    permission_classes = [HasPermissionOrLegacy('qhse_voir')]

    def list(self, request):
        annee = request.query_params.get('annee')
        try:
            annee = int(annee) if annee else timezone.now().year
        except (TypeError, ValueError):
            annee = timezone.now().year

        rollup = dict(cout_non_qualite(request.user.company, annee))
        if not getattr(request.user, 'can_view_cout_non_qualite', True):
            rollup['interne'] = None
            rollup['externe'] = None
            rollup['total'] = None
            rollup['par_mois'] = [
                {'mois': m['mois'], 'interne': None, 'externe': None}
                for m in rollup['par_mois']
            ]
        else:
            rollup['interne'] = str(rollup['interne'])
            rollup['externe'] = str(rollup['externe'])
            rollup['total'] = str(rollup['total'])
            rollup['par_mois'] = [
                {'mois': m['mois'], 'interne': str(m['interne']),
                 'externe': str(m['externe'])}
                for m in rollup['par_mois']
            ]
        return Response(rollup)


# ── XQHS24 — Gestion du changement (MOC léger) ─────────────────────────────

class DemandeChangementViewSet(_QhseBaseViewSet):
    """CRUD des demandes de changement (MOC). ``company`` posée côté serveur.
    Le cycle de vie avance via ``transitionner`` (jamais un PATCH direct du
    ``statut``) pour garder le gate d'approbation-avant-déploiement
    centralisé côté serveur."""
    queryset = DemandeChangement.objects.all()
    serializer_class = DemandeChangementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'justification']
    ordering_fields = ['id', 'date_creation', 'date_expiration']

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def transitionner(self, request, pk=None):
        demande = self.get_object()
        nouveau_statut = request.data.get('statut')
        if not nouveau_statut:
            return Response(
                {'detail': 'statut est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            demande = transitionner_demande_changement(
                demande, nouveau_statut, approbateur=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=['post'], url_path='creer-capa')
    def creer_capa(self, request, pk=None):
        demande = self.get_object()
        description = request.data.get('description')
        if not description:
            return Response(
                {'detail': 'description est requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        capa = creer_capa_mise_en_oeuvre_moc(
            demande, description=description,
            responsable_id=request.data.get('responsable'),
            echeance=request.data.get('echeance'))
        return Response(
            ActionCorrectivePreventiveSerializer(capa).data,
            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='a-reverser')
    def a_reverser(self, request):
        demandes = demandes_changement_a_reverser(request.user.company)
        return Response(self.get_serializer(demandes, many=True).data)

    @action(detail=False, methods=['post'])
    def relancer(self, request):
        demandes = relancer_demandes_changement(request.user.company)
        return Response({'relances': len(demandes)})


# ── XQHS26 — Veille réglementaire QHSE Maroc (revue périodique assistée) ───

class VeilleReglementaireViewSet(_QhseBaseViewSet):
    """Textes réglementaires suivis + cadence de revue (XQHS26). ``company``
    posée côté serveur. La cadence par défaut est trimestrielle
    (``cadence_jours=90``) ; ``date_prochaine_revue`` est initialisée à la
    création si absente et n'avance ensuite QUE via une revue conclue
    (jamais un PATCH direct)."""
    queryset = VeilleReglementaire.objects.all()
    serializer_class = VeilleReglementaireSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['texte_suivi', 'source']
    ordering_fields = ['id', 'date_prochaine_revue', 'date_creation']

    def perform_create(self, serializer):
        veille = serializer.save(company=self.request.user.company)
        initialiser_prochaine_revue(veille)
        return veille

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        veille = self.perform_create(serializer)
        out = self.get_serializer(veille)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='generer-revues-dues')
    def generer_revues_dues(self, request):
        """Génère les tâches de revue DUES pour la société (idempotent —
        n'ouvre jamais deux revues ``a_faire`` pour la même veille)."""
        revues = generer_revues_veille_dues(request.user.company)
        return Response({
            'generees': len(revues),
            'revues': RevueVeilleReglementaireSerializer(
                revues, many=True).data,
        })


class RevueVeilleReglementaireViewSet(_QhseBaseViewSet):
    """Revues (occurrences) des veilles réglementaires (XQHS26). ``company``
    posée côté serveur. Filtre optionnel ``?veille=`` / ``?conclusion=``.

    * ``POST …/<id>/conclure/`` — conclut la revue (``conclusion`` requis :
      ``applicable``/``non_applicable``), avance ``date_prochaine_revue`` du
      parent, et lie/instancie le registre légal (XQHS8) si applicable.
    """
    queryset = RevueVeilleReglementaire.objects.all()
    serializer_class = RevueVeilleReglementaireSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_echeance', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        veille = self.request.query_params.get('veille')
        if veille not in (None, ''):
            qs = qs.filter(veille_id=veille)
        conclusion = self.request.query_params.get('conclusion')
        if conclusion not in (None, ''):
            qs = qs.filter(conclusion=conclusion)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def conclure(self, request, pk=None):
        revue = self.get_object()
        conclusion = request.data.get('conclusion')
        if not conclusion:
            return Response(
                {'detail': 'conclusion est requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            revue = conclure_revue_veille(
                revue, conclusion,
                impact_evalue=request.data.get('impact_evalue', ''),
                resume_ia=request.data.get('resume_ia', ''))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(revue).data)


# ── XQHS25 — Assistance IA QHSE (classification + brouillon d'analyse) ────
# Key-gated (GROQ_API_KEY) : sans clé, 200 + `disponible=false`, jamais
# d'erreur ni de dépendance dure. TOUJOURS une proposition éditable, jamais
# auto-appliquée (pattern propose→confirm du groupe AG). Authentifié
# (Responsable/Admin) — CE N'EST PAS un endpoint public.

@api_view(['POST'])
@permission_classes([HasPermissionOrLegacy('qhse_gerer')])
def ia_suggestion_classification(request):
    """XQHS25 — `POST {"description": str}` → suggestion de classification
    (type/gravité/code défaut) d'un incident ou d'une NCR à partir d'une
    description libre. Aucune donnée d'une autre société n'est envoyée au
    modèle (le prompt ne contient que le texte fourni par CET utilisateur)."""
    description = request.data.get('description') or ''
    return Response(suggerer_classification_incident(description))


@api_view(['POST'])
@permission_classes([HasPermissionOrLegacy('qhse_gerer')])
def ia_suggestion_analyse(request):
    """XQHS25 — `POST {"recit": str}` → brouillon 5-Pourquoi + plan CAPA
    depuis un récit d'investigation libre."""
    recit = request.data.get('recit') or ''
    return Response(suggerer_analyse_capa(recit))


# ── XQHS27 — Documents terrain QHSE imprimables bilingues FR/AR ────────────
# La causerie sécurité vit dans ``rh`` (modèle ``CauserieSecurite``) : lue
# EXCLUSIVEMENT via ``apps.rh.selectors.causerie_securite_for_id`` (jamais un
# import de ``rh.models``/``rh.views``), scopée société côté serveur.

@api_view(['GET'])
def causerie_securite_pdf(request, causerie_id):
    """XQHS27 — PDF INTERNE de la fiche causerie + émargement (FR/AR).

    ``?lang=fr`` (défaut) ou ``?lang=ar`` (gabarit RTL, police arabe
    embarquée). 404 si la causerie n'existe pas / n'appartient pas à la
    société de l'utilisateur. JAMAIS ``/proposal`` — aucun prix."""
    from django.http import HttpResponse

    from apps.rh.selectors import causerie_securite_for_id

    from .pdf_terrain import render_causerie_securite_pdf

    causerie = causerie_securite_for_id(request.user.company, causerie_id)
    if causerie is None:
        return Response(
            {'detail': 'Causerie introuvable.'},
            status=status.HTTP_404_NOT_FOUND)
    lang = request.query_params.get('lang', 'fr')
    pdf_bytes = render_causerie_securite_pdf(causerie, lang=lang)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="causerie-securite-{causerie.pk}-{lang}.pdf"')
    return response


# ── WIR115 — Check-in sécurité (technicien seul sur site à risque) ───────────
class CheckinSecuriteViewSet(_QhseBaseViewSet):
    """Cycle check-in/check-out d'un technicien seul sur site à risque (WIR115).

    Donne enfin un moyen d'insérer / clôturer une ligne (la tâche beat
    ``escalader_checkins_en_retard`` tournait contre une table sans écran).
    CRUD scopé société ; ``company`` posée côté serveur. ``technicien`` par
    défaut = utilisateur courant. Filtres : ``?en_retard=1`` (non checkout et
    délai dépassé), ``?technicien=`` , ``?escalade=1``. Action détail
    ``POST …/<id>/checkout/`` pose l'heure de check-out réelle (maintenant).
    """
    queryset = CheckinSecurite.objects.all()
    serializer_class = CheckinSecuriteSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'heure_checkin', 'heure_checkout_prevue',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        technicien = self.request.query_params.get('technicien')
        if technicien not in (None, ''):
            qs = qs.filter(technicien_id=technicien)
        escalade = self.request.query_params.get('escalade')
        if escalade in ('1', 'true'):
            qs = qs.filter(escalade_declenchee=True)
        if self.request.query_params.get('en_retard') in ('1', 'true'):
            ids = [c.id for c in qs if c.en_retard()]
            qs = qs.filter(id__in=ids)
        return qs

    def perform_create(self, serializer):
        # Le technicien par défaut est l'utilisateur courant (jamais un autre
        # posé silencieusement) ; l'heure de check-in par défaut = maintenant.
        data = {'company': self.request.user.company}
        if not serializer.validated_data.get('technicien'):
            data['technicien'] = self.request.user
        if not serializer.validated_data.get('heure_checkin'):
            data['heure_checkin'] = timezone.now()
        return serializer.save(**data)

    @action(detail=True, methods=['post'])
    def checkout(self, request, pk=None):
        """Enregistre le check-out réel (maintenant) — clôt le cycle."""
        checkin = self.get_object()
        checkin.heure_checkout_reelle = timezone.now()
        checkin.save(update_fields=['heure_checkout_reelle'])
        return Response(self.get_serializer(checkin).data)


# ── WIR115 — SCAR : demande d'action corrective fournisseur ──────────────────
class DemandeActionFournisseurViewSet(_QhseBaseViewSet):
    """SCAR — demande d'action corrective adressée à un fournisseur (WIR115).

    CRUD scopé société ; ``company`` posée côté serveur. Le ``statut`` est en
    lecture seule au CRUD ; deux actions détail pilotent le cycle de vie :

    * ``POST …/<id>/repondre/`` — ``emise`` → ``repondue`` (enregistre cause
      racine / action fournisseur + ``date_reponse``) ;
    * ``POST …/<id>/verifier/`` — ``repondue`` → ``verifiee``/``close`` selon
      ``efficace`` (booléen requis) ; ``verifiee_par`` = utilisateur courant.

    Filtres : ``?statut=`` , ``?fournisseur=`` , ``?ncr_source=``.
    """
    queryset = DemandeActionFournisseur.objects.all()
    serializer_class = DemandeActionFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'echeance_reponse', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        for champ in ('statut', 'fournisseur', 'ncr_source'):
            val = self.request.query_params.get(champ)
            if val not in (None, ''):
                key = {'fournisseur': 'fournisseur_id',
                       'ncr_source': 'ncr_source_id'}.get(champ, champ)
                qs = qs.filter(**{key: val})
        return qs

    @action(detail=True, methods=['post'])
    def repondre(self, request, pk=None):
        """Enregistre la réponse fournisseur (``emise`` → ``repondue``)."""
        scar = self.get_object()
        if scar.statut != DemandeActionFournisseur.Statut.EMISE:
            return Response(
                {'detail': 'Seule une SCAR émise peut recevoir une réponse.'},
                status=status.HTTP_400_BAD_REQUEST)
        scar.cause_racine_fournisseur = request.data.get(
            'cause_racine_fournisseur', scar.cause_racine_fournisseur)
        scar.action_fournisseur = request.data.get(
            'action_fournisseur', scar.action_fournisseur)
        scar.statut = DemandeActionFournisseur.Statut.REPONDUE
        scar.date_reponse = timezone.now()
        scar.save(update_fields=[
            'cause_racine_fournisseur', 'action_fournisseur', 'statut',
            'date_reponse'])
        return Response(self.get_serializer(scar).data)

    @action(detail=True, methods=['post'])
    def verifier(self, request, pk=None):
        """Vérifie l'efficacité (``repondue`` → ``verifiee``/``close``).

        ``efficace`` (booléen) requis : True → ``close``, False → ``verifiee``
        (l'action reste ouverte). ``verifiee_par`` = utilisateur courant.
        """
        scar = self.get_object()
        if scar.statut not in (
                DemandeActionFournisseur.Statut.REPONDUE,
                DemandeActionFournisseur.Statut.VERIFIEE):
            return Response(
                {'detail': 'Seule une SCAR répondue peut être vérifiée.'},
                status=status.HTTP_400_BAD_REQUEST)
        efficace = request.data.get('efficace')
        if efficace is None:
            return Response(
                {'efficace': 'Champ requis (booléen).'},
                status=status.HTTP_400_BAD_REQUEST)
        efficace = str(efficace).lower() in ('1', 'true', 'yes', 'oui')
        scar.efficace = efficace
        scar.verifiee_par = request.user
        scar.date_verification = timezone.now()
        scar.statut = (DemandeActionFournisseur.Statut.CLOSE if efficace
                       else DemandeActionFournisseur.Statut.VERIFIEE)
        scar.save(update_fields=[
            'efficace', 'verifiee_par', 'date_verification', 'statut'])
        return Response(self.get_serializer(scar).data)


# ── WIR115 — SCAFFOLDING DIFFÉRÉ (note explicite) ────────────────────────────
# Les modèles QHSE ci-dessous (services testés, aucune exposition REST) sont
# volontairement laissés SANS API dans ce lot : la priorité WIR115 était
# CheckinSecurite (une tâche beat d'escalade tournait contre une table sans
# écran) et DemandeActionFournisseur (SCAR) — tous deux exposés ci-dessus. Les
# suivants restent en scaffolding différé (à exposer par un lot ultérieur, un
# viewset ``_QhseBaseViewSet`` par modèle sur le même patron) et NE doivent
# jamais être re-listés comme « backend sombre non traité » :
#   CampagneRappel, AnalyseNcr, Certification, AuditCertification,
#   ProgrammeAudit, ClauseNorme, ReunionQhse, ObjectifQhse, RisqueOpportunite,
#   RisqueOpportuniteCapa, PartieInteressee, ContexteOrganisation,
#   DiffusionProcedure.
