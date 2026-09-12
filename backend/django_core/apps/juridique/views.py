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
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import HasPermissionOrLegacy
from core.permissions import ScopedPermission
from core.viewsets import CompanyScopedModelViewSet

from . import selectors, services
from .models import (
    CabinetAvocat, DossierJuridique, EtapeApprobationJuridique, MandatAvocat,
    RegleApprobationJuridique,
)
from .serializers import (
    CabinetAvocatSerializer, DossierJuridiqueSerializer,
    EtapeApprobationJuridiqueSerializer, MandatAvocatSerializer,
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


class RegleApprobationJuridiqueViewSet(CompanyScopedModelViewSet):
    """Règles d'approbation des engagements de dépenses juridiques (NTJUR19)."""

    queryset = RegleApprobationJuridique.objects.all()
    serializer_class = RegleApprobationJuridiqueSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['priorite', 'id']
    read_permission = 'juridique_voir'
    write_permission = 'juridique_gerer'
