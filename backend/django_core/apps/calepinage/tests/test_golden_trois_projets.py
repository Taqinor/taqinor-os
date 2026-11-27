"""ACAL382 — le GOLDEN de ``simuler_calepinage`` sur TROIS projets de référence.

Trois projets à Casablanca, bâtis sur les réponses PVGIS-SARAH3 2020
ENREGISTRÉES (``fixtures_pvgis/seriescalc_casablanca_annee_2020_*.json``,
année pleine, aucun appel réseau) :

* ``residentiel_pan_sud_15`` — un pan incliné 15° plein sud, 12 modules ;
* ``ci_toit_plat_est_ouest_chassis`` — un pan est-ouest posé sur châssis,
  20 modules, UN onduleur ;
* ``champ_sol_sud`` — une surface de pose au sol (``poseSurfaces``).

La météo passe par le VRAI client PVGIS (``ClientPvgis``), dont seul le
transport est remplacé par un rejeu de la fixture de l'orientation demandée.
Matériel et réglages sont ceux de TEST de ``test_calx5_simulation`` ; les
postes saisis sont sourcés « réglages de TEST, aucune valeur produit ».

Le texte des ``motif_omission`` n'est pas comparé (règle de CALX196) : l'état
omise/appliquée et tous les kWh le sont. Un écart échoue en nommant le projet,
l'étape et les DEUX valeurs. Le golden ne se réécrit qu'à la main :

    python -m apps.calepinage.tests.test_golden_trois_projets --write

Run :
    python manage.py test apps.calepinage.tests.test_golden_trois_projets -v2
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys
import urllib.parse

if __name__ == '__main__':  # pragma: no cover — chemin « --write » seulement
    import os

    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'erp_agentique.settings.dev')
    import django

    django.setup()

from django.test import SimpleTestCase

from apps.calepinage.services.pvgis_serie import ClientPvgis, _Cache
from apps.calepinage.services.simulation import simuler_calepinage
from apps.calepinage.tests.test_acal_multi_pans import _resume
from apps.calepinage.tests.test_calx5_simulation import (
    MATERIEL, REGLAGES, _Calepinage,
)

RACINE = pathlib.Path(__file__).resolve().parent
FIXTURES = RACINE / 'fixtures_pvgis'
GOLDEN = RACINE / 'golden_simulation' / 'trois_projets_reference.json'

REFERENCE_CAS = ('Cas figé ACAL382 — réglages de TEST, aucune valeur '
                 'produit')
DELTA_KWH = 0.01
DELTA_RATIO = 1e-4

POSTES = [
    {'poste': nom, 'pct': pct, 'source': 'societe',
     'reference': REFERENCE_CAS}
    for nom, pct in (('salissure', 2.0), ('mismatch', 2.0),
                     ('onduleur', 3.0), ('indisponibilite', 3.0))
]

#: La fixture ANNÉE PLEINE 2020 (8 784 h, réponse brute de PVGIS-SARAH3) à
#: rejouer selon (inclinaison, aspect PVGIS : 0 sud, −90 est, +90 ouest).
FIXTURE_PAR_PLAN = {
    (15.0, 0.0): 'seriescalc_casablanca_annee_2020_sud_15.json',
    (10.0, -90.0): 'seriescalc_casablanca_annee_2020_est_10.json',
    (10.0, 90.0): 'seriescalc_casablanca_annee_2020_ouest_10.json',
    (20.0, 0.0): 'seriescalc_casablanca_annee_2020_sud_20.json',
}


#: Le plan horizontal (ACAL706) n'a AUCUNE réponse enregistrée : on ne
#: l'invente pas, le transport rejoué le refuse comme PVGIS le ferait et la
#: simulation publie un gain d'inclinaison « non calculé » avec son motif.
PLAN_SANS_ENREGISTREMENT = (0.0, 0.0)


def _transport(url, timeout_s):
    requete = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    plan = (float(requete['angle'][0]), float(requete['aspect'][0]))
    if plan == PLAN_SANS_ENREGISTREMENT:
        return 404, ''
    return 200, (FIXTURES / FIXTURE_PAR_PLAN[plan]).read_text(
        encoding='utf-8')


def _reglages():
    reglages = copy.deepcopy(REGLAGES)
    reglages['simulation']['fenetre_annees'] = {
        'valeur': [2020, 2020], 'source': 'note interne',
        'reference': 'base PVGIS enregistrée (2020)'}
    return reglages


class _ClientEnregistre:
    """Le vrai client PVGIS sur transport rejoué ; rien d'autre n'est exposé
    (l'écart PVcalc est donc publié sans mesure, comme dans ACAL53)."""

    def __init__(self):
        self._client = ClientPvgis(_transport, cache=_Cache(),
                                   dormir=lambda _s: None)

    def serie_irradiance(self, **parametres):
        return self._client.serie_irradiance(**parametres)


LAYOUT_PIN = {'lat': 33.5731, 'lng': -7.5898}

PROJETS = {
    'residentiel_pan_sud_15': {
        'version': 2, 'pin': LAYOUT_PIN,
        'zones': [{'id': 'z1', 'label': 'PAN-SUD',
                   'geometry': {'count': 12, 'azimuthDeg': 180.0,
                                'tiltDeg': 15.0,
                                'family': 'surimposition'}}]},
    'ci_toit_plat_est_ouest_chassis': {
        'version': 2, 'pin': LAYOUT_PIN,
        'zones': [{'id': 'z1', 'label': 'TOIT-PLAT', 'pitchDeg': 10.0,
                   'facingAzimuthDeg': 90.0,
                   'geometry': {'count': 20, 'azimuthDeg': 90.0,
                                'tiltDeg': 10.0, 'family': 'eastwest'}}]},
    'champ_sol_sud': {
        'version': 2, 'pin': LAYOUT_PIN, 'zones': [],
        'poseSurfaces': [{'id': 'champ-1', 'kind': 'sol',
                          'label': 'CHAMP-SOL', 'moduleWc': 710,
                          'tiltDeg': 20.0, 'rowAzimuthDeg': 90.0,
                          'engine': {'modules': 24}}]},
}


def simuler_projet(nom, pertes=None, layout=None, watt=None):  # ACAL982
    calepinage = _Calepinage(
        layout=copy.deepcopy(PROJETS[nom] if layout is None else layout),
        pertes=pertes if pertes is not None else POSTES)
    materiel = copy.deepcopy(MATERIEL)
    materiel['onduleur']['ac_kw'] = 30.0
    if watt is not None:
        materiel['module']['pmax_wc'] = float(watt)
    rendu = simuler_calepinage(
        calepinage, client=_ClientEnregistre(), materiel=materiel,
        reglages=_reglages(), enregistrer=False)
    return json.loads(json.dumps(_resume(rendu['blocs'])))


def _refus_nomme(nom):
    """Si la chaîne REFUSE le projet, le golden gèle ce refus NOMMÉ."""
    try:
        return simuler_projet(nom)
    except Exception as erreur:  # noqa: BLE001 — le refus EST la valeur
        return {'refus': type(erreur).__name__,
                'etape': str(getattr(erreur, 'etape', '')
                             or getattr(erreur, 'champ', '') or '')}


def calculer():
    return {nom: _refus_nomme(nom) for nom in PROJETS}


# ── la comparaison, qui NOMME projet, étape et les deux valeurs ─────────

def _feuilles(valeur, chemin=''):
    if isinstance(valeur, dict):
        for cle, sous in valeur.items():
            yield from _feuilles(sous, f'{chemin}.{cle}' if chemin else cle)
    elif isinstance(valeur, list):
        for rang, sous in enumerate(valeur):
            etiquette = (sous.get('etape') or sous.get('pan')
                         if isinstance(sous, dict) else None)
            yield from _feuilles(sous, f'{chemin}[{etiquette or rang}]')
    else:
        yield chemin, valeur


def ecarts(projet, attendu, obtenu):
    gauche, droite = dict(_feuilles(attendu)), dict(_feuilles(obtenu))
    messages = []
    for chemin in sorted(set(gauche) | set(droite)):
        a, b = gauche.get(chemin, '<absent>'), droite.get(chemin, '<absent>')
        nombres = all(isinstance(v, (int, float)) and not isinstance(v, bool)
                      for v in (a, b))
        delta = DELTA_RATIO if 'performance_ratio' in chemin else DELTA_KWH
        if (nombres and abs(a - b) <= delta) or a == b:
            continue
        messages.append(
            f'Projet « {projet} » — {chemin} : attendu {a!r}, obtenu {b!r}.')
    return messages


class GoldenTroisProjetsTest(SimpleTestCase):

    def test_les_trois_projets_rejouent_leur_golden(self):
        if not GOLDEN.exists():
            self.fail('golden à générer : python -m apps.calepinage.tests.'
                      'test_golden_trois_projets --write')
        attendu = json.loads(GOLDEN.read_text(encoding='utf-8'))['attendu']
        self.assertEqual(sorted(attendu), sorted(PROJETS))
        messages = []
        for nom, obtenu in calculer().items():
            messages += ecarts(nom, attendu[nom], obtenu)
        self.assertEqual(messages, [], '\n'.join(messages))

    def test_un_ecart_de_salissure_est_nomme(self):
        attendu = json.loads(GOLDEN.read_text(encoding='utf-8'))['attendu']
        nom = 'residentiel_pan_sud_15'
        pertes = [dict(poste, pct=3.0) if poste['poste'] == 'salissure'
                  else poste for poste in POSTES]
        messages = ecarts(nom, attendu[nom],
                          simuler_projet(nom, pertes=pertes))
        self.assertTrue(any(nom in m and 'salissure' in m
                            for m in messages), messages)


EXEMPLES = (pathlib.Path(__file__).resolve().parent.parent / 'exemples')
NOMS_EXEMPLES = ('residentiel_pan_sud_15', 'ci_toit_plat_est_ouest_chassis',
                 'champ_sol_sud')


class ExemplesDeBibliothequeTest(SimpleTestCase):
    """ACAL895 — les trois documents d'exemple sont de VRAIS documents
    dessinables (contour + pans), jamais le dictionnaire ``PROJETS``."""

    def _document(self, nom):
        return json.loads(
            (EXEMPLES / f'{nom}.json').read_text(encoding='utf-8'))

    def test_valides_au_schema_et_decrivent_une_geometrie(self):
        from apps.calepinage.services.io_layout import valider_document
        from apps.calepinage.services.layout import (
            layout_decrit_une_geometrie)

        for nom in NOMS_EXEMPLES:
            with self.subTest(exemple=nom):
                document = self._document(nom)
                valider_document(document)
                self.assertTrue(layout_decrit_une_geometrie(document))

    def test_ne_sont_pas_les_documents_sans_contour_du_golden(self):
        for nom in NOMS_EXEMPLES:
            with self.subTest(exemple=nom):
                self.assertNotEqual(self._document(nom), PROJETS[nom])
                self.assertGreaterEqual(len(self._document(nom)['outline']), 3)

    def test_se_simulent(self):
        for nom in NOMS_EXEMPLES:
            with self.subTest(exemple=nom):
                calepinage = _Calepinage(
                    layout=self._document(nom), pertes=POSTES)
                materiel = copy.deepcopy(MATERIEL)
                materiel['onduleur']['ac_kw'] = 30.0
                rendu = simuler_calepinage(
                    calepinage, client=_ClientEnregistre(),
                    materiel=materiel, reglages=_reglages(),
                    enregistrer=False)
                self.assertTrue(rendu['blocs'])


def ecrire_le_golden():  # pragma: no cover — chemin « --write » seulement
    document = {
        '_provenance': {
            'tache': 'ACAL382',
            'produit_par': ('python -m apps.calepinage.tests.'
                            'test_golden_trois_projets --write'),
            'cas': ('Casablanca, PVGIS-SARAH3 ANNÉE PLEINE 2020 enregistrée '
                    '(sud 15° / est 10° / ouest 10° / sud 20°) ; postes '
                    'salissure 2 / mismatch 2 / onduleur 3 / '
                    'indisponibilité 3 % de TEST ; onduleur 30 kW.'),
            'comment_regenerer': (
                'Relancer la commande À LA MAIN, lire le diff, dire dans le '
                'message de commit POURQUOI les chiffres ont bougé.'),
        },
        'attendu': calculer(),
    }
    GOLDEN.write_text(json.dumps(document, ensure_ascii=False, indent=1)
                      + '\n', encoding='utf-8')
    return GOLDEN


if __name__ == '__main__':  # pragma: no cover — chemin « --write » seulement
    if '--write' not in sys.argv[1:]:
        raise SystemExit('--write est obligatoire : écrire écrase le golden.')
    print(ecrire_le_golden())
