"""Vues des Ressources humaines (toutes scopées société, admin-gated).

Le module RH est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``). Les
viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la société
côté serveur ; le ``cout_horaire`` (paie/marge) ne quitte jamais cette API.
"""
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.records.models import Attachment
from apps.records.storage import delete_attachment, store_attachment
from authentication.mixins import TenantMixin
from authentication.permissions import (
    HasPermission,
    IsAnyRole,
    IsResponsableOrAdmin,
)

from . import activity, selectors, services
from .models import (
    AccidentTravail,
    AffectationRoster,
    AffectationVehicule,
    AnalyseRisquesChantier,
    AttributionBadge,
    AvanceSalaire,
    AvantageSocial,
    AyantDroit,
    BadgeReconnaissance,
    BesoinFormation,
    BulletinPaie,
    CampagneEvaluation,
    CampagnePulse,
    Candidature,
    CandidatureActivity,
    CauserieParticipant,
    CauserieSecurite,
    Certification,
    Competence,
    CompetenceEmploye,
    CompetenceRequise,
    CorrectionPointage,
    DemandeAllocation,
    DemandeConge,
    DemandeRH,
    Departement,
    DeviceKiosque,
    EmployeDeviceMap,
    EntretienRecrutement,
    EntretienSortie,
    GabaritEmailRecrutement,
    GrilleSalariale,
    HistoriqueCompetence,
    LigneParcours,
    NoteEntretien,
    PeriodeFermeture,
    PromesseEmbauche,
    ReglageRH,
    DocumentEmploye,
    DossierEmploye,
    DotationEpi,
    ElementIntegration,
    ElementIntegrationEmploye,
    ElementSortie,
    ElementsVariablesPaie,
    EpiCatalogue,
    EvaluationEmploye,
    FeuilleTemps,
    Habilitation,
    HeuresSupp,
    HoraireTravail,
    IncidentPresence,
    JourBloqueConge,
    ModeleEvaluation,
    ModeleIntegration,
    NoteDeFrais,
    OrdreMission,
    OuverturePoste,
    PermisConduire,
    Pointage,
    Poste,
    PresenceChantier,
    PresquAccident,
    PrimeAttribuee,
    QuizFormation,
    Remuneration,
    RetourFeedback360,
    Sanction,
    SessionFormation,
    SoldeConge,
    TentativeQuiz,
    TypeAbsence,
    TypeLigneParcours,
    TypePrime,
    VisiteMedicale,
)
from .serializers import (
    AccidentTravailSerializer,
    AffectationRosterSerializer,
    AffectationVehiculeSerializer,
    AnalyseRisquesChantierSerializer,
    AnnuaireEmployeSerializer,
    AttributionBadgeSerializer,
    AutoEvaluationSerializer,
    AvantageSocialSerializer,
    AyantDroitSerializer,
    AvanceSalaireSerializer,
    BadgeReconnaissanceSerializer,
    BesoinFormationSerializer,
    BulletinPaieSerializer,
    CampagneEvaluationSerializer,
    CampagnePulseSerializer,
    CandidatureActivitySerializer,
    CandidatureSerializer,
    CauserieParticipantSerializer,
    CauserieSecuriteSerializer,
    CertificationSerializer,
    EmbaucherSerializer,
    CompetenceEmployeSerializer,
    CompetenceRequiseSerializer,
    CompetenceSerializer,
    CorrectionPointageSerializer,
    DemandeAllocationSerializer,
    DemandeCongeSerializer,
    DemandeRHSerializer,
    DepartementSerializer,
    DeviceKiosqueSerializer,
    EmployeDeviceMapSerializer,
    EntretienRecrutementSerializer,
    EntretienSortieSerializer,
    GabaritEmailRecrutementSerializer,
    GrilleSalarialeSerializer,
    LigneParcoursSerializer,
    NoteEntretienSerializer,
    PeriodeFermetureSerializer,
    PromesseEmbaucheSerializer,
    ReglageRHSerializer,
    DocumentEmployeSerializer,
    DossierActivitySerializer,
    DossierEmployeSerializer,
    DotationEpiSerializer,
    ElementIntegrationEmployeSerializer,
    ElementIntegrationSerializer,
    ElementSortieSerializer,
    ElementsVariablesPaieSerializer,
    EmargementEpiSerializer,
    EmargerEpiSerializer,
    EvaluationEmployeSerializer,
    EpiCatalogueSerializer,
    FeuilleTempsSerializer,
    HabilitationSerializer,
    HeuresSuppSerializer,
    HoraireTravailSerializer,
    IncidentPresenceSerializer,
    JourBloqueCongeSerializer,
    MesInfosSerializer,
    ModeleEvaluationSerializer,
    ModeleIntegrationSerializer,
    NoteDeFraisSerializer,
    OrdreMissionSerializer,
    OuverturePosteSerializer,
    PermisConduireSerializer,
    PointageSerializer,
    PosteSerializer,
    PresenceChantierSerializer,
    PresquAccidentSerializer,
    PrimeAttribueeSerializer,
    QuizFormationPortailSerializer,
    QuizFormationSerializer,
    MonFeedback360Serializer,
    RemunerationSerializer,
    RetourFeedback360Serializer,
    SanctionSerializer,
    SessionFormationSerializer,
    SoldeCongeSerializer,
    TentativeQuizSerializer,
    TypeAbsenceSerializer,
    TypeLigneParcoursSerializer,
    TypePrimeSerializer,
    VisiteMedicaleSerializer,
)


def _client_ip(request):
    """Adresse IP du client à partir de la requête (preuve d'émargement).

    Préfère ``X-Forwarded-For`` (première IP de la chaîne) derrière un proxy,
    sinon ``REMOTE_ADDR``. Tronquée à 45 caractères pour tenir dans le champ
    ``ip_adresse`` (IPv6) — runtime-safety (leçon FG136).
    """
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '') or ''
    return ip[:45]


class _RhBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class DepartementViewSet(_RhBaseViewSet):
    """Départements de la société. Recherche par nom/code.

    XRH27 — ``parent`` (FK self) modélise la hiérarchie (cycle rejeté 400).

    Action :
    * ``GET .../arbre/`` — arbre imbriqué avec effectifs par nœud (propre +
      cumulé descendants), via ``selectors.arbre_departements``.
    """
    queryset = Departement.objects.select_related('parent').all()
    serializer_class = DepartementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'code']
    ordering_fields = ['nom']

    @action(detail=False, methods=['get'], url_path='arbre')
    def arbre(self, request):
        return Response(
            selectors.arbre_departements(request.user.company))


