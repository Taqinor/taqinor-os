"""PUB69 — installation_share_link : réutilise ShareLink.for_devis (QJ1,
aucun nouveau modèle) pour la carte de partage « mon installation » après
signature, avec UTM canal parrainage_whatsapp."""
from decimal import Decimal

from django.test import TestCase, override_settings

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, ShareLink
from apps.ventes.services import installation_share_link

MONTH = '202607'


class InstallationShareLinkTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB69 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Partage')

    def _devis(self, ref, statut):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            taux_tva=Decimal('20'), statut=statut)

    def test_not_accepted_devis_returns_none(self):
        devis = self._devis(f'DEV-{MONTH}-PUB6901', Devis.Statut.ENVOYE)
        link, url = installation_share_link(devis)
        self.assertIsNone(link)
        self.assertEqual(url, '')

    def test_accepted_devis_reuses_sharelink_infra(self):
        devis = self._devis(f'DEV-{MONTH}-PUB6902', Devis.Statut.ACCEPTE)
        link, url = installation_share_link(devis)
        self.assertIsInstance(link, ShareLink)
        self.assertEqual(link.devis_id, devis.id)
        self.assertIn(link.token, url)

    def test_url_carries_parrainage_whatsapp_utm(self):
        devis = self._devis(f'DEV-{MONTH}-PUB6903', Devis.Statut.ACCEPTE)
        _, url = installation_share_link(devis)
        self.assertIn('utm_campaign=parrainage_whatsapp', url)
        self.assertIn('utm_medium=whatsapp', url)

    def test_second_call_reuses_same_sharelink(self):
        devis = self._devis(f'DEV-{MONTH}-PUB6904', Devis.Statut.ACCEPTE)
        link1, _ = installation_share_link(devis)
        link2, _ = installation_share_link(devis)
        self.assertEqual(link1.pk, link2.pk)

    @override_settings(PUBLIC_BASE_URL='https://api.taqinor.ma')
    def test_absolute_url_with_configured_base(self):
        devis = self._devis(f'DEV-{MONTH}-PUB6905', Devis.Statut.ACCEPTE)
        _, url = installation_share_link(devis)
        self.assertTrue(url.startswith('https://api.taqinor.ma/proposition/'))
