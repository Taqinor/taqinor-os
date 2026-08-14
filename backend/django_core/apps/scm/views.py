"""Vues de planification supply chain (Groupe NTSCM).

Accès réservé Responsable/Administrateur (données de planification achat —
même palier que les modules de conformité/planification voisins, ex.
``apps.fiscal``) : ``get_permissions`` renvoie ``[IsResponsableOrAdmin()]``
sur chaque viewset, société toujours scopée par ``CompanyScopedModelViewSet``.
"""
from decimal import Decimal

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    ClassificationABC, CyclePlanificationSOP, EvenementDemande, LigneDemandeSOP,
    PolitiqueStock, PrevisionDemande,
)
from .serializers import (
    ClassificationABCSerializer, CyclePlanificationSOPSerializer,
    EvenementDemandeSerializer, LigneDemandeSOPSerializer, LigneOffreSOPSerializer,
    PolitiqueStockSerializer, PrevisionDemandeSerializer,
)


class PrevisionDemandeViewSet(CompanyScopedModelViewSet):
    """CRUD des prévisions de demande (NTSCM1) + génération automatique
    (NTSCM2/3, ``@action`` ``generer``)."""
    queryset = PrevisionDemande.objects.select_related(
        'produit', 'genere_par').all()
    serializer_class = PrevisionDemandeSerializer

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        # ``DjangoFilterBackend`` n'est pas monté dans ce projet (défaut
        # global = OrderingFilter/SearchFilter seulement, voir
        # ``apps/assurances/views.py``) : filtre manuel, à la main, pour que
        # ``?produit=&segment=`` filtrent réellement la liste.
        qs = super().get_queryset()
        params = self.request.query_params
        produit = params.get('produit')
        if produit:
            qs = qs.filter(produit_id=produit)
        segment = params.get('segment')
        if segment:
            qs = qs.filter(segment=segment)
        periode_min = params.get('periode_min')
        periode_max = params.get('periode_max')
        if periode_min:
            qs = qs.filter(periode__gte=periode_min)
        if periode_max:
            qs = qs.filter(periode__lte=periode_max)
        return qs

    @action(detail=False, methods=['post'], url_path='generer')
    def generer(self, request):
        """NTSCM2/3 — (re)génère les prévisions d'un produit sur un horizon
        donné. Corps : ``{"produit_id": …, "horizon_mois": 3, "segment": ""}``.
        Le produit est résolu via ``apps.stock.selectors`` (jamais un import
        de modèle)."""
        from apps.stock.selectors import get_produit_scoped

        from . import services

        produit_id = request.data.get('produit_id')
        if not produit_id:
            return Response({'produit_id': 'Requis.'}, status=400)
        produit = get_produit_scoped(request.user.company, produit_id)
        if produit is None:
            return Response({'produit_id': 'Produit introuvable.'}, status=404)

        horizon_mois = int(request.data.get('horizon_mois') or 3)
        segment = request.data.get('segment') or ''
        previsions = services.generer_previsions(
            produit, horizon_mois, request.user.company,
            segment=segment, user=request.user)
        return Response(
            PrevisionDemandeSerializer(previsions, many=True).data)


class EvenementDemandeViewSet(CompanyScopedModelViewSet):
    """CRUD des événements de demande (NTSCM3) — promotions, chantiers
    planifiés, ruptures fournisseur connues, appliqués par
    ``services.generer_previsions``."""
    queryset = EvenementDemande.objects.select_related(
        'produit', 'categorie').all()
    serializer_class = EvenementDemandeSerializer
    filterset_fields = ['produit', 'categorie', 'type_evenement']

    def get_permissions(self):
        return [IsResponsableOrAdmin()]


