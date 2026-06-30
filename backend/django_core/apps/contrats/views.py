"""Vues de la Gestion des contrats (scopées société, accès admin/responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; l'accès est réservé au palier Administrateur/Responsable
(``IsResponsableOrAdmin``).

Niveaux de confidentialité (CONTRAT6)
--------------------------------------
La visibilité d'un ``Contrat`` est réglée par son champ ``confidentialite`` :

- ``PUBLIC``       : visible par tous les utilisateurs authentifiés de la société
                     qui ont accès au module (responsable + admin).
- ``INTERNE``      : même visibilité que PUBLIC au niveau du rôle — pas de
                     restriction supplémentaire au-dessus du filtre société.
- ``CONFIDENTIEL`` : visible uniquement par les Administrateurs.

Le filtre est appliqué dans ``ContratViewSet.get_queryset``.  Les filtres
``?confidentialite=`` permettent de restreindre la liste côté client.

ModeleContratViewSet (CONTRAT7)
--------------------------------
Bibliothèque de gabarits/modèles de contrats. Scopé société (TenantMixin).
Action ``/instancier/`` crée un ``Contrat`` pré-rempli depuis le gabarit.
"""
from django.http import HttpResponse
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import selectors, services
from .models import (
    Clause,
    ClauseContrat,
    Contrat,
    ContratLien,
    ModeleContrat,
    ModeleContratClause,
    PartieContrat,
    RegleApprobation,
    VersionContrat,
)
from .serializers import (
    ChangerStatutSerializer,
    ClauseContratSerializer,
    ClauseSerializer,
    ContratActivitySerializer,
    ContratLienSerializer,
    ContratSerializer,
    CreerVersionSerializer,
    DeciderEtapeSerializer,
    EtapeApprobationSerializer,
    InstancierContratSerializer,
    ModeleContratClauseSerializer,
    ModeleContratSerializer,
    NoterContratSerializer,
    PartieContratSerializer,
    RegleApprobationSerializer,
    RendreContratSerializer,
    ResoudreRegleApprobationSerializer,
    SignatureContratSerializer,
    SignerContratSerializer,
    VersionContratSerializer,
)


