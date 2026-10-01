"""QAH-PROP (feature #3 du lot QA) — PROPRIÉTÉS Hypothesis sur le moteur de
TARIFS / FACTURES / ÉCONOMIES / ROI (``quote_engine.pricing`` + ``bareme`` +
``etude_horaire.serie_kwh_depuis_mad``).

POURQUOI. Les huit bugs de miroir tarifaire trouvés avant ce lot vivaient dans
une BRANCHE qu'aucun exemple fixe n'avait choisie (aucun distributeur, « autre »,
SRM, facture nulle, un seul mois, été != hiver…). Ici chaque test est une LOI
qui doit tenir pour TOUTE entrée valide, et les stratégies visent exprès ces
branches limites.

Fonctions pures, AUCUNE base de données : SimpleTestCase. Déterministe en CI
(``derandomize=True``, ``deadline=None``) ; le balayage profond est ``@tag('slow')``.

RÈGLE SUR LES VRAIS BUGS (fondateur). Une propriété qui échoue sur une entrée
LÉGITIME est un BUG RÉEL : on ne corrige PAS le code de production ici et on
n'affaiblit PAS la propriété. On l'enregistre dans ``KNOWN_VIOLATIONS`` avec son
exemple minimal (celui que Hypothesis a réduit) ; ``test_violations_connues_se_
reproduisent_encore`` exige que chacune ÉCHOUE encore (``hypothesis.find``) — une
violation corrigée doit donc être RETIRÉE (la liste ne peut que rétrécir).

Run : ``python manage.py test apps.ventes.tests.test_proprietes_tarifs``
"""
import math

from django.test import SimpleTestCase, tag
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.errors import NoSuchExample

from hypothesis import find as hyp_find

from apps.ventes.etude_horaire import serie_kwh_depuis_mad
from apps.ventes.quote_engine import bareme
from apps.ventes.quote_engine.pricing import (
    _FALLBACK_KWH_PRICE,
    ONEE_TRANCHES,
    PRODUCTION_DERATE,
    _monthly_bill_from_kwh,
    calculate_savings_roi,
    kwh_from_bill,
    two_bills_savings,
)
from apps.ventes.quote_engine.productible import productible_for_city

