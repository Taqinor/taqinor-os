"""QX46 — Renderer COMMERCIAL (catégorie-aware) dédié.

Couvre la sélection (full/premium seulement ; jamais un autre mode), les blocs
CONDITIONNELS par catégorie (hôtel saisonnalité + éco-OTA, restaurant/froid
chaîne du froid, boulangerie cuisson nocturne, école fermeture estivale/injection,
bureau alignement horaires ; sans catégorie → générique), la garde rule #4
(prix_achat/marge jamais rendus) et le rendu 3 pages (WeasyPrint, CI/Docker).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qx46_commercial_quote -v 2
"""
import copy
import json
import re
from decimal import Decimal
from html import unescape
from pathlib import Path

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.economie_ci import economie_ci_publique
from apps.ventes.quote_engine.ci.synthese import chiffres_cles, synthese_ci
from apps.ventes.quote_engine.commercial import render, renderer, sample_data

from ._moteur_fixtures import etude_ci_au_kwc_servi


class _Devis:
    def __init__(self, mode):
        self.mode_installation = mode


class TestCommercialSelection(SimpleTestCase):
    def test_full_commercial_selected(self):
        self.assertTrue(renderer.is_commercial(_Devis("commercial"), {"pdf_mode": "full"}))
        self.assertTrue(renderer.is_commercial(_Devis("commercial"), None))  # défaut full

    def test_onepage_commercial_falls_back(self):
        self.assertFalse(renderer.is_commercial(_Devis("commercial"), {"pdf_mode": "onepage"}))

    def test_include_etude_reste_premium(self):
        """CIQ332 (remplace QJR621) — « Inclure l'étude » ne renvoie plus au
        moteur legacy : l'étude est intégrée aux 3 pages premium."""
        self.assertTrue(renderer.is_commercial(
            _Devis("commercial"), {"pdf_mode": "full", "include_etude": 1}))
        self.assertTrue(renderer.is_commercial(
            _Devis("commercial"), {"pdf_mode": "full", "include_etude": 0}))
        self.assertFalse(renderer.is_commercial(
            _Devis("commercial"), {"pdf_mode": "onepage", "include_etude": 1}))

    def test_other_modes_not_commercial(self):
        self.assertFalse(renderer.is_commercial(_Devis("residentiel"), {"pdf_mode": "full"}))
        self.assertFalse(renderer.is_commercial(_Devis("industriel"), {"pdf_mode": "full"}))
        self.assertFalse(renderer.is_commercial(_Devis("agricole"), {"pdf_mode": "full"}))


class TestCommercialContent(SimpleTestCase):
    def _html(self, category="hotel"):
        return render.build_html(renderer._augment(sample_data.build(category)))

    def test_three_pages(self):
        self.assertEqual(self._html().count('class="page"'), 3)

    def test_cover_category_aware(self):
        html = self._html("hotel")
        self.assertIn("Hôtel", html)         # label catégorie
        self.assertIn("Équipements", html)   # P2
        self.assertIn("Total TTC", html)     # totaux

    def test_rule4_no_buy_price_or_margin(self):
        html = self._html("hotel")
        self.assertNotIn("prix_achat", html.lower())
        self.assertNotIn("marge", html.lower())

    def test_no_peak_promise_without_battery(self):
        html = self._html("hotel")
        self.assertIn("stockage", html.lower())
        self.assertIn("pointe", html.lower())


