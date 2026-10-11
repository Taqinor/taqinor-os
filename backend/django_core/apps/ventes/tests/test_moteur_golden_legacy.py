"""SPL161 — golden du moteur LEGACY (``render_html_for``) AVANT tout
déplacement de ``generate_devis_premium.py`` (capture seule, aucun
déplacement).

Le HTML comparé est celui que ``render_html_for`` remet à WeasyPrint — le
document réel, jamais une regex de source ni un mock du moteur. Les cas sont
rendus sous ``_RENDER_LOCK`` dans un ORDRE FIXE (``CAS``) : l'ingestion écrit
les globales du module et une clé absente d'une charge utile peut garder la
valeur du rendu précédent ; le golden fige cette séquence telle quelle. Avant
la séquence, les globales « données » du moteur et les ``rcParams`` de
matplotlib sont ramenés à leur état à l'IMPORT de ce module (état d'un
processus neuf) : sans cela le golden dépendrait des tests passés avant lui
dans le même processus (ordre variable sous ``--parallel``). L'état d'avant le
test est restauré à la fin.

UN json PAR CAS sous ``golden/moteur/legacy/`` : sha256 du HTML masqué, sha256
par segment (en-tête puis chaque ``<div class="page"``, pour localiser un
écart), nombre de pages, compteurs de masques, empreinte des graphes d'étude.

Masques — SEULEMENT le non-déterministe qui ne bouge pas : le base64 des
polices woff2 et les PNG de ``make_chart_roi`` / ``make_chart_monthly``
(cadre 680×170). Le PNG de ``make_chart_etude`` (déplacé par SPL169) n'est PAS
masqué : son tableau de pixels DÉCODÉ est haché (mode + taille + pixels) et
l'empreinte remplace le base64 dans le HTML haché — une mauvaise
qualification ``_g.`` après déplacement y serait visible.

WeasyPrint change le HTML du une-page (``_mesure_onepage`` mesure la page
composée et tronque) : le golden n'est capturé et vérifié que dans l'image
backend, et le test est SAUTÉ proprement quand WeasyPrint est absent. Capture
(une fois ; une tâche SPL ne re-capture JAMAIS — CIQ327 / CIQ340, si elles
fusionnent après, re-capturent leurs seuls cas). ``SimpleTestCase`` : aucune
base n'est créée. ``scripts/test-backend.ps1`` ne transmet au conteneur que
``DJANGO_SETTINGS_MODULE`` ; ``UPDATE_GOLDEN`` se passe donc par ``-e``,
depuis la racine du dépôt :

    docker compose run --rm --no-deps \\
        -e DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev \\
        -e UPDATE_GOLDEN=1 django_core \\
        python manage.py test apps.ventes.tests.test_moteur_golden_legacy

puis la vérification, sans ``UPDATE_GOLDEN`` :

    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_moteur_golden_legacy"

Golden absent ⇒ rouge ; deux exécutions consécutives sans ``UPDATE_GOLDEN``
donnent les mêmes hachages.

Cas directs (``BankableConcordeTests``, sans WeasyPrint) :
``_bankable_concorde_avec_la_page`` lit ``globals().get("ETUDE")`` — avant
toute ingestion (``ETUDE`` absent du module) elle rend True ; après
``moteur.ETUDE = …`` contradictoire, False. État restauré au tearDown.
"""
import base64
import copy
import hashlib
import io
import json
import os
import re
import types
import unittest
from pathlib import Path

import matplotlib
from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine import generate_devis_premium as moteur
from apps.ventes.quote_engine import i18n_labels
from apps.ventes.tests import _moteur_fixtures as F

try:
    import weasyprint  # noqa: F401
    _WEASY = True
except Exception:  # noqa: BLE001 — bibliothèques Pango absentes (hôte)
    _WEASY = False

DOSSIER = Path(__file__).resolve().parent / 'golden' / 'moteur' / 'legacy'


# ── état « processus neuf » du moteur ──────────────────────────────────────

def _est_donnee(nom, valeur):
    """Globale « donnée » du moteur (ni module, ni fonction, ni classe)."""
    if nom.startswith('__'):
        return False
    if isinstance(valeur, (types.ModuleType, type)) or callable(valeur):
        return False
    return True


