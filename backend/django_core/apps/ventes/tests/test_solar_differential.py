"""QAH3 (docs/PLAN.md, GROUPE QAH — « tester comme un humain ») — TEST
DIFFÉRENTIEL `solar.js` (écran) <-> `quote_engine/builder.py` (PDF) sur le
corpus FIGÉ PACT10 (``apps/ventes/tests/fixtures/solar_corpus.json`` /
``solar_corpus_expected.json``, générés par ``frontend/scripts/solar_corpus.mjs``
— lire l'en-tête de ce script pour la portée exacte et pourquoi).

CE QUE CE FICHIER COMPARE, ET RIEN D'AUTRE (jamais une comparaison inventée) :

  1. CLASSIFICATION de chaque ligne (réseau/injection, hybride, offgrid,
     batterie, panneau) — ``apps.ventes.solar_design`` (importé par
     ``builder.py`` sous les alias ``_is_battery``/``_is_hybrid_inverter``/
     ``_is_reseau_inverter``/``_is_offgrid_inverter``/``_is_inverter``/
     ``_is_panel``) contre les valeurs ``solar.js`` committées dans le fichier
     attendu. ATTENTION AU NOM (voir l'en-tête de ``solar_corpus.mjs``) :
     l'alias JS ``isAnyInverter`` correspond à ``_is_inverter`` — PAS à
     ``solar_design.is_any_inverter``, qui répond à une question différente
     (hybride OU réseau OU offgrid, donc faux sur un micro-onduleur non classé
     que ``_is_inverter``/``isAnyInverter`` reconnaissent comme onduleur).

  2. kWc DÉRIVÉ DES LIGNES — ``builder.panneaux_et_watt_lu(lignes)``, la
     fonction RÉELLEMENT utilisée par le moteur PDF (PVUNI), appelée sur des
     objets légers dupliquant l'interface qu'elle lit (``designation``,
     ``produit.nom``, ``quantite`` — aucune requête, ``getattr`` partout dans
     la fonction réelle).

  3. PRODUCTIBLE PAR VILLE (PVGIS, QX38) — ``quote_engine.productible.
     productible_for_city``, miroir déclaré exact de ``solar.js
     productibleForCity``.

  4. PRODUCTION ANNUELLE — ``kwc × productible × PRODUCTION_DERATE``
     (``quote_engine.pricing.PRODUCTION_DERATE``, miroir déclaré exact de
     ``solar.js PRODUCTIBLE_NET_FACTOR``) : SEULEMENT ce calcul fermé, jamais
     le reste de ``calculate_savings_roi`` (tarifs par tranche, décalage
     batterie horaire...) — hors périmètre de QAH3, voir l'en-tête de
     ``solar_corpus.mjs``.

  5. TOTAUX, ÉGALITÉ AU CENTIME — ``apps.ventes.selectors._canonical_totaux``,
     LA chaîne canonique que le backend facture réellement (celle que
     ``domain.argent.totaux``/``utils.options.option_totaux`` appellent, et
     que ``quote_engine.builder`` appelle pour le PDF, builder.py:1786),
     contre le total TTC de l'option effective que ``solar.js
     optionTotalsTTC`` calcule à l'écran (100 % TTC — CLAUDE.md).

  6. HORS PÉRIMÈTRE, VÉRIFIÉ ABSENT CÔTÉ PYTHON — pompe/débit/HMT.
     ``builder.py`` ne recalcule RIEN sur le pompage (grep confirmé : aucune
     fonction HMT/débit/pompe n'existe dans ce fichier) — il relit tel quel
     ``devis.etude_params``/``region``/``pompe_nom``, calculés UNE FOIS par
     ``solar.js`` à la création. Comparer reviendrait à comparer ``solar.js``
     à lui-même ; ``test_builder_ne_calcule_aucun_pompage`` verrouille ce
     constat pour que la portée reste honnête si ça change un jour.

DIVERGENCES — jamais un test assoupli pour repasser au vert (règle fondateur).
Une divergence RÉELLE devient une entrée de ``KNOWN_DIVERGENCES`` ci-dessous,
avec un id ``ERR-QAH-SOLAR-<SLUG>`` : le test exige que l'ENSEMBLE des entrées
divergentes mesurées soit EXACTEMENT celui-ci — une divergence NOUVELLE (pas
dans la liste) fait échouer le test, une divergence CORRIGÉE (encore dans la
liste mais qui ne se reproduit plus) le fait échouer aussi, pour que la liste
ne puisse que rétrécir avec intention. ``solar_corpus_expected.json`` n'est
JAMAIS régénéré pour faire disparaître une divergence : seul un humain qui a
tranché laquelle des deux moitiés a raison peut le faire (PACT10).

Run : ``python manage.py test apps.ventes.tests.test_solar_differential``
"""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes.quote_engine.builder import (
    _is_battery,
    _is_hybrid_inverter,
    _is_inverter,
    _is_offgrid_inverter,
    _is_panel,
    _is_reseau_inverter,
    panneaux_et_watt_lu,
)
from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE
from apps.ventes.quote_engine.productible import productible_for_city
from apps.ventes.selectors import _canonical_totaux

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
CORPUS_PATH = FIXTURES / 'solar_corpus.json'
EXPECTED_PATH = FIXTURES / 'solar_corpus_expected.json'

