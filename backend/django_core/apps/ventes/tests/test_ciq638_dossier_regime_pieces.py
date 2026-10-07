"""CIQ638 (moitié serveur) — le dossier 82-21 sert ``regime`` (base légale,
guichet « à confirmer ») et ``pieces`` (par étape, avec leur source), les clés
du contrat ``dossier_8221.json`` que l'écran « Dossiers réglementaires » lit.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import Devis, RegulatoryDossier
from authentication.models import Company

User = get_user_model()
DOSSIERS = '/api/django/ventes/dossiers-reglementaires/'
_CONTRAT = (Path(__file__).resolve().parent.parent
            / 'contract_samples' / 'dossier_8221.json')
EXEMPLE = json.loads(_CONTRAT.read_text(encoding='utf-8'))['exemple']


class DossierRegimePiecesTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ638', slug='ciq638-co')
        user = User.objects.create_user(
            username='ciq638', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user)
        client = Client.objects.create(
            company=self.company, nom='Hôtel', email='ciq638@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-CIQ638-10', client=client,
            statut='accepte', taux_tva=Decimal('20'),
            mode_installation='industriel',
            etude_params={'puissance_kwc': 150})

    def _dossier(self, regime):
        dossier = RegulatoryDossier.objects.create(
            company=self.company, devis=self.devis, regime_8221=regime)
        r = self.api.get(f'{DOSSIERS}{dossier.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_regime_avec_base_legale_et_guichet_a_confirmer(self):
        data = self._dossier('accord_raccordement')
        self.assertEqual(set(data['regime']), set(EXEMPLE['regime']))
        regime = data['regime']
        self.assertEqual(regime['code'], 'accord_raccordement')
        self.assertIn('art. 4', regime['base'])
        self.assertEqual(regime['guichet'], 'distributeur')
        self.assertEqual(regime['guichet_statut'], 'a_confirmer')
        self.assertEqual(regime['puissance_retenue_kw'], 150)
        self.assertFalse(regime['a_qualifier'])

    def test_regime_a_qualifier_sans_code_ni_guichet(self):
        regime = self._dossier('a_qualifier')['regime']
        self.assertTrue(regime['a_qualifier'])
        self.assertIsNone(regime['code'])
        self.assertIsNone(regime['guichet'])

    def test_pieces_par_etape_avec_source(self):
        pieces = self._dossier('accord_raccordement')['pieces']
        cles = set(EXEMPLE['pieces'][0])
        self.assertTrue(cles <= set(pieces[0]))
        par_code = {p['code']: p for p in pieces}
        assurance = par_code['attestation_assurance']
        self.assertEqual(assurance['etape'], 'exploitation')
        self.assertIn('art. 15', assurance['source'])
        for piece in pieces:
            self.assertTrue(piece['source'].strip(), piece['code'])
            self.assertTrue(piece['etape'], piece['code'])

    def test_declaration_sans_assurance(self):
        codes = {p['code']
                 for p in self._dossier('declaration_bt')['pieces']}
        self.assertNotIn('attestation_assurance', codes)

    def test_regime_sans_pieces_liste_vide(self):
        self.assertEqual(self._dossier('a_qualifier')['pieces'], [])
