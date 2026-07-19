"""PUB58/59/60/62/67/69 — sélecteurs ventes des boucles de croissance ERP
(Groupe PUB, section PUB-P4). Chaque test prouve un contrat de données pur
(aucun réseau, aucun mock Meta ici — ça vit côté apps/adsengine/tests) :
segmentation devis vu/jamais-ouvert (QJ1), devis expiré + exclusion signée,
cross-sell base installée (entretien/batterie), totaux devis acceptés par
lead (carte chaleur ville), vélocité de signature par mois/mode (saisonnalité
réelle), lien de partage « mon installation » après signature.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, ShareLink
from apps.ventes.selectors import devis_view_tracking_segments

MONTH = timezone.now().strftime('%Y%m')


class DevisViewTrackingSegmentsTests(TestCase):
    """PUB58 — jamais ouvert vs ouvert-non-signé, depuis ShareLink.view_count."""

    def setUp(self):
        self.company = Company.objects.create(nom='PUB58 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='A',
            email='clienta@example.ma', telephone='+212600000001')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead B', email='leadb@example.ma',
            telephone='+212600000002')

    def _devis(self, ref, **kw):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            taux_tva=Decimal('20'), statut=Devis.Statut.ENVOYE, **kw)

    def test_never_opened_bucket(self):
        self._devis(f'DEV-{MONTH}-PUB5801')
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(len(segments['jamais_ouvert']), 1)
        self.assertEqual(segments['jamais_ouvert'][0]['email'],
                         'clienta@example.ma')
        self.assertEqual(segments['ouvert_non_signe'], [])

    def test_opened_not_signed_bucket_uses_view_count(self):
        d = self._devis(f'DEV-{MONTH}-PUB5802')
        ShareLink.objects.create(
            company=self.company, devis=d, view_count=3,
            first_viewed_at=timezone.now())
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(segments['jamais_ouvert'], [])
        self.assertEqual(len(segments['ouvert_non_signe']), 1)

    def test_share_link_with_zero_views_still_never_opened(self):
        d = self._devis(f'DEV-{MONTH}-PUB5803')
        ShareLink.objects.create(company=self.company, devis=d, view_count=0)
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(len(segments['jamais_ouvert']), 1)
        self.assertEqual(segments['ouvert_non_signe'], [])

    def test_contact_prefers_lead_over_client(self):
        d = self._devis(f'DEV-{MONTH}-PUB5804', lead=self.lead)
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(segments['jamais_ouvert'][0]['email'],
                         'leadb@example.ma')
        self.assertTrue(d.lead_id)

    def test_accepted_devis_excluded_entirely(self):
        self._devis(f'DEV-{MONTH}-PUB5805', statut=Devis.Statut.ACCEPTE)
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(segments['jamais_ouvert'], [])
        self.assertEqual(segments['ouvert_non_signe'], [])

    def test_devis_without_any_contact_identifier_skipped(self):
        client_no_contact = Client.objects.create(
            company=self.company, nom='Sans', prenom='Contact')
        self._devis(f'DEV-{MONTH}-PUB5806', client=client_no_contact)
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(segments['jamais_ouvert'], [])
