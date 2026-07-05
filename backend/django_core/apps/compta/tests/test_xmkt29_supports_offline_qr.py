"""XMKT29 — Ponts QR pour supports offline (flyers, bâches, véhicules).

Couvre : créer un support → QR téléchargeable, un scan compte + tague le
lead créé derrière, tableau scans/leads par support.
"""
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import LienTrackee, SupportOffline
from apps.stock.selectors import qr_svg


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


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