class TestCommercialCategoryBlocks(SimpleTestCase):
    """Chaque catégorie déclenche SON bloc conditionnel P2.

    CIQ330 — le contenu vient de la table trilingue ``ci/categories.py``
    (réponses DÉCLARÉES) : plus de « Saisonnalité hôtelière », d'« éco-OTA »,
    d'« Alignement horaires » ni de « surplus injectable » en BT."""

    def _html(self, category):
        return render.build_html(renderer._augment(sample_data.build(category)))

    def test_hotel_reponses_declarees_sans_ota(self):
        html = self._html("hotel")
        self.assertIn("Votre hôtel", html)
        self.assertIn("48 chambres, occupation 62 %, piscine chauffée", html)
        self.assertNotIn("éco-OTA", html)
        self.assertNotIn("alignement idéal", html)

    def test_restaurant_reponses_traduites(self):
        html = self._html("restaurant")
        self.assertIn("Votre restaurant", html)
        self.assertIn("service continu, cuisson au gaz", html)

    def test_froid_reponses(self):
        html = self._html("froid")
        self.assertIn("Votre entrepôt froid", html)
        self.assertIn("Consigne -18 °C", html)

    def test_boulangerie_nocturnal_baking(self):
        html = self._html("boulangerie")
        self.assertIn("cuisson nocturne", html)
        self.assertIn("pas couverte", html)
        self.assertIn("Four électrique", html)

    def test_ecole_sans_promesse_injection(self):
        html = self._html("ecole")
        self.assertIn("Votre école", html)
        self.assertNotIn("injectable", html)
        self.assertNotIn("valorisable", html)
        self.assertNotIn("prévisible", html)

    def test_bureau_sans_promesse_export(self):
        html = self._html("bureau")
        self.assertIn("Vos bureaux", html)
        self.assertNotIn("quasi-totalité", html)
        self.assertNotIn("peu d'export", html)

    def test_no_category_generic_block(self):
        base = sample_data.build("hotel")
        base["etude"] = dict(base["etude"])
        base["etude"].pop("categorie_commerciale", None)
        # AMOT85 — la catégorie se lit aussi dans le rythme (devis auto) :
        # « sans catégorie » = nulle part.
        base["etude"]["rythme"] = {k: v for k, v in dict(base["etude"].get("rythme") or {}).items()
                                   if k != "categorie_commerciale"}
        html = render.build_html(renderer._augment(base))
        self.assertIn("Votre établissement", html)
        self.assertIn("Autre commerce", html)
        # les blocs spécifiques n'apparaissent pas
        self.assertNotIn("Votre hôtel", html)


class TestCommercialUnsupported(SimpleTestCase):
    def test_no_priced_lines_unsupported(self):
        base = sample_data.build("hotel")
        base["all_items"] = [{"designation": "x", "quantite": 0}]
        with self.assertRaises(renderer.Unsupported):
            renderer._augment(base)


@tag("weasyprint")
class TestCommercialPageCount(SimpleTestCase):
    """Rendu PDF réel — exactement 3 pages A4 (WeasyPrint, CI/Docker)."""
    def test_three_pages(self):
        try:
            __import__('weasyprint')
        except Exception:  # pragma: no cover - skip where native libs absent
            self.skipTest("weasyprint native libs unavailable")
        from weasyprint import HTML
        for cat in sample_data.keys():
            data = renderer._augment(sample_data.build(cat))
            pdf = renderer.render_pdf_bytes(data)
            self.assertTrue(pdf[:4] == b"%PDF")
            doc = HTML(string=render.build_html(data)).render()
            self.assertEqual(len(doc.pages), 3, f"{cat} not 3 pages")


class TestQjr615LignesEnHT(SimpleTestCase):
    """QJR615 — la page équipements imprime P.U. HT / Total HT par ligne, et la
    somme des Total HT imprimés est le Sous-total HT imprimé, au centime."""

    def _page2(self):
        data = sample_data.build("hotel")
        data["all_items"] = [
            {"designation": "Panneau Jinko 710W", "marque": "Jinko",
             "quantite": 3, "prix_unit_ht": 1150.37, "prix_unit_ttc": 1265.41,
             "taux_tva": 10},
            {"designation": "Onduleur Huawei 100kW", "marque": "Huawei",
             "quantite": 1, "prix_unit_ht": 60000.20, "prix_unit_ttc": 72000.24,
             "taux_tva": 20},
        ]
        ht = Decimal("3451.11") + Decimal("60000.20")
        tva = Decimal("345.11") + Decimal("12000.04")
        data["totaux_all"] = {"ht_brut": float(ht), "remise": 0,
                              "ht_net": float(ht), "tva": float(tva),
                              "ttc": float(ht + tva)}
        data["display_total"] = float(ht + tva)
        html = render.build_html(renderer._augment(data))
        return html.split('class="page"')[2]

    @staticmethod
    def _dec(txt):
        return Decimal(re.sub(r"[^0-9,]", "", txt).replace(",", "."))

    def test_en_tetes_ht(self):
        p2 = self._page2()
        self.assertIn("P.U. HT", p2)
        self.assertIn("Total HT", p2)
        self.assertNotIn("P.U. TTC", p2)

    def test_somme_des_lignes_egale_sous_total_ht(self):
        p2 = self._page2()
        totaux = re.findall(r'<td class="c2-t">([^<]*)</td>', p2)
        self.assertEqual(len(totaux), 2, totaux)
        m = re.search(r'Sous-total HT<span[^>]*></span></td><td[^>]*>'
                      r'([^<]*) MAD</td>', p2)
        self.assertIsNotNone(m)
        self.assertEqual(sum(self._dec(t) for t in totaux), self._dec(m.group(1)))
        self.assertEqual(self._dec(m.group(1)), Decimal("63451.31"))

    def test_taux_de_tva_par_ligne(self):
        p2 = self._page2()
        taux = re.findall(r'<td class="c2-v">([^<]*)</td>', p2)
        self.assertEqual([re.sub(r"\D", "", t) for t in taux], ["10", "20"])


