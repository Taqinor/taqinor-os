"""QJR120 — ``industriel/finance.py`` dit la vérité sur ses hypothèses.

Trois défauts d'une même famille, corrigés par QJR120 puis repris par CIQ342
(D-CIQ-10) qui fait LIRE la page sur ``synthese_ci['argent']`` (le bloc du
moteur C&I) au lieu d'une série BT reconstruite :

(a) la page imprime la série SERVIE (jalons 5/10/15/20/25 et cumul sur tout
    l'horizon), jamais une droite locale ; ses hypothèses sont CELLES DU
    MOTEUR, avec leur source (remplacement onduleur compris) ;
(b) l'O&M n'est dite déduite que si l'option est chiffrée — sinon « non
    déduite », et rien quand le devis n'en porte pas ;
(c) le retour imprimé est celui du MÊME flux (``indicateurs.retour_ans``),
    ancré pour la parité.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr120_hypotheses_industriel -v 2
"""
import copy
import re

from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine.figures import extract_figures
from apps.ventes.quote_engine.industriel import render, renderer, sample_data


def _visible(html):
    txt = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = txt.replace("&nbsp;", " ").replace(" ", " ").replace("&amp;", "&")
    txt = txt.replace("&#160;", " ").replace(" ", " ")
    return re.sub(r"[\s  ]+", " ", txt)


def _data(exemple="exemple", **argent):
    """La fixture industrielle avec le bloc ``economie_ci`` d'un exemple du
    contrat (``argent`` : surcharges du bloc servi)."""
    d = sample_data.build()
    bloc = sample_data.economie_ci(exemple)
    bloc.update(copy.deepcopy(argent))
    d["economie_ci"] = bloc
    return d


def _page_finance(d):
    return render.build_html(renderer._augment(d)).split('class="page"')[3]


class TestFluxServi(SimpleTestCase):
    """(a) — la page imprime la série SERVIE, pas une droite locale."""

    def setUp(self):
        self.d = _data()
        self.page = _page_finance(self.d)
        self.txt = _visible(self.page)

    def test_les_jalons_servis_sont_ceux_imprimes(self):
        for jalon in self.d["economie_ci"]["jalons"]:
            with self.subTest(annee=jalon["annee"]):
                self.assertIn(f"Année {jalon['annee']}", self.txt)
        self.assertIn("2 180 003,60", self.txt)

    def test_la_courbe_couvre_tout_l_horizon(self):
        barres = re.findall(r'class="i2-b[pn]"', self.page)
        self.assertEqual(len(barres),
                         len(self.d["economie_ci"]["flux_ht"]["flux"]))

    def test_les_hypotheses_du_moteur_avec_leur_source(self):
        # CPDF5 — le titre client « Bases du calcul ».
        self.assertIn("Bases du calcul", self.txt)
        self.assertNotIn("Hypothèses de l'estimation", self.txt)
        self.assertNotIn("moteur", self.txt)
        # AMOT80 — la source en mots du client, jamais « D-CIQ-10 ».
        # « Horizon : 25 ans » — une seule mention, la source servie le
        # répétait (« durée d'analyse : 25 ans »).
        self.assertIn("Horizon : 25 ans", self.txt)
        self.assertNotIn("durée d'analyse", self.txt)
        self.assertNotIn("D-CIQ", self.txt)
        self.assertIn("Remplacement onduleur en année 11", self.txt)
        self.assertNotIn("économies maintenues constantes", self.txt)

    def test_aucune_hypothese_sans_sa_donnee(self):
        """Sans argent servi : ni table, ni hypothèses, ni KPI."""
        txt = _visible(_page_finance(sample_data.build()))
        self.assertNotIn("Bases du calcul", txt)
        self.assertNotIn("Cumul net", txt)
        self.assertNotIn("TRI sur", txt)


class TestSerieNonAppariee(SimpleTestCase):
    """CIQ301 — le renderer ne republie plus la série BT du builder."""

    def test_serie_bt_du_builder_jamais_reprise(self):
        base = sample_data.build()
        base["cashflow_sans"] = [-1000.0, -500.0, 0.0, 500.0]
        base["cashflow_assumptions"] = {"notes": ["droite BT"]}
        d = renderer._augment(base)
        self.assertIsNone(d["ind_cashflow"])
        self.assertIsNone(d["ind_cashflow_branche"])
        self.assertIsNone(d["ind_cashflow_hypotheses"])
        self.assertNotIn("droite BT", render.build_html(d))

    def test_dossier_MT_n_expose_aucune_serie(self):
        base = sample_data.build()
        base["masquer_economies"] = True
        d = renderer._augment(base)
        self.assertIsNone(d["ind_cashflow"])
        self.assertIsNone(d["ind_cashflow_hypotheses"])