def _etat_donnees():
    """Copie profonde des globales « données » du moteur (le verrou et les
    objets non copiables sont laissés tels quels)."""
    etat = {}
    for nom, valeur in list(vars(moteur).items()):
        if not _est_donnee(nom, valeur):
            continue
        try:
            etat[nom] = copy.deepcopy(valeur)
        except Exception:  # noqa: BLE001 — RLock & co : jamais réécrits
            continue
    return etat


def _restaurer(etat):
    """Ramène les globales « données » du moteur à ``etat`` : celles posées
    depuis (``ETUDE``…) sont retirées, les autres réécrites."""
    for nom, valeur in list(vars(moteur).items()):
        if _est_donnee(nom, valeur) and nom not in etat:
            try:
                copy.deepcopy(valeur)
            except Exception:  # noqa: BLE001 — non copiable : jamais pris
                continue
            delattr(moteur, nom)
    for nom, valeur in etat.items():
        setattr(moteur, nom, copy.deepcopy(valeur))


#: État du moteur et de matplotlib à l'IMPORT de ce module (découverte des
#: tests, avant tout rendu) — ``_moteur_fixtures`` a déjà importé le renderer
#: résidentiel, dont ``charts.py`` pose ses ``rcParams`` à l'import.
_ETAT_A_L_IMPORT = _etat_donnees()
_RC_A_L_IMPORT = {cle: valeur
                  for cle, valeur in matplotlib.rcParams.copy().items()
                  if cle != 'backend'}


# ── charges utiles (copies FIGÉES : un golden ne suit pas une autre fixture) ─

#: ``test_qjr115_production_unique._etude(PROD_CARTE)`` — étude servable avec
#: bloc bancable concordant (P50 = carte « Production annuelle »).
ETUDE_PRODUCTION_UNIQUE = {
    'kwc': 9.94, 'conso_annuelle': 120000, 'taux_autoconso': 100,
    'taux_couverture': 10.4, 'economies_annuelles': 21851, 'payback': 3.0,
    'prix_kwc': 6543, 'prod_mensuelle': [1040] * 12,
    'conso_mensuelle': [10000] * 12, 'production_annuelle': 12486,
    'bankable': {
        'zones': [{'label': 'Pan Sud', 'kwc': 9.94,
                   'base_production_kwh': 13000}],
        'pr': {'p50_kwh': 12486, 'p90_kwh': 10200,
               'performance_ratio': 0.80,
               'loss_breakdown': {'temperature': 8.0, 'soiling': 3.0},
               'total_loss_pct': 20.0},
    },
}

#: ``test_qjr_optimum_publie`` — ``{'dimensionnement': _dim()}`` (optimum
#: de 14 panneaux / 5 kWh, publié quand le devis vend cette configuration).
_COMBINAISON = {
    'panneaux': 14, 'kwc': 7.7, 'batterie_kwh': 5.0,
    'residuel_kwh_mois': 420.0,
    'tranche_apres': {'rang': 5, 'libelle': 'Tranche 5 (401-500 kWh)'},
    'remplissage': {'moyen': 0.62},
}
ETUDE_OPTIMUM_PUBLIE = {'dimensionnement': {
    'falaise': {
        'tranche_actuelle': {'rang': 6, 'libelle': 'Tranche 6 (>500)'},
        'tranche_visee': {'rang': 5, 'libelle': 'Tranche 5 (401-500)'},
        'cible_kwh_mois': 500.0,
    },
    'meilleure_falaise': dict(_COMBINAISON),
    'recommandation_avec': dict(_COMBINAISON),
}}

#: ``test_agr302_onepage_agricole_formats.ETUDE_COURBE`` — pompage avec
#: courbe (m³/jour imprimé).
ETUDE_POMPAGE = {
    'pompe_cv': '5.5', 'pompe_kw': 3.7, 'type_pompe': 'immergee',
    'alim': 'tri', 'hmt_m': '62.5', 'debit_hmt_m3h': 30.5,
    'heures_pompage': 7, 'm3_jour': 213, 'champ_kwc': 5.68,
}

