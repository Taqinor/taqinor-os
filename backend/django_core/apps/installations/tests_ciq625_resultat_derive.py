"""CIQ625 — la fiche de recette IEC 62446-1 : ``resultat`` est CALCULÉ par le
serveur, un essai raté ne laisse plus passer « conforme ».

Run :
    python manage.py test apps.installations.tests_ciq625_resultat_derive
"""
from decimal import Decimal

from django.test import TestCase

from apps.installations.models import CommissioningRecord, Installation
from apps.installations.services import (
    ESSAIS_RECETTE, ensure_commissioning_record, seed_stages,
    verifier_transition_statut,
)
from apps.installations.tests_ch3_commissioning import (
    BASE, auth, make_company, make_installation, make_user,
)

TOUS_VRAIS = {champ: True for champ in ESSAIS_RECETTE}


class ResultatDeriveTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)
        self.api = auth(make_user(self.company))
        self.inst = make_installation(self.company)
        self.rec = ensure_commissioning_record(self.inst)
        self.url = f'{BASE}/recettes-commissioning/{self.rec.id}/'

    def _patch(self, corps):
        return self.api.patch(self.url, corps, format='json')

    def test_isolement_faux_et_conforme_demande_non_conforme_gate_bloque(self):
        """ROUGE AVANT : le PATCH rangeait « conforme » et ouvrait le gate."""
        corps = dict(TOUS_VRAIS, isolement_ok=False, resultat='conforme')
        r = self._patch(corps)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['resultat'], 'non_conforme')
        self.assertFalse(r.data['passe'])
        self.rec.refresh_from_db()
        self.assertEqual(self.rec.resultat,
                         CommissioningRecord.Resultat.NON_CONFORME)
        self.inst.refresh_from_db()
        raisons = verifier_transition_statut(
            self.inst, Installation.Statut.INSTALLE)
        self.assertTrue(any('62446' in r for r in raisons), raisons)

    def test_tous_les_essais_vrais_conforme(self):
        r = self._patch(TOUS_VRAIS)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['resultat'], 'conforme')
        self.inst.refresh_from_db()
        self.assertEqual(verifier_transition_statut(
            self.inst, Installation.Statut.INSTALLE), [])

    def test_un_essai_non_renseigne_en_cours(self):
        corps = dict(TOUS_VRAIS)
        corps.pop('performance_ok')
        r = self._patch(dict(corps, resultat='conforme'))
        self.assertEqual(r.data['resultat'], 'en_cours')

    def test_reserves_avec_un_essai_faux_400_fr(self):
        r = self._patch(dict(TOUS_VRAIS, polarite_ok=False,
                             resultat='reserves'))
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('réserves', str(r.data['resultat']))
        self.rec.refresh_from_db()
        self.assertEqual(self.rec.resultat,
                         CommissioningRecord.Resultat.EN_COURS)
        self.assertIsNone(self.rec.polarite_ok)

    def test_reserves_quand_tous_vrais_est_le_seul_choix_humain(self):
        r = self._patch(dict(TOUS_VRAIS, resultat='reserves'))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['resultat'], 'reserves')
        self.assertTrue(r.data['passe'])
        # Un PATCH sans « resultat » ne rétrograde pas le choix…
        r = self._patch({'observations': 'RAS'})
        self.assertEqual(r.data['resultat'], 'reserves')
        # …mais un essai qui tombe le fait tomber, sans 400.
        r = self._patch({'isolement_ok': False})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['resultat'], 'non_conforme')

    def test_un_string_iv_en_defaut_rend_la_fiche_non_conforme(self):
        # CIQ626 — le défaut I-V est jugé contre le seuil SAISI par la
        # société (aucune tolérance codée) : 5 % saisi ici explicitement.
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.get(self.rec.company)
        profil.recette_ecart_pmax_pct = Decimal('5')
        profil.save()
        self._patch(TOUS_VRAIS)
        r = self.api.post(f'{self.url}ajouter-iv/', {
            'string_label': 'S1', 'pmax_mesure_w': '700',
            'pmax_attendu_w': '1000'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.rec.refresh_from_db()
        self.assertEqual(self.rec.resultat,
                         CommissioningRecord.Resultat.NON_CONFORME)
