"""VEIL13 — Client ``ads_archive`` isolé, lecture seule, sans contournement de quota.

TOUS les tests passent par ``httpx.MockTransport`` (aucune requête ne sort) ou
par le transport de rejeu (aucun socket ouvert).
"""
import json
import logging
import pathlib
import socket
import tempfile
from unittest import mock

import httpx
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from authentication.models import Company

from apps.adsengine import ad_library_client as alc
from apps.adsengine import veille_acces
from apps.adsengine.api_version import GRAPH_VERSION

JETON = 'EAAJETONVEILLETEST1234567890'
APP_ID = '777000'
SECRET = 'secretdappli_veille_tres_secret'


class Enregistreur:
    """Transport simulé : rejoue une liste de réponses et note chaque requête.
    Une requête vers un autre hôte/chemin que la liste blanche ÉCHOUE."""

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.requetes = []

    def __call__(self, request):
        self.requetes.append(request)
        assert request.url.host == 'graph.facebook.com', request.url
        assert request.url.path in (
            f'/{GRAPH_VERSION}/ads_archive',
            f'/{GRAPH_VERSION}/debug_token'), request.url
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


def ok(data, suivant=True, apres='CURSEUR2', usage=None):
    corps = {'data': data, 'paging': {'cursors': {'after': apres}}}
    if suivant:
        corps['paging']['next'] = 'https://graph.facebook.com/next?after=x'
    entetes = {}
    if usage is not None:
        entetes['x-app-usage'] = json.dumps(usage)
    return httpx.Response(200, json=corps, headers=entetes)


def erreur(code, statut=400):
    return httpx.Response(statut, json={'error': {'code': code,
                                                  'message': 'x'}})


def pub(i, page_id='p1', snapshot=None):
    return {'id': str(i), 'page_id': page_id, 'page_name': 'Boutique',
            'ad_snapshot_url': snapshot or
            f'https://www.facebook.com/ads/archive/render_ad/?id={i}'}


def client_pour(enregistreur, **kw):
    return alc.AdLibraryClient(JETON, app_id=APP_ID, app_secret=SECRET,
                               http_client=enregistreur.client(),
                               dormir=lambda s: None, **kw)


@override_settings(META_AD_LIBRARY_FIXTURES_DIR='',
                   META_AD_LIBRARY_ENABLED=True)