#: ``test_quote_engine_formats.QJR163FinitionsTests._design(5)``.
DESIGN_ELECTRIQUE = {
    'chaines': [{'pan': 1, 'mppt': 1, 'nb_modules': 7,
                 'vmp_froid_v': 268.0, 'voc_froid_v': 327.2,
                 'vmp_chaud_v': 212.8, 'conforme': True}],
    'conformite': {'conforme': True, 'bloquants': [], 'alertes': []},
    'bom': [{'designation': 'Composant %02d' % i, 'quantite': i + 1,
             'spec': 'spec %02d' % i} for i in range(5)],
}

#: ``test_qjr666_premium_residentiel_options.SVG``.
SVG_CALEPINAGE = ('<svg xmlns="http://www.w3.org/2000/svg" '
                  'viewBox="0 0 400 200">'
                  '<rect x="10" y="10" width="80" height="40"/></svg>')

MULTI_VILLA = {
    'groupes': [
        {'index': 1, 'label': 'Villa A',
         'totaux': {'ht_net': 28000.0, 'ttc': 33600.0}},
        {'index': 2, 'label': 'Villa B',
         'totaux': {'ht_net': 28000.0, 'ttc': 33600.0}},
        {'index': 3, 'label': 'Villa C',
         'totaux': {'ht_net': 28000.0, 'ttc': 33600.0}},
    ],
    'grand_total': {'ht_net': 84000.0, 'ttc': 100800.0},
}

LIGNES_STRUCTURE = [
    {'type': 'section', 'ordre': 0, 'texte': 'Champ PV'},
    {'type': 'note', 'ordre': 2, 'texte': 'Pose sous 3 semaines.'},
]
OPTIONS_PROPOSEES = [
    {'designation': 'Monitoring 5 ans', 'quantite': 1,
     'prix_unit_ht': 1250.0, 'taux_tva': 20, 'total_ttc': 1500.0},
]

#: ``test_qjr668_clauses_cgv.CLAUSE`` / ``CLAUSE_2`` (forme servie).
CLAUSES_CGV = [
    {'nom': 'Garantie de production',
     'corps_texte': 'QJR668 production garantie quatre-vingt-dix pour cent'},
    {'nom': 'Pénalités de retard',
     'corps_texte': 'QJR668 pénalité un pour mille par jour'},
]
NOTE_CLIENT = 'Accès au toit par l\'escalier de service, prévenir la veille.'
NOTE_CLIENT_LONGUE = ' '.join(
    ['Accès au toit par l\'escalier de service, prévenir la veille ;'] * 8)

#: (nom, variante de ``donnees_legacy``, surcharges). ORDRE FIXE — voir la
#: docstring : ne pas réordonner sans re-capturer.
CAS = (
    ('variante_deux', 'deux', {}),
    ('variante_sans', 'sans', {}),
    ('variante_long', 'long', {}),
    ('onepage_residentiel', 'deux', {'pdf_mode': 'onepage'}),
    ('onepage_agricole', 'deux', {
        'pdf_mode': 'onepage', 'mode_installation': 'agricole',
        'etude': ETUDE_POMPAGE}),
    ('etude_production_unique', 'deux', {
        'include_etude': True, 'etude': ETUDE_PRODUCTION_UNIQUE,
        'puissance_kwc': 9.94}),
    ('etude_optimum_publie', 'deux', {
        'include_etude': True, 'etude': ETUDE_OPTIMUM_PUBLIE,
        'nb_panneaux': 14, 'batterie_kwh_total': 5.0}),
    ('annexe_technique', 'deux', {
        'include_annexe_technique': True,
        'electrical_design': DESIGN_ELECTRIQUE}),
    ('calepinage', 'deux', {
        'include_calepinage': True, 'include_calepinage_demande': True,
        'calepinage_svg': SVG_CALEPINAGE,
        'calepinage_empreinte': 'calepinage ab12'}),
    ('signe_au_domicile', 'deux', {'signe_au_domicile': True}),
    # Langue : le 3 pages legacy n'imprime ses libellés traduits (``_L``)
    # que sur l'arrondi multi-villas — HTML masqué fr/en/ar identique sur
    # cette fixture (mesuré) ; c'est le une-page qui traduit (NTI18N5).
    ('onepage_langue_en', 'deux', {
        'pdf_mode': 'onepage', 'langue_sortie': 'en',
        'libelles_document': i18n_labels.libelles('en')}),
    ('onepage_langue_ar', 'deux', {
        'pdf_mode': 'onepage', 'langue_sortie': 'ar',
        'libelles_document': i18n_labels.libelles('ar')}),
    ('devis_final_mensuel', 'deux', {
        'devis_final': True, 'show_monthly': True}),
    ('multi_villa', 'sans', {
        'nombre_proprietes': 3, 'display_total_multi': 100800.0,
        'multi_villa': MULTI_VILLA}),
    ('structure_options', 'deux', {
        'lignes_structure': LIGNES_STRUCTURE,
        'options_proposees': OPTIONS_PROPOSEES}),
    ('structure_options_onepage', 'deux', {
        'pdf_mode': 'onepage', 'lignes_structure': LIGNES_STRUCTURE,
        'options_proposees': OPTIONS_PROPOSEES}),
    ('filigrane', 'deux', {
        '_watermark_standard': 'Mohammed Lahlou · +212 6 61 00 00 00'}),
    ('acceptation', 'deux', {
        'accepte_par_nom': 'Karim Alaoui',
        'date_acceptation': '05/10/2026'}),
    ('clauses_cgv', 'deux', {'clauses_cgv': CLAUSES_CGV}),
    ('note_client', 'deux', {'note_client': NOTE_CLIENT}),
    ('onepage_note_clauses', 'deux', {
        'pdf_mode': 'onepage', 'note_client': NOTE_CLIENT_LONGUE,
        'clauses_cgv': CLAUSES_CGV}),
)


