"""XMKT29 — Ponts QR pour supports offline (flyers, bâches, véhicules).

Couvre : créer un support → QR téléchargeable, un scan compte + tague le
lead créé derrière, tableau scans/leads par support.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import LienTrackee, SupportOffline
from apps.stock.selectors import qr_svg

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SupportsOfflineQrTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt29', 'XMKT29')

    def test_creer_support_offline_genere_lien_tracke(self):
        support = services.creer_support_offline(
            self.co, nom='Flyer SIAM 2026',
            url_cible='https://taqinor.ma/contact')
        self.assertIsNotNone(support.lien_tracke)
        self.assertIn('utm_source=offline', support.url_cible)
        self.assertIn('utm_campaign=Flyer', support.url_cible)

    def test_qr_svg_telechargeable(self):
        support = services.creer_support_offline(
            self.co, nom='Bâche stand', url_cible='https://taqinor.ma')
        svg = services.qr_svg_support_offline(support)
        self.assertTrue(svg.startswith('<svg'))

    def test_scan_incremente_compteur(self):
        support = services.creer_support_offline(
            self.co, nom='Véhicule', url_cible='https://taqinor.ma/v')
        ok, _url = services.traiter_clic_lien(support.lien_tracke.token)
        self.assertTrue(ok)
        support.lien_tracke.refresh_from_db()
        self.assertEqual(support.lien_tracke.nb_clics, 1)

    def test_scan_endpoint_redirige(self):
        support = services.creer_support_offline(
            self.co, nom='Flyer2', url_cible='https://taqinor.ma/f2')
        resp = self.client.get(
            f'/api/django/compta/r/{support.lien_tracke.token}/')
        self.assertEqual(resp.status_code, 302)

    def test_tableau_scans_par_support(self):
        support = services.creer_support_offline(
            self.co, nom='Bâche 2', url_cible='https://taqinor.ma/b2')
        services.traiter_clic_lien(support.lien_tracke.token)
        services.traiter_clic_lien(support.lien_tracke.token)
        tableau = services.tableau_scans_par_support(self.co)
        entry = next(e for e in tableau if e['support_id'] == support.id)
        self.assertEqual(entry['nb_scans'], 2)

    def test_lien_tracke_sans_campagne_ne_casse_pas_clic(self):
        support = services.creer_support_offline(
            self.co, nom='Sans campagne', url_cible='https://taqinor.ma/x')
        # destinataire fourni malgré tout (edge case) : ne doit jamais lever
        # (lien.campagne est None pour un support offline).
        ok, _url = services.traiter_clic_lien(
            support.lien_tracke.token, destinataire='some@x.ma')
        self.assertTrue(ok)

    def test_qr_svg_utilise_selector_stock(self):
        rendu = qr_svg('https://taqinor.ma/test')
        self.assertTrue(rendu.startswith('<svg'))

    def test_isolation_multi_tenant(self):
        other = make_company('xmkt29-b', 'XMKT29-B')
        services.creer_support_offline(
            self.co, nom='Support A', url_cible='https://taqinor.ma/a')
        self.assertEqual(SupportOffline.objects.filter(company=other).count(), 0)

    def test_lientrackee_campagne_nullable(self):
        lien = LienTrackee.objects.create(
            company=self.co, campagne=None, url_cible='https://x.ma',
            token='tok123')
        self.assertIsNone(lien.campagne_id)


class SupportsOfflineViewSetTests(TestCase):
    """Régression : la création DOIT passer par le vrai viewset DRF.

    ``url_cible`` figurait dans ``read_only_fields`` de la sérialiseuse, donc
    DRF l'excluait de ``validated_data`` ; ``perform_create`` recevait alors
    ``url_cible=None`` et ``_tagger_utm_offline(None, …)`` levait → tout POST
    de création renvoyait 500. Les tests niveau service ci-dessus appelaient
    ``services.creer_support_offline`` en direct et ne voyaient pas la faille.
    """

    def setUp(self):
        self.co = make_company('xmkt29-vs', 'XMKT29 VS')
        self.user = make_user(self.co, 'xmkt29-vs-user')
        self.api = auth(self.user)

    def test_post_cree_support_avec_url_taguee(self):
        resp = self.api.post(
            '/api/django/compta/supports-offline/',
            {'nom': 'Flyer SIAM 2026',
             'url_cible': 'https://taqinor.ma/contact'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        support = SupportOffline.objects.get(id=resp.data['id'])
        # url_cible re-dérivée côté serveur (jamais None) + taguée UTM.
        self.assertIn('utm_source=offline', support.url_cible)
        self.assertIn('utm_campaign=Flyer', support.url_cible)
        self.assertEqual(resp.data['url_cible'], support.url_cible)
        self.assertIsNotNone(support.lien_tracke)
        # company forcée côté serveur, jamais depuis le corps de la requête.
        self.assertEqual(support.company_id, self.co.id)

    def test_qr_de_lobjet_cree_est_telechargeable(self):
        resp = self.api.post(
            '/api/django/compta/supports-offline/',
            {'nom': 'Bâche stand', 'url_cible': 'https://taqinor.ma'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        qr = self.api.get(
            f"/api/django/compta/supports-offline/{resp.data['id']}/qr/")
        self.assertEqual(qr.status_code, 200, qr.content)
        self.assertTrue(qr.content.decode().startswith('<svg'))

    def test_route_marketing_cree_aussi(self):
        # Le même viewset est monté sous /marketing/ (ODX9) — il doit créer
        # tout aussi bien que l'alias historique /compta/.
        resp = self.api.post(
            '/api/django/marketing/supports-offline/',
            {'nom': 'Véhicule', 'url_cible': 'https://taqinor.ma/v'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIn('utm_source=offline', resp.data['url_cible'])