# ── Prédicats Python, mappés EXACTEMENT sur les clés du fichier attendu ──────
# (voir le point 1 de l'en-tête pour le piège isAnyInverter/_is_inverter).
PREDICATS = {
    'is_battery': lambda d, _n: _is_battery(d),
    'is_hybrid_inverter': lambda d, _n: _is_hybrid_inverter(d),
    'is_reseau_inverter': lambda d, _n: _is_reseau_inverter(d),
    'is_offgrid_inverter': lambda d, _n: _is_offgrid_inverter(d),
    'is_any_inverter': lambda d, _n: _is_inverter(d),
    'is_panel': lambda d, produit_nom: _is_panel(d, produit_nom),
}

# ── Divergences RÉELLES, mesurées, jamais silencieusement alignées ──────────
# ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER : `solar.js optionTotalsTTC` (aperçu
# ÉCRAN) additionne les prix TTC DÉJÀ arrondis ligne à ligne puis applique la
# remise sur cette somme ; la chaîne CANONIQUE backend
# (`selectors._canonical_totaux`, celle que le PDF facture réellement)
# applique la remise sur le HT BRUT, taux par taux, PUIS calcule la TVA — deux
# ordres d'arrondi structurellement différents (documentés comme tels par
# `domain/argent.py`, l'historique « sept chaînes monétaires » QJR49). Sur un
# devis MULTI-TAUX (panneaux 10 % + reste 20 %, le cas normal) avec une remise
# non nulle, les deux totaux peuvent différer d'UN centime. Impact mesuré :
# 36 des 200 entrées du corpus (18 %) divergent, TOUJOURS de ±0,01 MAD
# exactement (jamais plus — voir `test_ecart_maximal_mesure_reste_de_l_ordre_du_centime`)
# — le prix que l'écran affiche au vendeur pendant la composition peut donc
# différer d'UN CENTIME du prix RÉELLEMENT facturé (PDF/BC/facture) sur le
# MÊME devis. La liste ci-dessous est FIGÉE — mesurée UNE FOIS sur le corpus
# figé au moment de QAH3 (28/09/2026) par un script indépendant de ce fichier
# (jamais recalculée au chargement du module, pour ne PAS être auto-
# confirmante) — et ne doit RÉTRÉCIR (une correction alignant les deux
# chaînes) ou GRANDIR (régression, ou un nouveau corpus régénéré) qu'après
# décision d'un humain — jamais un ajustement muet.
KNOWN_DIVERGENCES = {
    'ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER': {
        'axe': 'total_ttc',
        'ecart_max_attendu_mad': Decimal('0.01'),
        # ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER CORRIGÉ (28/09/2026) : l'écran
        # applique désormais la chaîne canonique (`solar.js
        # totauxCanoniquesTtc`). Les 36 ids mesurés par QAH3 (QAH3-0001 …
        # QAH3-0197) ne divergent plus : l'ensemble attendu est VIDE. Ne
        # jamais le ré-élargir sans décision humaine.
        'ids': frozenset(),
    },
}


