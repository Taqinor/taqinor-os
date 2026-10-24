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


class TestAmot88VocabulaireClient(SimpleTestCase):
    """AMOT88 — le document parle la langue du client : aucun mot interne,
    le bandeau sans bégaiement, les postes dits par leur rôle, le tarif
    sans « repli » ni « capture », l'arabe « للمنشآت التجارية »."""

    MOTS_INTERNES = ("CFO", "aseline", "ashflow", "payback", "moteur",
                     "repli", "capture", "reconfirm", "flux servi", "C&I",
                     "Couverture conso")

    def test_aucun_mot_interne_en_francais(self):
        for hors_total in (False, True):
            texte = _texte_ci("".join(_pages_ci(
                _data_ci(hors_total=hors_total))))
            for mot in self.MOTS_INTERNES:
                with self.subTest(hors_total=hors_total, mot=mot):
                    self.assertNotIn(mot, texte)

    def test_bandeau_sans_begaiement_postes_par_role(self):
        p1 = _texte_ci(_pages_ci(_data_ci(hors_total=True))[1])
        self.assertNotIn("À confirmer : À chiffrer", p1)
        self.assertIn(
            "À chiffrer après la visite technique (hors total) : câble DC — "
            "Câble solaire Nexans H1Z2Z2-K 4 mm² (au mètre), câble AC, "
            "structure de fixation", p1)
        # La désignation brute du moteur n'est plus imprimée.
        self.assertNotIn("Structure C&I", p1)
        self.assertNotIn("Onduleur réseau Huawei 50kW Triphasé → TGBT", p1)

    def test_bandeau_traduit(self):
        p1 = _texte_ci(_pages_ci(_data_ci(hors_total=True, langue="en"))[1])
        self.assertIn("To be priced after the site visit (not in the "
                      "total): DC cable — Câble solaire Nexans H1Z2Z2-K 4 "
                      "mm² (au mètre), AC cable, mounting structure", p1)
        self.assertNotIn("À chiffrer", p1)

    def test_tuile_couverture_et_tarif_en_mots_du_client(self):
        p1 = _texte_ci(_pages_ci(_data_ci())[1])
        self.assertIn("Part de votre consommation couverte", p1)
        self.assertIn("Tarif ONEE BT publié — à confirmer sur votre facture "
                      "(grille du 16/02/2025).", p1)

    def test_postes_arabes_sans_balise_echappee(self):
        """Les mots du rôle (libellés isolés en arabe) ne sont jamais
        ré-échappés ; seule la désignation du catalogue l'est."""
        pages = _pages_ci(_data_ci(hors_total=True, langue="ar"))
        for i in (1, 2):
            with self.subTest(page=i):
                self.assertNotIn("&lt;span", pages[i])
                self.assertIn("كابل التيار المستمر", pages[i])
        self.assertIn("هيكل التثبيت", pages[1])

    def test_kicker_arabe_generique(self):
        html = "".join(_pages_ci(_data_ci(langue="ar")))
        self.assertIn("للمنشآت التجارية", html)
        self.assertNotIn("للمحلات", html)


