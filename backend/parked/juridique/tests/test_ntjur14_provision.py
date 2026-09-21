"""NTJUR14 — provision pour risque PROPOSÉE, jamais auto-comptabilisée.

Critère d'acceptation : « ouvrir un dossier à fort montant en jeu NE crée
AUCUNE écriture comptable tant que "proposer-provision" n'a pas été cliqué et
confirmé ».
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.compta.models import Provision
from apps.juridique.models import DossierJuridique

from ._base import auth, make_admin, make_company

URL = '/api/django/juridique/dossiers/'


class ProvisionRisqueTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-p14-co', 'Juridique P14')
        self.admin = make_admin(self.company, 'jur-p14-admin')
        self.api = auth(self.admin)

    def _dossier(self):
        return DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0001',
            titre='Litige à fort enjeu', date_ouverture=date(2026, 5, 1),
            montant_en_jeu=Decimal('900000'),
            montant_risque_estime=Decimal('300000'),
            probabilite_risque=DossierJuridique.ProbabiliteRisque.FORTE)

    def test_ouvrir_un_dossier_a_fort_enjeu_ne_comptabilise_rien(self):
        resp = self.api.post(URL, {
            'titre': 'Litige à fort enjeu',
            'date_ouverture': '2026-05-01',
            'montant_en_jeu': '900000.00',
            'montant_risque_estime': '300000.00',
            'probabilite_risque': 'forte',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(Provision.objects.filter(
            company=self.company).exists())
        self.assertIsNone(resp.data['provision_comptable_id'])

    def test_sans_confirmation_aucune_ecriture_seulement_un_apercu(self):
        dossier = self._dossier()
        resp = self.api.post(
            f'{URL}{dossier.id}/proposer-provision/',
            {'montant': '300000.00', 'motif': 'Risque fort'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('confirme', resp.data)
        self.assertEqual(resp.data['apercu']['montant'], '300000.00')
        self.assertFalse(Provision.objects.filter(
            company=self.company).exists())
        dossier.refresh_from_db()
        self.assertIsNone(dossier.provision_comptable_id)

    def test_avec_confirmation_la_provision_est_comptabilisee(self):
        dossier = self._dossier()
        resp = self.api.post(
            f'{URL}{dossier.id}/proposer-provision/',
            {'montant': '300000.00', 'motif': 'Risque fort',
             'date_dotation': '2026-05-10', 'confirme': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        provision = Provision.objects.get(company=self.company)
        self.assertEqual(provision.nature,
                         Provision.Nature.RISQUES_CHARGES)
        self.assertEqual(provision.montant_dotation, Decimal('300000.00'))
        dossier.refresh_from_db()
        self.assertEqual(dossier.provision_comptable_id, provision.id)

    def test_seconde_dotation_refusee_sur_le_meme_dossier(self):
        dossier = self._dossier()
        corps = {'montant': '300000.00', 'confirme': True}
        self.api.post(f'{URL}{dossier.id}/proposer-provision/', corps,
                      format='json')
        second = self.api.post(f'{URL}{dossier.id}/proposer-provision/',
                               corps, format='json')
        self.assertEqual(second.status_code, 400, second.data)
        self.assertEqual(
            Provision.objects.filter(company=self.company).count(), 1)

    def test_montant_nul_ou_negatif_refuse(self):
        dossier = self._dossier()
        for montant in ('0', '-10'):
            resp = self.api.post(
                f'{URL}{dossier.id}/proposer-provision/',
                {'montant': montant, 'confirme': True}, format='json')
            self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(Provision.objects.filter(
            company=self.company).exists())

    def test_la_provision_n_est_pas_posable_par_patch(self):
        dossier = self._dossier()
        resp = self.api.patch(f'{URL}{dossier.id}/',
                              {'provision_comptable_id': 999}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        dossier.refresh_from_db()
        self.assertIsNone(dossier.provision_comptable_id)
