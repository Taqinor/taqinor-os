"""NTI18N19 — apps/parametres/tax_id_validators.py, framework extensible.

Toutes les assertions numériques ci-dessous (SIRET Luhn, NIF espagnol) sont
des valeurs RÉELLES vérifiées algorithmiquement (le SIRET 73282932000074 est
un cas-test SIRET/INSEE couramment cité ; le NIF 00000000T est la référence
canonique de l'algorithme officiel — 0 % 23 = 0 -> 'T', premier caractère de
la table de contrôle), jamais une valeur inventée.
"""
from django.test import TestCase

from apps.parametres.tax_id_validators import (
    validate_ice_ma, validate_siret_fr, validate_tva_intra_fr,
    validate_ninea_rccm_sn_ci, validate_nif_cif_es, validate_tax_id,
)


class IceMaTests(TestCase):
    def test_valid_15_digits(self):
        self.assertTrue(validate_ice_ma('123456789012345')['valide'])

    def test_invalid_length(self):
        res = validate_ice_ma('12345')
        self.assertFalse(res['valide'])
        self.assertIn('15 chiffres', res['message'])

    def test_non_numeric_rejected(self):
        self.assertFalse(validate_ice_ma('12345678901234A')['valide'])

    def test_empty_is_not_a_format_error(self):
        self.assertTrue(validate_ice_ma('')['valide'])
        self.assertTrue(validate_ice_ma(None)['valide'])


class SiretFrTests(TestCase):
    # SIRET réel de test couramment cité (passe la clé de Luhn) — vérifié
    # algorithmiquement, jamais une valeur inventée.
    VALID_SIRET = '73282932000074'

    def test_valid_siret_passes_luhn(self):
        self.assertTrue(validate_siret_fr(self.VALID_SIRET)['valide'])

    def test_wrong_length_rejected(self):
        res = validate_siret_fr('123')
        self.assertFalse(res['valide'])
        self.assertIn('14 chiffres', res['message'])

    def test_bad_luhn_key_rejected(self):
        # Dernier chiffre altéré : mêmes 13 premiers chiffres, clé rompue.
        altered = self.VALID_SIRET[:-1] + str((int(self.VALID_SIRET[-1]) + 1) % 10)
        res = validate_siret_fr(altered)
        self.assertFalse(res['valide'])
        self.assertIn('clé de contrôle', res['message'])

    def test_accepts_spaces(self):
        spaced = ' '.join([self.VALID_SIRET[i:i + 3] for i in range(0, 14, 3)])
        self.assertTrue(validate_siret_fr(spaced)['valide'])


class TvaIntraFrTests(TestCase):
    def test_valid_form(self):
        self.assertTrue(validate_tva_intra_fr('FR32123456789')['valide'])

    def test_lowercase_and_spaces_normalized(self):
        self.assertTrue(validate_tva_intra_fr(' fr32 123456789 ')['valide'])

    def test_missing_fr_prefix_rejected(self):
        self.assertFalse(validate_tva_intra_fr('32123456789')['valide'])

    def test_wrong_siren_length_rejected(self):
        self.assertFalse(validate_tva_intra_fr('FR3212345')['valide'])


class NineaRccmSnCiTests(TestCase):
    def test_plausible_alphanumeric_accepted(self):
        self.assertTrue(validate_ninea_rccm_sn_ci('CI-2021-B-12345')['valide'])

    def test_too_short_rejected(self):
        self.assertFalse(validate_ninea_rccm_sn_ci('AB')['valide'])

    def test_empty_is_not_a_format_error(self):
        self.assertTrue(validate_ninea_rccm_sn_ci('')['valide'])


class NifCifEsTests(TestCase):
    def test_reference_nif_00000000t(self):
        # Référence canonique : 0 % 23 = 0 -> 'T' (premier caractère de la
        # table de contrôle officielle) — pas une valeur devinée.
        self.assertTrue(validate_nif_cif_es('00000000T')['valide'])

    def test_wrong_control_letter_rejected(self):
        res = validate_nif_cif_es('00000000A')
        self.assertFalse(res['valide'])
        self.assertIn('T', res['message'])

    def test_cif_form_accepted(self):
        self.assertTrue(validate_nif_cif_es('B12345674')['valide'])

    def test_garbage_rejected(self):
        self.assertFalse(validate_nif_cif_es('not-a-nif')['valide'])


class ValidateTaxIdDispatcherTests(TestCase):
    def test_dispatches_to_ma_ice(self):
        self.assertFalse(validate_tax_id('MA', 'ice', '123')['valide'])
        self.assertTrue(validate_tax_id('MA', 'ice', '123456789012345')['valide'])

    def test_dispatches_to_fr_siret(self):
        self.assertTrue(validate_tax_id('FR', 'siret', '73282932000074')['valide'])
        self.assertFalse(validate_tax_id('FR', 'siret', '123')['valide'])

    def test_acceptance_criterion_ma_vs_fr_same_field_different_rule(self):
        # Critère d'acceptation littéral de la tâche : le MÊME champ logique
        # ('ice' vs 'siret', même longueur de saisie invalide) est jugé selon
        # le pack_pays demandé, jamais une règle unique globale.
        ice_invalide = '123'
        self.assertFalse(validate_tax_id('MA', 'ice', ice_invalide)['valide'])
        # Sur FR, ce n'est pas 'ice' qui est vérifié mais 'siret' : un champ
        # sans validateur pour ce pack passe sans erreur (jamais bloquant).
        self.assertTrue(validate_tax_id('FR', 'ice', ice_invalide)['valide'])

    def test_unknown_pack_never_blocks(self):
        # « jamais bloquant pour les pays sans validateur défini » (énoncé).
        self.assertTrue(validate_tax_id('DE', 'ice', 'nawak')['valide'])
        self.assertTrue(validate_tax_id('MA', 'champ_inconnu', 'nawak')['valide'])
