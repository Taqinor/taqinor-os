"""XFAC9 — Conversion d'un montant en lettres (Français), pour la quittance
(reçu de paiement) PDF marocaine.

Implémentation MAISON en Python pur (aucune nouvelle dépendance) : couvre les
montants usuels d'une facture (jusqu'aux milliards), avec les règles
françaises « vingt/cent » qui prennent un 's' sauf suivis d'un autre nombre,
et « un » invariable devant « mille ». MAD (dirhams/centimes).
"""
from decimal import Decimal, ROUND_HALF_UP

_UNITES = [
    '', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf',
    'dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize',
    'dix-sept', 'dix-huit', 'dix-neuf',
]
_DIZAINES = [
    '', '', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante',
    'soixante', 'quatre-vingt', 'quatre-vingt',
]


def _moins_de_cent(n):
    if n < 20:
        return _UNITES[n]
    dizaine, reste = divmod(n, 10)
    if dizaine in (7, 9):
        # soixante-dix / quatre-vingt-dix : dizaine réelle -1, reste +10.
        dizaine -= 1
        reste += 10
    mot = _DIZAINES[dizaine]
    if reste == 0:
        # "quatre-vingts" prend un s, "vingt"/"trente"... seuls ne le prennent
        # pas ; "quatre-vingt" en est la seule exception avec un s au pluriel.
        if dizaine == 8:
            return mot + 's'
        return mot
    liaison = '-et-' if reste == 1 and dizaine not in (8,) else '-'
    return f'{mot}{liaison}{_UNITES[reste]}'


def _moins_de_mille(n):
    centaine, reste = divmod(n, 100)
    parts = []
    if centaine > 0:
        if centaine == 1:
            parts.append('cent')
        else:
            suffixe_cent = 's' if reste == 0 else ''
            parts.append(f'{_UNITES[centaine]}-cent{suffixe_cent}')
    if reste > 0:
        parts.append(_moins_de_cent(reste))
    return '-'.join(parts) if parts else 'zéro'


_TRANCHES = [
    (1_000_000_000, 'milliard'),
    (1_000_000, 'million'),
    (1_000, 'mille'),
]


def _entier_en_lettres(n):
    if n == 0:
        return 'zéro'
    parts = []
    reste = n
    for valeur, mot in _TRANCHES:
        if reste >= valeur:
            quotient, reste = divmod(reste, valeur)
            if valeur == 1_000:
                # "mille" est invariable et "un mille" ne s'écrit pas "un".
                prefix = '' if quotient == 1 else f'{_moins_de_mille(quotient)}-'
                parts.append(f'{prefix}{mot}')
            else:
                prefix = _moins_de_mille(quotient)
                suffixe = 's' if quotient > 1 else ''
                parts.append(f'{prefix}-{mot}{suffixe}')
    if reste > 0:
        parts.append(_moins_de_mille(reste))
    return '-'.join(parts)


def montant_en_lettres(montant, devise='dirhams', sous_unite='centimes'):
    """Montant Decimal/float/str → chaîne française pleine lettre + devise.

    Ex. ``Decimal('1250.50')`` → « mille-deux-cent-cinquante dirhams et
    cinquante centimes ». Toujours positif (une facture/quittance ne porte
    jamais de montant négatif en lettres) ; arrondi au centime le plus proche.
    """
    montant = Decimal(str(montant)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant = abs(montant)
    entier = int(montant)
    centimes = int((montant - entier) * 100)

    texte = f'{_entier_en_lettres(entier)} {devise}'
    if centimes:
        texte += f' et {_entier_en_lettres(centimes)} {sous_unite}'
    return texte[0].upper() + texte[1:]
