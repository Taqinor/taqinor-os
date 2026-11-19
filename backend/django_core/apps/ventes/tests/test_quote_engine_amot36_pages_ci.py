"""AMOT36 (C-AMOT-046, volet C&I) — le PDF C&I tient son contrat de pages
(commerce 3, usine 4) : ``pdf_adaptatif`` mesure TOUTES les pages, la liste
variable des conditions est tronquée avec renvoi déclaré (« Suite des
conditions : proposition en ligne ») avant tout refus, et aucun repli legacy
n'est servi à un devis C&I dont le contrat de pages est intenable.

WeasyPrint + PyMuPDF RÉELS (sautés sans eux). Test-du-test : remettre
``deborde(doc.pages[index_page])`` dans ``pdf_adaptatif`` ⇒
``test_contrat_de_pages`` échoue (puces sous le pied, ou page de trop).
"""
import copy
from decimal import Decimal

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.ci import blocs
from apps.ventes.quote_engine.commercial import equip
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

GABARITS = (("commercial", c_sample, c_renderer, 3),
            ("industriel", i_sample, i_renderer, 4))
_SUITE = "Suite des conditions : proposition en ligne"


def _puces(n):
    return [(f"Condition contractuelle n° {i:02d} — " + "texte " * 40)[:220]
            for i in range(1, n + 1)]


def _avec_option_batterie(data):
    """Le panier « avec » d'un C&I à deux options (forme ``build_quote_data``)
    et l'option chiffrée par le moteur (``etude_ci.option_avec``)."""
    data["option_servie"] = "sans"
    data["option_batterie"] = {
        "lignes": [dict(it) for it in data["all_items"] if "Onduleur" not in it["designation"]] + [
            {"designation": "Onduleur hybride Deye SUN-20K-SG05LP3", "quantite": 2,
             "prix_unit_ht": 40000.0, "taux_tva": 20},
            {"designation": "Batterie Dyness 10 kWh", "quantite": 10,
             "prix_unit_ht": 25000.0, "taux_tva": 20}],
        "totaux": {"ht_net": 803333, "tva": 160667, "ttc": 964000},
        "valeur_chiffree": None, "motif": "valeur non chiffrée"}
    etude = data.setdefault("etude", {})
    etude["etude_ci"] = dict(etude.get("etude_ci") or {}, option_avec={
        "economie_annuelle_mad": 120000.0, "retour_simple_ans": 8.4,
        "bilan": {"batterie": {"capacite_utile_kwh": 92.2, "restitue_kwh_an": 31000}}})
    return data


def _option_avec_chiffree(data, decalage=250000.0, **surcharges):
    """Deux options ENTIÈREMENT chiffrées (fondateur 19/11/2026) : l'option
    « avec batterie » porte son ``economie_ci`` calculé et son flux 25 ans
    (``economie_flux``) — ici le bloc de l'offre réseau, cumul décalé de
    ``decalage`` et TRI / coût du kWh propres, pour distinguer les deux."""
    data = _avec_option_batterie(data)
    bloc = copy.deepcopy(data["economie_ci"])
    for cle in ("flux_ht", "flux_ttc"):
        for ligne in (bloc.get(cle) or {}).get("flux") or []:
            ligne["cumul_mad"] = round(ligne["cumul_mad"] - decalage, 2)
    bloc["indicateurs"] = dict(bloc["indicateurs"], tri_pct=17.26,
                               lcoe_mad_kwh=0.4567)
    bloc.update(copy.deepcopy(surcharges))
    avec = data["etude"]["etude_ci"]["option_avec"]
    avec["economie_ci"] = bloc
    avec["economie_flux"] = {cle: bloc[cle] for cle in (
        "base", "indicateurs", "flux_ht", "flux_ttc", "remplacements",
        "om", "entretien") if cle in bloc}
    return data


class OptionAvecValeurTests(SimpleTestCase):
    def test_valeur_chiffree_par_le_moteur(self):
        from apps.ventes.quote_engine.ci.mentions import valeur_option_avec
        from apps.ventes.quote_engine.commercial import sample_data
        valeur = valeur_option_avec(_avec_option_batterie(sample_data.build()))
        # CPDF2 — le retour SERVI par l'étude (flux 25 ans), jamais le
        # quotient HT ÷ économie (6,7 ans ici) recalculé par le PDF.
        self.assertEqual(valeur["retour_simple_ans"], 8.4)
        self.assertIn("92,2 kWh utiles", valeur["textes"]["fr"])
        self.assertIn("92.2 kWh usable", valeur["textes"]["en"])

    def test_sans_option_avec_rien(self):
        from apps.ventes.quote_engine.ci.mentions import valeur_option_avec
        from apps.ventes.quote_engine.commercial import sample_data
        self.assertIsNone(valeur_option_avec(sample_data.build()))
        self.assertEqual(blocs.bloc_option_avec(sample_data.build(), None, str, ("",) * 4), "")


