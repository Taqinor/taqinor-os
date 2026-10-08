"""APRF6 (C-APRF-003) — ``electrical_design`` n'est plus servi par la
représentation LISTE des devis (``GET /ventes/devis/``) ; le DÉTAIL
(``GET /ventes/devis/<id>/``) le sert identique.

Réponses HTTP réelles. Test-du-test : remettre le champ en liste ⇒
``test_liste_sans_conception`` échoue ; le retirer aussi du détail ⇒
``test_detail_avec_conception`` échoue.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ventes/devis/'
CONCEPTION = {
    'strings': [{'id': i, 'panneaux': 12, 'voc_v': 498.5, 'isc_a': 13.9}
                for i in range(40)],
    'protections': {'dc': 'fusible 15 A', 'ac': 'disjoncteur 32 A'},
    'cables': {'dc_mm2': 6, 'ac_mm2': 10},
}


class ListeSansConceptionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='APRF6', slug='aprf6-co')
        cls.user = User.objects.create_user(
            username='aprf6_admin', password='x', role_legacy='admin',
            company=cls.company)
        client = Client.objects.create(
            company=cls.company, nom='Client APRF6',
            email='aprf6@example.com')
        cls.devis = Devis.objects.create(
            company=cls.company, reference='DEV-APRF6-1', client=client,
            created_by=cls.user, electrical_design=CONCEPTION,
            electrical_design_hash='h-aprf6')

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_liste_sans_conception(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        corps = resp.json()
        lignes = corps.get('results', corps) if isinstance(corps, dict) \
            else corps
        ligne = next(x for x in lignes if x['id'] == self.devis.pk)
        self.assertNotIn('electrical_design', ligne)
        # roof_layout reste en liste (lu par DevisRow.jsx).
        self.assertIn('roof_layout', ligne)
        self.assertNotIn('voc_v', json.dumps(ligne))

    def test_detail_avec_conception(self):
        resp = self.api.get('%s%s/' % (URL, self.devis.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['electrical_design'], CONCEPTION)
        # CLAUSE PERSISTANCE — après la liste, la conception est intacte.
        self.api.get(URL)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.electrical_design, CONCEPTION)
