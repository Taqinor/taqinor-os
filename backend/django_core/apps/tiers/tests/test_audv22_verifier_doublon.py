"""AUDV22 (DRAFT165-123/124) — endpoint `verifier-doublon` (ARC20).

`find_by_ice`/`find_by_email` existaient déjà (testés au niveau sélecteur par
`test_arc20_recoupement.py`) mais aucun endpoint ne les exposait AVANT la
création d'un Client/Fournisseur — seul le rapport `doublons/` (admin-only,
a posteriori) les consommait. Ce fichier couvre UNIQUEMENT le câblage HTTP
de la recherche EXACTE anti-doublon ; la logique des sélecteurs reste
couverte par `test_arc20_recoupement.py` (non dupliquée ici).

Run:
    python manage.py test apps.tiers.tests.test_audv22_verifier_doublon -v 2
"""
from testkit.base import TenantAPITestCase

from apps.tiers.models import Tiers


class VerifierDoublonEndpointTests(TenantAPITestCase):
    URL = '/api/django/tiers/tiers/verifier-doublon/'

    def test_ice_match_trouve(self):
        Tiers.objects.create(
            company=self.company, nom='Import Solaire SARL', ice='ICE-42',
            is_fournisseur=True)
        r = self.client_as().get(self.URL, {'ice': 'ice-42'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['ice_matches']), 1)
        self.assertEqual(r.data['ice_matches'][0]['nom'], 'Import Solaire SARL')
        self.assertTrue(r.data['ice_matches'][0]['roles']['fournisseur'])
        self.assertEqual(r.data['email_matches'], [])

    def test_email_match_trouve(self):
        Tiers.objects.create(
            company=self.company, nom='Client X', email='x@example.ma',
            is_client=True)
        r = self.client_as().get(self.URL, {'email': 'X@Example.ma'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['email_matches']), 1)
        self.assertTrue(r.data['email_matches'][0]['roles']['client'])

    def test_aucun_match_liste_vide(self):
        r = self.client_as().get(self.URL, {'ice': 'INCONNU'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['ice_matches'], [])
        self.assertEqual(r.data['email_matches'], [])

    def test_sans_parametre_400(self):
        r = self.client_as().get(self.URL)
        self.assertEqual(r.status_code, 400)

    def test_company_scoped(self):
        Tiers.objects.create(
            company=self.other_company, nom='Autre société', ice='ICE-99')
        r = self.client_as().get(self.URL, {'ice': 'ICE-99'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['ice_matches'], [])
