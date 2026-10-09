"""AMOT46 (C-AMOT-059) — les textes du document sont tronqués sur le texte
BRUT (au mot, « … ») PUIS échappés : plus aucune entité HTML coupée dans
l'annexe FDA (``agricole.pages._fiches_annexe``, ``include_note_calcul``).

Rejoue la sonde VC agr6 : une description de 214 « x » + « l'eau pompée du
forage », échappée par le VRAI ``echapper_textes_client`` (``l'`` →
``l&#x27;``) : la coupe à 220 caractères tranchait l'entité (HTML
``l&#x2</div>``, PDF ``l\\x00``).

Balayage ``\\[:[0-9]+\\]`` des gabarits agricole / commercial / industriel /
résidentiel (08/10/2026) : une seule troncature de TEXTE (``agricole/pages.py``
— fiches de l'annexe) ; les autres coupes portent sur des dates ISO
(``[:10]``), des séries numériques ou une initiale (``[:1]``).

Test-du-test : remettre ``description[:220]`` ⇒ ``test_aucune_entite_coupee``
échoue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_quote_engine_amot46_troncature_entite"
"""
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine import montants
from apps.ventes.quote_engine.agricole import pages
from apps.ventes.quote_engine.builder import echapper_textes_client
from apps.ventes.tests.test_agr310_renderer_agricole import data_complete

DESCRIPTION = 'x' * 214 + " l'eau pompée du forage"
ENTITE_COUPEE = re.compile(r'&#?\w{0,5}(…)?</div>')


def _donnees():
    d = data_complete()
    d['all_items'][0]['description'] = DESCRIPTION
    return echapper_textes_client(d)


class TroncatureEntiteTests(SimpleTestCase):

    def test_aucune_entite_coupee(self):
        annexe = pages._fiches_annexe(_donnees(), 'fr')
        premiere = annexe.split('</div>')[0] + '</div>'
        self.assertIsNone(ENTITE_COUPEE.search(premiere), premiere[-40:])
        self.assertTrue(premiere.endswith('l&#x27;eau…</div>'), premiere[-40:])

    def test_mot_entier_et_points_de_suspension(self):
        texte = montants.tronquer_texte('un deux trois quatre', 9)
        self.assertEqual(texte, 'un deux…')
        self.assertEqual(montants.tronquer_texte('court', 220), 'court')
        # Un texte déjà échappé revient échappé à l'identique (aucune double entité).
        self.assertEqual(montants.tronquer_texte('l&#x27;eau &amp; co', 220), 'l&#x27;eau &amp; co')

    def test_annexe_note_de_calcul(self):
        d = _donnees()
        d['pdf_options'] = dict(d.get('pdf_options') or {}, include_note_calcul=True)
        d['include_note_calcul'] = True
        html = pages.build_html(d)
        self.assertIn('l&#x27;eau…</div>', html)  # l'annexe est bien rendue
        self.assertNotIn('l&#x2</div>', html)
