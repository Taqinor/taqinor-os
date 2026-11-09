"""ENF11 (api-fuzz-full) — champs de corps SAV qui n'atteignent plus PostgreSQL
avec une valeur qu'il refuse (500).

Le décodage JSON laisse passer une moitié de paire de substitution isolée
(un substitut isolé) : psycopg ne sait pas l'encoder en UTF-8 -> 500. Elle est
retirée avant toute validation (le schéma publié reste ``type: string``).
"""
import re
from contextlib import contextmanager
from decimal import Decimal

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.champs_stricts import ChaineStricte
from core.conflit_etat import ConflitEtat
from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE

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


#: 3e drainage api-fuzz 24/10 — ``pieces-retirees`` : une pièce en ``recyclage``
#: n'a qu'une destination, ``stock_occasion`` (``services.retirer_piece``, 400
#: sinon — y compris SANS ``destination``, qui retombe sur ``rebut``). Règle
#: ENTRE deux champs, donc publiée en ``anyOf`` : retrait (ou opération absente)
#: OU recyclage avec sa destination.
CORPS_PIECE_RETIREE = {EXTENSION_CORPS_RESSERRE: {'anyOf': [
    {'properties': {'operation': {'enum': ['retrait']}}},
    {'required': ['operation', 'destination'],
     'properties': {'operation': {'enum': ['recyclage']},
                    'destination': {'enum': ['stock_occasion']}}},
]}}

#: Décimal STRICTEMENT positif, 8 entiers + 2 décimales au plus (colonnes
#: ``numeric(10,2)`` de ``PieceRetiree``/``PieceConsommee`` : 9 entiers ou plus
#: débordaient en 500), écrit sans signe ni zéros de tête : ``"0"``/``"-1"``
#: ne sont plus « conformes » puis refusés « Quantité invalide ». Plus étroit
#: que le serveur (qui lit aussi ``"007"``) : le schéma n'annonce jamais une
#: valeur que le serveur refuse.
MOTIF_QUANTITE_POSITIVE = (
    r'^(?:[1-9][0-9]{0,7}(?:\.[0-9]{0,2})?|0?\.(?:0[1-9]|[1-9][0-9]?))$')


class QuantitePositive(serializers.DecimalField):
    """Quantité de pièces (``numeric(10,2)``) > 0, publiée avec son motif exact."""

    def __init__(self, **kwargs):
        from drf_spectacular.drainage import set_override

        super().__init__(
            max_digits=10, decimal_places=2, min_value=Decimal('0.01'),
            **kwargs)
        set_override(self, 'field', {
            'type': 'string', 'format': 'decimal',
            'pattern': MOTIF_QUANTITE_POSITIVE})


def erreurs_nombres_lignes(lignes, erreurs):
    """ASEC80 — ajoute à ``erreurs`` (``{i: {champ: [msg]}}``) chaque
    ``quantite`` (décimal fini > 0) et ``prix_unitaire`` (décimal fini ≥ 0)
    invalide des lignes de ``creer-devis``, AVANT le domaine ventes ; rend
    ``erreurs``. Un champ absent garde le défaut du domaine (1 / 0)."""
    from decimal import InvalidOperation

    for i, ligne in enumerate(lignes):
        if not isinstance(ligne, dict):
            continue
        for champ, strict, message in (
                ('quantite', True, 'Quantité strictement positive attendue.'),
                ('prix_unitaire', False, 'Prix positif ou nul attendu.')):
            brut = ligne.get(champ)
            if brut in (None, ''):
                continue
            try:
                v = Decimal(str(brut))
            except (InvalidOperation, ValueError, TypeError):
                v = None
            if v is None or not v.is_finite() or v < 0 or (strict and v == 0):
                erreurs.setdefault(i, {})[champ] = [message]
    return erreurs


@contextmanager
def refus_stock_en_conflit():
    """Le service stock refuse la quantité (fractionnaire sur un stock en
    unités entières) par un ``ValidationError`` : le corps était conforme au
    schéma, c'est l'ÉTAT du stock qui s'oppose -> 409 (``ConflitEtat``)."""
    try:
        yield
    except ValidationError as exc:
        raise ConflitEtat(exc.detail)
