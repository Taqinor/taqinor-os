"""Vues de l'app `mrp` (Groupe NTMFG — Production / MRP II)."""
from datetime import datetime, timedelta

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from core.permissions import ScopedPermission
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    CoutStandard, Gamme, OperationGamme, OperationOF, OrdreFabrication,
    OrdreModification, PosteDeCharge, ReglesKanbanProduction,
)
from .serializers import (
    CoutStandardSerializer, GammeSerializer, OperationGammeSerializer,
    OperationOFSerializer, OrdreFabricationSerializer, OrdreModificationSerializer,
    PosteDeChargeSerializer, ReglesKanbanProductionSerializer,
)


def _parse_date_param(request, nom, defaut):
    """Lit `?<nom>=AAAA-MM-JJ` sur la requête, ou `defaut` si absent/invalide
    (NTMFG7/NTMFG12 — jamais d'exception 500 sur une date mal formée)."""
    brut = request.query_params.get(nom)
    if not brut:
        return defaut
    try:
        return datetime.strptime(brut, '%Y-%m-%d').date()
    except ValueError:
        return defaut


class PosteDeChargeViewSet(CompanyScopedModelViewSet):
    """NTMFG1 — CRUD des postes de charge (company-scopé)."""
    queryset = PosteDeCharge.objects.all()
    serializer_class = PosteDeChargeSerializer
    filterset_fields = ['type_poste', 'actif']

    # YRBAC4 — garde DÉCLARÉE. Consultation d'un indicateur (TRS/OEE) sur un
    # queryset company-scopé : ``ScopedPermission`` (GET → ``read_permission``
    # None) exprime le tier réel « authentifié INTERNE de la société », égal au
    # défaut de classe — un opérateur d'atelier doit voir le TRS de son poste
    # sans être responsable. Aucun ``get_permissions`` sur ce viewset ni ses
    # bases → la déclaration n'est pas neutralisée.
    @action(detail=True, methods=['get'], url_path='oee',
            permission_classes=[ScopedPermission])
    def oee(self, request, pk=None):
        """NTMFG12 — TRS/OEE du poste sur `?debut=&fin=` (AAAA-MM-JJ, défaut
        les 28 derniers jours) + tendance hebdomadaire."""
        from django.utils import timezone as dj_timezone

        from .selectors import oee_poste, oee_tendance_hebdomadaire

        poste = self.get_object()
        aujourd_hui = dj_timezone.localdate()
        debut = _parse_date_param(request, 'debut', aujourd_hui - timedelta(days=27))
        fin = _parse_date_param(request, 'fin', aujourd_hui)
        resultat = oee_poste(request.user.company, poste.id, debut, fin)
        if resultat is None:
            return Response({'detail': 'Poste introuvable.'}, status=404)
        resultat['tendance_hebdomadaire'] = oee_tendance_hebdomadaire(
            request.user.company, poste.id, debut, fin)
        return Response(resultat)


class GammeViewSet(CompanyScopedModelViewSet):
    """NTMFG2 — CRUD des gammes opératoires (company-scopé)."""
    queryset = Gamme.objects.select_related('produit').prefetch_related(
        'operations__poste_charge').all()
    serializer_class = GammeSerializer
    filterset_fields = ['produit', 'actif']


