"""ENF1 — configuration gunicorn du SEUL serveur du job `api-fuzz`.

Coupe les throttles DRF dans ce processus, et nulle part ailleurs (aucun
réglage produit ne change ; même esprit que ``TENANT_RATE_LIMIT=0`` déjà
posé par le job). Raison : les budgets anonymes/par portée sont codés en
dur (``login`` 5/min, ``public_sharelink`` 30/min, ``ged_public_depot``…,
voir ``REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']``) ; sous les milliers de
requêtes du fuzzeur ils s'épuisaient et le reste du run recevait 429 — y
compris des ``TRACE`` qui auraient dû répondre 405 (cluster C10 du 09/10).
Le throttling est une politique de débit, couverte par ses tests Django,
pas une propriété du contrat d'API que le fuzz vérifie.

Usage :
    gunicorn -c scripts/fuzz/gunicorn_fuzz.py erp_agentique.wsgi:application
"""


def post_worker_init(worker):
    # Appelé APRÈS le chargement de l'application WSGI (Django prêt).
    from rest_framework.throttling import SimpleRateThrottle
    from rest_framework.views import APIView

    def _aucun_throttle(self, request):
        return None

    def _toujours_autorise(self, request, view):
        return True

    # Toutes les vues DRF : plus aucun throttle consulté.
    APIView.check_throttles = _aucun_throttle
    # Throttles appelés À LA MAIN hors `check_throttles` (ex. le webhook
    # entrant d'`apps/automation/public_views.py`) et sous-classes qui
    # délèguent à `super().allow_request` (publicapi).
    SimpleRateThrottle.allow_request = _toujours_autorise
    worker.log.info('ENF1 : throttles DRF coupés (serveur de fuzz seul)')
