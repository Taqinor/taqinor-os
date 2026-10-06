"""QJR120 — ``industriel/finance.py`` dit la vérité sur ses hypothèses.

Trois défauts d'une même famille, tous vérifiés en code :

(a) le cashflow était la droite PLATE ``t × économie − investissement``, qui
    ignore la dégradation panneau et la provision de remplacement onduleur —
    alors que le modèle canonique (``pricing.compute_cashflow_payback``) les
    impose, que l'année 12 du remplacement tombe DANS les 15 années imprimées,
    et que la série est DÉJÀ servie au renderer ; le tout sous un chapô qui
    qualifiait ce modèle de « Hypothèse prudente » ;
(b) « O&M (nettoyage, supervision) : inclus dans les économies nettes » était
    affirmé sur TOUT devis alors qu'``om_annuel`` n'a AUCUN producteur dans le
    dépôt — et le KPI voisin étiquetait « Économie nette / an » une valeur
    brute ;
(c) le « Payback » sortait d'un ratio année-1 sur l'option SANS pendant que le
    « Point mort » et le TRI de la MÊME page partaient du prix rendu.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr120_hypotheses_industriel -v 2
"""
import re

from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine import pricing
from apps.ventes.quote_engine.industriel import (
    finance, render, renderer, sample_data)


def _visible(html):
    txt = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = txt.replace("&nbsp;", " ").replace(" ", " ").replace("&amp;", "&")
    return re.sub(r"[\s  ]+", " ", txt)


def _augmente(base=None):
    """CIQ301 — le renderer C&I ne reprend PLUS aucune série BT : la page
    finance est testée sur une série injectée dans le dict AUGMENTÉ, comme
    la servira ``synthese_ci.argent`` (CIQ307)."""
    d = renderer._augment(base if base is not None else sample_data.build())
    d.update(sample_data.serie_finance())
    return d


def _nombre(txt):
    """'1 234' / '-1 234' -> int (toutes les espaces du document retirées)."""
    return int(re.sub(r"[^\d-]", "", txt))


def _lignes_table(html):
    """[(année, économie, cumul)] de la table « Cashflow cumulé »."""
    out = []
    for m in re.finditer(
            r'<td class="i2-y">Année (\d+)</td>\s*'
            r'<td class="i2-e">([^<]+)</td>\s*'
            r'<td class="i2-c [^"]*">([^<]+)</td>', html):
        out.append((int(m.group(1)), _nombre(m.group(2)),
                    _nombre(m.group(3))))
    return out


class TestCashflowCanonique(SimpleTestCase):
    """(a) — la table imprime la série SERVIE, pas une droite locale."""

    def setUp(self):
        self.d = _augmente()
        self.html = render.build_html(self.d)
        self.lignes = _lignes_table(self.html)

    def test_la_serie_servie_est_celle_imprimee(self):
        self.assertTrue(self.lignes)
        servie = self.d["ind_cashflow"]
        for annee, _eco, cumul in self.lignes:
            self.assertEqual(cumul, round(servie[annee - 1]),
                             "année %s hors série canonique" % annee)

    def test_le_cashflow_n_est_plus_une_droite_plate(self):
        # La dégradation panneau érode l'économie : jamais deux années égales.
        economies = [eco for _a, eco, _c in self.lignes]
        self.assertGreater(len(set(economies)), 1,
                           "économie constante = modèle plat")
        self.assertLess(economies[1], economies[0])

    def test_la_provision_onduleur_de_l_annee_12_est_visible(self):
        par_annee = {a: eco for a, eco, _c in self.lignes}
        self.assertIn(12, par_annee, "l'horizon imprimé doit couvrir l'an 12")
        self.assertLess(par_annee[12], par_annee[11] * 0.9,
                        "le palier de remplacement onduleur a disparu")

    def test_les_hypotheses_sont_declarees_sous_la_table(self):
        txt = _visible(self.html)
        self.assertIn("Nos hypothèses", txt)
        self.assertIn("Dégradation panneau", txt)
        self.assertIn("Provision de remplacement de l'onduleur en année 12",
                      txt)
        # …et le chapô ne qualifie plus le modèle de simple droite constante.
        self.assertNotIn("économies maintenues constantes", txt)

    def test_aucune_hypothese_sans_sa_donnee(self):
        """Sans série servie, ni table, ni hypothèses, ni KPI."""
        base = sample_data.build()
        for cle in ("cashflow_sans", "cashflow_avec", "cashflow_assumptions"):
            base.pop(cle, None)
        txt = _visible(render.build_html(renderer._augment(base)))
        self.assertNotIn("Nos hypothèses", txt)
        self.assertNotIn("Cashflow cumulé", txt)
        self.assertNotIn("Point mort", txt)


