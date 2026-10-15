"""ENF11 (api-fuzz « rejected schema-compliant request ») — une RÈGLE MÉTIER n'est
pas un défaut de forme : 409, jamais 400.

Un réglage de Paramètres porte des règles que le schéma OpenAPI n'exprime pas :
une source obligatoire dès qu'un taux est saisi (``indexation_source``), un
échéancier qui totalise 100 %, un ICE de 15 chiffres après normalisation, un
mode de commission qui exige sa valeur, un champ JSON libre (``{}`` au schéma)
dont le contenu doit avoir une forme. Le corps était CONFORME au schéma : c'est la
règle qui s'oppose à l'écriture — le même statut 409 que les autres refus d'état
(``core.conflit_etat``).

Le marquage est le CODE d'erreur DRF : une règle métier lève une
``ValidationError`` de code ``regle_metier`` (décorateur :func:`regle_metier` sur
un ``validate_<champ>`` / ``validate``). Les tests unitaires de sérialiseur voient
donc toujours ``is_valid() == False`` ; la vue appelle :func:`valider_ou_conflit` :
409 quand TOUTES les erreurs sont des règles métier, 400 dès qu'un défaut de forme
(type, longueur, énumération, borne publiée) s'y mêle.
"""
import functools

from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from core.conflit_etat import ConflitEtat

CODE_REGLE_METIER = 'regle_metier'


def _marquer(detail):
    """``detail`` (texte, liste ou dict d'une ``ValidationError``) dont chaque
    feuille porte le code ``regle_metier``."""
    if isinstance(detail, dict):
        return {cle: _marquer(valeur) for cle, valeur in detail.items()}
    if isinstance(detail, (list, tuple)):
        return [_marquer(valeur) for valeur in detail]
    return ErrorDetail(str(detail), code=CODE_REGLE_METIER)


def refus_metier(detail):
    """``ValidationError`` de règle métier — ``detail`` : texte, liste ou
    ``{champ: message}``."""
    return serializers.ValidationError(_marquer(detail))


def regle_metier(fonction):
    """Décorateur d'un ``validate_<champ>`` ou ``validate`` : tout refus qu'il
    lève est une règle métier (code ``regle_metier``)."""
    @functools.wraps(fonction)
    def enveloppe(self, *args, **kwargs):
        try:
            return fonction(self, *args, **kwargs)
        except serializers.ValidationError as exc:
            raise refus_metier(exc.detail) from None
    return enveloppe


def _feuilles(erreurs):
    if isinstance(erreurs, dict):
        for valeur in erreurs.values():
            yield from _feuilles(valeur)
    elif isinstance(erreurs, (list, tuple)):
        for valeur in erreurs:
            yield from _feuilles(valeur)
    else:
        yield erreurs


def que_des_regles_metier(erreurs):
    """Vrai si ``erreurs`` (``serializer.errors``) n'est faite QUE de règles
    métier."""
    feuilles = list(_feuilles(erreurs))
    return bool(feuilles) and all(
        getattr(f, 'code', None) == CODE_REGLE_METIER for f in feuilles)


def message_de_conflit(erreurs):
    """Texte du 409 : chaque refus, précédé du NOM du champ quand le message ne
    le porte pas déjà (l'écran n'a plus l'erreur par champ du 400)."""
    if not isinstance(erreurs, dict):
        return ' '.join(str(f) for f in _feuilles(erreurs))
    morceaux = []
    for champ, valeur in erreurs.items():
        for feuille in _feuilles(valeur):
            texte = str(feuille)
            morceaux.append(texte if champ in texte else f'{champ} : {texte}')
    return ' '.join(morceaux)


def valider_ou_conflit(serializer):
    """``serializer.is_valid(raise_exception=True)`` où un refus fait UNIQUEMENT
    de règles métier répond 409 (message = les refus, un par champ nommé), pas
    400."""
    if serializer.is_valid():
        return
    erreurs = serializer.errors
    if que_des_regles_metier(erreurs):
        raise ConflitEtat(message_de_conflit(erreurs))
    raise serializers.ValidationError(erreurs)