PUR = settings(
    max_examples=200, deadline=None, derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
PROFOND = settings(
    max_examples=1500, deadline=None, derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
TROUVER = settings(
    max_examples=600, deadline=None, derandomize=True, database=None,
    suppress_health_check=list(HealthCheck))

# ── VIOLATIONS RÉELLES CONNUES — jamais un test assoupli ─────────────────────
# id -> {resume, exemple}. Chacune a son ``find`` dans
# ``ViolationsConnuesTest`` : elle doit se reproduire ; corrigée, la RETIRER.
KNOWN_VIOLATIONS = {}


# ── Stratégies qui VISENT les branches limites ───────────────────────────────
def _log_floats(lo, hi):
    return st.floats(min_value=0.0, max_value=1.0, allow_nan=False).map(
        lambda u: math.exp(math.log(lo) + u * (math.log(hi) - math.log(lo))))


# Distributeurs : aucun (None / vide / blanc), les trois nommés (casse mixte),
# « autre », des SRM régionales — TOUTES les branches de ``_resolve_tranches``.
UTILITIES = st.sampled_from([
    None, '', '   ', 'onee', 'ONEE', 'lydec', 'redal', 'autre',
    'srm-casablanca-settat', 'SRM Souss-Massa', 'Amendis'])
NOMMES = st.sampled_from([
    'onee', 'ONEE', 'lydec', 'redal', 'autre', 'srm-casablanca-settat',
    'SRM Souss-Massa', 'Amendis'])


def _nomme(utility):
    return bool(utility and str(utility).strip())


@st.composite
def grille_vendeur(draw):
    """Barème vendeur PROGRESSIF collé à la main : [[plafond|None, prix], …]."""
    n = draw(st.integers(1, 6))
    plafond, prix, table = 0, draw(st.floats(0.5, 1.2)), []
    for i in range(n):
        plafond += draw(st.integers(30, 250))
        prix += draw(st.floats(0.0, 0.4))
        ouvert = i == n - 1 and draw(st.booleans())
        table.append([None if ouvert else plafond, round(prix, 4)])
    return table


TABLES = st.one_of(st.just(None), grille_vendeur())


@st.composite
def factures12(draw):
    """12 factures qui visent les cas limites : plates, été != hiver, UN SEUL
    mois, zéros, énormes, série incomplète."""
    forme = draw(st.sampled_from(
        ['plate', 'hiver_ete', 'aleatoire', 'un_mois', 'zeros', 'enorme', 'dix_mois']))
    base = round(draw(_log_floats(30, 6000)))
    if forme == 'plate':
        return [base] * 12
    if forme == 'hiver_ete':
        ete = round(base * draw(st.floats(1.2, 3.0)))
        return [ete if 5 <= i <= 8 else base for i in range(12)]
    if forme == 'un_mois':
        f = [0] * 12
        f[draw(st.integers(0, 11))] = base
        return f
    if forme == 'zeros':
        return [0] * 12
    if forme == 'enorme':
        return [round(draw(_log_floats(1e4, 4e5))) for _ in range(12)]
    if forme == 'dix_mois':
        return [round(draw(_log_floats(30, 6000))) for _ in range(10)]
    return [round(draw(_log_floats(30, 6000))) for _ in range(12)]


def _finis(valeur):
    """True si aucun nombre de la sortie n'est NaN/±inf (récursif)."""
    if isinstance(valeur, bool) or valeur is None or isinstance(valeur, str):
        return True
    if isinstance(valeur, (int, float)):
        return math.isfinite(valeur)
    if isinstance(valeur, dict):
        return all(_finis(v) for v in valeur.values())
    if isinstance(valeur, (list, tuple)):
        return all(_finis(v) for v in valeur)
    return True


class TarifsParTrancheProprietes(SimpleTestCase):

    @PUR
    @given(table=st.one_of(st.just(ONEE_TRANCHES), grille_vendeur()),
           k1=_log_floats(0.1, 5000), dk=st.floats(0, 400))
    def test_facture_monotone_finie_positive(self, table, k1, dk):
        a = _monthly_bill_from_kwh(k1, table)
        b = _monthly_bill_from_kwh(k1 + dk, table)
        self.assertTrue(math.isfinite(a) and math.isfinite(b))
        self.assertGreaterEqual(a, 0)
        self.assertGreaterEqual(b + 1e-9, a, f'facture({k1 + dk}) < facture({k1})')
        self.assertEqual(_monthly_bill_from_kwh(0, table), 0.0)

    @PUR
    @given(bill=_log_floats(1, 900000), utility=UTILITIES)
    def test_kwh_from_bill_est_l_inverse_du_bareme(self, bill, utility):
        """k = kwh_from_bill(b) => facture(k+0,1) >= b et facture(k-0,1) <= b
        (inf{k : facture(k) >= b}, arrondi 0,1 kWh près — un « trou » sélectif
        est résolu à sa borne basse, jamais fabriqué). Aucun distributeur :
        prix plat, estimation=True."""
        r = kwh_from_bill(bill, utility)
        self.assertTrue(_finis(r))
        if not _nomme(utility):
            self.assertTrue(r['estimation'])
            self.assertAlmostEqual(r['kwh_mensuel'], bill / _FALLBACK_KWH_PRICE, delta=0.051)
            return
        self.assertFalse(r['estimation'])
        k = r['kwh_mensuel']
        self.assertGreaterEqual(_monthly_bill_from_kwh(k + 0.1, ONEE_TRANCHES), bill - 1e-6)
        self.assertLessEqual(_monthly_bill_from_kwh(max(0.0, k - 0.1), ONEE_TRANCHES), bill + 1e-6)

    @PUR
    @given(bill=_log_floats(1, 30000), table=grille_vendeur(),
           utility=UTILITIES)
    def test_kwh_from_bill_inverse_sur_grille_vendeur(self, bill, table, utility):
        k = kwh_from_bill(bill, utility, table)['kwh_mensuel']
        self.assertGreaterEqual(_monthly_bill_from_kwh(k + 0.1, table), bill - 1e-6)
        self.assertLessEqual(_monthly_bill_from_kwh(max(0.0, k - 0.1), table), bill + 1e-6)

    @PUR
    @given(bill=st.one_of(st.just(0), st.just(-5), st.just(None), st.just(''),
                          st.just('abc'), st.floats(max_value=0, allow_nan=False)),
           utility=UTILITIES)
    def test_facture_nulle_ou_illisible_rend_zero_estimation(self, bill, utility):
        r = kwh_from_bill(bill, utility)
        self.assertEqual(r['kwh_mensuel'], 0.0)
        self.assertTrue(r['estimation'])

    @PUR
    @given(bill=_log_floats(2e6, 5e7), utility=NOMMES)
    def test_facture_hors_plage_est_une_estimation_jamais_la_borne(self, bill, utility):
        """QJR158(e) : une facture qu'aucune consommation <= 1e6 kWh/mois ne
        produit ne rend PAS la borne de boucle (~1 024 000 kWh) comme un résultat."""
        r = kwh_from_bill(bill, utility)
        self.assertEqual(r['kwh_mensuel'], 0.0)
        self.assertTrue(r['estimation'])

    @PUR
    @given(table=grille_vendeur(), b1=_log_floats(1, 30000), db=st.floats(0, 3000))
    def test_kwh_from_bill_monotone_en_facture(self, table, b1, db):
        a = kwh_from_bill(b1, 'onee', table)['kwh_mensuel']
        b = kwh_from_bill(b1 + db, 'onee', table)['kwh_mensuel']
        self.assertGreaterEqual(b + 0.1001, a)

    @PUR
    @given(kwh=_log_floats(0.1, 5000), dk=st.floats(0, 300), table=grille_vendeur())
    def test_facture_mensuelle_finie_positive_et_monotone(self, kwh, dk, table):
        """QJR629 — ``annual_bill_from_kwh`` (mort : seuls des tests
        l'appelaient) est supprimé ; sa propriété est portée par la SOURCE
        UNIQUE du prix d'un volume mensuel, ``_monthly_bill_from_kwh``."""
        for grille in (ONEE_TRANCHES, table):
            a = _monthly_bill_from_kwh(kwh, grille)
            b = _monthly_bill_from_kwh(kwh + dk, grille)
            self.assertTrue(math.isfinite(a) and math.isfinite(b))
            self.assertGreater(a, 0)
            self.assertGreaterEqual(b + 0.01, a)
        self.assertEqual(_monthly_bill_from_kwh(0, ONEE_TRANCHES), 0.0)


class FactureCompleteProprietes(SimpleTestCase):
    """Barème complet (énergie + lignes fixes + TPPAN) — ce que le CLIENT lit."""

    @PUR
    @given(kwh=_log_floats(0.5, 4000), dk=st.floats(0, 300),
           jours=st.sampled_from([28, 30, 31]))
    def test_facture_detaillee_bornes_et_monotonie(self, kwh, dk, jours):
        a = bareme.facture_mad(kwh, jours=jours)
        b = bareme.facture_mad(kwh + dk, jours=jours)
        self.assertTrue(_finis(a))
        self.assertAlmostEqual(
            a['total_mad'], a['energie_mad'] + a['location_entretien_mad'] + a['tppan_mad'],
            places=9)
        self.assertGreaterEqual(a['tppan_mad'], 0)
        self.assertLessEqual(a['tppan_mad'], 100 + 1e-9)
        self.assertGreaterEqual(b['total_mad'] + 1e-9, a['total_mad'])

    @PUR
    @given(bill=_log_floats(1, 900000))
    def test_inversion_facture_totale_est_l_inverse_de_facture_mad(self, bill):
        r = bareme.kwh_depuis_facture_mad(bill)
        k = r['kwh_mensuel']
        if k is None:
            return  # hors plage inversable : l'appelant omet
        if k == 0:
            # le montant ne couvre même pas les lignes fixes
            self.assertLessEqual(bill, bareme.facture_mad(0)['total_mad'] + 1e-9)
            return
        self.assertGreaterEqual(bareme.facture_mad(k + 0.1)['total_mad'], bill - 1e-6)
        self.assertLessEqual(bareme.facture_mad(max(0.0, k - 0.1))['total_mad'], bill + 1e-6)

    @PUR
    @given(factures=factures12())
    def test_serie_factures_reparee_redonne_les_factures(self, factures):
        """« consommation dérivée des factures puis re-tarifée redonne les
        factures » — la chaîne SERVEUR (``serie_kwh_depuis_mad`` + ``facture_mad``),
        pour toutes les formes de série (été != hiver, un seul mois, zéros…)."""
        kwh, _ = serie_kwh_depuis_mad(factures)
        if kwh is None:
            return  # série inexploitable : le moteur omet, n'invente pas
        self.assertEqual(len(kwh), 12)
        for montant, k in zip(factures, kwh):
            self.assertGreaterEqual(k, 0)
            if montant <= bareme.facture_mad(0)['total_mad']:
                self.assertEqual(k, 0)
                continue
            self.assertGreaterEqual(bareme.facture_mad(k + 0.1)['total_mad'], montant - 1e-6)
            self.assertLessEqual(bareme.facture_mad(max(0.0, k - 0.1))['total_mad'], montant + 1e-6)

    @PUR
    @given(factures=factures12(), coef=st.floats(1.0, 4.0))
    def test_serie_monotone_factures_montent_conso_monte(self, factures, coef):
        a, _ = serie_kwh_depuis_mad(factures)
        b, _ = serie_kwh_depuis_mad([f * coef for f in factures])
        if a is None or b is None:
            return
        self.assertGreaterEqual(sum(b) + 1.2, sum(a))  # 12 × arrondi 0,1


class EconomiesProprietes(SimpleTestCase):

    @PUR
    @given(prod=_log_floats(200, 300000), conso=_log_floats(200, 500000),
           ratio=st.sampled_from([0.05, 0.3, 0.6, 0.85, 1.0, 1.5]),
           jitter=st.floats(0.9, 1.1), utility=NOMMES, table=TABLES)
    def test_economies_bornes_chaine_et_aucun_nan(self, prod, conso, ratio, jitter, utility, table):
        r = two_bills_savings(prod, conso, ratio * jitter, utility, table)
        if r is None:
            return
        self.assertTrue(_finis(r))
        self.assertGreaterEqual(r['economie'], 0)
        self.assertLessEqual(r['economie'], r['facture_sans'], 'économie > facture actuelle')
        self.assertLessEqual(r['facture_avec'], r['facture_sans'])
        self.assertEqual(r['economie'], max(0, r['facture_sans'] - r['facture_avec']))
        self.assertLessEqual(r['autoconso_kwh'], round(conso))

    @PUR
    @given(prod=_log_floats(500, 100000), conso=_log_floats(500, 100000),
           ratio=st.floats(0.1, 0.95), d_ratio=st.floats(0, 0.3),
           d_prod=st.floats(0, 50000), utility=NOMMES)
    def test_plus_de_production_ou_d_autoconso_jamais_moins_d_economie(
            self, prod, conso, ratio, d_ratio, d_prod, utility):
        base = two_bills_savings(prod, conso, ratio, utility)
        plus_ratio = two_bills_savings(prod, conso, ratio + d_ratio, utility)
        plus_prod = two_bills_savings(prod + d_prod, conso, ratio, utility)
        if not (base and plus_ratio and plus_prod):
            return
        self.assertGreaterEqual(plus_ratio['economie'] + 1, base['economie'])
        self.assertGreaterEqual(plus_prod['economie'] + 1, base['economie'])

    def test_donnees_manquantes_rendent_none(self):
        self.assertIsNone(two_bills_savings(5000, 0, 0.6, 'onee'))
        self.assertIsNone(two_bills_savings(0, 5000, 0.6, 'onee'))
        self.assertIsNone(two_bills_savings(5000, 5000, 0, 'onee'))
        self.assertIsNone(two_bills_savings(5000, 5000, 0.6, None))
        self.assertIsNone(two_bills_savings(5000, 5000, 0.6, ''))

    @PUR
    @given(prod=_log_floats(500, 100000), conso=_log_floats(500, 100000),
           ratio=st.floats(0.1, 0.95), utility=NOMMES,
           parts=st.lists(st.floats(0.01, 5), min_size=12, max_size=12))
    def test_repartition_mensuelle_garde_les_bornes(self, prod, conso, ratio, utility, parts):
        r = two_bills_savings(prod, conso, ratio, utility, repartition_mensuelle=parts)
        if r is None:
            return
        self.assertTrue(_finis(r))
        self.assertLessEqual(r['economie'], r['facture_sans'])
        self.assertGreaterEqual(r['economie'], 0)


@st.composite
def roi_entrees(draw):
    kwc = draw(st.sampled_from([1, 3, 5, 8, 10, 20, 50, 200])) * draw(st.floats(0.8, 1.2))
    return {
        'kwc': kwc,
        'total_sans': round(kwc * draw(st.floats(6000, 14000))),
        'facteur_avec': draw(st.floats(1.05, 1.5)),
        'conso': draw(st.one_of(st.none(), _log_floats(500, 400000).map(round))),
        'utility': draw(st.one_of(NOMMES, UTILITIES)),
        'battery': draw(st.sampled_from([0, 0, 5, 10, 15.36])),
        'productible': draw(st.sampled_from([None, 1550, 1651, 1687])),
    }


def _roi(e, kwc=None):
    kwc = e['kwc'] if kwc is None else kwc
    return calculate_savings_roi(
        kwc, e['total_sans'], round(e['total_sans'] * e['facteur_avec']),
        conso_annuelle_kwh=e['conso'], utility=e['utility'],
        battery_kwh=e['battery'], productible=e['productible'])


class RoiProprietes(SimpleTestCase):

    @PUR
    @given(e=roi_entrees())
    def test_roi_bornes_coherence_aucun_nan(self, e):
        r = _roi(e)
        self.assertTrue(_finis({k: v for k, v in r.items() if k != 'cashflow_assumptions'}))
        self.assertGreaterEqual(r['eco_s_ann'], 0)
        self.assertGreaterEqual(r['eco_a_ann'], r['eco_s_ann'], 'avec batterie < sans')
        for k in ('autoconso_sans', 'autoconso_avec'):
            self.assertTrue(-1e-9 <= r[k] <= 1 + 1e-9, f'{k}={r[k]}')
        for k, eco in (('roi_s', r['eco_s_ann']), ('roi_a', r['eco_a_ann'])):
            if eco > 0:
                self.assertTrue(0 < r[k] <= 25, f'{k}={r[k]} pour économie {eco}')
            else:
                self.assertEqual(r[k], 0.0)
        if r['savings_model'] == 'factures':
            self.assertLessEqual(r['eco_s_ann'], r['facture_sans'])
            self.assertLessEqual(r['eco_a_ann'], r['facture_sans'])

    @PUR
    @given(e=roi_entrees(), d_kwc=st.floats(0, 20))
    def test_production_egale_kwc_productible_derate_et_monotone(self, e, d_kwc):
        r = _roi(e)
        prod = e['productible'] or 1651  # défaut du dépôt (productible.DEFAULT)
        attendu = round(e['kwc'] * prod * PRODUCTION_DERATE)
        self.assertEqual(r['prod_kwh'], attendu)
        self.assertGreaterEqual(_roi(e, e['kwc'] + d_kwc)['prod_kwh'], r['prod_kwh'])

    @PUR
    @given(e=roi_entrees())
    def test_sans_table_repli_plat_etiquete_estimation(self, e):
        """Aucun distributeur : jamais présenté comme précis (savings_estimated)."""
        e = dict(e, utility=None)
        r = _roi(e)
        self.assertEqual(r['savings_model'], 'estimation')
        self.assertTrue(r['savings_estimated'])

    @PUR
    @given(inv=_log_floats(8000, 3e6).map(round), eco=_log_floats(500, 4e5).map(round))
    def test_payback_positif_et_fini(self, inv, eco):
        if eco > inv * 3:
            return  # domaine réaliste : payback >= ~4 mois
        from apps.ventes.quote_engine.pricing import compute_cashflow_payback
        r = compute_cashflow_payback(inv, eco)
        self.assertTrue(_finis(r))
        self.assertTrue(0 < r['payback_years'] <= 25, r['payback_years'])

    @PUR
    @given(inv=_log_floats(8000, 1e6).map(round), eco=_log_floats(800, 2e5).map(round),
           coef=st.floats(1, 3))
    def test_payback_monotone_en_economie(self, inv, eco, coef):
        from apps.ventes.quote_engine.pricing import compute_cashflow_payback
        a = compute_cashflow_payback(inv, eco)['payback_years']
        b = compute_cashflow_payback(inv, eco * coef)['payback_years']
        self.assertLessEqual(b, a + 1e-9)


class ProductibleProprietes(SimpleTestCase):

    @PUR
    @given(ville=st.one_of(st.none(), st.text(max_size=40),
                           st.sampled_from(['Casablanca', 'rabat', ' TANGER ', 'Salé', 'Témara'])),
           override=st.one_of(st.none(), st.just(0), st.just(-3), st.just(1600),
                              st.floats(100, 3000)))
    def test_productible_toujours_positif_et_fini(self, ville, override):
        p = productible_for_city(ville, override)
        self.assertTrue(math.isfinite(p) and p > 0, p)


class ViolationsConnuesTest(SimpleTestCase):
    """Chaque violation listée dans ``KNOWN_VIOLATIONS`` se reproduit encore."""

    def test_violations_connues_se_reproduisent_encore(self):
        for err_id, v in KNOWN_VIOLATIONS.items():
            with self.subTest(err_id):
                try:
                    hyp_find(v['strategie'], v['viole'], settings=TROUVER)
                except NoSuchExample:
                    self.fail(
                        f'{err_id} : la violation connue ne se reproduit plus — '
                        'RETIRER l\'entrée de KNOWN_VIOLATIONS (elle ne peut que '
                        'rétrécir).')


@tag('slow')
class BalayageProfondTarifs(SimpleTestCase):
    """Même lois, 1 500 exemples — hors gate par-PR (``@tag('slow')``)."""

    @PROFOND
    @given(bill=_log_floats(1, 900000), utility=NOMMES)
    def test_inverse_du_bareme_profond(self, bill, utility):
        k = kwh_from_bill(bill, utility)['kwh_mensuel']
        self.assertGreaterEqual(_monthly_bill_from_kwh(k + 0.1, ONEE_TRANCHES), bill - 1e-6)
        self.assertLessEqual(_monthly_bill_from_kwh(max(0.0, k - 0.1), ONEE_TRANCHES), bill + 1e-6)

    @PROFOND
    @given(e=roi_entrees())
    def test_roi_profond(self, e):
        r = _roi(e)
        self.assertTrue(_finis({k: v for k, v in r.items() if k != 'cashflow_assumptions'}))
        self.assertGreaterEqual(r['eco_a_ann'], r['eco_s_ann'])
