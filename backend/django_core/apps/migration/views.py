"""Viewsets DRF du groupe NTMIG.

Accès réservé au palier Administrateur/Directeur (``menu_tier == 'admin'`` —
les deux rôles système y sont mappés, le superuser aussi). ``company`` est
TOUJOURS forcée côté serveur (``CompanyScopedModelViewSet``) ; ``cree_par``
est posé côté serveur en création, jamais lu du corps de requête.
"""
import logging

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView

from authentication.models import CustomUser
from core.viewsets import CompanyScopedModelViewSet

from . import services
from .serializers import ScoreCertificationSerializer
from .models import (
    DeploiementPartenaire, LotMigration, PlaybookInstance, ProjetMigration)
from .serializers import (
    DeploiementPartenaireSerializer, LotMigrationSerializer,
    PlaybookInstanceSerializer, ProjetMigrationSerializer,
    RapportReconciliationSerializer)

logger = logging.getLogger(__name__)


def _drapeau(valeur):
    """Booléen tolérant au multipart (où tout arrive en chaîne de caractères).

    Sans cette conversion, la chaîne ``'false'`` d'un formulaire serait
    « vraie » en Python et ferait écarter des lignes que l'utilisateur voulait
    charger.
    """
    if isinstance(valeur, str):
        return valeur.strip().lower() in ('1', 'true', 'vrai', 'oui', 'on')
    return bool(valeur)


def _fichier_de(request):
    """Récupère le fichier téléversé (multipart) → (octets, nom)."""
    fichier = request.FILES.get('fichier') or request.FILES.get('file')
    if fichier is None:
        raise ValidationError({'fichier': 'Fichier source requis.'})
    return fichier.read(), fichier.name


class IsDirecteurOuAdmin(BasePermission):
    """Palier Administrateur OU Directeur uniquement, comptes INTERNES.

    Les deux rôles système sont mappés au palier ``admin`` (``menu_tier``, qui
    renvoie déjà ``admin`` pour un superuser) ; le Responsable et l'Utilisateur
    limité sont exclus. Une migration réécrit des données métier en masse : ce
    n'est pas une action d'utilisateur courant.

    Le contrôle de PORTÉE est refait ici : cette classe remplace le
    ``ScopedPermission`` par défaut, qui est le seul endroit où l'exclusion des
    comptes de portail est appliquée. Sans ce rappel, un compte portail portant
    un rôle large passerait la garde.
    """

    message = 'Action réservée aux Administrateurs et Directeurs internes.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if getattr(user, 'portee', CustomUser.PORTEE_INTERNE) != \
                CustomUser.PORTEE_INTERNE:
            return False
        return getattr(user, 'menu_tier', None) == CustomUser.ROLE_ADMIN