class DossierEmployeViewSet(_RhBaseViewSet):
    """Dossiers employés (DC29). Recherche par matricule/nom/prénom."""
    queryset = DossierEmploye.objects.select_related('departement', 'user').all()
    serializer_class = DossierEmployeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['matricule', 'nom', 'prenom', 'cin', 'email']
    ordering_fields = ['nom', 'prenom', 'matricule', 'date_embauche']

    def get_permissions(self):
        # XRH16 — ``compa-ratio`` est une consultation SENSIBLE (paie) gatée
        # EXPLICITEMENT par ``salaires_voir`` : un porteur de cette seule
        # permission (rôle lecture-seule paie, sans droit d'écriture ailleurs)
        # doit pouvoir la consulter même s'il ne satisfait pas
        # ``IsResponsableOrAdmin`` (gate d'écriture de la base RH). On
        # remplace donc entièrement le gate de classe pour cette action, au
        # lieu de l'empiler dessus (sinon un lecteur salaires_voir-only reste
        # bloqué en 403 avant même d'atteindre le corps de l'action).
        if self.action == 'compa_ratio':
            return [HasPermission('salaires_voir')()]
        # XRH28 — l'annuaire est accessible à TOUT employé authentifié de la
        # société (pas seulement Administrateur/Responsable) : le serializer
        # dédié ``AnnuaireEmployeSerializer`` garantit qu'AUCUN champ sensible
        # ne fuit, donc élargir ici l'accès en lecture est sûr.
        if self.action == 'annuaire':
            return [IsAnyRole()]
        # ZRH16 — savoir où l'équipe travaille aujourd'hui sert à tous, pas
        # seulement responsable/admin ; aucun champ sensible n'est exposé
        # (nom, jour, lieu).
        if self.action == 'localisation_du_jour':
            return [IsAnyRole()]
        return super().get_permissions()

    def perform_update(self, serializer):
        # XRH6 — journalise automatiquement les champs suivis (chatter) en
        # comparant l'instance AVANT à celle APRÈS sauvegarde.
        import copy
        old = copy.copy(serializer.instance)
        new_dossier = serializer.save()
        activity.log_changes(old, new_dossier, self.request.user)

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """Timeline chatter du dossier (auto + notes), récent d'abord (XRH6)."""
        employe = self.get_object()
        return Response(
            DossierActivitySerializer(
                employe.activites.all(), many=True).data)

    @action(detail=True, methods=['post'])
    def noter(self, request, pk=None):
        """Note manuelle sur le chatter du dossier — auteur pris de la
        requête (XRH6)."""
        employe = self.get_object()
        message = (request.data.get('message') or '').strip()
        if not message:
            return Response({'message': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = activity.log_note(employe, request.user, message)
        return Response(DossierActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='definir-code-pointage')
    def definir_code_pointage(self, request, pk=None):
        """XRH10 — définit/régénère le PIN du kiosque (jamais exposé en liste).

        Corps : ``code`` (chaîne courte). Unicité par société assurée par la
        contrainte DB (``rh_dossier_code_pointage_uniq``) — un doublon renvoie
        400. Vide = retire le PIN.
        """
        from django.db import IntegrityError

        employe = self.get_object()
        code = (request.data.get('code') or '').strip()[:12]
        employe.code_pointage = code
        try:
            employe.save(update_fields=['code_pointage'])
        except IntegrityError:
            return Response(
                {'code': 'Ce PIN est déjà utilisé par un autre employé.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'detail': 'PIN mis à jour.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='rapport-turnover')
    def rapport_turnover(self, request):
        """ZRH11 — rapport de rétention/turnover ANNUEL détaillé (« Employee
        retention report » Odoo), DISTINCT du turnover 12 mois glissants du
        cockpit RH FG200. ``?annee=`` (défaut année en cours). Gaté
        ``IsResponsableOrAdmin`` (gate de classe par défaut)."""
        annee = int(
            request.query_params.get('annee')
            or timezone.localdate().year)
        return Response(selectors.rapport_turnover(request.user.company, annee))

    @action(detail=True, methods=['get'], url_path='certificat-travail')
    def certificat_travail(self, request, pk=None):
        """ZRH12 — certificat de travail légal (art. 72) — PDF.

        DISTINCT de l'attestation de travail (PAIE34) et du reçu STC
        (XPAI1) — ne les duplique pas. 404 si l'employé n'est pas sorti
        (aucun sens pour un actif). Gaté ``IsResponsableOrAdmin`` (gate de
        classe par défaut)."""
        from django.http import HttpResponse

        from .pdf_sortie import render_certificat_travail_pdf

        employe = self.get_object()
        if employe.statut != DossierEmploye.Statut.SORTI or not employe.date_sortie:
            return Response(
                {'detail': "Certificat de travail indisponible : "
                           "l'employé n'est pas sorti."},
                status=status.HTTP_404_NOT_FOUND)
        try:
            pdf_bytes = render_certificat_travail_pdf(employe)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="certificat-travail-{employe.pk}.pdf"')
        return response

    @action(detail=True, methods=['get'], url_path='compa-ratio')
    def compa_ratio(self, request, pk=None):
        """XRH16 — compa-ratio de l'employé (salaire vs bande de son poste).

        Donnée SENSIBLE (paie) : gatée EXPLICITEMENT ``salaires_voir`` (voir
        ``get_permissions``) — un porteur sans cette permission reçoit 403
        avant même d'atteindre ce corps de méthode.
        """
        employe = self.get_object()
        resultat = selectors.compa_ratio(employe)
        if resultat is None:
            detail = (
                'Compa-ratio indisponible (poste, bande ou '
                'salaire manquant).')
            return Response(
                {'detail': detail}, status=status.HTTP_404_NOT_FOUND)
        return Response(resultat)

    @action(detail=False, methods=['get'], url_path='annuaire')
    def annuaire(self, request):
        """XRH28 — annuaire interne (trombinoscope), TOUT employé de la
        société. ``?q=`` recherche nom/prénom/poste/département ; ``?
        competence=<id>&niveau_min=`` filtre par compétence (matrice FG172).
        Serializer dédié SANS champ sensible (voir
        ``AnnuaireEmployeSerializer``)."""
        from django.db.models import Q

        qs = DossierEmploye.objects.filter(
            company=request.user.company).exclude(
            statut=DossierEmploye.Statut.SORTI).select_related(
            'poste_ref', 'departement', 'user')

        q = request.query_params.get('q')
        if q:
            qs = qs.filter(
                Q(nom__icontains=q) | Q(prenom__icontains=q)
                | Q(poste__icontains=q) | Q(poste_ref__intitule__icontains=q)
                | Q(departement__nom__icontains=q))

        competence_id = request.query_params.get('competence')
        if competence_id:
            niveau_min = request.query_params.get('niveau_min', 0)
            qs = qs.filter(
                competences__company=request.user.company,
                competences__competence_id=competence_id,
                competences__niveau__gte=niveau_min)

        return Response(
            AnnuaireEmployeSerializer(qs.distinct(), many=True).data)

    @action(
        detail=False, methods=['get'], url_path='localisation-du-jour')
    def localisation_du_jour(self, request):
        """ZRH16 — localisation de travail attendue de chaque employé actif
        ce jour (« Remote Work » Odoo). ``?jour=YYYY-MM-DD`` (défaut
        aujourd'hui)."""
        from datetime import datetime
        jour_str = request.query_params.get('jour')
        if jour_str:
            try:
                jour = datetime.strptime(jour_str, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                jour = timezone.localdate()
        else:
            jour = timezone.localdate()
        return Response(
            selectors.localisation_du_jour(request.user.company, jour))

    @action(detail=True, methods=['get'], url_path='ecart-competences')
    def ecart_competences(self, request, pk=None):
        """XRH15 — écart requis-vs-actuel de l'employé, au poste de référence."""
        employe = self.get_object()
        return Response(selectors.ecarts_competences(employe))

    @action(detail=True, methods=['get'], url_path='risque-attrition')
    def risque_attrition(self, request, pk=None):
        """XRH31 — score de risque d'attrition de l'employé (scorer pur
        ``core.attrition_risk``, features assemblées via
        ``selectors.features_risque_attrition``). Gaté
        ``IsResponsableOrAdmin`` (gate de classe par défaut)."""
        employe = self.get_object()
        return Response(selectors.risque_attrition_employe(employe))

    @action(detail=True, methods=['post'],
            url_path='ecart-competences-creer-besoin-formation')
    def creer_besoin_formation_depuis_ecart(self, request, pk=None):
        """XRH15 — crée un ``BesoinFormation`` (FG188) en un clic depuis un
        écart de compétence détecté (``theme`` = libellé de la compétence).
        Corps : ``competence`` (id)."""
        employe = self.get_object()
        competence = Competence.objects.filter(
            company=request.user.company,
            pk=request.data.get('competence')).first()
        if competence is None:
            return Response(
                {'detail': 'Compétence introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        besoin = BesoinFormation.objects.create(
            company=request.user.company,
            employe=employe,
            theme=competence.libelle,
            priorite=BesoinFormation.Priorite.MOYENNE,
        )
        return Response(
            {'id': besoin.id, 'theme': besoin.theme},
            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='cdd-a-echeance')
    def cdd_a_echeance(self, request):
        """Alerte fin de CDD : dossiers en CDD dont la fin de contrat tombe
        dans les ``?within=`` prochains jours (défaut 30), scopés société.

        Exclut les CDI (et tout autre type), les CDD sans date de fin, ceux
        déjà expirés et ceux dont la fin dépasse la fenêtre. La société est
        garantie par ``get_queryset`` (TenantMixin) — jamais lue du corps.
        """
        try:
            within = int(request.query_params.get('within', 30))
        except (TypeError, ValueError):
            within = 30
        if within < 0:
            within = 0
        today = timezone.localdate()
        limite = today + timedelta(days=within)
        qs = self.get_queryset().filter(
            type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin__isnull=False,
            contrat_date_fin__gte=today,
            contrat_date_fin__lte=limite,
        ).order_by('contrat_date_fin')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='sortir')
    def sortir(self, request, pk=None):
        """YHIRE2 — orchestre la sortie de l'employé (``services.sortir_employe``) :
        checklist ``ElementSortie`` générée depuis les dotations/affectations
        réelles, compte utilisateur désactivé, ``ProfilPaie`` coupé (via le
        bus d'événements, sans import croisé).

        Corps : ``date_sortie`` (ISO, obligatoire), ``motif``
        (``DossierEmploye.MotifSortie``, obligatoire), ``notes_avances``
        (optionnel). Refuse (400) un dossier déjà SORTI (idempotence :
        rejouer l'action ne re-génère pas la checklist).
        """
        employe = self.get_object()
        date_sortie_raw = request.data.get('date_sortie')
        motif = (request.data.get('motif') or '').strip()
        try:
            from datetime import date as _date
            date_sortie = _date.fromisoformat(str(date_sortie_raw))
        except (TypeError, ValueError):
            date_sortie = None
        if date_sortie is None:
            return Response(
                {'date_sortie': 'Date de sortie invalide ou manquante.'},
                status=status.HTTP_400_BAD_REQUEST)
        if motif not in DossierEmploye.MotifSortie.values:
            return Response(
                {'motif': 'Motif de sortie invalide ou manquant.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            services.sortir_employe(
                employe, date_sortie=date_sortie, motif=motif,
                notes_avances=(request.data.get('notes_avances') or ''))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DossierEmployeSerializer(employe).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='comptes-actifs-sortis')
    def comptes_actifs_sortis(self, request):
        """YHIRE2 — rapport de sécurité PERMANENT : comptes utilisateur restés
        ACTIFS alors que leur dossier est SORTI (doit rester vide en
        fonctionnement normal ; utile pour détecter des sorties faites hors
        de ce chemin, p. ex. données historiques)."""
        rows = services.comptes_actifs_employes_sortis(request.user.company)
        return Response(rows)

    @action(detail=False, methods=['get'], url_path='a-declarer')
    def a_declarer(self, request):
        """Embauchés sans déclaration d'entrée CNSS/AMO (XRH5), scopés société.

        Filtre sur ``declaration_entree_statut = a_faire``. Marquer déclaré
        (``employes/{id}/marquer-declare``) retire l'employé de cette liste.
        """
        qs = self.get_queryset().filter(
            declaration_entree_statut=(
                DossierEmploye.DeclarationEntreeStatut.A_FAIRE)
        ).order_by('date_embauche')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='marquer-declare')
    def marquer_declare(self, request, pk=None):
        """Marque la déclaration d'entrée CNSS/AMO comme faite (XRH5).

        ``declaration_entree_date`` est posée CÔTÉ SERVEUR (aujourd'hui) —
        jamais lue du corps. On ne transmet RIEN à Damancom ici : action
        manuelle du fondateur, ceci ne fait que TRACER la conformité.
        """
        employe = self.get_object()
        employe.declaration_entree_statut = (
            DossierEmploye.DeclarationEntreeStatut.DECLAREE)
        employe.declaration_entree_date = timezone.localdate()
        employe.save(update_fields=[
            'declaration_entree_statut', 'declaration_entree_date'])
        return Response(self.get_serializer(employe).data)

    @action(detail=True, methods=['get'], url_path='verifier-habilitation')
    def verifier_habilitation(self, request, pk=None):
        """Garde d'affectation par habilitation (FG176) — BLOCAGE DOUX.

        Indique si cet employé est AUTORISÉ pour une affectation exigeant
        certain(s) titre(s) d'habilitation. La garde se contente de RAPPORTER :
        l'appelant (l'affectation côté ``installations``) décide d'alerter ou de
        bloquer ; aucune écriture n'est faite ici.

        Titres requis (au moins l'un des deux) :
        * ``?type=b1v&type=br`` (répété) ou ``?type=b1v,br`` (séparé par des
          virgules) — codes ``Habilitation.TypeHabilitation`` exigés ;
        * ``?intervention=pose_pv_bt`` — type d'intervention traduit côté serveur
          en titres requis via ``INTERVENTION_HABILITATIONS``. Les deux sources
          sont cumulées.

        L'employé est résolu via ``get_object`` (scopé société par TenantMixin) :
        un employé d'une autre société renvoie 404. Réponse :
        ``{employe, autorise, manquantes, expirees, message}``.
        """
        employe = self.get_object()
        types = []
        for valeur in request.query_params.getlist('type'):
            types.extend(t.strip() for t in valeur.split(',') if t.strip())
        intervention = request.query_params.get('intervention')
        if intervention:
            types.extend(
                selectors.habilitations_requises_pour_intervention(
                    intervention))
        rapport = selectors.verifier_habilitation_requise(
            request.user.company, employe, types)
        return Response({'employe': employe.pk, **rapport})

    @action(detail=True, methods=['get'], url_path='registre-formation')
    def registre_formation(self, request, pk=None):
        """Registre de formation de l'employé (FG188) — historique des sessions.

        Agrège l'historique de formation de l'employé : toutes ses inscriptions
        (``InscriptionFormation``) avec le détail de la session (intitulé,
        type, organisme, dates, lieu, statut, compétence visée), présence et
        résultat. L'employé est résolu via ``get_object`` (scopé société par
        TenantMixin) — un employé d'une autre société renvoie 404. Lecture
        seule ; renvoie ``{employe, lignes, total, total_realisees}``.
        """
        employe = self.get_object()
        registre = selectors.registre_formation_employe(
            request.user.company, employe.pk)
        return Response(registre)

    @action(detail=True, methods=['post'], url_path='confirmer-essai')
    def confirmer_essai(self, request, pk=None):
        """Confirme la période d'essai (XRH1) — retire l'alerte d'échéance.

        Efface ``essai_date_fin`` (plus d'échéance à surveiller). L'employé est
        résolu via ``get_object`` (scopé société par TenantMixin) — un employé
        d'une autre société renvoie 404. Journalisée si XRH6 (chatter) est
        disponible, best-effort sinon.
        """
        employe = self.get_object()
        if employe.essai_date_fin is None:
            return Response(
                {'detail': "Aucune période d'essai en cours pour ce dossier."},
                status=status.HTTP_400_BAD_REQUEST)
        employe.essai_date_fin = None
        employe.save(update_fields=['essai_date_fin'])
        return Response(self.get_serializer(employe).data)

    @action(detail=True, methods=['post'], url_path='instancier-integration')
    def instancier_integration(self, request, pk=None):
        """Instancie manuellement la checklist d'intégration (XRH4).

        Corps optionnel : ``modele`` (id) pour forcer un modèle précis (validé
        même société) ; sinon le modèle le plus spécifique au poste/
        département de l'employé est résolu automatiquement. Idempotent : si
        des lignes existent déjà pour l'employé, elles sont renvoyées sans
        duplication.
        """
        employe = self.get_object()
        modele = None
        modele_id = request.data.get('modele')
        if modele_id:
            try:
                modele = ModeleIntegration.objects.get(
                    pk=modele_id, company=request.user.company)
            except (ModeleIntegration.DoesNotExist, ValueError, TypeError):
                return Response(
                    {'modele': "Modèle d'intégration inconnu."},
                    status=status.HTTP_400_BAD_REQUEST)
        lignes = services.instancier_integration(employe, modele=modele)
        return Response(
            ElementIntegrationEmployeSerializer(lignes, many=True).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='integration')
    def integration(self, request, pk=None):
        """Checklist d'intégration de l'employé + progression % (XRH4).

        Lecture seule ; renvoie ``{lignes, total, faits, progression_pct}``.
        """
        employe = self.get_object()
        lignes = list(
            ElementIntegrationEmploye.objects.filter(employe=employe))
        total = len(lignes)
        faits = sum(1 for ligne in lignes if ligne.fait)
        pct = round((faits / total) * 100) if total else 0
        return Response({
            'lignes': ElementIntegrationEmployeSerializer(
                lignes, many=True).data,
            'total': total,
            'faits': faits,
            'progression_pct': pct,
        })


class RemunerationViewSet(TenantMixin, viewsets.ModelViewSet):
    """Rémunération de base des employés (FG157) — paie SENSIBLE.

    Lecture ET écriture réservées aux porteurs de ``salaires_voir`` (palier RH) :
    sans cette permission tout accès est refusé (403). Société scopée
    (TenantMixin) et posée côté serveur. L'historique d'un employé s'obtient via
    ``?employe=<id>`` — les lignes sont triées de la plus récente à la plus
    ancienne (``date_effet`` décroissante), la première étant la rémunération en
    vigueur.
    """
    permission_classes = [HasPermission('salaires_voir')]
    queryset = Remuneration.objects.select_related('employe').all()
    serializer_class = RemunerationSerializer
    filter_backends = [filters.OrderingFilter]
    filterset_fields = ['employe']
    ordering_fields = ['date_effet', 'date_creation', 'montant']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        return qs


class DocumentEmployeViewSet(TenantMixin, viewsets.ModelViewSet):
    """Coffre documents employé (FG159) — pièces administratives d'un dossier.

    Accès calqué sur le dossier : Administrateur/Responsable uniquement
    (``IsResponsableOrAdmin``), société scopée + posée côté serveur (TenantMixin).
    Le fichier RÉUTILISE le stockage objet existant de ``records.Attachment``
    (``store_attachment`` → MinIO) : on ne construit aucun nouveau stockage. La
    création est multipart (``employe`` + ``file`` + ``type_document`` +
    ``date_expiration`` optionnelle) ; la liste d'un employé s'obtient via
    ``?employe=<id>``. La suppression efface la pièce jointe MinIO en cascade.
    """
    permission_classes = [IsResponsableOrAdmin]
    queryset = DocumentEmploye.objects.select_related(
        'employe', 'attachment').all()
    serializer_class = DocumentEmployeSerializer
    parser_classes = [MultiPartParser, JSONParser]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_expiration', 'date_creation', 'type_document']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        type_document = self.request.query_params.get('type_document')
        if type_document:
            qs = qs.filter(type_document=type_document)
        return qs

    def create(self, request, *args, **kwargs):
        """Téléverse un fichier (MinIO via records.storage) puis enregistre le
        document. ``employe`` doit appartenir à la société ; ``company`` et la
        pièce jointe sont posées côté serveur (jamais lues du corps)."""
        company = request.user.company
        employe_id = request.data.get('employe')
        try:
            employe = DossierEmploye.objects.get(
                pk=employe_id, company=company)
        except (DossierEmploye.DoesNotExist, ValueError, TypeError):
            return Response({'employe': 'Employé inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        file = request.FILES.get('file')
        if not file:
            return Response({'file': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Valide les métadonnées (type/expiration) AVANT de toucher le stockage.
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)

        meta, err = store_attachment(file)
        if err:
            return Response({'file': err},
                            status=status.HTTP_400_BAD_REQUEST)
        # La pièce jointe records cible le dossier employé (ContentType) — même
        # modèle de stockage que toute autre pièce jointe, sans nouveau stockage.
        ct = ContentType.objects.get_for_model(DossierEmploye)
        attachment = Attachment.objects.create(
            company=company, content_type=ct, object_id=employe.id,
            uploaded_by=request.user, **meta)
        doc = DocumentEmploye.objects.create(
            company=company, employe=employe, attachment=attachment,
            type_document=ser.validated_data.get(
                'type_document', DocumentEmploye.TypeDocument.AUTRE),
            date_expiration=ser.validated_data.get('date_expiration'),
            note=ser.validated_data.get('note', ''))
        return Response(self.get_serializer(doc).data,
                        status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        # Efface le fichier MinIO puis le document (la pièce jointe part en
        # cascade via le OneToOne, mais on libère explicitement le stockage).
        att = instance.attachment
        instance.delete()
        if att is not None:
            delete_attachment(att.file_key)
            att.delete()

    @action(detail=False, methods=['get'], url_path='expirant-bientot')
    def expirant_bientot(self, request):
        """Documents de la société qui expirent dans les ``?within=`` prochains
        jours (défaut 30). S'appuie sur ``selectors.documents_expirant_bientot``
        — scopé société, exclut les documents sans échéance et déjà expirés."""
        within = request.query_params.get('within', 30)
        qs = selectors.documents_expirant_bientot(
            request.user.company, within_days=within)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class PosteViewSet(_RhBaseViewSet):
    """Référentiel des postes (FG160). Recherche par intitulé/code."""
    queryset = Poste.objects.select_related('departement').all()
    serializer_class = PosteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['intitule', 'code']
    ordering_fields = ['intitule']

    def get_queryset(self):
        qs = super().get_queryset()
        departement = self.request.query_params.get('departement')
        if departement:
            qs = qs.filter(departement_id=departement)
        return qs

    @action(detail=True, methods=['get'], url_path='candidats-internes')
    def candidats_internes(self, request, pk=None):
        """XRH15 — classe les employés par couverture du profil requis de
        ce poste (décroissante)."""
        poste = self.get_object()
        return Response(
            selectors.candidats_internes(request.user.company, poste.id))


class HoraireTravailViewSet(_RhBaseViewSet):
    """Gabarits d'horaire de travail (XRH8) — 44 h standard, Ramadan,
    saisonnier. Recherche par nom ; ``?actif=1`` filtre les actifs."""
    queryset = HoraireTravail.objects.all()
    serializer_class = HoraireTravailSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom', 'date_debut']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        elif actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        return qs


class ElementSortieViewSet(_RhBaseViewSet):
    """Checklist d'offboarding (FG161) — éléments à récupérer au départ.

    Société scopée + Administrateur/Responsable. La liste d'un employé s'obtient
    via ``?employe=<id>``. ``employe`` doit appartenir à la société.
    """
    queryset = ElementSortie.objects.select_related('employe').all()
    serializer_class = ElementSortieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['type_element', 'libelle', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        recupere = self.request.query_params.get('recupere')
        if recupere in ('0', 'false', 'False'):
            qs = qs.filter(recupere=False)
        elif recupere in ('1', 'true', 'True'):
            qs = qs.filter(recupere=True)
        return qs


class EntretienSortieViewSet(_RhBaseViewSet):
    """Entretiens de sortie / exit interview (XRH25).

    Société scopée + Administrateur/Responsable. ``employe`` doit appartenir
    à la société ; un seul entretien par employé (``OneToOne`` — un second
    ``POST`` sur le même employé échoue à la contrainte d'unicité plutôt que
    de dupliquer). Filtre ``?employe=<id>``.
    """
    queryset = EntretienSortie.objects.select_related('employe').all()
    serializer_class = EntretienSortieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        return qs


class AyantDroitViewSet(_RhBaseViewSet):
    """Ayants droit / personnes à charge (XRH29). ``?employe=<id>``."""
    queryset = AyantDroit.objects.select_related('employe').all()
    serializer_class = AyantDroitSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['nom', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        return qs


class AvantageSocialViewSet(_RhBaseViewSet):
    """Avantages sociaux (XRH29 — mutuelle/assurance groupe/CIMR).
    ``?employe=<id>``."""
    queryset = AvantageSocial.objects.select_related('employe').all()
    serializer_class = AvantageSocialSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['type', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        return qs


class CampagnePulseViewSet(_RhBaseViewSet):
    """XRH32 — campagnes de baromètre interne eNPS anonyme (pulse).

    Gestion (création/liste) réservée Administrateur/Responsable
    (``IsResponsableOrAdmin`` — gate de classe par défaut) ; le VOTE lui-même
    est ouvert à tout employé via une action dédiée en accès élargi.

    Actions :
    * ``POST .../{id}/repondre/`` — vote ANONYME (ouvert à tout employé
      authentifié) ; un second vote du même utilisateur est refusé 409.
    * ``GET .../{id}/resultats/`` — score eNPS agrégé (masqué sous 5
      réponses), réservé Administrateur/Responsable.
    """
    queryset = CampagnePulse.objects.all()
    serializer_class = CampagnePulseSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_creation']

    def get_permissions(self):
        # XRH32 — voter est ouvert à TOUT employé authentifié de la société ;
        # gérer les campagnes/consulter les résultats reste
        # Administrateur/Responsable (gate de classe).
        if self.action == 'repondre':
            return [IsAnyRole()]
        return super().get_permissions()

    @action(detail=True, methods=['post'], url_path='repondre')
    def repondre(self, request, pk=None):
        campagne = self.get_object()
        score = request.data.get('score')
        try:
            score = int(score)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Note (0–10) requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        if not 0 <= score <= 10:
            return Response(
                {'detail': 'La note doit être comprise entre 0 et 10.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            services.repondre_pulse(
                campagne, request.user, score=score,
                commentaire=request.data.get('commentaire', ''))
        except services.DejaVoteError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(
            {'detail': 'Réponse enregistrée. Merci !'},
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='resultats')
    def resultats(self, request, pk=None):
        campagne = self.get_object()
        return Response(
            selectors.score_enps_campagne(request.user.company, campagne.id))


class ModeleIntegrationViewSet(_RhBaseViewSet):
    """Gabarits de checklist d'intégration (XRH4). Recherche par nom."""
    queryset = ModeleIntegration.objects.select_related(
        'poste_ref', 'departement').prefetch_related('elements').all()
    serializer_class = ModeleIntegrationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom']


class ElementIntegrationViewSet(_RhBaseViewSet):
    """Lignes gabarit d'un modèle d'intégration (XRH4). ``?modele=<id>``."""
    queryset = ElementIntegration.objects.select_related('modele').all()
    serializer_class = ElementIntegrationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'libelle']

    def get_queryset(self):
        qs = super().get_queryset()
        modele = self.request.query_params.get('modele')
        if modele:
            qs = qs.filter(modele_id=modele)
        return qs


class ElementIntegrationEmployeViewSet(_RhBaseViewSet):
    """Checklist d'intégration d'un employé (XRH4). ``?employe=<id>``.

    Cocher/décocher journalise ``fait_par``/``date`` côté serveur.
    """
    queryset = ElementIntegrationEmploye.objects.select_related(
        'employe', 'fait_par').all()
    serializer_class = ElementIntegrationEmployeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'libelle']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        return qs

    def perform_update(self, serializer):
        # ``fait_par``/``date`` sont posés côté serveur à la coche/décoche —
        # jamais lus du corps (une note manuelle ne peut pas falsifier l'auteur
        # ou la date de réalisation).
        fait = serializer.validated_data.get('fait')
        if fait is True and not serializer.instance.fait:
            serializer.save(fait_par=self.request.user, date=timezone.now())
        elif fait is False:
            serializer.save(fait_par=None, date=None)
        else:
            serializer.save()


class TypeAbsenceViewSet(_RhBaseViewSet):
    """Typologie d'absences (FG164) — référentiel + règle de décompte."""
    queryset = TypeAbsence.objects.all()
    serializer_class = TypeAbsenceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle']
    ordering_fields = ['libelle', 'code']


class SoldeCongeViewSet(_RhBaseViewSet):
    """Soldes de congés annuels (FG162). ``?employe=`` / ``?annee=`` filtrent."""
    queryset = SoldeConge.objects.select_related('employe').all()
    serializer_class = SoldeCongeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['annee', 'employe']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        annee = self.request.query_params.get('annee')
        if annee:
            qs = qs.filter(annee=annee)
        return qs


class DemandeCongeViewSet(_RhBaseViewSet):
    """Demandes & validation de congés (FG163) — workflow employé → superviseur.

    Société scopée + Administrateur/Responsable. À la création, le nombre de
    ``jours`` est calculé côté serveur (jours ouvrés hors fériés/WE si le type le
    requiert — FG5 ``working_days``, sinon jours calendaires). Les actions
    ``valider``/``refuser``/``annuler`` pilotent les transitions et mettent à jour
    le solde via ``services``. Filtres : ``?employe=`` / ``?statut=``.
    """
    queryset = DemandeConge.objects.select_related(
        'employe', 'type_absence', 'decide_par').all()
    serializer_class = DemandeCongeSerializer
    parser_classes = [MultiPartParser, JSONParser]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_fin', 'date_creation', 'statut']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        # ``jours`` calculé côté serveur selon la règle de décompte du type
        # (XRH3 : les drapeaux demi-journée retranchent chacun 0,5 j).
        # ZRH1 — ``extra_holidays`` renseigné (Aïd/Mawlid/1er Moharram/férié
        # société via notifications.Holiday) : sans cela le décompte n'utilise
        # que la table FIXE des 9 fêtes grégoriennes.
        type_absence = serializer.validated_data['type_absence']
        date_debut = serializer.validated_data['date_debut']
        date_fin = serializer.validated_data['date_fin']
        employe = serializer.validated_data['employe']

        # ZRH4 — jour bloqué du département de l'employé : refus 400 sauf
        # forçage explicite RH (``?forcer=1``, journalisé via le motif).
        conflit = services.jour_bloque_conflit(employe, date_debut, date_fin)
        forcer = self.request.query_params.get('forcer') in ('1', 'true', 'True')
        if conflit and not forcer:
            raise serializers.ValidationError(
                {'detail': (
                    f'Congés bloqués du {conflit.date_debut} au '
                    f'{conflit.date_fin} : {conflit.libelle}.')})

        jours = services.calculer_jours_demande(
            type_absence, date_debut, date_fin,
            extra_holidays=services.feries_periode(
                self.request.user.company, date_debut, date_fin),
            demi_journee_debut=serializer.validated_data.get(
                'demi_journee_debut', False),
            demi_journee_fin=serializer.validated_data.get(
                'demi_journee_fin', False))
        serializer.save(company=self.request.user.company, jours=jours)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valide une demande soumise et déduit le solde si le type le requiert.

        XRH3 : refusée (400, message explicite) si le type exige un
        justificatif au-delà de son seuil et qu'aucun n'est joint.
        """
        demande = self.get_object()
        try:
            services.valider_demande(demande, decide_par=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=['post'])
    def refuser(self, request, pk=None):
        """Refuse une demande soumise (aucune déduction de solde)."""
        demande = self.get_object()
        motif = request.data.get('motif_refus', '')
        try:
            services.refuser_demande(
                demande, decide_par=request.user, motif_refus=motif)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """Annule une demande ; recrédite le solde si elle était validée."""
        demande = self.get_object()
        services.annuler_demande(demande)
        return Response(self.get_serializer(demande).data)

    @action(detail=False, methods=['get'], url_path='calendrier-equipe')
    def calendrier_equipe(self, request):
        """Calendrier d'absences d'équipe (FG165) — demandes VALIDÉES chevauchant
        ``?debut=YYYY-MM-DD`` → ``?fin=YYYY-MM-DD`` (défaut : 30 jours à venir).

        Sert d'agenda d'équipe : un technicien listé ici n'est pas assignable au
        dispatch terrain sur la période. Scopé société.
        """
        from datetime import datetime
        today = timezone.localdate()

        def _parse(name, fallback):
            raw = request.query_params.get(name)
            if not raw:
                return fallback
            try:
                return datetime.strptime(raw, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                return fallback

        debut = _parse('debut', today)
        fin = _parse('fin', today + timedelta(days=30))
        qs = selectors.absences_equipe(request.user.company, debut, fin)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='rapport')
    def rapport(self, request):
        """ZRH3 — rapport congés par type et par employé (Odoo « Time Off
        Reporting »). ``?annee=`` (défaut année courante), ``?employe=``,
        ``?departement=`` optionnels. Lecture seule, gaté
        ``IsResponsableOrAdmin`` (déjà la classe de la vue).
        """
        annee = request.query_params.get('annee') or timezone.localdate().year
        try:
            annee = int(annee)
        except (TypeError, ValueError):
            annee = timezone.localdate().year
        employe = request.query_params.get('employe') or None
        departement = request.query_params.get('departement') or None
        data = selectors.rapport_conges(
            request.user.company, annee, employe_id=employe,
            departement_id=departement)
        return Response(data)


class DemandeAllocationViewSet(_RhBaseViewSet):
    """Demandes d'allocation de congés self-service (ZRH13).

    Un employé authentifié peut CRÉER une demande pour LUI-MÊME (via le
    portail, voir ``PortailSelfServiceViewSet.demander_allocation``) ; la
    liste/validation/refus restent réservées ``IsResponsableOrAdmin`` (gate
    de classe par défaut). À la VALIDATION, ``services.valider_allocation``
    crédite ``SoldeConge.acquis`` du nombre de jours — jamais écrit
    directement du corps. Filtres : ``?employe=`` / ``?statut=``.
    """
    queryset = DemandeAllocation.objects.select_related(
        'employe', 'type_absence', 'decide_par').all()
    serializer_class = DemandeAllocationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'statut']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valide une demande soumise et crédite le solde disponible."""
        demande = self.get_object()
        try:
            services.valider_allocation(demande, decide_par=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=['post'])
    def refuser(self, request, pk=None):
        """Refuse une demande soumise (aucun crédit de solde)."""
        demande = self.get_object()
        try:
            services.refuser_allocation(demande, decide_par=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(demande).data)


class TypeLigneParcoursViewSet(_RhBaseViewSet):
    """Types de ligne de parcours configurables par société (ZRH15).

    La LECTURE (liste/détail) est ouverte à TOUT employé authentifié de
    la société — ces types s'affichent sur la fiche employé et dans
    l'annuaire self-service ; seule l'écriture (créer/modifier/supprimer
    un type) reste réservée au palier Administrateur/Responsable.
    """
    queryset = TypeLigneParcours.objects.all()
    serializer_class = TypeLigneParcoursSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'libelle']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class LigneParcoursViewSet(_RhBaseViewSet):
    """Timeline de parcours d'un employé (ZRH15, « Resume Line Types »
    Odoo). CRUD company-scopé ; ``company`` posée côté serveur. Affichée
    triée par date (voir ``Meta.ordering``) sur la fiche employé et dans
    l'annuaire self-service (XRH28, via
    ``LigneParcoursAnnuaireSerializer`` — champs non sensibles
    uniquement). Filtre : ``?employe=``. La LECTURE (liste/détail) est
    ouverte à TOUT employé authentifié de la société (consultation de sa
    propre fiche/de l'annuaire) ; seule l'écriture reste réservée au
    palier Administrateur/Responsable.
    """
    queryset = LigneParcours.objects.select_related('type', 'employe').all()
    serializer_class = LigneParcoursSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_creation']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class JourBloqueCongeViewSet(_RhBaseViewSet):
    """Jours de blocage congés (ZRH4) — Mandatory/Stress Days.

    Société scopée + Administrateur/Responsable. ``departements`` vide =
    blocage société entière ; sinon restreint aux départements liés (même
    société, validé côté serializer).
    """
    queryset = JourBloqueConge.objects.prefetch_related('departements').all()
    serializer_class = JourBloqueCongeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_fin', 'date_creation']

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class FeuilleTempsViewSet(_RhBaseViewSet):
    """Feuilles de temps par chantier (FG167) — heures imputées job-costing.

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur ; ``employe`` doit appartenir à la même société. Filtres :
    * ``?employe=<id>`` — feuilles d'un employé.
    * ``?installation_id=<id>`` — feuilles d'une installation (chantier).
    * ``?date=YYYY-MM-DD`` — feuilles d'un jour précis.
    * ``?intervention_id=<id>`` — feuilles liées à une intervention SAV.
    """
    queryset = FeuilleTemps.objects.select_related('employe').all()
    serializer_class = FeuilleTempsSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'heures', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        installation_id = self.request.query_params.get('installation_id')
        if installation_id:
            qs = qs.filter(installation_id=installation_id)
        intervention_id = self.request.query_params.get('intervention_id')
        if intervention_id:
            qs = qs.filter(intervention_id=intervention_id)
        date_str = self.request.query_params.get('date')
        if date_str:
            try:
                from datetime import datetime
                jour = datetime.strptime(date_str, '%Y-%m-%d').date()
                qs = qs.filter(date=jour)
            except (TypeError, ValueError):
                pass
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur. ``employe`` validé via le sérialiseur."""
        serializer.save(company=self.request.user.company)


class HeuresSuppViewSet(_RhBaseViewSet):
    """Heures supplémentaires & calcul majoré (FG168) — entrée de paie.

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur ; ``employe`` doit appartenir à la même société. À la création ET à
    la mise à jour, les décomptes majorés (heures normales, HS 25/50/100 %, taux
    interne, montant majoré) sont CALCULÉS côté serveur via
    ``services.appliquer_majoration`` (taux pris du dossier si non fourni) —
    jamais lus du corps. Filtres : ``?employe=<id>``, ``?date=YYYY-MM-DD``,
    ``?debut=`` / ``?fin=`` (plage).
    """
    queryset = HeuresSupp.objects.select_related('employe').all()
    serializer_class = HeuresSuppSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        date_str = self.request.query_params.get('date')
        if date_str:
            from datetime import datetime
            try:
                jour = datetime.strptime(date_str, '%Y-%m-%d').date()
                qs = qs.filter(date=jour)
            except (TypeError, ValueError):
                pass
        debut = self._parse_date(self.request.query_params.get('debut'))
        if debut:
            qs = qs.filter(date__gte=debut)
        fin = self._parse_date(self.request.query_params.get('fin'))
        if fin:
            qs = qs.filter(date__lte=fin)
        return qs

    @staticmethod
    def _parse_date(raw):
        if not raw:
            return None
        from datetime import datetime
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def perform_create(self, serializer):
        """Company posée côté serveur ; majoration calculée côté serveur.

        XRH8 — si le corps ne fournit PAS explicitement ``seuil_journalier``,
        le seuil est dérivé de l'horaire actif de l'employé à la date de
        l'entrée (Ramadan/saisonnier abaisse le seuil sur sa fenêtre).
        """
        derive = 'seuil_journalier' not in self.request.data
        instance = serializer.save(company=self.request.user.company)
        services.appliquer_majoration(
            instance, derive_seuil_from_horaire=derive)
        instance.save()

    def perform_update(self, serializer):
        """Recalcule la majoration à chaque mise à jour (même règle XRH8)."""
        derive = 'seuil_journalier' not in self.request.data
        instance = serializer.save()
        services.appliquer_majoration(
            instance, derive_seuil_from_horaire=derive)
        instance.save()

    @action(detail=False, methods=['get'], url_path='export-paie')
    def export_paie(self, request):
        """Totaux d'heures sup. majorées par employé sur une période (paie).

        ``?debut=YYYY-MM-DD`` → ``?fin=YYYY-MM-DD`` (défaut : 30 jours écoulés).
        ``?employe=<id>`` restreint à un employé. S'appuie sur
        ``selectors.heures_supp_pour_paie`` — scopé société.
        """
        today = timezone.localdate()
        debut = self._parse_date(request.query_params.get('debut')) \
            or (today - timedelta(days=30))
        fin = self._parse_date(request.query_params.get('fin')) or today
        employe = request.query_params.get('employe') or None
        rows = selectors.heures_supp_pour_paie(
            request.user.company, debut, fin, employe_id=employe)
        return Response(rows)


class PointageViewSet(_RhBaseViewSet):
    """Pointages (FG166) — arrivée/départ avec géoloc (mobile).

    Société scopée + Administrateur/Responsable. ``company`` et
    ``heure_arrivee`` sont posés côté serveur à la création ; ``employe`` doit
    appartenir à la même société. Filtres : ``?employe=``, ``?date=YYYY-MM-DD``
    (filtre sur la date de l'heure_arrivee).

    Actions spéciales :
    * ``POST .../pointager-arrivee/`` — ouvre un pointage : pose ``heure_arrivee``
      côté serveur et type ARRIVEE ; accepte ``employe``, ``note`` et GPS.
    * ``POST <id>/pointager-depart/`` — ferme un pointage : pose ``heure_depart``
      côté serveur ; accepte ``note`` et GPS départ. Calcule la durée en réponse.
    """
    queryset = Pointage.objects.select_related('employe').all()
    serializer_class = PointageSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['heure_arrivee', 'heure_depart', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        date_str = self.request.query_params.get('date')
        if date_str:
            try:
                from datetime import datetime
                jour = datetime.strptime(date_str, '%Y-%m-%d').date()
                qs = qs.filter(heure_arrivee__date=jour)
            except (TypeError, ValueError):
                pass
        return qs

    # XRH11 — champs suivis par l'audit immuable des corrections.
    _CHAMPS_AUDITES = (
        'heure_arrivee', 'heure_depart', 'type_pointage',
        'arrivee_gps_lat', 'arrivee_gps_lng',
        'depart_gps_lat', 'depart_gps_lng',
    )

    def update(self, request, *args, **kwargs):
        """XRH11 — toute modification d'un pointage EXISTANT (heures/type/GPS)
        exige un ``motif`` non vide et écrit une ligne d'audit immuable par
        champ modifié (``CorrectionPointage``). Sans motif → 400 ; avec motif
        → correction créée AVANT la sauvegarde effective. La création (POST)
        n'est PAS concernée — seule l'édition d'un pointage déjà existant."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        changements = []
        for champ in self._CHAMPS_AUDITES:
            if champ not in serializer.validated_data:
                continue
            ancien = getattr(instance, champ)
            nouveau = serializer.validated_data[champ]
            if ancien != nouveau:
                changements.append((champ, ancien, nouveau))

        if changements:
            motif = (request.data.get('motif') or '').strip()
            if not motif:
                return Response(
                    {'motif': "Un motif est obligatoire pour corriger "
                              "un pointage."},
                    status=status.HTTP_400_BAD_REQUEST)
            for champ, ancien, nouveau in changements:
                CorrectionPointage.objects.create(
                    company=request.user.company,
                    pointage=instance,
                    champ=champ,
                    ancienne_valeur=str(ancien) if ancien is not None else '',
                    nouvelle_valeur=str(nouveau) if nouveau is not None else '',
                    motif=motif,
                    auteur=request.user,
                )
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='corrections')
    def corrections(self, request, pk=None):
        """XRH11 — historique immuable des corrections de ce pointage."""
        pointage = self.get_object()
        qs = pointage.corrections.select_related('auteur').all()
        return Response(CorrectionPointageSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='importer',
            parser_classes=[MultiPartParser])
    def importer(self, request):
        """XRH13 — importe un CSV de pointeuse externe (device_user_id,
        horodatage, sens). Mappe via ``EmployeDeviceMap`` (société scopée) ;
        idempotent par ``(employe, horodatage)`` ; les lignes sans mapping
        connu sont rapportées en erreur (jamais silencieusement ignorées).

        ARC13 — lecture déléguée à ``apps.dataimport.parsing.iter_rows``
        (parseur générique partagé) au lieu d'un ``csv.DictReader`` local ;
        comportement inchangé (mêmes en-têtes, mêmes clés de lignes)."""
        from apps.dataimport.parsing import iter_rows

        f = request.FILES.get('file')
        if f is None:
            return Response(
                {'detail': 'Aucun fichier fourni.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            _headers, rows = iter_rows(f.read(), f.name)
        except Exception:
            return Response(
                {'detail': 'Fichier illisible (encodage invalide).'},
                status=status.HTTP_400_BAD_REQUEST)
        result = services.importer_pointages_csv(
            request.user.company, rows)
        return Response(result, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        """Company posée côté serveur ; heure_arrivee auto si absente."""
        now = timezone.now()
        # Si le corps ne fournit pas heure_arrivee, on la pose côté serveur.
        if not serializer.validated_data.get('heure_arrivee'):
            serializer.save(
                company=self.request.user.company,
                heure_arrivee=now,
                type_pointage=Pointage.TypePointage.ARRIVEE)
        else:
            serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['post'], url_path='pointager-arrivee')
    def pointager_arrivee(self, request):
        """Ouvre un pointage arrivée côté serveur (heure = now, type ARRIVEE).

        Corps attendu : ``employe`` (id), ``arrivee_gps_lat``,
        ``arrivee_gps_lng`` (facultatifs), ``note`` (facultatif). ``company``
        et ``heure_arrivee`` sont TOUJOURS posés côté serveur.
        """
        from django.http import Http404

        from core.selectors import get_company_object

        company = request.user.company
        employe_id = request.data.get('employe')
        # YRBAC11 — helper canonique (company-scopé, 404 indistinct converti
        # en 400 « employé inconnu » ici, contrat de validation de ce champ).
        try:
            employe = get_company_object(
                DossierEmploye, employe_id, request.user)
        except (Http404, ValueError, TypeError):
            return Response({'employe': 'Employé inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        pointage = Pointage.objects.create(
            company=company,
            employe=employe,
            type_pointage=Pointage.TypePointage.ARRIVEE,
            heure_arrivee=timezone.now(),
            arrivee_gps_lat=request.data.get('arrivee_gps_lat') or None,
            arrivee_gps_lng=request.data.get('arrivee_gps_lng') or None,
            note=request.data.get('note', ''),
        )
        return Response(self.get_serializer(pointage).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='pointager-depart')
    def pointager_depart(self, request, pk=None):
        """Ferme un pointage en posant ``heure_depart`` côté serveur (now).

        Met à jour le type à COMPLET si une arrivée était déjà renseignée.
        Accepte ``depart_gps_lat``, ``depart_gps_lng``, ``note``.
        La réponse inclut ``duree_minutes`` calculée.
        """
        pointage = self.get_object()
        if pointage.heure_depart is not None:
            return Response(
                {'detail': 'Ce pointage a déjà un départ enregistré.'},
                status=status.HTTP_400_BAD_REQUEST)
        pointage.heure_depart = timezone.now()
        if pointage.heure_arrivee:
            pointage.type_pointage = Pointage.TypePointage.COMPLET
        else:
            pointage.type_pointage = Pointage.TypePointage.DEPART
        lat = request.data.get('depart_gps_lat')
        lng = request.data.get('depart_gps_lng')
        note = request.data.get('note')
        if lat is not None:
            pointage.depart_gps_lat = lat or None
        if lng is not None:
            pointage.depart_gps_lng = lng or None
        if note is not None:
            pointage.note = note
        pointage.save()
        return Response(self.get_serializer(pointage).data)

    @action(detail=False, methods=['get'], url_path='absents-non-justifies')
    def absents_non_justifies(self, request):
        """ZRH6 — employés attendus le jour sans pointage NI congé validé
        (« Absence management » Odoo). ``?jour=YYYY-MM-DD`` (défaut
        aujourd'hui). Chaque ligne peut générer un ``IncidentPresence`` via
        ``POST .../generer-incident/``.
        """
        from datetime import datetime
        jour_str = request.query_params.get('jour')
        if jour_str:
            try:
                jour = datetime.strptime(jour_str, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                jour = timezone.localdate()
        else:
            jour = timezone.localdate()
        data = selectors.absents_non_justifies(request.user.company, jour)
        return Response(data)

    @action(detail=False, methods=['post'], url_path='generer-incident-absence')
    def generer_incident_absence(self, request):
        """ZRH6 — crée un ``IncidentPresence`` ABSENCE_INJUSTIFIEE pour un
        employé/jour (depuis la liste des absents non justifiés). Corps :
        ``employe`` (id), ``jour`` (YYYY-MM-DD, défaut aujourd'hui)."""
        from datetime import datetime
        employe_id = request.data.get('employe')
        if not employe_id:
            return Response(
                {'detail': "Le champ 'employe' est requis."},
                status=status.HTTP_400_BAD_REQUEST)
        jour_str = request.data.get('jour')
        if jour_str:
            try:
                jour = datetime.strptime(jour_str, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                jour = timezone.localdate()
        else:
            jour = timezone.localdate()
        employe = DossierEmploye.objects.filter(
            company=request.user.company, pk=employe_id).first()
        if employe is None:
            return Response(
                {'detail': 'Employé introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        incident = IncidentPresence.objects.create(
            company=request.user.company, employe=employe,
            type_incident=IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE,
            date=jour)
        return Response(
            IncidentPresenceSerializer(incident).data,
            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='rapport')
    def rapport(self, request):
        """ZRH18 — rapport de présence & heures supp. par employé/
        département sur période (« Attendance reporting » Odoo).
        ``?debut=&fin=`` (YYYY-MM-DD, requis) + filtres optionnels
        ``?employe=&departement=``. Gaté ``IsResponsableOrAdmin`` (gate de
        classe par défaut)."""
        from datetime import datetime

        debut_str = request.query_params.get('debut')
        fin_str = request.query_params.get('fin')
        if not debut_str or not fin_str:
            return Response(
                {'detail': "Les paramètres 'debut' et 'fin' sont requis."},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            debut = datetime.strptime(debut_str, '%Y-%m-%d').date()
            fin = datetime.strptime(fin_str, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return Response(
                {'detail': "Format de date invalide (attendu YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST)
        employe_id = request.query_params.get('employe')
        departement_id = request.query_params.get('departement')
        data = selectors.rapport_presence(
            request.user.company, debut, fin,
            employe_id=employe_id, departement_id=departement_id)
        return Response(data)


class PeriodeFermetureViewSet(_RhBaseViewSet):
    """Fermetures collectives / congés imposés (XRH14).

    Société scopée + Administrateur/Responsable. ``company`` posée CÔTÉ
    SERVEUR. ``departements`` (M2M) restreint la fermeture ; vide = toute
    la société.

    Action :
    * ``POST .../{id}/appliquer/`` — génère les demandes de congé VALIDÉES
      pour tous les employés concernés (idempotent, ré-appliquer ne duplique
      jamais).
    """
    queryset = PeriodeFermeture.objects.prefetch_related(
        'departements').select_related('type_absence').all()
    serializer_class = PeriodeFermetureSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_creation']

    @action(detail=True, methods=['post'], url_path='appliquer')
    def appliquer(self, request, pk=None):
        fermeture = self.get_object()
        creees = services.appliquer_fermeture(fermeture)
        return Response({
            'appliquee': True,
            'demandes_creees': len(creees),
        }, status=status.HTTP_200_OK)


class EmployeDeviceMapViewSet(_RhBaseViewSet):
    """Mappages pointeuse externe → employé (XRH13) — préalable à l'import CSV.

    Société scopée + Administrateur/Responsable. ``company`` posée CÔTÉ
    SERVEUR ; ``employe`` doit appartenir à la société. ``device_user_id``
    unique par société.
    """
    queryset = EmployeDeviceMap.objects.select_related('employe').all()
    serializer_class = EmployeDeviceMapSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['device_user_id', 'employe__matricule', 'employe__nom']
    ordering_fields = ['device_user_id', 'date_creation']


class ReglageRHViewSet(viewsets.ViewSet):
    """Réglages RH (XRH12) — singleton par société (Paramètres RH).

    Société scopée + Administrateur/Responsable. ``GET .../mon-reglage/`` /
    ``PATCH .../mon-reglage/`` lisent/éditent le réglage de l'appelant (créé à
    la demande — ``get_or_create``). ``company`` posée CÔTÉ SERVEUR.
    """
    permission_classes = [IsResponsableOrAdmin]

    @action(detail=False, methods=['get', 'patch'], url_path='mon-reglage')
    def mon_reglage(self, request):
        reglage, _ = ReglageRH.objects.get_or_create(
            company=request.user.company)
        if request.method == 'PATCH':
            ser = ReglageRHSerializer(
                reglage, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        return Response(ReglageRHSerializer(reglage).data)


class DeviceKiosqueViewSet(_RhBaseViewSet):
    """Devices kiosque de pointage (XRH10) — administration (Paramètres RH).

    Société scopée + Administrateur/Responsable. ``company`` posée CÔTÉ
    SERVEUR. Le token en clair n'est renvoyé QU'À l'émission
    (``POST .../emettre/``) — jamais stocké ni relisible ensuite.

    Actions :
    * ``POST .../emettre/`` — génère un nouveau device + son token en clair
      (``token`` dans la réponse, une seule fois). Corps : ``label``.
    * ``POST .../{id}/revoquer/`` — ``actif=False`` (idempotent).
    """
    queryset = DeviceKiosque.objects.all()
    serializer_class = DeviceKiosqueSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']

    @action(detail=False, methods=['post'], url_path='emettre')
    def emettre(self, request):
        device, raw_token = services.emettre_device_kiosque(
            request.user.company, label=request.data.get('label', ''))
        data = self.get_serializer(device).data
        data['token'] = raw_token
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='revoquer')
    def revoquer(self, request, pk=None):
        device = self.get_object()
        if device.actif:
            device.actif = False
            device.save(update_fields=['actif'])
        return Response(self.get_serializer(device).data)


class _KiosqueThrottle(AnonRateThrottle):
    """Throttle du guichet kiosque — protège contre le brute-force du PIN."""
    scope = 'rh_kiosque'

    def get_rate(self):
        return '30/min'


class KiosquePointageViewSet(viewsets.ViewSet):
    """Guichet kiosque de pointage (XRH10) — PIN + token de device, sans session.

    AUCUNE session utilisateur : authentifié par un token de device (header
    ``X-Kiosque-Token``, émis/révocable dans Paramètres via
    ``DeviceKiosqueViewSet``). Throttlé (30/min) contre le brute-force du PIN.
    Un PIN inconnu renvoie 404 neutre (jamais 400 — ne confirme ni n'infirme
    l'existence d'un PIN proche). Un token révoqué/inconnu renvoie 401.
    """
    permission_classes = [AllowAny]
    throttle_classes = [_KiosqueThrottle]

    def create(self, request):
        """``POST pointages/kiosque/`` — pointe l'employé du PIN (XRH10)."""
        raw_token = request.META.get('HTTP_X_KIOSQUE_TOKEN', '')
        device = services.resoudre_device_kiosque(raw_token)
        if device is None:
            return Response(
                {'detail': 'Token de device invalide ou révoqué.'},
                status=status.HTTP_401_UNAUTHORIZED)
        pin = request.data.get('pin', '')
        try:
            dossier, pointage, sens = services.pointer_via_kiosque(
                device, pin)
        except services.KiosqueError:
            return Response(
                {'detail': 'PIN inconnu.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'nom': f'{dossier.prenom} {dossier.nom}'.strip(),
            'sens': sens,
            'heure': (
                pointage.heure_depart if sens == 'depart'
                else pointage.heure_arrivee),
        }, status=status.HTTP_201_CREATED)


class AffectationRosterViewSet(_RhBaseViewSet):
    """Planning d'équipes / roster (FG169) — affectation hebdo + conflit congés.

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur ; ``employe`` doit appartenir à la même société. À la création ET à
    la mise à jour, ``semaine_du`` (lundi de la semaine) et ``conflit_conge``
    (congé validé couvrant le jour) sont CALCULÉS côté serveur via
    ``services.appliquer_roster`` — jamais lus du corps.

    Filtres : ``?employe=<id>``, ``?equipe=<libellé>``, ``?date=YYYY-MM-DD``,
    ``?semaine=YYYY-MM-DD`` (lundi de semaine), ``?conflit=1`` (conflits seuls).

    Actions :
    * ``GET .../semaine/?lundi=YYYY-MM-DD`` — roster d'une semaine entière.
    * ``GET .../conflits/?debut=&fin=`` — affectations en conflit de congé.
    """
    queryset = AffectationRoster.objects.select_related('employe').all()
    serializer_class = AffectationRosterSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['equipe']
    ordering_fields = ['date', 'equipe', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        equipe = self.request.query_params.get('equipe')
        if equipe:
            qs = qs.filter(equipe=equipe)
        date_str = self.request.query_params.get('date')
        if date_str:
            jour = self._parse_date(date_str)
            if jour:
                qs = qs.filter(date=jour)
        semaine = self._parse_date(self.request.query_params.get('semaine'))
        if semaine:
            lundi = services.lundi_de_la_semaine(semaine)
            qs = qs.filter(semaine_du=lundi)
        conflit = self.request.query_params.get('conflit')
        if conflit in ('1', 'true', 'True'):
            qs = qs.filter(conflit_conge=True)
        return qs

    @staticmethod
    def _parse_date(raw):
        if not raw:
            return None
        from datetime import datetime
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def perform_create(self, serializer):
        """Company posée côté serveur ; semaine + conflit calculés côté serveur."""
        instance = serializer.save(company=self.request.user.company)
        services.appliquer_roster(instance)
        instance.save(update_fields=['semaine_du', 'conflit_conge'])

    def perform_update(self, serializer):
        """Recalcule semaine + conflit de congé à chaque mise à jour."""
        instance = serializer.save()
        services.appliquer_roster(instance)
        instance.save(update_fields=['semaine_du', 'conflit_conge'])

    @action(detail=False, methods=['get'])
    def semaine(self, request):
        """Roster d'une semaine entière (``?lundi=YYYY-MM-DD``, défaut : semaine
        courante). S'appuie sur ``selectors.roster_semaine`` — scopé société."""
        lundi = self._parse_date(request.query_params.get('lundi'))
        if lundi is None:
            lundi = services.lundi_de_la_semaine(timezone.localdate())
        else:
            lundi = services.lundi_de_la_semaine(lundi)
        qs = selectors.roster_semaine(request.user.company, lundi)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def conflits(self, request):
        """Affectations en CONFLIT de congé sur une plage (``?debut=&fin=``,
        défaut : 30 jours à venir). S'appuie sur ``selectors.conflits_roster``."""
        today = timezone.localdate()
        debut = self._parse_date(request.query_params.get('debut')) or today
        fin = self._parse_date(request.query_params.get('fin')) \
            or (today + timedelta(days=30))
        qs = selectors.conflits_roster(request.user.company, debut, fin)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class PresenceChantierViewSet(_RhBaseViewSet):
    """Registre de présence chantier journalier / émargement (FG170).

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur ; ``employe`` doit appartenir à la même société. Trace QUI était
    présent sur QUEL chantier (preuve litige + base facturation main-d'œuvre).

    Filtres : ``?employe=<id>``, ``?installation_id=<id>``,
    ``?date=YYYY-MM-DD``, ``?statut=``, ``?emarge=0|1``,
    ``?debut=`` / ``?fin=`` (plage).

    Actions :
    * ``POST <id>/emarger/`` — pose l'émargement (signature de présence) côté
      serveur : ``emarge=True``, ``emarge_le=now``, ``emarge_par=user``.
    * ``GET .../chantier/?installation_id=&debut=&fin=`` — registre d'un chantier.
    """
    queryset = PresenceChantier.objects.select_related('employe').all()
    serializer_class = PresenceChantierSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'installation_id', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        installation_id = self.request.query_params.get('installation_id')
        if installation_id:
            qs = qs.filter(installation_id=installation_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        emarge = self.request.query_params.get('emarge')
        if emarge in ('0', 'false', 'False'):
            qs = qs.filter(emarge=False)
        elif emarge in ('1', 'true', 'True'):
            qs = qs.filter(emarge=True)
        date_str = self.request.query_params.get('date')
        if date_str:
            jour = self._parse_date(date_str)
            if jour:
                qs = qs.filter(date=jour)
        debut = self._parse_date(self.request.query_params.get('debut'))
        if debut:
            qs = qs.filter(date__gte=debut)
        fin = self._parse_date(self.request.query_params.get('fin'))
        if fin:
            qs = qs.filter(date__lte=fin)
        return qs

    @staticmethod
    def _parse_date(raw):
        if not raw:
            return None
        from datetime import datetime
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def perform_create(self, serializer):
        """Company posée côté serveur ; employe validé via le sérialiseur."""
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def emarger(self, request, pk=None):
        """Pose l'émargement (signature de présence) côté serveur.

        ``emarge=True``, ``emarge_le=now``, ``emarge_par=user``. Idempotent :
        ré-émarger ne change que l'horodatage/auteur. Société garantie par le
        TenantMixin (un autre tenant reçoit 404).

        XRH12 — accepte optionnellement ``gps_lat``/``gps_lng`` (GPS mobile) :
        si un géofence est configuré (Paramètres RH) et les coordonnées de
        référence du chantier sont connues, hors rayon flague ``hors_zone``
        et journalise un incident (FG171) — JAMAIS bloquant.
        """
        presence = self.get_object()
        presence.emarge = True
        presence.emarge_le = timezone.now()
        presence.emarge_par = request.user
        update_fields = [
            'emarge', 'emarge_le', 'emarge_par', 'date_modification']
        gps_lat = request.data.get('gps_lat')
        gps_lng = request.data.get('gps_lng')
        if gps_lat is not None or gps_lng is not None:
            services.controler_geofence_presence(presence, gps_lat, gps_lng)
            update_fields += ['gps_lat', 'gps_lng', 'hors_zone']
        presence.save(update_fields=update_fields)
        return Response(self.get_serializer(presence).data)

    @action(detail=False, methods=['get'])
    def chantier(self, request):
        """Registre de présence d'un chantier (``?installation_id=`` requis,
        ``?debut=&fin=`` optionnels, ``?presents=1`` exclut les absents).
        S'appuie sur ``selectors.presences_installation`` — scopé société."""
        installation_id = request.query_params.get('installation_id')
        if not installation_id:
            return Response(
                {'installation_id': "Paramètre 'installation_id' requis."},
                status=status.HTTP_400_BAD_REQUEST)
        debut = self._parse_date(request.query_params.get('debut'))
        fin = self._parse_date(request.query_params.get('fin'))
        presents = request.query_params.get('presents') in ('1', 'true', 'True')
        qs = selectors.presences_installation(
            request.user.company, installation_id,
            date_debut=debut, date_fin=fin, presents_seulement=presents)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class IncidentPresenceViewSet(_RhBaseViewSet):
    """Retards & absences injustifiées (FG171) — marquage + compteur.

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur ; ``employe`` doit appartenir à la même société. Marque les
    incidents disciplinaires (retard / absence injustifiée / départ anticipé) ;
    le compteur par employé se dérive par agrégation, jamais stocké.

    Filtres : ``?employe=<id>``, ``?type_incident=``, ``?justifie=0|1``,
    ``?date=YYYY-MM-DD``, ``?debut=`` / ``?fin=`` (plage).

    Actions :
    * ``POST <id>/justifier/`` — régularise l'incident (``justifie=True``,
      ``motif``, ``justifie_par=user``, ``justifie_le=now``) côté serveur.
    * ``GET .../compteur/?debut=&fin=&employe=&inclure_justifies=1`` — compteur
      d'incidents par employé (pilotage/disciplinaire).
    """
    queryset = IncidentPresence.objects.select_related('employe').all()
    serializer_class = IncidentPresenceSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'type_incident', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        type_incident = self.request.query_params.get('type_incident')
        if type_incident:
            qs = qs.filter(type_incident=type_incident)
        justifie = self.request.query_params.get('justifie')
        if justifie in ('0', 'false', 'False'):
            qs = qs.filter(justifie=False)
        elif justifie in ('1', 'true', 'True'):
            qs = qs.filter(justifie=True)
        date_str = self.request.query_params.get('date')
        if date_str:
            jour = self._parse_date(date_str)
            if jour:
                qs = qs.filter(date=jour)
        debut = self._parse_date(self.request.query_params.get('debut'))
        if debut:
            qs = qs.filter(date__gte=debut)
        fin = self._parse_date(self.request.query_params.get('fin'))
        if fin:
            qs = qs.filter(date__lte=fin)
        return qs

    @staticmethod
    def _parse_date(raw):
        if not raw:
            return None
        from datetime import datetime
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def perform_create(self, serializer):
        """Company posée côté serveur ; employe validé via le sérialiseur."""
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def justifier(self, request, pk=None):
        """Régularise un incident (le sort du décompte disciplinaire).

        Pose ``justifie=True``, ``motif`` (corps), ``justifie_par=user`` et
        ``justifie_le=now`` côté serveur. Société garantie par le TenantMixin.
        """
        incident = self.get_object()
        incident.justifie = True
        motif = request.data.get('motif')
        if motif is not None:
            incident.motif = motif
        incident.justifie_par = request.user
        incident.justifie_le = timezone.now()
        incident.save(update_fields=[
            'justifie', 'motif', 'justifie_par', 'justifie_le',
            'date_modification'])
        return Response(self.get_serializer(incident).data)

    @action(detail=False, methods=['get'])
    def compteur(self, request):
        """Compteur d'incidents par employé sur une période (``?debut=&fin=``,
        défaut : 90 jours écoulés ; ``?employe=`` restreint ; ``?inclure_justifies=1``
        rétablit le total brut). S'appuie sur ``selectors.compteur_incidents``."""
        today = timezone.localdate()
        debut = self._parse_date(request.query_params.get('debut')) \
            or (today - timedelta(days=90))
        fin = self._parse_date(request.query_params.get('fin')) or today
        employe = request.query_params.get('employe') or None
        inclure = request.query_params.get('inclure_justifies') in (
            '1', 'true', 'True')
        rows = selectors.compteur_incidents(
            request.user.company, date_debut=debut, date_fin=fin,
            employe_id=employe, inclure_justifies=inclure)
        return Response(rows)


class CompetenceViewSet(_RhBaseViewSet):
    """Référentiel de compétences (FG172) — catalogue par société.

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur (jamais lue du corps). Catalogue des savoir-faire techniques (pose
    structure, raccordement DC/AC, MES onduleur, pompage, soudure…) évalués
    dans la matrice ``competences-employe``.

    Filtres : ``?domaine=``, ``?actif=0|1``. Recherche : code / libellé.
    """
    queryset = Competence.objects.all()
    serializer_class = CompetenceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle', 'description']
    ordering_fields = ['domaine', 'libelle', 'code', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        domaine = self.request.query_params.get('domaine')
        if domaine:
            qs = qs.filter(domaine=domaine)
        actif = self.request.query_params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        return qs

    def get_permissions(self):
        # ZRH17 — la recherche par compétence sert au staffing terrain
        # (« qui maîtrise X ? ») : accessible à TOUT employé authentifié de
        # la société, pas seulement Administrateur/Responsable. Le
        # serializer annuaire dédié garantit qu'aucun champ sensible ne
        # fuit, donc élargir ici l'accès en lecture est sûr (même pattern
        # que XRH28 sur ``DossierEmployeViewSet.annuaire``).
        if self.action == 'employes':
            return [IsAnyRole()]
        return super().get_permissions()

    def perform_create(self, serializer):
        """Company posée côté serveur, jamais lue du corps."""
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['get'], url_path='employes')
    def employes(self, request, pk=None):
        """ZRH17 — employés qualifiés sur CETTE compétence (« Skills
        search/filter » Odoo). ``?niveau_min=`` (défaut 0). Multi-critères :
        ``?competences=<id1>,<id2>`` ajoute une INTERSECTION (l'employé doit
        satisfaire ``niveau_min`` sur toutes). Champs non sensibles
        (serializer annuaire XRH28), lecture seule, société scopée."""
        competence = self.get_object()
        niveau_min = int(request.query_params.get('niveau_min', 0))
        autres_raw = request.query_params.get('competences', '')
        autres_ids = [
            cid.strip() for cid in autres_raw.split(',') if cid.strip()]
        employes = selectors.employes_par_competence(
            request.user.company, competence.id,
            niveau_min=niveau_min, competence_ids=autres_ids)
        return Response(
            AnnuaireEmployeSerializer(employes, many=True).data)

    @action(detail=False, methods=['get'], url_path='evolution')
    def evolution(self, request):
        """ZRH10 — rapport d'évolution des compétences (« Skills Evolution »
        Odoo). ``?employe=&competence=&debut=&fin=`` optionnels (YYYY-MM-DD).
        Gaté ``IsResponsableOrAdmin`` (gate de classe par défaut)."""
        from datetime import datetime

        def _parse(name):
            raw = request.query_params.get(name)
            if not raw:
                return None
            try:
                return datetime.strptime(raw, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                return None

        data = selectors.evolution_competences(
            request.user.company,
            employe_id=request.query_params.get('employe'),
            competence_id=request.query_params.get('competence'),
            debut=_parse('debut'), fin=_parse('fin'))
        return Response(data)


class CompetenceEmployeViewSet(_RhBaseViewSet):
    """Matrice de compétences — niveau par employé (FG172).

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur ; ``employe`` ET ``competence`` doivent appartenir à la même
    société. Une ligne par (employé, compétence) — on met à jour le niveau
    plutôt que d'empiler. ``evalue_par``/``evalue_le`` sont posés côté serveur
    à chaque écriture du niveau.

    Filtres : ``?employe=<id>``, ``?competence=<id>``, ``?domaine=``,
    ``?niveau_min=<0-4>``.
    """
    queryset = CompetenceEmploye.objects.select_related(
        'employe', 'competence').all()
    serializer_class = CompetenceEmployeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['niveau', 'competence', 'date_modification']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        competence = self.request.query_params.get('competence')
        if competence:
            qs = qs.filter(competence_id=competence)
        domaine = self.request.query_params.get('domaine')
        if domaine:
            qs = qs.filter(competence__domaine=domaine)
        niveau_min = self.request.query_params.get('niveau_min')
        if niveau_min is not None:
            try:
                qs = qs.filter(niveau__gte=int(niveau_min))
            except (TypeError, ValueError):
                pass
        return qs

    def perform_create(self, serializer):
        """Company + traçabilité d'évaluation posées côté serveur.

        ZRH10 — une CRÉATION avec niveau > 0 est un changement (0 -> niveau)
        et écrit une ligne ``HistoriqueCompetence`` (source='manuelle').
        """
        instance = serializer.save(
            company=self.request.user.company,
            evalue_par=self.request.user,
            evalue_le=timezone.now())
        if instance.niveau:
            HistoriqueCompetence.objects.create(
                company=instance.company, employe=instance.employe,
                competence=instance.competence,
                ancien_niveau=0, nouveau_niveau=instance.niveau,
                source=HistoriqueCompetence.Source.MANUELLE)

    def perform_update(self, serializer):
        """Réévaluation : on retrace l'auteur/date côté serveur.

        ZRH10 — écrit ``HistoriqueCompetence`` (source='manuelle') si le
        niveau change réellement."""
        ancien_niveau = serializer.instance.niveau
        instance = serializer.save(
            evalue_par=self.request.user,
            evalue_le=timezone.now())
        if instance.niveau != ancien_niveau:
            HistoriqueCompetence.objects.create(
                company=instance.company, employe=instance.employe,
                competence=instance.competence,
                ancien_niveau=ancien_niveau, nouveau_niveau=instance.niveau,
                source=HistoriqueCompetence.Source.MANUELLE)

    @action(detail=False, methods=['get'])
    def matrice(self, request):
        """Matrice de compétences (FG172) : pour chaque employé évalué, la
        liste de ses compétences avec niveau.

        Société garantie par ``get_queryset`` (TenantMixin). Respecte les
        mêmes filtres que la liste standard (``?employe=``, ``?competence=``,
        ``?domaine=``, ``?niveau_min=``).
        """
        qs = self.get_queryset().order_by('employe', 'competence')
        matrice = {}
        for ligne in qs:
            emp = ligne.employe
            entry = matrice.setdefault(emp.id, {
                'employe_id': emp.id,
                'matricule': emp.matricule,
                'employe_nom': f'{emp.nom} {emp.prenom}',
                'competences': [],
            })
            entry['competences'].append({
                'competence_id': ligne.competence_id,
                'code': ligne.competence.code,
                'libelle': ligne.competence.libelle,
                'domaine': ligne.competence.domaine,
                'niveau': ligne.niveau,
                'niveau_display': ligne.get_niveau_display(),
            })
        return Response(list(matrice.values()))


class GrilleSalarialeViewSet(TenantMixin, viewsets.ModelViewSet):
    """Grille salariale par poste (XRH16) — bandes min/max, paie SENSIBLE.

    Lecture ET écriture réservées aux porteurs de ``salaires_voir`` (comme
    ``RemunerationViewSet``) : sans cette permission tout accès est refusé
    (403). Société scopée + posée côté serveur. Filtre ``?poste=<id>``.
    """
    permission_classes = [HasPermission('salaires_voir')]
    queryset = GrilleSalariale.objects.select_related('poste').all()
    serializer_class = GrilleSalarialeSerializer
    filter_backends = [filters.OrderingFilter]
    filterset_fields = ['poste']
    ordering_fields = ['date_effet', 'poste']

    def get_queryset(self):
        qs = super().get_queryset()
        poste = self.request.query_params.get('poste')
        if poste:
            qs = qs.filter(poste_id=poste)
        return qs


class CompetenceRequiseViewSet(_RhBaseViewSet):
    """Profil de compétences requises par poste (XRH15) — analyse d'écart.

    Société scopée + Administrateur/Responsable. ``company`` posée CÔTÉ
    SERVEUR ; ``poste`` et ``competence`` doivent appartenir à la société.
    Unicité (poste, compétence).

    Filtres : ``?poste=<id>``.
    """
    queryset = CompetenceRequise.objects.select_related(
        'poste', 'competence').all()
    serializer_class = CompetenceRequiseSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['poste', 'competence']

    def get_queryset(self):
        qs = super().get_queryset()
        poste = self.request.query_params.get('poste')
        if poste:
            qs = qs.filter(poste_id=poste)
        return qs

    @action(detail=False, methods=['get'])
    def matrice(self, request):
        """Matrice par employé : pour chaque employé ayant au moins un niveau,
        la liste de ses compétences évaluées (code/libellé/domaine/niveau).

        Société garantie par ``get_queryset`` (TenantMixin). ``?employe=`` et
        ``?domaine=`` restreignent comme la liste standard.
        """
        qs = self.get_queryset().order_by('employe', 'competence')
        matrice = {}
        for ligne in qs:
            emp = ligne.employe
            entry = matrice.setdefault(emp.id, {
                'employe_id': emp.id,
                'matricule': emp.matricule,
                'employe_nom': f'{emp.nom} {emp.prenom}',
                'competences': [],
            })
            entry['competences'].append({
                'competence_id': ligne.competence_id,
                'code': ligne.competence.code,
                'libelle': ligne.competence.libelle,
                'domaine': ligne.competence.domaine,
                'niveau': ligne.niveau,
                'niveau_display': ligne.get_niveau_display(),
            })
        return Response(list(matrice.values()))


class HabilitationViewSet(_RhBaseViewSet):
    """Habilitations électriques par employé (FG173) — titre + validité/organisme.

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur (jamais lue du corps) ; ``employe`` doit appartenir à la même
    société. Une ligne par (employé, titre) ; ``valide`` (actif ET non expiré)
    est calculé. Concept DISTINCT de la matrice de compétences (FG172) : ici un
    TITRE réglementaire avec échéance, exigé sur tout chantier PV.

    Filtres : ``?employe=<id>``, ``?type_habilitation=``, ``?actif=0|1``.
    Recherche : organisme.

    Actions :
    * ``GET .../expirantes/?expire_within=N&employe=&inclure_expirees=0`` —
      habilitations qui expirent dans N jours (défaut 30) ou déjà expirées.
    """
    queryset = Habilitation.objects.select_related('employe').all()
    serializer_class = HabilitationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['organisme']
    ordering_fields = [
        'date_validite', 'date_obtention', 'type_habilitation',
        'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        type_habilitation = self.request.query_params.get('type_habilitation')
        if type_habilitation:
            qs = qs.filter(type_habilitation=type_habilitation)
        actif = self.request.query_params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur ; employe validé via le sérialiseur."""
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'])
    def expirantes(self, request):
        """Habilitations qui expirent bientôt ou sont déjà expirées (FG173).

        ``?expire_within=N`` (défaut 30) fixe la fenêtre ; ``?employe=``
        restreint à un employé ; ``?inclure_expirees=0`` ne garde que les
        échéances à venir (par défaut on inclut aussi les titres déjà échus, qui
        sont précisément ceux à signaler avant un chantier PV). S'appuie sur
        ``selectors.habilitations_expirantes`` — scopé société.
        """
        within = request.query_params.get('expire_within', 30)
        employe = request.query_params.get('employe') or None
        inclure = request.query_params.get('inclure_expirees') \
            not in ('0', 'false', 'False')
        qs = selectors.habilitations_expirantes(
            request.user.company, within_days=within,
            inclure_expirees=inclure, employe_id=employe)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class CertificationViewSet(_RhBaseViewSet):
    """Certifications spécifiques par employé (FG174) — hauteur/harnais/CACES…

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur (jamais lue du corps) ; ``employe`` doit appartenir à la même
    société. Une ligne par (employé, certification) ; ``valide`` (actif ET non
    expiré) est calculé. Famille DISTINCTE des habilitations électriques
    (FG173) : ici les certifications NON électriques (travail en hauteur,
    harnais, CACES/nacelle, secourisme SST, conduite), avec expiration.

    Filtres : ``?employe=<id>``, ``?type_certification=``, ``?actif=0|1``.
    Recherche : organisme.

    Actions :
    * ``GET .../expirantes/?expire_within=N&employe=&inclure_expirees=0`` —
      certifications qui expirent dans N jours (défaut 30) ou déjà expirées.
    """
    queryset = Certification.objects.select_related('employe').all()
    serializer_class = CertificationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['organisme']
    ordering_fields = [
        'date_validite', 'date_obtention', 'type_certification',
        'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        type_certification = self.request.query_params.get(
            'type_certification')
        if type_certification:
            qs = qs.filter(type_certification=type_certification)
        actif = self.request.query_params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur ; employe validé via le sérialiseur."""
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'])
    def expirantes(self, request):
        """Certifications qui expirent bientôt ou sont déjà expirées (FG174).

        ``?expire_within=N`` (défaut 30) fixe la fenêtre ; ``?employe=``
        restreint à un employé ; ``?inclure_expirees=0`` ne garde que les
        échéances à venir (par défaut on inclut aussi les certifications déjà
        échues, qui sont précisément celles à signaler avant un chantier PV).
        S'appuie sur ``selectors.certifications_expirantes`` — scopé société.
        """
        within = request.query_params.get('expire_within', 30)
        employe = request.query_params.get('employe') or None
        inclure = request.query_params.get('inclure_expirees') \
            not in ('0', 'false', 'False')
        qs = selectors.certifications_expirantes(
            request.user.company, within_days=within,
            inclure_expirees=inclure, employe_id=employe)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class VisiteMedicaleViewSet(_RhBaseViewSet):
    """Visites médicales du travail par employé (FG177) — aptitude + échéance.

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur (jamais lue du corps) ; ``employe`` doit appartenir à la même
    société. On garde l'historique des visites (pas d'unicité) ; ``a_jour``
    (active ET prochaine visite non dépassée) est calculé. Famille DISTINCTE des
    habilitations (FG173) et certifications (FG174) : ici l'examen de la
    médecine du travail prononçant l'aptitude (apte / apte avec restrictions /
    inapte), obligatoire avant le chantier.

    Filtres : ``?employe=<id>``, ``?aptitude=``, ``?actif=0|1``.
    Recherche : médecin, organisme.

    Actions :
    * ``GET .../expirantes/?expire_within=N&employe=&inclure_expirees=0`` —
      visites dont la prochaine échéance arrive dans N jours (défaut 30) ou est
      déjà dépassée.
    """
    queryset = VisiteMedicale.objects.select_related('employe').all()
    serializer_class = VisiteMedicaleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['medecin', 'organisme']
    ordering_fields = [
        'prochaine_visite', 'date_visite', 'aptitude', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        aptitude = self.request.query_params.get('aptitude')
        if aptitude:
            qs = qs.filter(aptitude=aptitude)
        actif = self.request.query_params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur ; employe validé via le sérialiseur."""
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'])
    def expirantes(self, request):
        """Visites médicales à renouveler bientôt ou déjà échues (FG177).

        ``?expire_within=N`` (défaut 30) fixe la fenêtre ; ``?employe=``
        restreint à un employé ; ``?inclure_expirees=0`` ne garde que les
        échéances à venir (par défaut on inclut aussi les visites déjà échues,
        qui sont précisément celles à signaler avant un chantier). S'appuie sur
        ``selectors.visites_medicales_expirantes`` — scopé société.
        """
        within = request.query_params.get('expire_within', 30)
        employe = request.query_params.get('employe') or None
        inclure = request.query_params.get('inclure_expirees') \
            not in ('0', 'false', 'False')
        qs = selectors.visites_medicales_expirantes(
            request.user.company, within_days=within,
            inclure_expirees=inclure, employe_id=employe)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class EpiCatalogueViewSet(_RhBaseViewSet):
    """Catalogue des EPI de la société (FG178) — référentiel d'équipements.

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur (jamais lue du corps). Référentiel des équipements de protection
    individuelle (casque, harnais, gants isolants, chaussures, lunettes…) ; la
    dotation nominative est portée par ``DotationEpi``.

    Filtres : ``?type_epi=``, ``?actif=0|1``. Recherche : désignation.
    """
    queryset = EpiCatalogue.objects.all()
    serializer_class = EpiCatalogueSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['designation']
    ordering_fields = ['type_epi', 'designation', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        type_epi = self.request.query_params.get('type_epi')
        if type_epi:
            qs = qs.filter(type_epi=type_epi)
        actif = self.request.query_params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur (jamais lue du corps)."""
        serializer.save(company=self.request.user.company)


class DotationEpiViewSet(_RhBaseViewSet):
    """Dotations EPI nominatives (FG178) — qui porte quel EPI, taille + date.

    Société scopée + Administrateur/Responsable. ``company`` est posée côté
    serveur (jamais lue du corps) ; ``employe`` et ``epi`` doivent appartenir à
    la même société. Une ligne par attribution (employé, EPI) avec taille, date
    de dotation et éventuelle date de renouvellement (échéance).

    Filtres : ``?employe=<id>``, ``?epi=<id>``, ``?type_epi=``. Recherche :
    taille, note.

    Actions :
    * ``GET .../a-renouveler/?expire_within=N&employe=&inclure_expirees=0`` —
      dotations dont le renouvellement arrive dans N jours (défaut 30) ou est
      déjà dépassé.
    * ``GET .../a-remplacer-controler/?expire_within=N&employe=`` — EPI à durée
      de vie (FG179) dont la péremption OU le recontrôle arrive dans N jours
      (défaut 30) ou est déjà dépassé.
    * ``GET .../employe/?employe=<id>`` — dotations EPI d'un employé.
    * ``POST .../<id>/emarger/`` — émargement signé de la remise (FG180) :
      accusé de réception prouvant la dotation (exigible CNSS / accident).
    * ``GET .../<id>/emargements/`` — historique des émargements d'une dotation.
    """
    queryset = DotationEpi.objects.select_related('employe', 'epi').all()
    serializer_class = DotationEpiSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['taille', 'note']
    ordering_fields = [
        'date_renouvellement', 'date_dotation',
        'date_peremption', 'date_prochain_controle', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        epi = self.request.query_params.get('epi')
        if epi:
            qs = qs.filter(epi_id=epi)
        type_epi = self.request.query_params.get('type_epi')
        if type_epi:
            qs = qs.filter(epi__type_epi=type_epi)
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur ; employe/epi validés via le sérialiseur.

        YHIRE13 — passe par ``services.creer_dotation_epi`` : si l'EPI est lié
        à un produit de stock, décrémente le stock (warn par défaut, jamais un
        blocage silencieux) ; un EPI non lié = comportement inchangé.
        """
        data = serializer.validated_data
        try:
            dotation = services.creer_dotation_epi(
                company=self.request.user.company,
                epi=data['epi'], employe=data['employe'],
                quantite=data.get('quantite', 1),
                user=self.request.user,
                **{k: v for k, v in data.items()
                   if k not in ('epi', 'employe', 'quantite', 'company')})
        except ValueError as exc:
            raise serializers.ValidationError({'detail': str(exc)})
        serializer.instance = dotation

    @action(detail=True, methods=['post'], url_path='restituer')
    def restituer(self, request, pk=None):
        """YHIRE13 — restitue la dotation : réintègre le stock si l'EPI est
        lié à un produit, marque ``restituee``. Déjà restituée → 400."""
        dotation = self.get_object()
        try:
            services.restituer_dotation_epi(dotation, user=request.user)
        except services.RestitutionEpiError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(dotation).data)

    @action(detail=False, methods=['get'], url_path='a-renouveler')
    def a_renouveler(self, request):
        """Dotations EPI dont le renouvellement approche ou est dépassé (FG178).

        ``?expire_within=N`` (défaut 30) fixe la fenêtre ; ``?employe=``
        restreint à un employé ; ``?inclure_expirees=0`` ne garde que les
        échéances à venir (par défaut on inclut aussi les EPI déjà à remplacer,
        précisément ceux à signaler avant un chantier). S'appuie sur
        ``selectors.dotations_epi_a_renouveler`` — scopé société.
        """
        within = request.query_params.get('expire_within', 30)
        employe = request.query_params.get('employe') or None
        inclure = request.query_params.get('inclure_expirees') \
            not in ('0', 'false', 'False')
        qs = selectors.dotations_epi_a_renouveler(
            request.user.company, within_days=within,
            inclure_expirees=inclure, employe_id=employe)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='a-remplacer-controler')
    def a_remplacer_controler(self, request):
        """EPI à durée de vie : péremption OU recontrôle proche/dépassé (FG179).

        ``?expire_within=N`` (défaut 30) fixe la fenêtre ; ``?employe=``
        restreint à un employé. Inclut toujours les échéances déjà dépassées
        (un EPI périmé ou en retard de contrôle est précisément ce qui doit
        alerter avant un chantier). S'appuie sur
        ``selectors.epi_a_remplacer_ou_controler`` — scopé société.
        """
        within = request.query_params.get('expire_within', 30)
        employe = request.query_params.get('employe') or None
        qs = selectors.epi_a_remplacer_ou_controler(
            request.user.company, within_days=within, employe_id=employe)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def employe(self, request):
        """Dotations EPI d'un employé (``?employe=<id>``), scopé société."""
        employe = request.query_params.get('employe')
        qs = self.get_queryset()
        if employe:
            qs = qs.filter(employe_id=employe)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='emarger')
    def emarger(self, request, pk=None):
        """Émargement signé de la remise d'un EPI (FG180) — accusé de réception.

        Corps : ``signataire_nom`` (nom dactylographié, requis — loi 53-05),
        ``role_signataire`` (employe/remettant/temoin, défaut ``employe``),
        ``methode`` (typed/draw, défaut ``typed``), ``mention`` (optionnelle).
        L'utilisateur agissant, la société et les preuves (IP, user agent) sont
        posés CÔTÉ SERVEUR — jamais lus du corps. Marque la dotation ACCUSÉE
        (``accuse_remise``), preuve exigible en cas de contrôle CNSS / accident
        du travail. La société est garantie par ``get_object``.
        """
        dotation = self.get_object()
        body = EmargerEpiSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        try:
            resultat = services.emarger_dotation(
                dotation,
                signataire_nom=data['signataire_nom'],
                role_signataire=data['role_signataire'],
                methode=data['methode'],
                mention=data.get('mention', ''),
                signataire=request.user,
                ip_adresse=_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
        except services.EmargementError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        dotation.refresh_from_db()
        return Response(
            {
                'emargement': EmargementEpiSerializer(
                    resultat['emargement']).data,
                'deja_accusee': resultat['deja_accusee'],
                'accuse_remise': dotation.accuse_remise,
                'date_accuse': dotation.date_accuse,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='emargements')
    def emargements(self, request, pk=None):
        """Historique des émargements signés d'une dotation EPI (FG180).

        Lecture seule, scopée société (``get_object``). Renvoie les preuves de
        remise (nom dactylographié, rôle, méthode, mention, IP, date) du plus
        récent au plus ancien.
        """
        dotation = self.get_object()
        qs = dotation.emargements.all()
        serializer = EmargementEpiSerializer(qs, many=True)
        return Response(serializer.data)


class EcheancesRhViewSet(TenantMixin, viewsets.ViewSet):
    """Moteur d'échéances RH unifié (FG175) — alertes d'expiration agrégées.

    Société scopée + Administrateur/Responsable. Réunit en UNE liste normalisée
    les habilitations (FG173), certifications (FG174), documents employé
    (FG159), visites médicales (FG177) et dotations EPI à renouveler (FG178) qui
    expirent (ou sont déjà expirés) dans la fenêtre demandée.

    Action :
    * ``GET .../echeances/?within=N`` — échéances dans les N prochains jours
      (défaut 30) ou déjà dépassées, triées par échéance la plus proche.

    Le résultat est une liste de dicts ``{type, employe_id, employe, libelle,
    date_validite, jours_restants}`` — non paginée (vue d'alerte synthétique).
    """
    permission_classes = [IsResponsableOrAdmin]

    def list(self, request):
        within = request.query_params.get('within', 30)
        rows = selectors.echeances_rh(
            request.user.company, within_days=within)
        return Response(rows)


class RecrutementStatistiquesViewSet(TenantMixin, viewsets.ViewSet):
    """XRH22 — analytics recrutement (délai d'embauche, entonnoir, sources).

    Société scopée + Administrateur/Responsable. Lecture seule.

    Action :
    * ``GET .../recrutement/statistiques/?debut=YYYY-MM-DD&fin=YYYY-MM-DD`` —
      délai d'embauche moyen, entonnoir par étape, candidatures par ouverture
      et efficacité par source sur la période (bornes optionnelles).
    """
    permission_classes = [IsResponsableOrAdmin]

    def list(self, request):
        debut = request.query_params.get('debut') or None
        fin = request.query_params.get('fin') or None
        data = selectors.stats_recrutement(
            request.user.company, debut=debut, fin=fin)
        return Response(data)


class TableauBordHseViewSet(TenantMixin, viewsets.ViewSet):
    """Tableau de bord HSE (FG185) — agrégation lecture seule, admin-gated.

    Société scopée + Administrateur/Responsable. Endpoint READ/agrégation pur
    (aucun nouveau modèle, aucune écriture) qui synthétise les indicateurs
    Hygiène-Sécurité-Environnement de la société : taux de fréquence / taux de
    gravité des accidents du travail (FG181), compteurs bruts d'accidents et de
    presqu'accidents (FG182), alertes d'expiration des habilitations (FG173),
    certifications (FG174), visites médicales (FG177) et EPI (FG178/FG179), et
    les presqu'accidents regroupés par chantier.

    Action :
    * ``GET .../tableau-bord-hse/?within=N`` (et le ``list`` du routeur) —
      agrège sur les N derniers jours pour les événements et les N prochains
      jours pour les alertes d'échéance (défaut 30). Délègue à
      ``selectors.tableau_bord_hse`` ; division par zéro gardée (taux ``null``
      si aucune heure travaillée). Réponse = un seul dict (non paginé).
    """
    permission_classes = [IsResponsableOrAdmin]

    def list(self, request):
        within = request.query_params.get('within', 30)
        data = selectors.tableau_bord_hse(
            request.user.company, within_days=within)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='tableau-bord-hse')
    def tableau_bord_hse(self, request):
        """Alias explicite du tableau de bord HSE (FG185)."""
        return self.list(request)


class AccidentTravailViewSet(_RhBaseViewSet):
    """Registre HSE & accidents du travail (FG181) — déclaration + export CNSS.

    Société scopée + Administrateur/Responsable. ``company`` ET ``reference``
    (``AT-YYYYMM-NNNN``, race-safe — jamais ``count()+1``) sont posées CÔTÉ
    SERVEUR ; ``employe`` (le blessé) doit appartenir à la même société.
    Déclare un accident du travail (date / lieu / blessé / gravité / arrêt /
    photo) et suit la déclaration CNSS (``declare_cnss`` + date).

    Filtres : ``?gravite=leger|grave|mortel``, ``?statut=declare|clos``,
    ``?employe=<id>``. Recherche : référence, lieu.

    Action :
    * ``GET .../?export=csv`` (ou ``GET .../export-cnss/``) — export CSV des
      champs d'une déclaration d'accident du travail CNSS, scopé société et
      filtré comme la liste. ``?debut=`` / ``?fin=`` bornent la date d'accident.
    """
    queryset = AccidentTravail.objects.select_related('employe').all()
    serializer_class = AccidentTravailSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'lieu']
    ordering_fields = [
        'date_accident', 'gravite', 'statut', 'reference', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        gravite = self.request.query_params.get('gravite')
        if gravite:
            qs = qs.filter(gravite=gravite)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        debut = self._parse_date(self.request.query_params.get('debut'))
        if debut:
            qs = qs.filter(date_accident__gte=debut)
        fin = self._parse_date(self.request.query_params.get('fin'))
        if fin:
            qs = qs.filter(date_accident__lte=fin)
        return qs

    @staticmethod
    def _parse_date(raw):
        if not raw:
            return None
        from datetime import datetime
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def perform_create(self, serializer):
        """Company + reference (race-safe) posées côté serveur (FG181).

        YHIRE10 — un arrêt de travail déclaré à la création synchronise
        aussitôt l'absence de présence liée (roster + import paie)."""
        services.creer_accident_travail(serializer, self.request.user.company)
        services.synchroniser_absence_accident_travail(serializer.instance)

    def perform_update(self, serializer):
        """YHIRE10 — toute mise à jour de l'AT (prolongation/retrait de
        l'arrêt) resynchronise l'absence liée (idempotent : même ligne
        étendue, jamais de doublon ; arrêt retiré → absence annulée)."""
        accident = serializer.save()
        services.synchroniser_absence_accident_travail(accident)

    def list(self, request, *args, **kwargs):
        """Liste paginée OU export CSV de la déclaration CNSS (``?export=csv``).

        On garde ``?export=`` (et NON ``?format=``, réservé par DRF et qui
        renverrait un 404) comme déclencheur d'export.
        """
        if (request.query_params.get('export') or '').lower() == 'csv':
            return self._export_cnss(request)
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='export-cnss')
    def export_cnss(self, request):
        """Export CSV des déclarations d'accident du travail CNSS (FG181)."""
        return self._export_cnss(request)

    def _export_cnss(self, request):
        """Construit le CSV de déclaration CNSS, scopé société + filtré.

        Colonnes = champs d'une déclaration d'accident du travail à la CNSS :
        référence interne, matricule + identité + CIN du blessé, date et lieu
        de l'accident, gravité, arrêt de travail et nombre de jours, état de la
        déclaration CNSS + sa date, statut du dossier et description.
        """
        import csv

        from django.http import HttpResponse

        rows = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            'attachment; filename="declaration-accidents-cnss.csv"')
        # BOM UTF-8 pour qu'Excel ouvre correctement les accents.
        response.write('﻿')
        writer = csv.writer(response)
        writer.writerow([
            'Reference', 'Matricule', 'Nom', 'Prenom', 'CIN',
            'Date accident', 'Lieu', 'Gravite',
            'Arret travail', 'Jours arret',
            'Declare CNSS', 'Date declaration CNSS',
            'Statut', 'Description',
        ])
        for acc in rows:
            emp = acc.employe
            writer.writerow([
                acc.reference,
                emp.matricule,
                emp.nom,
                emp.prenom,
                getattr(emp, 'cin', '') or '',
                acc.date_accident.isoformat() if acc.date_accident else '',
                acc.lieu,
                acc.get_gravite_display(),
                'Oui' if acc.arret_travail else 'Non',
                acc.nb_jours_arret,
                'Oui' if acc.declare_cnss else 'Non',
                acc.date_declaration_cnss.isoformat()
                if acc.date_declaration_cnss else '',
                acc.get_statut_display(),
                acc.description,
            ])
        return response


class PresquAccidentViewSet(_RhBaseViewSet):
    """Registre des presqu'accidents / near-miss (FG182) — saisie rapide terrain.

    Société scopée + Administrateur/Responsable. Pensé pour une SAISIE RAPIDE
    sur le terrain : on remonte vite un événement à risque qui n'a pas blessé,
    pour piloter la prévention de façon proactive. Plus léger que l'accident du
    travail (FG181) : pas de blessé, pas d'arrêt, pas de déclaration CNSS.

    ``company``, ``reference`` (``NM-YYYYMM-NNNN``, race-safe — jamais
    ``count()+1``) ET ``declare_par`` (l'utilisateur qui remonte) sont posées
    CÔTÉ SERVEUR ; jamais lues du corps de requête.

    Filtres : ``?gravite=faible|moyenne|elevee``, ``?statut=ouvert|traite``.
    ``?debut=`` / ``?fin=`` bornent la date de constat. Recherche : référence,
    lieu, chantier.

    Action :
    * ``GET .../stats/`` — synthèse par gravité potentielle (total, ouverts,
      ventilation par gravité), scopée société + bornée comme la liste
      (``?debut=`` / ``?fin=`` / ``?statut=``).
    """
    queryset = PresquAccident.objects.select_related('declare_par').all()
    serializer_class = PresquAccidentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'lieu', 'chantier_id']
    ordering_fields = [
        'date_constat', 'gravite_potentielle', 'statut',
        'reference', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        gravite = self.request.query_params.get('gravite')
        if gravite:
            qs = qs.filter(gravite_potentielle=gravite)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        debut = self._parse_date(self.request.query_params.get('debut'))
        if debut:
            qs = qs.filter(date_constat__gte=debut)
        fin = self._parse_date(self.request.query_params.get('fin'))
        if fin:
            qs = qs.filter(date_constat__lte=fin)
        return qs

    @staticmethod
    def _parse_date(raw):
        if not raw:
            return None
        from datetime import datetime
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def perform_create(self, serializer):
        """Company + reference (race-safe) + declare_par posées côté serveur."""
        services.creer_presqu_accident(
            serializer, self.request.user.company, self.request.user)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Synthèse des presqu'accidents par gravité potentielle (FG182)."""
        debut = self._parse_date(request.query_params.get('debut'))
        fin = self._parse_date(request.query_params.get('fin'))
        statut = request.query_params.get('statut') or None
        data = selectors.stats_presqu_accidents(
            request.user.company, date_debut=debut, date_fin=fin,
            statut=statut)
        return Response(data)


class CauserieSecuriteViewSet(_RhBaseViewSet):
    """Causeries sécurité / toolbox talks (FG183) — le quart d'heure sécurité.

    Société scopée + Administrateur/Responsable. Enregistre un briefing sécurité
    court tenu AVANT chantier : thème, date, chantier (référence chaîne),
    animateur (employé qui mène), lieu/notes, et la liste des participants avec
    leur émargement individuel. ``company`` est posée CÔTÉ SERVEUR (jamais lue du
    corps) ; ``animateur`` et chaque ``participant`` doivent appartenir à la
    même société.

    Filtres : ``?chantier=<ref>``, ``?animateur=<id>``. ``?debut=`` / ``?fin=``
    bornent la date. Recherche : thème, lieu, chantier.

    Action :
    * ``POST .../{id}/emarger/`` — corps ``participant=<id>`` (ou
      ``participant_id``) : marque ce participant comme ayant émargé (présence
      signée), horodatage posé côté serveur. Le participant doit déjà figurer
      sur la feuille de la causerie.
    """
    queryset = CauserieSecurite.objects.select_related('animateur') \
        .prefetch_related('participants__participant').all()
    serializer_class = CauserieSecuriteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['theme', 'lieu', 'chantier_id']
    ordering_fields = ['date_causerie', 'theme', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        chantier = self.request.query_params.get('chantier')
        if chantier:
            qs = qs.filter(chantier_id=chantier)
        animateur = self.request.query_params.get('animateur')
        if animateur:
            qs = qs.filter(animateur_id=animateur)
        debut = self._parse_date(self.request.query_params.get('debut'))
        if debut:
            qs = qs.filter(date_causerie__gte=debut)
        fin = self._parse_date(self.request.query_params.get('fin'))
        if fin:
            qs = qs.filter(date_causerie__lte=fin)
        return qs

    @staticmethod
    def _parse_date(raw):
        if not raw:
            return None
        from datetime import datetime
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def perform_create(self, serializer):
        """Company posée côté serveur ; FK validés via le sérialiseur."""
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='emarger')
    def emarger(self, request, pk=None):
        """Émargement d'un participant à la causerie (FG183) — présence signée.

        Corps : ``participant`` (ou ``participant_id``) = l'id du
        ``DossierEmploye`` qui signe. Le participant doit DÉJÀ figurer sur la
        feuille de la causerie (sinon 400). Marque sa ligne ``emarge=True`` +
        ``emarge_le`` (horodatage posé CÔTÉ SERVEUR). La société est garantie par
        ``get_object`` ; l'horodatage n'est jamais lu du corps. Idempotent : ré-
        émarger renvoie la même ligne sans dupliquer.
        """
        causerie = self.get_object()
        participant_id = request.data.get('participant') \
            or request.data.get('participant_id')
        if not participant_id:
            return Response(
                {'detail': 'Le champ « participant » est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ligne = causerie.participants.get(participant_id=participant_id)
        except CauserieParticipant.DoesNotExist:
            return Response(
                {'detail':
                 "Ce participant ne figure pas sur cette causerie."},
                status=status.HTTP_400_BAD_REQUEST)
        if not ligne.emarge:
            ligne.emarge = True
            ligne.present = True
            ligne.emarge_le = timezone.now()
            ligne.save(update_fields=['emarge', 'present', 'emarge_le'])
        return Response(
            CauserieParticipantSerializer(ligne).data,
            status=status.HTTP_200_OK)


class AnalyseRisquesChantierViewSet(_RhBaseViewSet):
    """Analyses de risques chantier / plans de prévention (FG184) — AVANT travaux.

    Société scopée + Administrateur/Responsable. Enregistre le plan de
    prévention d'un chantier établi AVANT le démarrage : chantier (référence
    chaîne), date, rédacteur (employé qui mène l'analyse), lieu/notes, statut
    (brouillon → validé), et la liste des risques identifiés (danger, gravité,
    probabilité, niveau, mesure de prévention). C'est distinct de la check-list
    par intervention (F18) et de la causerie du jour (FG183) : on évalue ici les
    risques EN AMONT. ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``redacteur`` doit appartenir à la même société, et ``company`` est propagée
    aux lignes de risque.

    Filtres : ``?chantier=<ref>``, ``?redacteur=<id>``, ``?statut=brouillon|
    valide``. ``?debut=`` / ``?fin=`` bornent la date. Recherche : lieu,
    chantier, danger d'une ligne.

    Action :
    * ``POST .../{id}/valider/`` — passe l'analyse en ``statut=valide`` (le plan
      de prévention est arrêté). Idempotent.
    """
    queryset = AnalyseRisquesChantier.objects.select_related('redacteur') \
        .prefetch_related('risques').all()
    serializer_class = AnalyseRisquesChantierSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['lieu', 'chantier_id', 'risques__danger']
    ordering_fields = ['date_analyse', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        chantier = self.request.query_params.get('chantier')
        if chantier:
            qs = qs.filter(chantier_id=chantier)
        redacteur = self.request.query_params.get('redacteur')
        if redacteur:
            qs = qs.filter(redacteur_id=redacteur)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        debut = self._parse_date(self.request.query_params.get('debut'))
        if debut:
            qs = qs.filter(date_analyse__gte=debut)
        fin = self._parse_date(self.request.query_params.get('fin'))
        if fin:
            qs = qs.filter(date_analyse__lte=fin)
        return qs.distinct()

    @staticmethod
    def _parse_date(raw):
        if not raw:
            return None
        from datetime import datetime
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def perform_create(self, serializer):
        """Company posée côté serveur ; FK validés via le sérialiseur."""
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valide le plan de prévention (FG184) — passe en ``statut=valide``.

        Le plan de prévention est arrêté : ``statut`` → ``valide`` (horodatage
        de modification posé côté serveur). La société est garantie par
        ``get_object`` (un autre tenant reçoit 404). Idempotent : revalider
        renvoie la même analyse sans erreur.
        """
        analyse = self.get_object()
        if analyse.statut != AnalyseRisquesChantier.Statut.VALIDE:
            analyse.statut = AnalyseRisquesChantier.Statut.VALIDE
            analyse.save(update_fields=['statut', 'date_modification'])
        return Response(
            self.get_serializer(analyse).data, status=status.HTTP_200_OK)


class SessionFormationViewSet(_RhBaseViewSet):
    """Sessions de formation (FG187) — gestion de la formation des équipes.

    Société scopée + Administrateur/Responsable. Enregistre une session de
    formation (interne / externe), son organisme, ses dates, son lieu, son
    coût, la compétence visée et la liste des participants inscrits (présence,
    résultat). ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``competence_visee`` et chaque ``participant`` doivent appartenir à la même
    société, et ``company`` est propagée aux inscriptions.

    Filtres : ``?type=interne|externe``, ``?statut=planifiee|realisee|annulee``,
    ``?competence=<id>``. ``?debut=`` / ``?fin=`` bornent la date de début.
    Recherche : intitulé, organisme, lieu.

    Action :
    * ``POST .../{id}/marquer-realisee/`` — passe la session en
      ``statut=realisee``. Si une ``competence_visee`` est définie, met à jour
      (upsert) le niveau de compétence des participants PRÉSENTS dans la
      matrice (``CompetenceEmploye``, même société). ``?niveau=`` (0–4, défaut
      3 « Confirmé ») fixe le niveau attribué. Idempotent.
    """
    queryset = SessionFormation.objects.select_related('competence_visee') \
        .prefetch_related('inscriptions').all()
    serializer_class = SessionFormationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['intitule', 'organisme', 'lieu']
    ordering_fields = ['date_debut', 'statut', 'cout', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        type_param = self.request.query_params.get('type')
        if type_param:
            qs = qs.filter(type=type_param)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        competence = self.request.query_params.get('competence')
        if competence:
            qs = qs.filter(competence_visee_id=competence)
        debut = self._parse_date(self.request.query_params.get('debut'))
        if debut:
            qs = qs.filter(date_debut__gte=debut)
        fin = self._parse_date(self.request.query_params.get('fin'))
        if fin:
            qs = qs.filter(date_debut__lte=fin)
        return qs.distinct()

    @staticmethod
    def _parse_date(raw):
        if not raw:
            return None
        from datetime import datetime
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    @action(detail=True, methods=['post'], url_path='marquer-realisee')
    def marquer_realisee(self, request, pk=None):
        """Marque la session RÉALISÉE et alimente la matrice de compétences.

        Passe ``statut`` → ``realisee`` (horodatage côté serveur). Si la
        session vise une ``competence_visee``, on met à jour (upsert) le niveau
        de chaque participant PRÉSENT dans ``CompetenceEmploye`` (même société,
        évalué par l'utilisateur courant) — c'est le lien formation →
        compétences. ``?niveau=`` (0–4, défaut 3) fixe le niveau attribué. La
        société est garantie par ``get_object`` (un autre tenant reçoit 404).
        Idempotent.
        """
        session = self.get_object()
        if session.statut != SessionFormation.Statut.REALISEE:
            session.statut = SessionFormation.Statut.REALISEE
            session.save(update_fields=['statut', 'date_modification'])

        # Upsert de la matrice de compétences pour les présents (gardé : ne
        # fait rien sans compétence visée).
        if session.competence_visee_id:
            try:
                niveau = int(request.query_params.get('niveau', 3))
            except (TypeError, ValueError):
                niveau = 3
            niveau = max(0, min(4, niveau))
            now = timezone.now()
            for inscr in session.inscriptions.filter(present=True):
                # ZRH10 — passe par le point d'entrée unique (historise le
                # changement de niveau, source='formation').
                services.enregistrer_niveau_competence(
                    inscr.participant, session.competence_visee_id, niveau,
                    company=session.company, evalue_par=request.user,
                    evalue_le=now, source='formation')
        return Response(
            self.get_serializer(session).data, status=status.HTTP_200_OK)


class BesoinFormationViewSet(_RhBaseViewSet):
    """Besoins de formation (FG188) — plan de formation par employé.

    Société scopée + Administrateur/Responsable. Enregistre un BESOIN DE
    FORMATION repéré pour un employé : thème, priorité, échéance souhaitée,
    drapeau d'obligation réglementaire (OFPPT / CSF) + son type, statut
    (identifié → planifié → satisfait) et éventuelle session de formation qui
    le couvre. ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``employe`` et ``session_liee`` doivent appartenir à la même société.

    Filtres : ``?employe=<id>``, ``?statut=identifie|planifie|satisfait``,
    ``?priorite=basse|moyenne|haute``, ``?obligation=1`` (besoins réglementaires
    uniquement), ``?type_obligation=ofppt|csf|autre``. Recherche : thème.

    Action :
    * ``POST .../{id}/satisfaire/`` — bascule le besoin en ``statut=satisfait``.
      Si une ``session_liee`` est posée, elle doit être RÉALISÉE (sinon 400 :
      on ne satisfait pas un besoin sur une session non tenue). Idempotent.
    """
    queryset = BesoinFormation.objects.select_related(
        'employe', 'session_liee').all()
    serializer_class = BesoinFormationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['theme']
    ordering_fields = ['priorite', 'echeance', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        priorite = self.request.query_params.get('priorite')
        if priorite:
            qs = qs.filter(priorite=priorite)
        type_obligation = self.request.query_params.get('type_obligation')
        if type_obligation:
            qs = qs.filter(type_obligation=type_obligation)
        obligation = self.request.query_params.get('obligation')
        if obligation in ('1', 'true', 'True'):
            qs = qs.filter(obligation_reglementaire=True)
        return qs

    @action(detail=True, methods=['post'], url_path='satisfaire')
    def satisfaire(self, request, pk=None):
        """Marque le besoin SATISFAIT.

        Passe ``statut`` → ``satisfait``. Garde-fou : si une ``session_liee``
        est posée, elle doit être RÉALISÉE (sinon 400) — on ne satisfait pas un
        besoin via une session non tenue. La société est garantie par
        ``get_object`` (un autre tenant reçoit 404). Idempotent.
        """
        besoin = self.get_object()
        session = besoin.session_liee
        if session is not None and \
                session.statut != SessionFormation.Statut.REALISEE:
            return Response(
                {'session_liee':
                    'La session liée doit être réalisée pour satisfaire '
                    'le besoin.'},
                status=status.HTTP_400_BAD_REQUEST)
        if besoin.statut != BesoinFormation.Statut.SATISFAIT:
            besoin.statut = BesoinFormation.Statut.SATISFAIT
            besoin.save(update_fields=['statut', 'date_modification'])
        return Response(
            self.get_serializer(besoin).data, status=status.HTTP_200_OK)


class QuizFormationViewSet(_RhBaseViewSet):
    """XRH34 — quiz d'évaluation de formation (eLearning léger, gestion RH).

    Société scopée + Administrateur/Responsable. Porte le CONTENU (questions
    + bonnes réponses, seuil de réussite, validité de certification, liens
    optionnels compétence/type d'habilitation). Un employé passe un quiz via
    le portail (``PortailSelfServiceViewSet``), jamais directement ici (les
    bonnes réponses ne doivent jamais atteindre son écran).

    Filtres : ``?actif=1``, ``?competence=<id>``, ``?habilitation_type=...``.
    """
    queryset = QuizFormation.objects.select_related('competence').all()
    serializer_class = QuizFormationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['intitule']
    ordering_fields = ['intitule', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        competence = self.request.query_params.get('competence')
        if competence:
            qs = qs.filter(competence_id=competence)
        habilitation_type = self.request.query_params.get('habilitation_type')
        if habilitation_type:
            qs = qs.filter(habilitation_type=habilitation_type)
        return qs


class TentativeQuizViewSet(_RhBaseViewSet):
    """XRH34 — tentatives de quiz (consultation gestion RH — un employé
    consulte SES tentatives via le portail, pas ici).

    Lecture seule côté API générale (la création passe TOUJOURS par
    ``services.passer_tentative_quiz``, jamais par un POST direct qui
    accepterait un ``score``/``reussi`` côté client).

    Filtres : ``?employe=<id>``, ``?quiz=<id>``, ``?reussi=1``.

    Action :
    * ``GET .../{id}/attestation/`` — attestation PDF de réussite
      (``apps.rh.pdf_attestation``, renderer RH dédié — JAMAIS ``/proposal``).
      404 si la tentative n'est pas réussie.
    """
    http_method_names = ['get', 'head', 'options']
    queryset = TentativeQuiz.objects.select_related('quiz', 'employe').all()
    serializer_class = TentativeQuizSerializer
    ordering_fields = ['date_creation', 'score']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        quiz = self.request.query_params.get('quiz')
        if quiz:
            qs = qs.filter(quiz_id=quiz)
        reussi = self.request.query_params.get('reussi')
        if reussi in ('1', 'true', 'True'):
            qs = qs.filter(reussi=True)
        return qs

    @action(detail=True, methods=['get'], url_path='attestation')
    def attestation(self, request, pk=None):
        """PDF d'attestation de réussite — 404 si non réussie."""
        tentative = self.get_object()
        if not tentative.reussi:
            return Response(
                {'detail': 'Aucune attestation : tentative non réussie.'},
                status=status.HTTP_404_NOT_FOUND)
        from django.http import HttpResponse

        from .pdf_attestation import render_attestation_reussite_pdf

        try:
            pdf_bytes = render_attestation_reussite_pdf(tentative)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="attestation-quiz-{tentative.pk}.pdf"')
        return response


class BadgeReconnaissanceViewSet(_RhBaseViewSet):
    """Catalogue des badges de reconnaissance interne (ZRH14).

    Société scopée + Administrateur/Responsable (gate d'écriture du
    catalogue). La LECTURE (liste/détail) est ouverte à TOUT employé
    authentifié de la société : la reconnaissance pair-à-pair (ZRH14)
    suppose que chacun puisse consulter le catalogue (nom/icône/nombre
    d'attributions) pour choisir un badge à attribuer — seule
    l'écriture (créer/modifier/supprimer un badge) reste réservée au
    palier Administrateur/Responsable. ``company`` posée côté serveur.
    """
    queryset = BadgeReconnaissance.objects.all()
    serializer_class = BadgeReconnaissanceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'date_creation']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class AttributionBadgeViewSet(_RhBaseViewSet):
    """Attribution de badges de reconnaissance entre collègues (ZRH14).

    Accessible en LECTURE+CRÉATION à TOUT employé authentifié de la société
    (pas seulement Administrateur/Responsable) : la reconnaissance
    pair-à-pair est le point de la fonctionnalité. ``company`` et
    ``attribue_par`` sont posés côté serveur. Auto-attribution refusée
    (400) : ``beneficiaire`` ne peut pas être le dossier employé de
    l'auteur de la requête.
    """
    queryset = AttributionBadge.objects.select_related(
        'badge', 'beneficiaire').all()
    serializer_class = AttributionBadgeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']

    def get_permissions(self):
        return [IsAnyRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        beneficiaire = self.request.query_params.get('beneficiaire')
        if beneficiaire:
            qs = qs.filter(beneficiaire_id=beneficiaire)
        return qs

    def perform_create(self, serializer):
        beneficiaire = serializer.validated_data.get('beneficiaire')
        dossier_auteur = DossierEmploye.objects.filter(
            company=self.request.user.company,
            user=self.request.user).first()
        if (dossier_auteur is not None and beneficiaire is not None
                and beneficiaire.id == dossier_auteur.id):
            raise serializers.ValidationError(
                {'beneficiaire': "Impossible de s'attribuer un badge "
                                 "à soi-même."})
        serializer.save(
            company=self.request.user.company,
            attribue_par=self.request.user)


class OuverturePosteViewSet(_RhBaseViewSet):
    """Ouvertures de poste / postes ouverts (FG189) — recrutement ATS-lite.

    Société scopée + Administrateur/Responsable. Enregistre un POSTE OUVERT au
    recrutement : intitulé, poste de référence (``rh.Poste``) et département
    optionnels, description du profil, nombre de postes à pourvoir, statut
    (ouvert → pourvu / clos / annulé) et dates d'ouverture / cible. La liste
    imbriquée ``candidatures`` est exposée en lecture. ``company`` est posée
    CÔTÉ SERVEUR (jamais lue du corps) ; ``poste_ref`` et ``departement``
    doivent appartenir à la même société.

    Filtres : ``?statut=ouvert|pourvu|clos|annule``, ``?departement=<id>``.
    Recherche : intitulé. Tri : date de création, statut.
    """
    queryset = OuverturePoste.objects.select_related(
        'poste_ref', 'departement').prefetch_related('candidatures').all()
    serializer_class = OuverturePosteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['intitule', 'description']
    ordering_fields = ['date_creation', 'statut', 'date_cible']

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        departement = self.request.query_params.get('departement')
        if departement:
            qs = qs.filter(departement_id=departement)
        return qs.distinct()

    @action(detail=True, methods=['post'])
    def soumettre(self, request, pk=None):
        """YHIRE14 — soumet l'ouverture BROUILLON à approbation."""
        ouverture = self.get_object()
        try:
            services.soumettre_ouverture(ouverture, demandeur=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(ouverture).data)

    @action(detail=True, methods=['post'])
    def approuver(self, request, pk=None):
        """YHIRE14 — approuve l'ouverture (SoD : approbateur != demandeur)."""
        ouverture = self.get_object()
        try:
            services.approuver_ouverture(ouverture, approbateur=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(ouverture).data)

    @action(detail=True, methods=['post'])
    def refuser(self, request, pk=None):
        """YHIRE14 — refuse l'ouverture (SoD : approbateur != demandeur)."""
        ouverture = self.get_object()
        motif = request.data.get('motif_refus', '')
        try:
            services.refuser_ouverture(
                ouverture, approbateur=request.user, motif_refus=motif)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(ouverture).data)


class CandidatureViewSet(_RhBaseViewSet):
    """Candidatures (FG189) — pipeline de recrutement ATS-lite.

    Société scopée + Administrateur/Responsable. Enregistre un CANDIDAT
    postulant à une ``ouverture`` (de la même société) : nom, e-mail,
    téléphone, CV, source, note et son ``etape`` dans le pipeline (reçu →
    présélection → entretien → offre → embauché / rejeté). ``company`` est posée
    CÔTÉ SERVEUR (jamais lue du corps).

    Filtres : ``?ouverture=<id>``, ``?etape=recu|preselection|entretien|offre|
    embauche|rejete``. Recherche : nom, e-mail. Accepte le multipart pour le CV.

    Action :
    * ``POST .../{id}/embaucher/`` — convertit la candidature en
      ``DossierEmploye`` (même société), lie ``employe_cree``, passe l'étape à
      ``embauche`` et bascule l'ouverture en ``pourvu`` quand elle est
      pourvue. ``matricule`` / ``type_contrat`` / ``date_embauche`` / ``poste``
      sont renseignables. Idempotent (ne recrée jamais un dossier déjà lié).
    """
    queryset = Candidature.objects.select_related(
        'ouverture', 'employe_cree').all()
    serializer_class = CandidatureSerializer
    parser_classes = [JSONParser, MultiPartParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'email']
    ordering_fields = ['date_creation', 'etape', 'date_candidature']

    def get_queryset(self):
        qs = super().get_queryset()
        ouverture = self.request.query_params.get('ouverture')
        if ouverture:
            qs = qs.filter(ouverture_id=ouverture)
        etape = self.request.query_params.get('etape')
        if etape:
            qs = qs.filter(etape=etape)
        return qs

    def perform_update(self, serializer):
        """XRH18 — journalise automatiquement une transition d'étape.
        XRH19 — envoie l'email automatique du gabarit actif de la nouvelle
        étape (best-effort, jamais bloquant)."""
        old_etape = serializer.instance.etape
        candidature = serializer.save()
        if old_etape != candidature.etape:
            CandidatureActivity.objects.create(
                company=candidature.company, candidature=candidature,
                auteur=self.request.user,
                type=CandidatureActivity.Kind.LOG, field='etape',
                old_value=old_etape, new_value=candidature.etape)
            services.envoyer_email_transition(candidature)

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """XRH18 — timeline chatter de la candidature (auto + notes)."""
        candidature = self.get_object()
        return Response(CandidatureActivitySerializer(
            candidature.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter')
    def noter(self, request, pk=None):
        """XRH18 — note manuelle sur le chatter (auteur posé côté serveur)."""
        candidature = self.get_object()
        message = (request.data.get('message') or '').strip()
        if not message:
            return Response({'message': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = CandidatureActivity.objects.create(
            company=candidature.company, candidature=candidature,
            auteur=request.user, type=CandidatureActivity.Kind.NOTE,
            message=message)
        return Response(CandidatureActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='check-duplicates')
    def check_duplicates(self, request):
        """XRH18 — contrôle PRÉ-CRÉATION (et édition) : un téléphone/email
        saisi correspond-il déjà à une candidature de la société ?
        Avertissement NON bloquant (pattern CRM ``check-duplicates``).
        ``?exclude=<id>`` retire la candidature en cours d'édition."""
        telephone = request.query_params.get('telephone')
        email = request.query_params.get('email')
        exclude = request.query_params.get('exclude')
        exclude_pk = exclude if (exclude or '').isdigit() else None
        doublons = services.candidatures_doublons(
            request.user.company, telephone=telephone, email=email,
            exclude_pk=exclude_pk)
        return Response([
            {'id': d.id, 'nom': d.nom, 'email': d.email,
             'telephone': d.telephone, 'etape': d.etape}
            for d in doublons
        ])

    @action(detail=True, methods=['post'], url_path='fusionner')
    def fusionner(self, request, pk=None):
        """XRH18 — fusionne une candidature SOURCE dans CETTE candidature
        (cible). Corps : ``source`` (id, même société)."""
        cible = self.get_object()
        source = Candidature.objects.filter(
            company=request.user.company,
            pk=request.data.get('source')).first()
        if source is None:
            return Response(
                {'detail': 'Candidature source introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            services.fusionner_candidatures(
                cible, source, auteur=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        cible.refresh_from_db()
        return Response(self.get_serializer(cible).data)

    @action(detail=True, methods=['post'], url_path='embaucher')
    def embaucher(self, request, pk=None):
        """Embauche le candidat : crée son ``DossierEmploye`` et le lie.

        Délègue au service ``apps.rh.services.embaucher`` (transaction atomique,
        idempotent). La société est garantie par ``get_object`` (un autre tenant
        reçoit 404). Renvoie la candidature mise à jour (avec ``employe_cree``).
        """
        candidature = self.get_object()
        in_ser = EmbaucherSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        kwargs = {k: v for k, v in in_ser.validated_data.items()
                  if v not in (None, '')}
        services.embaucher(candidature, **kwargs)
        candidature.refresh_from_db()
        return Response(
            self.get_serializer(candidature).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='comparatif')
    def comparatif(self, request, pk=None):
        """XRH17 — comparatif des candidats de la MÊME ouverture (moyennes
        des notes d'entretien, classées décroissant)."""
        candidature = self.get_object()
        return Response(
            selectors.comparatif_candidats(
                request.user.company, candidature.ouverture_id))

    @action(detail=True, methods=['post'], url_path='mettre-au-vivier')
    def mettre_au_vivier(self, request, pk=None):
        """XRH21 — met la candidature au vivier (``vivier=True``). Corps
        optionnel : ``tags_vivier`` (chaîne, remplace les tags existants si
        fournie)."""
        candidature = self.get_object()
        candidature.vivier = True
        update_fields = ['vivier', 'date_modification']
        if 'tags_vivier' in request.data:
            candidature.tags_vivier = request.data.get('tags_vivier', '')
            update_fields.append('tags_vivier')
        candidature.save(update_fields=update_fields)
        return Response(self.get_serializer(candidature).data)

    @action(detail=False, methods=['get'], url_path='vivier')
    def vivier(self, request):
        """XRH21 — recherche company-scopée dans le vivier (``?q=`` nom/
        email/tags/note, ``?tag=`` filtre exact sur un tag)."""
        qs = Candidature.objects.filter(
            company=request.user.company, vivier=True)
        q = request.query_params.get('q')
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(nom__icontains=q) | Q(email__icontains=q)
                | Q(tags_vivier__icontains=q) | Q(note__icontains=q))
        tag = request.query_params.get('tag')
        if tag:
            qs = qs.filter(tags_vivier__icontains=tag)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='rattacher')
    def rattacher(self, request, pk=None):
        """XRH21 — clone cette candidature du vivier vers une NOUVELLE
        ``OuverturePoste`` (corps : ``ouverture``, id de la même société).
        CV et historique conservés, lien vers l'originale."""
        candidature = self.get_object()
        ouverture = OuverturePoste.objects.filter(
            company=request.user.company,
            pk=request.data.get('ouverture')).first()
        if ouverture is None:
            return Response(
                {'detail': 'Ouverture introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            nouvelle = services.rattacher_depuis_vivier(
                candidature, ouverture)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(nouvelle).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='parser-cv')
    def parser_cv(self, request, pk=None):
        """XRH23 — OCR le CV attaché et pré-remplit les champs VIDES
        (nom/email/téléphone) + suggère des tags vivier. Sans
        ``ZHIPU_API_KEY`` configurée, répond 503 douce (message explicite,
        aucune exception) — les champs déjà saisis ne sont jamais écrasés."""
        candidature = self.get_object()
        try:
            resultat = services.parser_cv(candidature)
        except services.CvParsingUnavailable as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        candidature.refresh_from_db()
        return Response({
            'candidature': self.get_serializer(candidature).data,
            'champs_remplis': resultat['champs_remplis'],
            'tags_suggeres': resultat['tags_suggeres'],
        })


class EntretienRecrutementViewSet(_RhBaseViewSet):
    """Entretiens de recrutement (XRH17) — planification + évaluation.

    Société scopée + Administrateur/Responsable. ``company`` posée CÔTÉ
    SERVEUR ; ``candidature`` doit appartenir à la société. Filtre
    ``?candidature=<id>``.
    """
    queryset = EntretienRecrutement.objects.select_related(
        'candidature').prefetch_related('evaluateurs', 'notes').all()
    serializer_class = EntretienRecrutementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_heure', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        candidature = self.request.query_params.get('candidature')
        if candidature:
            qs = qs.filter(candidature_id=candidature)
        return qs

    @action(detail=True, methods=['post'], url_path='noter')
    def noter(self, request, pk=None):
        """Note l'entretien pour l'évaluateur APPELANT (posé côté serveur).
        Une seule note par (entretien, évaluateur) — un 2e appel met à jour."""
        entretien = self.get_object()
        note, _ = NoteEntretien.objects.update_or_create(
            entretien=entretien, evaluateur=request.user,
            defaults={
                'company': request.user.company,
                'notes_criteres': request.data.get('notes_criteres', {}),
                'commentaire': request.data.get('commentaire', ''),
                'avis': request.data.get('avis', NoteEntretien.Avis.RESERVE),
            })
        return Response(
            NoteEntretienSerializer(note).data, status=status.HTTP_201_CREATED)


class PromesseEmbaucheViewSet(_RhBaseViewSet):
    """Promesses d'embauche / lettres d'offre (XRH20) — administration RH.

    Société scopée + Administrateur/Responsable. ``company`` posée CÔTÉ
    SERVEUR ; ``candidature`` doit appartenir à la société.

    Action :
    * ``GET .../{id}/pdf/`` — PDF interne (accès RH, sans jeton).
    """
    queryset = PromesseEmbauche.objects.select_related('candidature').all()
    serializer_class = PromesseEmbaucheSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'statut']

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        from django.http import HttpResponse

        from .pdf import render_promesse_embauche_pdf

        promesse = self.get_object()
        pdf_bytes = render_promesse_embauche_pdf(promesse)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            'inline; filename="promesse_embauche.pdf"')
        return resp


class GabaritEmailRecrutementViewSet(_RhBaseViewSet):
    """Gabarits d'email automatique par étape du pipeline (XRH19).

    Société scopée + Administrateur/Responsable. ``company`` posée CÔTÉ
    SERVEUR. Filtre ``?etape=``.
    """
    queryset = GabaritEmailRecrutement.objects.all()
    serializer_class = GabaritEmailRecrutementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['etape', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        etape = self.request.query_params.get('etape')
        if etape:
            qs = qs.filter(etape=etape)
        return qs


class ModeleEvaluationViewSet(_RhBaseViewSet):
    """Gabarits de questions d'évaluation réutilisables (ZRH7).

    Société scopée + Administrateur/Responsable. ``departement``/``poste_ref``
    ciblent optionnellement le modèle (vide/vide = modèle par défaut société).
    ``company`` posée CÔTÉ SERVEUR (jamais lue du corps).

    Filtres : ``?departement=<id>``, ``?poste_ref=<id>``, ``?actif=0|1``.
    """
    queryset = ModeleEvaluation.objects.select_related(
        'departement', 'poste_ref').all()
    serializer_class = ModeleEvaluationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        departement = self.request.query_params.get('departement')
        if departement:
            qs = qs.filter(departement_id=departement)
        poste_ref = self.request.query_params.get('poste_ref')
        if poste_ref:
            qs = qs.filter(poste_ref_id=poste_ref)
        actif = self.request.query_params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class CampagneEvaluationViewSet(_RhBaseViewSet):
    """Campagnes d'appréciation annuelle (FG190) — entretiens & évaluations.

    Société scopée + Administrateur/Responsable. Enregistre une campagne
    d'appréciation (le cycle d'entretiens annuels) : intitulé, année, période,
    dates, statut (ouverte → clôturée), description ; la liste imbriquée des
    entretiens (``evaluations``) est exposée en lecture seule (chaque entretien
    se gère via son propre endpoint). ``company`` est posée CÔTÉ SERVEUR
    (jamais lue du corps). C'est une appréciation RH — DISTINCTE des objectifs
    commerciaux de vente (FG39).

    Filtres : ``?annee=<n>``, ``?statut=ouverte|cloturee``. Recherche :
    intitulé, période, description.

    Action :
    * ``POST .../{id}/cloturer/`` — passe la campagne en ``statut=cloturee``.
      Idempotent.
    """
    queryset = CampagneEvaluation.objects.prefetch_related(
        'evaluations__objectifs',
        'evaluations__employe', 'evaluations__evaluateur').all()
    serializer_class = CampagneEvaluationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['intitule', 'periode', 'description']
    ordering_fields = ['annee', 'statut', 'date_debut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        annee = self.request.query_params.get('annee')
        if annee:
            qs = qs.filter(annee=annee)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur."""
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='cloturer')
    def cloturer(self, request, pk=None):
        """Clôture la campagne (FG190) — passe en ``statut=cloturee``.

        La société est garantie par ``get_object`` (un autre tenant reçoit
        404). Idempotent : reclôturer renvoie la même campagne sans erreur.
        """
        campagne = self.get_object()
        if campagne.statut != CampagneEvaluation.Statut.CLOTUREE:
            campagne.statut = CampagneEvaluation.Statut.CLOTUREE
            campagne.save(update_fields=['statut', 'date_modification'])
        return Response(
            self.get_serializer(campagne).data, status=status.HTTP_200_OK)


class EvaluationEmployeViewSet(_RhBaseViewSet):
    """Entretiens annuels d'évaluation (FG190) — appréciation par collaborateur.

    Société scopée + Administrateur/Responsable. Enregistre l'entretien
    d'évaluation d'un collaborateur dans une campagne : campagne, employé
    évalué, évaluateur (manager), date d'entretien, note globale (1–5),
    synthèse, statut (planifié → réalisé → validé) et la liste imbriquée des
    objectifs individuels (libellé, pondération, cible, atteinte, note).
    ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps) ; ``campagne`` /
    ``employe`` / ``evaluateur`` doivent appartenir à la même société, et
    ``company`` est propagée aux objectifs. Le couple (campagne, employe) est
    unique.

    Filtres : ``?campagne=<id>``, ``?employe=<id>``, ``?evaluateur=<id>``,
    ``?statut=planifie|realise|valide``. Recherche : synthèse, libellé d'un
    objectif.

    Action :
    * ``POST .../{id}/valider/`` — passe l'entretien en ``statut=valide``.
      Idempotent.
    """
    queryset = EvaluationEmploye.objects.select_related(
        'campagne', 'employe', 'evaluateur').prefetch_related(
        'objectifs').all()
    serializer_class = EvaluationEmployeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['synthese', 'objectifs__libelle']
    ordering_fields = ['date_entretien', 'statut', 'note_globale',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        campagne = self.request.query_params.get('campagne')
        if campagne:
            qs = qs.filter(campagne_id=campagne)
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        evaluateur = self.request.query_params.get('evaluateur')
        if evaluateur:
            qs = qs.filter(evaluateur_id=evaluateur)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs.distinct()

    def perform_create(self, serializer):
        """Company posée côté serveur ; FK validés via le sérialiseur."""
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valide l'entretien (FG190) — passe en ``statut=valide``.

        La société est garantie par ``get_object`` (un autre tenant reçoit
        404). Idempotent : revalider renvoie le même entretien sans erreur
        (les effets de bord XRH26 ne sont déclenchés qu'à la PREMIÈRE
        validation — jamais recréés/renotifiés en boucle).

        XRH26 — si ``issue``/``issue_details`` sont fournis dans le corps, ils
        sont posés AVANT la validation (mêmes garanties FK que le sérialiseur
        générique n'imposent pas ici car ce sont de simples choix bornés).
        À la première validation : ``issue='formation'`` crée un
        ``BesoinFormation`` lié ; ``issue='augmentation_proposee'`` notifie
        (best-effort) les porteurs de ``salaires_voir`` — jamais de montant.
        """
        evaluation = self.get_object()
        issue = request.data.get('issue')
        if issue in dict(EvaluationEmploye.Issue.choices):
            evaluation.issue = issue
        if 'issue_details' in request.data:
            evaluation.issue_details = request.data.get('issue_details') or ''

        deja_validee = evaluation.statut == EvaluationEmploye.Statut.VALIDE
        if not deja_validee:
            evaluation.statut = EvaluationEmploye.Statut.VALIDE
        evaluation.save(update_fields=[
            'statut', 'issue', 'issue_details', 'date_modification'])

        if not deja_validee and evaluation.issue:
            services.traiter_issue_evaluation(evaluation)

        return Response(
            self.get_serializer(evaluation).data, status=status.HTTP_200_OK)


class RetourFeedback360ViewSet(_RhBaseViewSet):
    """Feedback 360° — gestion des invitations (ZRH9).

    Société scopée + Administrateur/Responsable (le RH/manager invite N
    répondants sur une évaluation — ``POST`` crée une ligne NON SOUMISE,
    ``company``/``evaluation``/``repondant`` validés). Le répondant
    lui-même utilise l'endpoint self-service dédié (portail,
    ``mes-feedback360``) pour remplir/soumettre — jamais cette vue de
    gestion, qui ne modifie pas ``reponses``/``commentaire``/``soumis``.
    Filtres : ``?evaluation=``.

    Action :
    * ``GET .../synthese/?evaluation=`` — synthèse agrégée (moyennes par
      critère, retours anonymisés sous le seuil de répondants).
    """
    queryset = RetourFeedback360.objects.select_related(
        'evaluation', 'repondant').all()
    serializer_class = RetourFeedback360Serializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_invitation']

    def get_queryset(self):
        qs = super().get_queryset()
        evaluation = self.request.query_params.get('evaluation')
        if evaluation:
            qs = qs.filter(evaluation_id=evaluation)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'], url_path='synthese')
    def synthese(self, request):
        """Synthèse agrégée des retours SOUMIS d'une évaluation.
        ``?evaluation=`` requis."""
        evaluation_id = request.query_params.get('evaluation')
        evaluation = EvaluationEmploye.objects.filter(
            company=request.user.company, pk=evaluation_id).first()
        if evaluation is None:
            return Response(
                {'detail': "Paramètre 'evaluation' requis/introuvable."},
                status=status.HTTP_404_NOT_FOUND)
        return Response(selectors.synthese_feedback360(evaluation))


class SanctionViewSet(_RhBaseViewSet):
    """Sanctions disciplinaires (FG191) — registre conforme au code du travail.

    Société scopée + Administrateur/Responsable. Enregistre les mesures
    disciplinaires (observation, avertissement, blâme, mise à pied, mutation,
    rétrogradation, licenciement) notifiées à un collaborateur : employé,
    auteur, type, date des faits, date de notification, durée (mise à pied),
    motif, statut (notifiée → contestée → annulée). ``company`` est posée CÔTÉ
    SERVEUR (jamais lue du corps) ; ``employe`` / ``auteur`` doivent appartenir
    à la même société.

    Filtres : ``?employe=<id>``, ``?type_sanction=...``,
    ``?statut=notifiee|contestee|annulee``. Recherche : motif, matricule/nom de
    l'employé.

    Action :
    * ``POST .../{id}/annuler/`` — passe la sanction en ``statut=annulee``.
      Idempotent.
    """
    queryset = Sanction.objects.select_related('employe', 'auteur').all()
    serializer_class = SanctionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['motif', 'employe__matricule', 'employe__nom']
    ordering_fields = ['date_notification', 'date_faits', 'statut',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        type_sanction = self.request.query_params.get('type_sanction')
        if type_sanction:
            qs = qs.filter(type_sanction=type_sanction)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur ; FK validés via le sérialiseur.

        YHIRE7(a) — une sanction créée directement ``NOTIFIEE`` (défaut) avec
        une MISE_A_PIED propage aussitôt son effet (absence non rémunérée).
        """
        sanction = serializer.save(company=self.request.user.company)
        if sanction.statut == Sanction.Statut.NOTIFIEE:
            services.propager_effets_sanction_notification(sanction)

    def perform_update(self, serializer):
        """YHIRE7(a) — si la mise à jour fait TRANSITIONNER la sanction vers
        NOTIFIEE (elle ne l'était pas avant), propage l'effet à ce moment-là
        (une sanction créée en brouillon puis notifiée plus tard)."""
        etait_notifiee = serializer.instance.statut == Sanction.Statut.NOTIFIEE
        sanction = serializer.save()
        if sanction.statut == Sanction.Statut.NOTIFIEE and not etait_notifiee:
            services.propager_effets_sanction_notification(sanction)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """Annule la sanction (FG191) — passe en ``statut=annulee``.

        La société est garantie par ``get_object`` (un autre tenant reçoit
        404). Idempotent : ré-annuler renvoie la même sanction sans erreur.

        YHIRE7(a) — si une MISE_A_PIED avait propagé une absence, l'annulation
        de la sanction (contestation gagnée) retire l'effet (annule
        l'absence liée).
        """
        sanction = self.get_object()
        if sanction.statut != Sanction.Statut.ANNULEE:
            sanction.statut = Sanction.Statut.ANNULEE
            sanction.save(update_fields=['statut', 'date_modification'])
            services.propager_effets_sanction_annulation(sanction)
        return Response(
            self.get_serializer(sanction).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='declencher-sortie')
    def declencher_sortie(self, request, pk=None):
        """YHIRE7(b) — une sanction LICENCIEMENT PROPOSE la sortie de
        l'employé (jamais automatique) : sans ``confirmer: true`` dans le
        corps, renvoie 409 avec les infos pré-remplies pour confirmation ;
        avec confirmation, déclenche ``sortir_employe`` (YHIRE2).

        Corps : ``confirmer`` (bool), ``date_sortie`` (ISO, optionnel —
        défaut ``date_notification`` de la sanction).
        """
        sanction = self.get_object()
        if sanction.type_sanction != Sanction.TypeSanction.LICENCIEMENT:
            return Response(
                {'detail': "Cette action ne s'applique qu'à un licenciement."},
                status=status.HTTP_400_BAD_REQUEST)
        confirmer = bool(request.data.get('confirmer'))
        date_sortie = None
        raw = request.data.get('date_sortie')
        if raw:
            try:
                from datetime import date as _date
                date_sortie = _date.fromisoformat(str(raw))
            except (TypeError, ValueError):
                date_sortie = None
        try:
            resultat = services.proposer_sortie_pour_licenciement(
                sanction, confirmer=confirmer, date_sortie=date_sortie)
        except services.SortieNonConfirmeeError as exc:
            return Response(
                {
                    'detail': str(exc),
                    'employe_id': sanction.employe_id,
                    'date_sortie_proposee': (
                        (date_sortie or sanction.date_notification)
                        and (date_sortie or sanction.date_notification)
                        .isoformat()),
                },
                status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DossierEmployeSerializer(resultat).data
            if resultat is not None else {'detail': 'Aucun effet.'},
            status=status.HTTP_200_OK)


class ElementsVariablesPaieViewSet(_RhBaseViewSet):
    """Éléments variables de paie mensuels (FG192) — export prestataire paie.

    Société scopée + Administrateur/Responsable. Enregistre le bordereau
    mensuel par employé (heures normales/supp, jours d'absence/congés, primes,
    retenues, commentaire, statut) destiné au prestataire de paie — ce n'est
    PAS un moteur de paie. ``company`` et ``date_export`` sont posées CÔTÉ
    SERVEUR (jamais lues du corps) ; ``employe`` doit appartenir à la même
    société. Le couple (employe, annee, mois) est unique.

    Filtres : ``?employe=<id>``, ``?annee=<n>``, ``?mois=<1-12>``,
    ``?statut=brouillon|valide|exporte``.

    Actions :
    * ``GET .../export-paie-csv/?annee=&mois=`` — CSV du bordereau (matricule,
      identité, quantités, montants), scopé société + filtré.
    * ``POST .../{id}/marquer-exporte/`` — passe en ``statut=exporte`` et pose
      ``date_export`` côté serveur. Idempotent.
    """
    queryset = ElementsVariablesPaie.objects.select_related('employe').all()
    serializer_class = ElementsVariablesPaieSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employe__matricule', 'employe__nom', 'commentaire']
    ordering_fields = ['annee', 'mois', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        annee = self.request.query_params.get('annee')
        if annee:
            qs = qs.filter(annee=annee)
        mois = self.request.query_params.get('mois')
        if mois:
            qs = qs.filter(mois=mois)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur ; FK validé via le sérialiseur."""
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'], url_path='export-paie-csv')
    def export_paie_csv(self, request):
        """Export CSV du bordereau mensuel (FG192), scopé société + filtré.

        On garde ``?export``/un endpoint dédié (et NON ``?format=``, réservé
        par DRF) comme déclencheur d'export.
        """
        import csv

        from django.http import HttpResponse

        rows = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            'attachment; filename="elements-variables-paie.csv"')
        # BOM UTF-8 pour qu'Excel ouvre correctement les accents.
        response.write('﻿')
        writer = csv.writer(response)
        writer.writerow([
            'Matricule', 'Nom', 'Prenom', 'Annee', 'Mois',
            'Heures normales', 'Heures supp',
            'Jours absence', 'Jours conges',
            'Primes', 'Retenues', 'Statut', 'Commentaire',
        ])
        for evp in rows:
            emp = evp.employe
            writer.writerow([
                emp.matricule, emp.nom, emp.prenom,
                evp.annee, evp.mois,
                evp.heures_normales, evp.heures_supp,
                evp.jours_absence, evp.jours_conges,
                evp.primes, evp.retenues,
                evp.get_statut_display(), evp.commentaire,
            ])
        return response

    @action(detail=True, methods=['post'], url_path='marquer-exporte')
    def marquer_exporte(self, request, pk=None):
        """Marque le bordereau exporté (FG192) — ``statut=exporte`` + date.

        La société est garantie par ``get_object`` (autre tenant → 404).
        Idempotent : re-marquer renvoie le même bordereau sans réécrire la date.
        """
        evp = self.get_object()
        if evp.statut != ElementsVariablesPaie.Statut.EXPORTE:
            evp.statut = ElementsVariablesPaie.Statut.EXPORTE
            evp.date_export = timezone.now()
            evp.save(update_fields=[
                'statut', 'date_export', 'date_modification'])
        return Response(
            self.get_serializer(evp).data, status=status.HTTP_200_OK)


class TypePrimeViewSet(_RhBaseViewSet):
    """Référentiel des primes & indemnités (FG193).

    Société scopée + Administrateur/Responsable. Catalogue des types de primes
    (rendement, chantier, panier, transport…) : code, libellé, nature, montant
    par défaut, drapeaux imposable/actif. ``company`` est posée CÔTÉ SERVEUR
    (jamais lue du corps) ; (company, code) est unique.

    Filtres : ``?nature=prime|indemnite``, ``?actif=true|false``.
    """
    queryset = TypePrime.objects.all()
    serializer_class = TypePrimeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle']
    ordering_fields = ['libelle', 'code', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        nature = self.request.query_params.get('nature')
        if nature:
            qs = qs.filter(nature=nature)
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui'))
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur."""
        serializer.save(company=self.request.user.company)


class PrimeAttribueeViewSet(_RhBaseViewSet):
    """Primes/indemnités attribuées (FG193) — par employé et par période.

    Société scopée + Administrateur/Responsable. Attribue un type de prime à un
    employé pour une période (année/mois) avec un montant (par défaut celui du
    type), un motif et un statut (proposée → validée → payée). ``company`` est
    posée CÔTÉ SERVEUR (jamais lue du corps) ; ``type_prime`` / ``employe``
    doivent appartenir à la même société. Si le montant n'est pas fourni (0),
    il est initialisé au montant par défaut du type côté serveur.

    Filtres : ``?employe=<id>``, ``?type_prime=<id>``, ``?annee=<n>``,
    ``?mois=<1-12>``, ``?statut=proposee|validee|payee``.

    Action :
    * ``POST .../{id}/valider/`` — passe en ``statut=validee``. Idempotent.
    """
    queryset = PrimeAttribuee.objects.select_related(
        'type_prime', 'employe').all()
    serializer_class = PrimeAttribueeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['motif', 'employe__matricule', 'type_prime__libelle']
    ordering_fields = ['annee', 'mois', 'montant', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        type_prime = self.request.query_params.get('type_prime')
        if type_prime:
            qs = qs.filter(type_prime_id=type_prime)
        annee = self.request.query_params.get('annee')
        if annee:
            qs = qs.filter(annee=annee)
        mois = self.request.query_params.get('mois')
        if mois:
            qs = qs.filter(mois=mois)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur ; montant par défaut du type si absent."""
        montant = serializer.validated_data.get('montant') or 0
        extra = {}
        if not montant:
            type_prime = serializer.validated_data.get('type_prime')
            if type_prime is not None:
                extra['montant'] = type_prime.montant_defaut
        serializer.save(company=self.request.user.company, **extra)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valide la prime (FG193) — passe en ``statut=validee``.

        La société est garantie par ``get_object`` (autre tenant → 404).
        Idempotent : revalider renvoie la même prime sans erreur.
        """
        prime = self.get_object()
        if prime.statut != PrimeAttribuee.Statut.VALIDEE:
            prime.statut = PrimeAttribuee.Statut.VALIDEE
            prime.save(update_fields=['statut', 'date_modification'])
        return Response(
            self.get_serializer(prime).data, status=status.HTTP_200_OK)


class OrdreMissionViewSet(_RhBaseViewSet):
    """Ordres de mission / déplacements chantier (FG194).

    Société scopée + Administrateur/Responsable. Enregistre un ordre de mission
    (déplacement chantier) : employé, destination, motif, dates départ/retour,
    moyen de transport, véhicule (ID flotte), per-diem, statut (brouillon →
    émis → clôturé). ``company`` et ``reference`` (préfixe ``OM``, par société/
    mois) sont posées CÔTÉ SERVEUR (jamais lues du corps) ; ``employe`` doit
    appartenir à la même société.

    Filtres : ``?employe=<id>``, ``?statut=brouillon|emis|cloture``. Recherche :
    référence, destination, motif.

    Actions :
    * ``GET .../{id}/pdf/`` — restitue l'ordre de mission en PDF (streamé).
    * ``POST .../{id}/emettre/`` — passe en ``statut=emis``. Idempotent.
    """
    queryset = OrdreMission.objects.select_related('employe').all()
    serializer_class = OrdreMissionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'destination', 'motif',
                     'employe__matricule', 'employe__nom']
    ordering_fields = ['date_depart', 'reference', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        """Company + référence (préfixe ``OM``) posées côté serveur."""
        from apps.ventes.utils.references import create_with_reference

        company = self.request.user.company
        create_with_reference(
            OrdreMission, 'OM', company,
            lambda reference: serializer.save(
                company=company, reference=reference))

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        """Restitue l'ordre de mission en PDF (FG194), scopé société.

        La société est garantie par ``get_object`` (autre tenant → 404).
        """
        from django.http import HttpResponse

        from . import mission_pdf

        ordre = self.get_object()
        pdf_bytes = mission_pdf.render_ordre_mission_pdf(ordre)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="ordre-mission-{ordre.reference}.pdf"')
        return response

    @action(detail=True, methods=['post'], url_path='emettre')
    def emettre(self, request, pk=None):
        """Émet l'ordre de mission (FG194) — passe en ``statut=emis``.

        La société est garantie par ``get_object`` (autre tenant → 404).
        Idempotent : ré-émettre renvoie le même ordre sans erreur.
        """
        ordre = self.get_object()
        if ordre.statut == OrdreMission.Statut.BROUILLON:
            ordre.statut = OrdreMission.Statut.EMIS
            ordre.save(update_fields=['statut', 'date_modification'])
        return Response(
            self.get_serializer(ordre).data, status=status.HTTP_200_OK)


class AvanceSalaireViewSet(_RhBaseViewSet):
    """Avances sur salaire (FG195) — demande, validation, déduction.

    Société scopée + Administrateur/Responsable. Enregistre une demande
    d'avance (employé, montant, date, motif, mois/année de déduction). Si le
    mois de déduction n'est pas fourni, il est posé côté serveur au mois SUIVANT
    la demande (l'avance est récupérée sur la paie suivante). ``company`` est
    posée CÔTÉ SERVEUR (jamais lue du corps) ; ``employe`` doit appartenir à la
    même société. Les avances APPROUVÉES alimentent l'export paie (FG192) via
    le sélecteur ``avances_a_deduire``.

    Filtres : ``?employe=<id>``, ``?statut=demandee|approuvee|deduite|refusee``,
    ``?annee_deduction=<n>``, ``?mois_deduction=<1-12>``.

    Actions :
    * ``POST .../{id}/approuver/`` — passe en ``statut=approuvee`` et trace le
      valideur (DossierEmploye du compte appelant si lié). Idempotent.
    * ``POST .../{id}/refuser/`` — passe en ``statut=refusee``. Idempotent.
    * ``POST .../{id}/marquer-deduite/`` — passe en ``statut=deduite`` (avance
      récupérée sur paie). Idempotent.
    """
    queryset = AvanceSalaire.objects.select_related(
        'employe', 'valideur').all()
    serializer_class = AvanceSalaireSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['motif', 'employe__matricule', 'employe__nom']
    ordering_fields = ['date_demande', 'montant', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        annee = self.request.query_params.get('annee_deduction')
        if annee:
            qs = qs.filter(annee_deduction=annee)
        mois = self.request.query_params.get('mois_deduction')
        if mois:
            qs = qs.filter(mois_deduction=mois)
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur ; déduction par défaut = mois suivant."""
        data = serializer.validated_data
        extra = {}
        if not data.get('mois_deduction') or not data.get('annee_deduction'):
            base = data.get('date_demande') or timezone.localdate()
            mois = base.month + 1
            annee = base.year
            if mois > 12:
                mois = 1
                annee += 1
            extra['mois_deduction'] = mois
            extra['annee_deduction'] = annee
        serializer.save(company=self.request.user.company, **extra)

    def _valideur_pour(self, request):
        """DossierEmploye lié au compte appelant (même société) ou None."""
        return DossierEmploye.objects.filter(
            company=request.user.company, user=request.user).first()

    @action(detail=True, methods=['post'], url_path='approuver')
    def approuver(self, request, pk=None):
        """Approuve l'avance (FG195) — ``statut=approuvee`` + valideur.

        YHIRE5 — matérialise IMMÉDIATEMENT l'avance côté paie
        (``apps.paie.services.creer_avance_depuis_rh``, cross-app WRITE par
        la couche services, jamais un import de ``paie.models``) : sans ce
        câblage, une avance approuvée n'était JAMAIS retenue sur le
        bulletin. Idempotent (une seule ``AvanceSalarie`` par demande, même
        si ``approuver`` est rejoué). Un employé sans profil de paie ne
        bloque pas l'approbation RH — l'erreur est journalisée, l'avance
        reste approuvée (à corriger côté paie).

        Garantie société par ``get_object`` (autre tenant → 404).
        """
        avance = self.get_object()
        if avance.statut != AvanceSalaire.Statut.APPROUVEE:
            avance.statut = AvanceSalaire.Statut.APPROUVEE
            avance.valideur = self._valideur_pour(request)
            avance.save(update_fields=[
                'statut', 'valideur', 'date_modification'])
        if not avance.paie_avance_id:
            from apps.paie import services as paie_services
            try:
                paie_services.creer_avance_depuis_rh(avance)
            except ValueError:
                pass  # pas de profil de paie — approbation RH inchangée
        return Response(
            self.get_serializer(avance).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='refuser')
    def refuser(self, request, pk=None):
        """Refuse l'avance (FG195) — ``statut=refusee``. Idempotent, 404 autre
        tenant."""
        avance = self.get_object()
        if avance.statut != AvanceSalaire.Statut.REFUSEE:
            avance.statut = AvanceSalaire.Statut.REFUSEE
            avance.valideur = self._valideur_pour(request)
            avance.save(update_fields=[
                'statut', 'valideur', 'date_modification'])
        return Response(
            self.get_serializer(avance).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='marquer-deduite')
    def marquer_deduite(self, request, pk=None):
        """Marque l'avance déduite (FG195) — ``statut=deduite``. Idempotent,
        404 autre tenant."""
        avance = self.get_object()
        if avance.statut != AvanceSalaire.Statut.DEDUITE:
            avance.statut = AvanceSalaire.Statut.DEDUITE
            avance.save(update_fields=['statut', 'date_modification'])
        return Response(
            self.get_serializer(avance).data, status=status.HTTP_200_OK)


class BulletinPaieViewSet(_RhBaseViewSet):
    """Bulletins de paie en lecture seule (FG196) — dépôt mensuel.

    Société scopée. Dépose le bulletin PDF mensuel (produit par le prestataire
    de paie) rattaché à un employé pour une période (annee/mois) ; AUCUN calcul
    légal n'est fait ici. La création est multipart (``employe`` + ``file`` +
    ``annee`` + ``mois``) ; le fichier RÉUTILISE le stockage objet existant de
    ``records.Attachment`` (MinIO). ``company`` et la pièce jointe sont posées
    CÔTÉ SERVEUR. Le couple (employe, annee, mois) est unique.

    Dépôt/administration : Administrateur/Responsable. Consultation par le
    collaborateur : action ``mes-bulletins`` (rôle authentifié), qui ne renvoie
    QUE les bulletins du dossier lié à son compte.

    Filtres : ``?employe=<id>``, ``?annee=<n>``, ``?mois=<1-12>``.
    """
    queryset = BulletinPaie.objects.select_related(
        'employe', 'attachment').all()
    serializer_class = BulletinPaieSerializer
    parser_classes = [MultiPartParser, JSONParser]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['annee', 'mois', 'date_creation']

    def get_permissions(self):
        # Le collaborateur consulte SON bulletin sans être Responsable/Admin.
        if self.action == 'mes_bulletins':
            return [IsAnyRole()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        annee = self.request.query_params.get('annee')
        if annee:
            qs = qs.filter(annee=annee)
        mois = self.request.query_params.get('mois')
        if mois:
            qs = qs.filter(mois=mois)
        return qs

    def create(self, request, *args, **kwargs):
        """Téléverse le bulletin (MinIO via records.storage) puis l'enregistre.

        ``employe`` doit appartenir à la société ; ``company`` et la pièce
        jointe sont posées côté serveur (jamais lues du corps).
        """
        company = request.user.company
        employe_id = request.data.get('employe')
        try:
            employe = DossierEmploye.objects.get(
                pk=employe_id, company=company)
        except (DossierEmploye.DoesNotExist, ValueError, TypeError):
            return Response({'employe': 'Employé inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        file = request.FILES.get('file')
        if not file:
            return Response({'file': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)

        meta, err = store_attachment(file)
        if err:
            return Response({'file': err},
                            status=status.HTTP_400_BAD_REQUEST)
        ct = ContentType.objects.get_for_model(DossierEmploye)
        attachment = Attachment.objects.create(
            company=company, content_type=ct, object_id=employe.id,
            uploaded_by=request.user, **meta)
        bulletin = BulletinPaie.objects.create(
            company=company, employe=employe, attachment=attachment,
            annee=ser.validated_data['annee'],
            mois=ser.validated_data['mois'],
            note=ser.validated_data.get('note', ''))
        return Response(self.get_serializer(bulletin).data,
                        status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        att = instance.attachment
        instance.delete()
        if att is not None:
            delete_attachment(att.file_key)
            att.delete()

    @action(detail=False, methods=['get'], url_path='mes-bulletins')
    def mes_bulletins(self, request):
        """Bulletins de paie du collaborateur connecté (FG196/FG199).

        Ne renvoie QUE les bulletins du ``DossierEmploye`` lié au compte
        appelant (même société). Si aucun dossier n'est lié, renvoie une liste
        vide. Société garantie par le filtrage TenantMixin + le lien user.
        """
        dossier = DossierEmploye.objects.filter(
            company=request.user.company, user=request.user).first()
        if dossier is None:
            return Response([])
        qs = self.get_queryset().filter(employe=dossier)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)


class PermisConduireViewSet(_RhBaseViewSet):
    """Permis de conduire & habilitation à conduire (FG197).

    Société scopée + Administrateur/Responsable. Suit le permis d'un employé
    (catégorie, numéro, dates de délivrance/expiration, habilitation interne).
    ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps) ; ``employe`` doit
    appartenir à la même société. Le couple (employe, categorie) est unique.
    Source de vérité du droit de conduire pour la garde d'affectation FG198.

    Filtres : ``?employe=<id>``, ``?categorie=...``,
    ``?habilitation_conduite=true|false``. Recherche : numéro, matricule/nom.

    Action :
    * ``GET .../expirant-bientot/?within=`` — permis qui expirent dans les
      ``?within=`` prochains jours (défaut 30), scopés société.
    """
    queryset = PermisConduire.objects.select_related('employe').all()
    serializer_class = PermisConduireSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero', 'employe__matricule', 'employe__nom']
    ordering_fields = ['date_expiration', 'categorie', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        hab = self.request.query_params.get('habilitation_conduite')
        if hab is not None:
            qs = qs.filter(
                habilitation_conduite=hab.lower() in ('1', 'true', 'oui'))
        return qs

    def perform_create(self, serializer):
        """Company posée côté serveur ; FK validé via le sérialiseur."""
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'], url_path='expirant-bientot')
    def expirant_bientot(self, request):
        """Permis de la société expirant dans les ``?within=`` prochains jours
        (défaut 30). S'appuie sur ``selectors.permis_expirant_bientot`` — scopé
        société, exclut les permis sans échéance et déjà expirés."""
        within = request.query_params.get('within', 30)
        qs = selectors.permis_expirant_bientot(
            request.user.company, within_days=within)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)


class AffectationVehiculeViewSet(_RhBaseViewSet):
    """Affectations conducteur ↔ véhicule (FG198) — garde permis valide.

    Société scopée + Administrateur/Responsable. Lie un conducteur à un véhicule
    du parc (``vehicule_id`` = ID flotte.Vehicule, STRING-FK) sur une période.
    ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps) ; ``employe`` doit
    appartenir à la même société.

    GARDE PERMIS (décision FG198) : à la création/màj, l'affectation est REFUSÉE
    (400) si le conducteur n'a pas de permis VALIDE (FG197) — contrôle posé côté
    serveur via ``services.controler_permis_affectation`` ; ``permis_verifie``
    est alors posé à ``True``.

    Filtres : ``?employe=<id>``, ``?vehicule_id=<id>``,
    ``?statut=active|terminee``.

    Action :
    * ``POST .../{id}/terminer/`` — clôt l'affectation (``statut=terminee``,
      pose ``date_fin`` si absente). Idempotent.
    """
    queryset = AffectationVehicule.objects.select_related('employe').all()
    serializer_class = AffectationVehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employe__matricule', 'employe__nom', 'note']
    ordering_fields = ['date_debut', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        vehicule = self.request.query_params.get('vehicule_id')
        if vehicule:
            qs = qs.filter(vehicule_id=vehicule)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _verifier_permis(self, serializer):
        """Refuse (400) si le conducteur n'a pas de permis valide (FG198)."""
        from rest_framework.exceptions import ValidationError

        company = self.request.user.company
        employe = serializer.validated_data.get('employe')
        le = serializer.validated_data.get('date_debut')
        if employe is not None and not services.controler_permis_affectation(
                company, employe.id, le=le):
            raise ValidationError({
                'employe': ("Affectation refusée : ce conducteur n'a pas de "
                            'permis de conduire valide (FG197).')})

    def perform_create(self, serializer):
        """Company posée côté serveur ; garde permis valide (FG198)."""
        self._verifier_permis(serializer)
        serializer.save(
            company=self.request.user.company, permis_verifie=True)

    def perform_update(self, serializer):
        """Re-contrôle le permis si l'employé/la date change (FG198)."""
        if ('employe' in serializer.validated_data
                or 'date_debut' in serializer.validated_data):
            self._verifier_permis(serializer)
            serializer.save(permis_verifie=True)
        else:
            serializer.save()

    @action(detail=True, methods=['post'], url_path='terminer')
    def terminer(self, request, pk=None):
        """Clôt l'affectation (FG198) — ``statut=terminee`` + ``date_fin``.

        La société est garantie par ``get_object`` (autre tenant → 404).
        Idempotent : re-terminer renvoie la même affectation sans erreur.
        """
        affectation = self.get_object()
        if affectation.statut != AffectationVehicule.Statut.TERMINEE:
            affectation.statut = AffectationVehicule.Statut.TERMINEE
            if affectation.date_fin is None:
                affectation.date_fin = timezone.localdate()
            affectation.save(update_fields=[
                'statut', 'date_fin', 'date_modification'])
        return Response(
            self.get_serializer(affectation).data, status=status.HTTP_200_OK)


class NoteDeFraisViewSet(_RhBaseViewSet):
    """Notes de frais (FG199) — administration (Administrateur/Responsable).

    Société scopée. Liste/administre TOUTES les notes de frais de la société et
    pilote leur approbation. La SAISIE par le collaborateur passe par le portail
    self-service (``portail/declarer-frais``). ``company`` est posée CÔTÉ
    SERVEUR (jamais lue du corps).

    Filtres : ``?employe=<id>``, ``?categorie=...``,
    ``?statut=soumise|approuvee|remboursee|refusee``.

    Actions :
    * ``POST .../{id}/approuver/`` — ``statut=approuvee``. Idempotent.
    * ``POST .../{id}/refuser/`` — ``statut=refusee``. Idempotent.
    * ``POST .../{id}/marquer-remboursee/`` — ``statut=remboursee``. Idempotent.
    """
    queryset = NoteDeFrais.objects.select_related('employe').all()
    serializer_class = NoteDeFraisSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'employe__matricule', 'employe__nom']
    ordering_fields = ['date_frais', 'montant', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _set_statut(self, request, pk, nouveau):
        note = self.get_object()
        if note.statut != nouveau:
            note.statut = nouveau
            note.save(update_fields=['statut', 'date_modification'])
        return Response(
            self.get_serializer(note).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='approuver')
    def approuver(self, request, pk=None):
        """Approuve la note de frais (FG199). Idempotent, 404 autre tenant."""
        return self._set_statut(request, pk, NoteDeFrais.Statut.APPROUVEE)

    @action(detail=True, methods=['post'], url_path='refuser')
    def refuser(self, request, pk=None):
        """Refuse la note de frais (FG199). Idempotent, 404 autre tenant."""
        return self._set_statut(request, pk, NoteDeFrais.Statut.REFUSEE)

    @action(detail=True, methods=['post'], url_path='marquer-remboursee')
    def marquer_remboursee(self, request, pk=None):
        """Marque la note remboursée (FG199). Idempotent, 404 autre tenant."""
        return self._set_statut(request, pk, NoteDeFrais.Statut.REMBOURSEE)


class DemandeRHViewSet(_RhBaseViewSet):
    """Demandes RH (XRH9) — administration du guichet self-service.

    Société scopée + Administrateur/Responsable. Liste/traite TOUTES les
    demandes de la société ; la SAISIE par le collaborateur passe par le
    portail self-service (``portail/demander-attestation``). ``company`` est
    posée CÔTÉ SERVEUR.

    Filtres : ``?employe=<id>``, ``?statut=soumise|traitee|refusee``,
    ``?type=...``.

    Actions :
    * ``POST .../{id}/traiter/`` — génère le PDF (réutilise le renderer paie
      existant) et le lie à la demande ; refuse 403 si l'attestation de
      salaire est demandée sans ``salaires_voir``.
    * ``POST .../{id}/refuser/`` — refuse la demande (``motif_refus``
      optionnel dans le corps).
    """
    queryset = DemandeRH.objects.select_related(
        'employe', 'attachment', 'traite_par').all()
    serializer_class = DemandeRHSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employe__matricule', 'employe__nom']
    ordering_fields = ['date_creation', 'statut']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        type_ = self.request.query_params.get('type')
        if type_:
            qs = qs.filter(type=type_)
        return qs

    @action(detail=True, methods=['post'], url_path='traiter')
    def traiter(self, request, pk=None):
        """Traite la demande : génère + lie le PDF d'attestation."""
        demande = self.get_object()
        peut_voir_salaires = HasPermission('salaires_voir')().has_permission(
            request, self)
        try:
            services.traiter_demande_rh(
                demande, traitant=request.user,
                peut_voir_salaires=peut_voir_salaires)
        except services.DemandeRHError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            self.get_serializer(demande).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='refuser')
    def refuser(self, request, pk=None):
        """Refuse la demande RH (motif optionnel)."""
        demande = self.get_object()
        motif = request.data.get('motif_refus', '')
        services.refuser_demande_rh(
            demande, traitant=request.user, motif_refus=motif)
        return Response(
            self.get_serializer(demande).data, status=status.HTTP_200_OK)


class PortailSelfServiceViewSet(viewsets.ViewSet):
    """Portail self-service employé (FG199) — accès du collaborateur connecté.

    Permission : tout compte authentifié (``IsAnyRole``). TOUTES les données
    sont résolues à partir du ``DossierEmploye`` LIÉ au compte appelant (même
    société) — un collaborateur ne voit/édite JAMAIS les données d'un autre.
    Si aucun dossier n'est lié au compte, les lectures renvoient une réponse
    vide/404 et les écritures sont refusées (400).

    Endpoints :
    * ``GET portail/mes-infos/`` / ``PATCH portail/mes-infos/`` — fiche perso
      (coordonnées + contact d'urgence éditables ; poste/contrat/statut en
      lecture seule).
    * ``GET portail/mes-soldes/`` — soldes de congés.
    * ``GET portail/mes-conges/`` — ses demandes de congé.
    * ``POST portail/demander-conge/`` — créer une demande de congé.
    * ``GET portail/mes-frais/`` — ses notes de frais.
    * ``POST portail/declarer-frais/`` — déclarer une note de frais.
    * ``GET portail/mes-epi/`` — ses dotations EPI.
    * ``GET portail/mes-habilitations/`` — ses habilitations.
    * ``GET portail/mes-bulletins/`` — ses bulletins de paie.
    """
    permission_classes = [IsAnyRole]

    def _dossier(self, request):
        return DossierEmploye.objects.filter(
            company=request.user.company, user=request.user).first()

    @action(detail=False, methods=['get', 'patch'], url_path='mes-infos')
    def mes_infos(self, request):
        """Fiche perso du collaborateur (lecture/édition limitée)."""
        dossier = self._dossier(request)
        if dossier is None:
            return Response(
                {'detail': 'Aucun dossier employé lié à ce compte.'},
                status=status.HTTP_404_NOT_FOUND)
        if request.method == 'PATCH':
            ser = MesInfosSerializer(dossier, data=request.data, partial=True)
            ser.is_valid(raise_exception=True)
            ser.save()
            return Response(ser.data)
        return Response(MesInfosSerializer(dossier).data)

    @action(detail=False, methods=['get'], url_path='mes-soldes')
    def mes_soldes(self, request):
        dossier = self._dossier(request)
        if dossier is None:
            return Response([])
        qs = SoldeConge.objects.filter(
            company=request.user.company, employe=dossier)
        return Response(SoldeCongeSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='mes-conges')
    def mes_conges(self, request):
        dossier = self._dossier(request)
        if dossier is None:
            return Response([])
        qs = DemandeConge.objects.filter(
            company=request.user.company, employe=dossier).select_related(
            'type_absence')
        return Response(DemandeCongeSerializer(qs, many=True).data)

    @action(detail=False, methods=['get', 'post'], url_path='mes-allocations')
    def mes_allocations(self, request):
        """ZRH13 — allocation de congés self-service : ``GET`` liste les
        demandes du collaborateur connecté (avec son solde disponible par
        type) ; ``POST`` en crée une nouvelle pour LUI-MÊME. ``employe`` et
        ``company`` sont posés CÔTÉ SERVEUR (jamais lus du corps)."""
        dossier = self._dossier(request)
        if dossier is None:
            if request.method == 'POST':
                return Response(
                    {'detail': 'Aucun dossier employé lié à ce compte.'},
                    status=status.HTTP_400_BAD_REQUEST)
            return Response([])
        if request.method == 'POST':
            data = {
                k: v for k, v in request.data.items() if k != 'employe'}
            data['employe'] = dossier.id
            ser = DemandeAllocationSerializer(
                data=data, context={'request': request})
            ser.is_valid(raise_exception=True)
            ser.save(company=request.user.company)
            return Response(ser.data, status=status.HTTP_201_CREATED)
        qs = DemandeAllocation.objects.filter(
            company=request.user.company, employe=dossier).select_related(
            'type_absence')
        return Response(DemandeAllocationSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='demander-conge')
    def demander_conge(self, request):
        """Crée une demande de congé pour le collaborateur connecté.

        ``employe`` et ``company`` sont posés CÔTÉ SERVEUR (jamais lus du
        corps) à partir du dossier lié au compte.
        """
        dossier = self._dossier(request)
        if dossier is None:
            return Response(
                {'detail': 'Aucun dossier employé lié à ce compte.'},
                status=status.HTTP_400_BAD_REQUEST)
        # ``employe`` est TOUJOURS forcé au dossier du compte appelant (jamais
        # lu du corps) ; le serializer valide la cohérence société du type.
        data = {k: v for k, v in request.data.items() if k != 'employe'}
        data['employe'] = dossier.id
        ser = DemandeCongeSerializer(
            data=data, context={'request': request})
        ser.is_valid(raise_exception=True)
        # ``jours`` calculé côté serveur selon la règle de décompte du type
        # (XRH3 : les drapeaux demi-journée retranchent chacun 0,5 j).
        # ZRH1 — même fériés mobiles société que le viewset direct.
        date_debut = ser.validated_data['date_debut']
        date_fin = ser.validated_data['date_fin']

        # ZRH4 — jour bloqué du département : refus 400 sauf forçage RH
        # explicite (``?forcer=1``, réservé Responsable/Admin — un employé
        # normal ne peut jamais forcer son propre blocage).
        conflit = services.jour_bloque_conflit(dossier, date_debut, date_fin)
        forcer = request.query_params.get('forcer') in ('1', 'true', 'True') \
            and getattr(request.user, 'is_responsable', False)
        if conflit and not forcer:
            return Response(
                {'detail': (
                    f'Congés bloqués du {conflit.date_debut} au '
                    f'{conflit.date_fin} : {conflit.libelle}.')},
                status=status.HTTP_400_BAD_REQUEST)

        jours = services.calculer_jours_demande(
            ser.validated_data['type_absence'], date_debut, date_fin,
            extra_holidays=services.feries_periode(
                request.user.company, date_debut, date_fin),
            demi_journee_debut=ser.validated_data.get(
                'demi_journee_debut', False),
            demi_journee_fin=ser.validated_data.get(
                'demi_journee_fin', False))
        ser.save(company=request.user.company, jours=jours)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='mes-frais')
    def mes_frais(self, request):
        dossier = self._dossier(request)
        if dossier is None:
            return Response([])
        qs = NoteDeFrais.objects.filter(
            company=request.user.company, employe=dossier)
        return Response(NoteDeFraisSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='declarer-frais')
    def declarer_frais(self, request):
        """Déclare une note de frais pour le collaborateur connecté.

        ``employe``, ``company`` et ``statut`` sont posés CÔTÉ SERVEUR.
        """
        dossier = self._dossier(request)
        if dossier is None:
            return Response(
                {'detail': 'Aucun dossier employé lié à ce compte.'},
                status=status.HTTP_400_BAD_REQUEST)
        ser = NoteDeFraisSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(company=request.user.company, employe=dossier)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='mes-epi')
    def mes_epi(self, request):
        dossier = self._dossier(request)
        if dossier is None:
            return Response([])
        qs = DotationEpi.objects.filter(
            company=request.user.company, employe=dossier)
        return Response(DotationEpiSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='mes-habilitations')
    def mes_habilitations(self, request):
        dossier = self._dossier(request)
        if dossier is None:
            return Response([])
        qs = Habilitation.objects.filter(
            company=request.user.company, employe=dossier)
        return Response(HabilitationSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='mes-bulletins')
    def mes_bulletins(self, request):
        """YHIRE12 — UNE surface bulletins : fusion dépôts externes (FG196,
        ce module) + bulletins générés/validés (paie, coffre-fort PAIE35).

        Dédupliquée par mois (le bulletin GÉNÉRÉ prime sur le dépôt externe du
        même mois — c'est le document faisant foi une fois la paie calculée en
        interne). La paie n'est JAMAIS importée directement : uniquement via
        ``apps.paie.selectors.mes_bulletins_valides`` (lecture seule).
        """
        dossier = self._dossier(request)
        if dossier is None:
            return Response([])
        deposes = BulletinPaie.objects.filter(
            company=request.user.company, employe=dossier).select_related(
            'attachment')
        deposes_data = BulletinPaieSerializer(deposes, many=True).data
        for item in deposes_data:
            item['source'] = 'depose'

        from apps.paie.selectors import mes_bulletins_valides
        generes = mes_bulletins_valides(request.user)
        generes_data = [
            {
                'id': g['id'],
                'source': 'genere',
                'annee': g['annee'],
                'mois': g['mois'],
                'date_creation': g['date_creation'],
                'employe': dossier.id,
                'employe_nom': str(dossier),
                'note': '',
                'filename': f"bulletin_{g['annee']}_{g['mois']:02d}.pdf",
                'size': None,
                'mime': 'application/pdf',
                'url': None,
            }
            for g in generes
        ]

        by_mois = {(item['annee'], item['mois']): item for item in deposes_data}
        for item in generes_data:
            # Le généré prime : il écrase un dépôt externe du même mois.
            by_mois[(item['annee'], item['mois'])] = item

        fusion = sorted(
            by_mois.values(), key=lambda i: (i['annee'], i['mois']),
            reverse=True)
        return Response(fusion)

    @action(detail=False, methods=['get'], url_path='quiz-disponibles')
    def quiz_disponibles(self, request):
        """XRH34 — quiz actifs de la société, SANS les bonnes réponses
        (``QuizFormationPortailSerializer``)."""
        qs = QuizFormation.objects.filter(
            company=request.user.company, actif=True)
        return Response(QuizFormationPortailSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='passer-quiz')
    def passer_quiz(self, request, pk=None):
        """XRH34 — passe (corrige côté serveur) le quiz ``pk`` pour le
        collaborateur connecté. Corps : ``reponses`` (liste parallèle aux
        questions), ``session`` (id ``SessionFormation`` optionnel — upsert
        ``InscriptionFormation.resultat`` si réussi).

        En cas de réussite : matrice de compétences mise à jour, habilitation
        prolongée le cas échéant, attestation PDF téléchargeable ensuite via
        ``GET tentatives-quiz/{id}/attestation/``.
        """
        dossier = self._dossier(request)
        if dossier is None:
            return Response(
                {'detail': 'Aucun dossier employé lié à ce compte.'},
                status=status.HTTP_400_BAD_REQUEST)
        quiz = QuizFormation.objects.filter(
            company=request.user.company, pk=pk, actif=True).first()
        if quiz is None:
            return Response(
                {'detail': 'Quiz introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        session = None
        session_id = request.data.get('session')
        if session_id:
            session = SessionFormation.objects.filter(
                company=request.user.company, pk=session_id).first()
        tentative = services.passer_tentative_quiz(
            quiz, dossier, reponses=request.data.get('reponses') or [],
            session=session)
        return Response(
            TentativeQuizSerializer(tentative).data,
            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='mes-tentatives-quiz')
    def mes_tentatives_quiz(self, request):
        """XRH34 — SES tentatives de quiz (autre employé → jamais visible)."""
        dossier = self._dossier(request)
        if dossier is None:
            return Response([])
        qs = TentativeQuiz.objects.filter(
            company=request.user.company, employe=dossier).select_related(
            'quiz')
        return Response(TentativeQuizSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='mes-demandes')
    def mes_demandes(self, request):
        """XRH9 — demandes RH (attestations…) du collaborateur connecté."""
        dossier = self._dossier(request)
        if dossier is None:
            return Response([])
        qs = DemandeRH.objects.filter(
            company=request.user.company, employe=dossier).select_related(
            'attachment')
        return Response(DemandeRHSerializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='demander-attestation')
    def demander_attestation(self, request):
        """XRH9 — soumet une demande d'attestation pour le collaborateur.

        ``employe``, ``company`` et ``statut`` sont posés CÔTÉ SERVEUR.
        """
        dossier = self._dossier(request)
        if dossier is None:
            return Response(
                {'detail': 'Aucun dossier employé lié à ce compte.'},
                status=status.HTTP_400_BAD_REQUEST)
        ser = DemandeRHSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(company=request.user.company, employe=dossier)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='mes-demandes-telecharger')
    def mes_demandes_telecharger(self, request, pk=None):
        """XRH9 — télécharge le PDF d'UNE demande, réservé à SON auteur.

        Une demande d'un autre employé (même société) renvoie 404 — le
        téléchargement est strictement personnel. Une demande non encore
        traitée (pas de PDF) renvoie 404.
        """
        from django.http import HttpResponse

        from apps.records.storage import fetch_attachment

        dossier = self._dossier(request)
        if dossier is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        demande = DemandeRH.objects.filter(
            company=request.user.company, employe=dossier, pk=pk).first()
        if demande is None or demande.attachment_id is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        data, err = fetch_attachment(demande.attachment.file_key)
        if err:
            return Response(
                {'detail': err}, status=status.HTTP_404_NOT_FOUND)
        resp = HttpResponse(
            data, content_type=demande.attachment.mime or 'application/pdf')
        safe_name = (demande.attachment.filename or 'attestation.pdf') \
            .replace('"', '')
        resp['Content-Disposition'] = f'inline; filename="{safe_name}"'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp

    @action(detail=False, methods=['get'], url_path='mes-evaluations')
    def mes_evaluations(self, request):
        """XRH26 — les entretiens d'évaluation DU collaborateur connecté."""
        dossier = self._dossier(request)
        if dossier is None:
            return Response([])
        qs = EvaluationEmploye.objects.filter(
            company=request.user.company, employe=dossier).select_related(
            'campagne', 'evaluateur')
        return Response(EvaluationEmployeSerializer(qs, many=True).data)

    @action(detail=True, methods=['patch'], url_path='mon-auto-evaluation')
    def mon_auto_evaluation(self, request, pk=None):
        """XRH26 — saisit SON auto-évaluation sur UN entretien.

        Réservé à l'employé LIÉ à l'évaluation (l'``employe`` de
        l'``EvaluationEmploye``, pas juste un membre de la société) : un
        autre employé de la même société reçoit 403. Seuls
        ``auto_evaluation``/``note_auto`` sont éditables via cette action.
        """
        dossier = self._dossier(request)
        if dossier is None:
            return Response(
                {'detail': 'Aucun dossier employé lié à ce compte.'},
                status=status.HTTP_404_NOT_FOUND)
        evaluation = EvaluationEmploye.objects.filter(
            company=request.user.company, pk=pk).first()
        if evaluation is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if evaluation.employe_id != dossier.id:
            return Response(
                {'detail': "Cette évaluation n'est pas la vôtre."},
                status=status.HTTP_403_FORBIDDEN)
        ser = AutoEvaluationSerializer(
            evaluation, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    @action(detail=False, methods=['get'], url_path='mes-feedback360')
    def mes_feedback360(self, request):
        """ZRH9 — liste les invitations feedback 360° du collaborateur
        connecté (celles où IL est le répondant)."""
        dossier = self._dossier(request)
        if dossier is None:
            return Response([])
        qs = RetourFeedback360.objects.filter(
            company=request.user.company, repondant=dossier
        ).select_related('evaluation')
        return Response(MonFeedback360Serializer(qs, many=True).data)

    @action(
        detail=True, methods=['patch'], url_path='mon-feedback360')
    def mon_feedback360(self, request, pk=None):
        """ZRH9 — remplit/soumet SON PROPRE retour feedback 360°
        (``pk`` = id du ``RetourFeedback360``). Un répondant ne voit ni ne
        modifie JAMAIS le retour d'un autre — un id qui n'est pas le sien
        (ou d'une autre société) renvoie 404."""
        dossier = self._dossier(request)
        if dossier is None:
            return Response(
                {'detail': 'Aucun dossier employé lié à ce compte.'},
                status=status.HTTP_404_NOT_FOUND)
        retour = RetourFeedback360.objects.filter(
            company=request.user.company, pk=pk, repondant=dossier).first()
        if retour is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ser = MonFeedback360Serializer(
            retour, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        if request.data.get('soumis'):
            ser.save(soumis=True, date_soumission=timezone.now())
        else:
            ser.save()
        return Response(ser.data)


class CockpitRhViewSet(viewsets.ViewSet):
    """Cockpit RH — effectifs & coûts (FG200), tableau de bord en lecture.

    Société scopée + Administrateur/Responsable (``IsResponsableOrAdmin``).
    Agrège (sans rien stocker) l'effectif par statut/contrat/département, la
    pyramide d'ancienneté, le turnover 12 mois et les alertes (CDD à échéance,
    documents/permis/visites à expirer) via ``selectors.cockpit_rh``.

    GATED — masse salariale : la ``masse_salariale_mensuelle`` (donnée INTERNE
    paie) n'est incluse QUE si l'appelant porte la permission ``salaires_voir``
    (palier RH), sinon elle est omise. Elle ne quitte jamais cette API admin.

    Endpoint :
    * ``GET cockpit/`` (list) — renvoie le tableau de bord agrégé.
    * ``GET cockpit/top-risque-attrition/?limite=N`` — XRH31, top-N employés
      actifs par risque d'attrition décroissant (scorer pur, calculé à la
      demande — jamais inclus dans ``list()`` pour ne pas alourdir le cockpit
      principal d'un scoring par employé à chaque chargement).
    """
    permission_classes = [IsResponsableOrAdmin]

    def list(self, request):
        peut_voir_salaires = HasPermission('salaires_voir')().has_permission(
            request, self)
        departement = request.query_params.get('departement')
        data = selectors.cockpit_rh(
            request.user.company,
            inclure_masse_salariale=peut_voir_salaires,
            departement_id=departement)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='top-risque-attrition')
    def top_risque_attrition(self, request):
        limite = int(request.query_params.get('limite', 10))
        return Response(
            selectors.top_risque_attrition(
                request.user.company, limite=limite))
