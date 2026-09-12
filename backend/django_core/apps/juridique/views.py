"""Vues du module ``apps.juridique`` (groupe NTJUR).

Tout est scopé société (``CompanyScopedModelViewSet``, ARC2 : queryset filtré
sur ``request.user.company`` + ``company`` forcée côté serveur dans
``perform_create``). S'y ajoute le filtrage de CONFIDENTIALITÉ (NTJUR1) : un
dossier ``confidentiel`` est simplement ABSENT du queryset d'un utilisateur
sans le palier requis — un accès direct par id renvoie donc 404 (jamais 403,
qui révélerait l'existence du dossier).

NTJUR40 — les DEUX actions de décision du workflow d'approbation
(``approuver-etape`` / ``rejeter-etape``) exigent, EN PLUS de l'écriture
``juridique_gerer``, la permission fine ``juridique_approuver_engagement``.
Être nommé approbateur d'une étape ne suffit donc jamais : retirer la
permission au rôle d'un approbateur désigné bloque son bouton « Approuver »
côté API immédiatement, sans toucher aux étapes en cours.
"""
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import filters, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import HasPermissionOrLegacy
from core.permissions import ScopedPermission
from core.viewsets import CompanyScopedModelViewSet

from . import selectors, services
from .models import (
    Audience, CabinetAvocat, DelaiPrescription, DossierJuridique,
    EtapeApprobationJuridique, MandatAvocat, NoteHonoraires,
    RegleApprobationJuridique,
)
from .serializers import (
    AudienceSerializer, CabinetAvocatSerializer, DelaiPrescriptionSerializer,
    DossierJuridiqueSerializer, EtapeApprobationJuridiqueSerializer,
    MandatAvocatSerializer, NoteHonorairesSerializer,
    RegleApprobationJuridiqueSerializer,
)


