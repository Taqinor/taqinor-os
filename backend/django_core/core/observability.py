"""NTPLT43/44/51 — observabilité par requête (contexte tenant, logs, métriques).

Couche de FONDATION : n'importe aucune app métier. Un unique middleware léger
capture, pour chaque requête HTTP :

  * ``request_id`` — repris de l'en-tête ``X-Request-ID`` s'il est fourni (un
    proxy/edge peut le propager), sinon un UUID4 généré ; renvoyé dans la
    réponse (en-tête ``X-Request-ID``) pour corréler client ↔ serveur ↔ logs ;
  * ``company_id`` / ``user_id`` — best-effort depuis ``request.user`` (jamais
    de résolution JWT ajoutée sur le chemin nominal — coût nul) ;
  * ``path`` / ``method`` / ``status`` / ``duration_ms``.

Ces champs sont posés dans un CONTEXTVAR (isolé par requête, aucune fuite) que :
  * NTPLT43 — le filtre de logs ``TenantLogFilter`` lit pour tagger CHAQUE
    enregistrement de log (format JSON activable par ``LOG_FORMAT=json``) ;
  * NTPLT44 — ``core.metrics`` lit pour incrémenter des compteurs par société ;
  * NTPLT51 — la trace des requêtes lentes lit pour journaliser au-delà d'un
    seuil.

Tout est OPT-IN : sans ``LOG_FORMAT=json``, sans ``SLOW_REQUEST_MS`` et sans
scrape ``/metrics``, le middleware se contente de poser le contextvar et de
mesurer une durée (deux lectures d'horloge) — coût négligeable, aucun log ni
métrique nouveau émis.
"""
from __future__ import annotations

import contextvars
import time
import uuid
from typing import Any, Dict, Optional

# Contexte de la requête courante (isolé par thread/coroutine).
_ctx: "contextvars.ContextVar[Optional[Dict[str, Any]]]" = (
    contextvars.ContextVar('obs_request_ctx', default=None))


def current_context() -> Dict[str, Any]:
    """Contexte de la requête courante (dict vide hors requête)."""
    return _ctx.get() or {}


def get_request_id() -> Optional[str]:
    return current_context().get('request_id')


def _best_effort_identity(request):
    """(company_id, user_id) depuis request.user sans forcer d'auth (coût nul)."""
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return None, None
    company = getattr(user, 'company', None)
    company_id = getattr(company, 'pk', None) if company is not None else None
    return company_id, getattr(user, 'pk', None)


class RequestObservabilityMiddleware:
    """Pose le contexte d'observabilité + mesure la durée de chaque requête."""

    def __init__(self, get_response):
        self.get_response = get_response
        from django.conf import settings
        # Seuil requêtes lentes (NTPLT51) : 0/absent = trace désactivée.
        try:
            self.slow_ms = int(getattr(settings, 'SLOW_REQUEST_MS', 0) or 0)
        except (TypeError, ValueError):
            self.slow_ms = 0
        self.access_log = bool(getattr(settings, 'REQUEST_ACCESS_LOG', False))
        # Capture SQL (compte + top requêtes) seulement si DEBUG et trace lente.
        self.debug = bool(getattr(settings, 'DEBUG', False))

    def __call__(self, request):
        # YAPIC4 — `core.middleware.RequestIdMiddleware` (monté PLUS TÔT dans
        # MIDDLEWARE) est désormais l'autorité sur l'id de corrélation ;
        # réutilisé ici pour ne JAMAIS diverger sur la même requête. Repli
        # sur la dérivation historique si ce middleware n'est pas monté
        # (ex. settings custom) — comportement inchangé dans ce cas.
        incoming = request.META.get('HTTP_X_REQUEST_ID', '').strip()
        request_id = getattr(request, 'request_id', None) or incoming or uuid.uuid4().hex
        ctx = {
            'request_id': request_id,
            'path': request.path,
            'method': request.method,
            'company_id': None,
            'user_id': None,
            'status': None,
            'duration_ms': None,
        }
        token = _ctx.set(ctx)
        start = time.monotonic()
        capture = None
        if self.debug and self.slow_ms > 0:
            from django.db import connection
            from django.test.utils import CaptureQueriesContext
            capture = CaptureQueriesContext(connection)
            capture.__enter__()
        try:
            try:
                response = self.get_response(request)
            finally:
                duration_ms = (time.monotonic() - start) * 1000.0
                company_id, user_id = _best_effort_identity(request)
                ctx['company_id'] = company_id
                ctx['user_id'] = user_id
                ctx['duration_ms'] = round(duration_ms, 1)
                if capture is not None:
                    capture.__exit__(None, None, None)
            status = getattr(response, 'status_code', None)
            ctx['status'] = status
            response['X-Request-ID'] = request_id
            # NTPLT44 — métriques par tenant (no-op si rien n'est enregistré).
            try:
                from . import metrics
                metrics.record_http_request(company_id, status, duration_ms)
            except Exception:  # noqa: BLE001 — l'observabilité ne casse jamais la requête
                pass
            # NTPLT51 — trace des requêtes lentes (WARNING au-delà du seuil).
            self._maybe_log_slow(ctx, duration_ms, capture)
            # NTPLT43 — access log structuré (opt-in).
            if self.access_log:
                import logging
                logging.getLogger('core.request').info(
                    '%s %s -> %s', ctx['method'], ctx['path'], status)
            return response
        finally:
            # Réinitialise le contextvar : aucune fuite de contexte d'une requête
            # à la suivante sur le même thread/coroutine (worker sync réutilisé).
            _ctx.reset(token)

    def _maybe_log_slow(self, ctx, duration_ms, capture):
        if self.slow_ms <= 0 or duration_ms < self.slow_ms:
            return
        import logging
        logger = logging.getLogger('core.slow_request')
        logger.warning(
            'Requête lente %.0fms %s %s (tenant=%s)',
            duration_ms, ctx['method'], ctx['path'], ctx['company_id'])
        if capture is not None:
            queries = list(capture.captured_queries)
            top = sorted(
                queries, key=lambda q: float(q.get('time', 0) or 0),
                reverse=True)[:3]
            logger.debug(
                'SQL: %d requêtes ; top: %s', len(queries),
                [(q['sql'][:120], q['time']) for q in top])
