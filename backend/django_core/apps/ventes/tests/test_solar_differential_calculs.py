"""QAH-PROP (feature #3 du lot QA) — TEST DIFFÉRENTIEL #2 `solar.js` (écran)
<-> Python, sur les CALCULS que ``test_solar_differential`` (QAH3) laissait HORS
PÉRIMÈTRE : tarifs par tranche, factures -> consommation, consommation ->
facture, économies « deux factures », ROI/payback/autoconsommation, et
dimensionnement pompage. C'est exactement là que vivaient les huit bugs de
miroir trouvés avant ce lot (1,20 MAD/kWh pour un distributeur nommé, inversion
énergie seule d'une facture TOTALE, …).

COMMENT. Même patron que QAH3 (PACT10) — deux fichiers FIGÉS, générés par
``frontend/scripts/solar_calculs_corpus.mjs`` (PRNG seedé, ~930 entrées qui
visent les branches limites : aucun distributeur, « autre », SRM, factures
nulles / un mois / été != hiver / énormes, bornes de tranche exactes, une ou
deux options, catalogues pompage à noms pièges) :

  * ``fixtures/solar_calculs_corpus.json``   — les ENTRÉES ;
  * ``fixtures/solar_calculs_expected.json`` — ce que ``solar.js`` calcule
    (relu et re-vérifié côté écran par ``solar.calculs.corpus.test.mjs``).

Ce fichier recalcule chaque entrée avec la fonction Python RÉELLE jumelle :

  ===================  =====================================================
  axe                  jumeaux
  ===================  =====================================================
  tranche_bill         monthlyBillFromKwh <-> pricing._monthly_bill_from_kwh
  bill_to_kwh          kwhFromBill        <-> pricing.kwh_from_bill
  facture_detail       factureMad/tppanMad <-> bareme.facture_mad/tppan_mad
  conso_annuelle       consoAnnuelleDepuisFactures <-> Σ kwh_from_bill
                       ET <-> etude_horaire.serie_kwh_depuis_mad (axe
                       ``conso_annuelle_serveur``, l'inversion que le
                       serveur applique RÉELLEMENT)
  two_bills            twoBillsSavings    <-> pricing.two_bills_savings
  roi                  computeROI         <-> pricing.calculate_savings_roi
  pompe_debit          debitAtHmt         <-> pompage._debit_a_hmt
  pompe_select         selectPompeByCurve <-> pompage.selection_pompe
  pompe_variateur      selectVariateurVeichi <-> pompage.selection_variateur
  ===================  =====================================================

DIVERGENCES — jamais un test assoupli (règle fondateur, comme QAH3). Une
divergence RÉELLE est une entrée de ``fixtures/solar_calculs_known_divergences
.json`` (id ``ERR-QAH-DIFF-…`` + la liste FIGÉE des ids d'entrées concernées,
mesurée UNE FOIS par un script indépendant, jamais recalculée au chargement) :
le test exige que l'ENSEMBLE mesuré soit EXACTEMENT celui-là — une divergence
NOUVELLE fait échouer, une divergence CORRIGÉE (encore listée mais qui ne se
reproduit plus) aussi, pour que la liste ne puisse que RÉTRÉCIR avec
intention. Le corpus n'est JAMAIS régénéré pour faire disparaître une
divergence : seul un humain qui a tranché laquelle des deux moitiés a raison
peut le faire (PACT10).

Aucune base de données : SimpleTestCase, fonctions pures.

Run : ``python manage.py test apps.ventes.tests.test_solar_differential_calculs``
"""
import json
import math
from pathlib import Path

from django.test import SimpleTestCase

from apps.calepinage.services import pompage as pompage_py
from apps.ventes.etude_horaire import serie_kwh_depuis_mad
from apps.ventes.quote_engine import bareme
from apps.ventes.quote_engine.pricing import (
    ONEE_TRANCHES,
    _monthly_bill_from_kwh,
    calculate_savings_roi,
    kwh_from_bill,
    two_bills_savings,
)

FIXTURES = Path(__file__).resolve().parent / 'fixtures'
CORPUS_PATH = FIXTURES / 'solar_calculs_corpus.json'
EXPECTED_PATH = FIXTURES / 'solar_calculs_expected.json'
KNOWN_PATH = FIXTURES / 'solar_calculs_known_divergences.json'

# Tolérance NUMÉRIQUE : les deux moteurs font la même arithmétique flottante
# IEEE-754 dans le même ordre ; on n'accepte que le bruit d'un dernier bit.
REL_TOL = 1e-9
ABS_TOL = 1e-6


def _charger(path):
    with path.open(encoding='utf-8') as fh:
        return json.load(fh)


def _table_py(table):
    """'onee' -> la grille ONEE sélective ; une liste JSON -> liste de paires."""
    return ONEE_TRANCHES if table == 'onee' else table