class ClassificationABCViewSet(CompanyScopedModelViewSet):
    """NTSCM4 — classement ABC (Pareto) des produits, recalculé par
    ``selectors.classifier_abc`` (``@action`` ``recalculer``, admin/
    responsable). Voir ``models.ClassificationABC`` pour l'adaptation de
    périmètre (persisté ici plutôt que sur ``stock.Produit``, frontière
    cross-app)."""
    queryset = ClassificationABC.objects.select_related('produit').all()
    serializer_class = ClassificationABCSerializer
    filterset_fields = ['classe']

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    @action(detail=False, methods=['post'], url_path='recalculer')
    def recalculer(self, request):
        """NTSCM4 — recalcule et persiste le classement ABC de la société.
        Corps optionnel : ``{"fenetre_mois": 12}``."""
        from . import selectors

        fenetre_mois = int(request.data.get('fenetre_mois') or 12)
        resultat = selectors.classifier_abc(request.user.company, fenetre_mois)
        qs = ClassificationABC.objects.filter(
            company=request.user.company).select_related('produit')
        return Response({
            'nb_produits_classes': len(resultat),
            'classement': ClassificationABCSerializer(qs, many=True).data,
        })


class PolitiqueStockViewSet(CompanyScopedModelViewSet):
    """NTSCM6 — politiques de stock (min/max, ROP, stock de sécurité) par
    produit, recalculées par ``services.recalculer_politiques_stock``
    (``@action`` ``recalculer``, admin/responsable)."""
    queryset = PolitiqueStock.objects.select_related('produit').all()
    serializer_class = PolitiqueStockSerializer
    filterset_fields = ['classe_abc']

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    @action(detail=False, methods=['post'], url_path='recalculer')
    def recalculer(self, request):
        """NTSCM6 — recalcule les politiques de stock de la société."""
        from . import services

        politiques = services.recalculer_politiques_stock(request.user.company)
        return Response({
            'nb_politiques': len(politiques),
            'politiques': PolitiqueStockSerializer(politiques, many=True).data,
        })