class TestAmot89DefinitionsEtSurplus(SimpleTestCase):
    """AMOT89 — la définition servie sous la tuile d'autoconsommation (la
    tuile de couverture SE dit déjà « Part de votre consommation
    couverte ») et le surplus chiffré en kWh du bilan, dit selon 82-21."""

    def test_definition_sous_la_tuile_sans_redite(self):
        p1 = _texte_ci(_pages_ci(_data_ci())[1])
        self.assertIn("Autoconsommation part de la production consommée sur "
                      "place", p1)
        self.assertIn("Part de votre consommation couverte", p1)
        self.assertNotIn("couverte par le solaire", p1)

    def test_surplus_bt_en_kwh_du_bilan(self):
        data = _data_ci()
        bilan = data["etude"]["etude_ci"]["bilan"]
        self.assertEqual(synthese_ci(data)["energie"]["surplus"], {
            "kwh_an": bilan["surplus_kwh"], "valorise_kwh_an": 0,
            "non_valorise_kwh_an": bilan["non_valorise_kwh"],
            "non_valorise_pct_production": round(
                bilan["non_valorise_kwh"] / bilan["production_kwh"] * 100)})
        self.assertIn("Surplus non valorisé : ≈ 25 959 kWh/an (27 % de la "
                      "production) — revente non ouverte en basse tension à "
                      "ce jour (ANRE, décision 04/26).",
                      _texte_ci(_pages_ci(data)[1]))

    def test_surplus_mt_revendu_sous_plafond(self):
        data = _data_ci()
        etude_ci = data["etude"]["etude_ci"]
        etude_ci["entrees_resolues"]["tension"]["valeur"] = "mt"
        etude_ci["bilan"].update(injecte_valorise_kwh=19085,
                                 non_valorise_kwh=6874)
        self.assertIn("Surplus injecté : ≈ 19 085 kWh/an valorisés (plafond "
                      "légal : 20 % de la production annuelle, loi 82-21 art. "
                      "12) ; ≈ 6 874 kWh/an non valorisés (7 % de la "
                      "production).", _texte_ci(_pages_ci(data)[1]))

    def test_sans_surplus_servi_ligne_omise(self):
        data = _data_ci()
        for cle in ("surplus_kwh", "non_valorise_kwh"):
            data["etude"]["etude_ci"]["bilan"].pop(cle)
        self.assertNotIn("surplus", synthese_ci(data)["energie"])
        self.assertNotIn("Surplus non valorisé", _texte_ci(_pages_ci(data)[1]))

    def test_anglais(self):
        p1 = _texte_ci(_pages_ci(_data_ci(langue="en"))[1])
        self.assertIn("Self-consumption share of the solar production "
                      "consumed on site", p1)
        self.assertIn("Surplus not valued: ≈ 25 959 kWh/yr (27 % of the "
                      "production)", p1)


class TestAmot90EnergieMensuelle(SimpleTestCase):
    """AMOT90 — l'énergie mois par mois en SVG en ligne sur la page 1, des
    kWh du bilan horaire servi (``synthese_ci.energie.par_mois``) ; retirée
    par le rendu adaptatif quand la page déborde, jamais une page de plus."""

    def test_douze_mois_du_bilan_servis(self):
        data = _data_ci()
        bilan = data["etude"]["etude_ci"]["bilan"]["par_mois"]
        par_mois = synthese_ci(data)["energie"]["par_mois"]
        self.assertEqual([m["mois"] for m in par_mois], list(range(1, 13)))
        for servi, brut in zip(par_mois, bilan):
            for cle in ("production_kwh", "consommation_kwh",
                        "autoconso_kwh", "surplus_kwh"):
                self.assertEqual(servi[cle], brut[cle])

    def test_svg_page_1_lu_sur_les_kwh_servis(self):
        data = _data_ci()
        p1 = _pages_ci(data)[1]
        self.assertIn('data-graphique="energie_mensuelle"', p1)
        bloc = p1[p1.index('data-graphique="energie_mensuelle"'):]
        svg = bloc[bloc.index("<svg"):bloc.index("</svg>")]
        # 12 mois × (consommation + autoconsommée + surplus).
        self.assertEqual(svg.count("<rect"), 36)
        mois = data["etude"]["etude_ci"]["bilan"]["par_mois"]
        plafond = max(max(m["consommation_kwh"], m["production_kwh"])
                      for m in mois)
        graduation = f"{plafond:,}".replace(",", " ") + " kWh"
        self.assertIn(_texte_ci(graduation), _texte_ci(svg))
        texte = _texte_ci(p1)
        self.assertIn("Votre énergie mois par mois", texte)
        for legende in ("Votre consommation", "Production autoconsommée",
                        "Surplus non consommé sur place",
                        "calculées heure par heure"):
            self.assertIn(legende, texte)

    def test_sans_douze_mois_aucun_graphique(self):
        data = _data_ci()
        data["etude"]["etude_ci"]["bilan"]["par_mois"].pop()
        self.assertNotIn("par_mois", synthese_ci(data)["energie"])
        self.assertNotIn('data-graphique="energie_mensuelle"',
                         _pages_ci(data)[1])

    def test_rendu_adaptatif_retire_le_graphique_avant_la_densite(self):
        """Une page qui déborde À CAUSE du graphique : le document sort au
        palier 0 SANS graphique (jamais une page de plus, ni une densité
        réduite pour lui)."""
        from apps.ventes.quote_engine.commercial import equip
        essais = []

        class _Doc:
            def write_pdf(self):
                return b"%PDF-sans-graphique"

        def _build(donnees):
            essais.append((donnees.get("_palier_equip"),
                           donnees.get("_sans_graphiques")))
            return render.build_html(donnees)

        def _tient(html, _doc):
            return 'data-graphique="' not in html

        d = renderer._augment(_data_ci())
        with patch.object(equip, "_tient", _tient):
            pdf = equip.pdf_adaptatif(d, _build, lambda _html: _Doc())
        self.assertEqual(pdf, b"%PDF-sans-graphique")
        # Palier 0 partout ; le GRAPHIQUE cède seul d'abord (re-mesuré),
        # puis les autres blocs cédables encore posés — jamais la densité.
        self.assertEqual([palier for palier, _r in essais], [None] * 3)
        self.assertIsNone(essais[0][1])
        self.assertEqual(essais[1][1], frozenset({"energie_mensuelle"}))
        self.assertIn("energie_mensuelle", essais[2][1])
        self.assertIn("etapes", essais[2][1])

    def test_rendu_adaptatif_le_graphique_seul_suffit(self):
        """AMOT90 — quand retirer le seul graphique suffit, la page 1 garde
        ses prochaines étapes et la page 2 sa fiche d'installation."""
        from apps.ventes.quote_engine.commercial import equip
        essais = []

        class _Doc:
            def write_pdf(self):
                return b"%PDF"

        def _build(donnees):
            essais.append(donnees.get("_sans_graphiques"))
            return render.build_html(donnees)

        def _tient(html, _doc):
            return 'data-graphique="energie_mensuelle"' not in html

        d = renderer._augment(_data_ci())
        with patch.object(equip, "_tient", _tient):
            self.assertEqual(
                equip.pdf_adaptatif(d, _build, lambda _html: _Doc()),
                b"%PDF")
        self.assertEqual(essais, [None, frozenset({"energie_mensuelle"})])


