"""Vues du module Gestion de flotte (toutes scopées société).

La flotte est INTERNE. Chaque viewset filtre par ``request.user.company``
(``TenantMixin``) et pose la société côté serveur ; aucune société n'est jamais
acceptée du corps de requête (multi-tenant).
"""
import datetime

from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from .models import (
    ActifFlotte,
    AffectationConducteur,
    AssuranceVehicule,
    BaremeVignette,
    CarteCarburant,
    CarteGriseVehicule,
    Conducteur,
    DemandeVehicule,
    EcheanceEntretien,
    EcheanceReglementaire,
    EnginRoulant,
    EtatDesLieux,
    Garage,
    Infraction,
    OrdreReparation,
    PieceFlotte,
    PlanEntretien,
    Pneumatique,
    PleinCarburant,
    ReferentielFlotte,
    ReleveTelematique,
    ReservationVehicule,
    Sinistre,
    TrajetChantier,
    TrajetTelematique,
    Vehicule,
    VisiteTechnique,
)
from .serializers import (
    ActifFlotteSerializer,
    AffectationConducteurSerializer,
    AssuranceVehiculeSerializer,
    BaremeVignetteSerializer,
    CarteCarburantSerializer,
    CarteGriseVehiculeSerializer,
    ConducteurSerializer,
    EcheanceEntretienSerializer,
    EcheanceReglementaireSerializer,
    EnginRoulantSerializer,
    EtatDesLieuxSerializer,
    GarageSerializer,
    InfractionSerializer,
    OrdreReparationSerializer,
    PieceFlotteSerializer,
    PlanEntretienSerializer,
    PneumatiqueSerializer,
    PleinCarburantSerializer,
    DemandeVehiculeSerializer,
    ReferentielFlotteSerializer,
    ReleveTelematiqueSerializer,
    ReservationVehiculeSerializer,
    SinistreSerializer,
    TrajetChantierSerializer,
    TrajetTelematiqueSerializer,
    VehiculeSerializer,
    VisiteTechniqueSerializer,
)

READ_ACTIONS = ['list', 'retrieve', 'consommation', 'anomalies', 'echeances',
                'couts', 'synthese', 'expirantes', 'tsav', 'alertes_echeances',
                'tco', 'eco_conduite', 'documents', 'tableau_bord', 'journal',
                'amortissement']


