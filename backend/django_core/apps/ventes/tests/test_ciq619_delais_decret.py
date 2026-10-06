"""CIQ619 — dossier 82-21 : étude du distributeur, capacité réservée,
convention et exploitation, avec les délais MAXIMAUX du décret 2.25.100.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import Devis, RegulatoryDossier
from apps.ventes.selectors_reglementaire import (
    paiement_etude_limite, resume_dossier_8221, travaux_limite)
from authentication.models import Company

User = get_user_model()
DOSSIERS = '/api/django/ventes/dossiers-reglementaires/'
CALENDRIER = '/api/django/ventes/calendrier-reglementaire/'
_CONTRAT = (Path(__file__).resolve().parent.parent / 'contract_samples'
            / 'dossier_8221.json')


class DelaisDecretTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ619', slug='ciq619-co')
        self.user = User.objects.create_user(
            username='ciq619', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        client = Client.objects.create(
            company=self.company, nom='Usine', email='ciq619@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-CIQ619-10', client=client,
            statut='accepte', taux_tva=Decimal('20'))

    def _dossier(self, regime='accord_raccordement', **champs):
        return RegulatoryDossier.objects.create(
            company=self.company, devis=self.devis, regime_8221=regime,
            **champs)

    def test_accord_convention_plus_deux_ans(self):
        dossier = self._dossier(convention_signee_le=date(2027, 3, 1))
        self.assertEqual(travaux_limite(dossier), date(2029, 3, 1))
        self.assertEqual(resume_dossier_8221(dossier)['travaux_limite_le'],
                         '2029-03-01')

    def test_declaration_recepisse_plus_douze_mois(self):
        dossier = self._dossier('declaration_bt',
                                date_decision=date(2027, 1, 31))
        self.assertEqual(travaux_limite(dossier), date(2028, 1, 31))

    def test_frais_notifies_paiement_limite_dix_jours(self):
        dossier = self._dossier(etude_frais_notifies_le=date(2027, 3, 1))
        self.assertEqual(paiement_etude_limite(dossier), date(2027, 3, 11))
        self.assertEqual(
            resume_dossier_8221(dossier)['etude']['paiement_limite_le'],
            '2027-03-11')

    def test_sans_date_aucune_echeance(self):
        dossier = self._dossier()
        self.assertIsNone(travaux_limite(dossier))
        self.assertIsNone(paiement_etude_limite(dossier))

    def test_calendrier_alerte_imminent(self):
        today = timezone.now().date()
        self._dossier(etude_frais_notifies_le=today - timedelta(days=3))
        resp = self.api.get(CALENDRIER)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['validite_accord_jours'])
        ligne = next(e for e in resp.data['echeances']
                     if e['type'] == 'paiement_etude')
        self.assertEqual(ligne['statut_alerte'], 'imminent')
        self.assertIn('art. 13', ligne['libelle'])
        # Plus de validité d'accord supposée à 365 jours.
        self.assertNotIn('validite_accord',
                         {e['type'] for e in resp.data['echeances']})

    def test_etude_payee_retire_l_echeance(self):
        today = timezone.now().date()
        self._dossier(etude_frais_notifies_le=today, etude_payee_le=today)
        resp = self.api.get(CALENDRIER)
        self.assertNotIn('paiement_etude',
                         {e['type'] for e in resp.data['echeances']})

    def test_champs_saisis_et_resume_conforme_au_contrat(self):
        dossier = self._dossier()
        r = self.api.patch(f'{DOSSIERS}{dossier.id}/', {
            'etude_conclusion': 'favorable', 'capacite_etat': 'provisoire',
            'capacite_date': '2027-02-01',
            'convention_signee_le': '2027-03-01'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        resume = r.data['resume']
        contrat = json.loads(_CONTRAT.read_text(encoding='utf-8'))
        modele = contrat['exemple']['resume']
        self.assertTrue(set(modele) <= set(resume))
        self.assertTrue(set(modele['etude']) <= set(resume['etude']))
        self.assertEqual(resume['capacite'],
                         {'etat': 'provisoire', 'date': '2027-02-01'})
        self.assertEqual(resume['travaux_limite_le'], '2029-03-01')