class TestOandM(SimpleTestCase):
    """(b) — ce qui n'est pas déduit est dit non déduit."""

    def test_om_proposee_dite_non_deduite(self):
        txt = _visible(_page_finance(_data(om={
            "statut": "propose", "montant_mad_an": None, "source": "x"})))
        self.assertIn("O&M proposée, non déduite de ces montants", txt)
        self.assertNotIn("inclus dans les économies nettes", txt)

    def test_sans_option_om_aucune_phrase(self):
        txt = _visible(_page_finance(_data(om=None)))
        self.assertNotIn("O&M", txt)
        self.assertNotIn("nettoyage, supervision", txt)

    def test_om_chiffree_dite_deduite(self):
        txt = _visible(_page_finance(_data(om={
            "statut": "souscrit", "montant_mad_an": 25000, "source": "x"})))
        self.assertIn("O&M déduite du flux : 25 000,00 MAD/an", txt)


class TestDeuxOptionsPageFinance(SimpleTestCase):
    """Fondateur 18/11/2026 — la page 3 d'un devis à DEUX options dit aussi
    l'économie annuelle, le retour et le TRI de l'option « avec batterie »,
    lus de l'étude (jamais recalculés). Depuis le 19/11/2026 cette bande
    n'est plus que le REPLI d'une option batterie sans flux 25 ans : avec
    son flux, la page montre les deux options à poids égal
    (``TestDeuxOptionsPoidsEgal``)."""

    def _avec(self, **option):
        from apps.ventes.tests.test_quote_engine_amot36_pages_ci import (
            _avec_option_batterie)
        d = _avec_option_batterie(_data())
        d["etude"]["etude_ci"]["option_avec"].update(option)
        return d

    def test_option_avec_batterie_dite_sous_l_offre_reseau(self):
        d = self._avec(economie_flux={"indicateurs": {
            "tri_pct": 21.7967, "tri_horizon_ans": 25}})
        page = _page_finance(d)
        bande = _visible(re.search(
            r'<div class="i2-avec".*?</div>', page, flags=re.S).group(0))
        self.assertIn("Option avec batterie", bande)
        self.assertIn("120 000", bande)            # économie annuelle servie
        self.assertIn("8,4 ans", bande)            # retour servi
        self.assertIn("TRI sur 25 ans : 21,8 %", bande)
        # L'offre réseau garde ses chiffres, désormais étiquetée.
        self.assertIn("Sans batterie", _visible(page))
        self.assertLess(page.index('class="i2-optl"'), page.index('class="i2-kpis"'))
        self.assertLess(page.index('class="i2-kpis"'), page.index('class="i2-avec"'))

    def test_sans_tri_servi_la_bande_l_omet(self):
        bande = _visible(re.search(
            r'<div class="i2-avec".*?</div>', _page_finance(self._avec()),
            flags=re.S).group(0))
        self.assertIn("120 000", bande)
        self.assertNotIn("TRI", bande)

    def test_une_seule_option_rendu_inchange(self):
        page = _page_finance(_data())
        self.assertNotIn('class="i2-avec"', page)
        self.assertNotIn('class="i2-optl"', page)