class TestAmot91Hypotheses(SimpleTestCase):
    """AMOT91 — la page 3 commerciale porte le tableau « Hypothèses de
    l'estimation », chaque rangée lue sur ``synthese_ci`` (tarif et sa date,
    indexation, dégradation, horizon, entretien, onduleur, base de
    production, règle de dimensionnement D-CIQ-2)."""

    def _p3(self, data):
        return _texte_ci(_pages_ci(data)[3])

    def test_rangees_lues_sur_les_donnees_servies(self):
        data = _data_ci()
        p3 = self._p3(data)
        production = _ETUDE_CI["production"]
        taille = _ETUDE_CI["taille"]
        for rangee in (
                "Hypothèses de l'estimation",
                "Prix du kWh Tarif ONEE BT publié — à confirmer sur votre "
                "facture (grille du 16/02/2025).",
                "Indexation du tarif 0 % / an", "Dégradation des panneaux",
                "Horizon 25 ans",
                "Entretien (O&M) non déduite des économies",
                "Remplacement onduleur en année 11 55 000,00 MAD TTC",
                f"Base de production {production['inclinaison_deg']}° "
                "d'inclinaison, plein sud — à confirmer au calepinage",
                f"Règle de dimensionnement chaque palier de "
                f"{taille['pas_kwc']} kWc retenu se rembourse en moins de "
                f"{taille['horizon_marginal_annees']} ans"):
            with self.subTest(rangee=rangee):
                self.assertIn(rangee, p3)
        # Compact : les montants de la couverture et de la page 2 n'y sont
        # pas répétés.
        tableau = p3[p3.index("Hypothèses de l'estimation"):]
        self.assertNotIn("Investissement", tableau[:tableau.index(
            "Règle de dimensionnement")])

    def test_om_souscrite_deduite(self):
        data = _data_ci()
        data["economie_ci"]["om"] = {"statut": "souscrit",
                                     "montant_mad_an": 12000.0,
                                     "source": "ligne O&M souscrite"}
        self.assertIn("Entretien (O&M) déduite des économies : 12 000,00 "
                      "MAD/an", self._p3(data))

    def test_calepinage_et_etude_d_une_autre_puissance(self):
        data = _data_ci()
        etude_ci = data["etude"]["etude_ci"]
        etude_ci["production"]["source"] = "calepinage"
        etude_ci["taille"]["retenue_kwc"] = 40  # ≠ 90 kWc servis
        p3 = self._p3(data)
        self.assertIn("Base de production production du calepinage retenu "
                      "pour votre toiture", p3)
        self.assertNotIn("Règle de dimensionnement", p3)

    def test_cede_sa_place_au_rendu_adaptatif(self):
        data = renderer._augment(_data_ci())
        p3 = render.build_html(dict(data, _sans_graphiques=True)).split(
            'class="page"')[3]
        self.assertNotIn("Hypothèses de l", p3)
        self.assertIn('data-graphique="hypotheses"',
                      render.build_html(data).split('class="page"')[3])