# ── masques + empreinte ─────────────────────────────────────────────────────

_RE_POLICE = re.compile(r'(data:font/woff2;base64,)[A-Za-z0-9+/=]+')
#: ``page2`` — les deux graphes du cadre 680×170 (ROI cumulé, mensuel).
_RE_GRAPHE_ROI_MENSUEL = re.compile(
    r'(<img src="data:image/png;base64,)[A-Za-z0-9+/=]+'
    r'(" style="width:680px;height:170px;display:block;">)')
#: ``page_etude`` — le graphe production / consommation (cadre 680×200).
_RE_GRAPHE_ETUDE = re.compile(
    r'<img src="data:image/png;base64,([A-Za-z0-9+/=]+)'
    r'(" style="width:680px;height:200px;object-fit:contain;'
    r'display:block;">)')
_RE_SEGMENT = re.compile(r'(?=<div class="page")')


def _pixels(b64):
    """Empreinte du PNG DÉCODÉ : mode, taille et tableau de pixels."""
    from PIL import Image

    image = Image.open(io.BytesIO(base64.b64decode(b64)))
    image.load()
    empreinte = hashlib.sha256(
        f'{image.mode}|{image.size[0]}x{image.size[1]}|'.encode('ascii')
        + image.tobytes()).hexdigest()
    return {'sha256_pixels': empreinte, 'mode': image.mode,
            'taille': [image.size[0], image.size[1]]}


def empreinte(html):
    """Masque le non-déterministe immobile, hache le reste."""
    graphes_etude = []

    def _etude(trouve):
        pix = _pixels(trouve.group(1))
        graphes_etude.append(pix)
        return (f'<img src="png-etude:{pix["sha256_pixels"]}:'
                f'{pix["mode"]}:{pix["taille"][0]}x{pix["taille"][1]}'
                f'{trouve.group(2)}')

    html, polices = _RE_POLICE.subn(r'\1<police>', html)
    html, graphes = _RE_GRAPHE_ROI_MENSUEL.subn(r'\1<graphe>\2', html)
    html = _RE_GRAPHE_ETUDE.sub(_etude, html)

    def _sha(texte):
        return hashlib.sha256(texte.encode('utf-8')).hexdigest()

    return {
        'sha256': _sha(html),
        'octets': len(html.encode('utf-8')),
        'pages': html.count('<div class="page"'),
        'sha256_par_segment': [_sha(s) for s in _RE_SEGMENT.split(html)],
        'polices_masquees': polices,
        'graphes_roi_mensuel_masques': graphes,
        'graphes_etude': graphes_etude,
    }


