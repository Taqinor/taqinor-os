"""FG66 / DC36 — Vue du kit / nomenclature (BOM) vendable.

Un kit est un en-tête + des composants (produits du catalogue). DC36 : le kit
ne porte aucun prix / marque / TVA propre ; l'action ``exploser`` le décompose
en lignes composant avec prix/TVA/marque LUS sur chaque ``Produit`` au vol.
Multi-tenant : querysets filtrés par société + ``company`` forcée côté serveur
(TenantMixin)."""
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.mixins import TenantMixin
from authentication.permissions import (
    IsAnyRole, IsAdminRole, IsResponsableOrAdmin, HasPermissionOrLegacy,
)

from ..models import KitProduit
from ..serializers import KitProduitSerializer

READ_ACTIONS = ['list', 'retrieve', 'exploser', 'revisions',
                'composition_au']
WRITE_ACTIONS = ['create', 'update', 'partial_update', 'dupliquer']


class KitProduitViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = KitProduit.objects.all().prefetch_related('composants__produit')
    serializer_class = KitProduitSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'sku', 'description']
    ordering = ['nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            # XMFG18 — `revisions` / `composition-au` sont LECTURE SEULE
            # (composition sans aucun prix), même garde que `exploser`.
            return [IsAnyRole()]
        elif self.action == 'structure':
            # XMFG5 — l'écran est accessible à tout rôle (disponibilité), le
            # coût/marge sont retirés de la réponse pour les rôles sans
            # accès responsable/admin (jamais client-facing).
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            # XMFG18 — `dupliquer` EST une écriture (crée un kit) : même
            # garde que create/update.
            return [HasPermissionOrLegacy('stock_modifier')()]
        return [IsAdminRole()]

    @action(detail=True, methods=['get'], url_path='exploser')
    def exploser(self, request, *args, **kwargs):
        """Explose le kit en lignes composant (param ``quantite`` ≥ 1, défaut 1).
        XMFG17 — traverse récursivement les sous-kits ; un cycle ou une
        profondeur excessive renvoie un 400 clair plutôt qu'une RecursionError.
        Prix / TVA / marque dérivés des produits (DC36). Le prix d'achat n'est
        jamais exposé."""
        from ..services import exploser_kit, KitCycleError
        kit = self.get_object()
        try:
            quantite = float(request.query_params.get('quantite', 1) or 1)
        except (TypeError, ValueError):
            quantite = 1
        if quantite <= 0:
            quantite = 1
        try:
            lignes = exploser_kit(kit, quantite)
        except (KitCycleError, ValueError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'kit_id': kit.id,
            'kit_nom': kit.nom,
            'quantite_kit': quantite,
            'lignes': lignes,
        })

    @action(detail=True, methods=['get'], url_path='structure')
    def structure(self, request, *args, **kwargs):
        """XMFG5 — nomenclature indentée + disponibilité + kits assemblables.
        XMFG17 — traverse récursivement les sous-kits (chaque ligne porte
        `niveau`) ; un cycle ou une profondeur excessive renvoie un 400 clair.
        Coût/marge RÉSERVÉS responsable/admin — retirés de la réponse pour
        les autres rôles (jamais client-facing)."""
        from ..services import structure_kit, KitCycleError
        kit = self.get_object()
        try:
            data = structure_kit(kit)
        except (KitCycleError, ValueError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        peut_voir_cout = IsResponsableOrAdmin().has_permission(request, self)
        if not peut_voir_cout:
            for ligne in data['composants']:
                ligne.pop('cout_unitaire', None)
                ligne.pop('cout_total', None)
            data.pop('cout_total_roll_up', None)
            data.pop('marge', None)
        else:
            # Le contrat d'API expose ces montants roll-up en CHAÎNE à 2
            # décimales ('9500.00') ; un Decimal brut serait rendu en nombre
            # JSON (9500.0). On les formate explicitement à la frontière vue.
            for _cle in ('cout_total_roll_up', 'marge'):
                if data.get(_cle) is not None:
                    data[_cle] = f'{data[_cle]:.2f}'
        return Response(data)

    @action(detail=True, methods=['get'], url_path='revisions')
    def revisions(self, request, *args, **kwargs):
        """XMFG18 — historique des révisions de nomenclature de ce kit
        (numéro, date, utilisateur, snapshot JSON — sans aucun prix).
        Lecture seule."""
        from ..serializers import RevisionKitSerializer
        kit = self.get_object()
        qs = kit.revisions.select_related('user').order_by('-numero')
        return Response(RevisionKitSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'], url_path='composition-au')
    def composition_au(self, request, *args, **kwargs):
        """XMFG18 — « composition au JJ/MM/AAAA » : renvoie la révision en
        vigueur à la date donnée (`?date=JJ/MM/AAAA` ou `AAAA-MM-JJ`).
        404 si aucune révision n'existait encore à cette date."""
        from datetime import datetime
        from ..serializers import RevisionKitSerializer
        kit = self.get_object()
        brut = (request.query_params.get('date') or '').strip()
        date_limite = None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
            try:
                date_limite = datetime.strptime(brut, fmt).date()
                break
            except ValueError:
                continue
        if date_limite is None:
            return Response(
                {'detail': 'Paramètre date requis (JJ/MM/AAAA ou '
                           'AAAA-MM-JJ).'},
                status=status.HTTP_400_BAD_REQUEST)
        from ..services import composition_kit_au
        revision = composition_kit_au(kit, date_limite)
        if revision is None:
            return Response(
                {'detail': 'Aucune révision à cette date.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response(RevisionKitSerializer(revision).data)

    @action(detail=True, methods=['post'], url_path='dupliquer')
    def dupliquer(self, request, *args, **kwargs):
        """XMFG18 — duplique ce kit (en-tête + composants), avec facteur
        d'échelle optionnel sur les quantités (`facteur_echelle`, ex. 1.67 —
        arrondi propre). La copie reçoit sa révision n°1."""
        from ..services import dupliquer_kit
        kit = self.get_object()
        facteur = request.data.get('facteur_echelle')
        try:
            copie = dupliquer_kit(
                kit, user=request.user, facteur_echelle=facteur)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(copie).data, status=status.HTTP_201_CREATED)
