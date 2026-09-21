"""CALX53 — les coefficients de température NON SOURCÉS, nommés jusqu'au bout.

LE CONSTAT QUE CE TEST VERROUILLE
---------------------------------
``core/electrique/types.py`` pose ``temp_coeff_voc_pct_c = -0.27`` et
``temp_coeff_pmax_pct_c = -0.35`` comme défauts de dataclass, sans citation, et
``services/chaines.py`` ne rend obligatoires que cinq champs de fiche : ces
deux coefficients tombaient donc SILENCIEUSEMENT sur leurs littéraux. C'était
le seul écart mesuré à la discipline « zéro chiffre inventé » du module.

CE QUI EST PROUVÉ ICI (``SimpleTestCase``, aucun accès base) :
1. fiche COMPLÈTE ⇒ aucun avertissement, et l'origine de chaque coefficient
   est ``fiche`` ;
2. fiche SANS coefficients ⇒ un avertissement qui NOMME
   ``temp_coeff_voc_pct_c`` et ``temp_coeff_pmax_pct_c``, publié dans le
   verdict de chaînage (``Conception.alertes``) ET dans les avertissements du
   résultat (``bloc_electrique``) ;
3. les bornes de chaîne restent CALCULÉES (rien n'est omis, rien n'est
   remplacé) — elles sont simplement marquées ;
4. une fiche qui ne publie QU'UN des deux ne fait nommer que celui-là.
"""
from django.test import SimpleTestCase

from apps.calepinage.services.chaines import (
    _avertissement_coefficients_non_sources, bloc_electrique,
    concevoir_par_pan, specs_module,
)
from apps.calepinage.services.electrique import temperatures_site
from core.electrique.types import (
    COEFFICIENTS_TEMPERATURE, ORIGINE_DEFAUT_NON_SOURCE, ORIGINE_FICHE,
)

#: Les cinq champs RÉELLEMENT obligatoires d'une fiche module (CAL124).
MODULE_SANS_COEFFS = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0,
}
MODULE_COMPLET = dict(MODULE_SANS_COEFFS,
                      temp_coeff_voc_pct_c=-0.24,
                      temp_coeff_pmax_pct_c=-0.29)
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3,
}


def _layout(*comptes):
    azimuts = (180.0, 90.0)
    return {'version': 2, 'zones': [
        {'id': 'z%d' % rang, 'label': 'PAN-%d' % rang,
         'geometry': {'count': compte, 'azimuthDeg': azimuts[rang - 1],
                      'tiltDeg': 15.0}}
        for rang, compte in enumerate(comptes, start=1)]}


def _concevoir(module_specs):
    return concevoir_par_pan(
        _layout(12, 8), module_specs=module_specs, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        module_designation='Module d essai 710 Wc',
        onduleur_designation='Onduleur d essai 10 kW')


class OrigineDesCoefficientsTest(SimpleTestCase):
    """La fiche dit d'où vient chaque coefficient — ou personne ne le dit."""

    def test_fiche_complete_tout_vient_de_la_fiche(self):
        module, manquantes = specs_module(MODULE_COMPLET, 'Module d essai')

        self.assertEqual(manquantes, ())
        self.assertEqual(module.coefficients_non_sources, ())
        for nom in COEFFICIENTS_TEMPERATURE:
            self.assertEqual(module.origine_coefficient(nom), ORIGINE_FICHE)
        # Les valeurs SERVIES sont celles de la fiche, pas les défauts.
        self.assertEqual(module.temp_coeff_voc_pct_c, -0.24)
        self.assertEqual(module.temp_coeff_pmax_pct_c, -0.29)

    def test_fiche_muette_les_deux_coefficients_sont_non_sources(self):
        module, manquantes = specs_module(MODULE_SANS_COEFFS, 'Module')

        # Ils ne deviennent PAS obligatoires : la fiche reste exploitable.
        self.assertEqual(manquantes, ())
        self.assertEqual(module.coefficients_non_sources,
                         COEFFICIENTS_TEMPERATURE)
        for nom in COEFFICIENTS_TEMPERATURE:
            self.assertEqual(module.origine_coefficient(nom),
                             ORIGINE_DEFAUT_NON_SOURCE)

    def test_un_seul_coefficient_publie_ne_fait_nommer_que_l_autre(self):
        module, _ = specs_module(
            dict(MODULE_SANS_COEFFS, temp_coeff_voc_pct_c=-0.24), 'Module')

        self.assertEqual(module.coefficients_non_sources,
                         ('temp_coeff_pmax_pct_c',))
        self.assertEqual(module.origine_coefficient('temp_coeff_voc_pct_c'),
                         ORIGINE_FICHE)