@tag('pdf')  # rendu PDF réel (WeasyPrint) — lourd → palier release-verify
class TestCiq332CommercialAvecEtude(TestCase):
    """CIQ332 (réécrit QJR621) — un devis commercial demandé « avec l'étude »
    sort en 3 pages PREMIUM, étude intégrée (D-CIQ-9) : plus de bascule vers
    le legacy 4 pages. Le une-page commercial reste servi par le legacy."""

    LIGNES = [
        ('Onduleur réseau Huawei 50kW', '1', '42000'),
        ('Panneau mono 710W', '70', '1150'),
        ('Structures acier', '70', '400'),
        ('Installation', '1', '30000'),
    ]
    ETUDE = {
        'kwc': 49.7, 'production_annuelle': 79520, 'conso_annuelle': 120000,
        'taux_autoconso': 92, 'taux_couverture': 61,
        'economies_annuelles': 98000, 'payback': 3.4, 'prix_kwc': 6100,
        'prod_mensuelle': [6627] * 12, 'conso_mensuelle': [10000] * 12,
    }

    def setUp(self):
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, self.LIGNES,
            reference='DEV-CIQ332-COM', etude_params=dict(self.ETUDE))
        self.devis.mode_installation = 'commercial'
        self.devis.save(update_fields=['mode_installation'])

    def _rendu(self, pdf_options):
        import fitz
        from apps.ventes.quote_engine import builder
        from apps.ventes.quote_engine import generate_devis_premium as moteur

        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf') as up, \
                patch.object(moteur, 'generate_premium_pdf',
                             wraps=moteur.generate_premium_pdf) as legacy:
            builder.generate_premium_devis_pdf(self.devis.id,
                                               pdf_options=pdf_options)
        up.assert_called_once()
        pdf = up.call_args[0][0]
        self.assertEqual(pdf[:4], b'%PDF')
        doc = fitz.open(stream=pdf, filetype='pdf')
        return [page.get_text() for page in doc], legacy.called

    def test_avec_etude_trois_pages_premium(self):
        pages, legacy = self._rendu({'pdf_mode': 'full', 'include_etude': 1})
        self.assertFalse(legacy, "le moteur legacy ne sert plus l'étude")
        self.assertEqual(len(pages), 3)
        self.assertTrue(any('Comment nous proc' in p for p in pages))

    def test_sans_etude_identique(self):
        pages, legacy = self._rendu({'pdf_mode': 'full'})
        self.assertFalse(legacy)
        self.assertEqual(len(pages), 3)

    def test_une_page_reste_legacy(self):
        pages, legacy = self._rendu({'pdf_mode': 'onepage'})
        self.assertTrue(legacy)
        self.assertEqual(len(pages), 1)


# ── Lane document C&I (AMOT86-93) — HTML RÉEL de ``build_html`` sur la
# fixture commerciale + la sortie du moteur C&I (contrat
# ``etude_ci_preview.json``) et le bloc PUBLIC ``economie_ci``. ──────────────

_CONTRATS_CI = Path(__file__).resolve().parents[1] / "contract_samples"
_ETUDE_CI = json.loads((_CONTRATS_CI / "etude_ci_preview.json").read_text(
    encoding="utf-8"))["exemple"]
_ECONOMIE_CI = json.loads((_CONTRATS_CI / "economie_ci.json").read_text(
    encoding="utf-8"))["exemple"]
#: Trois postes de la composition « à chiffrer après la visite » (ADEV79) :
#: un article du catalogue, deux libellés génériques du moteur.
POSTES_VISITE = [
    {"role": "cable_dc", "produit": 9, "quantite": None, "unite": "m",
     "designation": "Câble solaire Nexans H1Z2Z2-K 4 mm² (au mètre)",
     "prix_connu": False, "a_chiffrer_visite": True},
    {"role": "cable_ac", "produit": None, "quantite": 35, "unite": "m",
     "designation": "Câble AC Onduleur réseau Huawei 50kW Triphasé → TGBT",
     "prix_connu": False, "a_chiffrer_visite": True},
    {"role": "structure_ci", "produit": None, "quantite": 100,
     "unite": "module", "designation": "Structure C&I",
     "prix_connu": False, "a_chiffrer_visite": True},
]
MOTIF_VISITE = ("investissement à compléter après la visite technique "
                "(3 postes hors total)")


