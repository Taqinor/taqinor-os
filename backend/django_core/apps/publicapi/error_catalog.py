"""NTAPI4 — catalogue d'erreurs CONSULTABLE de l'API publique.

Registre ``code → (titre FR, description, action corrective, http_status)``,
exposé en lecture seule par ``GET /api/public/v1/errors/`` et pointé par
``doc_url`` dans chaque enveloppe d'erreur NTAPI3 (``errors.py``) :
``/api/public/v1/errors/#<code>``.

ALIGNEMENT 1:1 AVEC LES CODES RÉELLEMENT ÉMIS — c'est tout l'intérêt. Les codes
ne sont PAS ré-écrits à la main ici : ils sont DÉRIVÉS de la seule table qui les
produit, ``errors._KNOWN_CODES``, plus les deux codes hors-table que le handler
sait fabriquer (``server_error``, ``api_error``) et les ``default_code`` des
``APIException`` custom de l'app. ``tests_ntapi4_error_catalog.py`` verrouille
cette égalité : ajouter un code d'erreur sans l'expliquer fait rougir la CI.

Aucune fuite cross-tenant : le catalogue est un document de DÉCOUVERTE global
(comme ``openapi.json`` NTAPI20 et le changelog NTAPI24) — il ne contient aucune
donnée de société, donc aucune clé n'est requise pour le lire.
"""
from __future__ import annotations

from rest_framework import status

from .errors import _KNOWN_CODES

# Codes que le handler NTAPI3 fabrique SANS passer par `_KNOWN_CODES` :
#  * `server_error`  — exception non reconnue par DRF (handler natif → None) ;
#  * `api_error`     — `APIException` custom sans `default_code` utile.
CODES_HORS_TABLE = ('server_error', 'api_error')

# `default_code` des `APIException` custom de l'app (XPLT5 — idempotence).
# Énuméré ici plutôt que déduit par introspection : la déduction ramasserait
# aussi les exceptions d'autres apps, qui ne remontent jamais par ce handler.
CODES_EXCEPTIONS_APP = ('idempotency_conflict',)


def _codes_emis():
    """Tous les codes que ``errors.public_api_exception_handler`` peut émettre.

    Source unique : la table de correspondance du handler lui-même — jamais une
    seconde liste écrite à la main (qui divergerait en silence)."""
    codes = [code for _exc_class, code in _KNOWN_CODES]
    codes.extend(CODES_HORS_TABLE)
    codes.extend(CODES_EXCEPTIONS_APP)
    # Dédoublonne en conservant l'ordre (`not_authenticated` apparaît deux fois
    # dans `_KNOWN_CODES` : `AuthenticationFailed` et `NotAuthenticated`).
    vus = set()
    uniques = []
    for code in codes:
        if code not in vus:
            vus.add(code)
            uniques.append(code)
    return uniques