class TestSerieNonAppariee(SimpleTestCase):
    """CIQ301 — le renderer ne republie plus la série BT du builder."""

    def test_serie_bt_du_builder_jamais_reprise(self):
        base = sample_data.build()
        serie = sample_data.serie_finance()
        base["cashflow_sans"] = serie["ind_cashflow"]
        base["cashflow_assumptions"] = serie["ind_cashflow_hypotheses"]
        d = renderer._augment(base)
        self.assertIsNone(d["ind_cashflow"])
        self.assertIsNone(d["ind_cashflow_branche"])
        self.assertIsNone(d["ind_cashflow_hypotheses"])

    def test_dossier_MT_n_expose_aucune_serie(self):
        base = sample_data.build()
        base["masquer_economies"] = True
        d = renderer._augment(base)
        self.assertIsNone(d["ind_cashflow"])
        self.assertIsNone(d["ind_cashflow_hypotheses"])


class TestOandM(SimpleTestCase):
    """(b) — ce qui n'est pas déduit est dit non déduit."""

    def test_sans_om_le_document_dit_non_deduit(self):
        txt = _visible(render.build_html(
            _augmente()))
        self.assertNotIn("inclus dans les économies nettes", txt)
        self.assertIn("non déduit", txt)

    def test_le_kpi_ne_se_dit_plus_net(self):
        txt = _visible(render.build_html(
            _augmente()))
        self.assertNotIn("Économie nette / an", txt)
        self.assertIn("Économie année 1", txt)

    def test_avec_om_le_montant_deduit_est_nomme(self):
        base = sample_data.build()
        base["etude"] = dict(base["etude"], om_annuel=25000)
        txt = _visible(render.build_html(_augmente(base)))
        self.assertIn("O&M déduit : 25 000 MAD/an", txt)


class TestPaybackMemeFlux(SimpleTestCase):
    """(c) — payback et point mort sortent du MÊME flux."""

    def setUp(self):
        self.html = render.build_html(
            _augmente())
        self.lignes = _lignes_table(self.html)
        self.txt = _visible(self.html)

    def test_le_payback_encadre_le_point_mort(self):
        m = re.search(r"Payback.*?≈ (\d+),(\d+) ans", self.txt)
        self.assertIsNotNone(m, self.txt[:300])
        payback = float("%s.%s" % (m.group(1), m.group(2)))
        pm = re.search(r"Année (\d+) Point mort", self.txt)
        self.assertIsNotNone(pm)
        breakeven = int(pm.group(1))
        # Le croisement à zéro tombe DANS l'année du point mort.
        self.assertGreater(payback, breakeven - 1)
        self.assertLessEqual(payback, breakeven)
        # …et la table confirme le changement de signe à cette année-là.
        par_annee = {a: c for a, _e, c in self.lignes}
        self.assertLess(par_annee[breakeven - 1], 0)
        self.assertGreaterEqual(par_annee[breakeven], 0)

    def test_le_payback_ne_vient_plus_du_ratio_annee_1(self):
        # ``etude['payback']`` (3,1) est un ratio brut de l'option SANS ;
        # la courbe imprimée croise zéro plus tard — le PDF disait 3,1.
        self.assertNotIn("≈ 3,1 ans", self.txt)


class TestIrrSeries(SimpleTestCase):
    """Le TRI porte sur le flux RÉEL, pas sur une constante."""

    def test_flux_annuels_reconstruits_du_cumul(self):
        cf = pricing.compute_cashflow_payback(1000.0, 300.0)
        flux = finance._flux_annuels(cf["cumulative"], 1000.0)
        self.assertEqual(len(flux), len(cf["cumulative"]))
        self.assertAlmostEqual(flux[0], 300.0, delta=1.0)

    def test_tri_degenere_rend_none(self):
        self.assertIsNone(finance.irr_series(1000.0, []))
        self.assertIsNone(finance.irr_series(0, [100, 100]))
        # Flux dont la somme ne rembourse jamais l'investissement.
        self.assertIsNone(finance.irr_series(1000.0, [10, 10, 10]))

    def test_tri_d_un_flux_constant_egale_l_ancien_modele(self):
        plat = [400.0] * 15
        self.assertAlmostEqual(finance.irr_series(1000.0, plat),
                               finance.irr_flat(1000.0, 400.0, years=15),
                               delta=0.2)


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
            etude_params={'etude_kwc_base': 100.11, 'taux_autoconso': 62,
                          'taux_couverture': 47, 'payback': 3.3,
                          'conso_annuelle': 300000})
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
        self.assertEqual(data['etude'].get('taux_autoconso'), 62)
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
        for cle in ('taux_autoconso', 'taux_couverture', 'payback'):
            self.assertNotIn(cle, data['etude'])
        self.assertNotIn('62 %', txt)
        self.assertIn("étude industrielle périmée — relancer l'étude",
                      data.get('avertissements_internes') or [])
        # L'étude STOCKÉE n'est jamais mutée par le rendu (règle #4).
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params.get('taux_autoconso'), 62)
