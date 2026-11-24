"""CALX294 — le gabarit société des documents du module (en-tête, pied, logo,
couleurs).

Ce qui est prouvé ici :

* ``styles_de_societe({})`` (aucune base) rend une marque VIDE : toutes les
  clés (``CLES_STYLES``) sont présentes et valent ``''`` ;
* « un seul logo partout » : le logo du devis (``logo_html`` /
  ``logo_garde_html``, par la porte de ventes) passe AVANT celui du thème ;
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
    CHARTE_IMPRESSION, CLES_STYLES, _css_du_gabarit, document_html,
    _entete_html, pied_html, styles_de_societe,
)

SOURCE = (pathlib.Path(__file__).resolve().parents[1] / 'services'
          / 'documents' / 'gabarit_document.py').read_text(encoding='utf-8')

LOGO = 'https://cdn.exemple.test/marque/logo.png'
PRIMAIRE = '#1a3b8c'
THEME = SimpleNamespace(nom_affichage='Soleil Atlas', logo_url=LOGO,
                        couleur_primaire=PRIMAIRE, couleur_secondaire='#abc')
PROVENANCE = {'hash_entree': 'ab' * 32, 'version_moteur': 'calepinage-1.0.0',
              'calcule_le': '2026-09-19'}
#: « Un seul logo partout » (24/11/2026) : la balise du logo du DEVIS, telle
#: que la porte ``ventes.selectors.logos_societe_html`` la rend (taille portée
#: par le style en ligne du moteur).
LOGO_DEVIS = ('<img src="data:image/png;base64,AAAA" alt="logo" '
              'style="max-height:4.50mm;max-width:30.0mm;display:block;">')


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
        css = _css_du_gabarit(styles_de_societe({}))
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
        self.assertEqual(_entete_html({}), '')
        self.assertEqual(pied_html({}), '')

    def test_le_texte_de_la_societe_est_echappe(self):
        theme = SimpleNamespace(nom_affichage='<script>x</script>')
        html = _entete_html(styles_de_societe({'theme': theme}))
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)


class LogoDuDevisTest(unittest.TestCase):
    """« Un seul logo partout » : le logo du devis passe AVANT celui du thème."""

    def test_les_deux_cles_de_logo_du_devis_sont_dans_la_marque(self):
        for cle in ('logo_html', 'logo_garde_html'):
            self.assertIn(cle, CLES_STYLES)
        styles = styles_de_societe({'theme': THEME})
        self.assertEqual(styles['logo_html'], '')
        self.assertEqual(styles['logo_garde_html'], '')

    def test_le_dictionnaire_fournit_la_balise_telle_quelle(self):
        styles = styles_de_societe({'theme': THEME, 'logo_html': LOGO_DEVIS,
                                    'logo_garde_html': LOGO_DEVIS + ' '})
        self.assertEqual(styles['logo_html'], LOGO_DEVIS)
        self.assertEqual(styles['logo_garde_html'], LOGO_DEVIS)

    def test_la_balise_du_devis_est_imprimee_et_celle_du_theme_ne_l_est_pas(
            self):
        html = _entete_html(styles_de_societe(
            {'theme': THEME, 'logo_html': LOGO_DEVIS}), titre='Note')
        self.assertIn(LOGO_DEVIS, html)
        self.assertIn('class="gabarit-logo-devis"', html)
        self.assertNotIn(LOGO, html)
        self.assertNotIn('class="gabarit-logo"', html)
        self.assertEqual(html.count('<img'), 1)
        # Le nom et le titre suivent le logo, dans l'ordre d'avant.
        self.assertLess(html.index(LOGO_DEVIS), html.index('Soleil Atlas'))
        self.assertLess(html.index('Soleil Atlas'), html.index('Note'))

    def test_une_societe_lit_le_logo_par_la_porte_de_ventes_selon_le_role(
            self):
        from unittest import mock

        societe = SimpleNamespace(nom='Atlas Énergie')
        with mock.patch(
                'apps.ventes.selectors.logos_societe_html',
                side_effect=lambda company, roles, **kw:
                {role: '<img alt="%s">' % role for role in roles}) as porte:
            styles = styles_de_societe(societe, theme=None, profil={})
            # L'empreinte des livrables ne lit PAS le fichier du logo.
            sans = styles_de_societe(societe, theme=None, profil={},
                                     logos=False)
        self.assertEqual(styles['logo_html'], '<img alt="entete">')
        self.assertEqual(styles['logo_garde_html'], '<img alt="couverture">')
        # UNE lecture du fichier pour les deux rôles.
        self.assertEqual(porte.call_count, 1)
        self.assertEqual(tuple(porte.call_args.args[1]),
                         ('entete', 'couverture'))
        self.assertEqual((sans['logo_html'], sans['logo_garde_html']),
                         ('', ''))
        # La porte en panne : une marque sans logo du devis, jamais une erreur.
        with mock.patch('apps.ventes.selectors.logos_societe_html',
                        side_effect=RuntimeError('minio')):
            styles = styles_de_societe(societe, theme=None, profil={})
        self.assertEqual((styles['logo_html'], styles['logo_garde_html']),
                         ('', ''))

    def test_un_logo_du_devis_seul_suffit_a_l_entete(self):
        html = _entete_html({'logo_html': LOGO_DEVIS})
        self.assertIn(LOGO_DEVIS, html)

    def test_sans_logo_du_devis_le_comportement_d_avant(self):
        html = _entete_html(styles_de_societe({'theme': THEME}))
        self.assertIn('<img class="gabarit-logo" src="%s"' % LOGO, html)
        self.assertNotIn('gabarit-logo-devis', html)
        self.assertEqual(_entete_html(styles_de_societe({})), '')
        # Une balise vide ou blanche n'est pas un logo.
        self.assertEqual(_entete_html({'logo_html': '  '}), '')

    def test_le_document_porte_le_logo_du_devis(self):
        html = document_html('<p>corps</p>', titre='Note',
                             styles=styles_de_societe(
                                 {'theme': THEME, 'logo_html': LOGO_DEVIS}),
                             provenance=PROVENANCE)
        self.assertIn(LOGO_DEVIS, html)
        self.assertNotIn(LOGO, html)

    def test_la_feuille_ne_contredit_pas_la_taille_de_la_balise_du_moteur(
            self):
        css = _css_du_gabarit(styles_de_societe({}))
        regle = re.search(r'\.gabarit-logo-devis\{([^}]*)\}', css)
        self.assertIsNotNone(regle)
        self.assertNotIn('max-height', regle.group(1))
        self.assertNotIn('max-width', regle.group(1))
        self.assertNotIn('height', regle.group(1))
        self.assertIn('inline-block', regle.group(1))


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
