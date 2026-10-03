"""AGR207 — barème des charges solaires de pompage et règle FDA datée.

Réglages de ``TariffSettings`` pour le calcul INTERNE (jamais un montant
d'aide imprimé pour un client, D-AGR-6) :

* vides par défaut — la lecture rend ``[]`` / ``{}``, aucune valeur suggérée ;
* toute saisie sans ``source`` est refusée en 400 NOMMANT le champ ;
* migration additive (réversible) ;
* forme conforme au contrat partagé ``ventes/contract_samples/
  economie_pompage.json`` (``reglages_lus``).
"""
import json
import unittest
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import migrations
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres import tariff
from authentication.models import Company

User = get_user_model()

CONTRAT = (Path(__file__).resolve().parent.parent / 'ventes'
           / 'contract_samples' / 'economie_pompage.json')
URL = '/api/django/parametres/tarification/'
URL_MAJ = '/api/django/parametres/tarification/update/'


def _reglages_contrat():
    return json.loads(CONTRAT.read_text(encoding='utf-8'))['reglages_lus']


class ValidationPureTest(unittest.TestCase):
    def test_vides_sont_valides_et_lus_vides(self):
        vierge = SimpleNamespace(charges_pompage_solaire=[],
                                 regle_fda_pompage={})
        self.assertEqual(tariff.erreurs_reglages_tarif(vierge), {})
        self.assertEqual(tariff.charges_pompage_depuis_reglages(vierge), [])
        self.assertEqual(tariff.regle_fda_depuis_reglages(vierge), {})
        rien = SimpleNamespace()
        self.assertEqual(tariff.charges_pompage_depuis_reglages(rien), [])
        self.assertEqual(tariff.regle_fda_depuis_reglages(rien), {})

    def test_charge_sans_source_refusee_en_nommant_le_champ(self):
        erreurs = tariff.erreurs_charges_pompage(
            [{'libelle': 'Nettoyage', 'montant_mad_an': 600, 'source': ''}])
        self.assertIn('charges_pompage_solaire', erreurs)
        self.assertIn('source', erreurs['charges_pompage_solaire'])

    def test_regle_fda_sans_source_refusee_en_nommant_le_champ(self):
        erreurs = tariff.erreurs_regle_fda({'taux_pct': 30, 'source': ''})
        self.assertIn('regle_fda_pompage', erreurs)

    def test_regle_fda_valeurs_hors_forme_refusees(self):
        base = {'source': 'Guide FDA édition 2024, p.20-23'}
        for faute in ({'taux_pct': 130}, {'plafond_mad_par_ha': -1},
                      {'base': 'net'}, {'releve_le': '02/10/2026'},
                      {'montant_client': 9000}):
            self.assertIn('regle_fda_pompage',
                          tariff.erreurs_regle_fda({**base, **faute}), faute)

    def test_exemples_du_contrat_acceptes(self):
        reglages = _reglages_contrat()
        charges = reglages['TariffSettings.charges_pompage_solaire']['exemple']
        regle = reglages['TariffSettings.regle_fda_pompage']['exemple']
        self.assertEqual(tariff.erreurs_charges_pompage(charges), {})
        self.assertEqual(tariff.erreurs_regle_fda(regle), {})
        lu = SimpleNamespace(charges_pompage_solaire=charges,
                             regle_fda_pompage=regle)
        self.assertEqual(tariff.charges_pompage_depuis_reglages(lu), charges)
        self.assertEqual(tariff.regle_fda_depuis_reglages(lu), regle)


class ApiReglagesPompageTest(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='agr207-co', defaults={'nom': 'AGR207 Co'})[0]
        self.admin = User.objects.create_user(
            username='agr207_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_lecture_vierge_rend_liste_et_objet_vides(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['charges_pompage_solaire'], [])
        self.assertEqual(resp.data['regle_fda_pompage'], {})

    def test_reglage_sans_source_400_nommant_le_champ(self):
        resp = self.api.patch(URL_MAJ, {'charges_pompage_solaire': [
            {'libelle': 'Visite annuelle', 'montant_mad_an': 400,
             'source': ''}]}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('charges_pompage_solaire', resp.data)
        resp = self.api.patch(URL_MAJ, {'regle_fda_pompage': {
            'taux_pct': 30}}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('regle_fda_pompage', resp.data)

    def test_exemple_du_contrat_aller_retour_identique(self):
        reglages = _reglages_contrat()
        corps = {
            'charges_pompage_solaire':
                reglages['TariffSettings.charges_pompage_solaire']['exemple'],
            'regle_fda_pompage':
                reglages['TariffSettings.regle_fda_pompage']['exemple'],
        }
        resp = self.api.patch(URL_MAJ, corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lu = self.api.get(URL).data
        self.assertEqual(lu['charges_pompage_solaire'],
                         corps['charges_pompage_solaire'])
        self.assertEqual(lu['regle_fda_pompage'], corps['regle_fda_pompage'])
        # Enregistrer → rouvrir → enregistrer sans toucher = identique.
        resp = self.api.patch(URL_MAJ, {
            'charges_pompage_solaire': lu['charges_pompage_solaire'],
            'regle_fda_pompage': lu['regle_fda_pompage']}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.api.get(URL).data['regle_fda_pompage'],
                         corps['regle_fda_pompage'])

    def test_migration_additive_donc_reversible(self):
        module = import_module(
            'apps.parametres.migrations.0112_agr207_reglages_pompage')
        noms = set()
        for op in module.Migration.operations:
            self.assertIsInstance(op, migrations.AddField)
            self.assertTrue(op.reversible)
            noms.add(op.name)
        self.assertEqual(noms, {'charges_pompage_solaire',
                                'regle_fda_pompage'})
