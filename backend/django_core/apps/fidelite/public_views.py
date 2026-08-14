"""Endpoint PUBLIC (sans login) de la carte de fidélité dématérialisée —
NTRET11.

``GET /api/django/fidelite/carte/<token>/`` — accessible via ``code_qr``
(jeton opaque non séquentiel, jamais l'id de la ligne), pensé pour être
scanné par une douchette code-barres/QR à l'écran caisse (même famille que le
pattern étiquettes stock N20). LECTURE SEULE, JAMAIS de donnée sensible
(pas d'email/téléphone/adresse/CIN) — juste de quoi rattacher automatiquement
le bon client au panier en cours côté caisse.

Isolation tenant : ``code_qr`` est GLOBALEMENT unique (contrainte modèle) —
un jeton pointe toujours EXACTEMENT un compte d'UNE société ; il n'existe donc
aucune façon de le « réutiliser » pour un autre tenant.
"""
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .selectors import get_compte_par_code_qr


class CartePubliqueThrottle(SimpleRateThrottle):
    """YRBAC9 — anti-force-brute du ``code_qr``, par IP.

    Le jeton est le SEUL secret de cet endpoint : sans borne de débit, il
    serait énumérable. Même patron que ``sav.public_views.SavPublicThrottle``
    et ``stock.public_views.QuaiCheckinThrottle`` (``rate`` en dur +
    ``get_rate``, donc aucune entrée ``DEFAULT_THROTTLE_RATES`` requise ; une
    classe par app car importer le throttle d'une autre app passerait par ses
    ``views``, interdit par la frontière inter-apps).

    Budget 30/min : celui des autres liens tokenisés lus par un humain du
    dépôt (``sav_public_link``, ``public_sharelink``). Large pour une caisse
    qui enchaîne les scans à la douchette, dérisoire pour une énumération."""

    scope = 'fidelite_carte_publique'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope, 'ident': self.get_ident(request),
        }


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([CartePubliqueThrottle])
def carte_publique(request, token):
    """Carte de fidélité publique tokenisée (lecture seule)."""
    compte = get_compte_par_code_qr(token)
    if compte is None:
        return Response({'detail': 'Carte introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    client = compte.client
    nom = ' '.join(p for p in [client.prenom, client.nom] if p) or client.nom
    return Response({
        'compte_id': compte.id,
        'client_id': compte.client_id,
        'nom': nom,
        'solde_points': compte.solde_points,
        'palier': compte.palier_actuel.libelle if compte.palier_actuel_id else None,
    })
