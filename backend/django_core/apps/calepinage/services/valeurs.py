"""ACAL277 — LA règle « nombre fini borné » du module, écrite UNE fois.

Constat C-ACAL-142 (audit 2026-10-04) : ``float('nan')``, ``float('inf')``
et ``float('1e400')`` passent un ``float(valeur)`` nu. Un relevé, un champ de
dossier, un montant de « Générer le devis » ou un nom de variante du mauvais
type finissait donc en 500 (``ValueError`` / ``OverflowError`` /
``DataError`` d'un JSONField NaN) au lieu d'un refus 400 qui NOMME le champ.

Chaque service garde SON exception métier (le refus reste nommé dans le
vocabulaire de sa vue) : il passe sa classe en ``erreur=``. Aucune valeur
n'est jamais devinée ni rabotée — hors bornes ⇒ refus, jamais un écrêtage.
"""
from __future__ import annotations

import math

__all__ = ['ValeurRefusee', 'nombre', 'nombre_fini']


class ValeurRefusee(ValueError):
    """Refus par défaut : message français, champ nommé."""

    def __init__(self, message, champ=''):
        super().__init__(message)
        self.champ = champ


def nombre_fini(valeur, champ, *, libelle='', mini=None, maxi=None,
                mini_exclu=False, decimales=None, obligatoire=False,
                erreur=ValeurRefusee):
    """``valeur`` lue comme un réel FINI dans ses bornes, ou un refus nommé.

    Args:
        valeur: la saisie brute (nombre ou texte numérique ; un booléen
            n'est jamais un nombre).
        champ: le champ à NOMMER dans le refus.
        libelle: le nom lisible du champ (défaut : ``champ``).
        mini / maxi: bornes INCLUSES (``mini_exclu`` : strictement > mini).
        decimales: nombre maximal de décimales admises (``None`` : libre).
        obligatoire: ``True`` refuse une valeur absente ; sinon ``None``.
        erreur: la classe d'exception métier levée, appelée
            ``erreur(message, champ=champ)``.

    Returns:
        Le ``float`` lu, ou ``None`` pour une valeur absente non obligatoire.
    """
    nom = libelle or champ
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        if obligatoire:
            raise erreur(f'« {nom} » est obligatoire.', champ=champ)
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float, str)):
        raise erreur(f'« {nom} » doit être un nombre '
                     f'(reçu : {valeur!r}).', champ=champ)
    try:
        nombre = float(valeur)
    except (TypeError, ValueError, OverflowError):
        raise erreur(f'« {nom} » doit être un nombre '
                     f'(reçu : {valeur!r}).', champ=champ)
    if not math.isfinite(nombre):
        raise erreur(f'« {nom} » doit être un nombre fini '
                     f'(reçu : {valeur!r}).', champ=champ)
    if mini is not None and (nombre <= mini if mini_exclu else nombre < mini):
        signe = '>' if mini_exclu else '≥'
        raise erreur(f'« {nom} » doit être {signe} {mini:g} '
                     f'(reçu : {nombre:g}).', champ=champ)
    if maxi is not None and nombre > maxi:
        raise erreur(f'« {nom} » doit être ≤ {maxi:g} '
                     f'(reçu : {nombre:g}).', champ=champ)
    if decimales is not None and round(nombre, decimales) != nombre:
        raise erreur(f'« {nom} » admet au plus {decimales} décimale(s) '
                     f'(reçu : {valeur!r}).', champ=champ)
    return nombre


def nombre(valeur):
    """ACAL323 — LA lecture tolérante d'un nombre du module : ``float`` FINI
    ou ``None``, jamais un refus.

    Un booléen n'est JAMAIS un nombre (``True`` n'est pas ``1.0``) ; ``nan`` et
    ``±inf`` valent ``None`` (une valeur illisible est une valeur NON
    RENSEIGNÉE, jamais une valeur corrigée) ; une chaîne numérique est lue
    (``' 4 '`` → ``4.0``) ; tout le reste vaut ``None``. Survivant UNIQUE des
    copies privées ``_nombre(valeur)`` / ``_flottant(valeur)`` du module
    (garde AST ``tests/test_acal_nombre_unique.py``). Pour REFUSER en nommant
    le champ, c'est :func:`nombre_fini`.
    """
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        lu = float(valeur)
    except (TypeError, ValueError, OverflowError):
        return None
    return lu if math.isfinite(lu) else None
