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
    DemandeConge,
    Departement,
    DocumentEmploye,
    DossierEmploye,
    ElementSortie,
    Pointage,
    Poste,
    Remuneration,
    SoldeConge,
    TypeAbsence,
)
from .serializers import (
    DemandeCongeSerializer,
    DepartementSerializer,
    DocumentEmployeSerializer,
    DossierEmployeSerializer,
    ElementSortieSerializer,
    PointageSerializer,
    PosteSerializer,
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
