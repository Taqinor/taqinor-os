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
    BaremeVignette,
    CarteCarburant,
    Conducteur,
    EcheanceEntretien,
    EcheanceReglementaire,
    EnginRoulant,
    EtatDesLieux,
    Garage,
    OrdreReparation,
    PieceFlotte,
    PlanEntretien,
    Pneumatique,
    PleinCarburant,
    ReferentielFlotte,
    ReservationVehicule,
    Vehicule,
)
from .serializers import (
    ActifFlotteSerializer,
    AffectationConducteurSerializer,
    BaremeVignetteSerializer,
    CarteCarburantSerializer,
    ConducteurSerializer,
    EcheanceEntretienSerializer,
    EcheanceReglementaireSerializer,
    EnginRoulantSerializer,
    EtatDesLieuxSerializer,
    GarageSerializer,
    OrdreReparationSerializer,
    PieceFlotteSerializer,
    PlanEntretienSerializer,
    PneumatiqueSerializer,
    PleinCarburantSerializer,
    ReferentielFlotteSerializer,
    ReservationVehiculeSerializer,
    VehiculeSerializer,
)

READ_ACTIONS = ['list', 'retrieve', 'consommation', 'anomalies', 'echeances',
                'couts', 'synthese', 'expirantes', 'tsav']


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
