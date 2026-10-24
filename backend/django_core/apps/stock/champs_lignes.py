"""Champs déclarés d'une ligne de facture fournisseur (extraits de ``serializers.py``, C20)."""
import re
from decimal import Decimal

from rest_framework import serializers

from core.champs_stricts import DecimalBornee
from core.conflit_etat import ConflitEtat

#: api-fuzz-full 24/10 — ``total_ht`` d'une ligne est SERVI en
#: ``DecimalField(max_digits=14, decimal_places=2)`` alors que quantité et prix
#: valent chacun jusqu'à 10 chiffres entiers : leur produit levait
#: ``InvalidOperation`` à la lecture de la facture DÉJÀ commitée (500).
PLAFOND_TOTAL_LIGNE = Decimal('999999999999.995')


class TauxTvaLigne(DecimalBornee):
    r"""ENF11 nocturne - ``lignes[].taux_tva`` : chaine au motif EXACT publie
    (``\d{1,3}`` entiers ASCII, <= 2 decimales), 0..100. ``DecimalField``
    de DRF lit aussi `` 5 ``, ``1e1`` ou des chiffres non ASCII, que le schema
    declare invalides : on applique le motif avant la conversion."""

    _MOTIF = re.compile(r'(?:\d{1,3}(?:\.\d{0,2})?|\.\d{1,2})', re.ASCII)

    def to_internal_value(self, data):
        if not isinstance(data, str) or not self._MOTIF.fullmatch(data):
            self.fail('invalid')
        return super().to_internal_value(data)


class ChampsLigneFactureFournisseur(serializers.Serializer):
    """Champs declares de ``LigneFactureFournisseurSerializer`` (lecture
    seule + ``taux_tva`` strict)."""

    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None, allow_null=True)
    total_ht = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    # XPUR17 — TVA par ligne (taux marocains). total_tva = 0 si taux_tva vide
    # (ligne historique, suit le taux global agrégé de la facture).
    total_tva = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    taux_tva = TauxTvaLigne(
        max_digits=5, decimal_places=2, min_value=Decimal('0'),
        max_value=Decimal('100'), required=False, allow_null=True)

    def validate(self, attrs):
        """Un montant de ligne que la réponse ne peut pas servir est un refus
        d'état de la capacité du document (409, même corps par champ), comme
        les lignes de facture client (``ventes.serializers_facturation``)."""
        attrs = super().validate(attrs)

        def _valeur(nom, defaut):
            valeur = attrs.get(nom, getattr(self.instance, nom, None))
            return defaut if valeur is None else valeur

        total = _valeur('quantite', Decimal('1')) * _valeur('prix_unitaire_ht', Decimal('0'))
        if abs(total) >= PLAFOND_TOTAL_LIGNE:
            raise ConflitEtat({'quantite': [
                'Montant de ligne trop élevé : la quantité multipliée par le '
                'prix unitaire dépasse 999 999 999 999,99.']})
        return attrs