def _jsround(x):
    """Math.round de JS (demi vers +inf) — pour reconstruire une ENTRÉE que le
    script JS a arrondie avant de l'envoyer, jamais pour arrondir un résultat."""
    return math.floor(x + 0.5)


# ── Le calcul Python jumeau de chaque axe — mêmes clés que le fichier attendu ──
def _py_tranche_bill(e):
    return {'bill': _monthly_bill_from_kwh(e['kwh'], _table_py(e['table']))}


def _py_bill_to_kwh(e):
    r = kwh_from_bill(e['bill'], e['utility'], e['table'])
    return {'kwh': r['kwh_mensuel'], 'approximatif': r['approximatif'],
            'estimation': r['estimation']}


def _py_facture_detail(e):
    tranches = None if e['table'] == 'onee' else e['table']
    f = bareme.facture_mad(e['kwh'], jours=e['jours'], tranches=tranches)
    return {'energie': f['energie_mad'], 'fixes': f['location_entretien_mad'],
            'tppan': f['tppan_mad'], 'total': f['total_mad'],
            'tppan_seul': bareme.tppan_mad(e['kwh'], jours=e['jours'])}


def _py_conso_annuelle(e):
    """Jumeau DÉCLARÉ de l'écran : somme des kWh/mois de ``kwh_from_bill``
    (inversion énergie seule), arrondie à l'entier."""
    if not e['factures']:
        return {'conso': 0}
    total = sum(kwh_from_bill(b, e['utility'])['kwh_mensuel'] or 0
                for b in e['factures'])
    return {'conso': _jsround(total) if total > 0 else 0}


def _py_conso_annuelle_serveur(e):
    """L'inversion que le SERVEUR applique aux douze factures d'un devis :
    ``etude_horaire.serie_kwh_depuis_mad`` (barème complet, lignes fixes et
    TPPAN retirées). Seulement sur une série de douze mois."""
    if len(e['factures']) != 12:
        return None
    kwh, _ = serie_kwh_depuis_mad(list(e['factures']))
    total = sum(kwh) if kwh else 0
    return {'conso': _jsround(total) if total > 0 else 0}


def _py_two_bills(e):
    r = two_bills_savings(e['production'], e['conso'], e['ratio'], e['utility'],
                          e['table'])
    if r is None:
        return {'null': True}
    return {'facture_sans': r['facture_sans'], 'facture_avec': r['facture_avec'],
            'economie': r['economie'], 'autoconso_kwh': r['autoconso_kwh']}


def _py_roi(e):
    total_avec = _jsround(e['totalSans'] * e['facteurAvec'])
    r = calculate_savings_roi(
        e['kwp'], e['totalSans'], total_avec,
        conso_annuelle_kwh=e['conso'], utility=e['utility'],
        battery_kwh=e['batteryKwh'], productible=e['productible'])
    return {
        'modele': r['savings_model'], 'production': r['prod_kwh'],
        'eco_sans': r['eco_s_ann'], 'eco_avec': r['eco_a_ann'],
        # JS rend null quand l'économie est nulle ; Python 0.0 — même sens.
        'payback_sans': r['roi_s'] or None, 'payback_avec': r['roi_a'] or None,
        'autoconso_sans': r['autoconso_sans'], 'autoconso_avec': r['autoconso_avec'],
        'facture_sans': r['facture_sans'], 'facture_avec_sans': r['facture_avec_s'],
        'facture_avec_avec': r['facture_avec_a'],
        'net_gain_sans': r['net_gain_sans'], 'net_gain_avec': r['net_gain_avec'],
    }


def _py_pompe_debit(e):
    return {'debit': pompage_py._debit_a_hmt(e['courbe'], e['hmt'])}


def _py_pompe_select(e):
    r = pompage_py.selection_pompe(
        e['pompes'], hmt=e['hmt'], debit_souhaite_m3h=e['debit'],
        type_pompe=e['typePompe'], alim=e['alim'])
    p = r['pompe']
    return {'pompe_id': p['id'] if p else None, 'kw': r['kw'],
            'debit_hmt': r['debit_hmt_m3h'], 'sans_prix': r['sans_prix'],
            'ecart_phase': r['ecart_phase']}


def _py_pompe_variateur(e):
    r = pompage_py.selection_variateur(e['variateurs'], e['kw'], e['alim'])
    v = r['variateur']
    return {'variateur_id': v['id'] if v else None, 'insuffisant': r['insuffisant']}


PY = {
    'tranche_bill': _py_tranche_bill, 'bill_to_kwh': _py_bill_to_kwh,
    'facture_detail': _py_facture_detail, 'conso_annuelle': _py_conso_annuelle,
    'two_bills': _py_two_bills, 'roi': _py_roi, 'pompe_debit': _py_pompe_debit,
    'pompe_select': _py_pompe_select, 'pompe_variateur': _py_pompe_variateur,
}