class TestAmot92CouvertureProjet(SimpleTestCase):
    """AMOT92 — la couverture dit le PROJET du client : « Centrale solaire
    N kWc — raison sociale, ville », la catégorie en surtitre (plus en
    pastille), le téléphone mis en forme, « À l'attention de » omis quand
    c'est la société, le commercial nommé, les prochaines étapes et le QR
    de la proposition en ligne quand un lien de partage existe."""

    def _p1(self, data):
        return _pages_ci(data)[1]

    def _data(self, **surcharges):
        data = _data_ci()
        data.update(surcharges)
        return data

    def test_titre_arabe_segments_latins_isoles(self):
        """Arabe : « nom, ville » forment UN isolat bidirectionnel (U+2068 …
        U+2069) et le kWc un autre — la virgule reste entre le nom et la
        ville ; français et anglais sans isolat."""
        p1 = unescape(self._p1(self._data(langue_sortie="ar")))
        self.assertIn("\u2068Hôtel Atlas Riad SARL, Marrakech\u2069", p1)
        self.assertIn("\u206890\u2069", p1)
        for langue in ("fr", "en"):
            with self.subTest(langue=langue):
                p1 = unescape(self._p1(self._data(langue_sortie=langue)))
                self.assertNotIn("\u2068", p1)
                self.assertIn("Hôtel Atlas Riad SARL, Marrakech", p1)

    def test_titre_projet_et_categorie_en_surtitre(self):
        p1 = self._p1(self._data())
        texte = _texte_ci(p1)
        self.assertIn("Hôtel / Riad · Autoconsommation solaire commerciale "
                      "Centrale solaire 90 kWc — Hôtel Atlas Riad SARL, "
                      "Marrakech", texte)
        self.assertNotIn('class="c1c-tag"', p1)

    def test_raison_sociale_servie_prioritaire(self):
        data = self._data(entreprise_client={
            "raison_sociale": "Atlas Hospitality SA", "ice": "001234567000089"})
        self.assertIn("Centrale solaire 90 kWc — Atlas Hospitality SA, "
                      "Marrakech", _texte_ci(self._p1(data)))

    def test_telephone_mis_en_forme(self):
        from apps.ventes.quote_engine.ci.couverture import format_telephone
        for brut, attendu in (("212661234590", "+212 6 61 23 45 90"),
                              ("0661234590", "+212 6 61 23 45 90"),
                              ("+212 5 24 00 00 00", "+212 5 24 00 00 00"),
                              ("00212524000000", "+212 5 24 00 00 00"),
                              ("+33 1 23 45 67 89", "+33 1 23 45 67 89")):
            with self.subTest(brut=brut):
                self.assertEqual(format_telephone(brut), attendu)
        texte = _texte_ci(self._p1(self._data(client_phone="212661234590")))
        self.assertIn("+212 6 61 23 45 90", texte)
        self.assertNotIn("212661234590", texte)

    def test_a_l_attention_omis_quand_c_est_la_societe(self):
        meme = self._data(entreprise_client={
            "raison_sociale": "Pharmacie Phase", "interlocuteur":
            "Pharmacie Phase"})
        self.assertNotIn("À l'attention de", _texte_ci(self._p1(meme)))
        autre = self._data(entreprise_client={
            "raison_sociale": "Pharmacie Phase",
            "interlocuteur": "Youssef Benjelloun"})
        self.assertIn("À l'attention de Youssef Benjelloun",
                      _texte_ci(self._p1(autre)))

    def test_votre_interlocuteur_servi_jamais_invente(self):
        avec = self._data(seller={"nom": "Yassine Cherkaoui",
                                  "telephone": "0612345678"})
        self.assertIn("Votre interlocuteur : Yassine Cherkaoui · +212 6 12 34 "
                      "56 78", _texte_ci(self._p1(avec)))
        sans = self._data(seller={"nom": "", "telephone": "0522000000"})
        self.assertNotIn("Votre interlocuteur", _texte_ci(self._p1(sans)))

    def test_prochaines_etapes_et_qr_seulement_avec_un_lien(self):
        lien = "https://taqinor.ma/proposition/hotel-atlas/abcdEFGH1234"
        p1 = self._p1(self._data(links={"signer": lien}))
        texte = _texte_ci(p1)
        self.assertIn("Prochaines étapes 1 Visite technique de votre site 2 "
                      "Validation de l'offre définitive 3 Pose et mise en "
                      "service", texte)
        self.assertIn('alt="QR"', p1)
        self.assertIn("Votre proposition en ligne · taqinor.ma/proposition",
                      texte)
        self.assertNotIn("abcdEFGH1234", texte)
        # Le repli « /signer/<ref> » (jamais servi par le site) : aucun QR.
        p1_sans = self._p1(self._data(
            links={"signer": "taqinor.ma/signer/DEV-COM-DEMO"}))
        self.assertNotIn('alt="QR"', p1_sans)
        self.assertIn("Prochaines étapes", _texte_ci(p1_sans))

    def test_industriel_titre_projet_et_etapes_cedables(self):
        from apps.ventes.quote_engine.industriel import render as i_render
        from apps.ventes.quote_engine.industriel import renderer as i_rend
        from apps.ventes.quote_engine.industriel import sample_data as i_s
        data = copy.deepcopy(i_s.build())
        data["seller"] = {"nom": "Nadia Sefrioui", "telephone": "0661234590"}
        p1 = i_render.build_html(i_rend._augment(data)).split(
            'class="page"')[1]
        texte = _texte_ci(p1)
        self.assertIn("Centrale solaire 250 kWc — Société Atlas Industrie "
                      "SARL, Fès", texte)
        self.assertIn("Réduire votre coût de l'énergie", texte)
        self.assertIn("Votre interlocuteur : Nadia Sefrioui · +212 6 61 23 "
                      "45 90", texte)
        self.assertIn('data-graphique="etapes"', p1)
        self.assertNotIn('class="i1-tag"', p1)
        sans = i_render.build_html(dict(i_rend._augment(data),
                                        _sans_graphiques=True))
        self.assertNotIn("Prochaines étapes", sans.split('class="page"')[1])