class CyclePlanificationSOPViewSet(CompanyScopedModelViewSet):
    """NTSCM12 — cycles de planification S&OP mensuels. ``statut`` est en
    LECTURE SEULE (voir ``serializers.CyclePlanificationSOPSerializer``) : le
    cycle de vie passe exclusivement par les actions ``avancer-statut`` et
    ``reouvrir`` (admin), machine à états séquentielle appliquée côté
    serveur."""
    queryset = CyclePlanificationSOP.objects.select_related('anime_par').all()
    serializer_class = CyclePlanificationSOPSerializer
    filterset_fields = ['statut']

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    @action(detail=True, methods=['post'], url_path='avancer-statut')
    def avancer_statut(self, request, pk=None):
        """NTSCM12 — avance à l'étape suivante. Corps optionnel :
        ``{"statut": "revue_demande"}`` — DOIT être exactement l'étape
        suivante, sinon 400 (refuse tout saut d'étape)."""
        from . import services

        cycle = self.get_object()
        try:
            services.avancer_statut_cycle(
                cycle, request.user, statut_cible=request.data.get('statut') or None)
        except ValueError as exc:
            return Response({'statut': str(exc)}, status=400)
        return Response(CyclePlanificationSOPSerializer(cycle).data)

    @action(detail=True, methods=['post'], url_path='reouvrir')
    def reouvrir(self, request, pk=None):
        """NTSCM12 — réouverture ADMIN EXPLICITE (retour à brouillon),
        journalisée. Réservé Administrateur (au-delà du palier Responsable du
        viewset)."""
        from authentication.permissions import IsAdminRole

        from . import services

        if not IsAdminRole().has_permission(request, self):
            return Response(
                {'detail': 'Réservé aux administrateurs.'}, status=403)
        cycle = self.get_object()
        services.reouvrir_cycle(cycle, request.user, motif=request.data.get('motif', ''))
        return Response(CyclePlanificationSOPSerializer(cycle).data)

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """NTSCM12 — timeline des transitions (chatter générique
        ``records.Activity``, plus récent d'abord)."""
        from apps.records.serializers import ChatterActivitySerializer
        from apps.records.services import chatter_qs

        cycle = self.get_object()
        entries = chatter_qs(cycle, request.user.company)
        return Response(ChatterActivitySerializer(entries, many=True).data)

    @action(detail=True, methods=['get'], url_path='lignes-demande')
    def lignes_demande(self, request, pk=None):
        """NTSCM13 — lignes de demande gelées du cycle (voir
        ``services.geler_previsions_cycle``, déclenché automatiquement au
        passage brouillon -> revue_demande)."""
        cycle = self.get_object()
        lignes = cycle.lignes_demande.select_related('produit').all()
        return Response(LigneDemandeSOPSerializer(lignes, many=True).data)

    @action(detail=True, methods=['post'], url_path='ajuster-demande')
    def ajuster_demande(self, request, pk=None):
        """NTSCM13 — ajustement commercial MOTIVÉ d'une ligne de demande
        gelée. Corps : ``{"produit_id": …, "quantite_ajustee": …, "motif": …}``.
        Un motif vide est refusé (400) — l'ajustement doit toujours être
        expliqué."""
        cycle = self.get_object()
        produit_id = request.data.get('produit_id')
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response({'motif': 'Requis pour tout ajustement.'}, status=400)
        try:
            ligne = cycle.lignes_demande.get(produit_id=produit_id)
        except LigneDemandeSOP.DoesNotExist:
            return Response(
                {'produit_id': "Aucune ligne de demande gelée pour ce produit."},
                status=404)
        ligne.quantite_ajustee_commercial = request.data.get('quantite_ajustee')
        ligne.motif_ajustement = motif
        ligne.save(update_fields=[
            'quantite_ajustee_commercial', 'motif_ajustement',
            'quantite_finale', 'updated_at',
        ])
        return Response(LigneDemandeSOPSerializer(ligne).data)

    @action(detail=True, methods=['post'], url_path='calculer-offre')
    def calculer_offre(self, request, pk=None):
        """NTSCM14 — (re)calcule les lignes d'offre du cycle depuis
        ``apps.stock.selectors`` (stock disponible + capacité appro
        fournisseur)."""
        from . import services

        cycle = self.get_object()
        lignes = services.calculer_offre_cycle(cycle)
        return Response(LigneOffreSOPSerializer(lignes, many=True).data)

    @action(detail=True, methods=['get'], url_path='ecarts')
    def ecarts(self, request, pk=None):
        """NTSCM14 — lignes d'offre du cycle, TRIÉES par écart le plus
        négatif (pénurie prévisible) en premier (``Meta.ordering``)."""
        cycle = self.get_object()
        lignes = cycle.lignes_offre.select_related('produit').all()
        return Response(LigneOffreSOPSerializer(lignes, many=True).data)

    @action(detail=True, methods=['get'], url_path='impact-financier')
    def impact_financier(self, request, pk=None):
        """NTSCM15 — impact financier (CA prévisionnel vs forecast) du plan
        de demande du cycle. Réservé Administrateur (au-delà du palier
        Responsable du viewset — donnée de marge/CA sensible)."""
        from authentication.permissions import IsAdminRole

        from . import selectors

        if not IsAdminRole().has_permission(request, self):
            return Response(
                {'detail': 'Réservé aux administrateurs.'}, status=403)
        cycle = self.get_object()
        resultat = selectors.impact_financier_cycle(cycle)
        # Réponse construite à la main (pas de Serializer ici) : `resp.data`
        # DRF ne passe PAS par le JSONRenderer avant les tests — stringifier
        # les montants ici, comme `ventes/views/liste_prix.py`, plutôt que de
        # laisser fuiter des `Decimal` d'échelle variable (ex. 4 décimales
        # après une multiplication 2×2) au client.
        resultat['ca_previsionnel_ht'] = str(
            resultat['ca_previsionnel_ht'].quantize(Decimal('0.01')))
        if resultat['ca_forecast_ht'] is not None:
            resultat['ca_forecast_ht'] = str(
                resultat['ca_forecast_ht'].quantize(Decimal('0.01')))
        return Response(resultat)


