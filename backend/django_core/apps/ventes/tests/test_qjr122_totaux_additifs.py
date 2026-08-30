"""QJR122 — la chaîne de totaux du PDF premium additionne AU CENTIME.

Le bloc imprimait Sous-total HT, Remise et TVA via ``_fmt2`` (2 décimales) mais
le Total TTC via ``fmt``, qui fait ``int(round(float(v)))`` : la chaîne affichée
n'additionnait donc pas (52 655,42 + 10 531,08 s'imprimait « 63 186 MAD »).
Deux aggravants : ``round()`` de Python arrondit en mode BANQUIER alors que
``selectors._canonical_totaux`` quantifie en ``ROUND_HALF_UP`` au centime (deux
nombres possibles pour le MÊME devis entre le PDF et l'échéancier /
``option_totaux``), et c'est ce montant qui sert de base à l'échéancier de la
page 3.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr122_totaux_additifs -v 2
"""
import re
from decimal import Decimal

from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as moteur


_LIGNE_RE = re.compile(
    r'padding:3px 5px;">([^<]*)</td>'
    r'<td style="[^"]*white-space:nowrap;">([^<]*)</td>')


def _montant(txt):
    """« 52 655,42 MAD » / « −1 234,00 » -> Decimal."""
    net = re.sub(r"[^0-9,\-−]", "", txt).replace("−", "-")
    return Decimal(net.replace(",", "."))


def _lignes(html):
    return [(lbl.strip(), val.strip()) for lbl, val in _LIGNE_RE.findall(html)]


def _totaux(ht_brut, remise, ht_net, tva, ttc, par_taux=None):
    return {
        "ht_brut": Decimal(ht_brut), "remise": Decimal(remise),
        "ht_net": Decimal(ht_net), "tva": Decimal(tva), "ttc": Decimal(ttc),
        "tva_par_taux": par_taux or [],
    }


#: Trois fixtures : simple, remisée, multi-taux (réforme TVA 10/20).
_UN_TAUX = [{"taux": 20, "montant": Decimal("10531.08")}]
FIXTURES = {
    "simple": (_totaux("52655.42", "0", "52655.42", "10531.08", "63186.50",
                       _UN_TAUX), 0.0),
    "remisee": (_totaux("60000.00", "7344.58", "52655.42", "10531.08",
                        "63186.50", _UN_TAUX), 12.0),
    "multitaux": (_totaux("48120.75", "0", "48120.75", "7123.46",
                          "55244.21",
                          [{"taux": 10, "montant": Decimal("2145.83")},
                           {"taux": 20, "montant": Decimal("4977.63")}]), 0.0),
}


class TestChaineAdditive(SimpleTestCase):
    """Sous-total HT − Remise + Σ TVA == Total TTC, À L'AFFICHAGE."""

    def _rendu(self, cle):
        totaux, remise_pct = FIXTURES[cle]
        ancien = moteur.DISCOUNT_PCT
        moteur.DISCOUNT_PCT = remise_pct
        try:
            return _lignes(moteur._totals_block_rows(totaux, 3))
        finally:
            moteur.DISCOUNT_PCT = ancien

    def test_les_trois_fixtures_additionnent(self):
        for cle in FIXTURES:
            with self.subTest(fixture=cle):
                lignes = dict(self._rendu(cle))
                self.assertTrue(lignes)
                calcul = Decimal("0")
                ttc_affiche = None
                for label, valeur in self._rendu(cle):
                    montant = _montant(valeur)
                    if label.startswith("Sous-total HT"):
                        calcul += montant
                    elif label.startswith("Remise"):
                        calcul += montant          # déjà signé « − »
                    elif label.startswith("TVA"):
                        calcul += montant
                    elif label.startswith("Total TTC"):
                        ttc_affiche = montant
                self.assertIsNotNone(ttc_affiche, "aucun Total TTC imprimé")
                self.assertEqual(calcul, ttc_affiche,
                                 "chaîne non additive sur %s : %s" %
                                 (cle, lignes))

    def test_le_total_ttc_est_au_centime(self):
        for cle in FIXTURES:
            with self.subTest(fixture=cle):
                lignes = dict(self._rendu(cle))
                ttc = lignes["Total TTC"]
                self.assertRegex(ttc, r",\d{2} MAD$", ttc)
                self.assertNotEqual(ttc, "63 186 MAD")

    def test_le_multitaux_imprime_une_ligne_par_taux(self):
        labels = [lbl for lbl, _v in self._rendu("multitaux")]
        self.assertIn("TVA (10 %)", labels)
        self.assertIn("TVA (20 %)", labels)


class TestArrondiHalfUp(SimpleTestCase):
    """L'arrondi de la chaîne suit ``ROUND_HALF_UP``, pas le banquier."""

    def test_demi_centime_arrondi_vers_le_haut(self):
        # ``f"{1.005:,.2f}"`` (float) rend « 1,00 » — arrondi banquier sur la
        # valeur binaire ; la chaîne canonique rend « 1,01 ».
        self.assertEqual(moteur._fmt2(1.005), "1,01")
        self.assertEqual(moteur._fmt2(2.675), "2,68")
        self.assertEqual(moteur._fmt2(Decimal("0.125")), "0,13")

    def test_valeur_illisible_ne_casse_pas_le_rendu(self):
        self.assertEqual(moteur._fmt2("n/a"), "n/a")

    def test_le_suffixe_mad_est_pose_une_seule_fois(self):
        rendu = moteur._fmt2_mad(1234.5)
        self.assertEqual(rendu, "1 234,50 MAD")
        self.assertEqual(rendu.count("MAD"), 1)


_ONEPAGE_RE = re.compile(
    r'>([^<>]{0,40})</span>'
    r'<span style="display:inline-block;min-width:110px;[^"]*">([^<]*)</span>')


class TestUnePageMemeChaine(SimpleTestCase):
    """Le une-page imprimait le même Total TTC arrondi à l'unité."""

    def _lignes_onepage(self):
        # QJR162 — charge utile CANONIQUE : le moteur lève désormais quand les
        # totaux canoniques manquent (il ne fabrique plus de chaîne à taux
        # unique). On ne surcharge que ``totaux_all``, la chaîne testée ici.
        from apps.ventes.tests import _moteur_fixtures as F

        totaux, _pct = FIXTURES["simple"]
        data = F.donnees_legacy(pdf_mode="onepage")
        data["totaux_all"] = {k: float(v) if isinstance(v, Decimal) else v
                              for k, v in totaux.items()}
        data["all_items"] = data["sans_items"]
        html = moteur.render_html_for(data)
        return {lbl.strip(): val.strip()
                for lbl, val in _ONEPAGE_RE.findall(html)}

    def test_le_total_ttc_du_une_page_est_au_centime(self):
        lignes = self._lignes_onepage()
        self.assertIn("Total TTC", lignes)
        self.assertRegex(lignes["Total TTC"], r",\d{2}&nbsp;MAD$")

    def test_la_chaine_du_une_page_additionne(self):
        lignes = self._lignes_onepage()
        calcul = Decimal("0")
        for label, valeur in lignes.items():
            if (label.startswith("Sous-total HT") or label.startswith("TVA")
                    or label.startswith("Remise")):
                calcul += _montant(valeur)
        self.assertEqual(calcul, _montant(lignes["Total TTC"]))
