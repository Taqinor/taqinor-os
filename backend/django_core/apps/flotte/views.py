"""Vues du module Gestion de flotte (toutes scopées société).

La flotte est INTERNE. Chaque viewset filtre par ``request.user.company``
(``TenantMixin``) et pose la société côté serveur ; aucune société n'est jamais
acceptée du corps de requête (multi-tenant).
"""
import datetime

from rest_framework import filters, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
# ARC8 — chatter générique (records.Activity). records est une app de
# FONDATION : l'import direct de son mixin de vue est autorisé.
from apps.records.views import ChatterViewSetMixin

from .models import (
    AccuseCharte,
    ActifFlotte,
    AffectationConducteur,
    AssuranceVehicule,
    BaremeVignette,
    BudgetFlotte,
    CarteCarburant,
    CarteGriseVehicule,
    CharteVehicule,
    Conducteur,
    ContratVehicule,
    CoutVehicule,
    DemandeVehicule,
    EcheanceEntretien,
    EcheanceReglementaire,
    EnginRoulant,
    EtatDesLieux,
    Garage,
    GarantieFlotte,
    Infraction,
    InspectionVehicule,
    JournalStatutVehicule,
    ModeleInspection,
    ModeleVehicule,
    OrdreReparation,
    PieceFlotte,
    PlanEntretien,
    Pneumatique,
    PleinCarburant,
    RappelConstructeur,
    ReferentielFlotte,
    ReleveTelematique,
    RemiseAccessoire,
    ReservationVehicule,
    SignalementVehicule,
    Sinistre,
    TrajetChantier,
    TrajetTelematique,
    Vehicule,
    VisiteTechnique,
    ZoneGeographique,
)
from .serializers import (
    AccuseCharteSerializer,
    ActifFlotteSerializer,
    ActiviteFlotteSerializer,
    AffectationConducteurSerializer,
    AssuranceVehiculeSerializer,
    BaremeVignetteSerializer,
    BudgetFlotteSerializer,
    CarteCarburantSerializer,
    CarteGriseVehiculeSerializer,
    CharteVehiculeSerializer,
    ConducteurSerializer,
    ContratVehiculeSerializer,
    CoutVehiculeSerializer,
    EcheanceEntretienSerializer,
    EcheanceReglementaireSerializer,
    EnginRoulantSerializer,
    EtatDesLieuxSerializer,
    GarageSerializer,
    GarantieFlotteSerializer,
    InfractionSerializer,
    InspectionVehiculeSerializer,
    JournalStatutVehiculeSerializer,
    ModeleInspectionSerializer,
    ModeleVehiculeSerializer,
    OrdreReparationSerializer,
    PieceFlotteSerializer,
    PlanEntretienSerializer,
    PneumatiqueSerializer,
    PleinCarburantSerializer,
    DemandeVehiculeSerializer,
    RappelConstructeurSerializer,
    ReferentielFlotteSerializer,
    ReleveTelematiqueSerializer,
    RemiseAccessoireSerializer,
    ReservationVehiculeSerializer,
    SignalementVehiculeSerializer,
    SinistreSerializer,
    TrajetChantierSerializer,
    TrajetTelematiqueSerializer,
    VehiculeSerializer,
    VisiteTechniqueSerializer,
    ZoneGeographiqueSerializer,
)

READ_ACTIONS = ['list', 'retrieve', 'consommation', 'anomalies', 'echeances',
                'couts', 'synthese', 'expirantes', 'tsav', 'alertes_echeances',
                'tco', 'eco_conduite', 'documents', 'tableau_bord', 'journal',
                'amortissement', 'expirants', 'ledger', 'historique',
                'synthese_tva', 'detenteurs_courants', 'taux_completion',
                'activites', 'ocr', 'divergences_permis',
                # ARC8 — lecture du chatter générique (records.Activity).
                'chatter_historique']


def _parse_date_param(value):
    """XFLT8 — Parse une date 'YYYY-MM-DD' de query param (``None`` si
    absente/invalide)."""
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