def _egal(a, b):
    """Égalité de deux valeurs de sortie (nombres à ±1 dernier bit, le reste
    exactement). ``None`` (JSON null) n'est égal qu'à ``None``."""
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_egal(x, y) for x, y in zip(a, b))
    return a == b


def _champs_divergents(js, py, ignorer=()):
    """Les clés dont la valeur JS et la valeur Python diffèrent."""
    cles = (set(js) | set(py)) - {'id', 'axe'} - set(ignorer)
    return sorted(c for c in cles if not _egal(js.get(c), py.get(c)))


# Champs NON comparés, et POURQUOI (jamais un champ ignoré en silence).
IGNORES = {
    # Modèle « estimation » (aucun distributeur/aucune conso) : ancien forfait
    # PAR CONCEPTION différent des deux côtés (écran 1,75 MAD × part diurne 50 %,
    # PDF prix société/repli 1,20 × 0,60) — documenté, pas un miroir.
    'roi_estimation': ('eco_sans', 'eco_avec', 'payback_sans', 'payback_avec',
                       'autoconso_sans', 'autoconso_avec', 'net_gain_sans',
                       'net_gain_avec'),
}


def _comparaison(entry, js):
    """[(axe_comparé, id, champs_divergents)] pour UNE entrée du corpus."""
    axe = entry['axe']
    out = []
    py = PY[axe](entry)
    if axe == 'roi':
        js = dict(js)
        prod_js, prod_py = js.pop('production'), py.pop('production')
        if entry['productible'] is None:
            # SANS productible passé, l'écran retombe sur son chemin HISTORIQUE
            # (GHI mensuel × 0,8, ≈ 1 256 kWh/kWc) alors que le PDF retombe sur
            # le productible par défaut du dépôt (1 651 × 0,93 ≈ 1 536 kWh/kWc)
            # : production DIFFÉRENTE pour les mêmes entrées. Ce chemin diverge
            # PAR CONSTRUCTION, donc tout ce qui en découle aussi (économies,
            # payback…) — on ne compare que le MODÈLE choisi ; la production
            # est comparée à part et sa divergence est ENREGISTRÉE.
            champs = _champs_divergents(
                {'modele': js['modele']}, {'modele': py['modele']})
        else:
            ignorer = IGNORES['roi_estimation'] if js['modele'] == 'estimation' else ()
            champs = _champs_divergents(js, py, ignorer)
        # `production` : le JS arrondit à 0,1 kWh la somme mensuelle, le PDF à
        # l'entier — comparé à ±0,5 kWh (jamais une convention d'arrondi
        # confondue avec une divergence de calcul).
        if abs(prod_js - prod_py) > 0.5 + 1e-6:
            champs.append('production')
        out.append(('roi', entry['id'], sorted(champs)))
        return out
    if (axe == 'bill_to_kwh' and js['kwh'] is not None and py['kwh'] is not None
            and abs(js['kwh'] - py['kwh']) <= 0.1 + 1e-9):
        # Convention d'arrondi au 0,1 kWh : `Math.round(x*10)/10` (demi vers le
        # haut, JS) contre `round(x, 1)` (plus proche exact de la valeur binaire,
        # Python) — 34,98 MAD / 1,20 = 29,15 -> 29,2 en JS, 29,1 en Python.
        # ±0,1 kWh/mois (1,2 kWh/an), JAMAIS un écart de calcul : tolérance d'UN
        # pas d'arrondi, documentée, pas une divergence produit (même logique que
        # la tolérance 0,02 kWc de QAH3).
        js, py = dict(js), dict(py)
        js['kwh'] = py['kwh'] = 0
    out.append((axe, entry['id'], _champs_divergents(js, py)))
    if axe == 'conso_annuelle':
        serveur = _py_conso_annuelle_serveur(entry)
        if serveur is not None:
            out.append(('conso_annuelle_serveur', entry['id'],
                        _champs_divergents(js, serveur)))
    return out


def _mesurer():
    """Recalcule, à CHAQUE exécution, ``{(axe, champ): {ids}}`` de TOUTES les
    divergences JS <-> Python du corpus figé — la mesure FRAÎCHE que le test
    compare à la liste FIGÉE et COMMITÉE (``solar_calculs_known_divergences
    .json``). Indépendante d'elle : ce n'est pas la liste qui se remplit."""
    corpus = _charger(CORPUS_PATH)
    attendu = {e['id']: e for e in _charger(EXPECTED_PATH)['entries']}
    mesure = {}
    for entry in corpus['entries']:
        for axe, ident, champs in _comparaison(entry, attendu[entry['id']]):
            for champ in champs:
                mesure.setdefault((axe, champ), set()).add(ident)
    return mesure


_MESURE = _mesurer()


