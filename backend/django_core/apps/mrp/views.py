"""Vues de l'app `mrp` (Groupe NTMFG — Production / MRP II)."""
from datetime import datetime, timedelta

from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    CoutStandard, Gamme, OperationGamme, OperationOF, OrdreFabrication, PosteDeCharge,
)
from .serializers import (
    CoutStandardSerializer, GammeSerializer, OperationGammeSerializer,
    OperationOFSerializer, OrdreFabricationSerializer, PosteDeChargeSerializer,
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

    @action(detail=True, methods=['get'], url_path='oee')
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


class OperationGammeViewSet(viewsets.ModelViewSet):
    """NTMFG2 — opérations d'une gamme. Pas de `company` propre : scope via
    la gamme parente (même convention que
    `installations.KitComposantViewSet`). Filtrable par `?gamme=`."""
    queryset = OperationGamme.objects.select_related(
        'gamme', 'poste_charge').all()
    serializer_class = OperationGammeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(gamme__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
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
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()


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
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='confirmer')
    def confirmer(self, request, pk=None):
        """NTMFG3 — instancie les opérations depuis la gamme + planifie les
        dates (capacité poste), passe le statut en `planifie`."""
        from .services import confirmer_of
        of = self.get_object()
        confirmer_of(of, user=request.user)
        of.refresh_from_db()
        return Response(self.get_serializer(of).data)

    @action(detail=True, methods=['post'], url_path='cloturer')
    def cloturer(self, request, pk=None):
        """NTMFG4 — clôture l'OF : backflush (consommation composants +
        production composite) exactement une fois, sauf si un
        `kit_ordre_assemblage` porte déjà le mouvement (XMFG1)."""
        from .services import cloturer_of
        of = self.get_object()
        cloturer_of(of, user=request.user)
        of.refresh_from_db()
        return Response(self.get_serializer(of).data)

    @action(detail=True, methods=['post'], url_path='annuler')
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

    @action(detail=True, methods=['get'], url_path='dispo-composants')
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

    @action(detail=True, methods=['patch'], url_path='replanifier')
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

    @action(detail=True, methods=['post'], url_path='demarrer')
    def demarrer(self, request, pk=None):
        """NTMFG8 — terminal atelier : démarre l'opération."""
        from .services import demarrer_operation
        return self._mes_action(demarrer_operation, request, pk)

    @action(detail=True, methods=['post'], url_path='pauser')
    def pauser(self, request, pk=None):
        """NTMFG8 — terminal atelier : met l'opération en pause."""
        from .services import pauser_operation
        return self._mes_action(pauser_operation, request, pk)

    @action(detail=True, methods=['post'], url_path='reprendre')
    def reprendre(self, request, pk=None):
        """NTMFG8 — terminal atelier : reprend une opération en pause."""
        from .services import reprendre_operation
        return self._mes_action(reprendre_operation, request, pk)

    @action(detail=True, methods=['post'], url_path='terminer')
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
