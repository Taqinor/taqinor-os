"""Tests YAPIC3 — enveloppe d'erreur DRF unifiée (`core.exceptions`).

Unitaire sur `taqinor_exception_handler` directement (aucune vue HTTP, aucune
DB) : les 4 formes (400 validation, 401, 404, 500 non géré) doivent TOUTES
porter la même clé racine ``error`` avec un ``code`` énuméré stable, et le
``request_id`` du contexte est propagé sans jamais changer le statut HTTP.

Bug user-visible (2026-07-31) — un ``django.db.models.ProtectedError`` non
intercepté par la vue (ex. suppression d'un devis/facture encore référencé
par une pièce financière/légale en ``on_delete=PROTECT``) remontait en 500
générique au lieu d'un 409 explicite. Les tests ``ProtectedError…`` ci-dessous
couvrent le nouveau mapping DIRECTEMENT sur le handler (aucune DB requise :
un faux ``ProtectedError`` avec de faux objets protégés suffit) — les tests
API bout-en-bout (vraie suppression bloquée, deux lignes qui survivent) sont
dans ``apps/ventes/tests/test_protected_delete_409.py``.
"""
from types import SimpleNamespace

from django.db.models import ProtectedError
from django.test import SimpleTestCase
from rest_framework import exceptions as drf_exceptions
from rest_framework import status

from core.exceptions import taqinor_exception_handler


def _context(request_id=None):
    request = SimpleNamespace(request_id=request_id) if request_id else None
    return {'request': request, 'view': None}


class ErrorEnvelopeTests(SimpleTestCase):

    def test_validation_error_400_has_fields_and_stable_code(self):
        exc = drf_exceptions.ValidationError(
            {'email': ['Ce champ est requis.']})
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = response.data
        self.assertIn('error', body)
        self.assertEqual(body['error']['code'], 'validation_error')
        self.assertEqual(
            body['error']['fields'], {'email': ['Ce champ est requis.']})

    def test_not_authenticated_401_same_root_key(self):
        exc = drf_exceptions.NotAuthenticated()
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'not_authenticated')
        self.assertIsNone(response.data['error']['fields'])

    def test_not_found_404_same_root_key(self):
        exc = drf_exceptions.NotFound()
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'not_found')

    def test_unhandled_exception_folds_to_500_server_error(self):
        exc = RuntimeError('boom — détail interne jamais exposé')
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(
            response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'server_error')
        # Le message générique ne fuite jamais le détail de l'exception.
        self.assertNotIn('boom', response.data['error']['message'])

    def test_request_id_propagated_without_changing_status(self):
        exc = drf_exceptions.PermissionDenied()
        response = taqinor_exception_handler(
            exc, _context(request_id='req-abc-123'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['request_id'], 'req-abc-123')

    def test_request_id_absent_is_none_not_an_error(self):
        exc = drf_exceptions.PermissionDenied()
        response = taqinor_exception_handler(exc, _context())
        self.assertIsNone(response.data['error']['request_id'])

    def test_throttled_maps_to_throttled_code(self):
        exc = drf_exceptions.Throttled(wait=5)
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['error']['code'], 'throttled')

    def test_throttled_carries_retry_after_numeric(self):
        """YAPIC12 — un dépassement renvoie 429 + Retry-After numérique,
        via le Response DRF NATIF préservé (seul .data est reformaté)."""
        exc = drf_exceptions.Throttled(wait=42)
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(response.get('Retry-After'), '42')

    def test_throttled_with_scoped_view_adds_ratelimit_headers(self):
        """YAPIC12 — X-RateLimit-Limit/-Remaining quand un scope s'applique
        (lecture STATIQUE de la config, ne ré-invoque jamais allow_request)."""
        class _FakeThrottle:
            rate = '5/minute'

            def parse_rate(self, rate):
                return 5, 60

        class _FakeView:
            def get_throttles(self):
                return [_FakeThrottle()]

        exc = drf_exceptions.Throttled(wait=7)
        response = taqinor_exception_handler(
            exc, {'request': None, 'view': _FakeView()})
        self.assertEqual(response.get('X-RateLimit-Limit'), '5')
        self.assertEqual(response.get('X-RateLimit-Remaining'), '0')

    def test_throttled_without_scoped_view_omits_ratelimit_headers(self):
        exc = drf_exceptions.Throttled(wait=7)
        response = taqinor_exception_handler(exc, _context())
        self.assertNotIn('X-RateLimit-Limit', response)