# PACT7 — sans cette déclaration, le schéma OpenAPI publiait cet agrégat VIDE
# (aucun ``serializer_class`` sur une vue-fonction) : la vue renvoie une LISTE
# de lignes de réappro, jamais un objet unique. Cf.
# apps/flotte/views.py::VehiculeViewSet.tableau_bord.
@extend_schema(responses=inline_serializer('ScmTableauBordReapproLigne', {
    'produit_id': serializers.IntegerField(),
    'produit_nom': serializers.CharField(),
    'classe_abc': serializers.CharField(),
    'stock_actuel': serializers.IntegerField(),
    'point_commande': serializers.CharField(),
    'quantite_suggeree': serializers.IntegerField(),
    'statut': serializers.CharField(),
    'rupture_date': serializers.CharField(allow_null=True),
    'fournisseur_id': serializers.IntegerField(allow_null=True),
    'fournisseur_nom': serializers.CharField(allow_null=True),
    'prix_achat_unitaire': serializers.CharField(allow_null=True),
}, many=True))
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def tableau_bord_reappro_view(request):
    """NTSCM7 — ``GET /api/django/scm/tableau-bord-reappro/``.

    Filtres optionnels : ``?statut=ok|a_commander|rupture_imminente``,
    ``?classe_abc=A|B|C``, ``?fournisseur=<id>``."""
    from . import selectors

    data = selectors.tableau_bord_reappro(
        request.user.company,
        statut=request.query_params.get('statut'),
        classe_abc=request.query_params.get('classe_abc'),
        fournisseur_id=request.query_params.get('fournisseur'),
    )
    return Response(data)


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
def creer_brouillons_bcf_reappro_view(request):
    """NTSCM7 — ``POST /api/django/scm/tableau-bord-reappro/creer-bcf/``.

    Groupe les lignes du tableau de bord (statut ``a_commander`` ou
    ``rupture_imminente``, fournisseur connu) PAR FOURNISSEUR et crée un
    ``BonCommandeFournisseur`` BROUILLON par fournisseur via
    ``apps.stock.services.creer_bcf_depuis_lignes`` (réutilise l'existant,
    jamais une écriture directe dans ``apps.stock``). Corps optionnel :
    ``{"produit_ids": [...]}`` pour restreindre la sélection (défaut : toutes
    les lignes à commander)."""
    from apps.stock.selectors import get_fournisseur_by_id
    from apps.stock.services import creer_bcf_depuis_lignes

    from . import selectors

    lignes_tableau = selectors.tableau_bord_reappro(request.user.company)

    produit_ids = request.data.get('produit_ids')
    if produit_ids:
        wanted = {int(pid) for pid in produit_ids}
        lignes_tableau = [
            ligne for ligne in lignes_tableau if ligne['produit_id'] in wanted]

    lignes_a_commander = [
        ligne for ligne in lignes_tableau
        if ligne['statut'] != 'ok' and ligne['fournisseur_id']
    ]

    groupes = {}
    for ligne in lignes_a_commander:
        groupes.setdefault(ligne['fournisseur_id'], []).append(ligne)

    bons_crees = []
    for fournisseur_id, lignes in groupes.items():
        fournisseur = get_fournisseur_by_id(request.user.company, fournisseur_id)
        if fournisseur is None:
            continue
        lignes_bcf = [
            (ligne['produit_id'], ligne['produit_nom'],
             ligne['quantite_suggeree'] or 1, ligne['prix_achat_unitaire'] or 0)
            for ligne in lignes
        ]
        bon = creer_bcf_depuis_lignes(
            company=request.user.company, user=request.user,
            fournisseur=fournisseur, lignes=lignes_bcf,
            note='Brouillon généré depuis le tableau de bord réappro (NTSCM7).')
        bons_crees.append({
            'fournisseur_id': fournisseur_id,
            'bon_commande_id': bon.id,
            'reference': bon.reference,
            'nb_lignes': len(lignes_bcf),
        })

    return Response({'bons_crees': bons_crees})