def _cas():
    with CORPUS_PATH.open(encoding='utf-8') as fh:
        corpus = json.load(fh)
    with EXPECTED_PATH.open(encoding='utf-8') as fh:
        expected = json.load(fh)
    by_id = {e['id']: e for e in expected['entries']}
    out = []
    for entry in corpus['entries']:
        out.append((entry, by_id[entry['id']]))
    return out


def _fake_ligne(line):
    """Objet léger dupliquant l'interface que `panneaux_et_watt_lu` lit par
    `getattr` (designation, produit.nom, quantite) — aucune requête, aucun
    modèle Django : la fonction réelle du moteur PDF, sur des données pures."""
    produit = SimpleNamespace(nom=line.get('produit_nom') or '')
    return SimpleNamespace(
        designation=line['designation'], produit=produit,
        quantite=line['quantite'])


def _canonical_ttc_total(lines, discount_pct, fallback_taux=Decimal('20')):
    """Le total TTC CANONIQUE (celui que le backend facture réellement) pour
    un lot de lignes — appelle `_canonical_totaux`, LA chaîne unique, sur des
    objets légers exposant `total_ht`/`taux_tva_effectif` (l'adaptateur que
    `builder._LigneArgentPdf` construit aussi, en plus léger)."""
    lignes = [
        SimpleNamespace(
            total_ht=Decimal(str(li['quantite'])) * Decimal(str(li['prix_unitaire_ht'])),
            taux_tva_effectif=Decimal(str(li['taux_tva'])))
        for li in lines
    ]
    resultat = _canonical_totaux(
        lignes, remise_globale_pct=Decimal(str(discount_pct)),
        fallback_taux=fallback_taux)
    return resultat['ttc']


def _divergences_totaux_mesurees():
    """Recalcule, à CHAQUE exécution du test (jamais mémorisé d'un run à
    l'autre), l'ensemble des ids dont le total canonique Python diverge (même
    un centime) du total écran JS committé — la mesure FRAÎCHE que
    `TotauxDifferentielTest` compare à `KNOWN_DIVERGENCES`, la liste FIGÉE et
    committée ci-dessus. Les deux sont indépendantes : ce n'est PAS
    `KNOWN_DIVERGENCES` qui se remplit toute seule ici (ça serait un test qui
    ne peut jamais rougir)."""
    divergents = []
    ecarts = []
    for entry, attendu in _cas():
        py_ttc = _canonical_ttc_total(entry['lines'], entry['discount_pct'])
        js_ttc = Decimal(str(attendu['total_ttc'])).quantize(Decimal('0.01'))
        if py_ttc != js_ttc:
            divergents.append(entry['id'])
            ecarts.append(abs(py_ttc - js_ttc))
    return divergents, (max(ecarts) if ecarts else Decimal('0'))


_DIVERGENTS_TOTAUX, _ECART_MAX_TOTAUX = _divergences_totaux_mesurees()


class CorpusFigeLisibleTest(SimpleTestCase):
    """Le corpus PACT10 et son fichier attendu sont lisibles, alignés, et
    couvrent bien les trois marchés que QAH3 doit exercer."""

    def test_corpus_et_attendu_alignes(self):
        cas = _cas()
        self.assertGreaterEqual(
            len(cas), 150, 'le corpus solar_corpus.json a régressé (< 150 entrées)')
        for entry, attendu in cas:
            self.assertEqual(entry['id'], attendu['id'])

    def test_trois_marches_couverts(self):
        marches = {entry['marche'] for entry, _ in _cas()}
        for attendu_marche in ('residentiel', 'industriel_commercial', 'agricole_pompage'):
            self.assertIn(attendu_marche, marches)


class ClassificationDifferentielleTest(SimpleTestCase):
    """Les six prédicats de classification, ligne par ligne, sur les ~200
    entrées du corpus — un `subTest` par (entrée, ligne, prédicat)."""

    def test_classification_identique_sur_tout_le_corpus(self):
        cas = _cas()
        self.assertTrue(cas, 'corpus vide — solar_corpus.json a régressé')
        for entry, attendu in cas:
            classifications = {c['designation']: c for c in attendu['classifications']}
            for i, line in enumerate(entry['lines']):
                d = line['designation']
                produit_nom = line.get('produit_nom') or ''
                attendu_ligne = attendu['classifications'][i]
                self.assertEqual(
                    attendu_ligne['designation'], d,
                    f"{entry['id']} ligne {i} — ordre désaligné entre le "
                    "corpus et le fichier attendu")
                for cle, fn in PREDICATS.items():
                    with self.subTest(cas=f"{entry['id']} « {d} »", predicat=cle):
                        self.assertEqual(
                            fn(d, produit_nom), attendu_ligne[cle],
                            f"{entry['id']} — « {d} » : {cle} attendu "
                            f"{attendu_ligne[cle]} (contrat PACT10 solar.js), "
                            f"obtenu {fn(d, produit_nom)}")
            del classifications  # utilisé seulement pour la lisibilité ci-dessus


