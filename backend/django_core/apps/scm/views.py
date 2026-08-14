"""Vues de planification supply chain (Groupe NTSCM).

Accès réservé Responsable/Administrateur (données de planification achat —
même palier que les modules de conformité/planification voisins, ex.
``apps.fiscal``) : ``get_permissions`` renvoie ``[IsResponsableOrAdmin()]``
sur chaque viewset, société toujours scopée par ``CompanyScopedModelViewSet``.

NTSCM37 — quatre viewsets (prévisions/événements, politiques de stock, cycles
S&OP) affinent CETTE garde avec les permissions dédiées d'``apps.scm.
permissions`` (``HasPermissionOrLegacy`` — repli sur ce MÊME palier
Responsable/Admin pour un compte hérité sans rôle fin, donc AUCUNE régression
pour les comptes existants). ``ClassificationABCViewSet`` reste sur le
palier générique (aucun code dédié demandé par le plan)."""
from decimal import Decimal

from drf_spectacular.types import OpenApiTypes
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
from .permissions import (
    IsScmPolitiquesStockEditer, IsScmPrevisionsEditer, IsScmPrevisionsVoir,
    IsScmSopAnimer, IsScmSopVoir,
)
from .serializers import (
    ClassificationABCSerializer, CyclePlanificationSOPSerializer,
    EvenementDemandeSerializer, LigneDemandeSOPSerializer, LigneOffreSOPSerializer,
    PolitiqueStockSerializer, PrevisionDemandeSerializer,
)

# NTSCM37 — actions en LECTURE d'un ModelViewSet standard (les autres,
# create/update/partial_update/destroy + toute @action d'écriture, sont
# considérées ÉCRITURE).
_ACTIONS_LECTURE = frozenset({'list', 'retrieve'})


