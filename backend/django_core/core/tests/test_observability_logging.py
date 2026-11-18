"""NTPLT43 — contexte tenant + logs JSON structurés."""
import json
import logging
import sys
from unittest import mock

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core import observability
from core.logging_ext import JSONFormatter, TenantLogFilter
from core.observability import RequestObservabilityMiddleware


class RequestIdMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def _run(self, request):
        captured = {}

        def get_response(req):
            captured['ctx'] = dict(observability.current_context())
            return HttpResponse('ok')

        mw = RequestObservabilityMiddleware(get_response)
        return mw(request), captured['ctx']

    def test_generates_and_returns_request_id(self):
        resp, ctx = self._run(self.rf.get('/api/x/'))
        self.assertIn('X-Request-ID', resp)
        self.assertEqual(resp['X-Request-ID'], ctx['request_id'])
        self.assertEqual(ctx['path'], '/api/x/')

    def test_propagates_incoming_request_id(self):
        req = self.rf.get('/api/x/', HTTP_X_REQUEST_ID='abc-123')
        resp, ctx = self._run(req)
        self.assertEqual(resp['X-Request-ID'], 'abc-123')
        self.assertEqual(ctx['request_id'], 'abc-123')

    def test_context_cleared_outside_request(self):
        self._run(self.rf.get('/api/x/'))
        # Hors requête, current_context est vide (contextvar par défaut None).
        self.assertEqual(observability.current_context(), {})


class TenantLogFilterTests(SimpleTestCase):
    def test_filter_injects_fields_and_formatter_emits_json(self):
        rf = RequestFactory()

        def get_response(req):
            record = logging.LogRecord(
                'app', logging.INFO, __file__, 1, 'hello', None, None)
            TenantLogFilter().filter(record)
            line = JSONFormatter().format(record)
            data = json.loads(line)
            self.assertEqual(data['message'], 'hello')
            self.assertIn('request_id', data)
            self.assertEqual(data['path'], '/api/y/')
            return HttpResponse('ok')

        RequestObservabilityMiddleware(get_response)(rf.get('/api/y/'))