class TestAmot84UnitesCouverture(SimpleTestCase):
    """AMOT84 — la tuile « Puissance crête » des couvertures C&I dit son
    unité dans la langue du document : « kWp » en anglais (comme le titre),
    « kWc » en français, octet pour octet."""

    def _p1_industriel(self, langue=None):
        from apps.ventes.quote_engine.industriel import render as i_render
        from apps.ventes.quote_engine.industriel import renderer as i_rend
        from apps.ventes.quote_engine.industriel import sample_data as i_s
        data = copy.deepcopy(i_s.build())
        data["etude"] = dict(data["etude"], etude_ci=copy.deepcopy(_ETUDE_CI))
        if langue:
            data["langue_sortie"] = langue
        return i_render.build_html(i_rend._augment(
            etude_ci_au_kwc_servi(data))).split('class="page"')[1]

    def test_anglais_kwp(self):
        for p1 in (_pages_ci(_data_ci(langue="en"))[1],
                   self._p1_industriel("en")):
            texte = _texte_ci(p1)
            self.assertIn(" kWp", texte)
            self.assertNotIn("kWc", texte)
            self.assertNotIn("kWh/an", texte)

    def test_francais_inchange(self):
        for p1 in (_pages_ci(_data_ci())[1], self._p1_industriel()):
            self.assertIn("&nbsp;kWc", p1)
            self.assertNotIn("kWp", _texte_ci(p1))