def _data_ci(categorie="hotel", *, hors_total=False, langue=None):
    data = copy.deepcopy(sample_data.build(categorie))
    etude_ci = copy.deepcopy(_ETUDE_CI)
    economie = copy.deepcopy(_ECONOMIE_CI)
    if hors_total:
        composition = etude_ci["composition"]
        composition["lignes"] = [
            li for li in composition["lignes"]
            if li["role"] not in ("structure_ci", "cable_ac")
        ] + copy.deepcopy(POSTES_VISITE)
        composition["a_chiffrer_visite"] = [
            p["designation"] for p in POSTES_VISITE]
        # D-ACI-8=a — le moteur omet le retour sur un prix incomplet.
        economie["omissions"] = [{"cle": "investissement_mad",
                                  "motif": MOTIF_VISITE}]
        economie["flux_ht"] = dict(economie["flux_ht"], flux=[],
                                   retour_ans=None)
        economie["indicateurs"] = dict(economie["indicateurs"],
                                       retour_ans=None, tri_pct=None)
        economie["jalons"] = []
    data["etude"] = dict(data["etude"], etude_ci=etude_ci)
    data["economie_ci"] = economie_ci_publique(economie)
    if langue:
        data["langue_sortie"] = langue
    return etude_ci_au_kwc_servi(data)


def _pages_ci(data):
    return render.build_html(renderer._augment(data)).split('class="page"')


def _texte_ci(fragment):
    texte = re.sub(r"<style>.*?</style>", "", fragment, flags=re.S)
    texte = unescape(re.sub(r"<[^>]+>", " ", texte))
    return re.sub(r"\s+", " ", texte.replace(" ", " ")
                  .replace("\xa0", " "))


class TestAmot86PrixHorsTotal(SimpleTestCase):
    """AMOT86 (D-ACI-2=a) — des postes « à chiffrer après la visite » hors
    total : jamais « clé en main », les postes listés SANS montant page 2,
    la légende du retour sur le prix complet, aucun retour imprimé."""

    def test_titre_hors_postes_jamais_cle_en_main(self):
        pages = _pages_ci(_data_ci(hors_total=True))
        self.assertIn("Investissement hors postes à chiffrer après la visite",
                      _texte_ci(pages[1]))
        self.assertNotIn("clé en main", _texte_ci("".join(pages)))

    def test_sans_poste_hors_total_titre_d_hier(self):
        texte = _texte_ci("".join(_pages_ci(_data_ci())))
        self.assertIn("Investissement (clé en main)", texte)
        self.assertNotIn("hors postes à chiffrer", texte)
        self.assertNotIn("Postes à chiffrer après la visite", texte)

    def test_page2_postes_sans_montant_hors_totaux(self):
        p2 = _pages_ci(_data_ci(hors_total=True))[2]
        bloc = p2[p2.index("Postes à chiffrer après la visite technique"):
                  p2.index("</table>")]
        texte = _texte_ci(bloc)
        for nom in ("Câble DC — Câble solaire Nexans H1Z2Z2-K 4 mm² "
                    "(au mètre)", "Câble AC", "Structure de fixation"):
            self.assertIn(nom, texte)
        # Intertitre + une mention par poste.
        self.assertEqual(texte.count("à chiffrer après la visite technique"),
                         4)
        # Aucun montant (ni « 0,00 ») sur ces lignes ; les totaux d'hier.
        self.assertIsNone(re.search(r"\d+,\d{2}", texte), texte)
        self.assertIn("640 000,00", _texte_ci(p2))

    def test_legende_retour_et_aucun_retour(self):
        data = _data_ci(hors_total=True)
        p1 = _pages_ci(data)[1]
        self.assertIn("retour calculé sur le prix complet, après la visite",
                      _texte_ci(p1))
        self.assertIsNone(chiffres_cles(synthese_ci(data))["payback_ans"])
        self.assertNotIn('data-figure="payback_ans', p1)

    def test_poste_ajoute_au_devis_n_est_plus_hors_total(self):
        data = _data_ci(hors_total=True)
        data["all_items"].append({
            "designation": "Structure C&I", "quantite": 100,
            "prix_unit_ht": 300.0, "prix_unit_ttc": 360.0, "taux_tva": 20})
        postes = chiffres_cles(synthese_ci(data))["postes_hors_total"]
        self.assertEqual([p["role"] for p in postes],
                         ["cable_dc", "cable_ac"])

    def test_industriel_meme_titre_couverture_et_pied_finance(self):
        from apps.ventes.quote_engine.industriel import render as i_render
        from apps.ventes.quote_engine.industriel import renderer as i_rend
        from apps.ventes.quote_engine.industriel import sample_data as i_s
        data = copy.deepcopy(i_s.build())
        modele = _data_ci(hors_total=True)
        data["etude"] = dict(data["etude"],
                             etude_ci=modele["etude"]["etude_ci"])
        data["economie_ci"] = modele["economie_ci"]
        pages = i_render.build_html(i_rend._augment(
            etude_ci_au_kwc_servi(data))).split('class="page"')
        for i in (1, 3):
            self.assertIn("hors postes à chiffrer après la visite",
                          _texte_ci(pages[i]), i)
        self.assertNotIn("clé en main", _texte_ci("".join(pages)))

    def test_anglais_et_arabe_traduits(self):
        for langue, titre in (
                ("en", "Investment excluding items to be priced after the "
                       "site visit"),
                ("ar", "الاستثمار دون البنود التي تُسعَّر بعد الزيارة")):
            with self.subTest(langue=langue):
                texte = _texte_ci("".join(_pages_ci(
                    _data_ci(hors_total=True, langue=langue))))
                self.assertIn(titre, texte)
                self.assertNotIn("à chiffrer après la visite technique",
                                 texte)


