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


# ── QJR614 — les PDF premium résidentiel / commercial / industriel ─────────
# Le ``fmt`` du thème premium arrondissait à l'ENTIER (arrondi banquier) :
# 1 000,40 HT + 200,40 TVA s'imprimaient « 1 000 » + « 200 » sous un Total
# TTC « 1 201 » — la chaîne imprimée ne s'additionnait pas. Tous les montants
# dérivés du prix passent désormais par ``montants.fmt_centimes``.

NNBSP = "\u202f"
_TOT_1200_80 = {"ht_brut": 1000.40, "remise": 0, "ht_net": 1000.40,
                "tva": 200.40, "ttc": 1200.80,
                "tva_par_taux": [{"taux": 20, "montant": 200.40}]}


def _dec(txt):
    """« 1 000,40 » (espaces fines) -> Decimal."""
    return Decimal(re.sub(r"[^0-9,]", "", txt).replace(",", "."))


class TestResidentielPremiumAuCentime(SimpleTestCase):
    """PDF premium résidentiel : chaîne additive au centime."""

    def _html(self):
        from apps.ventes.quote_engine.residential import (
            render, renderer, sample_data)
        data = sample_data.build("deux")
        data["totaux_sans"] = dict(_TOT_1200_80)
        data["totaux_avec"] = dict(_TOT_1200_80)
        return render.build_html(renderer._augment(data))

    def test_le_ctx_porte_le_formateur_au_centime(self):
        from apps.ventes.quote_engine import montants
        from apps.ventes.quote_engine.residential import (
            render, renderer, sample_data)
        ctx = render.build_ctx(renderer._augment(sample_data.build("deux")))
        self.assertIs(ctx["fmt_mad"], montants.fmt_centimes)
        self.assertEqual(ctx["fmt_mad"](63187.50), f"63{NNBSP}187,50")

    def test_la_chaine_imprimee_s_additionne(self):
        html = self._html()
        sous_total = re.findall(
            r'<span>Sous-total HT</span><span>([^<]*)</span>', html)
        tva = re.findall(
            r'<span>TVA 20%</span><span>([^<]*)</span>', html)
        ttc = re.findall(
            r'<span class="p2-grand-v">([^<]*) <small>MAD</small>', html)
        self.assertTrue(sous_total and tva and ttc, "chaîne introuvable")
        self.assertEqual(sous_total[0], f"1{NNBSP}000,40")
        self.assertEqual(tva[0], "200,40")
        self.assertEqual(ttc[0], f"1{NNBSP}200,80")
        self.assertEqual(_dec(sous_total[0]) + _dec(tva[0]), _dec(ttc[0]))


class TestCommercialPremiumAuCentime(SimpleTestCase):
    """PDF premium commercial : chaîne additive au centime."""

    def _html(self):
        from apps.ventes.quote_engine.commercial import (
            render, renderer, sample_data)
        data = sample_data.build("hotel")
        data["totaux_all"] = {k: v for k, v in _TOT_1200_80.items()
                              if k != "tva_par_taux"}
        data["display_total"] = 1200.80
        return render.build_html(renderer._augment(data))

    def test_le_ctx_porte_le_formateur_au_centime(self):
        from apps.ventes.quote_engine import montants
        from apps.ventes.quote_engine.commercial import render, sample_data
        ctx = render.build_ctx(sample_data.build("hotel"))
        self.assertIs(ctx["fmt_mad"], montants.fmt_centimes)

    def test_la_chaine_imprimee_s_additionne(self):
        html = self._html()

        def _ligne(label):
            m = re.search(re.escape(label) + r'<span[^>]*></span></td>'
                          r'<td[^>]*>([^<]*) MAD</td>', html)
            self.assertIsNotNone(m, label)
            return m.group(1)

        ht = _ligne("Sous-total HT")
        tva = _ligne("TVA")
        ttc = _ligne("Total TTC")
        self.assertEqual(ht, f"1{NNBSP}000,40")
        self.assertEqual(tva, "200,40")
        self.assertEqual(ttc, f"1{NNBSP}200,80")
        self.assertEqual(_dec(ht) + _dec(tva), _dec(ttc))