class TestDeuxOptionsPoidsEgal(SimpleTestCase):
    """Fondateur 19/11/2026 (« the page 3 is still all about the ongrid
    option ») — deux options entièrement chiffrées : la page finance les
    montre à POIDS ÉGAL, chaque nombre LU de l'étude (``finance_deux``)."""

    def _donnees(self, **surcharges):
        from apps.ventes.tests.test_quote_engine_amot36_pages_ci import (
            _option_avec_chiffree)
        return _option_avec_chiffree(_data(), **surcharges)

    def _flux_avec(self, d):
        return d["etude"]["etude_ci"]["option_avec"]["economie_flux"][
            "flux_ht"]["flux"]

    def test_deux_cartes_aux_memes_chiffres(self):
        page = _page_finance(self._donnees())
        cartes = re.findall(r'<td class="i2d-opt">.*?</table></div></td>',
                            page, flags=re.S)
        self.assertEqual(len(cartes), 2)
        sans, avec = (_visible(c) for c in cartes)
        self.assertIn("Option 1 — Sans batterie", sans)
        self.assertIn("Option 2 — Avec batterie", avec)
        for carte in (sans, avec):
            for libelle in ("Économie de l'année 1", "Délai de retour",
                            "TRI sur 25 ans", "Cumul net sur 25 ans",
                            "Investissement"):
                self.assertIn(libelle, carte)
        # L'option batterie : SES nombres servis (économie et retour de la
        # valeur chiffrée, TRI de son flux, totaux de son panier).
        self.assertIn("120 000", avec)
        self.assertIn("8,4 ans", avec)
        self.assertIn("17,3 %", avec)
        self.assertIn("964 000,00", avec)
        # La bande d'une phrase (repli) n'est plus imprimée.
        self.assertNotIn('class="i2-avec"', page)

    def test_la_courbe_porte_les_deux_lignes_et_leurs_retours(self):
        d = self._donnees()
        page = _page_finance(d)
        svg = re.search(r'<div data-graphique="courbe_cumul">(.*?)</svg>',
                        page, flags=re.S).group(1)
        self.assertEqual(svg.count("<polyline"), 2)
        self.assertEqual(svg.count("<circle"), 2)
        # Le point de retour de chaque option porte le délai de SA carte.
        self.assertIn("8,4", svg)
        # Chaque ligne finit sur le cumul SERVI de sa dernière année.
        dernier = self._flux_avec(d)[-1]["cumul_mad"]
        self.assertIn(f"{round(dernier):,}".replace(",", " "), _visible(svg))

    def test_le_tableau_met_les_deux_flux_cote_a_cote(self):
        d = self._donnees()
        page = _page_finance(d)
        tableau = re.search(r'<table class="i2-tbl i2-fx i2d-fx">.*?</table>',
                            page, flags=re.S).group(0)
        rangees = re.findall(r"<tr><td>\d+</td>", tableau)
        self.assertEqual(len(rangees), len(self._flux_avec(d)))
        texte = _visible(tableau)
        self.assertIn("Sans batterie", texte)
        self.assertIn("Avec batterie", texte)
        # Le cumul de la dernière année est ancré pour CHAQUE option.
        ancres = re.findall(
            r'data-figure="cumul_net_25_ans_mad"( data-figure-option="avec")?',
            tableau)
        self.assertEqual(sorted(ancres), ["", ' data-figure-option="avec"'])
        for ligne in self._flux_avec(d)[1:4]:
            cumul = f"{ligne['cumul_mad']:,.2f}".replace(",", " ").replace(".", ",")
            self.assertIn(cumul, texte)

    def test_indicateurs_des_deux_options(self):
        txt = _visible(_page_finance(self._donnees()))
        bloc = txt[txt.index("Indicateurs pour votre direction financière"):]
        self.assertIn("0,457 MAD/kWh", bloc)       # coût du kWh, option batterie

    def test_bases_communes_une_fois_puis_par_option(self):
        remplacements = [
            {"composant": "onduleur", "annee": 12, "montant_ht_mad": 80000.0,
             "montant_ttc_mad": 96000.0, "source": "x"},
            {"composant": "batterie", "annee": 11, "montant_ht_mad": 250000.0,
             "montant_ttc_mad": 300000.0, "source": "x"}]
        page = _page_finance(self._donnees(remplacements=remplacements))
        bases = _visible(page[page.index('data-graphique="hypotheses"'):])
        self.assertEqual(bases.count("Horizon"), 1)
        self.assertIn("Avec batterie — ", bases)
        self.assertIn("Remplacement batterie en année 11 : 250 000,00", bases)

    def test_la_courbe_cede_par_paliers(self):
        d = self._donnees()
        d["_sans_graphiques"] = frozenset({"courbe_cumul"})
        compacte = _page_finance(d)
        self.assertIn('data-graphique="courbe_compacte"', compacte)
        self.assertEqual(compacte.count("<polyline"), 2)
        d["_sans_graphiques"] = frozenset({"courbe_cumul", "courbe_compacte"})
        sans = _page_finance(d)
        self.assertNotIn("<polyline", sans)
        self.assertIn('class="i2-tbl i2-fx i2d-fx"', sans)   # le tableau reste

    def test_arabe_aucun_mot_dans_le_dessin(self):
        d = self._donnees()
        d["langue_sortie"] = "ar"
        page = _page_finance(d)
        svg = re.search(r"<svg.*?</svg>", page, flags=re.S).group(0)
        self.assertIsNone(re.search("[\u0600-\u06FF]", svg))
        # Les noms des options passent dans la légende, sous la courbe.
        self.assertIn("بدون بطارية", page[page.index("</svg>"):])

    def test_bases_differentes_la_page_d_hier(self):
        page = _page_finance(self._donnees(base="ttc"))
        self.assertNotIn('class="i2d-opt"', page)
        self.assertIn('class="i2-kpis"', page)


