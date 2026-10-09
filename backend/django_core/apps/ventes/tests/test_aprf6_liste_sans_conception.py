"""APRF6 (C-APRF-003) — la conception électrique (``electrical_design``) est
absente de la représentation LISTE des devis (``GET /ventes/devis/``) et
servie identique, octet pour octet, au détail (``GET /ventes/devis/<id>/``).

Test-du-test : remettre le champ en liste ⇒ ``test_liste_sans_conception``
échoue ; le retirer aussi du détail ⇒ ``test_detail_avec_conception``
échoue. Réponses HTTP réelles, aucun mock.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis

User = get_user_model()
URL = '/api/django/ventes/devis/'

CONCEPTION = {
    'version': 1,
    'chaines': [{'mppt': 1, 'panneaux': 9, 'voc_v': 412.5}],
    'protections': {'dc': 'Fusible 15 A', 'ac': 'Disjoncteur 32 A'},
    'cables': [{'troncon': 'DC', 'section_mm2': 6, 'longueur_m': 25}],
}


class ListeSansConceptionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APRF6 SARL')
        self.user = User.objects.create_user(
            username='aprf6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='APRF6')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-APRF6-0001', client=client,
            created_by=self.user, taux_tva=Decimal('20'),
            electrical_design=CONCEPTION,
            roof_layout={'result': {'panels': 9}})

    def _ligne_liste(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        lignes = data.get('results', data) if isinstance(data, dict) else data
        return next(r for r in lignes if r['id'] == self.devis.pk)

    def test_liste_sans_conception(self):
        ligne = self._ligne_liste()
        self.assertNotIn('electrical_design', ligne)
        # Jumeaux : le calepinage reste en liste (lu par DevisRow.jsx).
        self.assertIn('roof_layout', ligne)

    def test_detail_avec_conception(self):
        resp = self.api.get('%s%s/' % (URL, self.devis.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            json.dumps(resp.data['electrical_design'], sort_keys=True),
            json.dumps(CONCEPTION, sort_keys=True))

    def test_liste_puis_detail_conception_intacte(self):
        # CLAUSE PERSISTANCE — ouvrir le devis après la liste.
        self._ligne_liste()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.electrical_design, CONCEPTION)
        resp = self.api.get('%s%s/' % (URL, self.devis.pk))
        self.assertEqual(resp.data['electrical_design'], CONCEPTION)