class KwcDesLignesTest(SimpleTestCase):
    """`panneaux_et_watt_lu` (moteur PDF, PVUNI) contre le kWc dérivé des
    lignes calculé côté écran (composition `isPanel` + `parseWatt`).

    PORTÉE DE L'ÉGALITÉ — nb_panneaux/watt sont EXACTS des deux côtés (les
    deux moteurs LISENT la même chose) : comparaison au bit près. Le kWc
    dérivé (`nb_panneaux × watt / 1000`, arrondi 2 décimales) n'est PAS
    comparé au centime : `builder.py` l'arrondit avec le `round()` natif de
    Python (round-half-to-even, ex. round(3.125, 2) == 3.12), tandis que le
    fichier attendu l'arrondit côté générateur avec l'idiome JS
    `Math.round(x*100)/100` (round-half-up, ex. 3.125 -> 3.13) — UN ÉCART
    MESURÉ (31/200 entrées, systématiquement ±0,01 kWc sur les cas pile sur
    un multiple de 0,125) qui n'est PAS une divergence produit : aucune ligne
    de code de `solar.js` ne fait RÉELLEMENT ce calcul aujourd'hui (voir
    l'en-tête du fichier, point 2) — ce script en compose l'équivalent
    seulement pour comparer `isPanel`/`parseWatt`. Comparer ce chiffre au
    centime reviendrait à opposer DEUX CONVENTIONS D'ARRONDI DE CE TEST,
    jamais deux comportements produit — donc une tolérance de 0,02 kWc ici,
    PAS un `known_divergences` (rien à corriger dans le produit)."""

    def test_kwc_derive_des_lignes(self):
        for entry, attendu in _cas():
            with self.subTest(cas=entry['id']):
                fake_lines = [_fake_ligne(li) for li in entry['lines']]
                nb_panneaux, watt = panneaux_et_watt_lu(fake_lines)
                self.assertEqual(
                    nb_panneaux, attendu['nb_panneaux'],
                    f"{entry['id']} — nb_panneaux attendu "
                    f"{attendu['nb_panneaux']} (contrat), obtenu {nb_panneaux}")
                self.assertEqual(
                    watt, attendu['watt'],
                    f"{entry['id']} — watt lu attendu {attendu['watt']} "
                    f"(contrat), obtenu {watt}")
                if nb_panneaux > 0 and watt:
                    kwc = round(nb_panneaux * watt / 1000, 2)
                    self.assertAlmostEqual(
                        kwc, attendu['kwc_des_lignes'], delta=0.02,
                        msg=f"{entry['id']} — kWc dérivé attendu "
                        f"~{attendu['kwc_des_lignes']} (contrat, tolérance "
                        "0,02 — conventions d'arrondi différentes, voir la "
                        f"docstring de la classe), obtenu {kwc}")
                else:
                    self.assertIsNone(attendu['kwc_des_lignes'])


class ProductibleEtProductionTest(SimpleTestCase):
    """`productible_for_city` (QX38) et la formule fermée de production
    annuelle (`kwc × productible × PRODUCTION_DERATE`) — miroirs déclarés
    exacts de `productibleForCity`/`PRODUCTIBLE_NET_FACTOR` côté écran."""

    def test_productible_par_ville(self):
        for entry, attendu in _cas():
            with self.subTest(cas=entry['id'], ville=entry['ville']):
                productible = productible_for_city(
                    entry['ville'], entry['productible_override'])
                self.assertEqual(
                    productible, attendu['productible'],
                    f"{entry['id']} — productible_for_city({entry['ville']!r}, "
                    f"{entry['productible_override']!r}) attendu "
                    f"{attendu['productible']} (contrat QX38), obtenu {productible}")

    def test_production_annuelle_formule_fermee(self):
        for entry, attendu in _cas():
            with self.subTest(cas=entry['id']):
                productible = productible_for_city(
                    entry['ville'], entry['productible_override'])
                production = round(entry['kwc'] * productible * PRODUCTION_DERATE)
                self.assertEqual(
                    production, attendu['production_annuelle'],
                    f"{entry['id']} — production annuelle attendue "
                    f"{attendu['production_annuelle']} (contrat), obtenu "
                    f"{production}")