class DossierJuridiqueViewSet(CompanyScopedModelViewSet):
    """CRUD des dossiers juridiques de la société (NTJUR1).

    Le contrôle d'accès suit le patron YRBAC3 des modules voisins
    (``contrats``/``litiges``) : lecture et écriture gardées par des codes
    distincts, avec le repli légacy pour les comptes sans rôle fin.
    """

    queryset = DossierJuridique.objects.select_related(
        'company', 'responsable_interne', 'created_by').all()
    serializer_class = DossierJuridiqueSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'titre', 'partie_adverse_nom']
    ordering_fields = ['id', 'date_ouverture', 'montant_en_jeu', 'statut']
    read_permission = 'juridique_voir'
    write_permission = 'juridique_gerer'

    def get_queryset(self):
        """Scope société (ARC2) + exclusion des dossiers confidentiels.

        Filtres optionnels : ``?statut=``, ``?nature=``, ``?type_procedure=``,
        ``?responsable_interne=``.
        """
        qs = super().get_queryset()
        user = self.request.user
        if not selectors.peut_voir_confidentiel(user):
            qs = qs.exclude(
                confidentialite=(
                    DossierJuridique.NiveauConfidentialite.CONFIDENTIEL))
        params = self.request.query_params
        for champ in ('statut', 'nature', 'type_procedure',
                      'responsable_interne', 'confidentialite'):
            valeur = params.get(champ)
            if valeur:
                qs = qs.filter(**{champ: valeur})
        return qs

    def perform_create(self, serializer):
        """Crée le dossier avec une référence anti-collision (``JUR-AAAA-NNNN``).

        La société est TOUJOURS celle de l'appelant (jamais lue du corps), et
        la référence passe par ``core.numbering`` — jamais ``count() + 1``.
        """
        from core.numbering import create_with_reference

        company = self.request.user.company
        create_with_reference(
            DossierJuridique, 'JUR', company,
            lambda reference: serializer.save(
                company=company, reference=reference,
                created_by=self.request.user),
            period='yearly')

    # ── NTJUR12 — budget engagé / consommé / alloué ─────────────────────────

    @extend_schema(responses=inline_serializer('JuridiqueBudgetDossier', {
        'dossier': serializers.IntegerField(),
        'reference': serializers.CharField(),
        'budget_alloue': serializers.CharField(allow_null=True),
        'engage': serializers.CharField(),
        'consomme': serializers.CharField(),
        'pourcentage_consomme': serializers.FloatField(allow_null=True),
        'depassement': serializers.BooleanField(),
    }))
    @action(detail=True, methods=['get'], url_path='budget')
    def budget(self, request, pk=None):
        """Budget du dossier : engagé vs consommé vs alloué (NTJUR12).

        Les montants sont des chaînes (``str(Decimal)``) — le schéma dit ce
        que le serveur fait, jamais ce qu'on aimerait qu'il fasse.
        """
        dossier = self.get_object()
        return Response(selectors.budget_dossier(dossier))

    @extend_schema(responses=inline_serializer('JuridiqueTableauBord', {
        'nombre_dossiers': serializers.IntegerField(),
        'total_engage': serializers.CharField(),
        'total_consomme': serializers.CharField(),
        'par_nature': inline_serializer('JuridiqueTableauBordNature', {
            'nature': serializers.CharField(),
            'nombre': serializers.IntegerField(),
            'engage': serializers.CharField(),
            'consomme': serializers.CharField(),
        }, many=True),
        'depassements': inline_serializer('JuridiqueTableauBordDepassement', {
            'dossier': serializers.IntegerField(),
            'reference': serializers.CharField(),
            'titre': serializers.CharField(),
            'budget_alloue': serializers.CharField(allow_null=True),
            'consomme': serializers.CharField(),
            'pourcentage_consomme': serializers.FloatField(allow_null=True),
        }, many=True),
    }))
    @action(detail=False, methods=['get'], url_path='tableau-bord')
    def tableau_bord(self, request):
        """Agrégat juridique de la société (NTJUR12).

        Le filtrage de confidentialité s'applique à l'agrégat : un rôle non
        autorisé obtient des totaux EXCLUANT les dossiers confidentiels.
        """
        return Response(selectors.tableau_bord_juridique(
            request.user.company, user=request.user))

    # ── NTJUR20 — timeline unifiée ──────────────────────────────────────────

    @extend_schema(responses=inline_serializer('JuridiqueTimeline', {
        'type': serializers.CharField(),
        'id': serializers.IntegerField(),
        'date': serializers.CharField(),
        'horodatage': serializers.CharField(),
        'libelle': serializers.CharField(),
        'detail': serializers.CharField(),
        'auteur': serializers.CharField(),
    }, many=True))
    @action(detail=True, methods=['get'], url_path='timeline')
    def timeline(self, request, pk=None):
        """Frise chronologique UNIQUE du dossier (NTJUR20).

        Chatter + audiences + délais + notes d'honoraires, déjà fusionnés et
        triés côté serveur : l'écran n'a aucun appel supplémentaire à faire ni
        aucun tri à refaire.
        """
        dossier = self.get_object()
        return Response(selectors.timeline_dossier(dossier))

    # ── NTJUR2 — machine à états procédurale ────────────────────────────────

    @action(detail=True, methods=['get'], url_path='statuts-suivants')
    def statuts_suivants(self, request, pk=None):
        """Statuts légalement atteignables depuis l'état courant (lecture)."""
        dossier = self.get_object()
        return Response({
            'statut': dossier.statut,
            'suivants': [
                {'valeur': str(v),
                 'libelle': DossierJuridique.Statut(v).label}
                for v in services.statuts_suivants(dossier)
            ],
        })

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Applique une transition GARDÉE. Corps : ``{statut, motif}``.

        Une transition hors machine renvoie 400 et laisse le dossier
        STRICTEMENT inchangé.
        """
        dossier = self.get_object()
        try:
            dossier = services.changer_statut(
                dossier, request.data.get('statut'), user=request.user,
                motif=(request.data.get('motif') or '').strip())
        except services.TransitionError as exc:
            return Response({'statut': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(DossierJuridiqueSerializer(dossier).data)

    @action(detail=True, methods=['post'], url_path='clore')
    def clore(self, request, pk=None):
        """Clôt le dossier. Corps : ``{statut_final, motif}``.

        NTJUR15 — si le dossier porte une provision comptabilisée, la clôture
        PROPOSE sa reprise (bannière) ; elle ne poste JAMAIS l'écriture.
        """
        dossier = self.get_object()
        try:
            dossier = services.clore_dossier(
                dossier, request.data.get('statut_final'), user=request.user,
                motif=(request.data.get('motif') or '').strip())
        except services.TransitionError as exc:
            return Response({'statut_final': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(DossierJuridiqueSerializer(dossier).data)

    # ── NTJUR15 — reprise de provision à la clôture (jamais automatique) ────

    @action(detail=True, methods=['post'], url_path='reprendre-provision',
            permission_classes=[
                ScopedPermission, HasPermissionOrLegacy('compta_saisir')])
    def reprendre_provision(self, request, pk=None):
        """Reprend (ou abandonne explicitement) la provision d'un dossier clos.

        Corps : ``{confirme: true, montant?}`` pour reprendre,
        ``{abandonner: true}`` pour éteindre la bannière SANS écriture.
        Sans l'un des deux : aucun effet, la réponse rappelle qu'une
        confirmation explicite est requise.
        """
        dossier = self.get_object()
        if request.data.get('abandonner'):
            services.abandonner_reprise_provision(dossier)
            return Response({'reprise_provision_traitee': True,
                             'provision_reprise': False})
        if not request.data.get('confirme'):
            return Response(
                {'confirme': ("Confirmez explicitement la reprise : aucune "
                              "écriture comptable n'est passée sans "
                              "confirmation.")},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            provision = services.reprendre_provision_dossier(
                dossier, montant=request.data.get('montant'),
                user=request.user)
        except services.ProvisionError as exc:
            return Response({'montant': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'reprise_provision_traitee': True,
            'provision_reprise': True,
            'provision_comptable_id': provision.id,
            'montant_repris': str(provision.montant_repris),
        })

    # ── NTJUR14 — provision pour risque PROPOSÉE (jamais automatique) ───────

    @action(detail=True, methods=['post'], url_path='proposer-provision',
            permission_classes=[
                ScopedPermission, HasPermissionOrLegacy('compta_saisir')])
    def proposer_provision(self, request, pk=None):
        """Propose (et, sur confirmation, comptabilise) la provision du dossier.

        Corps : ``{montant, motif, date_dotation, confirme}``. SANS
        ``confirme`` vrai, la réponse est un APERÇU et AUCUNE écriture n'est
        postée — c'est le patron « propose → confirme » du dépôt : aucune
        écriture comptable ne naît d'un simple changement d'état juridique.
        Réservée au palier comptable/Administrateur (``compta_saisir``).
        """
        from django.core.exceptions import ValidationError

        dossier = self.get_object()
        montant = request.data.get('montant')
        motif = (request.data.get('motif') or '').strip()
        date_dotation = request.data.get('date_dotation') or None
        apercu = services.apercu_provision(
            dossier, montant=montant, motif=motif,
            date_dotation=date_dotation)
        if not request.data.get('confirme'):
            return Response(
                {
                    'confirme': ("Confirmez explicitement la dotation : "
                                 "aucune écriture comptable n'est passée sans "
                                 "confirmation."),
                    'apercu': apercu,
                },
                status=status.HTTP_400_BAD_REQUEST)
        try:
            provision = services.proposer_provision(
                dossier, montant=montant, motif=motif,
                date_dotation=date_dotation, user=request.user)
        except services.ProvisionError as exc:
            return Response({'montant': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as exc:
            return Response(
                {'montant': getattr(exc, 'messages', [str(exc)])},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'provision_comptable_id': provision.id,
                'reference': provision.reference,
                'montant': str(provision.montant_dotation),
            },
            status=status.HTTP_201_CREATED)

    # ── NTJUR19 — workflow d'approbation d'un engagement juridique ──────────

    def _mandat_du_dossier(self, request, dossier):
        """Mandat visé par le corps (``{"mandat": id}``), borné au dossier."""
        mandat_id = request.data.get('mandat')
        if not mandat_id:
            return None, Response(
                {'mandat': "Indiquez le mandat concerné."},
                status=status.HTTP_400_BAD_REQUEST)
        mandat = MandatAvocat.objects.filter(
            company=request.user.company, dossier=dossier,
            pk=mandat_id).first()
        if mandat is None:
            return None, Response(
                {'mandat': "Ce mandat n'appartient pas à ce dossier."},
                status=status.HTTP_404_NOT_FOUND)
        return mandat, None

    def _etape_du_dossier(self, request, dossier):
        """Étape visée par le corps (``{"etape": id}``), bornée au dossier."""
        etape_id = request.data.get('etape')
        if not etape_id:
            return None, Response(
                {'etape': "Indiquez l'étape d'approbation concernée."},
                status=status.HTTP_400_BAD_REQUEST)
        etape = EtapeApprobationJuridique.objects.filter(
            company=request.user.company, mandat__dossier=dossier,
            pk=etape_id).select_related('mandat').first()
        if etape is None:
            return None, Response(
                {'etape': "Cette étape n'appartient pas à ce dossier."},
                status=status.HTTP_404_NOT_FOUND)
        return etape, None

    @action(detail=True, methods=['post'], url_path='lancer-approbation-mandat')
    def lancer_approbation_mandat(self, request, pk=None):
        """Instancie le workflow d'approbation d'un mandat (NTJUR19).

        Corps : ``{"mandat": <id>}``. 400 (message FR nommant le champ) si
        aucune règle ne couvre le montant engagé ou si le workflow existe déjà.
        """
        dossier = self.get_object()
        mandat, erreur = self._mandat_du_dossier(request, dossier)
        if erreur is not None:
            return erreur
        # NTJUR40 — désignation optionnelle des approbateurs, dans l'ordre des
        # étapes. Bornée à la société (jamais un utilisateur d'une autre).
        designes = []
        modele_utilisateur = get_user_model()
        for user_id in (request.data.get('approbateurs') or []):
            user = modele_utilisateur.objects.filter(
                pk=user_id, company=request.user.company).first()
            if user is None:
                return Response(
                    {'approbateurs': "Un approbateur désigné n'appartient pas "
                                     "à votre société."},
                    status=status.HTTP_400_BAD_REQUEST)
            designes.append(user)
        try:
            etapes = services.lancer_approbation_mandat(
                mandat, approbateurs=designes)
        except services.ApprobationError as exc:
            return Response({'mandat': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(
            EtapeApprobationJuridiqueSerializer(etapes, many=True).data,
            status=status.HTTP_201_CREATED)

    def _decider(self, request, decideur):
        """Corps commun des deux actions de décision (NTJUR19/NTJUR40)."""
        dossier = self.get_object()
        etape, erreur = self._etape_du_dossier(request, dossier)
        if erreur is not None:
            return erreur
        try:
            etape = decideur(
                etape, approbateur=request.user,
                commentaire=(request.data.get('commentaire') or '').strip())
        except services.ApprobationInterditeError as exc:
            # NTJUR40 — l'acteur n'a pas le droit (403), la transition ELLE
            # serait légale : jamais un 400 qui ferait croire à une saisie
            # fautive.
            return Response({'etape': str(exc)},
                            status=status.HTTP_403_FORBIDDEN)
        except services.ApprobationError as exc:
            return Response({'etape': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(EtapeApprobationJuridiqueSerializer(etape).data)

    @action(detail=True, methods=['post'], url_path='approuver-etape',
            permission_classes=[
                ScopedPermission,
                HasPermissionOrLegacy('juridique_approuver_engagement')])
    def approuver_etape(self, request, pk=None):
        """Approuve l'étape en attente d'un mandat. Corps : ``{"etape": <id>}``.

        NTJUR40 — exige ``juridique_approuver_engagement`` en plus de
        l'écriture du module : être nommé dans l'étape ne suffit pas.
        """
        return self._decider(request, services.approuver_etape)

    @action(detail=True, methods=['post'], url_path='rejeter-etape',
            permission_classes=[
                ScopedPermission,
                HasPermissionOrLegacy('juridique_approuver_engagement')])
    def rejeter_etape(self, request, pk=None):
        """Rejette une étape : le mandat retombe en ``brouillon``.

        Même garde que l'approbation (NTJUR40) : rejeter un engagement est une
        décision d'approbation, pas une simple écriture.
        """
        return self._decider(request, services.rejeter_etape)

    @action(detail=True, methods=['get'], url_path='etapes-approbation')
    def etapes_approbation(self, request, pk=None):
        """Étapes d'approbation de TOUS les mandats du dossier (lecture)."""
        dossier = self.get_object()
        etapes = EtapeApprobationJuridique.objects.filter(
            company=request.user.company, mandat__dossier=dossier
        ).order_by('mandat_id', 'niveau', 'id')
        return Response(
            EtapeApprobationJuridiqueSerializer(etapes, many=True).data)


