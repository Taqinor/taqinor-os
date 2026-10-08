"""AMOT30 (C-AMOT-031) — le moteur horaire des cartes Éco/Max et du détail
de taille est appelé avec LES MÊMES arguments que le devis (barème société,
charges fixes, jour de référence, source de conso) via UN constructeur
``etude_horaire.kwargs_moteur_horaire(entrees)`` ; ``tranches`` et
``charges_fixes_mad`` sont obligatoires dans ``calculer_etude_horaire``.

Rejoue VB (chemin offres_tailles 5 228,0 contre 6 155,95 pour le devis au
barème société +20 %).

Test-du-test : retirer ``tranches`` de ``kwargs_moteur_horaire`` ⇒
``test_constructeur_porte_le_bareme`` échoue.
"""
import inspect
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes import etude_horaire as EH
from apps.ventes import offres_tailles as OT

ENTREES = {
    'conso_kwh_mensuelles': [300.0] * 12, 'ville': 'Casablanca',
    'lat': None, 'lon': None, 'occupation': 'presence_jour',
    'equipements': None, 'tranches': [{'jusqu_a': 100, 'prix': 1.2}],
    'charges_fixes_mad': 22.0, 'jour_reference': '2026-10-08',
    'source_conso': 'facture_hiver',
}


class KwargsMoteurTests(SimpleTestCase):
    def test_constructeur_porte_le_bareme(self):
        kw = EH.kwargs_moteur_horaire(ENTREES)
        for cle in ('tranches', 'charges_fixes_mad', 'jour_reference',
                    'source_conso', 'conso_kwh_mensuelles', 'ville'):
            self.assertEqual(kw[cle], ENTREES[cle], cle)

    def test_tranches_obligatoires(self):
        with self.assertRaises(TypeError):
            EH.calculer_etude_horaire(kwc=5.0, conso_kwh_mensuelles=[300] * 12)
        params = inspect.signature(EH.calculer_etude_horaire).parameters
        self.assertIs(params['tranches'].default, inspect.Parameter.empty)
        self.assertIs(params['charges_fixes_mad'].default,
                      inspect.Parameter.empty)

    def _contexte(self, regles):
        ctx = OT._Contexte.__new__(OT._Contexte)
        ctx.devis = SimpleNamespace(regles_calcul=regles)
        ctx.entrees = ENTREES
        return ctx

    def test_cartes_et_devis_memes_arguments(self):
        kw = self._contexte(2).etude_kwargs
        self.assertEqual(kw, EH.kwargs_moteur_horaire(ENTREES))
        self.assertNotIn('source_conso', self._contexte(2).balayage_kwargs)

    def test_regles_d_origine_arguments_d_hier(self):
        kw = self._contexte(1).etude_kwargs
        self.assertIsNone(kw['tranches'])
        self.assertIsNone(kw['charges_fixes_mad'])