class _FlotteBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée (TenantMixin). Lecture tout rôle, écriture
    responsable/admin."""

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class VehiculeViewSet(_FlotteBaseViewSet):
    """Véhicules immatriculés du parc (FLOTTE2). Filtrable par énergie/statut,
    recherche par immatriculation/marque/modèle."""
    queryset = Vehicule.objects.all()
    serializer_class = VehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['immatriculation', 'marque', 'modele']
    ordering_fields = ['immatriculation', 'kilometrage', 'statut',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        energie = params.get('energie')
        if energie:
            qs = qs.filter(energie=energie)
        return qs

    @action(detail=True, methods=['get'])
    def tsav(self, request, pk=None):
        """FLOTTE20 — Vignette / TSAV due par ce véhicule (lecture tout rôle).

        Calcule le montant via le barème éditable de la société
        (``selectors.calcul_tsav``) à partir de l'énergie et de la puissance
        fiscale du véhicule. ``?annee=N`` cible un barème daté (retombe sur le
        barème générique sinon). Renvoie ``montant`` (``null`` si aucune tranche
        ne correspond ou si la puissance fiscale est inconnue), ``exonere`` et
        une ``note`` lisible.
        """
        vehicule = self.get_object()

        annee = None
        annee_param = request.query_params.get('annee')
        if annee_param:
            try:
                annee = int(annee_param)
            except (ValueError, TypeError):
                annee = None

        from .selectors import calcul_tsav
        return Response(calcul_tsav(vehicule, annee=annee))

    @action(detail=True, methods=['get'])
    def tco(self, request, pk=None):
        """FLOTTE31 — Coût total de possession (TCO) du véhicule (tout rôle).

        Agrège les coûts internes du véhicule (carburant, réparations, pneus/
        pièces, infractions, sinistres) en un coût total + coût par km, via
        ``selectors.tco_vehicule``. Lecture seule, scopée société.
        """
        vehicule = self.get_object()
        from .selectors import tco_vehicule
        return Response(tco_vehicule(request.user.company, vehicule.id))

    @action(detail=True, methods=['get'], url_path='eco-conduite')
    def eco_conduite(self, request, pk=None):
        """FLOTTE33 — Éco-conduite & empreinte CO₂ du véhicule (tout rôle).

        Calcule les émissions de CO₂ (tank-to-wheel), la consommation moyenne,
        l'intensité carbone (g CO₂/km) et un score d'éco-conduite via
        ``selectors.eco_conduite_co2``. Lecture seule, scopée société.
        """
        vehicule = self.get_object()
        from .selectors import eco_conduite_co2
        return Response(eco_conduite_co2(request.user.company, vehicule.id))

    @action(detail=True, methods=['get'])
    def amortissement(self, request, pk=None):
        """FLOTTE30 — Amortissement (VNC) du véhicule via son immobilisation.

        Lit l'amortissement comptable lié au véhicule (FLOTTE30) via
        ``selectors.amortissement_vehicule`` (lecture cross-app du module compta,
        jamais d'écriture). Lecture seule, scopée société.
        """
        vehicule = self.get_object()
        from .selectors import amortissement_vehicule
        return Response(
            amortissement_vehicule(request.user.company, vehicule.id))

    @action(detail=False, methods=['get'], url_path='tableau-bord')
    def tableau_bord(self, request):
        """FLOTTE35 — Tableau de bord flotte (dispo / échéances / coûts / conso).

        Synthèse société : véhicules/engins par statut + disponibles, échéances
        réglementaires par urgence (FLOTTE24), coûts réparations + carburant,
        entretien ouvert et demandes de pool en attente, via
        ``selectors.tableau_bord_flotte``. Lecture seule (tout rôle).
        """
        from .selectors import tableau_bord_flotte
        return Response(tableau_bord_flotte(request.user.company))


class EnginRoulantViewSet(_FlotteBaseViewSet):
    """Engins roulants suivis au compteur d'heures (FLOTTE4). Filtrable par
    type/statut, recherche par désignation/marque/modèle."""
    queryset = EnginRoulant.objects.all()
    serializer_class = EnginRoulantSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'marque', 'modele']
    ordering_fields = ['nom', 'compteur_heures', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        type_engin = params.get('type_engin')
        if type_engin:
            qs = qs.filter(type_engin=type_engin)
        return qs


class ReferentielFlotteViewSet(_FlotteBaseViewSet):
    """Listes de référence éditables du parc (FLOTTE6). Filtrable par
    ``?domaine=`` (type_vehicule/type_engin/energie/categorie_permis) et par
    ``?actif=true|false``, recherche par code/libellé."""
    queryset = ReferentielFlotte.objects.all()
    serializer_class = ReferentielFlotteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle']
    ordering_fields = ['domaine', 'ordre', 'libelle', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        domaine = params.get('domaine')
        if domaine:
            qs = qs.filter(domaine=domaine)
        actif = params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'vrai', 'oui'))
        return qs


class ConducteurViewSet(_FlotteBaseViewSet):
    """Conducteurs / chauffeurs du parc (FLOTTE7).

    Filtrable par ``?actif=true|false`` et ``?permis_expirant=<jours>`` (permis
    expirant dans les N prochains jours, 30 par défaut). Recherche par nom,
    numéro de permis et téléphone.
    """
    queryset = Conducteur.objects.select_related('user')
    serializer_class = ConducteurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'numero_permis', 'telephone']
    ordering_fields = ['nom', 'date_expiration', 'actif', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        actif = params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'vrai', 'oui'))

        permis_expirant = params.get('permis_expirant')
        if permis_expirant is not None:
            try:
                jours = int(permis_expirant)
            except (ValueError, TypeError):
                jours = 30
            today = datetime.date.today()
            horizon = today + datetime.timedelta(days=jours)
            qs = qs.filter(
                date_expiration__isnull=False,
                date_expiration__gte=today,
                date_expiration__lte=horizon,
            )
        return qs


class ActifFlotteViewSet(_FlotteBaseViewSet):
    """Références d'actif unifiées (FLOTTE5) — Vehicule | EnginRoulant.

    Chaque ``ActifFlotte`` pointe vers SOIT un véhicule SOIT un engin roulant
    de la même société, permettant aux futurs modules entretien/sinistre/
    document de se rattacher à l'un ou l'autre via un FK unique.

    Filtrable par ``?type_actif=vehicule`` ou ``?type_actif=engin``.
    """
    queryset = ActifFlotte.objects.select_related('vehicule', 'engin')
    serializer_class = ActifFlotteSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        type_actif = self.request.query_params.get('type_actif')
        if type_actif == ActifFlotte.TYPE_VEHICULE:
            qs = qs.filter(vehicule__isnull=False)
        elif type_actif == ActifFlotte.TYPE_ENGIN:
            qs = qs.filter(engin__isnull=False)
        return qs

    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """FLOTTE34 — Documents GED liés à l'actif (carte grise, assurance…).

        Lecture (tout rôle), scopée société. Retourne les documents GED rattachés
        à cet actif via ``selectors.documents_ged_pour_actif`` (lecture cross-app
        de la GED, jamais d'écriture). Chaque entrée porte id / nom / statut /
        date du document GED.
        """
        actif = self.get_object()
        from .selectors import documents_ged_pour_actif
        docs = documents_ged_pour_actif(request.user.company, actif.id)
        data = [
            {
                'id': doc.id,
                'nom': getattr(doc, 'nom', ''),
                'statut': getattr(doc, 'statut', None),
                'date_creation': getattr(doc, 'date_creation', None),
            }
            for doc in docs
        ]
        return Response(data)


class AffectationConducteurViewSet(_FlotteBaseViewSet):
    """Affectations datées conducteur ↔ véhicule (FLOTTE8).

    Filtrable par ``?vehicule=<id>``, ``?conducteur=<id>`` et
    ``?actif=true|false``. Toutes les affectations sont scopées par société.
    """
    queryset = AffectationConducteur.objects.select_related(
        'conducteur', 'vehicule')
    serializer_class = AffectationConducteurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_fin', 'actif', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        vehicule = params.get('vehicule')
        if vehicule:
            try:
                qs = qs.filter(vehicule_id=int(vehicule))
            except (ValueError, TypeError):
                pass

        conducteur = params.get('conducteur')
        if conducteur:
            try:
                qs = qs.filter(conducteur_id=int(conducteur))
            except (ValueError, TypeError):
                pass

        actif = params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'vrai', 'oui'))

        return qs


class ReservationVehiculeViewSet(_FlotteBaseViewSet):
    """Réservations de véhicules avec détection de conflit (FLOTTE10).

    Filtrable par ``?vehicule=<id>``, ``?statut=<demandee|confirmee|annulee>``
    et ``?actives=true`` (réservations qui occupent le véhicule). Recherche par
    motif. Toutes les réservations sont scopées par société.
    """
    queryset = ReservationVehicule.objects.select_related(
        'vehicule', 'conducteur')
    serializer_class = ReservationVehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['motif']
    ordering_fields = ['debut', 'fin', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        vehicule = params.get('vehicule')
        if vehicule:
            try:
                qs = qs.filter(vehicule_id=int(vehicule))
            except (ValueError, TypeError):
                pass

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        actives = params.get('actives')
        if actives is not None and actives.lower() in ('1', 'true', 'vrai',
                                                       'oui'):
            qs = qs.filter(statut__in=ReservationVehicule.STATUTS_ACTIFS)

        return qs


class EtatDesLieuxViewSet(_FlotteBaseViewSet):
    """Check-lists d'état des lieux départ/retour avec photos (FLOTTE11).

    Filtrable par ``?vehicule=<id>``, ``?moment=<depart|retour>`` et
    ``?reservation=<id>``. Recherche par commentaire. Scopé par société.
    """
    queryset = EtatDesLieux.objects.select_related(
        'vehicule', 'conducteur', 'reservation')
    serializer_class = EtatDesLieuxSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['commentaire']
    ordering_fields = ['date_constat', 'moment', 'kilometrage', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        vehicule = params.get('vehicule')
        if vehicule:
            try:
                qs = qs.filter(vehicule_id=int(vehicule))
            except (ValueError, TypeError):
                pass

        moment = params.get('moment')
        if moment:
            qs = qs.filter(moment=moment)

        reservation = params.get('reservation')
        if reservation:
            try:
                qs = qs.filter(reservation_id=int(reservation))
            except (ValueError, TypeError):
                pass

        return qs


class PleinCarburantViewSet(_FlotteBaseViewSet):
    """Carnet de carburant (FLOTTE12).

    Filtrable par ``?vehicule=<id>`` et ``?unite=<litre|kwh>``. Recherche par
    station. Scopé par société. Le kilométrage est validé cohérent (compteur
    monotone croissant) au sérialiseur.
    """
    queryset = PleinCarburant.objects.select_related('vehicule', 'conducteur')
    serializer_class = PleinCarburantSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['station']
    ordering_fields = ['date_plein', 'kilometrage', 'prix_total',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        vehicule = params.get('vehicule')
        if vehicule:
            try:
                qs = qs.filter(vehicule_id=int(vehicule))
            except (ValueError, TypeError):
                pass

        unite = params.get('unite')
        if unite:
            qs = qs.filter(unite=unite)

        return qs

    @action(detail=False, methods=['get'])
    def consommation(self, request):
        """FLOTTE13 — Consommation calculée d'un véhicule (L/100 km et
        kWh/100 km), à partir du carnet de carburant et du kilométrage.

        ``?vehicule=<id>`` (obligatoire). Lecture seule, scopée société : le
        véhicule doit appartenir à la société courante (sinon 404, comme la
        liste). Renvoie l'agrégat par unité + le détail des segments
        plein-à-plein (voir ``selectors.consommation_vehicule``).
        """
        company = request.user.company
        vehicule_param = request.query_params.get('vehicule')
        if not vehicule_param:
            return Response(
                {'vehicule': "Le paramètre 'vehicule' est obligatoire."},
                status=400)
        try:
            vehicule_id = int(vehicule_param)
        except (ValueError, TypeError):
            return Response(
                {'vehicule': "Le paramètre 'vehicule' doit être un entier."},
                status=400)

        # Scope société : le véhicule doit appartenir à la société courante.
        if not Vehicule.objects.filter(
                company=company, id=vehicule_id).exists():
            return Response(
                {'vehicule': "Véhicule introuvable pour cette société."},
                status=404)

        from .selectors import consommation_vehicule
        return Response(consommation_vehicule(company, vehicule_id))


class CarteCarburantViewSet(_FlotteBaseViewSet):
    """Cartes carburant de la société + alertes d'anomalie (FLOTTE14).

    CRUD scopé société (écriture responsable/admin). Filtrable par
    ``?vehicule=<id>`` et ``?actif=true|false``. Recherche par numéro.

    L'action de lecture ``GET /cartes/anomalies/`` liste les pleins suspects du
    carnet de carburant (kilométrage incohérent / saut invraisemblable,
    consommation aberrante vs la ligne de base du véhicule, dépassement du
    plafond de carte). Optionnellement scopée à un ``?vehicule=<id>`` (404 si le
    véhicule n'appartient pas à la société).
    """
    queryset = CarteCarburant.objects.select_related('vehicule', 'conducteur')
    serializer_class = CarteCarburantSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero']
    ordering_fields = ['numero', 'actif', 'plafond', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        vehicule = params.get('vehicule')
        if vehicule:
            try:
                qs = qs.filter(vehicule_id=int(vehicule))
            except (ValueError, TypeError):
                pass

        actif = params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'vrai', 'oui'))

        return qs

    @action(detail=False, methods=['get'])
    def anomalies(self, request):
        """FLOTTE14 — Pleins suspects (km incohérent / fraude).

        Lecture seule, scopée société. ``?vehicule=<id>`` (facultatif) restreint
        la détection à un véhicule, qui doit appartenir à la société courante
        (sinon 404). Renvoie l'agrégat des anomalies (voir
        ``selectors.anomalies_pleins``).
        """
        company = request.user.company
        vehicule_id = None
        vehicule_param = request.query_params.get('vehicule')
        if vehicule_param:
            try:
                vehicule_id = int(vehicule_param)
            except (ValueError, TypeError):
                return Response(
                    {'vehicule':
                     "Le paramètre 'vehicule' doit être un entier."},
                    status=400)
            if not Vehicule.objects.filter(
                    company=company, id=vehicule_id).exists():
                return Response(
                    {'vehicule': "Véhicule introuvable pour cette société."},
                    status=404)

        from .selectors import anomalies_pleins
        return Response(anomalies_pleins(company, vehicule_id))


class PlanEntretienViewSet(_FlotteBaseViewSet):
    """Plans d'entretien préventif km/date/heures (FLOTTE15).

    CRUD scopé société (écriture responsable/admin). Filtrable par
    ``?actif_flotte=<id>`` et ``?actif=true|false``. Recherche par type
    d'entretien.

    L'action de lecture ``GET /plans-entretien/echeances/`` calcule, pour chaque
    plan actif de la société, son statut (``due`` / ``upcoming`` / ``ok`` /
    ``inconnu``) vs l'état COURANT de l'actif ciblé (kilométrage du véhicule,
    compteur d'heures de l'engin, date du jour). ``?statut=due|upcoming|ok|inconnu``
    restreint la liste. Lecture seule (voir
    ``selectors.plans_entretien_status``).
    """
    queryset = PlanEntretien.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    serializer_class = PlanEntretienSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['type_entretien']
    ordering_fields = ['type_entretien', 'actif', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        actif = params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'vrai', 'oui'))

        return qs

    @action(detail=False, methods=['get'])
    def echeances(self, request):
        """FLOTTE15 — Entretiens DUS / À VENIR de la société.

        Lecture seule, scopée société. ``?statut=due|upcoming|ok|inconnu``
        (facultatif) restreint la liste ; ``?inclure_inactifs=true`` inclut les
        plans désactivés (par défaut seuls les plans actifs sont examinés).
        Renvoie l'agrégat des échéances (voir
        ``selectors.plans_entretien_status``).
        """
        company = request.user.company
        statut = request.query_params.get('statut')

        inclure = request.query_params.get('inclure_inactifs')
        actif_only = not (
            inclure is not None
            and inclure.lower() in ('1', 'true', 'vrai', 'oui'))

        from .selectors import plans_entretien_status
        return Response(
            plans_entretien_status(company, actif_only=actif_only,
                                   statut=statut))


class EcheanceEntretienViewSet(_FlotteBaseViewSet):
    """Échéances d'entretien dues, générées depuis les plans (FLOTTE16).

    Les échéances ne se CRÉENT pas à la main : elles sont matérialisées côté
    serveur par ``services.generer_echeances_entretien`` (action ``generer``,
    écriture responsable/admin). Le viewset expose donc la LISTE (due / en
    retard), le détail, et l'avancement du ``statut`` (``a_faire`` →
    ``planifie`` → ``fait``) — POST de création est désactivé.

    Filtrable par ``?statut=a_faire|planifie|fait``, ``?ouvertes=true`` (échéances
    encore à traiter) et ``?plan=<id>``. Tout est scopé par société.

    ``POST /echeances-entretien/generer/`` (écriture responsable/admin) lance la
    génération idempotente pour la société courante et renvoie le récapitulatif
    (nombre de plans dus, échéances créées / déjà existantes). ``?alerter=false``
    désactive la diffusion des alertes.
    """
    # Pas de POST de création manuelle : les échéances sont générées via
    # l'action `generer` (POST), jamais créées à la main. On désactive donc le
    # create par défaut (405) tout en gardant POST autorisé pour l'action.
    def create(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed('POST')

    queryset = EcheanceEntretien.objects.select_related(
        'plan', 'actif_flotte', 'actif_flotte__vehicule',
        'actif_flotte__engin')
    serializer_class = EcheanceEntretienSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['type_entretien']
    ordering_fields = ['statut', 'due_le', 'due_km', 'due_heures', 'genere_le']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        ouvertes = params.get('ouvertes')
        if ouvertes is not None and ouvertes.lower() in ('1', 'true', 'vrai',
                                                         'oui'):
            qs = qs.filter(statut__in=EcheanceEntretien.STATUTS_OUVERTS)

        plan = params.get('plan')
        if plan:
            try:
                qs = qs.filter(plan_id=int(plan))
            except (ValueError, TypeError):
                pass

        return qs

    @action(detail=False, methods=['post'])
    def generer(self, request):
        """FLOTTE16 — Génère les échéances dues depuis les plans actifs.

        Écriture (responsable/admin). Scopée société : la génération est
        idempotente (aucun doublon d'échéance ouverte par plan) et pose toujours
        la société côté serveur. ``?alerter=false`` n'envoie aucune alerte.
        Renvoie le récapitulatif + les échéances nouvellement créées.
        """
        company = request.user.company

        alerter_param = request.query_params.get('alerter')
        alerter = not (
            alerter_param is not None
            and alerter_param.lower() in ('0', 'false', 'faux', 'non'))

        from .services import generer_echeances_entretien
        resultat = generer_echeances_entretien(company, alerter=alerter)

        serializer = EcheanceEntretienSerializer(
            resultat['echeances'], many=True,
            context=self.get_serializer_context())
        return Response({
            'nb_plans_due': resultat['nb_plans_due'],
            'nb_creees': resultat['nb_creees'],
            'nb_existantes': resultat['nb_existantes'],
            'echeances': serializer.data,
        })


class GarageViewSet(_FlotteBaseViewSet):
    """Garages / ateliers de réparation de la société (FLOTTE17).

    CRUD scopé société (écriture responsable/admin). Filtrable par
    ``?actif=true|false``. Recherche par nom / adresse / téléphone.
    """
    queryset = Garage.objects.all()
    serializer_class = GarageSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'adresse', 'telephone']
    ordering_fields = ['nom', 'actif', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'vrai', 'oui'))
        return qs


class OrdreReparationViewSet(_FlotteBaseViewSet):
    """Ordres de réparation atelier/garage + coûts (FLOTTE17).

    CRUD scopé société (écriture responsable/admin). Filtrable par
    ``?actif_flotte=<id>``, ``?garage=<id>``, ``?statut=<ouvert|en_cours|
    cloture>`` et ``?ouverts=true`` (OR non clôturés). Recherche par description.
    ``cout_total`` est calculé côté serveur (main d'œuvre + pièces).

    Actions :
    - ``GET /ordres-reparation/couts/`` (lecture tout rôle) — synthèse des coûts
      (totaux + moyenne par OR), filtrable comme la liste.
    - ``POST /ordres-reparation/<id>/cloturer/`` (écriture responsable/admin) —
      clôture l'OR et, par défaut, l'échéance d'entretien liée (``fait``).
      ``?cloturer_echeance=false`` ne touche pas l'échéance.
    """
    queryset = OrdreReparation.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'garage', 'echeance')
    serializer_class = OrdreReparationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'notes']
    ordering_fields = ['date_ouverture', 'date_cloture', 'statut',
                       'cout_total', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        garage = params.get('garage')
        if garage:
            try:
                qs = qs.filter(garage_id=int(garage))
            except (ValueError, TypeError):
                pass

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        ouverts = params.get('ouverts')
        if ouverts is not None and ouverts.lower() in ('1', 'true', 'vrai',
                                                       'oui'):
            qs = qs.exclude(statut__in=OrdreReparation.STATUTS_CLOS)

        return qs

    @action(detail=False, methods=['get'])
    def couts(self, request):
        """FLOTTE17 — Synthèse des coûts de réparation (lecture seule).

        Scopée société. Filtres facultatifs ``?actif_flotte=<id>``,
        ``?garage=<id>``, ``?statut=<…>``. Renvoie totaux + coût moyen par OR
        (``None`` s'il n'y a aucun OR — pas de division par zéro).
        """
        company = request.user.company
        params = request.query_params

        def _int(name):
            value = params.get(name)
            if not value:
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        from .selectors import couts_reparation
        return Response(couts_reparation(
            company,
            actif_flotte_id=_int('actif_flotte'),
            garage_id=_int('garage'),
            statut=params.get('statut'),
        ))

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """FLOTTE17 — Clôture l'OR (et l'échéance liée par défaut).

        Écriture (responsable/admin). ``?cloturer_echeance=false`` laisse
        l'échéance d'entretien liée intacte. Renvoie l'OR clôturé sérialisé.
        """
        ordre = self.get_object()

        param = request.query_params.get('cloturer_echeance')
        cloturer_echeance = not (
            param is not None
            and param.lower() in ('0', 'false', 'faux', 'non'))

        from .services import cloturer_ordre_reparation
        cloturer_ordre_reparation(
            ordre, cloturer_echeance=cloturer_echeance)
        serializer = self.get_serializer(ordre)
        return Response(serializer.data)


class PneumatiqueViewSet(_FlotteBaseViewSet):
    """Pneumatiques montés sur les véhicules du parc (FLOTTE18).

    CRUD scopé société (écriture responsable/admin). Filtrable par
    ``?vehicule=<id>``, ``?position=<av_g|av_d|ar_g|ar_d|secours>``,
    ``?statut=<monte|depose|use>`` et ``?montes=true`` (pneus en service).
    Recherche par marque / dimension. Le véhicule lié doit appartenir à la
    société (validé au sérialiseur).
    """
    queryset = Pneumatique.objects.select_related('vehicule')
    serializer_class = PneumatiqueSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['marque', 'dimension']
    ordering_fields = ['position', 'statut', 'date_montage', 'km_montage',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        vehicule = params.get('vehicule')
        if vehicule:
            try:
                qs = qs.filter(vehicule_id=int(vehicule))
            except (ValueError, TypeError):
                pass

        position = params.get('position')
        if position:
            qs = qs.filter(position=position)

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        montes = params.get('montes')
        if montes is not None and montes.lower() in ('1', 'true', 'vrai',
                                                     'oui'):
            qs = qs.filter(statut__in=Pneumatique.STATUTS_MONTES)

        return qs


class PieceFlotteViewSet(_FlotteBaseViewSet):
    """Pièces détachées posées sur les véhicules du parc (FLOTTE18).

    CRUD scopé société (écriture responsable/admin). Filtrable par
    ``?vehicule=<id>`` et ``?ordre_reparation=<id>``. Recherche par désignation /
    référence. ``cout_total`` (quantité × coût unitaire) est calculé côté
    serveur. Le véhicule et l'OR liés doivent appartenir à la société (validé au
    sérialiseur).

    Action ``GET /pieces/synthese/?vehicule=<id>`` (lecture tout rôle) — synthèse
    pneus + pièces d'un véhicule (compteurs + coûts combinés).
    """
    queryset = PieceFlotte.objects.select_related(
        'vehicule', 'ordre_reparation')
    serializer_class = PieceFlotteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['designation', 'reference']
    ordering_fields = ['designation', 'date_pose', 'cout_unitaire',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        vehicule = params.get('vehicule')
        if vehicule:
            try:
                qs = qs.filter(vehicule_id=int(vehicule))
            except (ValueError, TypeError):
                pass

        ordre = params.get('ordre_reparation')
        if ordre:
            try:
                qs = qs.filter(ordre_reparation_id=int(ordre))
            except (ValueError, TypeError):
                pass

        return qs

    @action(detail=False, methods=['get'])
    def synthese(self, request):
        """FLOTTE18 — Synthèse pneus + pièces d'un véhicule (lecture seule).

        ``?vehicule=<id>`` (obligatoire). Scopée société : le véhicule doit
        appartenir à la société courante (sinon 404). Renvoie les compteurs et
        coûts combinés (voir ``selectors.synthese_pneus_pieces_vehicule``).
        """
        company = request.user.company
        vehicule_param = request.query_params.get('vehicule')
        if not vehicule_param:
            return Response(
                {'vehicule': "Le paramètre 'vehicule' est obligatoire."},
                status=400)
        try:
            vehicule_id = int(vehicule_param)
        except (ValueError, TypeError):
            return Response(
                {'vehicule': "Le paramètre 'vehicule' doit être un entier."},
                status=400)

        if not Vehicule.objects.filter(
                company=company, id=vehicule_id).exists():
            return Response(
                {'vehicule': "Véhicule introuvable pour cette société."},
                status=404)

        from .selectors import synthese_pneus_pieces_vehicule
        return Response(
            synthese_pneus_pieces_vehicule(company, vehicule_id))


class EcheanceReglementaireViewSet(_FlotteBaseViewSet):
    """Échéances réglementaires / administratives des actifs (FLOTTE19).

    CRUD scopé société (écriture responsable/admin) des obligations légales :
    visite technique, assurance, vignette / TSAV, carte grise, taxe à l'essieu…
    Filtrable par ``?type=<…>``, ``?statut=<a_jour|a_renouveler|expire>`` et
    ``?actif_flotte=<id>``. Recherche par organisme / notes. ``statut_calcule``
    (état réel vs la date du jour) est exposé en lecture. L'actif lié doit
    appartenir à la société (validé au sérialiseur).

    Action ``GET /echeances-reglementaires/expirantes/?within=N`` (lecture tout
    rôle) — échéances déjà expirées ou dues dans les ``N`` prochains jours
    (défaut 30), de la plus urgente à la moins urgente.

    Action ``GET /echeances-reglementaires/alertes-echeances/`` (FLOTTE24,
    lecture tout rôle) — moteur unifié d'alertes : agrège toutes les échéances
    réglementaires DUES/IMMINENTES de la société (échéances réglementaires,
    assurances, visites techniques, cartes grises, entretiens datés) et les
    classe par seau d'urgence (``echu`` / ``j7`` / ``j15`` / ``j30``).
    """
    queryset = EcheanceReglementaire.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    serializer_class = EcheanceReglementaireSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['organisme', 'notes']
    ordering_fields = ['type_echeance', 'date_echeance', 'statut', 'cout',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        type_echeance = params.get('type')
        if type_echeance:
            qs = qs.filter(type_echeance=type_echeance)

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        return qs

    @action(detail=False, methods=['get'])
    def expirantes(self, request):
        """FLOTTE19 — Échéances expirées ou dues sous ``?within=N`` jours.

        Lecture (tout rôle), scopée société. ``within`` défaut = 30 jours ;
        une valeur invalide retombe sur 30. Renvoie la liste sérialisée, de la
        plus urgente (déjà expirée) à la moins urgente.
        """
        company = request.user.company

        within_param = request.query_params.get('within')
        within = 30
        if within_param:
            try:
                within = int(within_param)
            except (ValueError, TypeError):
                within = 30

        from .selectors import echeances_reglementaires_expirantes
        qs = echeances_reglementaires_expirantes(company, within=within)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='alertes-echeances')
    def alertes_echeances(self, request):
        """FLOTTE24 — Moteur unifié d'alertes d'échéances réglementaires.

        Lecture (tout rôle), scopée société. Agrège toutes les échéances
        réglementaires DUES ou imminentes (échéances réglementaires,
        assurances, visites techniques, cartes grises, entretiens datés) et les
        classe par seau d'urgence : ``echu`` (date passée), ``j7`` (≤ 7 j),
        ``j15`` (≤ 15 j), ``j30`` (≤ 30 j) — au-delà de 30 j : hors fenêtre.
        Renvoie le dict du sélecteur (compteurs + seaux + liste plate triée).
        """
        company = request.user.company
        from .selectors import alertes_echeances_reglementaires
        return Response(alertes_echeances_reglementaires(company))


class BaremeVignetteViewSet(_FlotteBaseViewSet):
    """Barème éditable de la vignette / TSAV (FLOTTE20).

    CRUD scopé société (écriture responsable/admin) du référentiel des montants
    TSAV par énergie et tranche de chevaux fiscaux (CV). Filtrable par
    ``?energie=<essence|diesel|electrique|hybride>``, ``?annee=<N>`` et
    ``?actif=true|false``. Le calcul du montant pour un véhicule donné passe par
    ``GET /vehicules/{id}/tsav/?annee=N``.
    """
    queryset = BaremeVignette.objects.all()
    serializer_class = BaremeVignetteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['notes']
    ordering_fields = ['annee', 'energie', 'cv_min', 'montant', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        energie = params.get('energie')
        if energie:
            qs = qs.filter(energie=energie)

        annee = params.get('annee')
        if annee:
            try:
                qs = qs.filter(annee=int(annee))
            except (ValueError, TypeError):
                pass

        actif = params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'vrai', 'oui'))

        return qs


class AssuranceVehiculeViewSet(_FlotteBaseViewSet):
    """Polices d'assurance auto des actifs de flotte (FLOTTE21).

    CRUD scopé société (écriture responsable/admin) du CONTRAT d'assurance :
    assureur, numéro de police, période de couverture (début → échéance),
    franchise et attestation (document scanné). Complète — sans la dupliquer —
    l'``EcheanceReglementaire`` générique (FLOTTE19) qui ne porte que la date
    limite administrative. Filtrable par ``?statut=<valide|a_renouveler|expiree>``
    et ``?actif_flotte=<id>``. Recherche par assureur / numéro de police / notes.
    ``statut_calcule`` (état réel vs la date du jour) est exposé en lecture.
    L'actif lié doit appartenir à la société (validé au sérialiseur).

    Action ``GET /assurances/expirantes/?within=N`` (lecture tout rôle) —
    polices déjà expirées ou dues dans les ``N`` prochains jours (défaut 30),
    de la plus urgente à la moins urgente.
    """
    queryset = AssuranceVehicule.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    serializer_class = AssuranceVehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['assureur', 'numero_police', 'notes']
    ordering_fields = ['assureur', 'date_echeance', 'statut', 'franchise',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        return qs

    @action(detail=False, methods=['get'])
    def expirantes(self, request):
        """FLOTTE21 — Polices expirées ou dues sous ``?within=N`` jours.

        Lecture (tout rôle), scopée société. ``within`` défaut = 30 jours ;
        une valeur invalide retombe sur 30. Renvoie la liste sérialisée, de la
        plus urgente (déjà expirée) à la moins urgente.
        """
        company = request.user.company

        within_param = request.query_params.get('within')
        within = 30
        if within_param:
            try:
                within = int(within_param)
            except (ValueError, TypeError):
                within = 30

        from .selectors import assurances_vehicule_expirantes
        qs = assurances_vehicule_expirantes(company, within=within)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class VisiteTechniqueViewSet(_FlotteBaseViewSet):
    """Visites techniques des actifs de flotte (FLOTTE22).

    CRUD scopé société (écriture responsable/admin) du passage en centre de
    contrôle technique : centre, date de visite, résultat (favorable /
    défavorable / contre-visite), validité PARAMÉTRABLE (``validite_mois``,
    12 par défaut) et prochaine visite calculée automatiquement. Complète — sans
    la dupliquer — l'``EcheanceReglementaire`` générique (FLOTTE19) qui ne porte
    que la date limite administrative. Filtrable par
    ``?statut=<valide|a_renouveler|expiree>`` et ``?actif_flotte=<id>``.
    Recherche par centre / notes. ``statut_calcule`` (état réel vs la date du
    jour) est exposé en lecture. L'actif lié doit appartenir à la société
    (validé au sérialiseur).

    Action ``GET /visites-techniques/expirantes/?within=N`` (lecture tout rôle)
    — visites déjà expirées ou dues dans les ``N`` prochains jours (défaut 30),
    de la plus urgente à la moins urgente.
    """
    queryset = VisiteTechnique.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    serializer_class = VisiteTechniqueSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['centre', 'notes']
    ordering_fields = ['centre', 'date_visite', 'date_prochaine', 'statut',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        return qs

    @action(detail=False, methods=['get'])
    def expirantes(self, request):
        """FLOTTE22 — Visites expirées ou dues sous ``?within=N`` jours.

        Lecture (tout rôle), scopée société. ``within`` défaut = 30 jours ;
        une valeur invalide retombe sur 30. Renvoie la liste sérialisée, de la
        plus urgente (déjà expirée) à la moins urgente.
        """
        company = request.user.company

        within_param = request.query_params.get('within')
        within = 30
        if within_param:
            try:
                within = int(within_param)
            except (ValueError, TypeError):
                within = 30

        from .selectors import visites_techniques_expirantes
        qs = visites_techniques_expirantes(company, within=within)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class CarteGriseVehiculeViewSet(_FlotteBaseViewSet):
    """Cartes grises & autorisations de circulation des actifs (FLOTTE23).

    CRUD scopé société (écriture responsable/admin) des DOCUMENTS
    d'immatriculation : numéro de carte grise, dates d'immatriculation / de mise
    en circulation, autorisation de circulation (numéro + date de validité,
    facultatifs) et les deux documents scannés (carte grise, autorisation). Reste
    100 % flotte (aucun couplage à ``apps.ged``). Filtrable par
    ``?statut=<valide|a_renouveler|expiree>`` et ``?actif_flotte=<id>``.
    Recherche par numéro de carte grise / numéro d'autorisation / notes.
    ``statut_calcule`` (état réel de l'autorisation vs la date du jour) est exposé
    en lecture. L'actif lié doit appartenir à la société (validé au sérialiseur).

    Action ``GET /cartes-grises/expirantes/?within=N`` (lecture tout rôle) —
    autorisations de circulation déjà expirées ou dues dans les ``N`` prochains
    jours (défaut 30), de la plus urgente à la moins urgente.
    """
    queryset = CarteGriseVehicule.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    serializer_class = CarteGriseVehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_carte_grise', 'autorisation_circulation_numero',
                     'notes']
    ordering_fields = ['numero_carte_grise', 'date_immatriculation',
                       'autorisation_date_validite', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        return qs

    @action(detail=False, methods=['get'])
    def expirantes(self, request):
        """FLOTTE23 — Autorisations expirées ou dues sous ``?within=N`` jours.

        Lecture (tout rôle), scopée société. ``within`` défaut = 30 jours ;
        une valeur invalide retombe sur 30. Renvoie la liste sérialisée, de la
        plus urgente (déjà expirée) à la moins urgente. Les cartes grises sans
        date de validité d'autorisation sont exclues.
        """
        company = request.user.company

        within_param = request.query_params.get('within')
        within = 30
        if within_param:
            try:
                within = int(within_param)
            except (ValueError, TypeError):
                within = 30

        from .selectors import cartes_grises_expirantes
        qs = cartes_grises_expirantes(company, within=within)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class SinistreViewSet(_FlotteBaseViewSet):
    """Sinistres des actifs de flotte (FLOTTE25).

    CRUD scopé société (écriture responsable/admin) d'un incident impliquant un
    véhicule ou un engin du parc : date, type (accident matériel/corporel, vol,
    bris de glace, incendie, catastrophe naturelle, autre), description, lieu,
    constat amiable scanné, police d'assurance liée (FLOTTE21, même app),
    numéro de déclaration, montants (estimé, franchise) et statut du dossier
    (déclaré → en cours → clos / indemnisé). Filtrable par
    ``?statut=<declare|en_cours|clos|indemnise>``, ``?actif_flotte=<id>`` et
    ``?type_sinistre=<...>``. Recherche par numéro de déclaration / description
    / lieu / notes. L'actif lié ET la police d'assurance liée doivent appartenir
    à la société (validé au sérialiseur).
    """
    queryset = Sinistre.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'assurance')
    serializer_class = SinistreSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_declaration', 'description', 'lieu', 'notes']
    ordering_fields = ['date_sinistre', 'type_sinistre', 'statut',
                       'montant_estime', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        type_sinistre = params.get('type_sinistre')
        if type_sinistre:
            qs = qs.filter(type_sinistre=type_sinistre)

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        return qs


class ReleveTelematiqueViewSet(_FlotteBaseViewSet):
    """Relevés télématiques des actifs de flotte (FLOTTE27 — point d'intégration).

    CRUD scopé société (écriture responsable/admin) du MAGASIN de relevés GPS /
    télématiques : odomètre, position, niveau de carburant, heures moteur,
    source et charge brute du fournisseur. L'ingestion MANUELLE (POST direct,
    ``source='manuel'``) fonctionne toujours. Filtrable par ``?actif_flotte=<id>``
    et ``?source=<manuel|telematique>``. L'actif lié doit appartenir à la société
    (validé au sérialiseur).

    Action ``POST /releves-telematiques/synchroniser/`` (écriture
    responsable/admin) : déclenche la synchronisation depuis le fournisseur
    externe. KEY-GATED / NO-OP — tant qu'aucun fournisseur n'est configuré
    (``settings.TELEMATIQUE_ENABLED`` faux par défaut), elle ne fait RIEN (aucun
    appel réseau, aucun coût) et renvoie ``{'active': false, 'importes': 0}``.
    """
    queryset = ReleveTelematique.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    serializer_class = ReleveTelematiqueSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['horodatage', 'odometre', 'source', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        source = params.get('source')
        if source:
            qs = qs.filter(source=source)

        return qs

    @action(detail=False, methods=['post'])
    def synchroniser(self, request):
        """FLOTTE27 — Synchronise les relevés depuis le fournisseur (no-op gated).

        Écriture (responsable/admin). Scopée société : la synchro pose toujours
        la société côté serveur. NO-OP tant qu'aucun fournisseur n'est configuré
        (``settings.TELEMATIQUE_ENABLED`` faux) — aucun appel réseau, aucun coût.
        ``?actif_flotte=<id>`` restreint la synchro à un actif. Renvoie
        ``{'active', 'importes'}``.
        """
        company = request.user.company

        actif_flotte_id = None
        actif_param = request.query_params.get('actif_flotte')
        if actif_param:
            try:
                actif_flotte_id = int(actif_param)
            except (ValueError, TypeError):
                actif_flotte_id = None

        from .services import synchroniser_releves, telematique_active
        importes = synchroniser_releves(
            company, actif_flotte=actif_flotte_id)
        return Response({
            'active': telematique_active(),
            'importes': importes,
        })


class InfractionViewSet(_FlotteBaseViewSet):
    """Infractions / PV de circulation des actifs de flotte (FLOTTE26).

    CRUD scopé société (écriture responsable/admin) d'un procès-verbal dressé
    contre un véhicule ou un engin du parc : date, type (excès de vitesse,
    stationnement, feu rouge, défaut de document, autre), lieu, référence du PV,
    montant de l'amende, PV scanné, conducteur responsable (FLOTTE7, même app),
    statut (à payer → payée / contestée / classée) et date de paiement.
    Filtrable par ``?statut=<a_payer|payee|contestee|classee>``,
    ``?actif_flotte=<id>`` et ``?type_infraction=<...>``. Recherche par
    référence du PV / lieu / notes. L'actif lié ET le conducteur lié doivent
    appartenir à la société (validé au sérialiseur).
    """
    queryset = Infraction.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'conducteur')
    serializer_class = InfractionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference_pv', 'lieu', 'notes']
    ordering_fields = ['date_infraction', 'type_infraction', 'statut',
                       'montant_amende', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        type_infraction = params.get('type_infraction')
        if type_infraction:
            qs = qs.filter(type_infraction=type_infraction)

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        return qs


# ── FLOTTE28 — Suivi de position & trajets télématiques ────────────────────────

class TrajetTelematiqueViewSet(_FlotteBaseViewSet):
    """Trajets télématiques des actifs de flotte (FLOTTE28).

    CRUD scopé société (écriture responsable/admin) des trajets (déplacement de A
    à B) d'un véhicule ou d'un engin : début/fin, positions de départ/arrivée,
    distance, durée et vitesse moyenne (calculées). La saisie manuelle fonctionne
    toujours. Filtrable par ``?actif_flotte=<id>``, ``?date_debut=YYYY-MM-DD`` et
    ``?date_fin=YYYY-MM-DD``. L'actif lié doit appartenir à la société.

    Action ``POST /trajets-telematiques/construire/`` (écriture
    responsable/admin) : reconstruit les trajets d'un actif à partir de ses
    relevés télématiques (FLOTTE27) successifs. Idempotente. ``?actif_flotte=<id>``
    est REQUIS. Renvoie ``{'crees': <int>}``.
    """
    queryset = TrajetTelematique.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'releve_depart', 'releve_arrivee')
    serializer_class = TrajetTelematiqueSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['debut', 'fin', 'distance_km', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        date_debut = params.get('date_debut')
        if date_debut:
            qs = qs.filter(debut__date__gte=date_debut)
        date_fin = params.get('date_fin')
        if date_fin:
            qs = qs.filter(debut__date__lte=date_fin)

        return qs

    @action(detail=False, methods=['post'])
    def construire(self, request):
        """FLOTTE28 — Construit les trajets d'un actif depuis ses relevés.

        Écriture (responsable/admin), scopée société. ``?actif_flotte=<id>`` est
        REQUIS (renvoie 400 sinon). Idempotente. Renvoie ``{'crees': <int>}``.
        """
        company = request.user.company
        actif_param = request.query_params.get('actif_flotte')
        if not actif_param:
            return Response(
                {'detail': "Le paramètre 'actif_flotte' est requis."},
                status=400)
        try:
            actif_id = int(actif_param)
        except (ValueError, TypeError):
            return Response(
                {'detail': "Le paramètre 'actif_flotte' est invalide."},
                status=400)

        if not ActifFlotte.objects.filter(
                company=company, id=actif_id).exists():
            return Response(
                {'detail': "Cet actif n'appartient pas à votre société."},
                status=404)

        from .services import construire_trajets_telematiques
        crees = construire_trajets_telematiques(company, actif_id)
        return Response({'crees': len(crees)})


# ── FLOTTE29 — Journal kilométrique & trajets imputés chantier ─────────────────

class TrajetChantierViewSet(_FlotteBaseViewSet):
    """Trajets imputés chantier des actifs de flotte (FLOTTE29).

    CRUD scopé société (écriture responsable/admin) du journal kilométrique
    imputé chantier : actif, chantier (``installation_id``, validé via
    ``installations.selectors``), date, motif, km départ/arrivée, distance.
    Filtrable par ``?actif_flotte=<id>``, ``?installation=<id>``,
    ``?date_debut=YYYY-MM-DD`` et ``?date_fin=YYYY-MM-DD``.

    Action ``GET /trajets-chantier/journal/`` (lecture tout rôle) : journal
    kilométrique AGRÉGÉ ventilé par chantier. Mêmes filtres facultatifs.
    """
    queryset = TrajetChantier.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    serializer_class = TrajetChantierSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['motif', 'notes']
    ordering_fields = ['date_trajet', 'distance_km', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        installation = params.get('installation')
        if installation:
            try:
                qs = qs.filter(installation_id=int(installation))
            except (ValueError, TypeError):
                pass

        date_debut = params.get('date_debut')
        if date_debut:
            qs = qs.filter(date_trajet__gte=date_debut)
        date_fin = params.get('date_fin')
        if date_fin:
            qs = qs.filter(date_trajet__lte=date_fin)

        return qs

    @action(detail=False, methods=['get'])
    def journal(self, request):
        """FLOTTE29 — Journal kilométrique agrégé, ventilé par chantier.

        Lecture (tout rôle), scopée société. Filtres facultatifs :
        ``?actif_flotte=<id>``, ``?installation=<id>``, ``?date_debut=`` /
        ``?date_fin=``. Renvoie distance totale + ventilation par chantier.
        """
        company = request.user.company
        params = request.query_params

        def _int(nom):
            valeur = params.get(nom)
            if not valeur:
                return None
            try:
                return int(valeur)
            except (ValueError, TypeError):
                return None

        from .selectors import journal_kilometrique
        data = journal_kilometrique(
            company,
            actif_flotte_id=_int('actif_flotte'),
            installation_id=_int('installation'),
            date_debut=params.get('date_debut') or None,
            date_fin=params.get('date_fin') or None,
        )
        return Response(data)


# ── FLOTTE32 — Pool de véhicules & demandes ────────────────────────────────────

class DemandeVehiculeViewSet(_FlotteBaseViewSet):
    """Demandes de véhicule du pool partagé (FLOTTE32).

    CRUD scopé société : un collaborateur DEMANDE un véhicule du pool pour une
    période. ``company`` ET ``demandeur`` sont posés côté serveur (jamais du
    body). Filtrable par ``?statut=<demandee|approuvee|refusee|annulee>`` et
    ``?demandeur=<id>``. Lecture tout rôle ; création tout rôle (chacun peut
    demander) ; décision responsable/admin via les actions dédiées.

    Actions ``POST /demandes-vehicule/<id>/approuver/`` et ``…/refuser/``
    (écriture responsable/admin) : approuvent (avec ``vehicule_attribue`` au
    body, optionnel) ou refusent une demande, en posant le décideur côté serveur.
    """
    queryset = DemandeVehicule.objects.select_related(
        'demandeur', 'vehicule_attribue', 'decide_par')
    serializer_class = DemandeVehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['besoin', 'notes']
    ordering_fields = ['date_debut_souhaitee', 'statut', 'date_creation']

    def get_permissions(self):
        # La création d'une demande est ouverte à tout rôle (chacun demande) ;
        # la décision (approuver/refuser) reste responsable/admin.
        if self.action == 'create':
            return [IsAnyRole()]
        return super().get_permissions()

    def perform_create(self, serializer):
        # company ET demandeur posés côté serveur (jamais du body).
        serializer.save(
            company=self.request.user.company,
            demandeur=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        demandeur = params.get('demandeur')
        if demandeur:
            try:
                qs = qs.filter(demandeur_id=int(demandeur))
            except (ValueError, TypeError):
                pass

        return qs

    @action(detail=True, methods=['post'])
    def approuver(self, request, pk=None):
        """FLOTTE32 — Approuve la demande (responsable/admin).

        ``vehicule_attribue`` (id, optionnel) et ``motif_decision`` (optionnel)
        au body. Le véhicule attribué doit appartenir à la société. Le décideur
        est l'utilisateur courant (posé côté serveur).
        """
        return self._decider(request, DemandeVehicule.Statut.APPROUVEE)

    @action(detail=True, methods=['post'])
    def refuser(self, request, pk=None):
        """FLOTTE32 — Refuse la demande (responsable/admin).

        ``motif_decision`` (optionnel) au body. Aucune attribution conservée. Le
        décideur est l'utilisateur courant (posé côté serveur).
        """
        return self._decider(request, DemandeVehicule.Statut.REFUSEE)

    def _decider(self, request, statut):
        company = request.user.company
        demande = self.get_object()

        vehicule = None
        veh_id = request.data.get('vehicule_attribue')
        if statut == DemandeVehicule.Statut.APPROUVEE and veh_id:
            vehicule = Vehicule.objects.filter(
                company=company, id=veh_id).first()
            if vehicule is None:
                return Response(
                    {'detail': "Ce véhicule n'appartient pas à votre société."},
                    status=400)

        from .services import decider_demande_vehicule
        try:
            decider_demande_vehicule(
                demande, statut=statut, decide_par=request.user,
                vehicule=vehicule,
                motif=request.data.get('motif_decision', ''))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response(self.get_serializer(demande).data)
