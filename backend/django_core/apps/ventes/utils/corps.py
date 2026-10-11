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
