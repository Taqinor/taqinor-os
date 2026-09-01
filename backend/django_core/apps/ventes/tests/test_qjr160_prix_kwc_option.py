"""QJR160 — le « Prix par kWc » décrit UNE offre.

``etude['prix_kwc']`` divisait ``_ref_total`` — le TTC de l'option 1 (« sans »
quand elle est servable) — par ``puissance_kwc``, recalé quelques lignes plus
haut sur le kWc de l'option 2 (repli documenté ``panneaux_divergents``). Sur un
devis à deux options servables dont les champs PV divergent (22 panneaux sans /
26 avec), le quotient ne décrivait **aucune** des deux offres ; et même sans
divergence, c'était le prix au kWc de l'option 1 seule, imprimé sans dire
laquelle.

Le total et le kWc sont désormais appariés sur la MÊME branche, et la carte est
OMISE quand le document chiffre deux options de tailles différentes.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr160_prix_kwc_option -v 2
"""
from django.test import TestCase

from apps.ventes.tests._quote_engine_common import DEUX_OPTIONS
from apps.ventes.tests.test_quote_engine_deux_optimiseurs import (
    _DevisVariantesMixin)


ETUDE = {
    **DEUX_OPTIONS,
    'kwc': 15.62, 'production_annuelle': 25000, 'conso_annuelle': 30000,
    'economies_annuelles': 21851, 'payback': 3.0, 'prix_kwc': 6543,
}


class TestPrixKwcParOption(_DevisVariantesMixin, TestCase):

    def test_champs_divergents_la_carte_est_omise(self):
        """Deux options servables de TAILLES différentes : aucun prix au kWc
        unique n'a de sens — la carte disparaît plutôt que de mélanger le
        total de l'une et la puissance de l'autre."""
        data = self._build(self._devis(self.DIVERGENT, 'DEV-QJR160-A',
                                       etude_params=dict(ETUDE)))
        self.assertTrue(data['panneaux_divergents'])
        self.assertEqual(data['nb_options'], 2)
        self.assertIsNone(data['etude'].get('prix_kwc'))

    def test_le_pdf_n_imprime_alors_aucun_prix_par_kwc(self):
        from apps.ventes.quote_engine import generate_devis_premium as moteur
        data = self._build(self._devis(self.DIVERGENT, 'DEV-QJR160-B',
                                       etude_params=dict(ETUDE)),
                           {'include_etude': True})
        html = moteur.render_html_for(data)
        self.assertNotIn('Prix par kWc', html)

    def test_champs_egaux_le_quotient_est_celui_d_une_seule_option(self):
        """Sans divergence, le total et le kWc viennent de la MÊME branche."""
        data = self._build(self._devis(self.EGAL_22, 'DEV-QJR160-C',
                                       etude_params=dict(ETUDE)))
        self.assertFalse(data['panneaux_divergents'])
        attendu = round(data['total_sans'] / data['puissance_kwc_sans'])
        self.assertEqual(data['etude']['prix_kwc'], attendu)
        # …et cette branche est bien celle du kWc global (pas de mélange).
        self.assertEqual(data['puissance_kwc_sans'], data['puissance_kwc'])

    def test_la_valeur_stockee_ne_survit_pas_a_l_omission(self):
        """``prix_kwc`` saisi dans l'étude ne peut pas remplacer l'omission :
        un chiffre stocké décrit lui aussi UNE seule taille."""
        data = self._build(self._devis(self.DIVERGENT, 'DEV-QJR160-D',
                                       etude_params=dict(ETUDE)))
        self.assertNotIn('prix_kwc', data['etude'])
