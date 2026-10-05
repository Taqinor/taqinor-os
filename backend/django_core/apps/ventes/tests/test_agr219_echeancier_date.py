"""AGR219 (contrat AGR200) — échéancier agricole : 30/60/10 CONSERVÉ, date
de solde « après récolte » saisissable (``date_prevue`` facultative d'une
tranche). Aucune facture n'est datée automatiquement.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_agr219_echeancier_date"
"""
import json
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.quote_engine.builder import PAYMENT_TERMS_BY_MODE
from apps.ventes.utils.echeancier import (
    EcheancierInvalide, normaliser_tranche, termes_paiement_devis,
)
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'devis_replace_lines_entete.json').read_text(encoding='utf-8'))
ECHEANCIER = CONTRAT['corps_agricole']['entete']['echeancier']
DEFAUT = {'acompte': 30, 'materiel': 60, 'solde': 10}


class TranchePureTests(SimpleTestCase):
    def test_date_valide_conservee(self):
        t = normaliser_tranche({'type': 'solde', 'pct_or_montant': 10,
                                'date_prevue': '2027-03-31'}, 2)
        self.assertEqual(t['date_prevue'], '2027-03-31')

    def test_sans_date_sortie_identique(self):
        t = normaliser_tranche({'type': 'solde', 'pct_or_montant': 10}, 2)
        self.assertEqual(t, {'key': 'solde', 'libelle': 'Solde',
                             'valeur': 10.0, 'unite': 'pct'})
        t = normaliser_tranche({'type': 'solde', 'pct_or_montant': 10,
                                'date_prevue': None}, 2)
        self.assertNotIn('date_prevue', t)

    def test_date_invalide_refusee_en_nommant_le_champ(self):
        for brut in ('31/03/2027', '2027-02-30', 'après récolte', 20270331):
            with self.assertRaises(EcheancierInvalide) as ctx:
                normaliser_tranche({'pct_or_montant': 10,
                                    'date_prevue': brut}, 2)
            self.assertIn('echeancier[2].date_prevue', str(ctx.exception))

    def test_defaut_agricole_reste_30_60_10(self):
        self.assertEqual(PAYMENT_TERMS_BY_MODE['agricole'], DEFAUT)

    def test_termes_sans_date_identiques(self):
        devis = SimpleNamespace(echeancier=[
            {'type': 'acompte', 'pct_or_montant': 30},
            {'type': 'materiel', 'pct_or_montant': 60},
            {'type': 'solde', 'pct_or_montant': 10}],
            mode_installation='agricole', company=None)
        sans = termes_paiement_devis(devis, DEFAUT)
        avec = termes_paiement_devis(devis, DEFAUT, avec_dates=True)
        self.assertEqual(sans, avec)
        self.assertNotIn('dates_prevues', avec)

    def test_termes_exposent_la_date_par_creneau(self):
        devis = SimpleNamespace(echeancier=ECHEANCIER,
                                mode_installation='agricole', company=None)
        termes = termes_paiement_devis(devis, DEFAUT, avec_dates=True)
        self.assertEqual(termes['dates_prevues'],
                         {'acompte': None, 'materiel': None,
                          'solde': '2027-03-31'})
        self.assertNotIn('dates_prevues', termes_paiement_devis(devis, DEFAUT))


class _Base(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = ProduitFactory(company=self.company)
        self.devis = DevisFactory(company=self.company,
                                  mode_installation='agricole')

    def _replace(self, echeancier):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': [{'produit': self.produit.id, 'quantite': '1',
                         'prix_unitaire': '1000'}],
             'entete': {'echeancier': echeancier}}, format='json')


class AllerRetourTests(_Base):
    def test_date_valide_conservee_a_l_aller_retour(self):
        r = self._replace(ECHEANCIER)
        self.assertEqual(r.status_code, 200, r.content)
        lu = self.api.get(f'/api/django/ventes/devis/{self.devis.id}/')
        self.assertEqual(lu.data['echeancier'][2]['date_prevue'],
                         '2027-03-31')
        self.assertIsNone(lu.data['echeancier'][0]['date_prevue'])

    def test_date_invalide_400_nommant_le_champ(self):
        echeancier = [dict(t) for t in ECHEANCIER]
        echeancier[2]['date_prevue'] = '31/03/2027'
        r = self._replace(echeancier)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('echeancier[2].date_prevue',
                      json.dumps(r.data, ensure_ascii=False))

    def test_rendu_expose_les_dates_seulement_si_saisies(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(self.devis, {'pdf_mode': 'full'})
        self.assertNotIn('payment_dates', data)
        self.devis.echeancier = ECHEANCIER
        self.devis.save(update_fields=['echeancier'])
        data = build_quote_data(self.devis, {'pdf_mode': 'full'})
        self.assertEqual(data['payment_dates']['solde'], '2027-03-31')
        self.assertEqual(data['payment_terms'],
                         {'acompte': 30, 'materiel': 60, 'solde': 10})

    def test_dupliquer_conserve_la_date(self):
        from apps.ventes.domain.creation import cloner_devis
        self.devis.echeancier = ECHEANCIER
        self.devis.save(update_fields=['echeancier'])
        copie = cloner_devis(self.devis, user=self.user)
        self.assertEqual(copie.echeancier[2]['date_prevue'], '2027-03-31')
