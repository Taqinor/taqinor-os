"""CALX294 — le gabarit société des documents du module (en-tête, pied, logo,
couleurs).

Ce qui est prouvé ici :

* ``styles_de_societe({})`` (aucune base) rend une marque VIDE : les quatre
  clés sont présentes et valent ``''`` ;
* un thème société (``TenantTheme``) fait porter au HTML son ``logo_url`` et
  sa couleur primaire — essai pur sur un thème simulé, puis essai en base sur
  un vrai ``TenantTheme`` (CI) ;
* sans thème, AUCUNE couleur société : le profil ne complète que le nom, et
  un nom de profil resté au défaut du modèle cède la place à la raison
  sociale ;
* une couleur mal formée ou un logo sans schéma d'image sont ABSENTS ;
* l'empreinte et les mentions partent dans le pied COURANT (boîte
  ``@bottom-left``), la marque dans l'en-tête courant (``@top-center``) ;
* aucun code couleur n'est écrit dans le module hors le noir/gris de la
  charte d'impression existante.

Run (essais purs) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx294_gabarit_document.py -q
"""
import pathlib
import re
import unittest
from types import SimpleNamespace

from django.test import TestCase

from apps.calepinage.services.documents.gabarit_document import (
    CHARTE_IMPRESSION, CLES_STYLES, css_du_gabarit, document_html,
    entete_html, pied_html, styles_de_societe,
)

SOURCE = (pathlib.Path(__file__).resolve().parents[1] / 'services'
          / 'documents' / 'gabarit_document.py').read_text(encoding='utf-8')

LOGO = 'https://cdn.exemple.test/marque/logo.png'
PRIMAIRE = '#1a3b8c'
THEME = SimpleNamespace(nom_affichage='Soleil Atlas', logo_url=LOGO,
                        couleur_primaire=PRIMAIRE, couleur_secondaire='#abc')
PROVENANCE = {'hash_entree': 'ab' * 32, 'version_moteur': 'calepinage-1.0.0',
              'calcule_le': '2026-09-19'}


class StylesSansBaseTest(unittest.TestCase):
    def test_une_marque_vide_n_a_que_des_cles_vides(self):
        styles = styles_de_societe({})
        self.assertEqual(sorted(styles), sorted(CLES_STYLES))
        for cle, valeur in styles.items():
            with self.subTest(cle=cle):
                self.assertIn(valeur, (None, ''))

    def test_sans_societe_une_marque_vide(self):
        self.assertEqual(set(styles_de_societe(None).values()), {''})

    def test_le_theme_fournit_logo_couleurs_et_nom(self):
        styles = styles_de_societe({'theme': THEME})
        self.assertEqual(styles['logo_url'], LOGO)
        self.assertEqual(styles['couleur_primaire'], PRIMAIRE)
        self.assertEqual(styles['couleur_secondaire'], '#abc')
        self.assertEqual(styles['nom_affiche'], 'Soleil Atlas')

    def test_sans_theme_aucune_couleur_meme_si_le_profil_en_porte_une(self):
        # Le profil porte un DÉFAUT de modèle pour sa couleur : ce n'est pas
        # une saisie, il n'entre jamais dans un document.
        styles = styles_de_societe({'profil': {
            'nom': 'Soleil Atlas SARL', 'couleur_principale': '#2563EB'}})
        self.assertEqual(styles['nom_affiche'], 'Soleil Atlas SARL')
        self.assertEqual(styles['couleur_primaire'], '')
        self.assertEqual(styles['logo_url'], '')

    def test_une_couleur_mal_formee_est_absente(self):
        for mauvaise in ('red', '#12', '#1234567', '#12345g',
                         '#fff;} body{display:none', 'url(x)'):
            with self.subTest(couleur=mauvaise):
                theme = SimpleNamespace(couleur_primaire=mauvaise)
                self.assertEqual(
                    styles_de_societe({'theme': theme})['couleur_primaire'],
                    '')

    def test_un_logo_sans_schema_d_image_est_absent(self):
        for mauvais in ('logos/societe.png', 'javascript:alert(1)',
                        'https://x.test/a b.png', 'https://x.test/"a.png'):
            with self.subTest(logo=mauvais):
                theme = SimpleNamespace(logo_url=mauvais)
                self.assertEqual(
                    styles_de_societe({'theme': theme})['logo_url'], '')
        data = 'data:image/png;base64,iVBORw0KGgo='
        self.assertEqual(styles_de_societe(
            {'theme': SimpleNamespace(logo_url=data)})['logo_url'], data)