class _FlotteBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée (TenantMixin). Lecture tout rôle, écriture
    responsable/admin."""

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class VehiculeViewSet(ChatterViewSetMixin, _FlotteBaseViewSet):
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

    def perform_create(self, serializer):
        # XFLT12/ZCTR11 — À la sélection d'un ``modele_ref``, pré-remplit les
        # champs vides (energie/puissance_fiscale/valeur/valeur_residuelle/
        # pct_charges_non_deductibles) SANS écraser une saisie déjà présente
        # dans le body.
        from .services import prefill_depuis_modele

        modele = serializer.validated_data.get('modele_ref')
        prefill_depuis_modele(serializer.validated_data, modele)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        # XFLT21 — Journal d'audit : journalise chaque changement RÉEL des
        # champs suivis (statut, kilométrage, type fiscal, modèle de
        # référence). Le statut passé par ``changer-statut/`` a déjà son
        # propre journal dédié (``JournalStatutVehicule``, XFLT4) — un PATCH
        # direct ici (hors cette action) est ce que ``ActiviteFlotte`` capture.
        from .services import journaliser_diff_vehicule

        instance = serializer.instance
        avant = {
            'statut': instance.statut,
            'kilometrage': instance.kilometrage,
            'type_fiscal': instance.type_fiscal,
            'modele_ref_id': instance.modele_ref_id,
        }
        serializer.save(company=self.request.user.company)
        apres = {
            'company': self.request.user.company,
            'instance': serializer.instance,
            'statut': serializer.instance.statut,
            'kilometrage': serializer.instance.kilometrage,
            'type_fiscal': serializer.instance.type_fiscal,
            'modele_ref_id': serializer.instance.modele_ref_id,
        }
        journaliser_diff_vehicule(avant, apres, user=self.request.user)

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

        XFLT9 — Ajoute ``part_non_deductible`` : la part de l'amortissement
        NON déductible fiscalement quand un véhicule ``type_fiscal=tourisme``
        dépasse le plafond CGI de la société (voir
        ``selectors.part_non_deductible_amortissement``) — 0 pour un
        utilitaire ou un véhicule sous le plafond.
        """
        vehicule = self.get_object()
        from .selectors import (
            amortissement_vehicule,
            part_non_deductible_amortissement,
        )
        data = amortissement_vehicule(request.user.company, vehicule.id)
        plafond = part_non_deductible_amortissement(
            request.user.company, vehicule.id)
        data['part_non_deductible'] = plafond['part_non_deductible']
        data['plafond_ttc'] = plafond['plafond_ttc']
        data['assujetti_plafond_cgi'] = plafond['assujetti']
        return Response(data)

    @action(detail=True, methods=['get'])
    def ledger(self, request, pk=None):
        """XFLT3 — Grand livre unifié des coûts du véhicule (lecture seule).

        Fusionne carburant, réparations, assurances (franchise), TSAV,
        infractions et coûts divers (``CoutVehicule``) en une vue
        chronologique unique via ``selectors.ledger_vehicule``. Scopée
        société. Le TCO (FLOTTE31) reste disponible séparément.
        """
        vehicule = self.get_object()
        from .selectors import ledger_vehicule
        return Response(
            ledger_vehicule(request.user.company, vehicule.id))

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """XFLT4 — Change le statut du véhicule (écriture responsable/admin).

        ``statut`` (obligatoire) au body. Le passage ``commande`` → ``actif``
        est refusé (400, message FR) tant que la checklist de mise en
        service n'est pas complète. Chaque transition RÉELLE est journalisée
        (``JournalStatutVehicule``, utilisateur et horodatage posés côté
        serveur).
        """
        vehicule = self.get_object()
        nouveau_statut = request.data.get('statut')
        if not nouveau_statut:
            return Response(
                {'detail': "Le champ 'statut' est requis."}, status=400)

        from .services import changer_statut_vehicule
        try:
            vehicule = changer_statut_vehicule(
                vehicule, nouveau_statut, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response(self.get_serializer(vehicule).data)

    @action(detail=True, methods=['get'])
    def historique(self, request, pk=None):
        """XFLT4 — Journal des changements de statut du véhicule (lecture
        tout rôle), du plus récent au plus ancien."""
        vehicule = self.get_object()
        qs = JournalStatutVehicule.objects.filter(
            company=request.user.company, vehicule=vehicule
        ).select_related('user')
        serializer = JournalStatutVehiculeSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def activites(self, request, pk=None):
        """XFLT21 — Journal d'audit du véhicule (statut/affectation/etc.),
        lecture tout rôle, du plus récent au plus ancien. Distinct de
        ``historique/`` (XFLT4, dédié aux transitions de statut via l'action
        ``changer-statut/``) — ``ActiviteFlotte`` capture aussi les
        modifications directes et les changements d'affectation conducteur.
        """
        vehicule = self.get_object()
        from .models import ActiviteFlotte
        qs = ActiviteFlotte.objects.filter(
            company=request.user.company, vehicule=vehicule
        ).select_related('user')
        serializer = ActiviteFlotteSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def ceder(self, request, pk=None):
        """XFLT16 — Cède (vend) le véhicule (écriture responsable/admin).

        Exige le statut ``a_vendre`` (400 sinon). Body : ``date_cession``
        (obligatoire), ``prix_cession`` (obligatoire), ``acheteur``
        (facultatif). Calcule le gain/perte de cession — DÉLÉGUÉ à compta
        (``apps.compta.services``) si le véhicule est rattaché à une
        immobilisation, calcul local sinon — passe le statut à ``vendu`` et
        journalise. L'historique du véhicule reste consultable après vente.
        """
        vehicule = self.get_object()
        date_cession = request.data.get('date_cession')
        prix_cession = request.data.get('prix_cession')
        if not date_cession or prix_cession in (None, ''):
            return Response(
                {'detail': "Les champs 'date_cession' et 'prix_cession' "
                           "sont requis."}, status=400)

        from .services import ceder_vehicule
        try:
            resultat = ceder_vehicule(
                vehicule, date_cession=date_cession,
                prix_cession=prix_cession,
                acheteur=request.data.get('acheteur', ''),
                user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)

        data = self.get_serializer(resultat['vehicule']).data
        data['resultat_cession'] = resultat['resultat_cession']
        data['source_calcul'] = resultat['source']
        return Response(data)

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


class ModeleVehiculeViewSet(_FlotteBaseViewSet):
    """Catalogue de modèles véhicule de référence (XFLT12).

    CRUD scopé société (écriture responsable/admin). Recherche par marque /
    modèle. Sert au pré-remplissage à la création d'un ``Vehicule``
    (``modele_ref``) et au fallback CO₂ de l'éco-conduite (FLOTTE33).
    """
    queryset = ModeleVehicule.objects.all()
    serializer_class = ModeleVehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['marque', 'modele']
    ordering_fields = ['marque', 'modele', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        return qs


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

    @action(detail=False, methods=['get'], url_path='divergences-permis')
    def divergences_permis(self, request):
        """YHIRE11 — Rapport de réconciliation « divergences permis
        flotte↔RH » (lecture tout rôle), scopé société.

        Compare, pour chaque conducteur LIÉ à un dossier RH, la validité
        locale (champs ``Conducteur``) à la validité RH
        (``rh.selectors.peut_conduire``, source de vérité quand un lien
        existe). Voir ``selectors.divergences_permis_flotte_rh``.
        """
        from .selectors import divergences_permis_flotte_rh
        return Response(
            divergences_permis_flotte_rh(request.user.company))


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

    @action(detail=True, methods=['get'], url_path='detenteurs-courants')
    def detenteurs_courants(self, request, pk=None):
        """XFLT20 — Détenteur courant de chaque accessoire de l'actif
        (lecture tout rôle) — répond à « qui a les clés ? »."""
        actif = self.get_object()
        from .selectors import detenteurs_courants
        return Response(detenteurs_courants(request.user.company, actif.id))


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

    @action(detail=False, methods=['post'])
    def masse(self, request):
        """XFLT22 — Réaffectation conducteur en masse (écriture responsable/
        admin).

        Body : ``reaffectations`` (liste de ``{'vehicule_id',
        'conducteur_id'}``, obligatoire) et ``date_debut`` (obligatoire).
        Clôt les affectations courantes et ouvre les nouvelles ; le contrôle
        permis (FLOTTE9) par ligne est respecté — les échecs sont LISTÉS
        sans bloquer le lot. Renvoie ``{'reussies': [...], 'echecs': [...]}``.
        """
        reaffectations = request.data.get('reaffectations') or []
        date_debut = request.data.get('date_debut')
        if not isinstance(reaffectations, list) or not reaffectations \
                or not date_debut:
            return Response(
                {'detail': "Les champs 'reaffectations' (liste) et "
                           "'date_debut' sont requis."}, status=400)

        from datetime import date as _date

        try:
            date_debut_parsed = _date.fromisoformat(str(date_debut))
        except ValueError:
            return Response(
                {'detail': "Format de 'date_debut' invalide (YYYY-MM-DD)."},
                status=400)

        from .services import reaffecter_conducteurs_masse
        resultat = reaffecter_conducteurs_masse(
            request.user.company, reaffectations,
            date_debut=date_debut_parsed, user=request.user)
        return Response({
            'reussies': AffectationConducteurSerializer(
                resultat['reussies'], many=True).data,
            'echecs': resultat['echecs'],
        })


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

    @action(detail=True, methods=['post'])
    def signer(self, request, pk=None):
        """XFLT17 — Appose une e-signature sur l'état des lieux (écriture
        responsable/admin ou le conducteur lui-même).

        Body : ``role`` (``'conducteur'`` ou ``'responsable'``, obligatoire),
        ``nom`` (obligatoire — nom saisi, e-signature loi 53-05). Horodatage
        posé côté serveur. 400 si déjà signé pour ce rôle ou rôle invalide.
        """
        etat = self.get_object()
        role = request.data.get('role')
        nom = request.data.get('nom')
        if not role or not nom:
            return Response(
                {'detail': "Les champs 'role' et 'nom' sont requis."},
                status=400)

        from .services import signer_etat_des_lieux
        try:
            etat = signer_etat_des_lieux(etat, role=role, nom=nom)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response(self.get_serializer(etat).data)


class CharteVehiculeViewSet(_FlotteBaseViewSet):
    """Charte véhicule versionnée de la société (XFLT17).

    Lecture tout rôle, écriture (publication d'une nouvelle version)
    responsable/admin. ``version`` est posée côté serveur (auto-incrémentée
    par société) — jamais du body.
    """
    queryset = CharteVehicule.objects.all()
    serializer_class = CharteVehiculeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['version', 'date_publication']

    def perform_create(self, serializer):
        derniere = CharteVehicule.objects.filter(
            company=self.request.user.company).order_by('-version').first()
        prochaine_version = (derniere.version + 1) if derniere else 1
        serializer.save(
            company=self.request.user.company, version=prochaine_version)


class AccuseCharteViewSet(_FlotteBaseViewSet):
    """Accusés de lecture de la charte véhicule par les conducteurs (XFLT17).

    Tout rôle peut créer un accusé (le conducteur accuse lui-même) —
    ``company`` posée côté serveur, ``version`` toujours la version courante
    au moment de l'accusé (jamais du body). Filtrable par ``?conducteur=``.
    """
    queryset = AccuseCharte.objects.select_related('conducteur')
    serializer_class = AccuseCharteSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_accuse']

    def get_permissions(self):
        if self.action == 'create':
            return [IsAnyRole()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        conducteur = self.request.query_params.get('conducteur')
        if conducteur:
            try:
                qs = qs.filter(conducteur_id=int(conducteur))
            except (ValueError, TypeError):
                pass
        return qs

    def perform_create(self, serializer):
        from .services import charte_courante

        company = self.request.user.company
        charte = charte_courante(company)
        if charte is None:
            raise DRFValidationError(
                {'detail': "Aucune charte véhicule publiée pour cette "
                           "société."})
        serializer.save(company=company, version=charte.version)


class BudgetFlotteViewSet(_FlotteBaseViewSet):
    """Budget flotte annuel par catégorie (XFLT18).

    CRUD scopé société (écriture responsable/admin). Filtrable par
    ``?annee=``. ``notifie_depassement`` est géré côté serveur.
    """
    queryset = BudgetFlotte.objects.all()
    serializer_class = BudgetFlotteSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['annee', 'categorie']

    def get_queryset(self):
        qs = super().get_queryset()
        annee = self.request.query_params.get('annee')
        if annee:
            try:
                qs = qs.filter(annee=int(annee))
            except (ValueError, TypeError):
                pass
        return qs


class RemiseAccessoireViewSet(_FlotteBaseViewSet):
    """Registre de remise clés / carte / badge / tag Jawaz (XFLT20).

    CRUD scopé société (écriture responsable/admin). Filtrable par
    ``?actif_flotte=<id>`` et ``?conducteur=<id>``.
    """
    queryset = RemiseAccessoire.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'conducteur')
    serializer_class = RemiseAccessoireSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_remise', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        conducteur = params.get('conducteur')
        if conducteur:
            try:
                qs = qs.filter(conducteur_id=int(conducteur))
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

    @action(detail=False, methods=['get'], url_path='synthese-tva')
    def synthese_tva(self, request):
        """XFLT8 — Synthèse mensuelle TVA carburant récupérable / non
        déductible (lecture tout rôle).

        ``?debut=YYYY-MM-DD&fin=YYYY-MM-DD`` (facultatifs) bornent la
        période. Alimente la déclaration TVA (voir
        ``selectors.synthese_tva_carburant``) — lecture seule.
        """
        company = request.user.company
        debut = _parse_date_param(request.query_params.get('debut'))
        fin = _parse_date_param(request.query_params.get('fin'))

        from .selectors import synthese_tva_carburant
        return Response(
            synthese_tva_carburant(company, periode=(debut, fin)))

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

    @action(detail=False, methods=['post'])
    def ocr(self, request):
        """XFLT23 — OCR d'un reçu de station → champs pré-remplis (gated).

        Accepte une photo (``request.FILES['photo']``, multipart) du reçu de
        station et renvoie les champs extraits (``date_plein``, ``quantite``,
        ``prix_total``, ``station``…) pour pré-remplir le formulaire côté
        frontend — l'utilisateur valide TOUJOURS avant création (jamais de
        création automatique de ``PleinCarburant`` ici).

        KEY-GATED : sans configuration OCR (``settings.
        FLOTTE_OCR_PLEINS_ENABLED`` / ``ZHIPU_API_KEY``), renvoie 503 avec un
        message FR clair — aucun no-op cassant, l'écran de saisie manuelle
        reste utilisable normalement.
        """
        from .services import extraire_recu_carburant, mapper_recu_vers_plein

        photo = request.FILES.get('photo')
        if photo is None:
            return Response(
                {'photo': "Le fichier 'photo' est obligatoire."}, status=400)

        try:
            champs_bruts = extraire_recu_carburant(
                photo.read(), mime=getattr(photo, 'content_type', '') or '')
        except RuntimeError as exc:
            return Response({'detail': str(exc)}, status=503)

        return Response({'champs': mapper_recu_vers_plein(champs_bruts)})


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

    @action(detail=True, methods=['post'], url_path='importer-releve')
    def importer_releve(self, request, pk=None):
        """XFLT6 — Importe un relevé CSV (carte carburant / Jawaz) et
        rapproche les lignes (écriture responsable/admin).

        Fichier CSV attendu au champ ``fichier`` (colonnes : date, montant,
        litres, station/gare). Une ligne AVEC litres crée un
        ``PleinCarburant`` ; une ligne SANS litres (péage) crée un
        ``CoutVehicule`` catégorie péage (tag Jawaz). Import fichier
        uniquement — aucun appel réseau. Rapproche les doublons (même
        véhicule/date/montant) et signale les lignes non rapprochées (carte
        sans véhicule attribué).
        """
        carte = self.get_object()
        fichier = request.FILES.get('fichier')
        if fichier is None:
            return Response(
                {'detail': "Le champ 'fichier' (CSV) est requis."},
                status=400)

        try:
            contenu = fichier.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response(
                {'detail': "Fichier CSV illisible (encodage invalide)."},
                status=400)

        from .services import importer_releve_carte
        rapport = importer_releve_carte(carte, contenu)
        return Response(rapport)


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

    @action(detail=True, methods=['post'])
    def rollout(self, request, pk=None):
        """XFLT22 — Duplique ce plan sur une sélection d'actifs (écriture
        responsable/admin).

        Body : ``actif_flotte_ids`` (liste d'id, obligatoire). Un actif déjà
        couvert par un plan du même type d'entretien est SAUTÉ (jamais de
        doublon). Renvoie ``{'crees': [...], 'ignores': [...]}``.
        """
        plan = self.get_object()
        actif_ids = request.data.get('actif_flotte_ids') or []
        if not isinstance(actif_ids, list) or not actif_ids:
            return Response(
                {'detail': "Le champ 'actif_flotte_ids' (liste) est requis."},
                status=400)

        from .services import rollout_plan_entretien
        resultat = rollout_plan_entretien(
            request.user.company, plan, actif_ids)
        return Response({
            'crees': PlanEntretienSerializer(
                resultat['crees'], many=True).data,
            'ignores': resultat['ignores'],
        })


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


class GarantieFlotteViewSet(_FlotteBaseViewSet):
    """Garanties véhicule & pièces (XFLT14).

    CRUD scopé société (écriture responsable/admin). Filtrable par
    ``?actif_flotte=<id>``.
    """
    queryset = GarantieFlotte.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin')
    serializer_class = GarantieFlotteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['composant', 'fournisseur']
    ordering_fields = ['date_debut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        actif_flotte = self.request.query_params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass
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
        'garage', 'echeance', 'type_service')
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

        type_service = params.get('type_service')
        if type_service:
            try:
                qs = qs.filter(type_service_id=int(type_service))
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

    def perform_create(self, serializer):
        # XFLT14 — Pose ``sous_garantie`` automatiquement si l'actif a une
        # garantie active couvrant la date d'ouverture (warning non bloquant,
        # jamais recalculé après coup — juste un flag de suivi).
        from .services import garantie_active_pour

        actif = serializer.validated_data.get('actif_flotte')
        date_ouverture = serializer.validated_data.get('date_ouverture')
        sous_garantie = bool(
            actif is not None
            and garantie_active_pour(actif, today=date_ouverture))
        serializer.save(
            company=self.request.user.company, sous_garantie=sous_garantie)

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
        l'échéance d'entretien liée intacte. XFLT19 — si ``montant_devis``
        est renseigné, calcule et journalise l'écart facture/devis (%) ; un
        écart > seuil société (défaut 10 %) est signalé (warning non
        bloquant, ``ecart_alerte`` dans la réponse). Renvoie l'OR clôturé
        sérialisé.
        """
        ordre = self.get_object()

        param = request.query_params.get('cloturer_echeance')
        cloturer_echeance = not (
            param is not None
            and param.lower() in ('0', 'false', 'faux', 'non'))

        from .services import cloturer_ordre_reparation, ecart_facture_devis_alerte
        cloturer_ordre_reparation(
            ordre, cloturer_echeance=cloturer_echeance)
        data = self.get_serializer(ordre).data
        data['ecart_alerte'] = ecart_facture_devis_alerte(ordre)
        return Response(data)

    @action(detail=True, methods=['post'])
    def approuver(self, request, pk=None):
        """XFLT19 — Approuve le devis de réparation (écriture responsable/
        admin — mécanique rôles réutilisée de ``DemandeVehicule``).

        Exige le statut ``devis_recu`` (400 sinon). Pose ``approuve_par``/
        ``date_approbation`` côté serveur.
        """
        ordre = self.get_object()
        from .services import approuver_ordre_reparation
        try:
            ordre = approuver_ordre_reparation(ordre, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(self.get_serializer(ordre).data)


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

    def perform_create(self, serializer):
        # XFLT25 — un code défaut moteur (DTC) critique déclenche une alerte
        # + un signalement (idempotent). Best-effort : ne bloque jamais la
        # création du relevé si le traitement échoue.
        from .services import traiter_codes_defaut
        serializer.save(company=self.request.user.company)
        if serializer.instance.codes_defaut:
            try:
                traiter_codes_defaut(serializer.instance)
            except Exception:
                pass

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


class ZoneGeographiqueViewSet(_FlotteBaseViewSet):
    """Zones géographiques de géofencing (XFLT24).

    CRUD scopé société (écriture responsable/admin) des cercles de
    géofencing (dépôt/chantier/zone interdite + plage horaire autorisée
    optionnelle). Filtrable par ``?type_zone=<depot|chantier|interdite>`` et
    ``?actif=true|false``.

    Action ``POST /zones-geographiques/evaluer/`` (écriture responsable/
    admin) : évalue les relevés télématiques déjà ingérés contre les zones
    actives de la société (purement local, ``services.evaluer_geofencing``)
    et diffuse une alerte best-effort par détection. Renvoie la liste des
    alertes détectées.
    """
    queryset = ZoneGeographique.objects.all()
    serializer_class = ZoneGeographiqueSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['nom', 'type_zone', 'actif', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        type_zone = params.get('type_zone')
        if type_zone:
            qs = qs.filter(type_zone=type_zone)

        actif = params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'yes'))

        return qs

    @action(detail=False, methods=['post'])
    def evaluer(self, request):
        """XFLT24 — Évalue le géofencing sur les relevés télématiques
        existants (purement local, écriture responsable/admin — déclenche
        des notifications best-effort)."""
        from .services import evaluer_geofencing
        alertes = evaluer_geofencing(request.user.company)
        return Response({'nb_alertes': len(alertes), 'alertes': alertes})


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

        # XFLT11 — infractions refacturables au conducteur (lecture seule ;
        # l'écriture de la retenue de paie reste manuelle côté paie).
        if params.get('refacturables') == '1':
            qs = qs.filter(refacture_conducteur=True)

        return qs

    def _imputer_conducteur_auto(self, serializer):
        """XFLT11 — Si aucun conducteur n'est fourni, résout automatiquement
        le conducteur affecté au véhicule à la date de l'infraction via
        l'historique ``AffectationConducteur``. Ne s'applique qu'aux
        infractions rattachées à un ``Vehicule`` (pas un engin) ; une
        résolution manquante laisse ``conducteur=None`` et
        ``imputation_auto=False`` (le front peut afficher un avertissement)."""
        from .services import conducteur_a_la_date

        save_kwargs = {}
        if serializer.instance is None:
            # Create path only — company is immutable on update.
            save_kwargs['company'] = self.request.user.company

        conducteur_fourni = serializer.validated_data.get('conducteur')
        if conducteur_fourni is not None:
            serializer.save(imputation_auto=False, **save_kwargs)
            return

        actif = serializer.validated_data.get('actif_flotte')
        date_infraction = serializer.validated_data.get('date_infraction')
        vehicule = getattr(actif, 'vehicule', None) if actif else None
        conducteur_resolu = conducteur_a_la_date(vehicule, date_infraction)
        if conducteur_resolu is not None:
            serializer.save(
                conducteur=conducteur_resolu, imputation_auto=True,
                **save_kwargs)
        else:
            serializer.save(imputation_auto=False, **save_kwargs)

    def perform_create(self, serializer):
        self._imputer_conducteur_auto(serializer)

    def perform_update(self, serializer):
        self._imputer_conducteur_auto(serializer)


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


class ContratVehiculeViewSet(_FlotteBaseViewSet):
    """Contrats véhicule (leasing/LLD/location/entretien) (XFLT1).

    CRUD scopé société (écriture responsable/admin) : type de contrat,
    fournisseur/bailleur, dates début/fin, montant récurrent + périodicité,
    services inclus, km contractuel/an. Distinct de ``AssuranceVehicule``
    (FLOTTE21) — jamais de doublon. Filtrable par
    ``?statut=<actif|expire>`` et ``?vehicule=<id>``. Recherche par
    fournisseur/notes. ``statut_calcule`` (état réel vs la date du jour) est
    exposé en lecture. Le véhicule et le garage liés doivent appartenir à la
    société (validé au sérialiseur).

    Action ``GET /contrats-vehicule/expirants/?within=N`` (lecture tout
    rôle) — contrats déjà expirés ou dus dans les ``N`` prochains jours
    (défaut 30), de la plus urgente à la moins urgente. Ces mêmes contrats
    remontent aussi dans ``alertes-echeances`` (FLOTTE24, source
    ``contrat_vehicule``).
    """
    queryset = ContratVehicule.objects.select_related('vehicule', 'garage')
    serializer_class = ContratVehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['fournisseur', 'notes']
    ordering_fields = ['date_debut', 'date_fin', 'montant_recurrent',
                       'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        vehicule = params.get('vehicule')
        if vehicule:
            try:
                qs = qs.filter(vehicule_id=int(vehicule))
            except (ValueError, TypeError):
                pass

        return qs

    @action(detail=False, methods=['get'])
    def expirants(self, request):
        """XFLT1 — Contrats expirés ou dus sous ``?within=N`` jours.

        Lecture (tout rôle), scopée société. ``within`` défaut = 30 jours ;
        une valeur invalide retombe sur 30. Renvoie la liste sérialisée, de
        la plus urgente (déjà expirée) à la moins urgente.
        """
        company = request.user.company

        within_param = request.query_params.get('within')
        within = 30
        if within_param:
            try:
                within = int(within_param)
            except (ValueError, TypeError):
                within = 30

        from .selectors import contrats_vehicule_expirants
        qs = contrats_vehicule_expirants(company, within=within)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class CoutVehiculeViewSet(_FlotteBaseViewSet):
    """Coûts véhicule divers (péage, parking, lavage, contrat, autre…)
    (XFLT3).

    CRUD scopé société (écriture responsable/admin) : catégorie, date,
    montant, fournisseur, référence pièce, conducteur optionnel. Complète —
    sans les dupliquer — les sources déjà saisies ailleurs (carburant,
    réparation, assurance, infraction). Filtrable par
    ``?actif_flotte=<id>`` et ``?categorie=<...>``. Recherche par
    fournisseur / référence pièce / notes.
    """
    queryset = CoutVehicule.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'conducteur')
    serializer_class = CoutVehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['fournisseur', 'reference_piece', 'notes']
    ordering_fields = ['date', 'montant', 'categorie', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        categorie = params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)

        return qs

    @action(detail=False, methods=['post'])
    def ventiler(self, request):
        """XFLT30 — Ventile une facture fournisseur sur plusieurs véhicules
        (écriture responsable/admin).

        Corps attendu ::

            {
              "montant_total": "12000.00",
              "actif_flotte_ids": [1, 2, 3],
              "date": "2026-06-01",
              "categorie": "entretien",        # optionnel (défaut 'autre')
              "fournisseur": "Total Maroc",     # optionnel
              "fournisseur_id_ref": 5,          # optionnel (stock.Fournisseur)
              "reference_piece": "FAC-2026-042",
              "repartitions": {"1": "5000", "2": "4000", "3": "3000"},
              # optionnel — sinon répartition ÉGALE (arrondi centime,
              # reliquat sur la dernière ligne).
              "notes": "…",                     # optionnel
            }

        Crée N ``CoutVehicule`` (un par actif) portant TOUS la même
        ``reference_piece`` — jamais d'écriture comptable directe (compta lit
        le ledger via sélecteur). Renvoie les coûts créés (sérialisés).
        """
        data = request.data
        actif_flotte_ids = data.get('actif_flotte_ids') or []
        try:
            actif_flotte_ids = [int(a) for a in actif_flotte_ids]
        except (ValueError, TypeError):
            return Response(
                {'actif_flotte_ids': 'Liste d\'identifiants entiers attendue.'},
                status=400)
        if not actif_flotte_ids:
            return Response(
                {'actif_flotte_ids': 'Au moins un actif est requis.'},
                status=400)

        montant_total = data.get('montant_total')
        date_ventilation = _parse_date_param(data.get('date'))
        if montant_total is None or date_ventilation is None:
            return Response(
                {'detail': "'montant_total' et 'date' (YYYY-MM-DD) sont "
                           "obligatoires."},
                status=400)

        repartitions_brutes = data.get('repartitions')
        repartitions = None
        if repartitions_brutes:
            try:
                repartitions = {
                    int(k): v for k, v in repartitions_brutes.items()}
            except (ValueError, TypeError, AttributeError):
                return Response(
                    {'repartitions': 'Répartition invalide (attendu '
                                     '{actif_flotte_id: montant}).'},
                    status=400)

        from .services import ventiler_cout_fournisseur
        try:
            crees = ventiler_cout_fournisseur(
                request.user.company,
                montant_total=montant_total,
                actif_flotte_ids=actif_flotte_ids,
                date=date_ventilation,
                categorie=data.get('categorie'),
                fournisseur=data.get('fournisseur', ''),
                fournisseur_id_ref=data.get('fournisseur_id_ref'),
                reference_piece=data.get('reference_piece', ''),
                repartitions=repartitions,
                notes=data.get('notes', ''),
            )
        except (ValueError, TypeError) as exc:
            return Response({'detail': str(exc)}, status=400)

        serializer = self.get_serializer(crees, many=True)
        return Response(serializer.data, status=201)


class SignalementVehiculeViewSet(_FlotteBaseViewSet):
    """Signalements d'anomalie véhicule déposés par un conducteur (XFLT5).

    CRUD scopé société : tout rôle peut CRÉER un signalement (comme
    ``DemandeVehicule``, FLOTTE32) — ``company`` ET ``auteur`` posés côté
    serveur. La résolution (mise à jour du ``statut``) reste réservée aux
    rôles écriture. Filtrable par ``?statut=`` et ``?actif_flotte=``.

    Action ``POST /signalements/<id>/convertir-en-or/`` (écriture
    responsable/admin) : crée un ``OrdreReparation`` (FLOTTE17) pré-rempli
    depuis le signalement (actif, description) et lie les deux.
    """
    queryset = SignalementVehicule.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'conducteur', 'auteur', 'ordre_reparation')
    serializer_class = SignalementVehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description']
    ordering_fields = ['gravite', 'statut', 'date_creation']

    def get_permissions(self):
        # La création est ouverte à tout rôle (comme DemandeVehicule) ; la
        # résolution (update/convertir-en-or) reste responsable/admin.
        if self.action == 'create':
            return [IsAnyRole()]
        return super().get_permissions()

    def perform_create(self, serializer):
        # company ET auteur posés côté serveur (jamais du body).
        serializer.save(
            company=self.request.user.company, auteur=self.request.user)

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

    @action(detail=True, methods=['post'], url_path='convertir-en-or')
    def convertir_en_or(self, request, pk=None):
        """XFLT5 — Crée un ``OrdreReparation`` pré-rempli depuis le
        signalement et lie les deux (écriture responsable/admin)."""
        signalement = self.get_object()
        if signalement.ordre_reparation_id is not None:
            return Response(
                {'detail': "Ce signalement est déjà converti en ordre de "
                           "réparation."}, status=400)

        ordre = OrdreReparation.objects.create(
            company=request.user.company,
            actif_flotte=signalement.actif_flotte,
            description=signalement.description,
            date_ouverture=datetime.date.today(),
        )
        signalement.ordre_reparation = ordre
        signalement.save(update_fields=['ordre_reparation'])

        return Response(self.get_serializer(signalement).data)


class RappelConstructeurViewSet(_FlotteBaseViewSet):
    """Rappels constructeur (recall) de la société (XFLT28).

    CRUD scopé société (écriture responsable/admin) : référence de campagne,
    constructeur, description, liste de VIN concernés.

    Action ``POST /rappels-constructeur/<id>/rapprocher/`` (écriture
    responsable/admin) : rapproche le rappel contre le parc de VIN de la
    société (``services.rapprocher_rappel``) et crée un
    ``SignalementVehicule`` (XFLT5) par véhicule touché — idempotent (pas de
    doublon ouvert pour la même campagne). Renvoie le nombre de VIN matchés
    et les signalements créés.
    """
    queryset = RappelConstructeur.objects.all()
    serializer_class = RappelConstructeurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference_campagne', 'constructeur']
    ordering_fields = ['reference_campagne', 'date_creation']

    @action(detail=True, methods=['post'])
    def rapprocher(self, request, pk=None):
        """XFLT28 — Rapproche le rappel contre le parc de VIN (écriture
        responsable/admin, idempotent)."""
        rappel = self.get_object()
        from .services import rapprocher_rappel
        resultat = rapprocher_rappel(rappel)
        return Response({
            'nb_vin_matches': resultat['nb_vin_matches'],
            'signalements_crees': [s.id for s in resultat['crees']],
        })


# ── XFLT13 — Inspections périodiques paramétrables (check-lists DVIR) ──────────

class ModeleInspectionViewSet(_FlotteBaseViewSet):
    """Modèles de check-list d'inspection périodique (XFLT13).

    CRUD scopé société (écriture responsable/admin). Filtrable par
    ``?actif=true|false`` et ``?type_actif_cible=``.
    """
    queryset = ModeleInspection.objects.all()
    serializer_class = ModeleInspectionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        actif = params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true'))
        type_actif_cible = params.get('type_actif_cible')
        if type_actif_cible:
            qs = qs.filter(type_actif_cible=type_actif_cible)
        return qs


class InspectionVehiculeViewSet(_FlotteBaseViewSet):
    """Inspections périodiques réalisées sur les actifs (XFLT13).

    CRUD scopé société : tout rôle peut CRÉER une inspection (le conducteur
    réalise l'inspection lui-même) — ``company`` ET ``auteur`` posés côté
    serveur. Tout item ``resultat='fail'`` crée automatiquement un
    ``SignalementVehicule`` (XFLT5) lié. Filtrable par ``?actif_flotte=`` et
    ``?conducteur=``.

    Action ``GET /inspections/taux-completion/`` (lecture tout rôle) :
    taux de complétion des items par conducteur (``services.
    taux_completion_inspections_par_conducteur``).
    """
    queryset = InspectionVehicule.objects.select_related(
        'actif_flotte', 'actif_flotte__vehicule', 'actif_flotte__engin',
        'modele_inspection', 'conducteur', 'auteur')
    serializer_class = InspectionVehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['signature_nom']
    ordering_fields = ['date_inspection']

    def get_permissions(self):
        if self.action == 'create':
            return [IsAnyRole()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        actif_flotte = params.get('actif_flotte')
        if actif_flotte:
            try:
                qs = qs.filter(actif_flotte_id=int(actif_flotte))
            except (ValueError, TypeError):
                pass

        conducteur = params.get('conducteur')
        if conducteur:
            try:
                qs = qs.filter(conducteur_id=int(conducteur))
            except (ValueError, TypeError):
                pass

        return qs

    def perform_create(self, serializer):
        from .services import traiter_items_fail

        inspection = serializer.save(
            company=self.request.user.company, auteur=self.request.user)
        traiter_items_fail(inspection)

    @action(detail=False, methods=['get'], url_path='taux-completion')
    def taux_completion(self, request):
        from .services import taux_completion_inspections_par_conducteur
        return Response(
            taux_completion_inspections_par_conducteur(request.user.company))


# ── XFLT7 — Rapport d'analyse des coûts (pivot + benchmark) ────────────────────

GROUP_BY_VALIDES = (
    'vehicule', 'categorie', 'mois', 'conducteur', 'garage', 'type_service')


@api_view(['GET'])
@permission_classes([IsAnyRole])
def rapport_couts(request):
    """XFLT7 — Rapport d'analyse des coûts (pivot + benchmark), lecture seule.

    ``GET /flotte/rapports/couts/?group_by=vehicule|categorie|mois|conducteur|garage|type_service``
    (défaut ``vehicule`` ; une valeur inconnue retombe sur ``vehicule``).
    Construit sur le ledger unifié (XFLT3, ``selectors.analyse_couts_report``) :
    matrice coûts, coût/km par véhicule, dépense par garage, outliers de
    consommation. ``?export=xlsx`` télécharge le pivot (JAMAIS ``?format=``,
    réservé par DRF).
    """
    company = request.user.company
    group_by = request.query_params.get('group_by', 'vehicule')
    if group_by not in GROUP_BY_VALIDES:
        group_by = 'vehicule'

    from .selectors import analyse_couts_report
    rapport = analyse_couts_report(company, group_by=group_by)

    if request.query_params.get('export') == 'xlsx':
        from apps.records.xlsx import build_xlsx_response
        headers = ['Clé', 'Libellé', 'Total (MAD)']
        rows = [
            [ligne['cle'], ligne['libelle'], ligne['total']]
            for ligne in rapport['pivot']
        ]
        return build_xlsx_response(
            'flotte-analyse-couts.xlsx', headers, rows,
            sheet_title='Analyse coûts')

    return Response(rapport)


# ── XFLT15 — Analyse de remplacement (fin de vie économique) ───────────────────

@api_view(['GET'])
@permission_classes([IsAnyRole])
def rapport_remplacement(request):
    """XFLT15 — Analyse de remplacement (fin de vie économique), lecture seule.

    ``GET /flotte/rapports/remplacement/`` : pour chaque véhicule actif,
    évalue 3 règles paramétrables par société (âge, kilométrage, ratio
    coût-réparations-12-mois / valeur vénale — style 50/30/20) via
    ``selectors.analyse_remplacement``. Un véhicule dépassant ≥ 2 règles est
    flaggé « à remplacer » avec le plan annuel (liste triée + budget estimé).
    """
    from .selectors import analyse_remplacement
    return Response(analyse_remplacement(request.user.company))


# ── XFLT18 — Budget flotte annuel vs réalisé ────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAnyRole])
def rapport_budget(request):
    """XFLT18 — Variance budget vs réalisé par catégorie, lecture seule.

    ``GET /flotte/rapports/budget/?annee=N`` (défaut : année courante).
    Réalisé = agrégat du ledger unifié (XFLT3) reclassé sur les 6 clés
    budgétaires, via ``selectors.variance_budget_flotte``. Un dépassement
    ``niveau='rouge'`` (> 100 %) déclenche une notification best-effort et
    IDEMPOTENTE aux responsables/admins de la société
    (``services.verifier_depassements_budget`` — jamais renvoyée en double).
    """
    annee_param = request.query_params.get('annee')
    try:
        annee = int(annee_param) if annee_param else datetime.date.today().year
    except (ValueError, TypeError):
        annee = datetime.date.today().year

    from .services import verifier_depassements_budget

    verifier_depassements_budget(request.user.company, annee)

    from .selectors import variance_budget_flotte
    return Response(variance_budget_flotte(request.user.company, annee))