def _client_ip(request):
    """Adresse IP du client à partir de la requête (preuve de signature).

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


class _ContratsBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class ContratViewSet(_ContratsBaseViewSet):
    """Contrats de la société (CLM). Recherche par référence/objet.

    Visibilité par confidentialité : les contrats ``CONFIDENTIEL`` ne sont
    accessibles qu'aux Administrateurs. Les contrats ``PUBLIC``/``INTERNE``
    sont accessibles à tous les Responsables et Administrateurs de la société.
    Un filtre optionnel ``?confidentialite=<niveau>`` permet de restreindre
    la liste retournée.
    """
    queryset = Contrat.objects.all()
    serializer_class = ContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'objet']
    ordering_fields = ['date_debut', 'date_fin', 'montant', 'id', 'confidentialite']

    def get_queryset(self):
        """Queryset scopé société + filtre confidentialité.

        Les contrats ``CONFIDENTIEL`` sont exclus pour les non-Administrateurs.
        Un filtre optionnel ``?confidentialite=<valeur>`` restreint
        supplémentairement la liste.
        """
        qs = super().get_queryset()
        user = self.request.user
        # Exclure les contrats CONFIDENTIEL pour les non-Administrateurs.
        # Le palier FAISANT AUTORITÉ est ``menu_tier`` (dérive du Role FK, repli
        # legacy, et renvoie ROLE_ADMIN pour un superuser) — ``role_legacy``
        # seul n'est pas fiable pour un admin provisionné via le Role FK.
        if user.menu_tier != user.ROLE_ADMIN:
            qs = qs.exclude(
                confidentialite=Contrat.NiveauConfidentialite.CONFIDENTIEL)
        # Filtre optionnel par niveau de confidentialité.
        niveau = self.request.query_params.get('confidentialite')
        if niveau:
            qs = qs.filter(confidentialite=niveau)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    def perform_update(self, serializer):
        """Sauvegarde + audit du changement de confidentialité (CONTRAT15).

        Le ``statut`` n'est jamais modifié par PUT/PATCH direct (read-only au
        sérialiseur) ; sa transition est auditée par l'action ``changer-statut``.
        Ici on journalise uniquement un changement effectif de
        ``confidentialite`` (CONTRAT6), avec auteur et société posés côté serveur.
        """
        ancien = serializer.instance.confidentialite
        contrat = serializer.save()
        if contrat.confidentialite != ancien:
            services.journaliser_transition(
                contrat, field='confidentialite', old_value=ancien,
                new_value=contrat.confidentialite, auteur=self.request.user)

    @action(detail=False, methods=['get'])
    def preavis(self, request):
        """Contrats dont l'échéance de préavis approche (CONTRAT20).

        Liste, scopée société, les contrats dont la date limite de préavis
        (``date_fin − preavis_jours``) tombe dans les ``within`` prochains jours
        (défaut 30) et dont le préavis n'est pas encore traité — pour agir avant
        une éventuelle tacite reconduction. Ordonnés par urgence (échéance la
        plus proche d'abord). Lecture seule : ne change aucun statut.

        Le queryset passe par ``get_queryset`` (filtre confidentialité hérité),
        puis par le sélecteur — la société est toujours celle de l'utilisateur.
        """
        try:
            within = int(request.query_params.get('within', 30))
        except (TypeError, ValueError):
            within = 30
        base_ids = self.get_queryset().values_list('id', flat=True)
        qs = selectors.contrats_a_preavis(
            request.user.company, within_days=within
        ).filter(id__in=list(base_ids))
        return Response(
            ContratSerializer(
                qs, many=True, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='a-renouveler')
    def a_renouveler(self, request):
        """Contrats dont l'ÉCHÉANCE (``date_fin``) approche (CONTRAT21).

        Liste, scopée société, les contrats dont la date de fin tombe dans les
        ``within`` prochains jours (défaut 30) — ceux à RENOUVELER ou clôturer.
        Distinct de ``/preavis/`` (CONTRAT20) qui regarde la date limite de
        préavis (``date_fin − preavis_jours``) : ici on regarde la fin du
        contrat elle-même. Les contrats résiliés/expirés sont exclus ; un
        contrat en tacite reconduction RESTE listé (le drapeau
        ``tacite_reconduction`` du sérialiseur indique qu'il se reconduit seul).
        Ordonnés par échéance la plus proche d'abord. Lecture seule : ne change
        aucun statut.

        Le queryset passe par ``get_queryset`` (filtre confidentialité hérité),
        puis par le sélecteur — la société est toujours celle de l'utilisateur.
        """
        try:
            within = int(request.query_params.get('within', 30))
        except (TypeError, ValueError):
            within = 30
        base_ids = self.get_queryset().values_list('id', flat=True)
        qs = selectors.contrats_a_renouveler(
            request.user.company, within_days=within
        ).filter(id__in=list(base_ids))
        return Response(
            ContratSerializer(
                qs, many=True, context={'request': request}).data)

    @action(detail=True, methods=['get'])
    def liens(self, request, pk=None):
        """Liens du contrat ENRICHIS via les sélecteurs des apps cibles.

        Pour chaque lien : libellé frais quand l'app cible expose un sélecteur
        (``source='live'``), sinon le libellé stocké (``source='stored'``). La
        société est garantie par ``get_object`` (queryset scopé société).
        """
        contrat = self.get_object()
        return Response(selectors.liens_enrichis(contrat))

    @action(detail=True, methods=['post'], url_path='rendre')
    def rendre(self, request, pk=None):
        """Génère le texte du contrat par fusion de jetons (CONTRAT10).

        Fusionne les jetons ``{{ ... }}`` (champs du contrat, parties, clauses
        résolues) dans un gabarit : le ``gabarit`` fourni dans le corps, sinon
        le corps du ``ModeleContrat`` lié, sinon un gabarit par défaut. Lecture
        seule : ne persiste rien. La société est garantie par ``get_object``.
        """
        contrat = self.get_object()
        body = RendreContratSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        gabarit = body.validated_data.get('gabarit') or None
        return Response(services.rendre_contrat(contrat, gabarit=gabarit))

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        """Rendu PDF INTERNE du contrat — hors ``/proposal`` (CONTRAT11).

        PDF de travail interne (jamais un PDF de devis client : ``/proposal``
        reste l'unique chemin des PDF de devis). Fusionne le contrat
        (CONTRAT10) puis convertit le texte en PDF. La société est garantie par
        ``get_object`` (queryset scopé société).
        """
        contrat = self.get_object()
        pdf_bytes = services.rendre_contrat_pdf(contrat)
        filename = (contrat.reference or f'contrat-{contrat.id}') + '.pdf'
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Applique une transition de statut GARDÉE (CONTRAT12).

        Refuse (400) toute transition hors du graphe d'états ou un passage en
        approbation/signature sans au moins deux parties. La société est
        garantie par ``get_object``.
        """
        contrat = self.get_object()
        body = ChangerStatutSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        cible = body.validated_data['statut']
        ancien = contrat.statut
        try:
            services.changer_statut(contrat, cible)
        except services.TransitionInterdite as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # CONTRAT15 — audit de la transition de statut (sauf no-op). Auteur et
        # société posés côté serveur.
        if contrat.statut != ancien:
            services.journaliser_transition(
                contrat, field='statut', old_value=ancien,
                new_value=contrat.statut, auteur=request.user)
        return Response(
            ContratSerializer(contrat, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='statuts-suivants')
    def statuts_suivants(self, request, pk=None):
        """Liste des statuts cibles autorisés depuis le statut courant (CONTRAT12)."""
        contrat = self.get_object()
        return Response({
            'statut': contrat.statut,
            'suivants': services.statuts_suivants(contrat),
        })

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """Timeline du chatter (CONTRAT15) — du plus récent au plus ancien.

        Réunit les transitions auditées automatiques (statut, confidentialité,
        pas d'approbation) et les notes manuelles. La société est garantie par
        ``get_object`` (queryset scopé société).
        """
        contrat = self.get_object()
        return Response(
            ContratActivitySerializer(
                contrat.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter')
    def noter(self, request, pk=None):
        """Ajoute une note manuelle au chatter (CONTRAT15).

        Corps : ``message`` (requis, non vide). L'auteur est l'utilisateur
        courant et la société celle du contrat — tous deux posés côté serveur,
        jamais lus du corps de requête.
        """
        contrat = self.get_object()
        body = NoterContratSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        act = services.noter_contrat(
            contrat, message=body.validated_data['message'],
            auteur=request.user)
        return Response(
            ContratActivitySerializer(act).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='etapes-approbation')
    def etapes_approbation(self, request, pk=None):
        """Étapes du workflow d'approbation interne du contrat (CONTRAT14).

        Lecture seule, ordonnées par niveau. La société est garantie par
        ``get_object`` (queryset scopé société).
        """
        contrat = self.get_object()
        etapes = selectors.etapes_approbation(contrat)
        return Response(
            EtapeApprobationSerializer(
                etapes, many=True, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='lancer-approbation')
    def lancer_approbation(self, request, pk=None):
        """Lance le workflow d'approbation interne du contrat (CONTRAT14).

        Instancie les étapes depuis la ``RegleApprobation`` la plus spécifique
        (montant + type). Refuse (400) si un workflow est déjà en cours. Renvoie
        les étapes créées (liste vide si aucune règle ne couvre le contrat). Ne
        change AUCUN statut du contrat. La société est garantie par
        ``get_object``.
        """
        contrat = self.get_object()
        try:
            etapes = services.lancer_workflow_approbation(contrat)
        except services.ApprobationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # CONTRAT15 — audit du lancement du workflow d'approbation (CONTRAT14).
        services.journaliser_transition(
            contrat, field='approbation', old_value='',
            new_value=f'workflow lancé ({len(etapes)} étape(s))',
            auteur=request.user)
        return Response(
            EtapeApprobationSerializer(
                etapes, many=True, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='approuver-etape')
    def approuver_etape(self, request, pk=None):
        """Approuve une étape du workflow et le fait avancer (CONTRAT14).

        Corps : ``etape`` (id, requis), ``commentaire`` (optionnel).
        L'approbateur est l'utilisateur courant (posé côté serveur). Refuse
        (400) une étape hors séquence ou déjà décidée, (404) une étape d'un
        autre contrat/société. Ne change AUCUN statut du contrat.
        """
        return self._decider_etape(request, services.approuver_etape)

    @action(detail=True, methods=['post'], url_path='rejeter-etape')
    def rejeter_etape(self, request, pk=None):
        """Rejette une étape du workflow d'approbation (CONTRAT14).

        Mêmes garanties et corps que ``approuver-etape``. Ne change AUCUN statut
        du contrat.
        """
        return self._decider_etape(request, services.rejeter_etape)

    def _decider_etape(self, request, operation):
        """Logique partagée approuver/rejeter une étape (CONTRAT14).

        Résout l'étape DANS le contrat courant (scopé société par
        ``get_object``), applique l'opération gardée, et renvoie l'étape
        sérialisée. Toute erreur de workflow est rendue 400 ; une étape
        introuvable dans ce contrat est 404.
        """
        contrat = self.get_object()
        body = DeciderEtapeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        etape_id = body.validated_data['etape']
        commentaire = body.validated_data.get('commentaire', '')
        etape = contrat.etapes_approbation.filter(id=etape_id).first()
        if etape is None:
            return Response(
                {'detail': "Étape d'approbation introuvable pour ce contrat."},
                status=status.HTTP_404_NOT_FOUND)
        try:
            operation(
                etape, approbateur=request.user, commentaire=commentaire)
        except services.ApprobationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # CONTRAT15 — audit du pas de workflow (approbation/rejet d'une étape).
        # ``new_value`` porte le statut local de l'étape (approuve/rejete) ; le
        # commentaire éventuel est consigné en message.
        services.journaliser_transition(
            contrat, field='approbation',
            old_value=f'étape {etape.niveau} en attente',
            new_value=f'étape {etape.niveau} {etape.statut}',
            message=commentaire, auteur=request.user)
        return Response(
            EtapeApprobationSerializer(
                etape, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='signatures')
    def signatures(self, request, pk=None):
        """Signatures électroniques IN-APP du contrat (CONTRAT16).

        Lecture seule, ordonnées par id. La société est garantie par
        ``get_object`` (queryset scopé société).
        """
        contrat = self.get_object()
        sigs = selectors.signatures_contrat(contrat)
        return Response(
            SignatureContratSerializer(
                sigs, many=True, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='signer')
    def signer(self, request, pk=None):
        """Enregistre une signature électronique IN-APP du contrat (CONTRAT16).

        Corps : ``signataire_nom`` (nom dactylographié, requis — loi 53-05),
        ``role_signataire`` (client/prestataire/temoin), ``methode`` (optionnel,
        ``typed`` par défaut). L'utilisateur agissant, la société et les preuves
        (IP, user agent) sont posés CÔTÉ SERVEUR — jamais lus du corps. Quand le
        client ET le prestataire ont signé, le contrat bascule à ``signe`` via la
        machine d'états gardée (jamais un funnel STAGES.py). Dans la foulée, si
        la prise d'effet est atteinte, le contrat est activé automatiquement
        (``signe → actif`` — CONTRAT17). Refuse (400) une seconde signature de la
        même partie. La société est garantie par ``get_object``.
        """
        contrat = self.get_object()
        body = SignerContratSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        try:
            resultat = services.signer_contrat(
                contrat,
                signataire_nom=data['signataire_nom'],
                role_signataire=data['role_signataire'],
                methode=data.get('methode'),
                signataire=request.user,
                ip_adresse=_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                auteur=request.user,
            )
        except services.SignatureError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'signature': SignatureContratSerializer(
                    resultat['signature'], context={'request': request}).data,
                'contrat_signe': resultat['contrat_signe'],
                'contrat_actif': resultat['contrat_actif'],
                'statut': contrat.statut,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='versions')
    def versions(self, request, pk=None):
        """Versions IMMUABLES du rendu du contrat (CONTRAT18).

        Lecture seule, la dernière version en tête. La société est garantie par
        ``get_object`` (queryset scopé société).
        """
        contrat = self.get_object()
        versions = selectors.versions_contrat(contrat)
        return Response(
            VersionContratSerializer(
                versions, many=True, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='creer-version')
    def creer_version(self, request, pk=None):
        """Fige un instantané IMMUABLE du rendu courant du contrat (CONTRAT18).

        Corps : ``motif`` (optionnel), ``fichier_key`` (optionnelle — clé d'un
        rendu PDF stocké). Le ``contenu`` figé est calculé CÔTÉ SERVEUR (rendu
        par fusion du contrat — jamais lu du corps). Le numéro de ``version``,
        la société et ``cree_par`` sont posés côté serveur. La numérotation est
        sûre face aux courses (``max(version)+1`` sous verrou de ligne, jamais
        ``count()+1``). La société est garantie par ``get_object``.
        """
        contrat = self.get_object()
        body = CreerVersionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        version = services.creer_version(
            contrat,
            motif=body.validated_data.get('motif', ''),
            fichier_key=body.validated_data.get('fichier_key', ''),
            cree_par=request.user,
        )
        return Response(
            VersionContratSerializer(
                version, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class VersionContratViewSet(TenantMixin,
                            viewsets.ReadOnlyModelViewSet):
    """Versions IMMUABLES des rendus de contrat (CONTRAT18) — LECTURE SEULE.

    Récupération des versions figées : ``list`` (filtrable par ``?contrat=<id>``)
    et ``retrieve``. AUCUNE création/mise à jour/suppression n'est exposée ici —
    les versions sont créées exclusivement via l'action ``creer-version`` du
    contrat et restent immuables. Scopé société (``TenantMixin``) ; accès réservé
    au palier Administrateur/Responsable.
    """
    permission_classes = [IsResponsableOrAdmin]
    queryset = VersionContrat.objects.all()
    serializer_class = VersionContratSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['version', 'cree_le', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        return qs


class PartieContratViewSet(_ContratsBaseViewSet):
    """Parties/signataires des contrats de la société.

    Société posée côté serveur (``TenantMixin.perform_create``) ; le contrat
    rattaché est validé même société par le sérialiseur. Filtrable par
    ``?contrat=<id>`` et recherchable par nom/email.
    """
    queryset = PartieContrat.objects.all()
    serializer_class = PartieContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'email']
    ordering_fields = ['ordre', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        return qs


class ContratLienViewSet(_ContratsBaseViewSet):
    """Liens contrat → devis / lead / installation / maintenance (refs lâches).

    ``company`` est posée côté serveur (TenantMixin) ; le ``contrat`` reçu est
    validé même-société par le sérialiseur. Filtres optionnels ``?contrat=<id>``
    et ``?type_cible=<type>``.
    """
    queryset = ContratLien.objects.select_related('contrat').all()
    serializer_class = ContratLienSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        type_cible = self.request.query_params.get('type_cible')
        if type_cible:
            qs = qs.filter(type_cible=type_cible)
        return qs


class ModeleContratViewSet(_ContratsBaseViewSet):
    """Bibliothèque de gabarits de contrats (CONTRAT7).

    Scopé société (TenantMixin). ``company`` est posée côté serveur.

    Filtres : ``?actif=true/false``, ``?categorie=<texte>``.
    Recherche : ``nom``, ``categorie``.

    Action supplémentaire :
    - POST ``/<id>/instancier/`` : crée et renvoie un ``Contrat`` pré-rempli
      depuis ce gabarit (type_contrat, devise, confidentialite du gabarit ;
      ``objet`` et ``reference`` peuvent être surchargés dans le corps).
    """
    queryset = ModeleContrat.objects.all()
    serializer_class = ModeleContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'categorie']
    ordering_fields = ['ordre', 'nom', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        # Filtre optionnel ?actif=true/false
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui'))
        # Filtre optionnel ?categorie=<texte>
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie__icontains=categorie)
        return qs

    @action(detail=True, methods=['post'])
    def instancier(self, request, pk=None):
        """Crée un ``Contrat`` pré-rempli depuis ce gabarit.

        Les champs du gabarit (type_contrat_defaut, devise_defaut,
        confidentialite_defaut) sont copiés sur le nouveau contrat. L'appelant
        peut fournir ``objet`` et ``reference`` dans le corps de la requête pour
        surcharger les valeurs par défaut (``objet`` est requis si non fourni,
        car c'est un champ obligatoire sur ``Contrat``). La société est posée
        côté serveur.
        """
        modele = self.get_object()
        body_serializer = InstancierContratSerializer(data=request.data)
        body_serializer.is_valid(raise_exception=True)
        data = body_serializer.validated_data

        objet = data.get('objet') or modele.nom
        reference = data.get('reference', '')

        contrat = Contrat.objects.create(
            company=request.user.company,
            created_by=request.user,
            objet=objet,
            reference=reference,
            type_contrat=modele.type_contrat_defaut,
            devise=modele.devise_defaut,
            confidentialite=modele.confidentialite_defaut,
            # CONTRAT10 — garder le gabarit source pour le rendu par fusion.
            modele=modele,
        )
        return Response(
            ContratSerializer(contrat, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class ClauseViewSet(_ContratsBaseViewSet):
    """Bibliothèque de clauses réutilisables (CONTRAT8).

    Scopé société (TenantMixin). ``company`` est posée côté serveur.

    Filtres : ``?actif=true/false``, ``?type_clause=<valeur>``,
              ``?categorie=<texte>``.
    Recherche : ``titre``, ``categorie``, ``corps``.
    """

    queryset = Clause.objects.all()
    serializer_class = ClauseSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["titre", "categorie", "corps"]
    ordering_fields = ["ordre", "titre", "type_clause", "id"]

    def get_queryset(self):
        qs = super().get_queryset()
        # Filtre optionnel ?actif=true/false
        actif = self.request.query_params.get("actif")
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ("1", "true", "oui"))
        # Filtre optionnel ?type_clause=<valeur>
        type_clause = self.request.query_params.get("type_clause")
        if type_clause:
            qs = qs.filter(type_clause=type_clause)
        # Filtre optionnel ?categorie=<texte>
        categorie = self.request.query_params.get("categorie")
        if categorie:
            qs = qs.filter(categorie__icontains=categorie)
        return qs


class ModeleContratClauseViewSet(_ContratsBaseViewSet):
    """Liaisons ordonnées ModeleContrat ↔ Clause (CONTRAT8).

    Permet d'associer des clauses à un gabarit de contrat avec un ordre
    d'affichage propre au gabarit. Scopé société ; ``company`` posée côté
    serveur.

    Filtre optionnel : ``?modele=<id>`` pour lister les clauses d'un gabarit.
    """

    queryset = ModeleContratClause.objects.select_related("modele", "clause").all()
    serializer_class = ModeleContratClauseSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["ordre", "id"]

    def get_queryset(self):
        qs = super().get_queryset()
        modele_id = self.request.query_params.get("modele")
        if modele_id:
            qs = qs.filter(modele_id=modele_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class ClauseContratViewSet(_ContratsBaseViewSet):
    """Clauses RÉSOLUES d'un contrat (CONTRAT9).

    Clauses matérialisées (titre + corps résolus, ordonnées, surchargeables) sur
    un ``Contrat`` concret. Scopé société ; ``company`` posée côté serveur. Le
    ``contrat`` et la ``clause`` source (optionnelle) sont validés même-société
    par le sérialiseur.

    Filtres optionnels : ``?contrat=<id>``, ``?clause=<id>``,
    ``?surchargee=true/false``.
    """

    queryset = ClauseContrat.objects.select_related("contrat", "clause").all()
    serializer_class = ClauseContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["titre", "corps"]
    ordering_fields = ["ordre", "id"]

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get("contrat")
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        clause_id = self.request.query_params.get("clause")
        if clause_id:
            qs = qs.filter(clause_id=clause_id)
        surchargee = self.request.query_params.get("surchargee")
        if surchargee is not None:
            qs = qs.filter(surchargee=surchargee.lower() in ("1", "true", "oui"))
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class RegleApprobationViewSet(_ContratsBaseViewSet):
    """Règles d'approbation des contrats par montant/type (CONTRAT13).

    Scopé société (TenantMixin) ; ``company`` posée côté serveur. CRUD complet
    plus une action de résolution :

    - GET ``/regles-approbation/resoudre/?montant=<x>&type_contrat=<t>`` :
      renvoie la règle ACTIVE la plus spécifique couvrant ce couple (ou
      ``{"regle": null}`` si aucune ne s'applique). Lecture seule : ne change
      AUCUN statut.

    Filtres : ``?actif=true/false``, ``?type_contrat=<valeur>``.
    Recherche : ``libelle``.
    """

    queryset = RegleApprobation.objects.all()
    serializer_class = RegleApprobationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle']
    ordering_fields = ['priorite', 'montant_min', 'montant_max', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui'))
        type_contrat = self.request.query_params.get('type_contrat')
        if type_contrat:
            qs = qs.filter(type_contrat=type_contrat)
        return qs

    @action(detail=False, methods=['get'])
    def resoudre(self, request):
        """Résout la règle d'approbation la plus spécifique (CONTRAT13).

        Paramètres de requête : ``montant`` (requis), ``type_contrat``
        (optionnel). Le résolveur est scopé à la société de l'utilisateur. La
        réponse porte la règle sérialisée (ou ``null``).
        """
        params = ResoudreRegleApprobationSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        montant = params.validated_data['montant']
        type_contrat = params.validated_data.get('type_contrat') or None
        regle = selectors.resoudre_regle_approbation(
            request.user.company, montant, type_contrat)
        data = (
            RegleApprobationSerializer(regle, context={'request': request}).data
            if regle is not None else None
        )
        return Response({'regle': data})