class AvertissementTest(SimpleTestCase):
    """Le message NOMME les deux clés de fiche, et il est en français."""

    def test_fiche_complete_aucun_avertissement(self):
        module, _ = specs_module(MODULE_COMPLET, 'Module d essai')

        self.assertEqual(_avertissement_coefficients_non_sources(module), '')

    def test_le_message_nomme_les_deux_coefficients_et_le_module(self):
        module, _ = specs_module(MODULE_SANS_COEFFS, 'Module d essai 710 Wc')

        message = _avertissement_coefficients_non_sources(module)

        self.assertIn('temp_coeff_voc_pct_c', message)
        self.assertIn('temp_coeff_pmax_pct_c', message)
        self.assertIn('Module d essai 710 Wc', message)
        self.assertIn('NON SOURCÉS', message)
        # Le défaut RÉELLEMENT utilisé est dit, en français (virgule).
        self.assertIn('-0,270', message)
        self.assertIn('-0,350', message)

    def test_aucun_module_aucun_avertissement(self):
        self.assertEqual(_avertissement_coefficients_non_sources(None), '')


class VerdictTest(SimpleTestCase):
    """L'origine remonte jusqu'au verdict de chaînage ET au résultat."""

    def test_fiche_complete_le_verdict_ne_dit_rien_des_coefficients(self):
        conception = _concevoir(MODULE_COMPLET)

        self.assertEqual(conception.coefficients_non_sources, ())
        self.assertNotIn('temp_coeff_voc_pct_c',
                         '\n'.join(conception.alertes))
        _bloc, avertissements = bloc_electrique(conception)
        self.assertNotIn('temp_coeff_voc_pct_c', '\n'.join(avertissements))

    def test_fiche_muette_le_verdict_nomme_les_deux_coefficients(self):
        conception = _concevoir(MODULE_SANS_COEFFS)

        self.assertEqual(conception.coefficients_non_sources,
                         COEFFICIENTS_TEMPERATURE)
        message = '\n'.join(conception.alertes)
        self.assertIn('temp_coeff_voc_pct_c', message)
        self.assertIn('temp_coeff_pmax_pct_c', message)

    def test_fiche_muette_le_resultat_publie_l_avertissement(self):
        conception = _concevoir(MODULE_SANS_COEFFS)

        _bloc, avertissements = bloc_electrique(conception)

        message = '\n'.join(avertissements)
        self.assertIn('temp_coeff_voc_pct_c', message)
        self.assertIn('temp_coeff_pmax_pct_c', message)

    def test_les_bornes_restent_calculees_et_le_chainage_publie(self):
        muette = _concevoir(MODULE_SANS_COEFFS)
        complete = _concevoir(MODULE_COMPLET)

        # Rien n'est OMIS : le chaînage existe dans les deux cas.
        for conception in (muette, complete):
            self.assertEqual(conception.manquantes, ())
            self.assertIsNotNone(conception.resultat)
            self.assertTrue(conception.chaines)
            bloc, _avertissements = bloc_electrique(conception)
            self.assertIsNotNone(bloc['chainage'])
            self.assertTrue(bloc['chainage']['chaines'])
        # Et le défaut n'est pas non plus un bloquant : la pose tient.
        self.assertEqual(muette.bloquants, complete.bloquants)