class TestPaybackMemeFlux(SimpleTestCase):
    """(c) — le retour imprimé est celui du flux servi, ancré."""

    def test_retour_et_tri_du_flux_servi(self):
        d = _data()
        page = _page_finance(d)
        figures = extract_figures(page)
        payback = [m.valeur for i, ms in figures.items()
                   if i.startswith("payback_ans") for m in ms]
        tri = [m.valeur for i, ms in figures.items()
               if i.startswith("tri_pct") for m in ms]
        # CPDF7 — le retour imprimé est celui du flux servi au dixième, le
        # MÊME nombre que la couverture et /proposition (``chiffres_cles``).
        from apps.ventes.quote_engine.ci.synthese import (
            chiffres_cles, synthese_ci)
        self.assertEqual([float(v) for v in payback],
                         [chiffres_cles(synthese_ci(dict(d)))["payback_ans"]])
        self.assertAlmostEqual(float(tri[0]),
                               d["economie_ci"]["indicateurs"]["tri_pct"],
                               delta=0.05)
        self.assertIn("TRI sur 25 ans", _visible(page))


class TestEtudePerimeeQjr625(TestCase):
    """QJR625 — une étude I/C calculée pour 100 kWc n'est plus imprimée
    quand les lignes, corrigées, n'en font plus que 80."""

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.ventes.models import LigneDevis
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis, make_user)

        self.company = make_company()
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau Canadien Solar 710W', '141', '1150'),
                ('Onduleur réseau Huawei 100kW', '1', '90000'),
            ], reference='DEV-QJR625-IND',
            # CIQ129 — `etude_kwc_base` et les dérivées écran v1 ont quitté
            # le schéma : la base d'une étude saisie est `kwc` ; un taux v1
            # resté sur un ancien devis n'est plus jamais rendu.
            etude_params={'kwc': 100.11, 'production_annuelle': 150000,
                          'taux_autoconso': 62, 'conso_annuelle': 300000})
        self.devis.mode_installation = 'industriel'
        self.devis.save(update_fields=['mode_installation'])
        self.ligne_pv = LigneDevis.objects.get(
            devis=self.devis, designation__startswith='Panneau')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _rendu(self):
        from apps.ventes.models import Devis
        from apps.ventes.quote_engine.builder import (
            build_quote_data, echapper_textes_client)
        data = build_quote_data(Devis.objects.get(pk=self.devis.pk),
                                {'pdf_mode': 'full'})
        html = render.build_html(
            renderer._augment(echapper_textes_client(data)))
        return data, _visible(html)

    def test_etude_fraiche_imprimee(self):
        """Témoin : à 100,11 kWc, l'étude décrit les lignes — elle passe dans
        les données. CIQ307 : le PDF industriel ne lit plus que `synthese_ci`
        (moteur C&I) ; un taux d'étude d'écran n'est donc jamais imprimé, même
        frais (aucune étude moteur sur ce devis → « à confirmer »)."""
        data, txt = self._rendu()
        self.assertEqual(data['etude'].get('kwc'), 100.11)
        self.assertNotIn('taux_autoconso', data['etude'])
        self.assertNotIn('62 %', txt)
        # Décision fondateur 26/10/2026 — la liste « À confirmer : … » (dont
        # « étude détaillée de votre site à finaliser : chiffres
        # préliminaires ») n'est plus imprimée : le bandeau « Devis
        # préliminaire », imprimé sur tout document C&I, le dit à sa place.
        self.assertNotIn('étude détaillée de votre site à finaliser', txt)
        self.assertIn('Devis préliminaire', txt)
        self.assertNotIn("étude industrielle périmée — relancer l'étude",
                         data.get('avertissements_internes') or [])

    def test_ligne_ramenee_a_80_kwc_etude_omise(self):
        r = self.api.patch(
            f'/api/django/ventes/devis-lignes/{self.ligne_pv.id}/',
            {'quantite': '113'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        data, txt = self._rendu()
        self.assertAlmostEqual(data['puissance_kwc'], 80.23, places=2)
        for cle in ('kwc', 'production_annuelle', 'taux_autoconso'):
            self.assertNotIn(cle, data['etude'])
        self.assertNotIn('62 %', txt)
        self.assertIn("étude industrielle périmée — relancer l'étude",
                      data.get('avertissements_internes') or [])
        # L'étude STOCKÉE n'est jamais mutée par le rendu (règle #4).
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params.get('taux_autoconso'), 62)
