"""AMOT46 (C-AMOT-059) — les textes du document sont tronqués sur le texte
BRUT (au mot, « … ») puis ré-échappés : plus aucune entité HTML coupée dans
l'annexe FDA (``agricole/pages._fiches_annexe``) ni par le une-page legacy
(qui délègue au MÊME helper ``textes.tronquer_au_mot``).

Fonctions réelles, aucun mock. Test-du-test : remettre ``description[:220]``
dans ``_fiches_annexe`` ⇒ ``test_annexe_fda_sans_entite_coupee`` échoue
(``l&#x2`` en fin de bloc).
"""
import html as _html
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.agricole import pages
from apps.ventes.quote_engine.textes import tronquer_au_mot

_DESCRIPTION = _html.escape("x" * 214 + " l'eau pompée du forage")
_ENTITE_COUPEE = re.compile(r"&#?\w{0,6}$")


class TroncatureEntiteTests(SimpleTestCase):
    def test_helper_pur(self):
        sortie = tronquer_au_mot(_DESCRIPTION, 220)
        self.assertTrue(sortie.endswith("&#8230;"))
        corps = sortie[:-len("&#8230;")]
        self.assertIsNone(_ENTITE_COUPEE.search(corps))
        self.assertNotIn("\x00", _html.unescape(sortie))
        self.assertEqual(tronquer_au_mot("court", 220), "court")

    def test_annexe_fda_sans_entite_coupee(self):
        d = {"all_items": [{"designation": "Pompe OSP", "quantite": 1,
                            "description": _DESCRIPTION}]}
        html = pages._fiches_annexe(d, "fr")
        bloc = html.split(" : ", 1)[1].rsplit("</div>", 1)[0]
        self.assertTrue(bloc.endswith("&#8230;"), bloc[-20:])
        self.assertIsNone(_ENTITE_COUPEE.search(bloc[:-len("&#8230;")]))

    def test_legacy_meme_helper(self):
        self.assertEqual(G._tronquer_texte_echappe(_DESCRIPTION, 220),
                         tronquer_au_mot(_DESCRIPTION, 220))