class TotauxDifferentielTest(SimpleTestCase):
    """Égalité au centime : total TTC canonique backend
    (`selectors._canonical_totaux`, celui que le PDF facture) contre le total
    TTC écran (`solar.js optionTotalsTTC`, committé dans le fichier attendu).

    DIVERGENCES ATTENDUES — voir `KNOWN_DIVERGENCES` en tête de fichier :
    l'ensemble mesuré des entrées divergentes DOIT être EXACTEMENT celui-ci,
    ni plus (régression), ni moins (correction non actée), jamais un
    ajustement muet du corpus pour repasser au vert.
    """

    def test_ensemble_des_divergences_est_celui_connu(self):
        attendu_ids = KNOWN_DIVERGENCES['ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER']['ids']
        mesures_ids = frozenset(_DIVERGENTS_TOTAUX)
        nouvelles = mesures_ids - attendu_ids
        corrigees = attendu_ids - mesures_ids
        self.assertFalse(
            nouvelles,
            f"NOUVELLE(S) divergence(s) de total non enregistrée(s) dans "
            f"KNOWN_DIVERGENCES (ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER) : "
            f"{sorted(nouvelles)} — vérifier si c'est une vraie régression ou "
            "un cas à ajouter à la liste (jamais l'inverse, jamais muet).")
        self.assertFalse(
            corrigees,
            f"Divergence(s) enregistrée(s) qui ne se reproduisent plus : "
            f"{sorted(corrigees)} — RÉTRÉCIR KNOWN_DIVERGENCES (une correction "
            "a dû aligner les deux chaînes, bonne nouvelle : mettre à jour la "
            "liste, jamais laisser une entrée obsolète).")

    def test_ecart_maximal_mesure_reste_de_l_ordre_du_centime(self):
        # Garde-fou de PROPORTION, pas de tolérance déguisée : si l'écart
        # dépasse 1 MAD, ce n'est plus « un ordre d'arrondi différent », c'est
        # une VRAIE divergence de calcul qui mérite sa propre enquête —
        # jamais absorbée silencieusement dans ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER.
        self.assertLess(
            _ECART_MAX_TOTAUX, Decimal('1.00'),
            f"écart maximal mesuré {_ECART_MAX_TOTAUX} MAD — dépasse l'ordre "
            "du centime attendu pour un pur écart d'arrondi ; ceci sent une "
            "VRAIE divergence de calcul, à enquêter séparément (nouvelle "
            "entrée ERR-QAH-SOLAR-…, jamais fondue dans TOTALS-ROUNDING-ORDER).")


class BuilderNeCalculeAucunPompageTest(SimpleTestCase):
    """Verrou de PORTÉE (point 6 de l'en-tête) : `builder.py` ne porte AUCUNE
    fonction de calcul pompe/débit/HMT — il relit `etude_params` tel quel.
    Si ce test casse un jour (une fonction de ce nom apparaît), la portée de
    QAH3 doit être REVUE pour ajouter un vrai axe de comparaison pompage —
    d'ici là, comparer serait comparer `solar.js` à lui-même."""

    def test_aucune_fonction_pompage_dans_builder(self):
        import apps.ventes.quote_engine.builder as builder_module
        noms = dir(builder_module)
        suspects = [n for n in noms if 'pompe' in n.lower() or 'hmt' in n.lower()
                    or 'debit' in n.lower()]
        self.assertEqual(
            suspects, [],
            f"builder.py porte désormais {suspects} — la note de portée de "
            "QAH3 (« hors périmètre, vérifié absent ») est PÉRIMÉE : ajouter "
            "un vrai axe de comparaison pompe/débit/HMT à ce fichier.")
