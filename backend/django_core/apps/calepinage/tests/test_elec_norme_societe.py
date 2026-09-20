"""CAL130 — la norme électrique applicable, et la règle D5 (pays=ma).

Le cœur du test est le MAROC : sans sélection explicite, aucune norme n'est
supposée et le calcul concerné est OMIS **en le disant**. NF C 15-100 et
UTE C 15-712-1 ne s'impriment pas sur un chantier casablancais qui ne les a
pas choisies. Symétriquement, pour ``pays=fr`` le jeu français est la
sélection naturelle et il s'applique.

Deuxième garantie : chaque coefficient publié porte SA RÉFÉRENCE — et un
coefficient saisi sans référence est REFUSÉ (un chiffre qu'on ne sait pas
rattacher à un texte n'est pas défendable devant un bureau de contrôle).

Le contrat des réglages est relu SUR LE DISQUE : la huitième section doit y
être, sinon l'écran et le serveur divergent (PACT10).

Run :
    python manage.py test apps.calepinage.tests.test_elec_norme_societe -v2
"""
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.norme import (
    NORME_FRANCAISE, coefficients_publies, norme_applicable,
)
from core.electrique import cables

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'parametres_calepinage.json').read_text(encoding='utf-8'))


class RegleD5Test(SimpleTestCase):
    """Pays=ma : aucune norme supposée, calcul OMIS et DIT."""

    def test_maroc_sans_selection_omet_le_calcul(self):
        norme = norme_applicable({'imagerie': {'pays': 'ma'},
                                  'norme_electrique': {}})

        self.assertFalse(norme['applicable'])
        self.assertIsNone(norme['norme'])
        self.assertEqual(norme['coefficients'], {})
        self.assertIn('OMIS', norme['motif'])
        self.assertIn('aucun texte normatif marocain', norme['motif'].lower())

    def test_maroc_avec_selection_explicite_applique_le_jeu_choisi(self):
        norme = norme_applicable({
            'imagerie': {'pays': 'ma'},
            'norme_electrique': {'norme': NORME_FRANCAISE,
                                 'reference': 'NF C 15-100 (choix société)'}})

        self.assertTrue(norme['applicable'])
        self.assertEqual(norme['norme'], NORME_FRANCAISE)
        self.assertEqual(norme['reference'], 'NF C 15-100 (choix société)')

    def test_france_applique_le_jeu_francais_par_juridiction(self):
        norme = norme_applicable({'imagerie': {'pays': 'fr'},
                                  'norme_electrique': {}})

        self.assertTrue(norme['applicable'])
        self.assertEqual(norme['norme'], NORME_FRANCAISE)
        self.assertIn('juridiction', norme['motif'])

    def test_pays_inconnu_ne_suppose_rien(self):
        norme = norme_applicable({'imagerie': {}, 'norme_electrique': {}})

        self.assertFalse(norme['applicable'])

    def test_norme_choisie_sans_reference_est_refusee(self):
        norme = norme_applicable({
            'imagerie': {'pays': 'ma'},
            'norme_electrique': {'norme': 'norme_maison'}})

        self.assertFalse(norme['applicable'])
        self.assertIn('sans référence de texte', norme['motif'])


class CoefficientsTest(SimpleTestCase):
    """Chaque valeur publiée porte sa référence et sa source."""

    def test_les_valeurs_du_noyau_sont_lues_jamais_recopiees(self):
        valeurs, refus = coefficients_publies({})

        self.assertEqual(refus, ())
        self.assertEqual(valeurs['chute_dc_max_pct']['valeur'],
                         cables.CHUTE_MAX_DC_PCT)
        self.assertEqual(valeurs['chute_dc_max_pct']['source'], 'noyau')
        self.assertIn('UTE C 15-712-1',
                      valeurs['chute_dc_max_pct']['reference'])

    def test_une_valeur_saisie_ecrase_celle_du_noyau_avec_sa_reference(self):
        valeurs, refus = coefficients_publies({'coefficients': {
            'chute_dc_max_pct': {'valeur': 2.0,
                                 'reference': 'CPS du marché, art. 8'}}})

        self.assertEqual(refus, ())
        self.assertEqual(valeurs['chute_dc_max_pct']['valeur'], 2.0)
        self.assertEqual(valeurs['chute_dc_max_pct']['source'], 'societe')
        self.assertEqual(valeurs['chute_dc_max_pct']['reference'],
                         'CPS du marché, art. 8')

    def test_une_valeur_sans_reference_est_refusee_et_le_noyau_reste(self):
        valeurs, refus = coefficients_publies({'coefficients': {
            'chute_dc_max_pct': {'valeur': 9.0}}})

        self.assertEqual(len(refus), 1)
        self.assertIn('sans référence', refus[0])
        self.assertEqual(valeurs['chute_dc_max_pct']['valeur'],
                         cables.CHUTE_MAX_DC_PCT)

    def test_un_coefficient_inconnu_est_refuse_en_le_nommant(self):
        _valeurs, refus = coefficients_publies({'coefficients': {
            'chute_inventee': {'valeur': 1.0, 'reference': 'x'}}})

        self.assertIn('chute_inventee', refus[0])


class ContratDesReglagesTest(SimpleTestCase):
    """La huitième section est dans le contrat committé (PACT10)."""

    def test_la_section_est_publiee_dans_les_deux_exemples(self):
        self.assertIn('norme_electrique', CONTRAT['exemple'])
        self.assertIn('norme_electrique', CONTRAT['exemple_vide'])
        self.assertEqual(CONTRAT['exemple_vide']['norme_electrique'], {})

    def test_le_modele_et_le_selecteur_declarent_la_meme_liste(self):
        from apps.calepinage.models import ParametresCalepinage
        from apps.calepinage.selectors import SECTIONS_PARAMETRES

        self.assertEqual(tuple(ParametresCalepinage.SECTIONS),
                         tuple(SECTIONS_PARAMETRES))
        self.assertIn('norme_electrique', SECTIONS_PARAMETRES)
        self.assertEqual(sorted(CONTRAT['exemple']),
                         sorted(SECTIONS_PARAMETRES))