def _connu():
    """``{(axe, champ): {ids}}`` depuis le fichier figé, + les métadonnées."""
    brut = _charger(KNOWN_PATH)
    connu = {}
    for err_id, v in brut['divergences'].items():
        for cle, ids in v['constats'].items():
            axe, champ = cle.split('.', 1)
            connu[(axe, champ)] = (err_id, frozenset(ids))
    return brut, connu


class CorpusCalculsLisibleTest(SimpleTestCase):
    def test_corpus_et_attendu_alignes(self):
        corpus, attendu = _charger(CORPUS_PATH), _charger(EXPECTED_PATH)
        self.assertGreaterEqual(len(corpus['entries']), 800)
        self.assertEqual([e['id'] for e in corpus['entries']],
                         [e['id'] for e in attendu['entries']])

    def test_tous_les_axes_couverts(self):
        axes = {e['axe'] for e in _charger(CORPUS_PATH)['entries']}
        self.assertEqual(axes, set(PY))

    def test_branches_limites_dans_le_corpus(self):
        entries = _charger(CORPUS_PATH)['entries']
        b2k = [e for e in entries if e['axe'] == 'bill_to_kwh']
        utilisateurs = {str(e['utility'] or '').strip().lower() for e in b2k}
        for u in ('', 'onee', 'autre', 'srm-casablanca-settat'):
            self.assertIn(u, utilisateurs)
        self.assertTrue(any(e['bill'] <= 0 for e in b2k))
        roi = [e for e in entries if e['axe'] == 'roi']
        self.assertTrue(any(e['batteryKwh'] == 0 for e in roi))
        self.assertTrue(any(e['batteryKwh'] > 0 for e in roi))
        self.assertTrue(any(e['conso'] is None for e in roi))


class DifferentielCalculsTest(SimpleTestCase):
    """L'ENSEMBLE des divergences mesurées est EXACTEMENT la liste connue."""

    def test_ensemble_des_divergences_est_celui_connu(self):
        _, connu = _connu()
        nouvelles, corrigees = [], []
        for cle, ids in sorted(_MESURE.items()):
            attendus = connu.get(cle, (None, frozenset()))[1]
            en_plus = ids - attendus
            if en_plus:
                nouvelles.append((cle, sorted(en_plus)[:5], len(en_plus)))
        for cle, (err_id, ids) in sorted(connu.items()):
            en_moins = ids - _MESURE.get(cle, set())
            if en_moins:
                corrigees.append((err_id, cle, sorted(en_moins)[:5], len(en_moins)))
        self.assertFalse(
            nouvelles,
            "NOUVELLE(S) divergence(s) JS<->Python non enregistrée(s) "
            "(axe, champ, 5 premiers ids, total) : "
            f"{nouvelles} — vérifier si c'est une vraie régression ou un cas à "
            "ajouter à solar_calculs_known_divergences.json (jamais muet).")
        self.assertFalse(
            corrigees,
            "Divergence(s) enregistrée(s) qui ne se reproduisent plus : "
            f"{corrigees} — RÉTRÉCIR solar_calculs_known_divergences.json (une "
            "correction a aligné les deux moitiés : bonne nouvelle, mettre la "
            "liste à jour, jamais laisser une entrée obsolète).")

    def test_chaque_divergence_connue_a_un_id_et_un_resume(self):
        brut, _ = _connu()
        self.assertTrue(brut['divergences'])
        for err_id, v in brut['divergences'].items():
            self.assertRegex(err_id, r'^ERR-QAH-DIFF-[A-Z0-9-]+$')
            self.assertGreater(len(v['resume']), 30, err_id)
            self.assertTrue(v['constats'], err_id)
            self.assertTrue(v['exemple'], err_id)
            # Les ids listés existent bien dans le corpus figé.
            existants = {e['id'] for e in _charger(CORPUS_PATH)['entries']}
            for cle, ids in v['constats'].items():
                self.assertTrue(ids, f'{err_id} {cle}')
                self.assertFalse(set(ids) - existants, f'{err_id} {cle}')

    def test_les_axes_sans_divergence_restent_sans_divergence(self):
        """Verrou de portée : les axes de fermeture (tranches, facture
        détaillée, économies, pompage) n'ont AUCUNE divergence connue — toute
        entrée nouvelle sur ces axes est une régression, pas une « divergence à
        lister »."""
        _, connu = _connu()
        axes_connus = {axe for (axe, _champ) in connu}
        for axe in ('tranche_bill', 'facture_detail', 'two_bills', 'pompe_debit'):
            self.assertNotIn(axe, axes_connus, f"axe {axe} : divergence enregistrée")
            self.assertFalse(
                [k for k in _MESURE if k[0] == axe],
                f"axe {axe} : divergence mesurée {[k for k in _MESURE if k[0] == axe]}")