class OperationGammeViewSet(CompanyScopedModelViewSet):
    """NTMFG2 — opérations d'une gamme. Filtrable par `?gamme=`.

    Hérite de `CompanyScopedModelViewSet` (garde SCA4) : le scoping société et
    le forçage de `company` à l'écriture viennent de la plateforme, jamais d'un
    filtrage maison. `_check_parent` reste indispensable — il empêche de
    rattacher l'opération à une gamme ou un poste de charge d'une AUTRE
    société, ce que le scoping de la ligne elle-même ne couvre pas."""
    queryset = OperationGamme.objects.select_related(
        'gamme', 'poste_charge').all()
    serializer_class = OperationGammeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        gamme = self.request.query_params.get('gamme')
        if gamme:
            qs = qs.filter(gamme_id=gamme)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        gamme = serializer.validated_data.get('gamme')
        if gamme is not None and getattr(gamme, 'company_id', None) != cid:
            raise ValidationError({'gamme': 'Gamme inconnue pour cette société.'})
        poste = serializer.validated_data.get('poste_charge')
        if poste is not None and getattr(poste, 'company_id', None) != cid:
            raise ValidationError(
                {'poste_charge': 'Poste de charge inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._check_parent(serializer)
        super().perform_update(serializer)


class OrdreFabricationViewSet(CompanyScopedModelViewSet):
    """NTMFG3 — CRUD des Ordres de Fabrication (company-scopé). `confirmer/`
    instancie les opérations depuis la gamme et calcule les dates prévues
    (NTMFG3)."""
    queryset = OrdreFabrication.objects.select_related(
        'produit', 'gamme', 'kit_ordre_assemblage').prefetch_related(
        'operations__poste_charge').all()
    serializer_class = OrdreFabricationSerializer
    filterset_fields = ['statut', 'produit', 'gamme']

    def get_queryset(self):
        # NTMFG9 — filtre poste (les opérations portent le poste, pas l'OF
        # lui-même) : un OF matche s'il a AU MOINS une opération sur ce poste.
        qs = super().get_queryset()
        poste = self.request.query_params.get('poste')
        if poste:
            qs = qs.filter(operations__poste_charge_id=poste).distinct()
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        for champ in ('produit', 'gamme', 'kit_ordre_assemblage'):
            valeur = serializer.validated_data.get(champ)
            if valeur is not None and getattr(valeur, 'company_id', None) != cid:
                raise ValidationError(
                    {champ: 'Référence inconnue pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        # NTMFG16 — un OF déjà CLÔTURÉ (`termine`) ne peut plus basculer
        # prototype <-> normal : la seule voie est de créer un nouvel OF.
        instance = serializer.instance
        if ('est_prototype' in serializer.validated_data
                and instance.statut == OrdreFabrication.Statut.TERMINE
                and serializer.validated_data['est_prototype'] != instance.est_prototype):
            raise ValidationError({
                'est_prototype': "Impossible de changer le statut prototype d'un "
                                 'OF déjà clôturé — créez un nouvel OF.'})
        serializer.save(company=self.request.user.company)

    # YRBAC4 — gardes DÉCLARÉES, et un vrai RESSERREMENT sur les trois actions
    # d'écriture ci-dessous : ce viewset ne pose ni ``read_permission`` ni
    # ``write_permission``, donc le défaut ``ScopedPermission`` se réduisait à
    # « authentifié interne suffit » — n'importe quel compte, y compris en
    # lecture seule, pouvait confirmer, clôturer (backflush = mouvements de
    # stock RÉELS) ou annuler un ordre de fabrication. Ces transitions sont des
    # actes d'exploitation : elles exigent désormais un porteur de rôle, comme
    # ``CoutStandardViewSet`` dans ce même module. La lecture
    # (``dispo-composants``) reste au tier lecture. Aucun ``get_permissions``
    # sur ce viewset ni ses bases → gardes effectives.
    @action(detail=True, methods=['post'], url_path='confirmer',
            permission_classes=[IsResponsableOrAdmin])
    def confirmer(self, request, pk=None):
        """NTMFG3 — instancie les opérations depuis la gamme + planifie les
        dates (capacité poste), passe le statut en `planifie`."""
        from .services import confirmer_of
        of = self.get_object()
        confirmer_of(of, user=request.user)
        of.refresh_from_db()
        return Response(self.get_serializer(of).data)

    @action(detail=True, methods=['post'], url_path='cloturer',
            permission_classes=[IsResponsableOrAdmin])
    def cloturer(self, request, pk=None):
        """NTMFG4 — clôture l'OF : backflush (consommation composants +
        production composite) exactement une fois, sauf si un
        `kit_ordre_assemblage` porte déjà le mouvement (XMFG1)."""
        from .services import cloturer_of
        of = self.get_object()
        cloturer_of(of, user=request.user)
        of.refresh_from_db()
        return Response(self.get_serializer(of).data)

    @action(detail=True, methods=['post'], url_path='annuler',
            permission_classes=[IsResponsableOrAdmin])
    def annuler(self, request, pk=None):
        """NTMFG6 — annule l'OF : libère ses réservations de composants.
        Refuse (400) si le stock a déjà été mouvementé."""
        from .services import annuler_of
        of = self.get_object()
        try:
            annuler_of(of, user=request.user, motif=request.data.get('motif', ''))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        of.refresh_from_db()
        return Response(self.get_serializer(of).data)

    @action(detail=True, methods=['get'], url_path='dispo-composants',
            permission_classes=[ScopedPermission])
    def dispo_composants(self, request, pk=None):
        """NTMFG6 — disponibilité par ligne réservée (disponible/partiel/
        manquant)."""
        from .selectors import disponibilite_par_ligne_of
        of = self.get_object()
        return Response(disponibilite_par_ligne_of(of))


class OperationOFViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin,
                         viewsets.GenericViewSet):
    """NTMFG3/7/8 — opérations d'un OF. Pas de `company` propre : scope via
    l'OF parent. Filtrable par `?ordre_fabrication=`. Lecture seule + actions
    dédiées (`replanifier/` NTMFG7 ; démarrer/pauser/terminer NTMFG8) —
    jamais de PUT/PATCH/DELETE génériques."""
    queryset = OperationOF.objects.select_related(
        'ordre_fabrication', 'operation_gamme', 'poste_charge').all()
    serializer_class = OperationOFSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(ordre_fabrication__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        of = self.request.query_params.get('ordre_fabrication')
        if of:
            qs = qs.filter(ordre_fabrication_id=of)
        return qs

    # YRBAC4 — gardes DÉCLARÉES sur les 5 actions d'écriture de ce viewset.
    # RESSERREMENT réel : ``OperationOFViewSet`` est un ``GenericViewSet`` nu,
    # donc son défaut était le ``IsAuthenticated`` projet — tout compte
    # authentifié pouvait replanifier un Gantt ou pointer démarrage/pause/fin
    # d'opération (le « terminer » poste même un ``MouvementStock`` sur rebut).
    # Ces écritures exigent désormais un porteur de rôle, comme
    # ``CoutStandardViewSet`` juste en dessous. Ce viewset ne définit PAS de
    # ``get_permissions`` (contrairement à ``CoutStandardViewSet``) : les
    # déclarations ci-dessous sont donc bien celles que DRF applique.
    @action(detail=True, methods=['patch'], url_path='replanifier',
            permission_classes=[IsResponsableOrAdmin])
    def replanifier(self, request, pk=None):
        """NTMFG7 — déplace cette opération (glisser-déposer Gantt) : nouvelle
        `date_planifiee` et/ou `poste_charge` optionnel, contrôle de capacité
        NON bloquant (avertissement seulement)."""
        from .services import replanifier_operation
        operation = self.get_object()
        try:
            operation, avertissement = replanifier_operation(
                operation,
                nouvelle_date=request.data.get('date_planifiee'),
                nouveau_poste_id=request.data.get('poste_charge'),
                company=request.user.company)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        data = self.get_serializer(operation).data
        data['avertissement'] = avertissement
        return Response(data)

    @action(detail=True, methods=['post'], url_path='demarrer',
            permission_classes=[IsResponsableOrAdmin])
    def demarrer(self, request, pk=None):
        """NTMFG8 — terminal atelier : démarre l'opération. NTMFG14 —
        `avertissement_maintenance` (non bloquant) signale un poste dont une
        échéance d'entretien est en retard."""
        from .selectors import postes_en_alerte_maintenance
        from .services import demarrer_operation
        operation = self.get_object()
        try:
            demarrer_operation(operation, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        operation.refresh_from_db()
        data = self.get_serializer(operation).data
        alertes = postes_en_alerte_maintenance(request.user.company)
        data['avertissement_maintenance'] = operation.poste_charge_id in alertes
        return Response(data)

    @action(detail=True, methods=['post'], url_path='pauser',
            permission_classes=[IsResponsableOrAdmin])
    def pauser(self, request, pk=None):
        """NTMFG8 — terminal atelier : met l'opération en pause."""
        from .services import pauser_operation
        return self._mes_action(pauser_operation, request, pk)

    @action(detail=True, methods=['post'], url_path='reprendre',
            permission_classes=[IsResponsableOrAdmin])
    def reprendre(self, request, pk=None):
        """NTMFG8 — terminal atelier : reprend une opération en pause."""
        from .services import reprendre_operation
        return self._mes_action(reprendre_operation, request, pk)

    @action(detail=True, methods=['post'], url_path='terminer',
            permission_classes=[IsResponsableOrAdmin])
    def terminer(self, request, pk=None):
        """NTMFG8/10 — terminal atelier : termine l'opération (quantité
        bonne/rebut + motif si rebut, coût façon si sous-traitée), calcule le
        temps actif (pauses exclues), rebut > 0 poste un `MouvementStock`
        (XMFG11)."""
        from .services import terminer_operation
        operation = self.get_object()
        try:
            terminer_operation(
                operation,
                quantite_bonne=request.data.get('quantite_bonne', 0),
                quantite_rebut=request.data.get('quantite_rebut', 0),
                motif_rebut=request.data.get('motif_rebut', ''),
                cout_faconnage=request.data.get('cout_faconnage', 0),
                user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        operation.refresh_from_db()
        return Response(self.get_serializer(operation).data)

    def _mes_action(self, fonction, request, pk):
        operation = self.get_object()
        try:
            fonction(operation, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        operation.refresh_from_db()
        return Response(self.get_serializer(operation).data)


@extend_schema(responses=inline_serializer('MrpChargePostesLigne', {
    'poste_id': serializers.IntegerField(),
    'poste_nom': serializers.CharField(),
    'jour': serializers.CharField(),
    'minutes_planifiees': serializers.CharField(),
    'capacite_minutes': serializers.CharField(),
    'taux_charge_pct': serializers.CharField(),
    'surcharge': serializers.BooleanField(),
}, many=True))
@api_view(['GET'])
def charge_postes_view(request):
    """NTMFG7 — ``GET /api/django/mrp/charge-postes/?debut=&fin=`` : charge
    par poste/jour sur la fenêtre (défaut : aujourd'hui → +13 jours, 2
    semaines). Dates au format ``AAAA-MM-JJ``."""
    from django.utils import timezone as dj_timezone

    from .selectors import charge_postes

    aujourd_hui = dj_timezone.localdate()
    debut = _parse_date_param(request, 'debut', aujourd_hui)
    fin = _parse_date_param(request, 'fin', aujourd_hui + timedelta(days=13))
    return Response(charge_postes(request.user.company, debut, fin))


@extend_schema(request=None, responses=inline_serializer('MrpBesoinNetLigne', {
    'produit_id': serializers.IntegerField(),
    'produit_nom': serializers.CharField(),
    'sku': serializers.CharField(),
    'demande': serializers.CharField(),
    'stock_disponible': serializers.CharField(),
    'en_cours_fabrication': serializers.CharField(),
    'stock_securite': serializers.CharField(),
    'besoin_net': serializers.CharField(),
    'proposition': serializers.CharField(allow_null=True),
    'date_besoin': serializers.CharField(allow_null=True),
}, many=True))
@api_view(['POST'])
def mrp_run_view(request):
    """NTMFG5 — ``POST /api/django/mrp/mrp-run/`` : calcul des besoins nets
    (MRP) à la demande, company-scopé. Corps optionnel :
    ``{"produits": [id, ...], "demande_independante": {"<produit_id>": qte},
    "stock_securite_pct": "10", "horizon_jours": 30}``."""
    from .selectors import calculer_besoins_nets

    body = request.data or {}
    resultats = calculer_besoins_nets(
        request.user.company,
        produits=body.get('produits'),
        demande_independante=body.get('demande_independante'),
        stock_securite_pct=body.get('stock_securite_pct') or 0,
        horizon_jours=body.get('horizon_jours'))
    return Response(resultats)


class CoutStandardViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          viewsets.GenericViewSet):
    """NTMFG11 — coûts de revient standard (versionnés, FIGÉS — jamais créés
    à la main : seule l'action `figer/` calcule et enregistre une nouvelle
    version, aucun `create`/`update`/`delete` générique). Admin/responsable
    UNIQUEMENT — jamais `prix_achat`/coût client-facing (DC28)."""
    queryset = CoutStandard.objects.select_related('produit').all()
    serializer_class = CoutStandardSerializer
    filterset_fields = ['produit']

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            return qs.filter(company=user.company)
        return qs.none() if not user.is_superuser else qs

    @action(detail=False, methods=['post'], url_path='figer')
    def figer(self, request):
        """NTMFG11 — calcule et fige une nouvelle version de coût standard
        pour `produit` (roll-up nomenclature + gamme). Corps :
        ``{"produit": id, "gamme": id, "cout_indirect_pct": "5",
        "date_effective": "AAAA-MM-JJ"}``."""
        from .services import figer_cout_standard

        produit_id = request.data.get('produit')
        gamme_id = request.data.get('gamme')
        gamme = Gamme.objects.filter(
            id=gamme_id, company=request.user.company).first()
        if gamme is None:
            return Response({'detail': 'Gamme inconnue pour cette société.'}, status=400)
        if str(gamme.produit_id) != str(produit_id):
            return Response(
                {'detail': 'La gamme ne correspond pas au produit.'}, status=400)
        standard = figer_cout_standard(
            request.user.company, gamme.produit, gamme,
            cout_indirect_pct=request.data.get('cout_indirect_pct') or 0,
            date_effective=request.data.get('date_effective') or None,
            user=request.user)
        return Response(
            self.get_serializer(standard).data, status=201)


class OrdreModificationViewSet(CompanyScopedModelViewSet):
    """NTMFG15 — PLM léger : Ordres de Modification (ECO). Le `demandeur` est
    posé CÔTÉ SERVEUR (jamais accepté du corps de requête) ; `approuver/` et
    `rejeter/` sont les SEULES transitions de statut (jamais de PATCH direct
    sur `statut`, verrouillé en lecture seule côté serializer). Écriture
    réservée responsable/admin (un ECO approuvé modifie une gamme/nomenclature
    active — acte d'exploitation, même palier que `OrdreFabricationViewSet`)."""
    queryset = OrdreModification.objects.select_related(
        'produit', 'demandeur', 'approbateur').all()
    serializer_class = OrdreModificationSerializer
    filterset_fields = ['produit', 'statut', 'type_eco']

    def get_queryset(self):
        qs = super().get_queryset()
        produit = self.request.query_params.get('produit')
        if produit:
            qs = qs.filter(produit_id=produit)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        company = self.request.user.company
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(produit, 'company_id', None) != getattr(company, 'id', None):
            raise ValidationError({'produit': 'Produit inconnu pour cette société.'})
        serializer.save(company=company, demandeur=self.request.user)

    @action(detail=True, methods=['post'], url_path='approuver')
    def approuver(self, request, pk=None):
        """NTMFG15 — approuve l'ECO ; applique aussitôt si l'effectivité est
        déjà atteinte (ou absente = immédiat)."""
        from .services import approuver_eco
        eco = self.get_object()
        try:
            approuver_eco(eco, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        eco.refresh_from_db()
        return Response(self.get_serializer(eco).data)

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        """NTMFG15 — rejette l'ECO : aucun changement appliqué."""
        from .services import rejeter_eco
        eco = self.get_object()
        try:
            rejeter_eco(eco)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        eco.refresh_from_db()
        return Response(self.get_serializer(eco).data)


class ReglesKanbanProductionViewSet(CompanyScopedModelViewSet):
    """NTMFG17 — CRUD des règles kanban de production (company-scopé)."""
    queryset = ReglesKanbanProduction.objects.select_related(
        'produit', 'poste_charge_defaut').all()
    serializer_class = ReglesKanbanProductionSerializer
    filterset_fields = ['produit', 'actif']


@extend_schema(request=None, responses=inline_serializer('MrpKanbanDeclencheOF', {
    'id': serializers.IntegerField(),
    'produit': serializers.IntegerField(),
    'quantite': serializers.CharField(),
    'statut': serializers.CharField(),
}, many=True))
@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
def kanban_declencher_view(request):
    """NTMFG17 — ``POST /api/django/mrp/kanban/declencher/`` : déclenchement
    MANUEL de toutes les règles kanban actives de la société (dégrade
    proprement sans Celery beat déployé — même effet que la tâche
    périodique)."""
    from .services import declencher_kanban_toutes_regles

    crees = declencher_kanban_toutes_regles(request.user.company)
    return Response([
        {'id': of.id, 'produit': of.produit_id, 'quantite': str(of.quantite),
         'statut': of.statut}
        for of in crees
    ])


# PACT7 — sans cette déclaration, le schéma OpenAPI publiait cet agrégat VIDE
# (aucun ``serializer_class`` sur une vue-fonction) : la vue renvoie une LISTE
# de lignes d'écart par produit, jamais un objet unique. Cf.
# apps/flotte/views.py::VehiculeViewSet.tableau_bord.
@extend_schema(responses=inline_serializer('MrpAnalyseCoutsLigne', {
    'produit_id': serializers.IntegerField(),
    'produit_nom': serializers.CharField(),
    'nb_of': serializers.IntegerField(),
    'cout_matiere_standard': serializers.CharField(),
    'cout_matiere_reel': serializers.CharField(),
    'ecart_matiere': serializers.CharField(),
    'cout_main_oeuvre_standard': serializers.CharField(),
    'cout_main_oeuvre_reel': serializers.CharField(),
    'ecart_main_oeuvre': serializers.CharField(),
    'ecart_rendement': serializers.CharField(),
    'ecart_total': serializers.CharField(),
}, many=True))
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def analyse_couts_view(request):
    """NTMFG11 — ``GET /api/django/mrp/analyse-couts/?produit=&date_debut=
    &date_fin=`` : rapport d'écarts matière/main-d'œuvre/rendement vs coût
    standard courant, groupé par produit. Admin/responsable UNIQUEMENT."""
    from .selectors import analyse_couts

    resultats = analyse_couts(
        request.user.company,
        produit_id=request.query_params.get('produit'),
        date_debut=request.query_params.get('date_debut'),
        date_fin=request.query_params.get('date_fin'))
    return Response(resultats)


@extend_schema(responses=inline_serializer('MrpOeeTousPostesLigne', {
    'poste_id': serializers.IntegerField(),
    'poste_nom': serializers.CharField(),
    'debut': serializers.CharField(),
    'fin': serializers.CharField(),
    'donnees': serializers.BooleanField(),
    'nb_operations': serializers.IntegerField(),
    'disponibilite_pct': serializers.CharField(),
    'performance_pct': serializers.CharField(),
    'qualite_pct': serializers.CharField(),
    'trs_pct': serializers.CharField(),
}, many=True))
@api_view(['GET'])
def oee_tous_postes_view(request):
    """NTMFG12 — ``GET /api/django/mrp/oee-postes/?debut=&fin=`` : TRS de
    tous les postes actifs (comparaison inter-postes), triés décroissant."""
    from django.utils import timezone as dj_timezone

    from .selectors import oee_tous_postes

    aujourd_hui = dj_timezone.localdate()
    debut = _parse_date_param(request, 'debut', aujourd_hui - timedelta(days=27))
    fin = _parse_date_param(request, 'fin', aujourd_hui)
    return Response(oee_tous_postes(request.user.company, debut, fin))