# Explication FR de CHAQUE code. `http_status` = statut HTTP nominal ; une
# entrée absente ici pour un code émis fait rougir `tests_ntapi4`.
_EXPLICATIONS = {
    'validation_error': {
        'titre': 'Champ invalide',
        'description': (
            "Le corps de la requête a été refusé par la validation : un champ "
            "est absent, mal typé ou hors des valeurs admises. Le champ fautif "
            "est nommé dans « param »."),
        'action': (
            "Corrigez le champ indiqué par « param » et rejouez l'appel. La "
            "liste des champs attendus est dans /api/public/v1/openapi.json."),
        'http_status': status.HTTP_400_BAD_REQUEST,
    },
    'not_authenticated': {
        'titre': "Clé d'API absente ou refusée",
        'description': (
            "Aucune clé n'a été présentée, ou la clé présentée est inconnue, "
            "désactivée, ou expirée (fin de la période de grâce de rotation)."),
        'action': (
            "Envoyez l'en-tête « Authorization: Api-Key <votre_clé> ». Si la "
            "clé a été tournée, utilisez la nouvelle clé émise."),
        'http_status': status.HTTP_401_UNAUTHORIZED,
    },
    'permission_denied': {
        'titre': 'Droit manquant sur cette clé',
        'description': (
            "La clé est valide mais ne porte pas le scope exigé par cet "
            "endpoint (par exemple « read:leads » ou « devis:write »)."),
        'action': (
            "Ajoutez le scope manquant à la clé dans Paramètres → API & "
            "Webhooks, ou utilisez une clé qui le porte déjà."),
        'http_status': status.HTTP_403_FORBIDDEN,
    },
    'not_found': {
        'titre': 'Ressource introuvable',
        'description': (
            "L'objet demandé n'existe pas, ou n'appartient pas à la société de "
            "la clé. Les deux cas renvoient VOLONTAIREMENT la même réponse : "
            "une clé ne peut jamais déduire l'existence d'un enregistrement "
            "d'une autre société."),
        'action': "Vérifiez l'identifiant demandé.",
        'http_status': status.HTTP_404_NOT_FOUND,
    },
    'throttled': {
        'titre': 'Débit ou quota dépassé',
        'description': (
            "Le débit par clé, ou le quota de volume (jour/mois) du plan de la "
            "société, est atteint. Les en-têtes « X-RateLimit-* » donnent le "
            "compteur réel et « Retry-After » le délai d'attente."),
        'action': (
            "Attendez le délai indiqué par « Retry-After », puis rejouez. Pour "
            "un besoin durable, changez de palier d'API."),
        'http_status': status.HTTP_429_TOO_MANY_REQUESTS,
    },
    'method_not_allowed': {
        'titre': 'Méthode HTTP non autorisée',
        'description': (
            "Cet endpoint n'accepte pas ce verbe HTTP (les ressources de "
            "lecture ne servent que GET)."),
        'action': (
            "Consultez /api/public/v1/openapi.json pour la liste des méthodes "
            "acceptées par ce chemin."),
        'http_status': status.HTTP_405_METHOD_NOT_ALLOWED,
    },
    'not_acceptable': {
        'titre': 'Format de réponse non disponible',
        'description': (
            "L'en-tête « Accept » demande un format que cet endpoint ne sait "
            "pas produire."),
        'action': "Demandez « Accept: application/json ».",
        'http_status': status.HTTP_406_NOT_ACCEPTABLE,
    },
    'unsupported_media_type': {
        'titre': 'Type de contenu non supporté',
        'description': (
            "Le « Content-Type » de la requête n'est pas accepté par cet "
            "endpoint."),
        'action': (
            "Envoyez « Content-Type: application/json » (ou "
            "« multipart/form-data » pour un import de fichier)."),
        'http_status': status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    },
    'parse_error': {
        'titre': 'Corps de requête illisible',
        'description': "Le corps envoyé n'est pas un JSON valide.",
        'action': "Vérifiez la syntaxe JSON du corps envoyé.",
        'http_status': status.HTTP_400_BAD_REQUEST,
    },
    'idempotency_conflict': {
        'titre': "Conflit de clé d'idempotence",
        'description': (
            "La même « Idempotency-Key » a déjà servi sur cet endpoint avec un "
            "corps DIFFÉRENT. Rejouer une clé d'idempotence avec un autre corps "
            "est refusé — c'est la garantie qui empêche un doublon silencieux."),
        'action': (
            "Utilisez une nouvelle « Idempotency-Key » pour un appel différent, "
            "ou rejouez à l'identique pour récupérer la réponse mémorisée."),
        'http_status': status.HTTP_409_CONFLICT,
    },
    'api_error': {
        'titre': 'Erreur applicative',
        'description': (
            "Une erreur applicative non catégorisée s'est produite pendant le "
            "traitement."),
        'action': (
            "Rejouez l'appel ; si l'erreur persiste, transmettez le "
            "« request_id » de la réponse au support."),
        'http_status': status.HTTP_400_BAD_REQUEST,
    },
    'server_error': {
        'titre': 'Erreur inattendue du serveur',
        'description': (
            "Une erreur inattendue s'est produite côté serveur. Le détail "
            "technique n'est JAMAIS renvoyé (aucune fuite d'implémentation)."),
        'action': (
            "Rejouez l'appel plus tard ; si l'erreur persiste, transmettez le "
            "« request_id » de la réponse au support."),
        'http_status': status.HTTP_500_INTERNAL_SERVER_ERROR,
    },
}


def catalogue():
    """Le catalogue complet, dans l'ordre des codes émis (liste de dicts).

    Lève ``KeyError`` si un code émis n'a pas d'explication — c'est voulu :
    la faute est de code, détectée par le test de cohérence, jamais servie.
    """
    return [
        {
            'code': code,
            'titre': _EXPLICATIONS[code]['titre'],
            'description': _EXPLICATIONS[code]['description'],
            'action': _EXPLICATIONS[code]['action'],
            'http_status': _EXPLICATIONS[code]['http_status'],
            'doc_url': f'/api/public/v1/errors/#{code}',
        }
        for code in _codes_emis()
    ]


def codes_documentes():
    """Ensemble des codes présents dans le catalogue (pour les tests/gardes)."""
    return {entree['code'] for entree in catalogue()}


def codes_emis():
    """Ensemble des codes que le handler NTAPI3 peut émettre."""
    return set(_codes_emis())
