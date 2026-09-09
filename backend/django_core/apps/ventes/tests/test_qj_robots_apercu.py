"""QJ-ROBOTS (fondateur 09/09/2026) — les robots d'aperçu de lien ne comptent
jamais comme une ouverture client.

Le bug vécu : cliquer le bouton WhatsApp de la fiche lead ouvre wa.me avec
l'URL de la page client dans le texte ; WhatsApp pré-charge aussitôt cette URL
pour fabriquer la vignette d'aperçu (UA « WhatsApp/x.y » ou
« facebookexternalhit ») ; la page proposition étant rendue serveur, ce
pré-chargement atteignait le backend comme une vraie lecture → compteur de
vues + note chatter + notification « devis ouvert » au responsable, alors que
le CLIENT n'a encore rien vu.

Couvre :
  (a) UA WhatsApp / facebookexternalhit / TelegramBot / SemrushBot (motif
      générique « bot ») → 200 servi, AUCUN stamp ;
  (b) UA navigateur réel → stamp normal ; UA ABSENT (client de test, fetch
      SSR d'avant le chantier) → stamp normal (rétro-compatible) ;
  (c) requête HEAD → aucun stamp ;
  (d) un devis lié à un lead : le GET robot ne pose AUCUNE note chatter,
      le GET humain pose la note « ouvert » (chaîne de notification intacte).
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead, LeadActivity
from apps.ventes.models import Devis, ShareLink
from apps.ventes.public_views import _est_robot_apercu

UA_WHATSAPP = 'WhatsApp/2.23.24.76 A'
UA_FBEXT = 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)'
UA_TELEGRAM = 'TelegramBot (like TwitterBot)'
UA_SEMRUSH = 'Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)'
UA_CHROME = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')
UA_ANDROID_INAPP = ('Mozilla/5.0 (Linux; Android 14; SM-A515F) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36')


def _make_company(slug, nom):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


_PATCH_GEN = patch(
    'apps.ventes.public_views.generate_premium_devis_pdf',
    return_value='devis/1/DEV-QJR-0001.pdf',
)
_PATCH_DL = patch(
    'apps.ventes.public_views.download_pdf',
    return_value=b'%PDF-1.4 stub',
)


class TestEstRobotApercu(TestCase):
    """Le classifieur UA seul (aucun HTTP) — jetons robots vs navigateurs."""

    def _req(self, ua=None, method='GET'):
        from django.test import RequestFactory
        kwargs = {} if ua is None else {'HTTP_USER_AGENT': ua}
        return getattr(RequestFactory(), method.lower())('/x', **kwargs)

    def test_robots_reconnus(self):
        for ua in (UA_WHATSAPP, UA_FBEXT, UA_TELEGRAM, UA_SEMRUSH,
                   'Twitterbot/1.0', 'LinkedInBot/1.0', 'Applebot/0.1',
                   'Slackbot-LinkExpanding 1.0', 'curl/8.4.0'):
            self.assertTrue(_est_robot_apercu(self._req(ua)), ua)

    def test_navigateurs_humains_jamais_robots(self):
        for ua in (UA_CHROME, UA_ANDROID_INAPP,
                   'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) '
                   'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 '
                   'Mobile/15E148 Safari/604.1'):
            self.assertFalse(_est_robot_apercu(self._req(ua)), ua)

    def test_ua_absent_pas_robot(self):
        # Rétro-compatibilité : le fetch SSR d'avant le chantier et le client
        # de test Django n'envoient AUCUN UA — le comptage doit continuer.
        self.assertFalse(_est_robot_apercu(self._req(None)))

    def test_head_est_robot(self):
        self.assertTrue(_est_robot_apercu(self._req(UA_CHROME, method='HEAD')))

    def test_request_none_pas_robot(self):
        self.assertFalse(_est_robot_apercu(None))


class TestRobotParReseauOrigine(TestCase):
    """QJ-ROBOTS-2 (lead Mekapa, 09/09 12:34Z) — la sonde anti-cloaking de
    Meta arrive avec un UA de VRAI navigateur (iPhone Safari, 2 s après le
    fetch facebookexternalhit) : seul son RÉSEAU d'origine (AS32934) la
    trahit. Un UA navigateur + IP datacenter Meta = robot ; le même UA depuis
    une IP résidentielle marocaine = humain."""

    def _req(self, ua=UA_ANDROID_INAPP, **meta):
        from django.test import RequestFactory
        return RequestFactory().get('/x', HTTP_USER_AGENT=ua, **meta)

    def test_sonde_meta_ua_navigateur_xff(self):
        # Chaîne page publique : le SSR pose la vraie IP en 1er saut XFF.
        req = self._req(HTTP_X_FORWARDED_FOR='157.240.25.10, 172.68.103.143')
        self.assertTrue(_est_robot_apercu(req))

    def test_sonde_meta_cf_connecting_ip(self):
        # Accès direct : Cloudflare pose CF-Connecting-IP.
        req = self._req(HTTP_CF_CONNECTING_IP='173.252.70.5')
        self.assertTrue(_est_robot_apercu(req))

    def test_sonde_meta_ipv6(self):
        req = self._req(HTTP_X_FORWARDED_FOR='2a03:2880:f003:c07:face:b00c::2')
        self.assertTrue(_est_robot_apercu(req))

    def test_client_residentiel_meme_ua_reste_humain(self):
        req = self._req(HTTP_X_FORWARDED_FOR='196.75.10.20, 172.68.103.143')
        self.assertFalse(_est_robot_apercu(req))

    def test_ip_illisible_ignoree_sans_exception(self):
        req = self._req(HTTP_X_FORWARDED_FOR='unknown, pas-une-ip')
        self.assertFalse(_est_robot_apercu(req))

    def test_meta_externalagent_reconnu_par_ua(self):
        from django.test import RequestFactory
        req = RequestFactory().get('/x', HTTP_USER_AGENT=(
            'meta-externalagent/1.1 '
            '(+https://developers.facebook.com/docs/sharing/webmasters/crawler)'))
        self.assertTrue(_est_robot_apercu(req))


class TestRobotNeStampeJamais(TestCase):
    """(a)/(b)/(c) — sur les endpoints publics réels."""

    def setUp(self):
        self.company = _make_company('qjr-co', 'QJR Co')
        self.client_obj = Client.objects.get_or_create(
            company=self.company, nom='Client QJR')[0]
        self.devis = Devis.objects.get_or_create(
            company=self.company, reference='DEV-QJR-S1',
            defaults={'client': self.client_obj, 'taux_tva': Decimal('20')},
        )[0]
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)

    def _get_document(self, ua=None, method='get'):
        kwargs = {} if ua is None else {'HTTP_USER_AGENT': ua}
        return getattr(APIClient(), method)(
            f'/api/django/public/document/{self.link.token}/', **kwargs)

    @_PATCH_GEN
    @_PATCH_DL
    def test_ua_whatsapp_servi_mais_pas_stampe(self, m_dl, m_gen):
        resp = self._get_document(UA_WHATSAPP)
        self.assertEqual(resp.status_code, 200)
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)
        self.assertIsNone(self.link.first_viewed_at)
        self.assertIsNone(self.link.last_viewed_at)

    @_PATCH_GEN
    @_PATCH_DL
    def test_ua_facebookexternalhit_pas_stampe(self, m_dl, m_gen):
        self._get_document(UA_FBEXT)
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)

    @_PATCH_GEN
    @_PATCH_DL
    def test_ua_navigateur_stampe(self, m_dl, m_gen):
        self._get_document(UA_CHROME)
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 1)
        self.assertIsNotNone(self.link.first_viewed_at)

    @_PATCH_GEN
    @_PATCH_DL
    def test_sans_ua_stampe_comme_avant(self, m_dl, m_gen):
        self._get_document(None)
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 1)

    @_PATCH_GEN
    @_PATCH_DL
    def test_head_pas_stampe(self, m_dl, m_gen):
        self._get_document(UA_CHROME, method='head')
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)

    @_PATCH_GEN
    @_PATCH_DL
    def test_sonde_meta_ua_navigateur_pas_stampe(self, m_dl, m_gen):
        """QJ-ROBOTS-2 — la sonde Meta déguisée en iPhone (UA navigateur,
        IP datacenter AS32934 en 1er saut XFF) est servie mais jamais
        comptée ; le même UA depuis une IP résidentielle compte."""
        APIClient().get(
            f'/api/django/public/document/{self.link.token}/',
            HTTP_USER_AGENT=UA_ANDROID_INAPP,
            HTTP_X_FORWARDED_FOR='157.240.25.10, 172.68.103.143')
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)

        APIClient().get(
            f'/api/django/public/document/{self.link.token}/',
            HTTP_USER_AGENT=UA_ANDROID_INAPP,
            HTTP_X_FORWARDED_FOR='196.75.10.20, 172.68.103.143')
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 1)


class TestRobotNeNotifieJamais(TestCase):
    """(d) — devis lié à un LEAD : le robot ne laisse AUCUNE trace chatter ;
    l'humain déclenche la note « ouvert » habituelle (chaîne QJ1/QJ2 intacte)."""

    def setUp(self):
        self.company = _make_company('qjr-lead', 'QJR Lead')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect QJR')
        self.client_obj = Client.objects.get_or_create(
            company=self.company, nom='Client QJR Lead')[0]
        self.devis = Devis.objects.get_or_create(
            company=self.company, reference='DEV-QJR-N1',
            defaults={'client': self.client_obj, 'lead': self.lead,
                      'taux_tva': Decimal('20')},
        )[0]
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)

    def _get_data(self, ua=None):
        kwargs = {} if ua is None else {'HTTP_USER_AGENT': ua}
        return APIClient().get(
            f'/api/django/public/proposal/{self.link.token}/data/', **kwargs)

    @patch('apps.ventes.quote_engine.builder.build_quote_data',
           return_value={'ref': 'DEV-QJR-N1', 'date': '2026-09-09',
                         'client_name': 'Prospect QJR'})
    def test_robot_aucune_note_humain_note_ouvert(self, m_bqd):
        # Robot d'abord : aucune activité chatter ne doit apparaître.
        resp = self._get_data(UA_WHATSAPP)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), 0)
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)

        # Humain ensuite : la première ouverture pose la note « ouvert ».
        self._get_data(UA_ANDROID_INAPP)
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 1)
        notes = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any('ouvert' in (n.body or '') for n in notes),
            [n.body for n in notes])