class MiseEnPageTest(unittest.TestCase):
    def test_le_html_porte_le_logo_et_la_couleur_primaire(self):
        html = document_html('<p>corps</p>', titre="Rapport d'étude",
                             styles=styles_de_societe({'theme': THEME}),
                             provenance=PROVENANCE)
        self.assertIn('src="%s"' % LOGO, html)
        self.assertIn(PRIMAIRE, html)
        self.assertIn('Soleil Atlas', html)

    def test_sans_theme_le_document_n_a_ni_logo_ni_couleur_societe(self):
        html = document_html('<p>corps</p>', titre='Note',
                             styles=styles_de_societe({}),
                             provenance=PROVENANCE)
        self.assertNotIn('<img', html)
        self.assertNotIn('class="gabarit-nom"', html)
        couleurs = set(re.findall(r'#[0-9a-fA-F]{3,6}\b', html))
        self.assertLessEqual(couleurs, set(CHARTE_IMPRESSION))

    def test_les_boites_de_marge_sont_posees(self):
        css = css_du_gabarit(styles_de_societe({}))
        self.assertIn('@top-center{content:element(gabarit-entete)', css)
        self.assertIn('@bottom-left{content:element(gabarit-pied)', css)
        self.assertIn('position:running(gabarit-entete)', css)
        self.assertIn('position:running(gabarit-pied)', css)
        self.assertIn('counter(pages)', css)

    def test_les_elements_courants_precedent_le_corps(self):
        html = document_html('<p id="corps">x</p>', titre='Note',
                             styles=styles_de_societe({'theme': THEME}),
                             provenance=PROVENANCE)
        self.assertLess(html.index('gabarit-entete">'),
                        html.index('<p id="corps">'))
        self.assertLess(html.index('gabarit-pied">'),
                        html.index('<p id="corps">'))

    def test_le_pied_porte_l_empreinte_puis_les_mentions_sans_doublon(self):
        pied = pied_html(PROVENANCE, mentions=('Mention A', 'Mention A',
                                               '', 'Mention B'))
        self.assertIn('entrée abababababab', pied)
        self.assertIn('moteur calepinage-1.0.0', pied)
        self.assertEqual(pied.count('Mention A'), 1)
        self.assertLess(pied.index('entrée'), pied.index('Mention B'))

    def test_rien_a_dire_rien_d_imprime(self):
        self.assertEqual(entete_html({}), '')
        self.assertEqual(pied_html({}), '')

    def test_le_texte_de_la_societe_est_echappe(self):
        theme = SimpleNamespace(nom_affichage='<script>x</script>')
        html = entete_html(styles_de_societe({'theme': theme}))
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)


class AucuneCouleurEnDurTest(unittest.TestCase):
    def test_seuls_le_noir_et_le_gris_de_la_charte_sont_ecrits(self):
        trouvees = set(re.findall(r'#[0-9a-fA-F]{3,8}\b', SOURCE))
        self.assertLessEqual(
            trouvees, set(CHARTE_IMPRESSION),
            'code(s) couleur écrit(s) en dur hors charte d\'impression : %s'
            % sorted(trouvees - set(CHARTE_IMPRESSION)))

    def test_aucune_marque_ecrite_en_dur(self):
        self.assertNotRegex(SOURCE, r'TAQINOR|taqinor\.ma')


class StylesEnBaseTest(TestCase):
    """Le même contrat, lu sur de VRAIS enregistrements (CI)."""

    def setUp(self):
        from authentication.models import Company

        self.company = Company.objects.create(nom='Atlas Énergie',
                                              slug='atlas-calx294')

    def test_un_tenant_theme_porte_logo_et_couleur_dans_le_html(self):
        from core.models import TenantTheme

        TenantTheme.objects.create(company=self.company, logo_url=LOGO,
                                   couleur_primaire=PRIMAIRE,
                                   nom_affichage='Atlas Solaire')
        styles = styles_de_societe(self.company)
        self.assertEqual(styles['logo_url'], LOGO)
        self.assertEqual(styles['couleur_primaire'], PRIMAIRE)
        self.assertEqual(styles['nom_affiche'], 'Atlas Solaire')
        html = document_html('<p>x</p>', titre="Rapport d'étude",
                             styles=styles, provenance=PROVENANCE)
        self.assertIn(LOGO, html)
        self.assertIn(PRIMAIRE, html)

    def test_sans_theme_ni_couleur_ni_logo_et_la_raison_sociale_repond(self):
        from apps.parametres.models_company import CompanyProfile

        if not CompanyProfile.objects.filter(company=self.company).exists():
            CompanyProfile.objects.create(company=self.company)
        styles = styles_de_societe(self.company)
        self.assertEqual(styles['logo_url'], '')
        self.assertEqual(styles['couleur_primaire'], '')
        # Le nom du profil resté au DÉFAUT du modèle n'est pas une saisie.
        self.assertEqual(styles['nom_affiche'], 'Atlas Énergie')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
