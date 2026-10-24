"""ENF11 (api-fuzz-full) — champs de corps SAV qui n'atteignent plus PostgreSQL
avec une valeur qu'il refuse (500).

Le décodage JSON laisse passer une moitié de paire de substitution isolée
(un substitut isolé) : psycopg ne sait pas l'encoder en UTF-8 -> 500. Elle est
retirée avant toute validation (le schéma publié reste ``type: string``).
"""
import re
from decimal import Decimal

from rest_framework import serializers

from core.champs_stricts import ChaineStricte

_SUBSTITUTS_SEULS = re.compile(r'[\ud800-\udfff]')


def sans_substituts(valeur):
    """``valeur`` (chaîne, liste, objet JSON) sans substitut isolé, clés comprises."""
    if isinstance(valeur, str):
        return _SUBSTITUTS_SEULS.sub('', valeur)
    if isinstance(valeur, list):
        return [sans_substituts(v) for v in valeur]
    if isinstance(valeur, dict):
        return {sans_substituts(k): sans_substituts(v)
                for k, v in valeur.items()}
    return valeur


class TexteSansSubstitut(ChaineStricte):
    """``ChaineStricte`` dont les substituts isolés sont retirés d'abord."""

    def to_internal_value(self, data):
        return super().to_internal_value(sans_substituts(data))


#: Décimal STRICTEMENT positif, 10 entiers + 2 décimales au plus, écrit sans
#: signe ni zéros de tête : ``"0"``/``"-1"`` ne sont plus « conformes » puis
#: refusés « Quantité invalide ». Plus étroit que le serveur (qui lit aussi
#: ``"007"``) : le schéma n'annonce jamais une valeur que le serveur refuse.
MOTIF_QUANTITE_POSITIVE = (
    r'^(?:[1-9][0-9]{0,9}(?:\.[0-9]{0,2})?|0?\.(?:0[1-9]|[1-9][0-9]?))$')


class QuantitePositive(serializers.DecimalField):
    """Quantité de pièces (``numeric(12,2)``) > 0, publiée avec son motif exact."""

    def __init__(self, **kwargs):
        from drf_spectacular.drainage import set_override

        super().__init__(
            max_digits=12, decimal_places=2, min_value=Decimal('0.01'),
            **kwargs)
        set_override(self, 'field', {
            'type': 'string', 'format': 'decimal',
            'pattern': MOTIF_QUANTITE_POSITIVE})
