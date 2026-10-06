"""CIQ627 — recette : la promesse de production du devis est FIGÉE dans la
fiche, et comparée honnêtement (PR, pas des kWh annuels sur un jour d'essai).

Tests COMPORTEMENTAUX : le sélecteur ``ventes.selectors
.promesse_production_devis`` n'est jamais mocké.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.services import (
    MOTIF_PROMESSE_ABSENTE, ensure_commissioning_record)
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/installations'
_CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
            / 'recette_ci.json')


def _etude(production_kwh, pertes_pct):
    return {'etude_ci': {
        'bilan': {'production_kwh': production_kwh},
        'hypotheses': [{'cle': 'pertes_pct', 'valeur': pertes_pct,
                        'statut': 'estimation', 'source': 'PVGIS'}]}}


class PromesseFigeeTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ627', slug='ciq627-co')
        self.user = User.objects.create_user(
            username='ciq627', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Usine', email='ciq627@example.com')

    def _chantier(self, etude_params):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-CIQ627-10',
            client=self.client_obj, statut='accepte', taux_tva=Decimal('20'),
            etude_params=etude_params)
        inst = Installation.objects.create(
            company=self.company, reference='CHT-CIQ627-10', devis=devis,
            type_installation='industriel',
            puissance_installee_kwc=Decimal('100'))
        return devis, inst

    def test_promesse_figee_a_la_premiere_ecriture(self):
        _devis, inst = self._chantier(_etude(180000, 20))
        record = ensure_commissioning_record(inst, self.user)
        self.assertEqual(record.promesse_figee['production_annuelle_kwh'],
                         180000.0)
        self.assertEqual(record.promesse_figee['pr_modelise'], 0.8)
        self.assertEqual(record.promesse_figee['source'], 'estimation moteur')
        self.assertTrue(record.promesse_figee['figee_le'])

    def test_v2_a_200000_fiche_inchangee(self):
        devis, inst = self._chantier(_etude(180000, 20))
        record = ensure_commissioning_record(inst, self.user)
        devis.etude_params = _etude(200000, 15)
        devis.save(update_fields=['etude_params'])
        r = self.api.patch(f'{BASE}/recettes-commissioning/{record.id}/',
                           {'energie_mesuree_kwh': '400'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        record.refresh_from_db()
        self.assertEqual(record.promesse_figee['production_annuelle_kwh'],
                         180000.0)
        self.assertEqual(r.data['comparaison']['pr_modelise'], 0.8)
        self.assertEqual(r.data['energie']['pr_modele_devis'], 0.8)

    def test_devis_sans_etude_omission_avec_motif(self):
        _devis, inst = self._chantier({})
        record = ensure_commissioning_record(inst, self.user)
        self.assertIsNone(record.promesse_figee)
        r = self.api.get(f'{BASE}/chantiers/{inst.id}/recette/')
        comparaison = r.data['comparaison']
        self.assertIsNone(comparaison['promesse_figee'])
        self.assertEqual(comparaison['promesse_motif'], MOTIF_PROMESSE_ABSENTE)
        self.assertIsNone(comparaison['comparaison_annuelle'])
        self.assertEqual(comparaison['comparaison_annuelle_motif'],
                         MOTIF_PROMESSE_ABSENTE)

    def test_pas_de_kwh_annuels_sur_un_jour_d_essai(self):
        _devis, inst = self._chantier(_etude(180000, 20))
        ensure_commissioning_record(inst, self.user)
        r = self.api.get(f'{BASE}/chantiers/{inst.id}/recette/')
        self.assertIsNone(r.data['comparaison']['comparaison_annuelle'])
        self.assertEqual(r.data['comparaison']['comparaison_annuelle_motif'],
                         'Moins de 12 mois de relevés.')

    def test_conforme_au_contrat(self):
        _devis, inst = self._chantier(_etude(180000, 20))
        ensure_commissioning_record(inst, self.user)
        contrat = json.loads(_CONTRAT.read_text(encoding='utf-8'))
        modele = contrat['exemple']['comparaison']
        r = self.api.get(f'{BASE}/chantiers/{inst.id}/recette/')
        self.assertTrue(set(modele) <= set(r.data['comparaison']))
        self.assertTrue(set(modele['promesse_figee'])
                        <= set(r.data['comparaison']['promesse_figee']))
