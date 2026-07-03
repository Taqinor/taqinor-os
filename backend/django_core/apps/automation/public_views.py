"""XPLT4 — Webhook ENTRANT générique alimentant une règle d'automatisation.

``POST /api/django/public/hooks/<token>/`` (sans authentification session) :
le JSON reçu devient le contexte d'une seule ``AutomationRule`` (celle liée
au ``IncomingWebhookTrigger`` du token). La société est résolue UNIQUEMENT
par le token — jamais par le payload. Un token invalide/désactivé → 404
(ne révèle pas si le token a existé). Chaque appel est journalisé dans
``AutomationRun`` (via ``engine.evaluate``), throttlé par token.
"""
import hmac
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.throttling import SimpleRateThrottle

from .models import IncomingWebhookTrigger

logger = logging.getLogger(__name__)


class _WebhookTokenThrottle(SimpleRateThrottle):
    """Débit limité PAR TOKEN (pas par IP) — évite qu'un token compromis
    inonde le moteur d'automatisation. Taux configurable (scope
    ``automation_webhook`` dans DEFAULT_THROTTLE_RATES) ; à défaut de scope
    configuré, DRF applique aucune limite (comportement additif)."""
    scope = 'automation_webhook'

    def __init__(self, token):
        self._token = token
        super().__init__()

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self._token}

    def allow_request(self, request=None, view=None):
        # Utilisable en dehors du cycle DRF habituel (vue Django simple) :
        # request/view ne sont pas nécessaires à `get_cache_key` ici.
        return super().allow_request(request, view)


def _throttled(token):
    throttle = _WebhookTokenThrottle(token)
    try:
        return not throttle.allow_request(None, None)
    except Exception:  # pragma: no cover - défensif, jamais bloquant
        return False


def _verify_signature(trigger, raw_body, provided_sig):
    if not trigger.hmac_secret:
        return True  # signature optionnelle : token seul suffit
    if not provided_sig:
        return False
    expected = hmac.new(
        trigger.hmac_secret.encode('utf-8'), raw_body, 'sha256').hexdigest()
    return hmac.compare_digest(expected, provided_sig)


@csrf_exempt
@require_POST
def incoming_webhook(request, token):
    trigger = (
        IncomingWebhookTrigger.objects
        .select_related('rule', 'company')
        .filter(token=token, enabled=True)
        .first()
    )
    if trigger is None:
        return JsonResponse({'detail': 'Introuvable.'}, status=404)

    if _throttled(token):
        return JsonResponse({'detail': 'Trop de requêtes.'}, status=429)

    raw_body = request.body or b''
    provided_sig = request.headers.get('X-Signature', '')
    if not _verify_signature(trigger, raw_body, provided_sig):
        return JsonResponse({'detail': 'Signature invalide.'}, status=401)

    try:
        data = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        if not isinstance(data, dict):
            raise ValueError('payload non-objet')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail': 'JSON invalide.'}, status=400)

    rule = trigger.rule
    if rule is None or not rule.enabled:
        # Le trigger existe mais sa règle est désactivée/supprimée : on
        # accepte quand même la requête (jamais de perte silencieuse côté
        # émetteur) mais rien ne s'exécute — cohérent avec le principe
        # additif/opt-in du moteur.
        return JsonResponse({'detail': 'Reçu (règle inactive).'}, status=202)

    from . import engine
    from .models import TriggerType
    engine.evaluate(
        TriggerType.WEBHOOK_INBOUND, None, trigger.company,
        context={'payload': data, 'rule_id': rule.pk})

    return JsonResponse({'detail': 'Reçu.'}, status=202)