class TestAmot93VotreInstallation(SimpleTestCase):
    """AMOT93 — « Votre installation en bref » sous le tableau de la page 2
    (commercial ET industriel) : modules (modèle, Wc, nombre, kWc),
    onduleurs (modèle × n, kW AC SEULEMENT quand la composition décrit les
    onduleurs du devis), type de pose et surface DÉCLARÉS."""

    def _fiche(self, html_page):
        debut = html_page.index('data-graphique="installation"')
        return _texte_ci(html_page[debut:html_page.index("</table>", debut)])

    def test_fiche_lue_sur_les_lignes_et_la_synthese(self):
        fiche = self._fiche(_pages_ci(_data_ci())[2])
        self.assertIn("Votre installation en bref", fiche)
        self.assertIn("Modules 127 × Panneau Jinko 710W · 710 Wc par module · "
                      "90 kWc au total", fiche)
        # Composition (50 kW) ≠ onduleur du devis (100 kW) : aucun kW AC.
        self.assertIn("Onduleurs 1 × Onduleur réseau Huawei 100kW Triphasé",
                      fiche)
        self.assertNotIn("kW AC", fiche)
        self.assertIn("Type de pose Toit plat — lesté", fiche)
        self.assertIn("Surface disponible (déclarée) 650 m²", fiche)

    def test_kw_ac_quand_la_composition_decrit_les_onduleurs_du_devis(self):
        data = _data_ci()
        data["all_items"][1]["designation"] = \
            "Onduleur réseau Huawei 50kW Triphasé"
        self.assertEqual(synthese_ci(data)["installation"]["onduleurs"],
                         [{"kw_ac": 50, "quantite": 1}])
        self.assertIn("1 × Onduleur réseau Huawei 50kW Triphasé · 50 kW AC "
                      "au total", self._fiche(_pages_ci(data)[2]))

    def test_kw_ac_total_lu_tel_que_servi(self):
        """Le total AC vient de ``synthese_ci.installation.kw_ac_total``
        (servi une fois), imprimé tel quel ; un bloc sans ``kw_ac_total``
        n'imprime aucun total — le gabarit ne recalcule rien."""
        data = _data_ci()
        data["all_items"][1]["designation"] = (
            "Onduleur réseau Huawei 50kW Triphasé")
        self.assertEqual(synthese_ci(data)["installation"]["kw_ac_total"],
                         50)
        augmente = renderer._augment(data)
        installation = augmente["com_synthese"]["installation"]
        installation["kw_ac_total"] = 75
        fiche = self._fiche(render.build_html(augmente).split(
            'class="page"')[2])
        self.assertIn("75 kW AC au total", fiche)
        self.assertNotIn("50 kW AC", fiche)
        del installation["kw_ac_total"]
        fiche = self._fiche(render.build_html(augmente).split(
            'class="page"')[2])
        self.assertIn("1 × Onduleur réseau Huawei 50kW Triphasé", fiche)
        self.assertNotIn("kW AC", fiche)

    def test_industriel_et_cedable(self):
        from apps.ventes.quote_engine.industriel import render as i_render
        from apps.ventes.quote_engine.industriel import renderer as i_rend
        from apps.ventes.quote_engine.industriel import sample_data as i_s
        data = copy.deepcopy(i_s.build())
        data["etude"] = dict(data["etude"], etude_ci=copy.deepcopy(_ETUDE_CI))
        augmente = i_rend._augment(etude_ci_au_kwc_servi(data))
        p2 = i_render.build_html(augmente).split('class="page"')[2]
        self.assertIn("Modules 352 × Panneau Canadien Solar 710W",
                      self._fiche(p2))
        sans = i_render.build_html(dict(augmente, _sans_graphiques=True))
        self.assertNotIn("Votre installation en bref",
                         sans.split('class="page"')[2])
