"""NTOBS10 — page « Confiance » (trust center) : certifications, sous-
traitants, localisation des données."""
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from core.trust_center import TrustCenterEntry


class SeedTrustCenterTest(TestCase):
    def test_seed_creates_entries(self):
        call_command('seed_trust_center')
        self.assertGreater(TrustCenterEntry.objects.count(), 0)
        self.assertTrue(TrustCenterEntry.objects.filter(
            categorie=TrustCenterEntry.Categorie.LOCALISATION_DONNEES).exists())
        self.assertTrue(TrustCenterEntry.objects.filter(
            categorie=TrustCenterEntry.Categorie.SOUS_TRAITANT).exists())

    def test_seed_is_idempotent(self):
        call_command('seed_trust_center')
        n1 = TrustCenterEntry.objects.count()
        call_command('seed_trust_center')
        n2 = TrustCenterEntry.objects.count()
        self.assertEqual(n1, n2)

    def test_no_unconfirmed_country_claim(self):
        """checked-facts-only : le seed ne prétend PAS connaître le pays
        exact du datacenter tant qu'il n'est pas confirmé par le fondateur."""
        call_command('seed_trust_center')
        hebergement = TrustCenterEntry.objects.get(titre='Hébergement infrastructure')
        self.assertNotIn('Allemagne', hebergement.description)
        self.assertIn('confirmer', hebergement.description)


class TrustCenterPublicEndpointTest(TestCase):
    def test_endpoint_is_public_and_lists_entries(self):
        TrustCenterEntry.objects.create(
            categorie=TrustCenterEntry.Categorie.POLITIQUE,
            titre='Politique de confidentialité')
        resp = APIClient().get('/api/django/core/trust-center/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['titre'], 'Politique de confidentialité')

    def test_no_company_field_ever_exposed(self):
        TrustCenterEntry.objects.create(
            categorie=TrustCenterEntry.Categorie.CERTIFICATION, titre='X')
        resp = APIClient().get('/api/django/core/trust-center/')
        self.assertNotIn('company', resp.data[0])