def rendre_sequence():
    """Rend ``CAS`` dans l'ordre, depuis l'état « processus neuf », sous
    ``_RENDER_LOCK``. ``{nom: empreinte}`` ; un cas qui lève est noté
    ``{'exception': …}`` (la séquence continue : l'état fuit pareil)."""
    resultats = {}
    with moteur._RENDER_LOCK, matplotlib.rc_context(rc=_RC_A_L_IMPORT):
        _restaurer(_ETAT_A_L_IMPORT)
        for nom, variante, surcharges in CAS:
            data = F.donnees_legacy(variante, **copy.deepcopy(surcharges))
            try:
                html = moteur.render_html_for(data)
            except Exception as exc:  # noqa: BLE001 — caractérisation
                resultats[nom] = {'exception': type(exc).__name__}
                continue
            resultats[nom] = empreinte(html)
    return resultats


@unittest.skipUnless(_WEASY, 'WeasyPrint absent : le une-page mesuré '
                             '(_mesure_onepage) ne peut pas être rendu')
@tag('pdf')
class MoteurGoldenLegacyTests(SimpleTestCase):

    def setUp(self):
        etat = _etat_donnees()
        self.addCleanup(_restaurer, etat)

    def test_render_html_for_identique_au_golden(self):
        resultats = rendre_sequence()
        self.assertEqual(len(resultats), len(CAS))
        leves = sorted(n for n, r in resultats.items() if 'exception' in r)
        self.assertEqual(leves, [], 'un cas du golden lève : %s' % {
            n: resultats[n] for n in leves})
        maj = os.environ.get('UPDATE_GOLDEN') == '1'
        if maj:
            DOSSIER.mkdir(parents=True, exist_ok=True)
            for ancien in DOSSIER.glob('*.json'):
                if ancien.stem not in resultats:
                    ancien.unlink()
        ecarts, manquants = {}, []
        for ordre, (nom, _variante, _surcharges) in enumerate(CAS):
            reel = dict(resultats[nom], cas=nom, ordre=ordre)
            fichier = DOSSIER / f'{nom}.json'
            if maj:
                fichier.write_text(
                    json.dumps(reel, indent=2, ensure_ascii=False,
                               sort_keys=True) + '\n', encoding='utf-8')
            if not fichier.is_file():
                manquants.append(nom)
                continue
            attendu = json.loads(fichier.read_text(encoding='utf-8'))
            if attendu != reel:
                segments = [
                    i for i, (a, b) in enumerate(zip(
                        attendu.get('sha256_par_segment', []),
                        reel['sha256_par_segment'])) if a != b]
                ecarts[nom] = {'segments_differents': segments}
        self.assertEqual(manquants, [],
                         'golden non capturé : lancer une fois '
                         'UPDATE_GOLDEN=1 (voir la docstring)')
        self.assertEqual(ecarts, {}, 'HTML de render_html_for changé '
                                     '(segment 0 = en-tête/CSS)')
        presents = sorted(p.stem for p in DOSSIER.glob('*.json'))
        self.assertEqual(presents, sorted(n for n, _v, _s in CAS),
                         'un json par cas, aucun orphelin')


class BankableConcordeTests(SimpleTestCase):
    """``_bankable_concorde_avec_la_page`` lit ``globals().get("ETUDE")`` :
    capturé AVANT tout déplacement (une lecture du mauvais module après
    SPL169 rendrait toujours True)."""

    #: P50 à 11 000 kWh contre une carte à 12 486 kWh : ~12 % d'écart, hors
    #: de la tolérance de 1 % (``bankable.TOLERANCE_PRODUCTION_PAGE``).
    BANK = {'pr': {'p50_kwh': 11000, 'p90_kwh': 10200}}

    def setUp(self):
        etat = _etat_donnees()
        self.addCleanup(_restaurer, etat)
        _restaurer(_ETAT_A_L_IMPORT)

    def test_a_avant_toute_ingestion_rien_a_contredire(self):
        self.assertNotIn('ETUDE', vars(moteur))
        self.assertIs(moteur._bankable_concorde_avec_la_page(self.BANK), True)

    def test_b_etude_contradictoire_posee_refuse(self):
        moteur.ETUDE = {'production_annuelle': 12486}
        self.assertIs(moteur._bankable_concorde_avec_la_page(self.BANK),
                      False)
