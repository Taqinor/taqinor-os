"""CIQ626 — recette C&I : irradiance, énergie, PR « à titre d'information »,
thermographie, terre, limitation d'injection, découplage, échantillon I-V,
instrument par essai ; plus de tolérance 5 % inventée.
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.installations.models import CommissioningIVReading, Installation
from apps.installations.services import (
    compute_iv_ecart, ensure_commissioning_record)
from apps.outillage.models import Outillage
from apps.parametres.models import CompanyProfile
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/installations'
_CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
            / 'recette_ci.json')


class RecetteCITest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ626', slug='ciq626-co')
        self.user = User.objects.create_user(
            username='ciq626', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-CIQ626-10',
            type_installation='industriel',
            puissance_installee_kwc=Decimal('100'))
        self.record = ensure_commissioning_record(self.inst, self.user)

    def _reglages(self, **valeurs):
        profil = CompanyProfile.get(self.company)
        for champ, valeur in valeurs.items():
            setattr(profil, champ, valeur)
        profil.save()

    def _reading(self, mesure):
        reading = CommissioningIVReading(
            record=self.record, company=self.company, string_label='S1',
            pmax_mesure_w=Decimal(mesure), pmax_attendu_w=Decimal('1000'))
        return compute_iv_ecart(reading)

    def test_seuil_non_saisi_ecart_affiche_sans_verdict(self):
        reading = self._reading('900')
        self.assertEqual(reading.ecart_pmax_pct, Decimal('-10.00'))
        self.assertIsNone(reading.defaut_detecte)

    def test_seuil_cinq_ecart_moins_six_defaut(self):
        self._reglages(recette_ecart_pmax_pct=Decimal('5'))
        self.assertTrue(self._reading('940').defaut_detecte)
        self.assertFalse(self._reading('960').defaut_detecte)

    def test_pr_mesure_servi_avec_son_libelle(self):
        r = self.api.patch(
            f'{BASE}/recettes-commissioning/{self.record.id}/',
            {'energie_mesuree_kwh': '410', 'irradiation_kwh_m2': '5',
             'irradiance_poa_wm2': '780', 'irradiance_source': 'mesuree'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['energie']['pr_mesure'], 0.82)
        self.assertEqual(r.data['energie']['libelle'], "à titre d'information")
        self.assertEqual(r.data['comparaison']['pr_libelle'],
                         "à titre d'information")
        self.assertNotIn('pr_sous_seuil_interne', r.data['comparaison'])
        self._reglages(recette_pr_seuil_interne=Decimal('85'))
        r = self.api.get(f'{BASE}/chantiers/{self.inst.id}/recette/')
        self.assertTrue(r.data['comparaison']['pr_sous_seuil_interne'])

    def test_instrument_expire_sur_isolement_avertit(self):
        outil = Outillage.objects.create(
            company=self.company, nom='Mégohmmètre',
            intervalle_calibration_mois=12,
            date_prochaine_calibration=datetime.date(2025, 1, 1))
        r = self.api.patch(
            f'{BASE}/recettes-commissioning/{self.record.id}/',
            {'instruments_par_essai': {'isolement': outil.id}},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['instruments_par_essai'],
                         {'isolement': {'instrument_id': outil.id,
                                        'etalonnage_expire': True}})
        self.assertTrue(any('isolement' in a for a
                            in r.data['comparaison']['avertissements']))

    def test_instrument_d_une_autre_societe_refuse(self):
        autre = Company.objects.create(nom='Autre', slug='ciq626-autre')
        outil = Outillage.objects.create(company=autre, nom='Testeur')
        r = self.api.patch(
            f'{BASE}/recettes-commissioning/{self.record.id}/',
            {'instruments_par_essai': {'iv': outil.id}}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_essais_ci_sans_objet_par_defaut_et_non_ok_est_faux(self):
        self.assertEqual(self.record.limitation_injection_etat, 'sans_objet')
        self.assertEqual(self.record.decouplage_etat, 'sans_objet')
        r = self.api.patch(
            f'{BASE}/recettes-commissioning/{self.record.id}/',
            {'decouplage_etat': 'non_ok'}, format='json')
        self.assertEqual(r.data['resultat'], 'non_conforme')

    def test_sortie_conforme_au_contrat(self):
        contrat = json.loads(_CONTRAT.read_text(encoding='utf-8'))
        modele = contrat['exemple']['record']
        r = self.api.get(f'{BASE}/chantiers/{self.inst.id}/recette/')
        for cle in ('irradiance', 'energie', 'thermographie',
                    'limitation_injection', 'decouplage', 'echantillon_iv',
                    'instruments_par_essai', 'terre_installation_ohm'):
            self.assertIn(cle, r.data)
        for section in ('irradiance', 'energie', 'thermographie',
                        'limitation_injection', 'decouplage',
                        'echantillon_iv'):
            self.assertTrue(set(modele[section]) <= set(r.data[section]),
                            section)
        for cle in ('ecart_iv_pmax_pct', 'seuil_ecart_pmax_pct',
                    'defaut_detecte'):
            self.assertIn(cle, r.data['comparaison'])
