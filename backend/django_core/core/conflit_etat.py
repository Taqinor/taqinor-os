"""ENF11 — refus qui dépend de l'ÉTAT des données : 409, jamais un 400.

Le corps de la requête était conforme au schéma ; c'est la situation (facture
déjà émise, document figé…) qui s'oppose à l'écriture. ``ConflitEtat`` est
levable depuis une vue ou un ``perform_*`` (là où un ``ValidationError`` ferait
répondre 400) ; l'enveloppe d'erreur commune le rend en ``{"detail": …}``.
"""
from rest_framework import status
from rest_framework.exceptions import APIException


class ConflitEtat(APIException):
    """409 — l'état courant des données s'oppose à l'écriture demandée."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "L'état actuel du document s'oppose à cette opération."
    default_code = 'state_conflict'
