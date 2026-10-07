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
        self.assertIn("Hypothèses du moteur", self.txt)
        self.assertIn("D-CIQ-10 : 25 ans", self.txt)
        self.assertIn("Remplacement onduleur en année 11", self.txt)
        self.assertNotIn("économies maintenues constantes", self.txt)

    def test_aucune_hypothese_sans_sa_donnee(self):
        """Sans argent servi : ni table, ni hypothèses, ni KPI."""
        txt = _visible(_page_finance(sample_data.build()))
        self.assertNotIn("Hypothèses du moteur", txt)
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
        self.assertEqual([float(v) for v in payback],
                         [d["economie_ci"]["indicateurs"]["retour_ans"]])
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
        self.assertIn('étude du moteur C&I à faire', txt)
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
