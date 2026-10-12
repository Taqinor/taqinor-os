"""ENF11 — validation STRICTE d'un corps de requête par son sérialiseur déclaré.

Les actions de devis / facture lisaient ``request.data.get(...)`` à la main :
un corps non objet levait une 500, un champ de mauvais type était coercé en
silence. ``valider_corps`` rejoue le sérialiseur DÉCLARÉ dans le schéma
(``views/openapi_docs.py``) et répond 400 ; le reste du code de la vue est
inchangé (les clés inconnues restent ignorées).
"""


def valider_corps(request, declare):
    """Lève ``ValidationError`` (400) si ``request.data`` viole ``declare``."""
    serializer = type(declare)(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _premier_message(erreurs):
    """Premier message lisible d'une erreur DRF (liste, dict ou chaîne)."""
    if isinstance(erreurs, dict):
        champ, sous = next(iter(erreurs.items()))
        return f'{champ} — {_premier_message(sous)}'
    if isinstance(erreurs, list) and erreurs:
        return _premier_message(erreurs[0])
    return str(erreurs)


def valider_corps_lignes(request, declare, cle='lignes'):
    """``valider_corps`` dont un refus porté par UNE ligne de ``cle`` est
    rendu au format des refus ligne à ligne des vues : 400
    ``{"detail": "Ligne <n> : <champ> — <message>", "code": "ligne_invalide"}``.
    Toute autre erreur (corps non objet, ``mode``/``type`` hors liste…) reste
    l'erreur du sérialiseur déclaré."""
    from rest_framework.exceptions import ValidationError

    try:
        return valider_corps(request, declare)
    except ValidationError as exc:
        # ``ListField`` rend les erreurs de ses éléments en dict {rang: …} ;
        # une liste ici = ``lignes`` elle-même invalide (pas une liste).
        par_ligne = exc.detail.get(cle) if isinstance(exc.detail, dict) else None
        if not isinstance(par_ligne, dict):
            raise
        fautives = sorted(i for i, e in par_ligne.items()
                          if isinstance(i, int) and e)
        if not fautives:
            raise
        rang = fautives[0]
        raise ValidationError({
            'detail': f'Ligne {rang + 1} : '
                      f'{_premier_message(par_ligne[rang])}',
            'code': 'ligne_invalide'})
