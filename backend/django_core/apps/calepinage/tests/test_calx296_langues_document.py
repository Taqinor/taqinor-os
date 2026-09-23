"""CALX296 — les documents techniques en français ET en anglais.

Ce qui est prouvé ici :

* chaque code de ``contract_samples/rapport_etude.json`` a un libellé ``fr``
  ET ``en`` (non vides, et distincts d'un code brut) ;
* ``langue_du_document`` sur un calepinage dont le client n'exprime aucune
  préférence rend ``fr`` — la règle est CELLE de
  ``apps.parametres.i18n_resolver`` (délégation, pas une seconde règle) ;
* une demande ``?langue=ar`` rend ``fr`` ET la mention de repli figure dans
  le HTML produit (pied du gabarit) ; ``?langue=en`` rend ``en`` sans mention ;
* un code sans libellé est un défaut de code nommé, jamais un blanc imprimé ;
* en base (CI) : un vrai client resté à la langue par défaut du modèle rend
  ``fr``.

Run (essais purs) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx296_langues_document.py -q
"""
import json
import pathlib
import unittest
from types import SimpleNamespace

from django.test import TestCase

from apps.calepinage.services.documents.gabarit_document import (
    document_html, page_de_garde_html,
)
from apps.calepinage.services.documents.libelles_document import (
    LIBELLES, LibelleInconnu, langue_du_document, libelle, libelles_de_garde,
    resolution_langue,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
SECTIONS = json.loads(
    (RACINE_APP / 'contract_samples' / 'rapport_etude.json')
    .read_text(encoding='utf-8'))['exemple']['sections']

#: Un calepinage SANS client ni société : aucune lecture en base.
NU = SimpleNamespace(company=None, client_id=None)


class CouvertureDesLibellesTest(unittest.TestCase):
    def test_chaque_code_du_rapport_a_fr_et_en(self):
        for section in SECTIONS:
            code = section['code']
            with self.subTest(code=code):
                self.assertIn(code, LIBELLES)
                for langue in ('fr', 'en'):
                    texte = LIBELLES[code].get(langue) or ''
                    self.assertTrue(texte.strip(),
                                    f'« {code} » sans libellé {langue}')
                    self.assertNotEqual(texte, code)

    def test_le_titre_francais_est_celui_du_contrat(self):
        for section in SECTIONS:
            with self.subTest(code=section['code']):
                self.assertEqual(libelle(section['code'], 'fr'),
                                 section['titre'])

    def test_toute_la_table_est_bilingue(self):
        for code, entree in LIBELLES.items():
            with self.subTest(code=code):
                self.assertEqual(sorted(entree), ['en', 'fr'])

    def test_un_code_inconnu_est_un_defaut_nomme(self):
        with self.assertRaises(LibelleInconnu) as capture:
            libelle('section_fantome', 'fr')
        self.assertIn('section_fantome', str(capture.exception))

    def test_l_arabe_retombe_sur_le_francais(self):
        self.assertEqual(libelle('pertes', 'ar'), libelle('pertes', 'fr'))
        self.assertEqual(libelle('pertes', 'en'), 'Loss chain')


class ResolutionDeLangueTest(unittest.TestCase):
    def test_sans_preference_le_document_est_en_francais(self):
        self.assertEqual(langue_du_document(NU), 'fr')
        resolution = resolution_langue(NU)
        self.assertFalse(resolution['repli'])
        self.assertEqual(resolution['mention'], '')

    def test_une_demande_anglaise_est_servie_en_anglais(self):
        self.assertEqual(langue_du_document(NU, 'en'), 'en')
        self.assertEqual(langue_du_document(NU, 'EN '), 'en')

    def test_une_demande_arabe_rend_le_francais_en_le_disant(self):
        resolution = resolution_langue(NU, 'ar')
        self.assertEqual(resolution['langue'], 'fr')
        self.assertEqual(resolution['demandee'], 'ar')
        self.assertTrue(resolution['repli'])
        self.assertIn('arabe', resolution['mention'])
        self.assertEqual(langue_du_document(NU, 'ar'), 'fr')

    def test_la_mention_de_repli_figure_dans_le_html_produit(self):
        resolution = resolution_langue(NU, 'ar')
        html = document_html(
            '<p>corps</p>', titre=libelle('rapport_etude',
                                          resolution['langue']),
            provenance={'hash_entree': 'ab' * 32},
            mentions=[resolution['mention']], langue=resolution['langue'])
        self.assertIn('lang="fr"', html)
        self.assertIn('Document demandé en arabe', html)
        self.assertIn('gabarit-pied', html)

    def test_une_langue_inconnue_est_ignoree(self):
        self.assertEqual(langue_du_document(NU, 'xx'), 'fr')


class GardeTraduiteTest(unittest.TestCase):
    def test_la_garde_anglaise_n_a_aucun_libelle_francais(self):
        html = page_de_garde_html({}, {}, {}, {},
                                  libelles=libelles_de_garde('en'))
        self.assertIn('<s>Customer</s>', html)
        self.assertIn('not provided', html)
        self.assertNotIn('non renseigné', html)


class LangueEnBaseTest(TestCase):
    """Un vrai client resté au défaut du modèle n'exprime aucun choix (CI)."""

    def test_client_sans_preference_rend_fr(self):
        from apps.calepinage.models import Calepinage
        from apps.crm.models import Client
        from authentication.models import Company

        company = Company.objects.create(nom='Langue Co',
                                         slug='langue-co-calx296')
        client = Client.objects.create(company=company, nom='Client FR')
        calepinage = Calepinage.objects.create(company=company, client=client,
                                               titre='Toiture')
        self.assertEqual(langue_du_document(calepinage), 'fr')
        self.assertEqual(langue_du_document(calepinage, 'ar'), 'fr')
        self.assertTrue(resolution_langue(calepinage, 'ar')['repli'])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