class TestAmot87BlocInvestissement(SimpleTestCase):
    """AMOT87 — le montant et son unité sur une rangée insécable, la note
    « soit … HT · TVA récupérable… » sur SA rangée pleine largeur (plus une
    cellule anonyme de la table), sur les deux couvertures."""

    def _bloc(self, html, prefixe):
        debut = html.index(f'<div class="{prefixe}-inv">')
        return html[debut:html.index("</div>\n    </div>", debut)]

    def test_commercial_et_industriel(self):
        from apps.ventes.quote_engine.industriel import render as i_render
        from apps.ventes.quote_engine.industriel import renderer as i_rend
        from apps.ventes.quote_engine.industriel import sample_data as i_s
        data_i = copy.deepcopy(i_s.build())
        # Base « deux » (TVA récupérable inconnue) : le TTC et son HT.
        data_i["totaux_all"] = {"ht_brut": 533333.0, "remise": 0,
                                "ht_net": 533333.0, "tva": 106667.0,
                                "ttc": 640000.0}
        data_i["display_total"] = 640000.0
        data_i["etude"] = dict(data_i["etude"],
                               etude_ci=copy.deepcopy(_ETUDE_CI))
        data_i["economie_ci"] = economie_ci_publique(
            copy.deepcopy(_ECONOMIE_CI))
        cas = (("c1c", "".join(_pages_ci(_data_ci()))),
               ("i1", i_render.build_html(i_rend._augment(
                   etude_ci_au_kwc_servi(data_i)))))
        for prefixe, html in cas:
            with self.subTest(prefixe=prefixe):
                bloc = self._bloc(html, prefixe)
                rangee = bloc[:bloc.index(f'class="{prefixe}-inv-n"')]
                # Montant + « MAD TTC » insécables, dans la rangée du titre.
                self.assertIn("&nbsp;MAD&nbsp;TTC</span>", rangee)
                self.assertIn(f'<div class="{prefixe}-inv-r">', rangee)
                self.assertNotIn("soit", _texte_ci(rangee))
                # La note sur sa propre rangée, sous le montant.
                note = bloc[bloc.index(f'class="{prefixe}-inv-n"'):]
                self.assertIn("soit 533 333,00 MAD HT",
                              _texte_ci(note).replace("  ", " "))
                self.assertIn("TVA récupérable", _texte_ci(note))
                css = html[:html.index(f'<div class="{prefixe}-inv">')]
                self.assertRegex(css, rf"\.{prefixe}-inv-v\{{[^}}]*"
                                      r"white-space:nowrap")
                self.assertRegex(css, rf"\.{prefixe}-inv-r\{{display:table")