class ChercherTests(SimpleTestCase):
    def test_une_page_jeton_en_entete_jamais_dans_l_url(self):
        usage = {'call_count': 12, 'total_cputime': 3, 'total_time': 5}
        enr = Enregistreur([ok([pub(1)], usage=usage)])
        res = client_pour(enr).chercher('robe été', 'fr')
        self.assertEqual(len(enr.requetes), 1)
        requete = enr.requetes[0]
        self.assertEqual(requete.headers['authorization'], f'Bearer {JETON}')
        self.assertNotIn(JETON, str(requete.url))
        self.assertEqual(requete.url.params['ad_reached_countries'], '["FR"]')
        self.assertIn('ad_creative_link_captions',
                      requete.url.params['fields'])
        self.assertTrue(res['a_suivant'])
        self.assertEqual(res['after_suivant'], 'CURSEUR2')
        self.assertEqual(res['usage'], {'call_count': 12, 'total_cputime': 3,
                                        'total_time': 5})

    def test_chercher_envoie_ad_type_all(self):
        # AACQ37 — parité avec la sonde VEIL40 (ad_type=ALL).
        enr = Enregistreur([ok([pub(1)])])
        client_pour(enr).chercher('robe', 'FR')
        params = enr.requetes[0].url.params
        self.assertEqual(params['ad_type'], 'ALL')
        for cle in ('search_terms', 'ad_reached_countries', 'search_type',
                    'ad_active_status', 'fields'):
            self.assertIn(cle, params)

    def test_page_suivante_garde_ad_type(self):
        enr = Enregistreur([ok([pub(1)]), ok([pub(2)], suivant=False)])
        client = client_pour(enr)
        p1 = client.chercher('robe', 'FR')
        client.chercher('robe', 'FR', after=p1['after_suivant'], limit=25)
        params = enr.requetes[1].url.params
        self.assertEqual(params['ad_type'], 'ALL')
        self.assertEqual(params['after'], 'CURSEUR2')
        self.assertEqual(params['limit'], '25')

    def test_613_une_seule_requete_sans_reessai(self):
        enr = Enregistreur([erreur(613), ok([pub(1)])])
        with self.assertRaises(alc.QuotaAtteint) as ctx:
            client_pour(enr).chercher('robe', 'FR')
        self.assertEqual(len(enr.requetes), 1)
        self.assertEqual(ctx.exception.code, 613)

    def test_codes_quota_et_429_jamais_reessayes(self):
        for code, statut in ((4, 400), (17, 400), (32, 400), (None, 429)):
            with self.subTest(code=code, statut=statut):
                reponse = (httpx.Response(429, json={}) if code is None
                           else erreur(code, statut))
                enr = Enregistreur([reponse, ok([])])
                with self.assertRaises(alc.QuotaAtteint):
                    client_pour(enr).chercher('robe', 'FR')
                self.assertEqual(len(enr.requetes), 1)

    def test_190_acces_invalide(self):
        enr = Enregistreur([erreur(190)])
        with self.assertRaises(alc.AccesInvalide):
            client_pour(enr).chercher('robe', 'FR')
        self.assertEqual(len(enr.requetes), 1)

    def test_autre_4xx_requete_refusee(self):
        enr = Enregistreur([erreur(100)])
        with self.assertRaises(alc.RequeteRefusee) as ctx:
            client_pour(enr).chercher('robe', 'FR')
        self.assertEqual(ctx.exception.code, 100)

    def test_5xx_au_plus_deux_nouveaux_essais(self):
        enr = Enregistreur([httpx.Response(500), httpx.Response(502),
                            httpx.Response(503), ok([])])
        with self.assertRaises(alc.ErreurReseau):
            client_pour(enr).chercher('robe', 'FR')
        self.assertEqual(len(enr.requetes), 3)

    def test_reseau_puis_succes(self):
        enr = Enregistreur([httpx.ConnectError('boom'), ok([pub(1)])])
        res = client_pour(enr).chercher('robe', 'FR')
        self.assertEqual(len(enr.requetes), 2)
        self.assertEqual(len(res['pubs']), 1)

    def test_moins_que_limit_mais_next_present_continue(self):
        enr = Enregistreur([ok([pub(1), pub(2)], suivant=True)])
        res = client_pour(enr).chercher('robe', 'FR', limit=500)
        self.assertEqual(enr.requetes[0].url.params['limit'], '500')
        self.assertTrue(res['a_suivant'])
        self.assertFalse(res['page_vide_avec_suivant'])

    def test_page_vide_avec_next_signalee(self):
        enr = Enregistreur([ok([], suivant=True)])
        res = client_pour(enr).chercher('robe', 'FR')
        self.assertTrue(res['page_vide_avec_suivant'])
        self.assertTrue(res['a_suivant'])

    def test_fin_sans_next(self):
        enr = Enregistreur([ok([pub(1)], suivant=False)])
        res = client_pour(enr).chercher('robe', 'FR')
        self.assertFalse(res['a_suivant'])
        self.assertIsNone(res['after_suivant'])

    def test_snapshot_piege_sans_access_token(self):
        piege = ('https://www.facebook.com/ads/archive/render_ad/'
                 f'?id=9&access_token={JETON}')
        enr = Enregistreur([ok([pub(9, snapshot=piege)])])
        res = client_pour(enr).chercher('robe', 'FR')
        sortie = json.dumps(res)
        self.assertNotIn('access_token', sortie)
        self.assertNotIn(JETON, sortie)
        self.assertIn('id=9', res['pubs'][0]['ad_snapshot_url'])

    def test_validation_sans_requete(self):
        enr = Enregistreur([])
        client = client_pour(enr)
        with self.assertRaises(alc.ParametreInvalide):
            client.chercher('x' * 101, 'FR')
        for code in ('MA', 'US', 'AU'):
            with self.assertRaises(alc.ParametreInvalide):
                client.chercher('robe', code)
        with self.assertRaises(alc.ParametreInvalide) as ctx:
            client.chercher('robe', 'UK')
        self.assertIn('GB', ctx.exception.message_fr)
        with self.assertRaises(alc.ParametreInvalide) as ctx:
            client.chercher('robe', 'EL')
        self.assertIn('GR', ctx.exception.message_fr)
        self.assertEqual(enr.requetes, [])
        # 100 caractères pile : accepté ; GB (à confirmer) : accepté.
        enr2 = Enregistreur([ok([]), ok([])])
        client_pour(enr2).chercher('x' * 100, 'FR')
        client_pour(enr2).chercher('robe', 'GB')
        self.assertEqual(len(enr2.requetes), 2)