def _bloc_depart(**surcharge):
    """Le bloc ``etude_ci.depart_une_batterie`` du contrat
    ``devis_depart_une_batterie.json`` (jamais un chiffre inventé ici)."""
    import json
    import os
    chemin = os.path.join(os.path.dirname(__file__), os.pardir, "contract_samples",
                          "devis_depart_une_batterie.json")
    with open(chemin, encoding="utf-8") as fh:
        bloc = json.load(fh)["etude_ci_depart_une_batterie"]
    return dict(bloc, **surcharge)


def _avec_depart(data, **surcharge):
    data = _avec_option_batterie(data)
    data["etude"]["etude_ci"]["depart_une_batterie"] = _bloc_depart(**surcharge)
    return data


class DepartUneBatterieTests(SimpleTestCase):
    """Fondateur 19/11/2026 — la phrase « démarrer avec une seule batterie »
    est LUE sur ``etude_ci.depart_une_batterie`` (calculé par le serveur) ;
    sans bloc, le rendu d'hier."""

    def _textes(self, bloc, economie_ci=None):
        from apps.ventes.quote_engine.ci.mentions import depart_une_batterie_option_avec
        data = {"etude": {"etude_ci": {"depart_une_batterie": bloc}}}
        if economie_ci:
            data["economie_ci"] = economie_ci
        return depart_une_batterie_option_avec(data)

    def test_phrase_du_fondateur_et_accords(self):
        v = self._textes(_bloc_depart())
        self.assertEqual(v["textes"]["fr"], (
            "Pour démarrer avec une seule batterie : 24 panneaux (13,2 kWc) et 1 batterie de "
            "5,12 kWh utiles — 182 300 MAD TTC. Les 2 autres batteries pourront être ajoutées "
            "ensuite : l'onduleur est déjà prévu pour."))
        self.assertEqual((v["prix_mad"], v["base"], v["nb_panneaux"]), (182300, "ttc", 24))
        self.assertIn("24 panels (13.2 kWp)", v["textes"]["en"])
        self.assertIn("182,300 MAD incl. VAT", v["textes"]["en"])
        un = self._textes(_bloc_depart(batteries_ensuite=1, nb_panneaux=1))["textes"]["fr"]
        self.assertIn(": 1 panneau (", un)
        self.assertTrue(un.endswith(" La seconde batterie pourra être ajoutée ensuite : "
                                    "l'onduleur est déjà prévu pour."))

    def test_base_ht_le_prix_ht(self):
        v = self._textes(_bloc_depart(), economie_ci={"base": "ht"})
        self.assertIn("— 151 916,67 MAD HT.", v["textes"]["fr"])
        self.assertEqual((v["prix_mad"], v["base"]), (151916.67, "ht"))

    def test_bloc_absent_ou_incomplet_rien(self):
        for bloc in (None, {}, _bloc_depart(nb_batteries=2), _bloc_depart(nb_panneaux=0),
                     _bloc_depart(total_ttc=None), _bloc_depart(batteries_ensuite=0)):
            with self.subTest(bloc=bloc):
                self.assertIsNone(self._textes(bloc))
                self.assertEqual(blocs.phrase_depart_une_batterie(
                    {"etude": {"etude_ci": {"depart_une_batterie": bloc}}}, str, "#999"), "")

    def test_page_2_sous_les_totaux_option_2_avec_ancres_trois_langues(self):
        from apps.ventes.quote_engine.commercial import render as c_render
        from apps.ventes.quote_engine.figures import extract_figures
        sans = c_render.build_html(c_renderer._augment(_avec_option_batterie(c_sample.build())))
        self.assertNotIn("data-depart-une-batterie", sans)
        self.assertNotIn("depart_une_batterie", sans)
        for lg in ("fr", "en", "ar"):
            with self.subTest(langue=lg):
                data = _avec_depart(c_sample.build())
                data["langue_sortie"] = lg
                html = c_render.build_html(c_renderer._augment(data))
                self.assertEqual(html.count("data-depart-une-batterie"), 1)
                # Sous la chaîne de totaux de l'option 2, avant la fin de sa cellule.
                self.assertLess(html.rindex('class="c2-tot-tbl"'), html.index("data-depart-une-batterie"))
                figures = extract_figures(html)
                for cle, attendu in (("depart_une_batterie_panneaux", 24),
                                     ("depart_une_batterie_kwc", Decimal("13.2")),
                                     ("depart_une_batterie_kwh", Decimal("5.12")),
                                     ("depart_une_batterie_prix", 182300),
                                     ("depart_une_batterie_ajout", 2)):
                    self.assertEqual(figures[cle + "@avec"][0].valeur, attendu, (lg, cle))
                if lg == "ar":
                    self.assertIn('dir="rtl"', html[html.index("data-depart-une-batterie"):][:400])