class ProjetMigrationViewSet(CompanyScopedModelViewSet):
    """Conteneur d'une migration : CRUD + clôture gardée (NTMIG5)."""

    queryset = ProjetMigration.objects.select_related('cree_par').all()
    serializer_class = ProjetMigrationSerializer
    permission_classes = [IsDirecteurOuAdmin]

    @action(detail=True, methods=['get'], url_path='rapport', permission_classes=[IsDirecteurOuAdmin])
    def rapport(self, request, pk=None):
        """NTMIG19 — PV de migration en PDF (synthèse par lot).

        ``get_object()`` applique le queryset scopé société : un projet d'une
        autre société renvoie 404, jamais son PV.
        """
        from django.http import HttpResponse

        from .pdf_rapport import render_rapport_migration_pdf

        projet = self.get_object()
        pdf = render_rapport_migration_pdf(projet)
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="pv-migration-{projet.pk}.pdf"')
        return resp

    @action(detail=True, methods=['get'], url_path='estimation', permission_classes=[IsDirecteurOuAdmin])
    def estimation(self, request, pk=None):
        """NTMIG34 — estimation d'effort + checklist des points d'attention.

        Lecture seule et purement indicative : elle ne conditionne ni un
        chargement ni une clôture.
        """
        projet = self.get_object()
        return Response(services.estimer_effort(projet))

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            cree_par=self.request.user)

    def perform_destroy(self, instance):
        """Un projet clôturé n'est pas supprimable.

        La suppression cascaderait sur ses lots ET sur leurs rapports de
        réconciliation : la pièce justificative remise au client migré
        disparaîtrait en une requête. Un projet terminé se garde.
        """
        if instance.statut == ProjetMigration.Statut.TERMINE:
            raise ValidationError({'detail': (
                'Projet clôturé : sa suppression effacerait les rapports de '
                'réconciliation qui en sont la preuve. Non supprimable.')})
        super().perform_destroy(instance)

    @action(detail=True, methods=['post'], url_path='migrer-a-blanc', permission_classes=[IsDirecteurOuAdmin])
    def migrer_a_blanc(self, request, pk=None):
        """NTMIG33 — rejoue le projet sur le tenant SANDBOX (NTADM10).

        Sans sandbox provisionné : 400 explicite, rien n'est créé. La
        production n'est jamais touchée — le service refuse d'écrire si la
        société sandbox se confond avec celle du projet.
        """
        projet = self.get_object()
        try:
            rapport = services.migrer_a_blanc(projet, user=request.user)
        except services.SandboxIndisponible as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(rapport)

    @action(detail=True, methods=['post'], url_path='terminer', permission_classes=[IsDirecteurOuAdmin])
    def terminer(self, request, pk=None):
        """NTMIG5 — clôture gardée.

        400 + la liste des écarts bloquants (par lot) si un lot n'est pas
        réconcilié conforme ou dérogé ; le projet reste alors intact.
        """
        projet = self.get_object()
        try:
            services.terminer_projet(projet, user=request.user)
        except services.ReconcileBloque as exc:
            return Response(
                {'detail': str(exc), 'ecarts': exc.ecarts},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(ProjetMigrationSerializer(projet).data)


class LotMigrationViewSet(CompanyScopedModelViewSet):
    """Un lot par entité : analyse → chargement → réconciliation → clôture."""

    queryset = LotMigration.objects.select_related(
        'projet', 'derogation_par').all()
    serializer_class = LotMigrationSerializer
    permission_classes = [IsDirecteurOuAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs

    def perform_create(self, serializer):
        projet = serializer.validated_data['projet']
        # Le projet cité doit appartenir à la société de l'appelant : sans ce
        # contrôle, un lot d'une société pourrait se greffer sur le projet
        # d'une autre (le queryset scopé ne protège que la lecture).
        if projet.company_id != self.request.user.company_id:
            raise ValidationError({'projet': 'Projet introuvable.'})
        serializer.save(company=self.request.user.company)

    def perform_destroy(self, instance):
        """Un lot qui a réellement chargé des données n'est pas supprimable.

        Ses rapports partiraient avec lui (cascade), et avec eux la seule trace
        reliant les enregistrements importés à ce lot : plus rien ne
        permettrait ensuite de dire ce qui a été migré, ni d'annuler le lot.
        """
        if (instance.statut == LotMigration.Statut.RECONCILIE
                or instance.import_job_id is not None):
            raise ValidationError({'detail': (
                'Ce lot a chargé des données : le supprimer effacerait sa '
                'traçabilité et ses rapports. Non supprimable.')})
        super().perform_destroy(instance)

    @action(detail=True, methods=['post'], url_path='analyser', permission_classes=[IsDirecteurOuAdmin])
    def analyser(self, request, pk=None):
        """Analyse DRY-RUN du fichier source : rien n'est écrit en cible.

        Renvoie l'aperçu ``dataimport`` (mapping, comptages, et surtout les
        ``conflits``/``ecrasements_*`` : ce que le fichier toucherait sur des
        fiches déjà remplies) et pose les comptages source sur le lot.
        """
        lot = self.get_object()
        file_bytes, filename = _fichier_de(request)
        try:
            apercu = services.analyser_lot(
                lot, file_bytes, filename,
                mapping_name=request.data.get('mapping_name') or None)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(apercu)

    @action(detail=True, methods=['post'], url_path='valider-source', permission_classes=[IsDirecteurOuAdmin])
    def valider_source(self, request, pk=None):
        """NTMIG32 — qualité de la SOURCE avant chargement.

        Renvoie le nombre de lignes valides/invalides, les motifs, et les
        NUMÉROS des lignes fautives : l'écran peut alors proposer de charger
        sans elles (``ignorer_lignes_invalides`` sur ``charger``). N'écrit
        rien — ni en base cible, ni sur le lot.
        """
        lot = self.get_object()
        file_bytes, filename = _fichier_de(request)
        try:
            rapport = services.valider_source(
                lot, file_bytes, filename,
                kit_cle=request.data.get('kit') or None,
                mapping_name=request.data.get('mapping_name') or None)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(rapport)

    @action(detail=True, methods=['post'], url_path='charger', permission_classes=[IsDirecteurOuAdmin])
    def charger(self, request, pk=None):
        """NTMIG15 — chargement délégué à ``dataimport``.

        ``external_system`` = ``migration:<source>`` (rejeu idempotent) et
        REMPLISSAGE SEUL : l'API n'expose délibérément aucun interrupteur
        d'écrasement — une migration n'efface jamais une valeur déjà saisie.
        """
        lot = self.get_object()
        file_bytes, filename = _fichier_de(request)
        exclues = []
        try:
            if _drapeau(request.data.get('ignorer_lignes_invalides')):
                # NTMIG32 — on RE-valide côté serveur au lieu de croire une
                # liste de numéros envoyée par le client : le fichier chargé
                # peut ne pas être celui qui a été validé, et écarter des
                # lignes sur parole ferait disparaître des données sans motif
                # traçable.
                rapport = services.valider_source(
                    lot, file_bytes, filename,
                    kit_cle=request.data.get('kit') or None,
                    mapping_name=request.data.get('mapping_name') or None)
                exclues = rapport['lignes_invalides_numeros']
                if exclues:
                    file_bytes, filename = services.fichier_sans_lignes(
                        file_bytes, filename, exclues)
            result = services.charger_lot(
                lot, file_bytes, filename,
                # Le mode demandé est FILTRÉ par le service : « creer » ne
                # rapproche rien et ferait des doublons à chaque passe, il
                # n'est jamais accepté depuis une requête.
                mode=request.data.get('mode') or None,
                mapping_name=request.data.get('mapping_name') or None,
                user=request.user)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        if exclues:
            # Les lignes écartées ne disparaissent pas en silence : elles sont
            # journalisées et restent listées (numéro + motif) par
            # `valider-source`, dont la réponse est le contrat de référence —
            # la forme de CETTE réponse-ci ne bouge pas (contrat d'API).
            logger.info(
                'NTMIG32 — lot %s : %s ligne(s) source écartée(s) avant '
                'chargement (%s).', lot.pk, len(exclues), exclues[:20])
        return Response({
            'lot': LotMigrationSerializer(lot).data, 'resultat': result})

    @action(detail=True, methods=['post'], url_path='reprendre', permission_classes=[IsDirecteurOuAdmin])
    def reprendre(self, request, pk=None):
        """NTMIG38 — reprise d'un lot interrompu, sans doublon.

        Sans fichier joint, reprend le fichier MÉMORISÉ au dernier chargement
        (NTMIG35) ; 400 explicite s'il a été purgé ou s'il n'y a rien à
        reprendre.
        """
        lot = self.get_object()
        file_bytes, filename = None, None
        if request.FILES.get('fichier') or request.FILES.get('file'):
            file_bytes, filename = _fichier_de(request)
        try:
            rapport = services.reprendre_lot(
                lot, file_bytes, filename,
                mapping_name=request.data.get('mapping_name') or None,
                user=request.user)
        except services.RepriseImpossible as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response({
            'lot': LotMigrationSerializer(lot).data, 'reprise': rapport})

    @action(detail=True, methods=['post'], url_path='charger-odoo', permission_classes=[IsDirecteurOuAdmin])
    def charger_odoo(self, request, pk=None):
        """NTMIG9 — chargement via le connecteur Odoo JSON-2 (gated).

        Sans connecteur configuré : 400 explicite proposant l'import fichier.
        Le connecteur, quand il existe, est appelé en LECTURE SEULE ; aucune
        écriture n'est jamais faite côté Odoo (règle #1).
        """
        lot = self.get_object()
        try:
            services.charger_depuis_odoo_api(
                lot, params=request.data, user=request.user)
        except services.ConnecteurNonConfigure as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(LotMigrationSerializer(lot).data)

    @action(detail=True, methods=['post'], url_path='reconcilier', permission_classes=[IsDirecteurOuAdmin])
    def reconcilier(self, request, pk=None):
        """Produit le rapport de réconciliation du lot (source vs cible)."""
        lot = self.get_object()
        rapport = services.reconcilier_lot(lot)
        return Response(RapportReconciliationSerializer(rapport).data)

    @action(detail=True, methods=['post'], url_path='deroger', permission_classes=[IsDirecteurOuAdmin])
    def deroger(self, request, pk=None):
        """NTMIG5 — dérogation motivée : autorise la clôture d'un lot non
        conforme, en laissant une trace attribuée (qui/quand/pourquoi)."""
        lot = self.get_object()
        try:
            services.deroger_reconcile(
                lot, request.data.get('motif', ''), request.user)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(LotMigrationSerializer(lot).data)

    @action(detail=True, methods=['post'], url_path='terminer', permission_classes=[IsDirecteurOuAdmin])
    def terminer(self, request, pk=None):
        """NTMIG5 — passe CE lot en ``reconcilie``, ou 400 + écarts."""
        lot = self.get_object()
        try:
            services.marquer_lot_termine(lot, user=request.user)
        except services.ReconcileBloque as exc:
            return Response(
                {'detail': str(exc), 'ecarts': exc.ecarts},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(LotMigrationSerializer(lot).data)


class PlaybookInstanceViewSet(CompanyScopedModelViewSet):
    """NTMIG22 — checklist de déploiement instanciée depuis un playbook kb.

    La création passe par l'action ``instancier`` (elle a besoin du playbook
    source pour figer l'instantané d'étapes) ; un POST direct sur la liste est
    refusé plutôt que de créer une checklist vide qu'aucune étape ne
    remplirait jamais.
    """

    queryset = PlaybookInstance.objects.select_related(
        'projet_migration', 'responsable').all()
    serializer_class = PlaybookInstanceSerializer
    permission_classes = [IsDirecteurOuAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_migration_id=projet)
        article = self.request.query_params.get('playbook')
        if article:
            qs = qs.filter(playbook_article_id=article)
        return qs

    def create(self, request, *args, **kwargs):
        raise ValidationError({'detail': (
            'Utilisez POST playbook-instances/instancier/ avec le playbook '
            'à instancier : une instance sans étapes ne serait pas cochable.')})

    @action(detail=False, methods=['post'], url_path='instancier', permission_classes=[IsDirecteurOuAdmin])
    def instancier(self, request):
        """Instancie un playbook kb pour un déploiement.

        Le playbook est résolu par ``kb.selectors`` (scopé société + type
        ``playbook``) : un article d'une autre société, ou un article
        ordinaire, est introuvable — jamais instanciable.
        """
        from apps.kb import selectors as kb_selectors

        article = kb_selectors.playbook_par_id(
            request.data.get('playbook_article'), request.user.company)
        if article is None:
            raise ValidationError({'playbook_article': (
                'Playbook introuvable pour cette société.')})

        projet = None
        projet_id = request.data.get('projet_migration')
        if projet_id:
            projet = ProjetMigration.objects.filter(
                pk=projet_id, company=request.user.company).first()
            if projet is None:
                raise ValidationError(
                    {'projet_migration': 'Projet introuvable.'})

        responsable = None
        responsable_id = request.data.get('responsable')
        if responsable_id:
            responsable = CustomUser.objects.filter(
                pk=responsable_id, company=request.user.company).first()
            if responsable is None:
                raise ValidationError(
                    {'responsable': 'Responsable introuvable.'})

        try:
            instance = services.instancier_playbook(
                article,
                company=request.user.company,
                projet_migration=projet,
                responsable=responsable,
                client_final=request.data.get('client_final') or '')
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(
            PlaybookInstanceSerializer(instance).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='cocher', permission_classes=[IsDirecteurOuAdmin])
    def cocher(self, request, pk=None):
        """Coche (``fait`` absent ou vrai) ou décoche une étape."""
        instance = self.get_object()
        fait = request.data.get('fait', True)
        if isinstance(fait, str):
            fait = fait.lower() not in ('false', '0', 'non', '')
        try:
            services.cocher_etape(
                instance, request.data.get('cle'), fait=bool(fait))
        except services.EtapeInconnue as exc:
            raise ValidationError({'cle': str(exc)})
        return Response(PlaybookInstanceSerializer(instance).data)

    @action(detail=True, methods=['post'], url_path='terminer', permission_classes=[IsDirecteurOuAdmin])
    def terminer(self, request, pk=None):
        """Clôture l'instance — 400 + étapes restantes si incomplète."""
        instance = self.get_object()
        try:
            services.terminer_playbook(instance)
        except services.ReconcileBloque as exc:
            return Response(
                {'detail': str(exc), 'etapes_restantes': exc.ecarts},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(PlaybookInstanceSerializer(instance).data)


class DeploiementPartenaireViewSet(CompanyScopedModelViewSet):
    """NTMIG28 — qui a déployé quoi, chez quel client final.

    Chaque écriture RÉALIGNE le compteur miroir de la fiche partenaire (via
    ``crm.services``) : le compteur est recompté, jamais incrémenté — un
    déploiement repassé en ``abandonne`` ou supprimé doit le faire BAISSER.
    """

    queryset = DeploiementPartenaire.objects.select_related(
        'partenaire', 'projet_migration').all()
    serializer_class = DeploiementPartenaireSerializer
    permission_classes = [IsDirecteurOuAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        partenaire = self.request.query_params.get('partenaire')
        if partenaire:
            qs = qs.filter(partenaire_id=partenaire)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        deploiement = serializer.save(company=self.request.user.company)
        services.resynchroniser_compteur_partenaire(deploiement)

    def perform_update(self, serializer):
        avant = serializer.instance.partenaire_id
        deploiement = serializer.save()
        services.resynchroniser_compteur_partenaire(deploiement)
        # Un déploiement RÉATTRIBUÉ doit aussi décompter l'ancien partenaire,
        # sinon son historique reste crédité d'un déploiement qui ne lui
        # appartient plus.
        if avant and avant != deploiement.partenaire_id:
            from apps.crm import services as crm_services
            crm_services.poser_compteur_deploiements(
                avant, deploiement.company,
                services.compter_deploiements_reussis(
                    avant, deploiement.company))

    def perform_destroy(self, instance):
        partenaire_id, company = instance.partenaire_id, instance.company
        super().perform_destroy(instance)
        if partenaire_id:
            from apps.crm import services as crm_services
            crm_services.poser_compteur_deploiements(
                partenaire_id, company,
                services.compter_deploiements_reussis(partenaire_id, company))


class ScoreCertificationView(GenericAPIView):
    """NTMIG27 — score de certification PROPOSÉ pour un partenaire.

    LECTURE SEULE, et volontairement : le niveau reste attribué manuellement
    sur la fiche partenaire (PATCH ``partenaires/<id>/``). Cet endpoint dit ce
    que le barème suggère, il ne promeut personne.

    Le partenaire est résolu via ``crm.selectors`` (scopé société) : celui
    d'une autre société est introuvable — 404, jamais son score.
    """

    permission_classes = [IsDirecteurOuAdmin]
    # Forme DÉCLARÉE (pas devinée) — cf. `check_openapi_schema`.
    serializer_class = ScoreCertificationSerializer

    def get_queryset(self):
        """Partenaires de la SOCIÉTÉ de l'appelant, jamais au-delà.

        Passe par le selector `crm` (lecture seule, scopé société) — jamais
        un import des modèles d'une autre app métier. Rend le périmètre
        VÉRIFIABLE par la garde d'isolation (YDATA21) au lieu de le laisser
        implicite dans le corps de `get`.
        """
        from apps.crm import selectors as crm_selectors

        return crm_selectors.partenaires_certifies_qs(
            self.request.user.company)

    def get(self, request, partenaire_id):
        from apps.crm import selectors as crm_selectors

        from .certification import calculer_score_certification

        partenaire = crm_selectors.partenaire_pour_certification(
            request.user.company, partenaire_id)
        if partenaire is None:
            return Response(
                {'detail': 'Partenaire introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response(calculer_score_certification(partenaire))