class PrevisionDemandeViewSet(CompanyScopedModelViewSet):
    """CRUD des prévisions de demande (NTSCM1) + génération automatique
    (NTSCM2/3, ``@action`` ``generer``)."""
    queryset = PrevisionDemande.objects.select_related(
        'produit', 'genere_par').all()
    serializer_class = PrevisionDemandeSerializer

    def get_permissions(self):
        # NTSCM37 — `generer` (@action POST) est une ÉCRITURE.
        if self.action in _ACTIONS_LECTURE:
            return [IsScmPrevisionsVoir()]
        return [IsScmPrevisionsEditer()]

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

        from . import selectors, services

        produit_id = request.data.get('produit_id')
        if not produit_id:
            return Response({'produit_id': 'Requis.'}, status=400)
        produit = get_produit_scoped(request.user.company, produit_id)
        if produit is None:
            return Response({'produit_id': 'Produit introuvable.'}, status=404)

        # NTSCM33 — repli sur l'horizon par défaut de la société
        # (`ParametresSCM.horizon_prevision_mois_defaut`) quand non précisé.
        horizon_mois = request.data.get('horizon_mois')
        horizon_mois = (
            int(horizon_mois) if horizon_mois
            else selectors.parametres(request.user.company).horizon_prevision_mois_defaut)
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
        # NTSCM37 — les événements de demande alimentent NTSCM2/3 : mêmes
        # codes que les prévisions (même écran, même acheteur).
        if self.action in _ACTIONS_LECTURE:
            return [IsScmPrevisionsVoir()]
        return [IsScmPrevisionsEditer()]


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
        # NTSCM37 — lecture (liste/détail/fiche PDF/historique NTSCM44) reste
        # au palier générique historique (aucun code « politiques_stock.voir »
        # au plan) ; toute écriture (create/update/destroy + recalculer/
        # creer-en-lot) exige `scm_politiques_stock_editer`.
        if self.action in _ACTIONS_LECTURE or self.action in ('fiche_pdf', 'historique'):
            return [IsResponsableOrAdmin()]
        return [IsScmPolitiquesStockEditer()]

    # NTSCM44 — champs dont chaque révision journalise une entrée de chatter
    # automatique (ancienne/nouvelle valeur, horodatée + utilisateur).
    _CHAMPS_JOURNALISES = [
        ('service_level_pct', 'Niveau de service (%)'),
        ('stock_securite_manuel', 'Stock de sécurité (override manuel)'),
        ('stock_min', 'Stock min'),
        ('stock_max', 'Stock max'),
    ]

    def perform_update(self, serializer):
        """NTSCM44 — journalise (``records.Activity`` via ``log_field_change``,
        même mécanisme générique que ``crm.LeadActivity``) chaque champ
        RÉELLEMENT modifié par cette écriture — jamais une entrée pour un
        champ envoyé mais identique à sa valeur actuelle."""
        from apps.records.services import log_field_change

        instance = serializer.instance
        avant = {
            field: getattr(instance, field) for field, _ in self._CHAMPS_JOURNALISES
        }
        politique = serializer.save()
        for field, label in self._CHAMPS_JOURNALISES:
            ancien = avant[field]
            nouveau = getattr(politique, field)
            if ancien != nouveau:
                log_field_change(
                    politique, field, ancien, nouveau,
                    user=self.request.user, field_label=label,
                    company=politique.company)

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """NTSCM44 — fil d'activité de la politique de stock (chatter
        générique ``records.Activity``, plus récent d'abord) — même patron
        que ``CyclePlanificationSOPViewSet.historique`` (NTSCM12)."""
        from apps.records.serializers import ChatterActivitySerializer
        from apps.records.services import chatter_qs

        politique = self.get_object()
        entries = chatter_qs(politique, request.user.company)
        return Response(ChatterActivitySerializer(entries, many=True).data)

    @action(detail=False, methods=['post'], url_path='recalculer')
    def recalculer(self, request):
        """NTSCM6 — recalcule les politiques de stock de la société."""
        from . import services

        politiques = services.recalculer_politiques_stock(request.user.company)
        return Response({
            'nb_politiques': len(politiques),
            'politiques': PolitiqueStockSerializer(politiques, many=True).data,
        })

    @extend_schema(responses={200: OpenApiTypes.BINARY})
    @action(detail=True, methods=['get'], url_path='fiche-pdf')
    def fiche_pdf(self, request, pk=None):
        """NTSCM29 — PDF interne récapitulatif de la politique de stock
        (jamais un document client — bandeau visible, aucun prix d'achat)."""
        from django.http import HttpResponse

        from . import services

        politique = self.get_object()
        pdf_bytes = services.generer_fiche_politique_stock(politique)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="politique-stock-{politique.produit_id}.pdf"')
        return response

    @extend_schema(
        request=inline_serializer('ScmCreerPolitiquesEnLotRequest', {
            'produit_ids': serializers.ListField(
                child=serializers.IntegerField()),
            'service_level_pct': serializers.DecimalField(
                max_digits=5, decimal_places=2),
        }),
        responses=inline_serializer('ScmCreerPolitiquesEnLotResponse', {
            'nb_politiques': serializers.IntegerField(),
            'politiques': PolitiqueStockSerializer(many=True),
        }))
    @action(detail=False, methods=['post'], url_path='creer-en-lot')
    def creer_en_lot(self, request):
        """NTSCM30 — assistant guidé « Créer une politique de stock » :
        applique NTSCM6 en LOT à une sélection de produits. Corps :
        ``{"produit_ids": [...], "service_level_pct": 95}``."""
        from apps.stock.selectors import valid_produit_ids

        from . import services

        produit_ids = request.data.get('produit_ids') or []
        if not produit_ids:
            return Response({'produit_ids': 'Requis (au moins un produit).'}, status=400)
        service_level_pct = request.data.get('service_level_pct')
        if service_level_pct in (None, ''):
            return Response({'service_level_pct': 'Requis.'}, status=400)

        from django.apps import apps as django_apps
        Produit = django_apps.get_model('stock', 'Produit')

        ids_valides = valid_produit_ids(request.user.company, produit_ids)
        produits = list(Produit.objects.filter(
            company=request.user.company, pk__in=ids_valides))
        politiques = services.creer_politiques_en_lot(
            produits, Decimal(str(service_level_pct)), request.user.company)
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

    # NTSCM37 — LECTURE seule (liste/détail + sous-ressources en GET) exige
    # `scm_sop_voir` ; TOUT le reste — création, édition, et les actions qui
    # « animent » le cycle (avancer/ajuster/calculer/réouvrir) — exige
    # `scm_sop_animer` (réservé Administrateur/Directeur par défaut, voir
    # `apps.roles.models.RESPONSABLE_PERMISSIONS`). `reouvrir`/
    # `impact_financier` gardent EN PLUS leur vérification manuelle
    # `IsAdminRole` existante (inchangée).
    _ACTIONS_LECTURE_SOP = _ACTIONS_LECTURE | {
        'historique', 'lignes_demande', 'ecarts', 'impact_financier',
        'compte_rendu',
    }

    def get_permissions(self):
        if self.action in self._ACTIONS_LECTURE_SOP:
            return [IsScmSopVoir()]
        return [IsScmSopAnimer()]

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

    @extend_schema(responses={200: OpenApiTypes.BINARY})
    @action(detail=True, methods=['get'], url_path='compte-rendu')
    def compte_rendu(self, request, pk=None):
        """NTSCM27 — télécharge le compte-rendu .xlsx du cycle (3 feuilles :
        Demande consensuelle, Offre et écarts, Impact financier), régénéré à
        la demande. Le DÉPÔT en GED, lui, n'a lieu QU'À LA CLÔTURE du cycle
        (voir ``services.avancer_statut_cycle``, hook NTSCM27)."""
        import io

        from django.http import HttpResponse

        from apps.records.xlsx import XLSX_CONTENT_TYPE

        from . import services

        cycle = self.get_object()
        wb = services._construire_classeur_sop(cycle)
        buf = io.BytesIO()
        wb.save(buf)
        response = HttpResponse(buf.getvalue(), content_type=XLSX_CONTENT_TYPE)
        response['Content-Disposition'] = (
            f'attachment; filename="compte-rendu-sop-{cycle.periode}.xlsx"')
        return response