class ListeBlancheTests(SimpleTestCase):
    def test_urls_hors_liste_blanche_levent(self):
        for url in (
                'https://www.facebook.com/ads/library/?id=1',
                'https://www.facebook.com/ads/archive/render_ad/?id=1',
                f'https://graph.facebook.com/{GRAPH_VERSION}/me',
                f'https://graph.facebook.com/{GRAPH_VERSION}/act_1/campaigns',
                'https://graph.facebook.com/v1.0/ads_archive',
                f'http://graph.facebook.com/{GRAPH_VERSION}/ads_archive',
                f'https://evil.example/{GRAPH_VERSION}/ads_archive'):
            with self.subTest(url=url):
                with self.assertRaises(alc.UrlInterdite):
                    alc._verifier_url(url)

    def test_source_ne_lit_jamais_bibliotheque_ni_snapshot(self):
        source = pathlib.Path(alc.__file__).read_text(encoding='utf-8')
        self.assertNotIn('.get(pub', source)
        self.assertNotIn("get(p['ad_snapshot_url']", source)
        self.assertNotIn('facebook.com/ads/library', source)


@override_settings(META_AD_LIBRARY_ENABLED=False)
class RejeuTests(SimpleTestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        racine = pathlib.Path(self.dossier.name)
        (racine / 'robe-ete_FR_1.json').write_text(json.dumps({
            'data': [pub(1), pub(2, page_id='p2')],
            'paging': {'next': 'x'},
            '_x_app_usage': {'call_count': 5, 'total_cputime': 1,
                             'total_time': 2}}), encoding='utf-8')
        (racine / 'robe-ete_FR_2.json').write_text(json.dumps({
            'data': [pub(3, snapshot='https://x/?access_token=EAAPIEGE')],
            'paging': {}}), encoding='utf-8')

    def test_rejeu_zero_socket(self):
        def interdit(*a, **k):
            raise AssertionError('socket ouvert en mode rejeu')

        with override_settings(META_AD_LIBRARY_FIXTURES_DIR=self.dossier.name):
            with mock.patch.object(socket.socket, 'connect', interdit), \
                    mock.patch('httpx.Client.send', side_effect=interdit):
                client = alc.AdLibraryClient('')
                p1 = client.chercher('Robe été', 'FR')
                p2 = client.chercher('Robe été', 'FR', after=p1['after_suivant'])
                p3 = client.chercher('Robe été', 'BE')
        self.assertEqual(len(p1['pubs']), 2)
        self.assertTrue(p1['a_suivant'])
        self.assertEqual(p1['usage']['call_count'], 5)
        self.assertEqual(len(p2['pubs']), 1)
        self.assertFalse(p2['a_suivant'])
        self.assertNotIn('access_token', json.dumps(p2))
        self.assertEqual(p3['pubs'], [])  # fixture absente : page vide, fin

    def test_rejeu_inactif_si_interrupteur_vrai(self):
        with override_settings(META_AD_LIBRARY_FIXTURES_DIR=self.dossier.name,
                               META_AD_LIBRARY_ENABLED=True):
            self.assertIsNone(alc.AdLibraryClient.dossier_rejeu())


@override_settings(META_AD_LIBRARY_FIXTURES_DIR='',
                   META_AD_LIBRARY_ENABLED=True)
class VerifierJetonTests(SimpleTestCase):
    def _debug(self, is_valid=True, expires_at=1893456000):
        return httpx.Response(200, json={'data': {
            'is_valid': is_valid, 'expires_at': expires_at}})

    def test_debug_token_secret_jamais_journalise(self):
        enr = Enregistreur([self._debug()])
        with self.assertLogs(level=logging.DEBUG) as cm:
            res = client_pour(enr).verifier_jeton()
            logging.getLogger('httpx').info(
                'HTTP Request: GET %s', str(enr.requetes[0].url))
        sortie = '\n'.join(cm.output)
        self.assertNotIn(SECRET, sortie)
        self.assertNotIn(JETON, sortie)
        self.assertTrue(res['valide'])
        self.assertTrue(res['expire_le'].startswith('2030-01-01'))
        requete = enr.requetes[0]
        self.assertEqual(requete.headers['authorization'],
                         f'Bearer {APP_ID}|{SECRET}')
        self.assertNotIn(SECRET, str(requete.url))

    def test_expires_at_zero_jamais(self):
        enr = Enregistreur([self._debug(expires_at=0)])
        self.assertIsNone(client_pour(enr).verifier_jeton()['expire_le'])

    def test_repr_sans_jeton(self):
        self.assertNotIn(JETON, repr(alc.AdLibraryClient(JETON)))


@override_settings(META_AD_LIBRARY_FIXTURES_DIR='',
                   META_AD_LIBRARY_ACCESS_TOKEN=JETON,
                   META_AD_LIBRARY_APP_ID=APP_ID,
                   META_AD_LIBRARY_APP_SECRET=SECRET,
                   META_AD_LIBRARY_ENABLED=True)
class VeilleAccesVerifierTests(TestCase):
    """VEIL12 × VEIL13 — ``veille_acces.verifier`` appelle debug_token UNE fois
    (à la demande) et en déduit l'état."""

    def setUp(self):
        cache.delete(veille_acces.CLE_CACHE_VERIFICATION)
        self.company = Company.objects.create(nom='YanBow', slug='yanbow-vj')

    def test_verifier_jeton_invalide(self):
        enr = Enregistreur([httpx.Response(200, json={'data': {
            'is_valid': False, 'expires_at': 0}})])
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            res = veille_acces.verifier(self.company,
                                        http_client=enr.client())
        self.assertEqual(res['etat'], 'invalide')
        self.assertEqual(len(enr.requetes), 1)

    def test_verifier_190_invalide(self):
        enr = Enregistreur([erreur(190)])
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            res = veille_acces.verifier(self.company,
                                        http_client=enr.client())
        self.assertEqual(res['etat'], 'invalide')

    def test_verifier_pret_puis_cache(self):
        enr = Enregistreur([httpx.Response(200, json={'data': {
            'is_valid': True, 'expires_at': 0}})])
        with override_settings(VEILLE_SOCIETES_AUTORISEES=[self.company.id]):
            res = veille_acces.verifier(self.company,
                                        http_client=enr.client())
            self.assertEqual(res['etat'], 'pret')
            # lecture suivante : aucune nouvelle requête
            self.assertEqual(veille_acces.etat(self.company)['etat'], 'pret')
        self.assertEqual(len(enr.requetes), 1)
