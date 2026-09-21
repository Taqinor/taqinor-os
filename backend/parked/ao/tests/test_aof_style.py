"""AOF117 — style propre de la fabrique, zéro couplage au moteur de devis.

    python -m unittest apps.ao.tests.test_aof_style -v
"""
import pathlib
import re
import unittest

from apps.ao.fabrique import styles
from apps.ao.fabrique.contexte import construire_contexte, litteraux_chiffres

APP_AO = pathlib.Path(__file__).resolve().parents[1]
DJANGO_CORE = pathlib.Path(__file__).resolve().parents[3]
GABARITS = DJANGO_CORE / 'templates' / 'ao'


def sources_python():
    return sorted(p for p in APP_AO.rglob('*.py')
                  if '__pycache__' not in p.parts)


class TestAucunCouplageAuMoteurDeDevis(unittest.TestCase):
    """Règle #4 : la fabrique AO est un domaine NEUF, sans passerelle."""

    def lignes_d_import(self, fichier):
        """Les seules VRAIES lignes d'import : ancrées en début de ligne.

        Un `re.search` non ancré se déclencherait sur la regex de ce test
        lui-même — un détecteur qui s'auto-dénonce ne détecte plus rien.
        """
        for numero, ligne in enumerate(
                fichier.read_text(encoding='utf-8').splitlines(), 1):
            nue = ligne.strip()
            if re.match(r'^(?:import|from)\s', nue):
                yield numero, nue

    def test_aucun_import_de_quote_engine_dans_apps_ao(self):
        fautes = ['%s:%d %s' % (f.relative_to(DJANGO_CORE), n, ligne)
                  for f in sources_python()
                  for n, ligne in self.lignes_d_import(f)
                  if 'quote_engine' in ligne]
        self.assertEqual(fautes, [], '\n'.join(fautes))

    def test_aucun_import_direct_de_weasyprint(self):
        """ARC11 : tout PDF passe par `core.pdf.render_pdf`."""
        fautes = ['%s:%d %s' % (f.relative_to(DJANGO_CORE), n, ligne)
                  for f in sources_python()
                  for n, ligne in self.lignes_d_import(f)
                  if re.match(r'^(?:import|from)\s+weasyprint', ligne)]
        self.assertEqual(fautes, [], '\n'.join(fautes))

    def test_aucun_gabarit_ao_n_herite_du_moteur_de_devis(self):
        """Ni héritage, ni inclusion d'un gabarit du moteur de devis.

        Le contrôle porte sur les DIRECTIVES (`extends`/`include`), pas sur une
        occurrence de chaîne : un commentaire qui explique le découplage ne
        doit pas compter comme un couplage.
        """
        fautes = []
        for gabarit in sorted(GABARITS.rglob('*.html')):
            texte = gabarit.read_text(encoding='utf-8')
            texte = re.sub(r'\{#.*?#\}|<!--.*?-->', ' ', texte,
                           flags=re.DOTALL)
            for directive in re.findall(
                    r'\{%\s*(?:extends|include)\s+([^%]+?)\s*%\}', texte):
                if re.search(r'quote_engine|pdf/devis|devis_premium',
                             directive):
                    fautes.append('%s : %s' % (gabarit.name, directive))
        self.assertEqual(fautes, [], '\n'.join(fautes))


class TestFeuilleDeStyle(unittest.TestCase):

    def test_feuille_chargee_et_mise_en_cache(self):
        css = styles.css()
        self.assertGreater(len(css), 500)
        self.assertIs(css, styles.css())

    def test_feuille_inconnue_refusee(self):
        with self.assertRaises(styles.FeuilleInconnue):
            styles.css('premium')

    def test_jetons_declares(self):
        css = styles.css()
        for jeton in ('--ao-encre', '--ao-accent', '--ao-police',
                      '--ao-corps', '--ao-marge-gauche', '--ao-trait'):
            self.assertIn(jeton, css, jeton)

    def test_aucune_ressource_externe(self):
        """Un rendu ne dépend ni du réseau ni d'un chemin de fichier."""
        css = styles.css()
        self.assertNotIn('@import', css)
        self.assertEqual(re.findall(r'url\(\s*[\'"]?https?:', css), [])

    def test_grille_administrative_et_non_commerciale(self):
        css = styles.css()
        self.assertIn('size: A4 portrait', css)
        self.assertIn('page-break-inside: avoid', css)
        # Aucun code visuel de plaquette commerciale.
        self.assertNotIn('linear-gradient', css)
        self.assertNotIn('box-shadow', css)

    def test_contexte_style_porte_la_feuille(self):
        self.assertEqual(styles.contexte_style()['css_fabrique'], styles.css())


