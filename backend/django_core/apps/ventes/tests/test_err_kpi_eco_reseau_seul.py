"""ERR-QAH-FIG-KPI-ECO-RESEAU-SEUL — sur un devis RÉSEAU SEUL, la vignette KPI
« Économie » de la page 1 imprimait ``eco_a_ann`` (option AVEC batterie) alors
que la carte unique, le −N % et la proposition décrivent l'option SANS.

Aucune base : fixture PURE ``_moteur_fixtures.html_residentiel`` (variante
« sans », mono-option réseau) avec une économie AVEC volontairement
différente de l'économie SANS (DEV-202609-0108 : 8 808 vs 5 829 MAD/an).

Run : ``python manage.py test apps.ventes.tests.test_err_kpi_eco_reseau_seul``
"""
import re

from django.test import SimpleTestCase

from apps.ventes.tests._moteur_fixtures import html_residentiel


class KpiEconomieReseauSeulTests(SimpleTestCase):

    def test_vignette_kpi_egale_la_carte_sans(self):
        h = html_residentiel('sans', eco_s_ann=5829, eco_a_ann=8808)
        marqueurs = re.findall(
            r'data-figure="economie_annuelle" data-figure-option="(\w+)" '
            r'data-figure-value="([^"]*)"', h)
        # La carte « Sans batterie » ET la vignette KPI : deux marqueurs.
        self.assertEqual(len(marqueurs), 2, marqueurs)
        valeurs = {v.replace(' ', '').replace('\xa0', '').replace(' ', '')
                   for _opt, v in marqueurs}
        self.assertEqual(valeurs, {'5829'},
                         f'deux économies annuelles sur la page 1 : {valeurs}')
        self.assertEqual({opt for opt, _v in marqueurs}, {'sans'})
