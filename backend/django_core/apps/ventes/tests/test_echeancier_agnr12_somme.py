"""AGNR12 (C-AGNR-008) — ``valider_echeancier`` refuse un échéancier tout en
pourcentages dont la somme ≠ 100 % (tolérance 0,01) ou qui porte une tranche
vide : 400 en français sous la clé ``echeancier`` qui donne le total trouvé.
Un échéancier déjà stocké hors règle reste LISIBLE (aucune migration) ; tout
échéancier accepté donne des montants ≥ 0 qui somment au TTC.

API réelle (PATCH du devis), fonctions réelles, aucun mock. Test-du-test :
retirer ``controler_somme_echeancier`` de ``valider_echeancier`` ⇒
``test_cas_api`` échoue (70 / 60 / 10 repasse en 200).
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from hypothesis import given, settings
from hypothesis import strategies as st
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import Devis
from apps.ventes.tests import test_qjr_echeancier_validation as Q
from apps.ventes.utils.echeancier import (
    EcheancierInvalide, montants_tranches, tranches_normalisees,
    valider_echeancier,
)


def _pcts(*valeurs):
    return [{'libelle': f'T{i}', 'pct_or_montant': v}
            for i, v in enumerate(valeurs)]


class SommeEcheancierApiTests(TestCase):
    def setUp(self):
        self.company = Q._company()
        self.user = Q._user(self.company)
        self.client_obj = Q._client_obj(self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.devis = Q._devis(self.company, self.client_obj,
                              f'DEV-{Q.MONTH}-AGNR12',
                              statut=Devis.Statut.BROUILLON)

    def _patch(self, echeancier):
        return self.api.patch(
            f'/api/django/ventes/devis/{self.devis.id}/',
            {'echeancier': echeancier}, format='json')

    def test_cas_api(self):
        r = self._patch(_pcts(70, 60, 10))
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Total des tranches : 140 % — il doit faire 100 %.',
                      str(r.data['echeancier']))
        r = self._patch(_pcts(50, 40, 20))
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('110 %', str(r.data['echeancier']))
        r = self._patch(_pcts(40, 60, ''))
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Tranche n°3', str(r.data['echeancier']))
        # CLAUSE PERSISTANCE — un refus ne change rien en base.
        self.devis.refresh_from_db()
        self.assertIsNone(self.devis.echeancier)
        r = self._patch(_pcts(50, 30, 20))
        self.assertEqual(r.status_code, 200, r.data)

    def test_stocke_hors_regle_reste_lisible(self):
        self.devis.echeancier = _pcts(70, 60, 10)
        self.devis.save(update_fields=['echeancier'])
        self.assertEqual(len(tranches_normalisees(self.devis)), 3)


class SommeEcheancierProprieteTests(SimpleTestCase):
    def test_pure(self):
        with self.assertRaises(EcheancierInvalide):
            valider_echeancier(_pcts(70, 60, 10))
        self.assertEqual(len(valider_echeancier(_pcts(50, 30, 20))), 3)

    @settings(max_examples=60, deadline=None)
    @given(st.lists(st.integers(1, 80), min_size=1, max_size=5),
           st.integers(1000, 200000))
    def test_accepte_somme_au_ttc(self, poids, ttc):
        total = sum(poids)
        pcts = [round(p * 100 / total, 2) for p in poids]
        pcts[-1] = round(100 - sum(pcts[:-1]), 2)
        try:
            tranches = valider_echeancier(_pcts(*pcts))
        except EcheancierInvalide:
            return
        montants = montants_tranches(
            Decimal(ttc), [(t['key'], Decimal(str(t['valeur'])))
                           for t in tranches])
        self.assertEqual(sum(montants.values()), Decimal(ttc))
        self.assertTrue(all(m >= 0 for m in montants.values()))