# PACT7 — sans cette déclaration, le schéma OpenAPI publiait cet agrégat VIDE
# (aucun ``serializer_class`` sur une vue-fonction) : la vue renvoie une LISTE
# de lignes de réappro, jamais un objet unique. Cf.
# apps/flotte/views.py::VehiculeViewSet.tableau_bord.
@extend_schema(responses=inline_serializer('ScmTableauBordReapproLigne', {
    'produit_id': serializers.IntegerField(),
    'produit_nom': serializers.CharField(),
    'politique_id': serializers.IntegerField(),
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


@extend_schema(request=None, responses=inline_serializer('ScmBrouillonsBcfReappro', {
    'bons_crees': inline_serializer('ScmBrouillonBcfReapproLigne', {
        'fournisseur_id': serializers.IntegerField(),
        'bon_commande_id': serializers.IntegerField(),
        'reference': serializers.CharField(),
        'nb_lignes': serializers.IntegerField(),
    }, many=True),
}))
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


# ── NTSCM16 — suggestion d'achat groupée multi-fournisseurs (MOQ/paliers) ────

@extend_schema(responses=inline_serializer('ScmSuggestionAchatGroupe', {
    'fournisseur_id': serializers.IntegerField(),
    'fournisseur_nom': serializers.CharField(),
    'lignes': serializers.ListField(child=serializers.DictField()),
}, many=True))
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def suggestions_achat_groupe_view(request):
    """NTSCM16 — ``GET /api/django/scm/suggestions-achat-groupe/`` : suggestions
    d'achat groupées par fournisseur (MOQ/paliers respectés, NTSCM16/17)."""
    from . import services

    return Response(services.suggerer_achats_groupes(request.user.company))


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def export_suggestions_achat_groupe_view(request):
    """NTSCM41 — ``GET /api/django/scm/suggestions-achat-groupe/export/`` :
    export .xlsx des suggestions d'achat groupées (une ligne par produit,
    groupée par fournisseur) — bouton d'export sur ``/scm/reappro``."""
    from apps.records.xlsx import build_xlsx_response

    from . import services

    groupes = services.suggerer_achats_groupes(request.user.company)

    headers = [
        'Fournisseur', 'Produit', 'Besoin net', 'Décision', 'Quantité',
        'Prix unitaire', 'Coût total', 'Justification',
    ]
    rows = []
    for groupe in groupes:
        for ligne in groupe['lignes']:
            if ligne['decision'] == 'sous_moq':
                option_moq = next(
                    (o for o in ligne['options'] if o['action'] == 'commander_moq'),
                    None)
                rows.append([
                    groupe['fournisseur_nom'], ligne['produit_nom'],
                    ligne['besoin_net'], 'Sous le MOQ',
                    option_moq['quantite'] if option_moq else '',
                    option_moq['prix_unitaire'] if option_moq else '',
                    '',
                    f"Besoin sous le MOQ ({ligne['moq']}) — attendre ou "
                    'commander le MOQ (surstock).',
                ])
            else:
                rows.append([
                    groupe['fournisseur_nom'], ligne['produit_nom'],
                    ligne['besoin_net'], 'Commander', ligne['quantite'],
                    ligne['prix_unitaire'], ligne['cout_total'],
                    'Écart offre/demande couvert au coût total le plus bas.',
                ])

    return build_xlsx_response(
        'suggestions-achat-groupe.xlsx', headers, rows,
        sheet_title='Suggestions achat groupé')


# ── NTSCM18 — simulation « et si… » de rupture (lecture seule) ──────────────

@extend_schema(request=inline_serializer('ScmSimulerRuptureRequest', {
    'delai_fournisseur_jours_supplementaires': serializers.IntegerField(required=False),
    'demande_pct': serializers.FloatField(required=False),
    'commande_annulee_quantite': serializers.FloatField(required=False),
}), responses=inline_serializer('ScmSimulerRuptureResponse', {
    'produit_id': serializers.IntegerField(),
    'scenario': serializers.DictField(),
    'base': serializers.DictField(),
    'simule': serializers.DictField(),
    'delta_jours_rupture': serializers.IntegerField(allow_null=True),
    'delta_jours_date_limite_commande': serializers.IntegerField(allow_null=True),
}))
@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
def simuler_rupture_view(request, produit_id):
    """NTSCM18 — ``POST /api/django/scm/produits/<id>/simuler/`` : simulation
    « et si… » EN MÉMOIRE (aucune écriture DB, voir ``services.
    simuler_rupture``). Corps = scénario hypothétique (toutes clés
    optionnelles)."""
    from apps.stock.selectors import get_produit_scoped

    from . import services

    produit = get_produit_scoped(request.user.company, produit_id)
    if produit is None:
        return Response({'detail': 'Produit introuvable.'}, status=404)
    resultat = services.simuler_rupture(produit, request.data or {}, request.user.company)
    return Response(resultat)


# ── NTSCM19 — allocation en pénurie multi-clients (proposition) ─────────────

@extend_schema(responses=inline_serializer('ScmProposerAllocationResponse', {
    'produit_id': serializers.IntegerField(),
    'stock_disponible': serializers.CharField(),
    'mode': serializers.CharField(),
    'propositions': serializers.ListField(child=serializers.DictField()),
}))
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def proposer_allocation_penurie_view(request, produit_id):
    """NTSCM19 — ``GET /api/django/scm/produits/<id>/proposer-allocation/`` :
    proposition (jamais une réservation automatique) de répartition du stock
    disponible entre les devis ouverts qui en dépendent. ``?mode=fifo|priorite``
    (défaut ``fifo``)."""
    from apps.stock.selectors import get_produit_scoped

    from . import services

    produit = get_produit_scoped(request.user.company, produit_id)
    if produit is None:
        return Response({'detail': 'Produit introuvable.'}, status=404)
    mode = request.query_params.get('mode') or 'fifo'
    resultat = services.proposer_allocation_penurie(
        produit, request.user.company, mode=mode)
    return Response(resultat)


# ── NTSCM20 — suggestions de transfert inter-sites (anticipatif) ────────────

@extend_schema(responses=inline_serializer('ScmSuggestionTransfert', {
    'produit_id': serializers.IntegerField(),
    'produit_nom': serializers.CharField(),
    'emplacement_source_id': serializers.IntegerField(),
    'emplacement_source_nom': serializers.CharField(),
    'emplacement_destination_id': serializers.IntegerField(),
    'emplacement_destination_nom': serializers.CharField(),
    'quantite_suggeree': serializers.FloatField(),
}, many=True))
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def suggestions_transfert_view(request):
    """NTSCM20 — ``GET /api/django/scm/suggestions-transfert/`` : suggestions
    de transfert inter-sites PILOTÉES par écart offre/demande projeté
    (anticipatif — étend FG326, réactif)."""
    from . import selectors

    return Response(selectors.suggerer_transferts_inter_sites(request.user.company))


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def export_suggestions_transfert_view(request):
    """NTSCM41 — ``GET /api/django/scm/suggestions-transfert/export/`` :
    export .xlsx des suggestions de transfert inter-sites — bouton d'export
    sur ``/scm/transferts-suggeres``."""
    from apps.records.xlsx import build_xlsx_response

    from . import selectors, services

    lignes = selectors.suggerer_transferts_inter_sites(request.user.company)

    headers = [
        'Produit', 'Dépôt source', 'Dépôt destination', 'Quantité suggérée',
        'Justification',
    ]
    rows = [[
        ligne['produit_nom'], ligne['emplacement_source_nom'],
        ligne['emplacement_destination_nom'],
        services._fmt_dec(ligne['quantite_suggeree']),
        'Surstock projeté au dépôt source, déficit projeté au dépôt destination.',
    ] for ligne in lignes]

    return build_xlsx_response(
        'suggestions-transfert.xlsx', headers, rows,
        sheet_title='Suggestions de transfert')


# ── NTSCM24 — précision de prévision auto-mesurée (MAPE) ────────────────────

@extend_schema(responses=inline_serializer('ScmPrecisionPrevisions', {
    'mape_global_pct': serializers.FloatField(allow_null=True),
    'nb_mois_couverts': serializers.IntegerField(),
    'par_produit': serializers.ListField(child=serializers.DictField()),
}))
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def precision_previsions_view(request):
    """NTSCM24 — ``GET /api/django/scm/precision-previsions/`` : précision de
    prévision (MAPE) globale et par produit. ``?produit=&fenetre_mois=``."""
    from apps.stock.selectors import get_produit_scoped

    from . import selectors

    produit = None
    produit_id = request.query_params.get('produit')
    if produit_id:
        produit = get_produit_scoped(request.user.company, produit_id)
        if produit is None:
            return Response({'produit': 'Produit introuvable.'}, status=404)
    fenetre_mois = int(request.query_params.get('fenetre_mois') or 6)
    return Response(selectors.precision_prevision(
        request.user.company, produit=produit, fenetre_mois=fenetre_mois))


# ── NTSCM32 — export « Écarts de prévision » (.xlsx) ────────────────────────

@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def export_ecarts_prevision_view(request):
    """NTSCM32 — ``GET /api/django/scm/precision-previsions/export/`` :
    export .xlsx du rapport « Écarts de prévision » (NTSCM24 réutilisé) —
    une ligne par produit (prévision, réel, écart absolu, écart %) + un total
    en pied de tableau. ``?fenetre_mois=&produit=``."""
    from apps.records.xlsx import build_xlsx_response
    from apps.stock.selectors import get_produit_scoped

    from . import selectors, services

    produit = None
    produit_id = request.query_params.get('produit')
    if produit_id:
        produit = get_produit_scoped(request.user.company, produit_id)
        if produit is None:
            return Response({'produit': 'Produit introuvable.'}, status=404)
    fenetre_mois = int(request.query_params.get('fenetre_mois') or 6)

    lignes = selectors.ecarts_prevision(
        request.user.company, fenetre_mois=fenetre_mois, produit=produit)

    headers = [
        'Produit', 'Prévision totale', 'Réel total', 'Écart absolu', 'Écart %']
    rows = [[
        ligne['produit_nom'],
        services._fmt_dec(ligne['quantite_prevue_totale']),
        services._fmt_dec(ligne['quantite_reelle_totale']),
        services._fmt_dec(ligne['ecart_absolu']),
        (f"{ligne['ecart_pct']}%" if ligne['ecart_pct'] is not None else '—'),
    ] for ligne in lignes]

    total_prevu = sum((ligne['quantite_prevue_totale'] for ligne in lignes), Decimal('0'))
    total_reel = sum((ligne['quantite_reelle_totale'] for ligne in lignes), Decimal('0'))
    total_ecart = total_reel - total_prevu
    total_ecart_pct = (
        f"{(total_ecart / total_reel * 100).quantize(Decimal('0.01'))}%"
        if total_reel else '—')
    rows.append([
        'TOTAL', services._fmt_dec(total_prevu), services._fmt_dec(total_reel),
        services._fmt_dec(total_ecart), total_ecart_pct,
    ])

    return build_xlsx_response(
        'ecarts-prevision.xlsx', headers, rows, sheet_title='Écarts de prévision')


# ── NTSCM28 — tableau de bord SCM exécutif (KPI de synthèse) ────────────────

@extend_schema(responses=inline_serializer('ScmTableauBordExecutif', {
    'taux_service_pct': serializers.FloatField(allow_null=True),
    'otif_pondere_pct': serializers.FloatField(allow_null=True),
    'mape_global_pct': serializers.FloatField(allow_null=True),
    'valeur_stock_par_classe_abc': serializers.DictField(),
}))
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def tableau_bord_executif_view(request):
    """NTSCM28 — ``GET /api/django/scm/tableau-bord/`` : 4 KPI de synthèse
    exécutifs (taux de service, OTIF pondéré, MAPE global, valeur de stock
    par classe ABC — jamais de ``prix_achat`` en clair)."""
    from . import selectors

    return Response(selectors.tableau_bord_executif(request.user.company))


# ── NTSCM25 — détection d'anomalie de demande (pic/creux inattendu) ─────────

@extend_schema(responses=inline_serializer('ScmAnomalieDemande', {
    'id': serializers.IntegerField(),
    'produit_id': serializers.CharField(allow_null=True),
    'message': serializers.CharField(),
    'severity': serializers.CharField(),
    'created_at': serializers.DateTimeField(),
}, many=True))
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def anomalies_demande_view(request):
    """NTSCM25 — ``GET /api/django/scm/anomalies-demande/`` : anomalies de
    demande OUVERTES (``core.models.AnomalyFlag``, ``subject_type=
    'scm.demande'``, voir ``services.detecter_anomalies_demande``) — alimente
    le badge « ⚠ pic inhabituel détecté » de ``/scm/reappro``."""
    from core.models import AnomalyFlag

    flags = (
        AnomalyFlag.objects
        .filter(
            company=request.user.company, subject_type='scm.demande',
            status=AnomalyFlag.STATUS_OUVERT)
        .order_by('-created_at'))
    data = [{
        'id': f.id,
        'produit_id': f.metric.split(':')[-1] if ':' in (f.metric or '') else None,
        'message': f.message,
        'severity': f.severity,
        'created_at': f.created_at,
    } for f in flags]
    return Response(data)


@extend_schema(request=None, responses=inline_serializer(
    'ScmDetecterAnomaliesDemandeResponse', {'nb_flags': serializers.IntegerField()}))
@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
def detecter_anomalies_demande_view(request):
    """NTSCM25 — ``POST /api/django/scm/anomalies-demande/detecter/`` :
    déclenche manuellement le scan (``services.detecter_anomalies_demande``)."""
    from . import services

    flags = services.detecter_anomalies_demande(request.user.company)
    return Response({'nb_flags': len(flags)})


# ── NTSCM22 — réglages opt-in du cycle S&OP automatique (singleton société) ─

# `request=None` : le PATCH accepte un corps ad-hoc (sop_actif/animateur_sop),
# sans serializer d'entree — sans cette declaration drf-spectacular signale un
# « unable to guess serializer » cote REQUETE, et le cliquet PACT7 n'accepte
# que la decroissance de ce compteur.
@extend_schema(request=None, responses=inline_serializer('ScmParametresSopResponse', {
    'sop_actif': serializers.BooleanField(),
    'animateur_sop': serializers.IntegerField(allow_null=True),
    'animateur_sop_nom': serializers.CharField(allow_null=True),
}))
@api_view(['GET', 'PATCH'])
@permission_classes([IsResponsableOrAdmin])
def parametres_sop_view(request):
    """NTSCM22 — ``GET``/``PATCH /api/django/scm/parametres-sop/`` : réglages
    opt-in du cycle S&OP automatique (singleton par société, créé
    paresseusement — voir ``services.parametres_scm``/``models.
    ParametresSCM``). ``PATCH`` accepte ``{"sop_actif": bool,
    "animateur_sop": <user_id>|null}``."""
    from . import services

    parametres = services.parametres_scm(request.user.company)

    if request.method == 'PATCH':
        from django.contrib.auth import get_user_model

        if 'sop_actif' in request.data:
            parametres.sop_actif = bool(request.data.get('sop_actif'))
        if 'animateur_sop' in request.data:
            animateur_id = request.data.get('animateur_sop')
            if animateur_id in (None, ''):
                parametres.animateur_sop = None
            else:
                User = get_user_model()
                animateur = User.objects.filter(
                    company=request.user.company, pk=animateur_id).first()
                if animateur is None:
                    return Response(
                        {'animateur_sop': 'Utilisateur introuvable.'}, status=400)
                parametres.animateur_sop = animateur
        parametres.save(update_fields=['sop_actif', 'animateur_sop', 'updated_at'])

    return Response({
        'sop_actif': parametres.sop_actif,
        'animateur_sop': parametres.animateur_sop_id,
        'animateur_sop_nom': (
            parametres.animateur_sop.username if parametres.animateur_sop_id else None),
    })


# ── NTSCM33 — écran de réglages SCM par société (horizon/niveaux/seuils) ────

_PARAMETRES_SCM_FIELDS = [
    'horizon_prevision_mois_defaut', 'service_level_defaut_a_pct',
    'service_level_defaut_b_pct', 'service_level_defaut_c_pct',
    'seuil_ecart_delai_pct', 'seuil_alerte_score_fournisseur_pts',
    'seuil_alerte_ecart_financier_pct', 'retention_previsions_mois',
    # NTSCM45 — seuil d'alerte MAPE (notification ciblée écart de prévision).
    'seuil_alerte_mape_pct',
]


def _serialize_parametres_scm(parametres):
    return {field: str(getattr(parametres, field)) for field in _PARAMETRES_SCM_FIELDS}


# `request=None` : PATCH ad-hoc (sous-ensemble de `_PARAMETRES_SCM_FIELDS`),
# même motif que `parametres_sop_view` ci-dessus (PACT7).
@extend_schema(request=None, responses=inline_serializer(
    'ScmParametresResponse',
    {field: serializers.CharField() for field in _PARAMETRES_SCM_FIELDS}))
@api_view(['GET', 'PATCH'])
@permission_classes([IsResponsableOrAdmin])
def parametres_scm_view(request):
    """NTSCM33 — ``GET``/``PATCH /api/django/scm/parametres/`` : réglages SCM
    par société (horizon de prévision par défaut, niveaux de service par
    défaut par classe ABC, seuils d'alerte) — singleton créé paresseusement
    (``services.parametres_scm``). Distinct de ``scm/parametres-sop/``
    (NTSCM22, cycle S&OP automatique — reste séparé pour ne rien changer à
    son contrat existant), même modèle ``ParametresSCM``."""
    from . import services

    parametres = services.parametres_scm(request.user.company)

    if request.method == 'PATCH':
        champs_modifies = []
        for field in _PARAMETRES_SCM_FIELDS:
            if field not in request.data:
                continue
            valeur = request.data.get(field)
            if field.endswith('_mois') or field.endswith('_mois_defaut'):
                try:
                    valeur = int(valeur)
                except (TypeError, ValueError):
                    return Response({field: 'Nombre entier requis.'}, status=400)
            else:
                try:
                    valeur = Decimal(str(valeur))
                except Exception:  # noqa: BLE001 — valeur non convertible
                    return Response({field: 'Nombre requis.'}, status=400)
            setattr(parametres, field, valeur)
            champs_modifies.append(field)
        if champs_modifies:
            parametres.save(update_fields=champs_modifies + ['updated_at'])

    return Response(_serialize_parametres_scm(parametres))
