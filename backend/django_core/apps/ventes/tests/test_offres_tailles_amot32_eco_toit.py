"""AMOT32 (C-AMOT-033) — la taille « Éco » est bornée par le toit : Éco ≤
toit_max et Éco ≤ Max ; une Éco qui ne tient pas COLLAPSE (clé absente) au
lieu d'être proposée. L'ordre Éco ≤ Max ≤ toit est une propriété testée.

Règle réelle (``offres_tailles._champs_des_tailles`` sur
``dimensionnement.plus_grande_contenance``), tableau synthétique comme
``test_offres_tailles``. Test-du-test : retirer ``_borner_eco`` ⇒
``test_cas_vb_mur_physique`` échoue (Éco 30 > Max 26).
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from hypothesis import given, settings
from hypothesis import strategies as st

from apps.ventes import offres_tailles as ot
from apps.ventes.tests.test_offres_tailles import _contexte_factice, _tableau


def _champs(tableau, nb_devis=22, *, capacite=None, physique=None,
            plafond=None):
    devis = SimpleNamespace(
        etude_params={'dimensionnement': {'tableau': tableau}},
        offres_tailles_config=None, reference='DEV-AMOT32')
    contexte = _contexte_factice(devis, capacite=capacite, physique=physique,
                                 plafond=plafond)
    with mock.patch.object(ot, '_tableau_du_devis', return_value=tableau):
        return ot._champs_des_tailles(contexte, nb_devis), contexte


class EcoToitTests(SimpleTestCase):
    TABLEAU = _tableau((10, 9.0), (22, 8.0), (26, 8.5), (30, 5.0))

    def test_cas_vb_mur_physique(self):
        champs, _c = _champs(self.TABLEAU, physique=26)
        self.assertEqual(champs.get('max'), 26)
        self.assertNotIn('eco', champs)

    def test_cas_vb_contenance(self):
        champs, _c = _champs(self.TABLEAU, capacite=24)
        self.assertEqual(champs.get('max'), 24)
        self.assertNotIn('eco', champs)

    def test_eco_qui_tient_reste(self):
        champs, _c = _champs(_tableau((10, 9.0), (16, 5.0), (22, 8.0),
                                      (34, 11.0)), physique=40)
        self.assertEqual(champs.get('eco'), 16)

    @settings(max_examples=60, deadline=None)
    @given(st.lists(st.tuples(st.integers(4, 60),
                              st.floats(2.0, 20.0, allow_nan=False)),
                    min_size=1, max_size=8, unique_by=lambda t: t[0]),
           st.one_of(st.none(), st.integers(8, 60)),
           st.one_of(st.none(), st.integers(8, 60)))
    def test_propriete_ordre(self, paires, physique, capacite):
        champs, contexte = _champs(_tableau(*sorted(paires)),
                                   physique=physique, capacite=capacite)
        eco = champs.get('eco')
        if eco is None:
            return
        if champs.get('max') is not None:
            self.assertLessEqual(eco, champs['max'])
        if contexte.toit_max:
            self.assertLessEqual(eco, int(contexte.toit_max))
