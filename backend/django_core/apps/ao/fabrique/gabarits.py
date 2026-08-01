"""AOF116 — moteur de gabarits : rendu par placeholders, ZÉRO chiffre en dur.

Deux fonctions et une règle.

Le RENDU délègue entièrement à ``core.templating.rendre`` (fondation FG393,
déjà en production) : substitution purement littérale de ``{{ variable }}``,
aucun ``eval``, aucun moteur de template arbitraire. On ne recode donc aucun
mécanisme de rendu.

La RÈGLE est la raison d'être du module : **un gabarit ne contient AUCUN
littéral chiffré**. Un nombre écrit à la main dans un corps de texte est un
vestige qui SURVIT à la prochaine cascade de prix — c'est exactement le défaut
réel de la session : le montant final avait bien été cascadé partout, mais sa
parenthèse de justification citait toujours l'ancien prix au kWh. Un chiffre
n'a le droit d'exister que comme ``{{ placeholder }}`` résolu depuis le
contexte calculé.

Exceptions NOMMÉES (et seulement celles-là) : les références normatives et
réglementaires, qui SONT des chiffres mais ne sont pas des grandeurs du
dossier — une norme ne bouge pas quand le prix du kWh bouge.
"""
from __future__ import annotations

import re

from core.templating import rendre, rendre_html, variables_utilisees

__all__ = [
    'EXCEPTIONS_NORMATIVES',
    'LitteralChiffreRefuse',
    'literaux_chiffres',
    'rendre_gabarit',
    'rendre_gabarit_html',
    'valider_gabarit',
    'variables_du_gabarit',
]

#: Placeholders ``{{ … }}`` — masqués AVANT la recherche de chiffres : un
#: nombre PORTÉ par le contexte est précisément ce qu'on veut.
_PLACEHOLDER = re.compile(r'\{\{\s*[a-zA-Z_][a-zA-Z0-9_.]*\s*\}\}')

#: Références normatives et réglementaires TOLÉRÉES (liste FERMÉE, motivée).
#: Une norme, un article de décret ou une loi ne sont pas des grandeurs du
#: dossier : ils ne changent pas quand un prix ou un calepinage change.
EXCEPTIONS_NORMATIVES = (
    # Normes électriques et produit : NF C 15-100, NM 06.9.001, IEC 61215…
    re.compile(r'\b(?:NF|NM|EN|IEC|CEI|ISO|UTE|DTU)\s?[A-Z]?\s?[\d][\d\-.]*',
               re.IGNORECASE),
    # Textes marocains : loi 13-09, décret 2-12-349, dahir 1-14-05, arrêté…
    re.compile(r'\b(?:loi|d[ée]cret|dahir|arr[êe]t[ée]|circulaire)\s+n?°?\s*'
               r'[\d][\d\-.]*', re.IGNORECASE),
    # Renvois internes au texte : article 12, annexe 3, chapitre 4.
    re.compile(r'\b(?:article|annexe|chapitre|alin[ée]a)\s+[\d][\d.]*',
               re.IGNORECASE),
)


class LitteralChiffreRefuse(ValueError):
    """Levée par :func:`valider_gabarit` — message FR citant les littéraux."""


def _masquer(texte):
    """Remplace placeholders et exceptions normatives par des blancs.

    Le masquage préserve la LONGUEUR pour que les positions signalées à
    l'utilisateur restent celles du texte d'origine.
    """
    masque = _PLACEHOLDER.sub(lambda m: ' ' * len(m.group(0)), texte or '')
    for motif in EXCEPTIONS_NORMATIVES:
        masque = motif.sub(lambda m: ' ' * len(m.group(0)), masque)
    return masque


def literaux_chiffres(texte):
    """Les littéraux chiffrés d'un gabarit : ``[(position, littéral), …]``.

    Liste vide = gabarit propre. Un chiffre porté par un ``{{ placeholder }}``
    ou par une référence normative n'est JAMAIS retourné.
    """
    masque = _masquer(texte)
    return [(m.start(), m.group(0))
            for m in re.finditer(r'\d+(?:[  ,.]\d+)*', masque)]


def valider_gabarit(texte, *, origine=''):
    """Refuse un gabarit portant un littéral chiffré (AOF116).

    Args:
        texte: le corps du gabarit.
        origine: nom lisible de la pièce/section, cité dans le message.

    Raises:
        LitteralChiffreRefuse: message français listant chaque littéral et sa
            position — c'est ce que l'auteur du gabarit doit lire, pas un code.
    """
    trouves = literaux_chiffres(texte)
    if not trouves:
        return True
    details = ', '.join(
        f'« {litteral} » (position {position})'
        for position, litteral in trouves[:10])
    cible = f' dans « {origine} »' if origine else ''
    raise LitteralChiffreRefuse(
        f'Gabarit refusé{cible} : {len(trouves)} littéral(aux) chiffré(s) '
        f'écrit(s) en dur — {details}. Un chiffre ne peut exister que comme '
        f'placeholder {{{{ … }}}} résolu depuis le contexte calculé : un nombre '
        f'écrit à la main survit à la prochaine cascade de prix.'
    )


def variables_du_gabarit(texte):
    """Placeholders utilisés par le gabarit (ordre d'apparition, dédupliqué)."""
    return variables_utilisees(texte)


def rendre_gabarit(texte, contexte=None, *, strict=False, valider=True):
    """Rend un gabarit texte via ``core.templating.rendre``.

    ``valider=True`` (défaut) refuse d'abord tout littéral chiffré : on ne rend
    jamais un gabarit qu'on sait vestigial.
    """
    if valider:
        valider_gabarit(texte)
    return rendre(texte, contexte, strict=strict)


def rendre_gabarit_html(texte, contexte=None, *, strict=False, valider=True):
    """Comme :func:`rendre_gabarit`, valeurs ÉCHAPPÉES (corps HTML → PDF)."""
    if valider:
        valider_gabarit(texte)
    return rendre_html(texte, contexte, strict=strict)