class CabinetAvocatViewSet(CompanyScopedModelViewSet):
    """Registre des cabinets/avocats externes de la société (NTJUR9)."""

    queryset = CabinetAvocat.objects.all()
    serializer_class = CabinetAvocatSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'barreau', 'specialites']
    ordering_fields = ['nom', 'id', 'taux_horaire_moyen']
    read_permission = 'juridique_voir'
    write_permission = 'juridique_gerer'


class MandatAvocatViewSet(CompanyScopedModelViewSet):
    """Mandats confiés aux cabinets, par dossier (NTJUR10/NTJUR19)."""

    queryset = MandatAvocat.objects.select_related(
        'dossier', 'cabinet').all()
    serializer_class = MandatAvocatSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_mandat', 'statut']
    read_permission = 'juridique_voir'
    write_permission = 'juridique_gerer'

    def get_queryset(self):
        """Scope société + ``?dossier=`` ; jamais les mandats d'un dossier
        confidentiel invisible à l'appelant (la confidentialité du dossier
        gouverne aussi ses pièces financières)."""
        qs = super().get_queryset()
        user = self.request.user
        if not selectors.peut_voir_confidentiel(user):
            qs = qs.exclude(
                dossier__confidentialite=(
                    DossierJuridique.NiveauConfidentialite.CONFIDENTIEL))
        dossier_id = self.request.query_params.get('dossier')
        if dossier_id:
            qs = qs.filter(dossier_id=dossier_id)
        return qs

    @action(detail=True, methods=['post'], url_path='activer')
    def activer(self, request, pk=None):
        """Active le mandat — refusé tant que l'approbation requise manque."""
        mandat = self.get_object()
        try:
            mandat = services.activer_mandat(mandat)
        except services.ApprobationError as exc:
            return Response({'statut': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(MandatAvocatSerializer(mandat).data)


class _DossierScopedViewSet(CompanyScopedModelViewSet):
    """Base des objets rattachés à un dossier : scope société + héritage de la
    CONFIDENTIALITÉ du dossier (ses pièces suivent le dossier) + ``?dossier=``.
    """

    read_permission = 'juridique_voir'
    write_permission = 'juridique_gerer'
    #: Chemin d'accès au dossier depuis le modèle (ORM lookup).
    chemin_dossier = 'dossier'

    def get_queryset(self):
        qs = super().get_queryset()
        if not selectors.peut_voir_confidentiel(self.request.user):
            qs = qs.exclude(**{
                f'{self.chemin_dossier}__confidentialite':
                    DossierJuridique.NiveauConfidentialite.CONFIDENTIEL})
        dossier_id = self.request.query_params.get('dossier')
        if dossier_id:
            qs = qs.filter(**{f'{self.chemin_dossier}_id': dossier_id})
        return qs


class AudienceViewSet(_DossierScopedViewSet):
    """Audiences d'un dossier (NTJUR5)."""

    queryset = Audience.objects.select_related('dossier').all()
    serializer_class = AudienceSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_audience', 'id']

    @action(detail=True, methods=['post'], url_path='reporter')
    def reporter(self, request, pk=None):
        """Reporte l'audience : l'ancienne devient ``reportee``, une NOUVELLE
        ligne est créée (l'historique de la première est préservé)."""
        audience = self.get_object()
        try:
            nouvelle = services.reporter_audience(
                audience,
                request.data.get('date_audience'),
                heure=request.data.get('heure'),
                juridiction_salle=request.data.get('juridiction_salle'),
                motif=(request.data.get('motif') or '').strip())
        except services.TransitionError as exc:
            return Response({'date_audience': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(AudienceSerializer(nouvelle).data,
                        status=status.HTTP_201_CREATED)


class DelaiPrescriptionViewSet(_DossierScopedViewSet):
    """Délais procéduraux (NTJUR4). ``date_limite`` posée côté serveur."""

    queryset = DelaiPrescription.objects.select_related('dossier').all()
    serializer_class = DelaiPrescriptionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_limite', 'id']

    def _date_limite(self, serializer, instance=None):
        declenchement = serializer.validated_data.get(
            'date_declenchement',
            getattr(instance, 'date_declenchement', None))
        duree = serializer.validated_data.get(
            'duree_jours', getattr(instance, 'duree_jours', 0))
        return services.calculer_date_limite(
            self.request.user.company, declenchement, duree)

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company,
                        date_limite=self._date_limite(serializer))

    def perform_update(self, serializer):
        serializer.save(
            company=self.request.user.company,
            date_limite=self._date_limite(serializer, serializer.instance))

    @action(detail=False, methods=['get'], url_path='expirants')
    def expirants(self, request):
        """Délais encore ``en_cours`` dont la limite tombe dans ``?within=N``
        jours (défaut 30)."""
        from datetime import timedelta

        from django.utils import timezone

        try:
            within = int(request.query_params.get('within') or 30)
        except (TypeError, ValueError):
            within = 30
        aujourdhui = timezone.localdate()
        qs = self.get_queryset().filter(
            statut=DelaiPrescription.Statut.EN_COURS,
            date_limite__lte=aujourdhui + timedelta(days=within),
        ).order_by('date_limite', 'id')
        return Response(DelaiPrescriptionSerializer(qs, many=True).data)


class NoteHonorairesViewSet(_DossierScopedViewSet):
    """Notes d'honoraires reçues des cabinets (NTJUR11)."""

    queryset = NoteHonoraires.objects.select_related(
        'mandat', 'mandat__dossier').all()
    serializer_class = NoteHonorairesSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_facture', 'id']
    chemin_dossier = 'mandat__dossier'

    def get_queryset(self):
        qs = super().get_queryset()
        mandat_id = self.request.query_params.get('mandat')
        if mandat_id:
            qs = qs.filter(mandat_id=mandat_id)
        return qs

    def perform_create(self, serializer):
        """Référence anti-collision posée côté serveur (``NHJ-AAAAMM-NNNN``)."""
        from core.numbering import create_with_reference

        company = self.request.user.company
        create_with_reference(
            NoteHonoraires, 'NHJ', company,
            lambda reference: serializer.save(
                company=company, reference=reference))

    def _changer_statut(self, request, cible):
        note = self.get_object()
        note.statut = cible
        note.save(update_fields=['statut', 'updated_at'])
        return Response(NoteHonorairesSerializer(note).data)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valide la note : elle entre alors dans le budget CONSOMMÉ."""
        return self._changer_statut(request, NoteHonoraires.Statut.VALIDEE)

    @action(detail=True, methods=['post'], url_path='marquer-payee')
    def marquer_payee(self, request, pk=None):
        """Marque la note payée. Le paiement RÉEL reste un flux fournisseur
        (module achats) — cette action ne fait que tracer."""
        return self._changer_statut(request, NoteHonoraires.Statut.PAYEE)


class RegleApprobationJuridiqueViewSet(CompanyScopedModelViewSet):
    """Règles d'approbation des engagements de dépenses juridiques (NTJUR19)."""

    queryset = RegleApprobationJuridique.objects.all()
    serializer_class = RegleApprobationJuridiqueSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['priorite', 'id']
    read_permission = 'juridique_voir'
    write_permission = 'juridique_gerer'
