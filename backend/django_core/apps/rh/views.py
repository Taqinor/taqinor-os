"""Vues des Ressources humaines (toutes scopées société, admin-gated).

Le module RH est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``). Les
viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la société
côté serveur ; le ``cout_horaire`` (paie/marge) ne quitte jamais cette API.
"""
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.records.models import Attachment
from apps.records.storage import delete_attachment, store_attachment
from authentication.mixins import TenantMixin
from authentication.permissions import HasPermission, IsResponsableOrAdmin

from . import selectors, services
from .models import (
    AffectationRoster,
    Certification,
    Competence,
    CompetenceEmploye,
    DemandeConge,
    Departement,
    DocumentEmploye,
    DossierEmploye,
    ElementSortie,
    FeuilleTemps,
    Habilitation,
    HeuresSupp,
    IncidentPresence,
    Pointage,
    Poste,
    PresenceChantier,
    Remuneration,
    SoldeConge,
    TypeAbsence,
)
from .serializers import (
    AffectationRosterSerializer,
    CertificationSerializer,
    CompetenceEmployeSerializer,
    CompetenceSerializer,
    DemandeCongeSerializer,
    DepartementSerializer,
    DocumentEmployeSerializer,
    DossierEmployeSerializer,
    ElementSortieSerializer,
    FeuilleTempsSerializer,
    HabilitationSerializer,
    HeuresSuppSerializer,
    IncidentPresenceSerializer,
    PointageSerializer,
    PosteSerializer,
    PresenceChantierSerializer,
    RemunerationSerializer,
    SoldeCongeSerializer,
    TypeAbsenceSerializer,
)


class _RhBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class DepartementViewSet(_RhBaseViewSet):
    """Départements de la société. Recherche par nom/code."""
    queryset = Departement.objects.all()
    serializer_class = DepartementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'code']
    ordering_fields = ['nom']


class DossierEmployeViewSet(_RhBaseViewSet):
    """Dossiers employés (DC29). Recherche par matricule/nom/prénom."""
    queryset = DossierEmploye.objects.select_related('departement', 'user').all()
    serializer_class = DossierEmployeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['matricule', 'nom', 'prenom', 'cin', 'email']
    ordering_fields = ['nom', 'prenom', 'matricule', 'date_embauche']

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
        # ``jours`` calculé côté serveur selon la règle de décompte du type.
        type_absence = serializer.validated_data['type_absence']
        jours = services.calculer_jours_demande(
            type_absence,
            serializer.validated_data['date_debut'],
            serializer.validated_data['date_fin'])
        serializer.save(company=self.request.user.company, jours=jours)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valide une demande soumise et déduit le solde si le type le requiert."""
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
        """Company posée côté serveur ; majoration calculée côté serveur."""
        instance = serializer.save(company=self.request.user.company)
        services.appliquer_majoration(instance)
        instance.save()

    def perform_update(self, serializer):
        """Recalcule la majoration à chaque mise à jour."""
        instance = serializer.save()
        services.appliquer_majoration(instance)
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
        company = request.user.company
        employe_id = request.data.get('employe')
        try:
            employe = DossierEmploye.objects.get(pk=employe_id, company=company)
        except (DossierEmploye.DoesNotExist, ValueError, TypeError):
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
        """
        presence = self.get_object()
        presence.emarge = True
        presence.emarge_le = timezone.now()
        presence.emarge_par = request.user
        presence.save(update_fields=[
            'emarge', 'emarge_le', 'emarge_par', 'date_modification'])
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

    def perform_create(self, serializer):
        """Company posée côté serveur, jamais lue du corps."""
        serializer.save(company=self.request.user.company)


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
        """Company + traçabilité d'évaluation posées côté serveur."""
        serializer.save(
            company=self.request.user.company,
            evalue_par=self.request.user,
            evalue_le=timezone.now())

    def perform_update(self, serializer):
        """Réévaluation : on retrace l'auteur/date côté serveur."""
        serializer.save(
            evalue_par=self.request.user,
            evalue_le=timezone.now())

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


class EcheancesRhViewSet(TenantMixin, viewsets.ViewSet):
    """Moteur d'échéances RH unifié (FG175) — alertes d'expiration agrégées.

    Société scopée + Administrateur/Responsable. Réunit en UNE liste normalisée
    les habilitations (FG173), certifications (FG174) et documents employé
    (FG159) qui expirent (ou sont déjà expirés) dans la fenêtre demandée.

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