class TestGabaritDeBase(unittest.TestCase):

    def base(self):
        return (GABARITS / '_base.html').read_text(encoding='utf-8')

    def test_blocs_attendus(self):
        texte = self.base()
        for bloc in ('entete', 'titre', 'corps', 'signature', 'pied'):
            self.assertIn('{% block ' + bloc + ' %}', texte, bloc)

    def test_feuille_injectee_et_non_recopiee(self):
        self.assertIn('{{ css_fabrique }}', self.base())

    def test_empreinte_imprimee_en_pied(self):
        self.assertIn('contexte.empreinte', self.base())

    def test_aucun_chiffre_litteral_dans_le_gabarit(self):
        """AOF111 : un gabarit référence des clés, il n'écrit pas de valeurs."""
        self.assertEqual(litteraux_chiffres(self.base()), ())


class TestDocumentTemoin(unittest.TestCase):
    """« Un document témoin rendu et relu » — sans base et sans WeasyPrint."""

    def contexte(self):
        return construire_contexte({
            'identite': {'raison_sociale': 'TAQINOR SARL',
                         'ville': 'Casablanca', 'ice': '002345678000091',
                         'rc': '123456'},
            'acheteur': {'nom': 'FRDISI'},
            'marche': {'objet': 'Centrale photovoltaïque en toiture',
                       'reference_acheteur': 'AO 12/2026'},
            'montants': {'total_ht': '4166600', 'total_ttc': '4999920'},
        })

    def rendu(self):
        from django.template import Context, Engine
        moteur = Engine(dirs=[str(GABARITS.parent)],
                        libraries={}, builtins=[])
        gabarit = moteur.get_template('ao/_base.html')
        contexte = self.contexte()
        return gabarit.render(Context(dict(
            styles.contexte_style(),
            contexte=contexte,
            piece_titre='Bordereau des prix — document témoin'))), contexte

    def test_le_temoin_se_rend_et_porte_les_bonnes_valeurs(self):
        html, contexte = self.rendu()
        self.assertIn('TAQINOR SARL', html)
        self.assertIn('FRDISI', html)
        self.assertIn('Centrale photovoltaïque en toiture', html)
        self.assertIn('AO 12/2026', html)
        self.assertIn(contexte['empreinte'], html)

    def test_le_temoin_embarque_la_feuille_de_style(self):
        html, _ = self.rendu()
        self.assertIn('--ao-encre', html)
        self.assertIn('<style>', html)

    def test_le_temoin_ne_fuit_aucun_cout(self):
        """Contrôle sur le TEXTE LU, feuille de style et commentaires exclus.

        La feuille emploie le mot « marge » au sens typographique
        (`--ao-marge-gauche`) : scanner le HTML brut ferait rougir le test sur
        du vocabulaire de mise en page. Le ratchet d'étanchéité complet
        (AOF129) applique la même règle sur toutes les pièces.
        """
        html, _ = self.rendu()
        texte = re.sub(r'<style\b.*?</style>|\{#.*?#\}|<!--.*?-->', ' ', html,
                       flags=re.DOTALL | re.IGNORECASE)
        texte = re.sub(r'<[^>]+>', ' ', texte).lower()
        for interdit in ('prix_achat', 'prix d\'achat', 'coût de revient',
                         'marge', 'bénéfice'):
            self.assertNotIn(interdit, texte, interdit)


if __name__ == '__main__':
    unittest.main()
