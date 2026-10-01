"""
QJR600 (Groupe QJR5) — la règle « devis automatique prêt » est SERVIE
structurée : bloc ``devis_auto`` du lead = {pret, manquants, message,
manquants_detail: [{champ, label}], requis: [[…]]}.

Contrat partagé : ``apps/crm/contract_samples/devis_auto_pret.json`` (QJR509).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_devis_auto_contrat"
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.devis_auto import (
    champs_manquants, champs_manquants_detail, champs_requis)
from apps.crm.models import Lead
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'devis_auto_pret.json').read_text(encoding='utf-8'))


class TestDevisAutoContrat(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR600 Co', slug='qjr600-co')
        self.user = User.objects.create_user(
            username='qjr600_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _bloc(self, lead):
        r = self.api.get(f'/api/django/crm/leads/{lead.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['devis_auto']

    def test_industriel_bill_kwh_seul_est_pret_et_requis_porte_le_groupe(self):
        lead = Lead.objects.create(
            company=self.company, nom='Usine', type_installation='industriel',
            bill_kwh=500)
        bloc = self._bloc(lead)
        self.assertEqual(bloc['manquants_detail'], [])
        self.assertTrue(bloc['pret'])
        self.assertIn(['conso_mensuelle_kwh', 'bill_kwh'], bloc['requis'])

    def test_residentiel_facture_hiver_zero_est_manquant(self):
        lead = Lead.objects.create(
            company=self.company, nom='Maison', facture_hiver=Decimal('0'))
        bloc = self._bloc(lead)
        self.assertFalse(bloc['pret'])
        self.assertEqual([e['champ'] for e in bloc['manquants_detail']],
                         ['facture_hiver'])

    def test_bloc_porte_les_cles_du_contrat(self):
        lead = Lead.objects.create(
            company=self.company, nom='Usine 2', type_installation='commercial')
        bloc = self._bloc(lead)
        self.assertTrue(set(CONTRAT['exemple']['devis_auto']) <= set(bloc))
        detail = bloc['manquants_detail'][0]
        self.assertEqual(
            set(detail), set(CONTRAT['exemple']['devis_auto']['manquants_detail'][0]))
        self.assertEqual(bloc['requis'],
                         CONTRAT['exemple']['devis_auto']['requis'])

    def test_agricole_requis_conforme_au_contrat(self):
        lead = Lead.objects.create(
            company=self.company, nom='Ferme', type_installation='agricole')
        attendu = CONTRAT['exemple_agricole']['devis_auto']
        self.assertEqual(champs_requis(lead), attendu['requis'])
        self.assertEqual([e['champ'] for e in champs_manquants_detail(lead)],
                         [e['champ'] for e in attendu['manquants_detail']])

    def test_manquants_libelles_inchanges(self):
        lead = Lead.objects.create(
            company=self.company, nom='Été', facture_hiver=Decimal('500'),
            ete_differente=True)
        self.assertEqual(champs_manquants(lead), ['facture été'])
        self.assertEqual(champs_requis(lead),
                         [['facture_hiver'], ['facture_ete']])
