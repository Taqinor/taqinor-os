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
from authentication.permissions import (
    HasPermissionOrLegacy, IsAdminRole,
)
from core.permissions import ScopedPermission, WriteScopedPermissionMixin
# ARC8 — chatter générique (records.Activity). records est une app de
# FONDATION : l'import direct de son mixin de vue est autorisé (frontière
# cross-app exemptée pour records/core/authentication).
from apps.records.views import ChatterViewSetMixin

from . import selectors, services
from .models import (
    AbonnementAddOnLigne,
    AddOnAbonnement,
    AlerteContrat,
    Avenant,
    Caution,
    Clause,
    ClauseContrat,
    CompteurUsage,
    Contrat,
    ContratLien,
    CycleFacturationLog,
    EcheancierContrat,
    EngagementSLA,
    EtapeDunning,
    IndexationPrix,
    JalonContrat,
    LigneEcheance,
    ModeleContrat,
    ModeleContratClause,
    MotifResiliation,
    Obligation,
    OrdreLocation,
    PalierUsage,
    ParametresLocation,
    PartieContrat,
    PieceConformite,
    PlanAbonnement,
    PlanRecurrent,
    RegleApprobation,
    Resiliation,
    RetenueGarantie,
    SequenceDunning,
    VersionContrat,
)
from .serializers import (
    AbonnementAddOnLigneSerializer,
    AddOnAbonnementSerializer,
    AjouterLigneEcheanceSerializer,
    AlerteContratSerializer,
    AvenantSerializer,
    CautionSerializer,
    CompteurUsageSerializer,
    EtapeDunningSerializer,
    ChangerStatutOrdreLocationSerializer,
    ChangerStatutSerializer,
    EcourterOrdreLocationSerializer,
    ClauseContratSerializer,
    ClauseSerializer,
    ContratActivitySerializer,
    ContratLienSerializer,
    CampagneRevisionSerializer,
    ContratSerializer,
    CreerAvenantSerializer,
    CycleFacturationLogSerializer,
    CreerVersionSerializer,
    DeciderEtapeSerializer,
    EcheancierContratSerializer,
    EngagementSLASerializer,
    EtapeApprobationSerializer,
    GenererDevisRenouvellementSerializer,
    IndexationActionSerializer,
    IndexationPrixSerializer,
    LigneEcheanceSerializer,
    MarquerPieceFournieSerializer,
    InstancierContratSerializer,
    JalonContratSerializer,
    ModeleContratClauseSerializer,
    ModeleContratSerializer,
    MotifResiliationSerializer,
    NoterContratSerializer,
    ObligationSerializer,
    OrdreLocationSerializer,
    PalierUsageSerializer,
    ParametresLocationSerializer,
    PartieContratSerializer,
    PenaliteSLASerializer,
    PieceConformiteSerializer,
    PlanAbonnementSerializer,
    PlanRecurrentSerializer,
    ProlongerOrdreLocationSerializer,
    RegleApprobationSerializer,
    RendreContratSerializer,
    RenouvelerContratSerializer,
    ResilierContratSerializer,
    ResiliationSerializer,
    RetenueGarantieSerializer,
    ResoudreRegleApprobationSerializer,
    RollbackCampagneRevisionSerializer,
    SemerAlertesSerializer,
    SequenceDunningSerializer,
    SignatureContratSerializer,
    SignerContratSerializer,
    VersionContratSerializer,
)


def _money(valeur):
    """Formate un montant Decimal en chaîne à 2 décimales (sortie API stable)."""
    from decimal import Decimal

    return str((valeur or Decimal('0')).quantize(Decimal('0.01')))


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


