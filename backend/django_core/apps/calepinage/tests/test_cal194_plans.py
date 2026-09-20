"""CAL194 — plan de toiture et plan de masse, dérivés de la MÊME géométrie.

Ce qui est prouvé (essais PURS — ni base, ni WeasyPrint) :

* le plan de TOITURE montre la toiture SANS les modules (c'est ce qui le
  distingue de la vue d'implantation) ;
* le plan de MASSE montre la parcelle SAISIE et l'emprise du bâtiment ;
* SANS parcelle saisie, le plan de masse est REFUSÉ en nommant la saisie
  manquante — jamais dessiné avec une limite plausible. Une limite de parcelle
  est une affirmation juridique, pas une estimation ;
* l'échelle NOMMÉE est calculée du tracé et porte sa condition de validité ;
  la barre graphique reste là, parce qu'un tirage réduit rend la fraction
  fausse ;
* les trois plans partagent la même projection, donc ils ne peuvent pas se
  contredire.

Run :
    python manage.py test apps.calepinage.tests.test_cal194_plans -v2
"""
import copy

from django.test import SimpleTestCase

from apps.calepinage.services.planche import (
    CONTENU_IMPLANTATION, CONTENU_MASSE, CONTENU_TOITURE, PlancheRefusee,
    echelle_nommee, geometrie_de_planche, mention_d_echelle, rendre_plan_svg,
    svg_de_planche,
)

from .test_cal171_planche import LAYOUT
from .test_cal173_empreinte import MOMENT, FauxCalepinage

#: Une parcelle SAISIE (sommets en [lng, lat], comme les pans).
PARCELLE = [[-7.6002, 33.4998], [-7.5997, 33.4998], [-7.5997, 33.5003],
            [-7.6002, 33.5003]]


def layout_avec_parcelle():
    layout = copy.deepcopy(LAYOUT)
    layout['parcelle'] = PARCELLE
    return layout


class ParcelleTest(SimpleTestCase):
    def test_sans_parcelle_la_geometrie_n_en_invente_aucune(self):
        self.assertEqual(geometrie_de_planche(LAYOUT)['parcelle'], [])

    def test_une_parcelle_saisie_est_projetee_en_metres(self):
        parcelle = geometrie_de_planche(layout_avec_parcelle())['parcelle']
        self.assertEqual(len(parcelle), 4)
        largeur = max(p[0] for p in parcelle) - min(p[0] for p in parcelle)
        self.assertGreater(largeur, 20.0)
        self.assertLess(largeur, 100.0)

    def test_les_trois_graphies_de_parcelle_sont_admises(self):
        for cle in ('parcelle', 'parcel', 'parcelleCadastrale'):
            layout = copy.deepcopy(LAYOUT)
            layout[cle] = PARCELLE
            self.assertEqual(len(geometrie_de_planche(layout)['parcelle']), 4,
                             'graphie « %s » non lue' % cle)


class PlanDeMasseTest(SimpleTestCase):
    def test_sans_parcelle_le_plan_de_masse_est_refuse_en_la_nommant(self):
        with self.assertRaises(PlancheRefusee) as capture:
            rendre_plan_svg(FauxCalepinage(), contenu=CONTENU_MASSE,
                            moment=MOMENT)
        self.assertEqual(capture.exception.champ, 'parcelle')
        self.assertIn('parcelle', str(capture.exception).lower())

    def test_avec_parcelle_le_plan_de_masse_se_produit(self):
        svg = rendre_plan_svg(
            FauxCalepinage(roof_layout=layout_avec_parcelle()),
            contenu=CONTENU_MASSE, moment=MOMENT)
        self.assertIn('Plan de masse', svg)
        self.assertIn('width="420mm"', svg)

    def test_le_plan_de_masse_montre_la_parcelle_entiere(self):
        geometrie = geometrie_de_planche(layout_avec_parcelle())
        masse = svg_de_planche(geometrie, contenu=CONTENU_MASSE)
        implantation = svg_de_planche(geometrie,
                                      contenu=CONTENU_IMPLANTATION)
        # La parcelle est plus large que le bâtiment : le plan de masse est
        # donc dessiné à une échelle PLUS PETITE que l'implantation.
        self.assertNotEqual(masse, implantation)
        self.assertIn('stroke-dasharray="2 1"', masse)

    def test_le_plan_de_masse_ne_montre_pas_les_modules(self):
        svg = svg_de_planche(geometrie_de_planche(layout_avec_parcelle()),
                             contenu=CONTENU_MASSE)
        self.assertNotIn('#c8e6c9', svg)


class PlanDeToitureTest(SimpleTestCase):
    def setUp(self):
        self.geometrie = geometrie_de_planche(LAYOUT)

    def test_le_plan_de_toiture_ne_porte_aucun_module(self):
        toiture = svg_de_planche(self.geometrie, contenu=CONTENU_TOITURE)
        implantation = svg_de_planche(self.geometrie,
                                      contenu=CONTENU_IMPLANTATION)
        self.assertNotIn('#c8e6c9', toiture)
        self.assertIn('#c8e6c9', implantation)

    def test_le_plan_de_toiture_garde_nord_cotes_et_obstacles(self):
        toiture = svg_de_planche(self.geometrie, contenu=CONTENU_TOITURE)
        self.assertIn('>N</text>', toiture)
        self.assertIn(' m<', toiture)
        self.assertIn('LÉGENDE', toiture)

    def test_un_contenu_inconnu_est_refuse_en_le_nommant(self):
        with self.assertRaises(PlancheRefusee) as capture:
            svg_de_planche(self.geometrie, contenu='cadastral')
        self.assertEqual(capture.exception.champ, 'contenu')
        self.assertIn('cadastral', str(capture.exception))


class EchelleNommeeTest(SimpleTestCase):
    def test_l_echelle_nommee_est_calculee_du_trace(self):
        # 1 m de terrain occupe 5 mm de feuille -> 1/200.
        self.assertEqual(echelle_nommee(5.0), 200)
        self.assertEqual(echelle_nommee(10.0), 100)

    def test_la_mention_porte_sa_condition_de_validite(self):
        mention = mention_d_echelle(5.0)
        self.assertIn('1/200', mention)
        self.assertIn('non réduit', mention)
        # La barre graphique reste la référence : la fraction n'est valable
        # que sur un tirage non réduit, et la mention le dit.
        self.assertIn("barre d'échelle", mention)

    def test_une_echelle_absente_ne_produit_aucune_mention(self):
        self.assertIsNone(echelle_nommee(0))
        self.assertEqual(mention_d_echelle(0), '')

    def test_la_planche_porte_l_echelle_nommee(self):
        svg = svg_de_planche(geometrie_de_planche(LAYOUT))
        self.assertIn('Échelle du tracé 1/', svg)