class TroncatureDeclareeTests(SimpleTestCase):
    def test_puces_tronquees_avec_renvoi(self):
        d = {"cgv_ci": _puces(10), "_cgv_max": 3}
        puces = blocs.puces_conditions(d)
        self.assertEqual(len(puces), 4)
        self.assertEqual(puces[-1], _SUITE)

    def test_sans_troncature_inchange(self):
        self.assertEqual(blocs.puces_conditions({"cgv_ci": _puces(5)}),
                         _puces(5))


@tag("pdf")
class PagesCiTests(SimpleTestCase):
    def setUp(self):
        try:
            __import__('fitz')
            __import__('weasyprint')
        except Exception:  # pragma: no cover — libs natives absentes
            self.skipTest("weasyprint / PyMuPDF indisponible")

    def _rendre(self, sample, renderer, n):
        import fitz
        data = copy.deepcopy(sample.build())
        data["cgv_ci"] = _puces(n)
        pdf = renderer.render_pdf_bytes(data)
        return fitz.open(stream=pdf, filetype="pdf")

    def test_contrat_de_pages(self):
        for nom, sample, renderer, pages in GABARITS:
            for n in (15, 18, 19, 40):
                with self.subTest(gabarit=nom, puces=n):
                    doc = self._rendre(sample, renderer, n)
                    self.assertEqual(len(doc), pages)
                    for page in doc:
                        pied = page.rect.height * (1 - equip.PIED_MM / 297.0)
                        for bloc in page.get_text("blocks"):
                            x0, y0, x1, y1 = bloc[:4]
                            # Aucun bloc de texte ne CHEVAUCHE le haut du pied.
                            self.assertFalse(y0 < pied - 1 and y1 > pied + 1,
                                             (nom, n, bloc[4][:60]))

    def test_option_avec_batterie_tient_le_contrat_de_pages(self):
        """Fondateur 26/10/2026 — un C&I à deux options imprime l'option
        « avec batterie » (équipements propres, totaux, économie et retour du
        moteur) sans page de plus."""
        import fitz
        for nom, sample, renderer, pages in GABARITS:
            with self.subTest(gabarit=nom):
                data = _avec_option_batterie(copy.deepcopy(sample.build()))
                data["cgv_ci"] = _puces(15)
                doc = fitz.open(stream=renderer.render_pdf_bytes(data), filetype="pdf")
                self.assertEqual(len(doc), pages)
                texte = " ".join(page.get_text() for page in doc)
                self.assertIn("PROPRES À CETTE OPTION", texte)
                self.assertIn("964 000,00 MAD", texte)
                self.assertIn("Batterie Dyness 10 kWh", texte)
                self.assertIn("Retour sur investissement", texte)

    def test_deux_options_chiffrees_la_page_finance_tient(self):
        """Fondateur 19/11/2026 — la page finance à DEUX options (cartes,
        courbe à deux lignes, tableau côte à côte, indicateurs, bases) tient
        le contrat de l'usine dans les trois langues : 4 pages, rien sous le
        pied, et la courbe reste (pleine ou compacte)."""
        import fitz
        from apps.ventes.tests.test_qjr120_hypotheses_industriel import _data
        for langue in ("fr", "en", "ar"):
            with self.subTest(langue=langue):
                data = _option_avec_chiffree(_data())
                data["cgv_ci"] = _puces(15)
                data["langue_sortie"] = langue
                doc = fitz.open(stream=i_renderer.render_pdf_bytes(data),
                                filetype="pdf")
                self.assertEqual(len(doc), 4)
                page = doc[2]
                pied = page.rect.height * (1 - equip.PIED_MM / 297.0)
                for bloc in page.get_text("blocks"):
                    self.assertFalse(bloc[1] < pied - 1 and bloc[3] > pied + 1,
                                     (langue, bloc[4][:60]))
                # Les deux lignes de la courbe sont dessinées (traits épais).
                traits = [t for t in page.get_drawings()
                          if (t.get("width") or 0) > 1.5 and len(t["items"]) > 10]
                self.assertEqual(len(traits), 2, langue)

    def test_d_hyb_5_extension_onduleur_sans_page_de_plus(self):
        """D-HYB-5 (fondateur 17/11/2026) — la phrase de l'onduleur gardé pour
        l'extension tient dans le bloc de l'option « avec » : aucune page de
        plus (commerce 3, usine 4), aucun bloc sous le pied."""
        import fitz
        for nom, sample, renderer, pages in GABARITS:
            with self.subTest(gabarit=nom):
                data = _avec_option_batterie(copy.deepcopy(sample.build()))
                avec = data["etude"]["etude_ci"]["option_avec"]
                avec["batterie"] = {"quantite": 1}
                avec["onduleur_extension"] = {
                    "retenu": {"produit": 2, "nom": "Deye 20", "kw_ac": 20.0, "quantite": 2},
                    "suffisant": {"produit": 1, "nom": "Deye 15", "kw_ac": 15.0, "quantite": 2},
                    "batteries_max": 10}
                data["cgv_ci"] = _puces(18)
                doc = fitz.open(stream=renderer.render_pdf_bytes(data), filetype="pdf")
                self.assertEqual(len(doc), pages)
                texte = " ".join(" ".join(page.get_text().split()) for page in doc)
                self.assertIn("jusqu'à 10 batteries (9 à ajouter plus tard)", texte)
                for page in doc:
                    pied = page.rect.height * (1 - equip.PIED_MM / 297.0)
                    for bloc in page.get_text("blocks"):
                        self.assertFalse(bloc[1] < pied - 1 and bloc[3] > pied + 1,
                                         (nom, bloc[4][:60]))

    def test_depart_une_batterie_sans_page_de_plus_trois_langues(self):
        """Fondateur 19/11/2026 — la phrase « démarrer avec une seule batterie »
        (avec, en plus, la phrase D-HYB-5 de l'onduleur gardé : le pire cas de
        la page 2) tient le contrat de pages (commerce 3, usine 4) en fr, en,
        ar ; aucun bloc sous le pied ; la phrase est imprimée."""
        import fitz
        for nom, sample, renderer, pages in GABARITS:
            for lg in ("fr", "en", "ar"):
                with self.subTest(gabarit=nom, langue=lg):
                    data = _avec_depart(copy.deepcopy(sample.build()))
                    avec = data["etude"]["etude_ci"]["option_avec"]
                    avec["batterie"] = {"quantite": 3}
                    avec["onduleur_extension"] = {
                        "retenu": {"produit": 2, "nom": "Deye 20", "kw_ac": 20.0, "quantite": 2},
                        "suffisant": {"produit": 1, "nom": "Deye 15", "kw_ac": 15.0, "quantite": 2},
                        "batteries_max": 10}
                    data["langue_sortie"] = lg
                    data["cgv_ci"] = _puces(18)
                    doc = fitz.open(stream=renderer.render_pdf_bytes(data), filetype="pdf")
                    self.assertEqual(len(doc), pages)
                    if lg == "fr":
                        texte = " ".join(" ".join(page.get_text().split()) for page in doc)
                        self.assertIn("Pour démarrer avec une seule batterie", texte)
                        self.assertIn("Les 2 autres batteries", texte)
                    for page in doc:
                        pied = page.rect.height * (1 - equip.PIED_MM / 297.0)
                        for bloc in page.get_text("blocks"):
                            self.assertFalse(bloc[1] < pied - 1 and bloc[3] > pied + 1,
                                             (nom, lg, bloc[4][:60]))

    def test_quarante_puces_renvoi_imprime(self):
        for nom, sample, renderer, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                doc = self._rendre(sample, renderer, 40)
                texte = " ".join(page.get_text() for page in doc)
                self.assertIn("Suite des conditions", texte)