class RequeteLenteSentryTests(SimpleTestCase):
    """BPQ10 - requete lente => capture_message Sentry, dedupliquee par route/heure."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.rf = RequestFactory()

    def _appel(self, chemin):
        mw = RequestObservabilityMiddleware(lambda req: HttpResponse('ok'))
        mw.slow_ms = 1e-9  # tout appel depasse le seuil
        mw(self.rf.get(chemin))

    def _avec_sentry(self, actif=True):
        import sys
        faux = mock.MagicMock()
        ctx = mock.patch.dict(sys.modules, {'sentry_sdk': faux})
        gate = mock.patch('core.monitoring.is_enabled', return_value=actif)
        return faux, ctx, gate

    def test_envoie_un_message_tague_lent_avec_route_normalisee(self):
        faux, ctx, gate = self._avec_sentry()
        with ctx, gate:
            self._appel('/api/django/ventes/devis/123/')
        faux.capture_message.assert_called_once()
        scope = faux.new_scope.return_value.__enter__.return_value
        tags = {c.args[0]: c.args[1] for c in scope.set_tag.call_args_list}
        self.assertEqual(tags['lent'], 'true')
        self.assertEqual(tags['route'], '/api/django/ventes/devis/:id/')
        self.assertIn('request_id', tags)
        self.assertIn('duration_ms', tags)

    def test_dedoublonne_par_route_et_par_heure(self):
        faux, ctx, gate = self._avec_sentry()
        with ctx, gate:
            self._appel('/api/django/ventes/devis/1/')
            self._appel('/api/django/ventes/devis/2/')
            self._appel('/api/django/crm/leads/')
        self.assertEqual(faux.capture_message.call_count, 2)

    def test_sans_dsn_no_op(self):
        faux, ctx, gate = self._avec_sentry(actif=False)
        with ctx, gate:
            self._appel('/api/django/ventes/devis/1/')
        faux.capture_message.assert_not_called()


class CheminsSensiblesJournauxTests(SimpleTestCase):
    """Un secret porté par l'adresse (``core.chemins_sensibles``) : le contexte de requête, chaque
    enregistrement de journal (fabrique) et le formateur JSON ne l'écrivent jamais."""

    def setUp(self):
        from core import chemins_sensibles
        chemins_sensibles.enregistrer('test.secret', r'(/secret/)[^/?#.]+', r'\1<masqué>')
        self.addCleanup(chemins_sensibles.retirer, 'test.secret')

    def test_contexte_de_requete_masque(self):
        vu = {}

        def get_response(req):
            vu['ctx'] = dict(observability.current_context())
            return HttpResponse('ok')

        RequestObservabilityMiddleware(get_response)(RequestFactory().get('/api/secret/s3cr3t.ics'))
        self.assertEqual(vu['ctx']['path'], '/api/secret/<masqué>.ics')
        self.assertEqual(RequestObservabilityMiddleware._route_normalisee(vu['ctx']['path']),
                         '/api/secret/<masqué>.ics')

    def test_arguments_en_dictionnaire_specialise_gardent_leur_comportement(self):
        """Relecture finale n° 3 : la fabrique ne remplace pas les arguments par un `dict` nu. Le journal
        d'accès de gunicorn passe un dictionnaire qui rend « - » pour un en-tête absent (`SafeAtoms`) : le
        réécrire en `dict` levait `KeyError` au formatage. Rien n'est réécrit quand rien n'est masqué ; quand
        une valeur l'est, c'est une COPIE du même type qui la porte."""
        class Atomes(dict):
            def __getitem__(self, cle):
                return dict.get(self, cle, '-')

        sans_secret = Atomes(h='10.0.0.1', U='/api/sante/')
        record = logging.getLogger('test.secret').makeRecord(
            'test.secret', logging.INFO, __file__, 1, '%(h)s %(U)s %({x-absent}i)s', (sans_secret,), None)
        self.assertIs(record.args, sans_secret, 'rien à masquer : les arguments ne sont pas touchés')
        self.assertEqual(record.getMessage(), '10.0.0.1 /api/sante/ -')
        avec_secret = Atomes(h='10.0.0.1', U='/api/secret/s3cr3t.ics')
        record = logging.getLogger('test.secret').makeRecord(
            'test.secret', logging.INFO, __file__, 1, '%(h)s %(U)s %({x-absent}i)s', (avec_secret,), None)
        self.assertEqual(record.getMessage(), '10.0.0.1 /api/secret/<masqué>.ics -')
        self.assertIsInstance(record.args, Atomes)
        self.assertEqual(avec_secret['U'], '/api/secret/s3cr3t.ics', "l'objet de l'appelant n'est pas modifié")

    def test_enregistrement_et_formateur_json_masquent(self):
        try:
            raise RuntimeError('panne /secret/s3cr3t')
        except RuntimeError:
            exc_info = sys.exc_info()
        record = logging.getLogger('test.secret').makeRecord(
            'test.secret', logging.WARNING, __file__, 1, 'Not Found: %s', ('/api/secret/s3cr3t',), exc_info)
        self.assertEqual(record.getMessage(), 'Not Found: /api/secret/<masqué>')
        self.assertEqual(record.msg, 'Not Found: %s', 'un message sans secret garde son gabarit')
        self.assertNotIn('s3cr3t', logging.Formatter().format(record))
        brut = logging.LogRecord('x', logging.ERROR, __file__, 1, 'vu %(p)s', None, exc_info)
        brut.args = {'p': '/secret/s3cr3t'}
        ligne = JSONFormatter().format(brut)
        self.assertNotIn('s3cr3t', ligne)
        self.assertIn('/secret/<masqué>', json.loads(ligne)['exc'])