class TestIndustrielPremiumAuCentime(SimpleTestCase):
    """PDF premium industriel : investissement TTC au centime."""

    def test_le_ctx_porte_le_formateur_au_centime(self):
        from apps.ventes.quote_engine import montants
        from apps.ventes.quote_engine.industriel import render
        ctx = render.build_ctx({})
        self.assertIs(ctx["fmt_mad"], montants.fmt_centimes)


# ── ERR-QJR614-CI-INVESTISSEMENT-DIRHAM-VS-CENTIME ─────────────────────────
# Un même PDF C&I imprimait l'investissement arrondi au DIRHAM en couverture
# (``_invest_ttc = round(invest)``) et au CENTIME page équipements ; les
# tranches industrielles (``round(_invest_ttc × int(pct)/100)``) ne sommaient
# pas au Total TTC. Une seule chaîne de total TTC, des tranches au centime.

_TOT_1200_85 = {"ht_brut": 1000.71, "remise": 0, "ht_net": 1000.71,
                "tva": 200.14, "ttc": 1200.85}


class TestInvestissementCIUneSeuleChaine(SimpleTestCase):

    def _commercial(self):
        from apps.ventes.quote_engine.commercial import (
            render, renderer, sample_data)
        data = sample_data.build("hotel")
        data["totaux_all"] = dict(_TOT_1200_85)
        data["display_total"] = 1200.85
        return render.build_html(renderer._augment(data))

    def _industriel(self, chiffrable=True):
        from apps.ventes.quote_engine.industriel import (
            render, renderer, sample_data)
        data = sample_data.build()
        data["totaux_all"] = dict(_TOT_1200_85)
        data["display_total"] = 1200.85
        if not chiffrable:
            data["etude"] = dict(data.get("etude") or {},
                                 economies_annuelles=None)
            data["eco_s_ann"] = None
        return render.build_html(renderer._augment(data))

    def _ttc_equip(self, html):
        m = re.search(r'Total TTC<span[^>]*></span></td>'
                      r'<td[^>]*>([^<]*) MAD</td>', html)
        self.assertIsNotNone(m, "Total TTC équipements introuvable")
        return m.group(1)

    def test_commercial_couverture_egale_total_ttc(self):
        html = self._commercial()
        cover = re.findall(r'class="c1c-inv-v">([^<]*)<span>', html)
        self.assertEqual(cover, [f"1{NNBSP}200,85"])
        self.assertEqual(self._ttc_equip(html), f"1{NNBSP}200,85")
        self.assertNotIn(f"1{NNBSP}201", html)

    def test_industriel_couverture_egale_total_ttc(self):
        html = self._industriel()
        cover = re.findall(r'class="i1-inv-v">([^<]*)<span>', html)
        self.assertEqual(cover, [f"1{NNBSP}200,85"])
        self.assertEqual(self._ttc_equip(html), f"1{NNBSP}200,85")
        self.assertNotIn(f"1{NNBSP}201", html)

    def test_industriel_pied_finance_au_centime(self):
        html = self._industriel(chiffrable=False)
        foot = re.findall(r'Investissement \(TTC, clé en main\) : '
                          r'<b>([^<]*) MAD</b>', html)
        self.assertTrue(foot, "pied de page finance introuvable")
        self.assertEqual(set(foot), {f"1{NNBSP}200,85"})

    def test_industriel_tranches_somment_au_centime(self):
        html = self._industriel()
        tranches = re.findall(r'class="i3-tr-amt">([^<]*) MAD</div>', html)
        self.assertEqual(len(tranches), 3, tranches)
        self.assertEqual(sum(_dec(t) for t in tranches), Decimal("1200.85"))
        self.assertEqual(tranches[0], "600,43")
