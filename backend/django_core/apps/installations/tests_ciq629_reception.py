"""CIQ629 — réception provisoire puis définitive : la définitive n'est
prononcée qu'une fois toutes les réserves levées.
"""
import datetime
import json
from pathlib import Path

from django.test import TestCase

from apps.installations.models import InstallationActivity, Reserve
from apps.installations.selectors import reception_chantier
from apps.installations.services import (
    creer_reserve_chantier, lever_reserve_chantier,
)
from apps.installations.tests_ch3_commissioning import (
    BASE, auth, make_company, make_installation, make_user,
)
from apps.parametres.models import CompanyProfile

_CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
            / 'recette_ci.json')


class ReceptionDefinitiveTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.inst.date_reception = datetime.date(2026, 10, 13)
        self.inst.save(update_fields=['date_reception'])
        self.url = f'{BASE}/chantiers/{self.inst.id}/reception-definitive/'

    def test_reserve_ouverte_definitive_refusee(self):
        creer_reserve_chantier(self.inst, self.user, description='Coffret AC',
                               origine='reception')
        r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Coffret AC', r.data['detail'])
        self.inst.refresh_from_db()
        self.assertIsNone(self.inst.date_reception_definitive)

    def test_avant_provisoire_refusee(self):
        self.inst.date_reception = None
        self.inst.save(update_fields=['date_reception'])
        r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('provisoire', r.data['detail'])

    def test_toutes_levees_date_posee_et_journalisee(self):
        reserve = creer_reserve_chantier(
            self.inst, self.user, description='Coffret AC',
            origine='reception')
        lever_reserve_chantier(reserve, self.user)
        r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertIsNotNone(self.inst.date_reception_definitive)
        self.assertEqual(r.data['date_reception_definitive'],
                         self.inst.date_reception_definitive.isoformat())
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst,
            body__startswith='Réception définitive').exists())
        self.assertEqual(Reserve.objects.filter(statut='ouverte').count(), 0)

    def test_delai_douze_mois_date_prevue(self):
        profil = CompanyProfile.get(self.company)
        profil.delai_reception_definitive_mois = 12
        profil.save()
        bloc = reception_chantier(self.company, self.inst.id)
        self.assertEqual(bloc['date_definitive_prevue'], '2027-10-13')

    def test_delai_non_saisi_date_prevue_null(self):
        bloc = reception_chantier(self.company, self.inst.id)
        self.assertIsNone(bloc['date_definitive_prevue'])
        self.assertTrue(bloc['definitive_possible'])

    def test_autre_societe_404(self):
        autre = make_company()
        inst_autre = make_installation(autre)
        r = self.api.post(
            f'{BASE}/chantiers/{inst_autre.id}/reception-definitive/', {},
            format='json')
        self.assertEqual(r.status_code, 404)
        self.assertIsNone(reception_chantier(self.company, inst_autre.id))

    def test_patch_generique_ne_pose_pas_la_definitive(self):
        self.api.patch(f'{BASE}/chantiers/{self.inst.id}/',
                       {'date_reception_definitive': '2027-01-01'},
                       format='json')
        self.inst.refresh_from_db()
        self.assertIsNone(self.inst.date_reception_definitive)

    def test_bloc_conforme_au_contrat(self):
        contrat = json.loads(_CONTRAT.read_text(encoding='utf-8'))
        modele = contrat['exemple']['reception']
        bloc = reception_chantier(self.company, self.inst.id)
        self.assertEqual(set(bloc), set(modele))
