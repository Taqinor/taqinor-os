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


def _type_ok(valeur, attendu):
    """Type JSON d'un schéma OpenAPI 3.0 (un booléen n'est jamais un nombre ;
    ``2.0`` compte pour un entier, comme le validateur du schéma)."""
    if attendu == 'object':
        return isinstance(valeur, dict)
    if attendu == 'string':
        return isinstance(valeur, str)
    if attendu == 'boolean':
        return isinstance(valeur, bool)
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return False
    if valeur != valeur or valeur in (float('inf'), float('-inf')):
        return False
    return attendu == 'number' or float(valeur).is_integer()


def _erreur_valeur(valeur, schema):
    """Message du premier écart de ``valeur`` à ``schema`` (sous-ensemble
    publié : type, nullable, enum, minimum/maximum/exclusiveMinimum,
    properties), ``None`` si conforme."""
    if valeur is None:
        return None if schema.get('nullable') else 'Valeur nulle refusée.'
    attendu = schema.get('type')
    if attendu and not _type_ok(valeur, attendu):
        return f'Type attendu : {attendu}.'
    if 'enum' in schema and valeur not in schema['enum']:
        return 'Valeurs acceptées : ' + ', '.join(
            repr(v) for v in schema['enum']) + '.'
    mini, maxi = schema.get('minimum'), schema.get('maximum')
    if mini is not None and (valeur < mini or (
            schema.get('exclusiveMinimum') and valeur == mini)):
        return 'Valeur hors plage.'
    if maxi is not None and valeur > maxi:
        return 'Valeur hors plage.'
    for nom, sous in (schema.get('properties') or {}).items():
        if isinstance(valeur, dict) and nom in valeur:
            erreur = _erreur_valeur(valeur[nom], sous)
            if erreur:
                return f'{nom} — {erreur}'
    return None


def valider_corps_schema(request, schema):
    """CI #997 fuzz — corps validé par le schéma JSON PUBLIÉ lui-même (corps
    déclaré en dict, ``{'application/json': {...}}``) : UN prédicat, lu au
    même endroit que la documentation. Lève ``ValidationError`` (400) nommant
    le champ ; rend le corps (dict) sinon."""
    from rest_framework.exceptions import ValidationError

    regle = schema['application/json']
    donnees = request.data
    if not isinstance(donnees, dict):
        raise ValidationError({'detail': 'Corps JSON objet attendu.'})
    for nom, sous in (regle.get('properties') or {}).items():
        if nom in donnees:
            erreur = _erreur_valeur(donnees[nom], sous)
            if erreur:
                raise ValidationError({nom: [erreur]})
    branches = regle.get('anyOf')
    if branches and not any(
            all(cle in donnees for cle in b.get('required', ()))
            for b in branches):
        raise ValidationError({'detail': regle.get(
            'description', 'Corps incomplet.')})
    return donnees
