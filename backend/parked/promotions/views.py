from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from . import services
from .models import ReglexPromotion
from .serializers import ReglexPromotionSerializer


class ReglexPromotionViewSet(CompanyScopedModelViewSet):
    """NTRET12 — Règles de promotion panier. Lecture tout rôle (l'écran
    caisse doit connaître les règles actives), écriture responsable/admin."""
    queryset = ReglexPromotion.objects.all()
    serializer_class = ReglexPromotionSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'simuler'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=False, methods=['post'], url_path='simuler')
    def simuler(self, request):
        """Simule les promotions applicables à un panier SANS créer de
        vente — utile pour l'écran caisse (aperçu avant validation) et pour
        les tests d'intégration. ``lignes`` = liste de
        ``{produit_id, categorie_id, quantite, prix_unitaire_ttc}``."""
        from decimal import Decimal

        from . import engine

        lignes_in = request.data.get('lignes') or []
        try:
            lignes = [
                engine.LignePanier(
                    produit_id=ligne.get('produit_id'),
                    categorie_id=ligne.get('categorie_id'),
                    quantite=Decimal(str(ligne.get('quantite') or 0)),
                    prix_unitaire_ttc=Decimal(str(ligne.get('prix_unitaire_ttc') or 0)),
                )
                for ligne in lignes_in
            ]
        except (TypeError, ValueError):
            raise ValidationError({'lignes': 'Lignes de panier invalides.'})

        regles = services._regles_actives(request.user.company)
        remises = engine.evaluer_promotions(lignes, regles)
        return Response({
            'remises': [
                {'regle_id': r.regle_id, 'libelle': r.libelle, 'montant': str(r.montant)}
                for r in remises
            ],
            'total_remise': str(sum((r.montant for r in remises), Decimal('0'))),
        })