class _FakeProtectedObj:
    """Stand-in for a model instance with a ``Meta.verbose_name`` — just
    enough for ``_protected_error_message`` to build its label, no DB."""

    def __init__(self, verbose_name):
        self._meta = SimpleNamespace(verbose_name=verbose_name)


class ProtectedErrorTests(SimpleTestCase):
    """Bug fix (2026-07-31) — ``django.db.models.ProtectedError`` gets its
    OWN 409 branch instead of falling into the generic 500 bucket (the
    ``response is None`` path, since ProtectedError isn't a DRF
    APIException). Several FKs were just switched to ``on_delete=PROTECT``
    to stop a quote/invoice being deleted while financial/legal evidence
    still points at it (``RegulatoryDossier.devis``,
    ``SubventionDossier.devis``, ``PaiementFacturePortail.facture``,
    ``AcceptationDevisPortail.devis``) — the refusal was already correct,
    only the HTTP status/shape was wrong.

    Regression guard: ``apps.crm``'s ``ClientViewSet.destroy`` and
    ``apps.stock``'s ``ProduitViewSet``/``MarqueViewSet.destroy`` already
    catch ``ProtectedError`` THEMSELVES and return their own ``Response``
    directly — that exception never reaches DRF's exception handling at all
    for those paths, so this new branch cannot change (or double-handle)
    what they already return. It only fires for a view with NO local
    handling (e.g. ``apps.ventes`` Devis/Facture — see
    ``apps/ventes/tests/test_protected_delete_409.py`` for the end-to-end
    API proof)."""

    def test_protected_error_returns_409_not_500(self):
        exc = ProtectedError('Cannot delete', [_FakeProtectedObj('devis')])
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_protected_error_message_names_the_referencing_model(self):
        exc = ProtectedError(
            'Cannot delete', [_FakeProtectedObj('dossier réglementaire')])
        response = taqinor_exception_handler(exc, _context())
        self.assertIn('1 dossier réglementaire', response.data['detail'])
        self.assertIn('Suppression refusée', response.data['detail'])

    def test_protected_error_counts_multiple_referencing_rows(self):
        exc = ProtectedError(
            'Cannot delete',
            [_FakeProtectedObj('paiement'), _FakeProtectedObj('paiement')])
        response = taqinor_exception_handler(exc, _context())
        self.assertIn('2 paiement', response.data['detail'])

    def test_protected_error_envelope_matches_yapic3_shape(self):
        """`detail` at the root (same key crm/stock already use for their
        own 409s) PLUS the YAPIC3 machine envelope under `error` — additive,
        never a replacement (same contract as every other exception here)."""
        exc = ProtectedError('Cannot delete', [_FakeProtectedObj('devis')])
        response = taqinor_exception_handler(
            exc, _context(request_id='req-prot-1'))
        self.assertEqual(response.data['error']['code'], 'protected_error')
        self.assertEqual(
            response.data['error']['message'], response.data['detail'])
        self.assertEqual(
            response.data['error']['request_id'], 'req-prot-1')
        self.assertIsNone(response.data['error']['fields'])

    def test_protected_error_without_protected_objects_uses_generic_message(self):
        """Defensive fallback if Django ever raises ``ProtectedError`` with
        an empty/unavailable ``protected_objects`` — still a clear French
        409, never a KeyError/500."""
        exc = ProtectedError('Cannot delete', [])
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('référencé', response.data['detail'])
