"""QAH-PROP (feature #3 du lot QA) — PROPRIÉTÉS Hypothesis sur le DEVIS :
chaîne monétaire canonique (remise -> TVA par taux -> TTC) et dérivation
kWc / production depuis les lignes (``builder.panneaux_et_watt_lu``).

Complète ``test_invariants_money`` (QAH2 : la chaîne s'additionne, façades
devis == facture, etc.) par les lois de DIRECTION qu'il ne posait pas :

  * remise ↑  => total TTC jamais plus haut ; TTC >= 0 ;
  * chaîne exacte au centime pour n'importe quel jeu de lignes/quantités/prix/
    remise/TVA (TTC = HT net + TVA, ΣTVA par taux = TVA, Σ HT net par taux = HT net) ;
  * plus de panneaux (même modèle) => nb de panneaux, kWc et production annuelle
    jamais plus bas ; production = kWc × productible × PRODUCTION_DERATE ;
    ajouter une ligne non-panneau ne change ni le nombre ni le kWc.

Aucune base de données : SimpleTestCase, objets légers (mêmes que QAH3).

RÈGLE SUR LES VRAIS BUGS (fondateur) : une propriété violée sur une entrée
LÉGITIME est un BUG RÉEL — elle est enregistrée dans ``KNOWN_VIOLATIONS`` avec
l'exemple minimal réduit par Hypothesis, jamais corrigée ici ni affaiblie ; un
test exige qu'elle se reproduise encore (``hypothesis.find``), donc la liste ne
peut que rétrécir.

Run : ``python manage.py test apps.ventes.tests.test_proprietes_devis``
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase
from hypothesis import HealthCheck, find, given, settings
from hypothesis import strategies as st
from hypothesis.errors import NoSuchExample

from apps.ventes.quote_engine.builder import panneaux_et_watt_lu
from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE
from apps.ventes.quote_engine.productible import productible_for_city
from apps.ventes.selectors import TAUX_TVA_REFERENTIEL, _canonical_totaux

PUR = settings(
    max_examples=200, deadline=None, derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
TROUVER = settings(
    max_examples=1500, deadline=None, derandomize=True, database=None,
    suppress_health_check=list(HealthCheck))

TAUX_LEGAUX = tuple(sorted(Decimal(str(v)) for v in TAUX_TVA_REFERENTIEL.values()))
CENT = Decimal('0.01')

# Lignes : quantité et prix à 2 décimales => total HT à 4 décimales (les
# demi-centimes sont la source réelle des bugs d'arrondi).
quantite_st = st.decimals(min_value=Decimal('0.01'), max_value=Decimal('500'), places=2)
prix_st = st.decimals(min_value=Decimal('0'), max_value=Decimal('60000'), places=2)
ligne_st = st.tuples(quantite_st, prix_st, st.sampled_from(TAUX_LEGAUX))
lignes_st = st.lists(ligne_st, min_size=1, max_size=8)
remise_st = st.decimals(min_value=Decimal('0'), max_value=Decimal('99.99'), places=2)


def _lignes(specs):
    return [SimpleNamespace(total_ht=q * pu, taux_tva_effectif=t)
            for (q, pu, t) in specs]


def _totaux(specs, remise):
    return _canonical_totaux(
        _lignes(specs), remise_globale_pct=Decimal(remise),
        fallback_taux=Decimal('20'))


# ── VIOLATIONS RÉELLES CONNUES — jamais un test assoupli ─────────────────────
# id -> {resume, exemple, strategie, viole}. Retirer l'entrée quand corrigée.
# (ERR-QAH-PROP-TOTAUX-REMISE-100-NEGATIF corrigée : HT net borné à 0 dans
# selectors._canonical_totaux — voir ``test_remise_100_ttc_exactement_zero``.)
KNOWN_VIOLATIONS = {}


class ChaineCanoniqueProprietes(SimpleTestCase):

    @PUR
    @given(specs=lignes_st, remise=remise_st)
    def test_chaine_exacte_au_centime(self, specs, remise):
        t = _totaux(specs, remise)
        self.assertEqual(t['ttc'], t['ht_net'] + t['tva'], 'TTC != HT net + TVA')
        self.assertEqual(t['tva'], sum((b['montant'] for b in t['tva_par_taux']), Decimal('0')))
        self.assertEqual(
            sum((b['ht_net'] for b in t['tva_par_taux']), Decimal('0')), t['ht_net'],
            'Σ HT net par taux != HT net')
        for k in ('ht_brut', 'remise', 'ht_net', 'tva', 'ttc'):
            self.assertEqual(t[k], t[k].quantize(CENT), f'{k} pas au centime')
        self.assertGreaterEqual(t['remise'], 0)
        self.assertLessEqual(t['remise'], t['ht_brut'] + CENT)
        self.assertGreaterEqual(t['ht_net'], 0)
        self.assertGreaterEqual(t['ttc'], 0)

    @PUR
    @given(specs=lignes_st, r1=remise_st, dr=remise_st)
    def test_remise_croissante_total_ttc_jamais_plus_haut(self, specs, r1, dr):
        r2 = min(Decimal('99.99'), r1 + dr)
        a = _totaux(specs, r1)['ttc']
        b = _totaux(specs, r2)['ttc']
        self.assertLessEqual(b, a, f'TTC({r2} %) = {b} > TTC({r1} %) = {a}')

    @PUR
    @given(specs=lignes_st)
    def test_sans_remise_ht_net_egale_ht_brut(self, specs):
        t = _totaux(specs, '0')
        self.assertEqual(t['remise'], 0)
        self.assertEqual(t['ht_net'], t['ht_brut'])

    @PUR
    @given(specs=lignes_st, remise=remise_st)
    def test_ttc_encadre_par_les_taux_extremes(self, specs, remise):
        t = _totaux(specs, remise)
        taux = [s[2] for s in specs]
        bas = t['ht_net'] * (1 + min(taux) / 100) - CENT * (len(specs) + 1)
        haut = t['ht_net'] * (1 + max(taux) / 100) + CENT * (len(specs) + 1)
        self.assertTrue(bas <= t['ttc'] <= haut, f'{t["ttc"]} hors [{bas}, {haut}]')

    @PUR
    @given(specs=lignes_st, remise=remise_st)
    def test_quantite_doublee_sans_remise_ne_baisse_jamais_le_total(self, specs, remise):
        doubles = [(q * 2, pu, tx) for (q, pu, tx) in specs]
        self.assertGreaterEqual(_totaux(doubles, '0')['ttc'] + CENT, _totaux(specs, '0')['ttc'])


# ── kWc / production dérivés des lignes ──────────────────────────────────────
WATTS = [400, 455, 550, 585, 590, 605, 625, 710]
MARQUES = ['Canadian Solar', 'JA Solar', 'Trina Solar', 'Longi']
AUTRES = [
    'Onduleur réseau Huawei SUN2000 10kW', 'Onduleur hybride Deye 8kW Monophasé',
    'Batterie Dyness 10 kWh', 'Structure aluminium toiture inclinée',
    'Câble DC solaire 6mm² (lot)', 'Smart Meter Huawei DTSU666',
    'Pompe immergée OSP 30-8 3HP', 'Variateur VEICHI SVF3 5.5kW']


def _ligne(designation, quantite):
    return SimpleNamespace(
        designation=designation, produit=SimpleNamespace(nom=''),
        quantite=quantite)


@st.composite
def panneaux_st(draw):
    watt = draw(st.sampled_from(WATTS))
    forme = draw(st.sampled_from(['panneau', 'module_pv', 'marque_watt']))
    marque = draw(st.sampled_from(MARQUES))
    designation = {
        'panneau': f'Panneau {marque} {watt}W',
        'module_pv': f'Module PV {watt} W',
        'marque_watt': f'JA Solar {watt} Wc',
    }[forme]
    return watt, designation


class KwcDesLignesProprietes(SimpleTestCase):

    @PUR
    @given(p=panneaux_st(), n=st.integers(1, 400), d_n=st.integers(0, 200),
           autres=st.lists(st.sampled_from(AUTRES), max_size=5),
           ville=st.sampled_from(['Casablanca', 'Rabat', 'Agadir', 'Tanger', 'Inconnue', '']),
           override=st.sampled_from([None, 1450, 1600, 1750]))
    def test_plus_de_panneaux_kwc_et_production_jamais_plus_bas(
            self, p, n, d_n, autres, ville, override):
        watt, designation = p
        bruit = [_ligne(a, 1) for a in autres]
        nb1, w1 = panneaux_et_watt_lu([_ligne(designation, n)] + bruit)
        nb2, w2 = panneaux_et_watt_lu([_ligne(designation, n + d_n)] + bruit)
        self.assertEqual((nb1, w1), (n, watt), 'lecture des lignes')
        self.assertEqual(w2, watt)
        self.assertGreaterEqual(nb2, nb1)
        kwc1, kwc2 = nb1 * w1 / 1000, nb2 * w2 / 1000
        self.assertGreaterEqual(kwc2, kwc1)
        prod = productible_for_city(ville, override)
        p1 = round(kwc1 * prod * PRODUCTION_DERATE)
        p2 = round(kwc2 * prod * PRODUCTION_DERATE)
        self.assertGreaterEqual(p2, p1, 'production annuelle baisse avec plus de panneaux')
        # production = kWc × productible × dérating (à l'arrondi entier près)
        self.assertAlmostEqual(p1, kwc1 * prod * PRODUCTION_DERATE, delta=0.5)

    @PUR
    @given(p=panneaux_st(), n=st.integers(1, 100),
           autres=st.lists(st.sampled_from(AUTRES), min_size=1, max_size=6))
    def test_lignes_non_panneau_ne_changent_ni_nombre_ni_watt(self, p, n, autres):
        _, designation = p
        seul = panneaux_et_watt_lu([_ligne(designation, n)])
        avec = panneaux_et_watt_lu([_ligne(designation, n)] + [_ligne(a, 3) for a in autres])
        self.assertEqual(seul, avec)

    @PUR
    @given(autres=st.lists(st.sampled_from(AUTRES), min_size=1, max_size=6))
    def test_sans_panneau_zero_et_watt_illisible(self, autres):
        nb, watt = panneaux_et_watt_lu([_ligne(a, 2) for a in autres])
        self.assertEqual(nb, 0)
        self.assertIsNone(watt)


class ViolationsConnuesTest(SimpleTestCase):
    """Chaque violation listée dans ``KNOWN_VIOLATIONS`` se reproduit encore."""

    def test_violations_connues_se_reproduisent_encore(self):
        for err_id, v in KNOWN_VIOLATIONS.items():
            with self.subTest(err_id):
                self.assertRegex(err_id, r'^ERR-QAH-PROP-[A-Z0-9-]+$')
                self.assertGreater(len(v['resume']), 40)
                try:
                    find(v['strategie'], v['viole'], settings=TROUVER)
                except NoSuchExample:
                    self.fail(
                        f'{err_id} : la violation connue ne se reproduit plus — '
                        "RETIRER l'entrée de KNOWN_VIOLATIONS (elle ne peut que "
                        'rétrécir).')

    def test_remise_100_exemple_minimal_ttc_zero(self):
        """ERR-QAH-PROP-TOTAUX-REMISE-100-NEGATIF — l'exemple réduit par
        Hypothesis (0,50 × 0,01, TVA 20 %, remise 100 %) rendait -0,01."""
        specs = [(Decimal('0.50'), Decimal('0.01'), Decimal('20'))]
        t = _totaux(specs, '100')
        self.assertEqual((t['ht_net'], t['tva'], t['ttc']),
                         (Decimal('0.00'), Decimal('0.00'), Decimal('0.00')))

    @PUR
    @given(specs=lignes_st)
    def test_remise_100_ttc_exactement_zero(self, specs):
        t = _totaux(specs, '100')
        self.assertEqual(t['ttc'], 0)
        self.assertEqual(t['ht_net'], 0)
        self.assertEqual(t['ttc'], t['ht_net'] + t['tva'])