class _ContratsBaseViewSet(
        WriteScopedPermissionMixin, TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + lecture/écriture fine-grainées (YRBAC3).

    ``contrat_voir`` gate les méthodes sûres (GET/HEAD/OPTIONS), ``contrat_gerer``
    gate l'écriture (POST/PUT/PATCH/DELETE + actions custom) — SAUF les actions
    qui déclarent explicitement leur propre ``permission_classes`` plus strict
    (ex. ``campagne-revision`` réservée ``IsAdminRole``, inchangé). Comptes
    légacy sans rôle fin : repli historique Administrateur/Responsable préservé.
    """
    read_permission = 'contrat_voir'
    write_permission = 'contrat_gerer'


class ContratViewSet(ChatterViewSetMixin, _ContratsBaseViewSet):
    """Contrats de la société (CLM). Recherche par référence/objet.

    Visibilité par confidentialité : les contrats ``CONFIDENTIEL`` ne sont
    accessibles qu'aux Administrateurs. Les contrats ``PUBLIC``/``INTERNE``
    sont accessibles à tous les Responsables et Administrateurs de la société.
    Un filtre optionnel ``?confidentialite=<niveau>`` permet de restreindre
    la liste retournée.

    SCA35 — pilote « bout en bout » du kit ``core.documents`` : ce viewset
    mixe DÉJÀ ``ChatterViewSetMixin`` (ARC8, chatter générique consommé —
    jamais refait) ; le kit CONSOMME ce chatter au lieu de le dupliquer. Base
    volontairement conservée (``_ContratsBaseViewSet`` + confidentialité +
    actions ``pdf``/``changer-statut``/``statuts-suivants`` ci-dessous) plutôt
    que remplacée par la factory générique ``core.documents.document_viewset``
    : cette dernière composerait un viewset PLUS PAUVRE (perdrait le filtre de
    confidentialité YRBAC3, le second garde-fou « ≥2 parties », et les actions
    métier) pour un gain nul — la Meta note « Done = cycle de vie contrat
    inchangé fonctionnellement » (``docs/PLAN.md``) exclut ce remplacement.
    """
    queryset = Contrat.objects.all()
    serializer_class = ContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'objet']
    ordering_fields = ['date_debut', 'date_fin', 'montant', 'id', 'confidentialite']

    def get_queryset(self):
        """Queryset scopé société + filtre confidentialité/responsable.

        Les contrats ``CONFIDENTIEL`` sont exclus pour les non-Administrateurs.
        Filtres optionnels : ``?confidentialite=<valeur>``,
        ``?responsable=<id>`` (XCTR10).
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
        # XCTR10 — filtre optionnel par responsable (owner).
        responsable_id = self.request.query_params.get('responsable')
        if responsable_id:
            qs = qs.filter(responsable_id=responsable_id)
        return qs

    def perform_create(self, serializer):
        contrat = serializer.save(
            company=self.request.user.company, created_by=self.request.user)
        # NTSUB1 — un plan d'abonnement (offre catalogue) rattaché à la
        # CRÉATION pré-remplit montant/plan_recurrent en SNAPSHOT, SAUF si le
        # client a explicitement saisi un montant (jamais d'écrasement d'une
        # valeur saisie). Sans plan_abonnement : comportement inchangé.
        if contrat.plan_abonnement_id and 'montant' not in serializer.initial_data:
            services.appliquer_plan_abonnement(
                contrat, contrat.plan_abonnement)

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

    @action(detail=False, methods=['get'], url_path='tableau-de-bord')
    def tableau_de_bord(self, request):
        """Tableau de bord des contrats (CONTRAT33).

        Indicateurs scopés société (lecture seule) : total, répartition par
        statut/type, contrats actifs, à renouveler, en risque, valeur active /
        totale, et MRR (revenu mensuel récurrent des échéanciers actifs). Le
        filtre ``?within=<jours>`` règle la fenêtre « à renouveler / en risque »
        (défaut 30). La société est celle de l'utilisateur (posée côté serveur) ;
        ne change AUCUN statut.
        """
        try:
            within = int(request.query_params.get('within', 30))
        except (TypeError, ValueError):
            within = 30
        data = selectors.tableau_de_bord_contrats(
            request.user.company, within_days=within)
        return Response({
            'total': data['total'],
            'par_statut': data['par_statut'],
            'par_type': data['par_type'],
            'actifs': data['actifs'],
            'a_renouveler': data['a_renouveler'],
            'en_risque': data['en_risque'],
            'valeur_active': _money(data['valeur_active']),
            'valeur_totale': _money(data['valeur_totale']),
            'mrr': _money(data['mrr']),
            'mrr_combine': _money(data['mrr_combine']),
            'exceptions_facturation': data['exceptions_facturation'],
            'mrr_par_responsable': {
                str(k): _money(v)
                for k, v in data['mrr_par_responsable'].items()},
        })

    @action(detail=False, methods=['get'], url_path='mrr-mouvements')
    def mrr_mouvements(self, request):
        """Cascade MRR new/expansion/contraction/churn/net (XCTR7).

        Filtres requis ``?debut=AAAA-MM-JJ&fin=AAAA-MM-JJ`` (défaut : le mois
        calendaire en cours). Lecture seule, scopée société ; ventile le churn
        par ``Resiliation.motif`` (``churn_par_motif``).
        """
        from datetime import date as _date

        from django.utils import timezone as _tz

        debut_raw = request.query_params.get('debut')
        fin_raw = request.query_params.get('fin')
        try:
            debut = (
                _date.fromisoformat(debut_raw) if debut_raw
                else _tz.localdate().replace(day=1))
            fin = _date.fromisoformat(fin_raw) if fin_raw else _tz.localdate()
        except ValueError:
            return Response(
                {'detail': 'debut/fin invalides (AAAA-MM-JJ).'},
                status=status.HTTP_400_BAD_REQUEST)
        if debut > fin:
            return Response(
                {'detail': 'debut doit précéder fin.'},
                status=status.HTTP_400_BAD_REQUEST)

        data = selectors.mouvements_mrr(request.user.company, debut, fin)
        return Response({
            'debut': data['debut'].isoformat(),
            'fin': data['fin'].isoformat(),
            'new': _money(data['new']),
            'expansion': _money(data['expansion']),
            'contraction': _money(data['contraction']),
            'churn': _money(data['churn']),
            'churn_par_motif': {
                k: _money(v) for k, v in data['churn_par_motif'].items()},
            'net': _money(data['net']),
            'net_par_responsable': {
                str(k): _money(v)
                for k, v in data['net_par_responsable'].items()},
        })

    @action(detail=False, methods=['get'], url_path='cohortes-retention')
    def cohortes_retention(self, request):
        """Cohortes de rétention contrats (logo + revenu, NRR/GRR) — XCTR8.

        Matrice par mois de signature × mois d'ancienneté : % contrats actifs
        restants (``logo_pct``) et % MRR retenu (``revenu_pct`` = NRR, avenants
        inclus ; ``revenu_grr_pct`` = GRR, plafonné à 100 % par contrat).
        Lecture seule, scopée société. Ne change AUCUN statut.
        """
        data = selectors.cohortes_retention(request.user.company)
        cohortes = {}
        for mois, matrice in data['cohortes'].items():
            cohortes[mois] = {
                str(k): {
                    'nb_contrats': v['nb_contrats'],
                    'nb_actifs': v['nb_actifs'],
                    'logo_pct': _money(v['logo_pct']),
                    'revenu_pct': _money(v['revenu_pct']),
                    'revenu_grr_pct': _money(v['revenu_grr_pct']),
                }
                for k, v in matrice.items()
            }
        return Response({'cohortes': cohortes, 'mois_max': data['mois_max']})

    @action(detail=False, methods=['get'])
    def clv(self, request):
        """Valeur vie client (CLV) sur revenu récurrent — XCTR9.

        Requiert ``?client_id=<id>`` (lien LÂCHE ``Contrat.client_id``).
        Délègue à ``core.clv`` via ``selectors.clv_client`` (ARPC = MRR du
        client, taux de churn observé de la société). ``clv=null`` quand le
        calcul est impossible (churn nul/inconnu) — jamais une fausse valeur.
        Lecture seule, scopée société.
        """
        client_id = request.query_params.get('client_id')
        if not client_id:
            return Response(
                {'detail': 'client_id est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            client_id = int(client_id)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'client_id invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        resultat = selectors.clv_client(request.user.company, client_id)
        return Response({
            'client_id': client_id,
            'arpc': _money(selectors.mrr_client(
                request.user.company, client_id)),
            'clv': _money(resultat.clv) if resultat.clv is not None else None,
            'duree_vie_mois': (
                str(resultat.duree_vie_mois)
                if resultat.duree_vie_mois is not None else None),
            'used_fallback': resultat.used_fallback,
            'plafonnee': resultat.plafonnee,
        })

    @action(detail=False, methods=['post'], url_path='campagne-revision',
            permission_classes=[IsAdminRole])
    def campagne_revision(self, request):
        """Campagne de révision tarifaire en masse — XCTR11 (admin uniquement).

        Corps : ``filtres`` (optionnel), ``pct`` (requis), ``date_effet``
        (optionnel), ``preview`` (défaut ``True``). Preview = AUCUNE écriture.
        Application (``preview=false``) = un avenant d'indexation par contrat
        couvert (idempotent — re-run = 0 nouvel avenant) + notification aux
        responsables + liste de rollback (``rollback_ids``).
        """
        body = CampagneRevisionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        resultat = services.campagne_revision(
            request.user.company,
            filtres=body.validated_data.get('filtres'),
            pct=body.validated_data['pct'],
            date_effet=body.validated_data.get('date_effet'),
            preview=body.validated_data.get('preview', True),
            auteur=request.user,
        )
        if resultat['preview']:
            return Response({
                'preview': True,
                'lignes': [
                    {
                        'contrat_id': ligne['contrat_id'],
                        'objet': ligne['objet'],
                        'ancien_montant': _money(ligne['ancien_montant']),
                        'nouveau_montant': _money(ligne['nouveau_montant']),
                        'delta': _money(ligne['delta']),
                    }
                    for ligne in resultat['lignes']
                ],
            })
        return Response({
            'preview': False,
            'avenants_crees': resultat['avenants_crees'],
            'rollback_ids': resultat['rollback_ids'],
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'],
            url_path='campagne-revision-rollback',
            permission_classes=[IsAdminRole])
    def campagne_revision_rollback(self, request):
        """Rollback d'une campagne de révision tarifaire — XCTR11 (admin only).

        Corps : ``avenant_ids`` (liste retournée par l'application). Crée un
        avenant COMPENSATOIRE par avenant listé (jamais de suppression —
        historique immuable CONTRAT18/24).
        """
        body = RollbackCampagneRevisionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        compensations = services.rollback_campagne_revision(
            request.user.company, body.validated_data['avenant_ids'],
            auteur=request.user)
        return Response({
            'compensations_creees': len(compensations),
            'avenant_ids': [c.id for c in compensations],
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def reporting(self, request):
        """Reporting valeur contractuelle & taux de renouvellement (CONTRAT35).

        Lecture seule, scopé société : valeur totale/active, valeur par type,
        nombre de renouvellements, contrats renouvelés, contrats échus et taux de
        renouvellement (%). Ne change AUCUN statut.
        """
        data = selectors.reporting_contrats(request.user.company)
        return Response({
            'valeur_totale': _money(data['valeur_totale']),
            'valeur_active': _money(data['valeur_active']),
            'valeur_par_type': {
                k: _money(v) for k, v in data['valeur_par_type'].items()},
            'nb_renouvellements': data['nb_renouvellements'],
            'nb_contrats_renouveles': data['nb_contrats_renouveles'],
            'nb_echus': data['nb_echus'],
            'taux_renouvellement': str(data['taux_renouvellement']),
        })

    @action(detail=True, methods=['post'])
    def renouveler(self, request, pk=None):
        """Renouvelle EFFECTIVEMENT le contrat (action manuelle — CONTRAT23).

        Prolonge la période contractuelle : ``nouvelle_date_fin`` explicite OU
        ``duree_mois`` (à défaut, la ``duree_reconduction_mois`` du contrat).
        Avance ``date_fin`` (et ``date_debut`` à l'ancienne fin), remet
        ``preavis_traite=False``, fige un instantané (CONTRAT18) et journalise
        (CONTRAT15). Refuse (400) un contrat résilié/expiré ou un calcul
        impossible (aucune durée). Le ``statut`` n'est JAMAIS modifié
        (préservation des statuts) ; jamais un funnel STAGES.py. L'auteur et la
        société sont posés côté serveur. La société est garantie par
        ``get_object``.
        """
        contrat = self.get_object()
        body = RenouvelerContratSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            contrat = services.renouveler_contrat(
                contrat,
                nouvelle_date_fin=body.validated_data.get('nouvelle_date_fin'),
                duree_mois=body.validated_data.get('duree_mois'),
                auteur=request.user,
            )
        except services.RenouvellementError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ContratSerializer(contrat, context={'request': request}).data)

    @action(detail=False, methods=['post'], url_path='traiter-reconductions')
    def traiter_reconductions(self, request):
        """Reconduit automatiquement les contrats en tacite reconduction dus (CONTRAT23).

        Trouve les contrats ``tacite_reconduction=True`` non résiliés/expirés
        dont l'échéance (``date_fin``) est atteinte et qui portent une durée de
        reconduction, et les renouvelle chacun de leur ``duree_reconduction_mois``
        (idempotent : un second appel le même jour ne re-reconduit pas la même
        période). La date du jour et la société sont posées CÔTÉ SERVEUR. Ne
        change AUCUN statut de contrat.
        """
        resultat = services.traiter_reconductions_tacites(
            request.user.company, auteur=request.user)
        return Response({
            'nb_traites': resultat['nb_traites'],
            'nb_renouvellements': resultat['nb_renouvellements'],
            'contrats': ContratSerializer(
                resultat['contrats'], many=True,
                context={'request': request}).data,
        })

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

    @action(detail=True, methods=['get'], url_path='avenants')
    def avenants(self, request, pk=None):
        """Avenants (amendements) du contrat (CONTRAT24).

        Lecture seule, le dernier avenant en tête. La société est garantie par
        ``get_object`` (queryset scopé société).
        """
        contrat = self.get_object()
        avenants = selectors.avenants_contrat(contrat)
        return Response(
            AvenantSerializer(
                avenants, many=True, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='creer-avenant')
    def creer_avenant(self, request, pk=None):
        """Enregistre un AVENANT (amendement) au contrat → nouvelle version (CONTRAT24).

        Corps : ``objet`` (requis, titre court de l'amendement), ``description``
        (optionnel), ``date_effet`` (optionnel), ``montant_delta`` (optionnel —
        variation du montant, AJOUTÉE à ``Contrat.montant`` côté serveur quand
        fournie). L'avenant produit un INSTANTANÉ IMMUABLE du contrat
        (``VersionContrat`` — CONTRAT18) figeant son état amendé ; l'avenant
        pointe vers cette version (``version_creee``). Le ``numero`` (max+1 sous
        verrou de ligne, jamais ``count()+1``), la société et ``cree_par`` sont
        posés côté serveur. Le ``statut`` n'est JAMAIS modifié (préservation des
        statuts) ; jamais un funnel STAGES.py. La société est garantie par
        ``get_object``.
        """
        contrat = self.get_object()
        body = CreerAvenantSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        avenant = services.creer_avenant(
            contrat,
            objet=data['objet'],
            description=data.get('description', ''),
            date_effet=data.get('date_effet'),
            montant_delta=data.get('montant_delta'),
            auteur=request.user,
        )
        return Response(
            AvenantSerializer(
                avenant, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='resiliations')
    def resiliations(self, request, pk=None):
        """Résiliations du contrat (CONTRAT25).

        Lecture seule, la dernière résiliation en tête. La société est garantie
        par ``get_object`` (queryset scopé société).
        """
        contrat = self.get_object()
        resils = selectors.resiliations_contrat(contrat)
        return Response(
            ResiliationSerializer(
                resils, many=True, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='resilier')
    def resilier(self, request, pk=None):
        """Résilie le contrat (motif / préavis / solde) — CONTRAT25.

        Corps : ``motif`` (optionnel), ``date_effet`` (optionnel),
        ``preavis_jours`` (optionnel), ``solde`` (optionnel — solde de tout
        compte). Enregistre une ``Resiliation`` ET fait basculer le contrat vers
        ``resilie`` via la machine d'états GARDÉE (jamais une écriture directe du
        statut, jamais un funnel STAGES.py). Refuse (400) une résiliation depuis
        un état non résiliable (la machine d'états enforce la garde) ou un contrat
        ayant déjà une résiliation active. Fige un instantané (CONTRAT18) et
        journalise (CONTRAT15). L'auteur, la société, la date de demande et le
        statut sont posés CÔTÉ SERVEUR. La société est garantie par
        ``get_object``.
        """
        contrat = self.get_object()
        body = ResilierContratSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        try:
            resiliation = services.resilier_contrat(
                contrat,
                motif=data.get('motif', ''),
                motif_ref=data.get('motif_ref'),
                date_effet=data.get('date_effet'),
                preavis_jours=data.get('preavis_jours'),
                solde=data.get('solde'),
                auteur=request.user,
            )
        except services.ResiliationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ResiliationSerializer(
                resiliation, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'],
            url_path='generer-devis-renouvellement')
    def generer_devis_renouvellement(self, request, pk=None):
        """Génère un devis de renouvellement AVANT échéance (XCTR12).

        Corps optionnel : ``valeur_indice`` (révise le montant proposé via
        l'indexation active du contrat). Crée un ``ventes.Devis`` (référence
        via ``ventes.utils.references`` — jamais ``count()+1``), lié au
        contrat via ``ContratLien``. Refuse (400) si un devis de
        renouvellement OUVERT existe déjà (garde anti-doublon — un double clic
        ne crée jamais deux devis) ou si le contrat n'a pas de client
        résoluble. Le ``Contrat.statut`` n'est JAMAIS modifié. L'utilisateur
        et la société sont posés CÔTÉ SERVEUR.
        """
        contrat = self.get_object()
        body = GenererDevisRenouvellementSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            devis = services.generer_devis_renouvellement(
                contrat,
                auteur=request.user,
                valeur_indice=body.validated_data.get('valeur_indice'),
            )
        except services.RenouvellementDevisError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'devis_id': devis.id,
                'devis_reference': devis.reference,
                'note': devis.note,
            },
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
    permission_classes = [HasPermissionOrLegacy('contrat_voir')]
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


class AvenantViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Avenants (amendements) des contrats de la société (CONTRAT24) — LECTURE SEULE.

    Récupération des avenants : ``list`` (filtrable par ``?contrat=<id>``) et
    ``retrieve``. AUCUNE création/mise à jour/suppression n'est exposée ici — les
    avenants sont créés exclusivement via l'action ``creer-avenant`` du contrat
    (qui fige aussi la ``VersionContrat`` associée). Scopé société
    (``TenantMixin``) ; accès réservé au palier Administrateur/Responsable.
    """
    permission_classes = [HasPermissionOrLegacy('contrat_voir')]
    queryset = Avenant.objects.select_related('contrat', 'version_creee').all()
    serializer_class = AvenantSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['numero', 'date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        return qs


class ResiliationViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Résiliations des contrats de la société (CONTRAT25) — LECTURE SEULE.

    Récupération des résiliations : ``list`` (filtrable par ``?contrat=<id>`` et
    ``?statut=<valeur>``) et ``retrieve``. AUCUNE création/mise à jour/suppression
    n'est exposée ici — les résiliations sont créées exclusivement via l'action
    ``resilier`` du contrat (qui fait aussi basculer le statut via la machine
    d'états gardée). Scopé société (``TenantMixin``) ; accès réservé au palier
    Administrateur/Responsable.
    """
    permission_classes = [HasPermissionOrLegacy('contrat_voir')]
    queryset = Resiliation.objects.select_related(
        'contrat', 'version_creee').all()
    serializer_class = ResiliationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_demande', 'date_effet', 'date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
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


class AlerteContratViewSet(_ContratsBaseViewSet):
    """Alertes/rappels planifiés sur les contrats de la société (CONTRAT22).

    Scopé société (TenantMixin) ; ``company`` posée CÔTÉ SERVEUR (déduite du
    contrat à la création). CRUD des alertes plus deux actions :

    - POST ``/alertes/declencher/`` : dispatche toutes les alertes ``planifiee``
      DUES de la société via le système de notifications, idempotent (jamais de
      double-envoi). Optionnel : corps/param ``today`` n'est PAS accepté du
      client (la date du jour est posée côté serveur).
    - POST ``/alertes/semer-echeances/`` : sème des alertes ``preavis`` /
      ``echeance`` à partir des contrats dont l'échéance approche (réutilise les
      sélecteurs CONTRAT20/21), sans rien dispatcher. Param ``within`` (jours).

    Filtres : ``?contrat=<id>``, ``?statut=<valeur>``, ``?type_alerte=<valeur>``.
    """
    queryset = AlerteContrat.objects.select_related('contrat').all()
    serializer_class = AlerteContratSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_declenchement', 'date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        type_alerte = self.request.query_params.get('type_alerte')
        if type_alerte:
            qs = qs.filter(type_alerte=type_alerte)
        return qs

    def perform_create(self, serializer):
        """Pose ``company`` (celle du contrat) et ``cree_par`` côté serveur.

        Le ``contrat`` est déjà validé même-société par le sérialiseur ; on
        déduit la société du contrat (jamais lue du corps de requête) — donc
        cohérente avec le filtre TenantMixin de l'utilisateur.
        """
        contrat = serializer.validated_data['contrat']
        serializer.save(
            company=contrat.company, cree_par=self.request.user)

    @action(detail=False, methods=['post'])
    def declencher(self, request):
        """Dispatche les alertes DUES de la société via les notifications.

        Idempotent : seules les alertes ``planifiee`` dues (date ≤ aujourd'hui)
        sont envoyées, puis marquées ``envoyee`` — un second appel ne re-notifie
        rien. La date du jour et la société sont posées CÔTÉ SERVEUR.
        """
        resultat = services.declencher_alertes_contrat(request.user.company)
        return Response({
            'nb_dues': resultat['nb_dues'],
            'nb_envoyees': resultat['nb_envoyees'],
            'nb_notifications': resultat['nb_notifications'],
            'alertes': AlerteContratSerializer(
                resultat['alertes'], many=True,
                context={'request': request}).data,
        })

    @action(detail=False, methods=['post'], url_path='semer-echeances')
    def semer_echeances(self, request):
        """Sème des alertes depuis les contrats dont l'échéance approche.

        Réutilise les sélecteurs CONTRAT20/21 (préavis + renouvellement) pour
        créer des alertes ``planifiee`` idempotentes. Ne dispatche rien. La
        société est celle de l'utilisateur (posée côté serveur).
        """
        body = SemerAlertesSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        within = body.validated_data.get('within', 30)
        resultat = services.semer_alertes_echeances(
            request.user.company, within_days=within, cree_par=request.user)
        return Response(
            {
                'nb_creees': resultat['nb_creees'],
                'alertes': AlerteContratSerializer(
                    resultat['alertes'], many=True,
                    context={'request': request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class JalonContratViewSet(_ContratsBaseViewSet):
    """Jalons / étapes clés des contrats de la société (CONTRAT26).

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR (déduite du
    contrat). La CRÉATION passe par ``services.creer_jalon`` (numéro = max+1 sous
    verrou de ligne, jamais ``count()+1``). Action ``marquer-atteint`` pour
    pointer un jalon comme atteint (statut + date côté serveur). Le ``statut``
    d'un jalon est PROPRE au suivi des jalons — il ne touche JAMAIS le
    ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2).

    Filtres : ``?contrat=<id>``, ``?statut=<valeur>``.
    """
    queryset = JalonContrat.objects.select_related('contrat').all()
    serializer_class = JalonContratSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['numero', 'date_cible', 'date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        """Crée le jalon via le service (numérotation max+1 côté serveur).

        La société est déduite du contrat (validé même-société par le
        sérialiseur) — jamais lue du corps de requête.
        """
        contrat = serializer.validated_data['contrat']
        jalon = services.creer_jalon(
            contrat,
            intitule=serializer.validated_data['intitule'],
            description=serializer.validated_data.get('description', ''),
            date_cible=serializer.validated_data.get('date_cible'),
            auteur=self.request.user,
        )
        serializer.instance = jalon

    @action(detail=True, methods=['post'], url_path='marquer-atteint')
    def marquer_atteint(self, request, pk=None):
        """Marque le jalon comme ATTEINT (statut + date côté serveur — CONTRAT26).

        Idempotent : un jalon déjà atteint reste inchangé. La date du jour et
        l'auteur sont posés CÔTÉ SERVEUR. Ne change AUCUN ``Contrat.statut``.
        """
        jalon = self.get_object()
        jalon = services.marquer_jalon_atteint(jalon, auteur=request.user)
        return Response(
            JalonContratSerializer(
                jalon, context={'request': request}).data)


class ObligationViewSet(_ContratsBaseViewSet):
    """Obligations / livrables des contrats de la société (CONTRAT26).

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR (déduite du
    contrat). CRUD complet plus une action ``marquer-faite`` qui pose
    ``statut=faite`` + ``date_realisation`` côté serveur. Le ``statut`` d'une
    obligation est PROPRE au suivi des livrables — il ne touche JAMAIS le
    ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2).

    Filtres : ``?contrat=<id>``, ``?jalon=<id>``, ``?statut=<valeur>``,
    ``?redevable=<valeur>``.
    """
    queryset = Obligation.objects.select_related('contrat', 'jalon').all()
    serializer_class = ObligationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['intitule', 'description']
    ordering_fields = ['ordre', 'date_echeance', 'date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        jalon_id = self.request.query_params.get('jalon')
        if jalon_id:
            qs = qs.filter(jalon_id=jalon_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        redevable = self.request.query_params.get('redevable')
        if redevable:
            qs = qs.filter(redevable=redevable)
        return qs

    def perform_create(self, serializer):
        """Pose ``company`` (celle du contrat) côté serveur."""
        contrat = serializer.validated_data['contrat']
        serializer.save(company=contrat.company)

    @action(detail=True, methods=['post'], url_path='marquer-faite')
    def marquer_faite(self, request, pk=None):
        """Marque l'obligation comme RÉALISÉE (statut + date côté serveur — CONTRAT26).

        Idempotent : une obligation déjà réalisée reste inchangée. La date du
        jour et l'auteur sont posés CÔTÉ SERVEUR. Ne change AUCUN
        ``Contrat.statut``.
        """
        obligation = self.get_object()
        obligation = services.marquer_obligation_faite(
            obligation, auteur=request.user)
        return Response(
            ObligationSerializer(
                obligation, context={'request': request}).data)


class EngagementSLAViewSet(_ContratsBaseViewSet):
    """Engagements de niveau de service (SLA) & pénalités des contrats (CONTRAT27).

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR (déduite du
    contrat). CRUD complet plus une action ``penalite`` qui CALCULE (lecture
    seule, déclaratif) la pénalité encourue — sans créer d'écriture, sans toucher
    le ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2), et
    sans émettre de facture.

    Filtres : ``?contrat=<id>``, ``?actif=true/false``.
    """
    queryset = EngagementSLA.objects.select_related('contrat').all()
    serializer_class = EngagementSLASerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'unite']
    ordering_fields = ['taux_cible', 'date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui'))
        return qs

    def perform_create(self, serializer):
        """Pose ``company`` (celle du contrat) côté serveur."""
        contrat = serializer.validated_data['contrat']
        serializer.save(company=contrat.company)

    @action(detail=True, methods=['post'])
    def penalite(self, request, pk=None):
        """Calcule la pénalité encourue pour ce SLA (lecture seule — CONTRAT27).

        Corps : ``taux_realise`` (optionnel, %) et ``montant_contrat``
        (optionnel). Déclaratif : ne crée AUCUNE écriture, ne change AUCUN
        statut, n'émet aucune facture.
        """
        sla = self.get_object()
        body = PenaliteSLASerializer(data=request.data)
        body.is_valid(raise_exception=True)
        resultat = services.calculer_penalite_sla(
            sla,
            taux_realise=body.validated_data.get('taux_realise'),
            montant_contrat=body.validated_data.get('montant_contrat'),
        )
        return Response({
            'penalite': str(resultat['penalite']),
            'respecte': resultat['respecte'],
            'taux_cible': str(resultat['taux_cible']),
            'taux_realise': (
                str(resultat['taux_realise'])
                if resultat['taux_realise'] is not None else None),
        })


class RetenueGarantieViewSet(_ContratsBaseViewSet):
    """Retenues de garantie des contrats de la société + suivi de libération (CONTRAT28).

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR (déduite du
    contrat). À la création, ``montant_retenu`` est CALCULÉ côté serveur
    (= base × taux %). Action ``liberer`` pour pointer la libération (statut +
    date côté serveur). Le ``statut`` est PROPRE au suivi de la retenue — il ne
    touche JAMAIS le ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py``
    (rule #2), et n'émet aucune facture.

    Filtres : ``?contrat=<id>``, ``?statut=<valeur>``.
    """
    queryset = RetenueGarantie.objects.select_related('contrat').all()
    serializer_class = RetenueGarantieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_retenue', 'date_liberation_prevue',
                       'date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        """Pose ``company`` (celle du contrat) + calcule ``montant_retenu``.

        Le montant retenu est dérivé CÔTÉ SERVEUR (= base × taux %) — jamais lu
        du corps de requête.
        """
        contrat = serializer.validated_data['contrat']
        instance = serializer.save(company=contrat.company)
        instance.montant_retenu = instance.calculer_montant_retenu()
        instance.save(update_fields=['montant_retenu'])

    def perform_update(self, serializer):
        """Recalcule ``montant_retenu`` après une mise à jour base/taux."""
        instance = serializer.save()
        nouveau = instance.calculer_montant_retenu()
        if instance.montant_retenu != nouveau:
            instance.montant_retenu = nouveau
            instance.save(update_fields=['montant_retenu'])

    @action(detail=True, methods=['post'])
    def liberer(self, request, pk=None):
        """Libère la retenue (statut + date côté serveur — CONTRAT28).

        Idempotent : une retenue déjà libérée reste inchangée. Une retenue
        annulée ne peut pas être libérée (400). La date du jour et l'auteur sont
        posés CÔTÉ SERVEUR. Ne change AUCUN ``Contrat.statut``.
        """
        retenue = self.get_object()
        try:
            retenue = services.liberer_retenue(retenue, auteur=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            RetenueGarantieSerializer(
                retenue, context={'request': request}).data)


class CautionViewSet(_ContratsBaseViewSet):
    """Registre des cautions / garanties liées aux contrats (CONTRAT29).

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR (déduite du
    contrat). CRUD complet. Le ``statut`` d'une caution est un simple champ de
    registre (éditable) — il ne pilote AUCUNE machine d'états du contrat
    (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2).

    Filtres : ``?contrat=<id>``, ``?statut=<valeur>``, ``?type_caution=<valeur>``.
    Recherche : ``garant`` / ``reference``.
    """
    queryset = Caution.objects.select_related('contrat').all()
    serializer_class = CautionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['garant', 'reference']
    ordering_fields = ['date_emission', 'date_expiration', 'montant',
                       'date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        type_caution = self.request.query_params.get('type_caution')
        if type_caution:
            qs = qs.filter(type_caution=type_caution)
        return qs

    def perform_create(self, serializer):
        """Pose ``company`` (celle du contrat) côté serveur."""
        contrat = serializer.validated_data['contrat']
        serializer.save(company=contrat.company)


class EcheancierContratViewSet(_ContratsBaseViewSet):
    """Échéanciers de paiement des contrats (en-tête + lignes) — CONTRAT30.

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR (déduite du
    contrat). CRUD de l'en-tête plus l'action ``ajouter-ligne`` qui crée une
    ``LigneEcheance`` (numéro = max+1 sous verrou, jamais ``count()+1``) et
    recalcule ``montant_total``. Le ``statut`` est PROPRE à l'échéancier — il ne
    touche JAMAIS le ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py``
    (rule #2), et n'émet aucune facture (CONTRAT31 est séparé).

    Filtres : ``?contrat=<id>``, ``?statut=<valeur>``.
    """
    queryset = EcheancierContrat.objects.select_related(
        'contrat').prefetch_related('lignes').all()
    serializer_class = EcheancierContratSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        """Pose ``company`` (celle du contrat) côté serveur."""
        contrat = serializer.validated_data['contrat']
        serializer.save(company=contrat.company)

    @action(detail=True, methods=['post'], url_path='ajouter-ligne')
    def ajouter_ligne(self, request, pk=None):
        """Ajoute une ligne (échéance) à l'échéancier (CONTRAT30).

        Corps : ``date_echeance`` (requis), ``montant`` (optionnel), ``libelle``
        (optionnel). Le ``numero`` (max+1 sous verrou), la société et le statut
        sont posés CÔTÉ SERVEUR ; ``montant_total`` est recalculé.
        """
        echeancier = self.get_object()
        body = AjouterLigneEcheanceSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        ligne = services.ajouter_ligne_echeance(
            echeancier,
            date_echeance=body.validated_data['date_echeance'],
            montant=body.validated_data.get('montant'),
            libelle=body.validated_data.get('libelle', ''),
        )
        return Response(
            LigneEcheanceSerializer(
                ligne, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class LigneEcheanceViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Lignes (échéances) des échéanciers — LECTURE SEULE + pointage de paiement (CONTRAT30).

    Récupération : ``list`` (filtrable par ``?echeancier=<id>``,
    ``?statut=<valeur>``) et ``retrieve``. Les lignes sont créées exclusivement
    via l'action ``ajouter-ligne`` de l'échéancier (numéro côté serveur). Action
    ``pointer-paiement`` pour marquer une ligne payée (statut + date côté
    serveur). Scopé société (``TenantMixin``) ; lecture ``contrat_voir``,
    écriture (``pointer-paiement``) ``contrat_gerer`` (YRBAC3).
    """
    read_permission = 'contrat_voir'
    write_permission = 'contrat_gerer'
    queryset = LigneEcheance.objects.select_related('echeancier').all()
    serializer_class = LigneEcheanceSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['numero', 'date_echeance', 'date_creation', 'id']

    def get_permissions(self):
        return [ScopedPermission()]

    def get_queryset(self):
        qs = super().get_queryset()
        echeancier_id = self.request.query_params.get('echeancier')
        if echeancier_id:
            qs = qs.filter(echeancier_id=echeancier_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @action(detail=True, methods=['post'], url_path='pointer-paiement')
    def pointer_paiement(self, request, pk=None):
        """Marque la ligne d'échéance PAYÉE (statut + date côté serveur — CONTRAT30).

        Idempotent : une ligne déjà payée reste inchangée. La date du jour est
        posée CÔTÉ SERVEUR. Ne change AUCUN ``Contrat.statut`` et n'émet aucune
        facture.
        """
        ligne = self.get_object()
        ligne = services.pointer_paiement_echeance(ligne)
        return Response(
            LigneEcheanceSerializer(
                ligne, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def facturer(self, request, pk=None):
        """Émet une facture récurrente pour cette échéance (CONTRAT31).

        Crée une ``ventes.Facture`` via la frontière cross-app (client résolu par
        ``crm.selectors``, numérotation par ``ventes``) et relie la facture à la
        ligne (``facture_id``). Refuse (400) si la facturation n'est pas activée
        sur l'échéancier, si l'échéance est déjà facturée/annulée, si le montant
        est nul, ou si le client est introuvable. Le ``Contrat.statut`` n'est
        JAMAIS modifié. L'utilisateur et la société sont posés CÔTÉ SERVEUR.

        Chaque tentative (succès/échec) est journalisée dans le journal de
        facturation récurrente (XCTR5 — ``services.enregistrer_cycle``).
        """
        ligne = self.get_object()
        try:
            facture = services.facturer_ligne_echeance_journalisee(
                ligne, user=request.user)
        except services.FacturationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        ligne.refresh_from_db()
        return Response(
            {
                'facture_id': facture.id,
                'facture_reference': facture.reference,
                'ligne': LigneEcheanceSerializer(
                    ligne, context={'request': request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class IndexationPrixViewSet(_ContratsBaseViewSet):
    """Indexations / révisions de prix des contrats (CONTRAT32).

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR (déduite du
    contrat). CRUD des règles d'indexation plus deux actions :

    - POST ``/indexations/<id>/simuler/`` : CALCULE (lecture seule, déclaratif)
      le prix révisé pour une ``valeur_actuelle`` d'indice — aucune écriture.
    - POST ``/indexations/<id>/appliquer/`` : APPLIQUE la révision via un AVENANT
      (CONTRAT24) ajustant ``Contrat.montant`` du delta. Le ``Contrat.statut``
      n'est JAMAIS modifié (CONTRAT12) ; jamais un funnel ``STAGES.py`` (rule #2).

    Filtres : ``?contrat=<id>``, ``?actif=true/false``.
    """
    queryset = IndexationPrix.objects.select_related('contrat').all()
    serializer_class = IndexationPrixSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'indice']
    ordering_fields = ['date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui'))
        return qs

    def perform_create(self, serializer):
        """Pose ``company`` (celle du contrat) côté serveur."""
        contrat = serializer.validated_data['contrat']
        serializer.save(company=contrat.company)

    @action(detail=True, methods=['post'])
    def simuler(self, request, pk=None):
        """Simule le prix révisé pour une valeur d'indice (lecture seule — CONTRAT32)."""
        indexation = self.get_object()
        body = IndexationActionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            resultat = services.calculer_prix_indexe(
                indexation,
                valeur_actuelle=body.validated_data['valeur_actuelle'],
                prix_base=body.validated_data.get('prix_base'),
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'prix_base': str(resultat['prix_base']),
            'prix_revise': str(resultat['prix_revise']),
            'delta': str(resultat['delta']),
            'valeur_actuelle': str(resultat['valeur_actuelle']),
        })

    @action(detail=True, methods=['post'])
    def appliquer(self, request, pk=None):
        """Applique la révision via un avenant (CONTRAT32).

        Corps : ``valeur_actuelle`` (requis). Crée un AVENANT ajustant
        ``Contrat.montant`` du delta (ou aucun si delta nul) et trace la date de
        révision. L'auteur et la société sont posés CÔTÉ SERVEUR.
        """
        indexation = self.get_object()
        body = IndexationActionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            resultat = services.appliquer_indexation(
                indexation,
                valeur_actuelle=body.validated_data['valeur_actuelle'],
                auteur=request.user,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        avenant = resultat['avenant']
        return Response({
            'prix_base': str(resultat['prix_base']),
            'prix_revise': str(resultat['prix_revise']),
            'delta': str(resultat['delta']),
            'avenant_id': avenant.id if avenant is not None else None,
            'avenant_numero': avenant.numero if avenant is not None else None,
            'lignes_reappliquees': resultat.get('lignes_reappliquees', 0),
        }, status=status.HTTP_200_OK)


class PieceConformiteViewSet(_ContratsBaseViewSet):
    """Pièces de conformité / attestations obligatoires des contrats (CONTRAT34).

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR (déduite du
    contrat). CRUD plus une action ``marquer-fournie`` qui pose ``statut=fournie``
    + ``date_fourniture`` (et relie éventuellement un document GED par id LÂCHE).
    Le ``statut`` est PROPRE au suivi de conformité — il ne touche JAMAIS le
    ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2).

    Filtres : ``?contrat=<id>``, ``?statut=<valeur>``, ``?type_piece=<valeur>``,
    ``?obligatoire=true/false``.
    """
    queryset = PieceConformite.objects.select_related('contrat').all()
    serializer_class = PieceConformiteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'note']
    ordering_fields = ['date_expiration', 'date_fourniture', 'date_creation',
                       'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        type_piece = self.request.query_params.get('type_piece')
        if type_piece:
            qs = qs.filter(type_piece=type_piece)
        obligatoire = self.request.query_params.get('obligatoire')
        if obligatoire is not None:
            qs = qs.filter(
                obligatoire=obligatoire.lower() in ('1', 'true', 'oui'))
        return qs

    def perform_create(self, serializer):
        """Pose ``company`` (celle du contrat) côté serveur."""
        contrat = serializer.validated_data['contrat']
        serializer.save(company=contrat.company)

    @action(detail=True, methods=['post'], url_path='marquer-fournie')
    def marquer_fournie(self, request, pk=None):
        """Marque la pièce FOURNIE (statut + date côté serveur — CONTRAT34).

        Corps optionnel : ``ged_document_id`` (lien LÂCHE vers un document GED),
        ``date_expiration``. La date du jour et l'auteur sont posés CÔTÉ SERVEUR.
        Ne change AUCUN ``Contrat.statut``.
        """
        piece = self.get_object()
        body = MarquerPieceFournieSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        piece = services.marquer_piece_fournie(
            piece,
            ged_document_id=body.validated_data.get('ged_document_id'),
            date_expiration=body.validated_data.get('date_expiration'),
            auteur=request.user,
        )
        return Response(
            PieceConformiteSerializer(
                piece, context={'request': request}).data)


class CycleFacturationLogViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Journal des cycles de facturation récurrente + file d'exceptions — XCTR5.

    LECTURE SEULE : les entrées sont écrites exclusivement côté serveur par les
    services de facturation récurrente (``services.enregistrer_cycle``). Action
    ``rejouer`` : re-tente UN échec (garde anti double-facturation — jamais
    deux factures pour la même période contrat). Scopé société (``TenantMixin``).

    Filtres : ``?statut=<valeur>``, ``?source_type=<valeur>``.

    Lecture ``contrat_voir`` ; écriture (action ``rejouer``) ``contrat_gerer``
    (YRBAC3).
    """
    read_permission = 'contrat_voir'
    write_permission = 'contrat_gerer'
    queryset = CycleFacturationLog.objects.all()
    serializer_class = CycleFacturationLogSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'id']

    def get_permissions(self):
        return [ScopedPermission()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        source_type = self.request.query_params.get('source_type')
        if source_type:
            qs = qs.filter(source_type=source_type)
        return qs

    @action(detail=False, methods=['get'])
    def exceptions(self, request):
        """Liste des cycles en échec (file d'exceptions) — XCTR5.

        Raccourci en lecture seule de ``?statut=echec`` pour la carte du
        tableau de bord contrats.
        """
        entries = services.exceptions_facturation(request.user.company)
        page = self.paginate_queryset(entries)
        serializer = CycleFacturationLogSerializer(
            page if page is not None else entries, many=True,
            context={'request': request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def rejouer(self, request, pk=None):
        """Rejoue UN échec de facturation (XCTR5).

        Refuse (400) une entrée non-échec ou si aucune échéance facturable
        n'est retrouvable. Succès → 201 avec la nouvelle facture. L'utilisateur
        et la société sont posés CÔTÉ SERVEUR.
        """
        log = self.get_object()
        try:
            facture = services.rejouer_cycle(log, user=request.user)
        except services.RejeuError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'facture_id': facture.id,
                'facture_reference': facture.reference,
                'log': CycleFacturationLogSerializer(
                    log, context={'request': request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# XCTR17 — Location de matériel SORTANTE (aux clients)
# ---------------------------------------------------------------------------


class OrdreLocationViewSet(_ContratsBaseViewSet):
    """Ordres de location de matériel aux clients (XCTR17).

    Scopé société (``TenantMixin``). Le produit DOIT être ``louable``
    (vérifié via ``stock.selectors.get_produit_louable`` — jamais un import
    du modèle ``stock``) et la fenêtre demandée ne doit chevaucher AUCUN
    ordre actif du même produit + numéro de série (400 sinon). ``company`` et
    ``created_by`` sont posés CÔTÉ SERVEUR.

    Filtres : ``?produit=<id>``, ``?statut=<valeur>``, ``?client=<id>``.
    """
    queryset = OrdreLocation.objects.select_related('produit').all()
    serializer_class = OrdreLocationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = [
        'date_reservation', 'date_enlevement_prevue', 'date_retour_prevue',
        'date_creation', 'id',
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        produit_id = self.request.query_params.get('produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        client_id = self.request.query_params.get('client')
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs

    def create(self, request, *args, **kwargs):
        from apps.stock.selectors import get_produit_louable

        produit_id = request.data.get('produit')
        produit = get_produit_louable(request.user.company, produit_id)
        if produit is None:
            return Response(
                {'produit': "Produit introuvable ou non louable."},
                status=status.HTTP_400_BAD_REQUEST)

        def _parse_date(key):
            raw = (request.data.get(key) or '').strip()
            if not raw:
                return None
            from datetime import date as _date
            try:
                return _date.fromisoformat(raw)
            except ValueError:
                return None

        date_reservation = _parse_date('date_reservation')
        date_enlevement = _parse_date('date_enlevement_prevue')
        date_retour = _parse_date('date_retour_prevue')
        if not (date_reservation and date_enlevement and date_retour):
            return Response(
                {'detail': 'date_reservation, date_enlevement_prevue et '
                           'date_retour_prevue sont requises (AAAA-MM-JJ).'},
                status=status.HTTP_400_BAD_REQUEST)

        client_id = request.data.get('client_id')
        if not client_id:
            return Response(
                {'client_id': 'Requis.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ordre = services.creer_ordre_location(
                request.user.company,
                client_id=client_id,
                produit=produit,
                numero_serie=request.data.get('numero_serie', ''),
                date_reservation=date_reservation,
                date_enlevement_prevue=date_enlevement,
                date_retour_prevue=date_retour,
                tarif_jour=request.data.get('tarif_jour') or None,
                frais_retard_jour=request.data.get(
                    'frais_retard_jour') or None,
                note=request.data.get('note', ''),
                created_by=request.user,
            )
        except services.OrdreLocationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            OrdreLocationSerializer(
                ordre, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Transition GARDÉE du statut local de l'ordre de location."""
        ordre = self.get_object()
        serializer = ChangerStatutOrdreLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.changer_statut_ordre_location(
                ordre, serializer.validated_data['statut'])
        except services.OrdreLocationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            OrdreLocationSerializer(
                ordre, context={'request': request}).data)

    @action(detail=False, methods=['get'])
    def disponibilite(self, request):
        """GET /ordres-location/disponibilite/?produit=<id>&numero_serie=&
        date_debut=&date_fin= (XCTR17)."""
        produit_id = request.query_params.get('produit')
        if not produit_id:
            return Response(
                {'detail': 'produit requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        def _parse_date(key):
            raw = (request.query_params.get(key) or '').strip()
            if not raw:
                return None
            from datetime import date as _date
            try:
                return _date.fromisoformat(raw)
            except ValueError:
                return None

        result = selectors.disponibilite_produit(
            request.user.company, produit_id,
            numero_serie=request.query_params.get('numero_serie'),
            date_debut=_parse_date('date_debut'),
            date_fin=_parse_date('date_fin'))
        return Response(result)

    # ── XCTR18 — Caution (dépôt de garantie) ────────────────────────────────

    @action(detail=True, methods=['post'], url_path='caution/encaisser')
    def caution_encaisser(self, request, pk=None):
        ordre = self.get_object()
        try:
            services.encaisser_caution(
                ordre, montant=request.data.get('montant'),
                auteur=request.user)
        except services.CautionLocationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            OrdreLocationSerializer(
                ordre, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='caution/restituer')
    def caution_restituer(self, request, pk=None):
        ordre = self.get_object()
        try:
            services.restituer_caution(ordre, auteur=request.user)
        except services.CautionLocationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            OrdreLocationSerializer(
                ordre, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='caution/retenir')
    def caution_retenir(self, request, pk=None):
        ordre = self.get_object()
        try:
            resultat = services.retenir_caution_partielle(
                ordre,
                montant_retenu=request.data.get('montant_retenu'),
                motif=request.data.get('motif', ''),
                user=request.user, auteur=request.user)
        except services.CautionLocationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'ordre': OrdreLocationSerializer(
                    resultat['ordre'], context={'request': request}).data,
                'facture_id': resultat['facture'].id,
                'facture_reference': resultat['facture'].reference,
            },
            status=status.HTTP_201_CREATED,
        )

    # ── XCTR19 — Retour de location : retards, frais, inspection ────────────

    @action(detail=False, methods=['get'], url_path='en-retard')
    def en_retard(self, request):
        """GET /ordres-location/en-retard/ (XCTR19) — ordres enlevés dont le
        retour prévu est dépassé sans retour effectif."""
        ordres = selectors.ordres_location_en_retard(request.user.company)
        page = self.paginate_queryset(ordres)
        serializer = OrdreLocationSerializer(
            page if page is not None else ordres, many=True,
            context={'request': request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='cloturer')
    def cloturer(self, request, pk=None):
        """Clôture l'ordre RETOURNÉ, facture les frais de retard éventuels."""
        ordre = self.get_object()
        try:
            services.cloturer_ordre_location(ordre, user=request.user)
        except services.RetourLocationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            OrdreLocationSerializer(
                ordre, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='inspecter')
    def inspecter(self, request, pk=None):
        """Enregistre l'inspection de retour (checklist + relevé + dommages
        chiffrés éventuels → ligne de facture + ticket SAV)."""
        ordre = self.get_object()
        try:
            resultat = services.inspecter_retour(
                ordre,
                checklist=request.data.get('checklist'),
                releve_compteur=request.data.get('releve_compteur', ''),
                dommages_montant=request.data.get('dommages_montant'),
                motif_dommages=request.data.get('motif_dommages', ''),
                user=request.user)
        except services.RetourLocationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        payload = OrdreLocationSerializer(
            resultat['ordre'], context={'request': request}).data
        payload['ticket_id'] = resultat['ticket_id']
        return Response(payload)

    # ── XCTR20 — Location longue durée : récurrence + prolongation/écourtage

    @action(detail=True, methods=['post'], url_path='facturer-cycle')
    def facturer_cycle(self, request, pk=None):
        """Émet UNE facture de cycle récurrent (XCTR20)."""
        ordre = self.get_object()
        try:
            facture = services.facturer_ordre_location_recurrent(
                ordre, user=request.user,
                periode=request.data.get('periode'))
        except services.RetourLocationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'facture_id': facture.id,
                'facture_reference': facture.reference,
                'ordre': OrdreLocationSerializer(
                    ordre, context={'request': request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def prolonger(self, request, pk=None):
        """Prolonge l'ordre (nouvelle date de retour, re-vérifie la
        disponibilité) — XCTR20."""
        ordre = self.get_object()
        serializer = ProlongerOrdreLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.prolonger_ordre_location(
                ordre,
                nouvelle_date_retour=serializer.validated_data[
                    'nouvelle_date_retour'])
        except services.OrdreLocationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            OrdreLocationSerializer(
                ordre, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def ecourter(self, request, pk=None):
        """Écourte l'ordre : delta → avoir — XCTR20."""
        ordre = self.get_object()
        serializer = EcourterOrdreLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resultat = services.ecourter_ordre_location(
                ordre,
                nouvelle_date_retour=serializer.validated_data[
                    'nouvelle_date_retour'],
                user=request.user)
        except services.OrdreLocationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        payload = OrdreLocationSerializer(
            resultat['ordre'], context={'request': request}).data
        avoir = resultat['avoir']
        payload['avoir_id'] = avoir.id if avoir is not None else None
        payload['avoir_reference'] = avoir.reference if avoir is not None else None
        return Response(payload)

    # ── XCTR21 — Utilisation & ROI du parc de location (ADMIN-ONLY) ─────────

    @action(detail=False, methods=['get'], permission_classes=[IsAdminRole])
    def utilisation(self, request):
        """GET /ordres-location/utilisation/?periode=AAAA-MM (XCTR21).

        ADMIN-ONLY (403 pour tout autre rôle) : le rapport inclut
        ``prix_achat``/``payback``, jamais client-facing. ``?periode=`` fixe
        le mois analysé (défaut : mois courant)."""
        from datetime import date as _date
        import calendar

        from django.utils import timezone

        raw = (request.query_params.get('periode') or '').strip()
        today = timezone.localdate()
        if raw:
            try:
                annee, mois = (int(p) for p in raw.split('-', 1))
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'periode invalide (AAAA-MM attendu).'},
                    status=status.HTTP_400_BAD_REQUEST)
        else:
            annee, mois = today.year, today.month

        periode_debut = _date(annee, mois, 1)
        dernier_jour = calendar.monthrange(annee, mois)[1]
        periode_fin = _date(annee, mois, dernier_jour)

        rows = selectors.utilisation_parc_location(
            request.user.company, periode_debut=periode_debut,
            periode_fin=periode_fin, admin=True)

        def _fmt(row):
            out = dict(row)
            out['taux_utilisation'] = float(out['taux_utilisation'])
            out['revenu_locatif'] = _money(out['revenu_locatif'])
            if 'prix_achat' in out:
                out['prix_achat'] = _money(out['prix_achat'])
            if out.get('payback') is not None:
                out['payback'] = float(out['payback'])
            return out

        return Response({
            'periode_debut': periode_debut.isoformat(),
            'periode_fin': periode_fin.isoformat(),
            'results': [_fmt(r) for r in rows],
        })

    @action(detail=True, methods=['get'], url_path='bon-enlevement')
    def bon_enlevement(self, request, pk=None):
        """Bon d'enlèvement PDF de cet ordre de location — ZCTR5.

        Rendu par le WeasyPrint générique existant (jamais le moteur devis
        premium ``/proposal``). Aucun statut modifié par le rendu."""
        ordre = self.get_object()
        from .pdf_location import generate_bon_enlevement_pdf

        pdf_bytes = generate_bon_enlevement_pdf(ordre)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="Bon_enlevement_{ordre.id}.pdf"')
        return resp

    @action(detail=True, methods=['get'], url_path='bon-restitution')
    def bon_restitution(self, request, pk=None):
        """Bon de restitution PDF de cet ordre de location — ZCTR5.

        Reprend l'inspection de retour (XCTR19) et les dommages chiffrés le
        cas échéant. Rendu par le WeasyPrint générique existant. Aucun
        statut modifié par le rendu."""
        ordre = self.get_object()
        from .pdf_location import generate_bon_restitution_pdf

        pdf_bytes = generate_bon_restitution_pdf(ordre)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="Bon_restitution_{ordre.id}.pdf"')
        return resp

    @action(detail=False, methods=['post'],
            url_path=r'depuis-devis/(?P<devis_id>[0-9]+)')
    def depuis_devis(self, request, devis_id=None):
        """Crée un ``OrdreLocation`` par ligne louable d'un devis ACCEPTÉ —
        ZCTR6 (``POST /ordres-location/depuis-devis/<devis_id>/``).

        Corps optionnel : ``date_enlevement_prevue``/``date_retour_prevue``
        (AAAA-MM-JJ), appliquées à tous les ordres créés — repli demain →
        +7 jours si absentes. Idempotent (re-run = 0 doublon). Le devis doit
        appartenir à la société courante et être ACCEPTÉ, sinon 400. Le
        ``Devis.statut`` n'est JAMAIS modifié (règle #4)."""
        from apps.ventes.selectors import get_devis_by_pk

        devis = get_devis_by_pk(devis_id)
        if devis is None:
            return Response(
                {'detail': 'Devis introuvable.'},
                status=status.HTTP_404_NOT_FOUND)

        def _parse_date(key):
            raw = (request.data.get(key) or '').strip()
            if not raw:
                return None
            from datetime import date as _date
            try:
                return _date.fromisoformat(raw)
            except ValueError:
                return None

        try:
            ordres = services.creer_ordres_location_depuis_devis(
                devis, company=request.user.company,
                created_by=request.user,
                date_enlevement_prevue=_parse_date(
                    'date_enlevement_prevue'),
                date_retour_prevue=_parse_date('date_retour_prevue'),
            )
        except services.OrdreLocationError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            OrdreLocationSerializer(ordres, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class PlanRecurrentViewSet(_ContratsBaseViewSet):
    """Plans de facturation récurrente réutilisables (nommés) — ZCTR1.

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR
    (``perform_create`` du ``TenantMixin`` — jamais lue du corps de requête).
    CRUD complet. Filtre ``?actif=1``.
    """
    queryset = PlanRecurrent.objects.all()
    serializer_class = PlanRecurrentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom', 'date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui'))
        return qs


class MotifResiliationViewSet(_ContratsBaseViewSet):
    """Référentiel éditable des motifs de résiliation (close reasons) — ZCTR3.

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR
    (``perform_create`` du ``TenantMixin`` — jamais lue du corps de requête).
    CRUD complet. Filtre ``?actif=1``.
    """
    queryset = MotifResiliation.objects.all()
    serializer_class = MotifResiliationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle']
    ordering_fields = ['ordre', 'libelle', 'date_creation', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui'))
        return qs


class ParametresLocationViewSet(_ContratsBaseViewSet):
    """Réglages de location, SINGLETON par société — ZCTR4.

    ``GET/PATCH /parametres-location/courant/`` lit/modifie la ligne unique de
    la société (créée à la volée, ``get_or_create``) ; ``company`` posée CÔTÉ
    SERVEUR (jamais lue du corps de requête). Le CRUD standard reste
    disponible (scopé société) mais ``courant/`` est le point d'entrée
    recommandé côté frontend (jamais deux lignes par société — contrainte
    ``OneToOneField``).
    """
    queryset = ParametresLocation.objects.all()
    serializer_class = ParametresLocationSerializer

    @action(detail=False, methods=['get', 'patch'], url_path='courant')
    def courant(self, request):
        parametres, _ = ParametresLocation.objects.get_or_create(
            company=request.user.company)
        if request.method == 'GET':
            return Response(
                ParametresLocationSerializer(parametres).data)
        serializer = ParametresLocationSerializer(
            parametres, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# NTSUB1-4 — Revenus récurrents : catalogue d'offres, add-ons, paliers d'usage,
# compteurs génériques.
# ---------------------------------------------------------------------------


class PlanAbonnementViewSet(_ContratsBaseViewSet):
    """Catalogue d'offres commerciales (« Product Catalog ») — NTSUB1.

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR. CRUD
    complet. Filtre ``?actif=1``.
    """
    queryset = PlanAbonnement.objects.all()
    serializer_class = PlanAbonnementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom']
    ordering_fields = ['nom', 'prix_base', 'created_at', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui'))
        return qs


class AddOnAbonnementViewSet(_ContratsBaseViewSet):
    """Add-ons (options payantes) du catalogue — NTSUB2.

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR. CRUD
    complet. Filtres ``?actif=1``, ``?plan_abonnement=<id>``.
    """
    queryset = AddOnAbonnement.objects.all()
    serializer_class = AddOnAbonnementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom']
    ordering_fields = ['nom', 'prix_unitaire', 'created_at', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui'))
        plan_abonnement = self.request.query_params.get('plan_abonnement')
        if plan_abonnement:
            qs = qs.filter(plan_abonnement_id=plan_abonnement)
        return qs


class AbonnementAddOnLigneViewSet(_ContratsBaseViewSet):
    """Rattachement d'un add-on à une cible (contrat/maintenance SAV) — NTSUB2.

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR. Filtres
    ``?type_cible=<contrat|sav_maintenance>&cible_id=<id>``.
    """
    queryset = AbonnementAddOnLigne.objects.all()
    serializer_class = AbonnementAddOnLigneSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['actif_depuis', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        type_cible = self.request.query_params.get('type_cible')
        if type_cible:
            qs = qs.filter(type_cible=type_cible)
        cible_id = self.request.query_params.get('cible_id')
        if cible_id:
            qs = qs.filter(cible_id=cible_id)
        return qs


class PalierUsageViewSet(_ContratsBaseViewSet):
    """Paliers de prix (tiered/volume pricing) pour la facturation à l'usage — NTSUB3.

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR. Filtres
    ``?addon=<id>``, ``?plan_abonnement=<id>``.
    """
    queryset = PalierUsage.objects.all()
    serializer_class = PalierUsageSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['seuil_min', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        addon = self.request.query_params.get('addon')
        if addon:
            qs = qs.filter(addon_id=addon)
        plan_abonnement = self.request.query_params.get('plan_abonnement')
        if plan_abonnement:
            qs = qs.filter(plan_abonnement_id=plan_abonnement)
        return qs


class CompteurUsageViewSet(_ContratsBaseViewSet):
    """Compteurs d'usage génériques (metering) — NTSUB4.

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR. La
    CRÉATION (``POST``) est IDEMPOTENTE par ``(type_cible, cible_id,
    code_compteur, periode_debut, periode_fin)`` : ré-ingérer la même période
    MET À JOUR la quantité au lieu de créer un doublon (``services.
    ingerer_compteur_usage`` — ``update_or_create``, jamais un 400/409 de
    contrainte d'unicité). Filtres ``?type_cible=&cible_id=&code_compteur=``.
    """
    queryset = CompteurUsage.objects.all()
    serializer_class = CompteurUsageSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['periode_debut', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        type_cible = self.request.query_params.get('type_cible')
        if type_cible:
            qs = qs.filter(type_cible=type_cible)
        cible_id = self.request.query_params.get('cible_id')
        if cible_id:
            qs = qs.filter(cible_id=cible_id)
        code_compteur = self.request.query_params.get('code_compteur')
        if code_compteur:
            qs = qs.filter(code_compteur=code_compteur)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        compteur, _cree = services.ingerer_compteur_usage(
            request.user.company,
            type_cible=data['type_cible'], cible_id=data['cible_id'],
            code_compteur=data['code_compteur'],
            periode_debut=data['periode_debut'],
            periode_fin=data['periode_fin'],
            quantite=data.get('quantite', 0),
            source=data.get('source', CompteurUsage.Source.MANUEL),
        )
        out = self.get_serializer(compteur)
        return Response(out.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# NTSUB8 — Séquences de dunning (relances impayés multi-étapes)
# ---------------------------------------------------------------------------


class SequenceDunningViewSet(_ContratsBaseViewSet):
    """Séquences de dunning (relances impayés) — NTSUB8.

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR. CRUD
    complet + étapes en lecture imbriquée. Filtre ``?actif=1``.
    """
    queryset = SequenceDunning.objects.all()
    serializer_class = SequenceDunningSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom', 'created_at', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'oui'))
        return qs


class EtapeDunningViewSet(_ContratsBaseViewSet):
    """Étapes d'une séquence de dunning — NTSUB8.

    Scopé société (``TenantMixin``) ; ``company`` posée CÔTÉ SERVEUR. Filtre
    ``?sequence=<id>``.
    """
    queryset = EtapeDunning.objects.all()
    serializer_class = EtapeDunningSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'jour_offset', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        sequence = self.request.query_params.get('sequence')
        if sequence:
            qs = qs.filter(sequence_id=sequence)
        return qs
