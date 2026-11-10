"""CAL224 — borne de durée SERVEUR pour planche/note/DXF, sur un layout de
RÉFÉRENCE.

POURQUOI CETTE BORNE, ET PAS UNE AUTRE
---------------------------------------
Le chunk `roof-tool` a déjà son garde de nommage (frontend,
`build-tools/roof_tool_chunk_naming.test.mjs`) et le module a désormais son
budget de bundle (`features/calepinage/budget.test.mjs`) — mais rien ne
bornait le temps de COMPOSITION serveur des trois sorties que l'atelier
télécharge (planche SVG, note de calcul PDF, export DXF, `views/sorties.py`
CAL174/CAL175/CAL176). Une régression de complexité (une boucle O(n²) glissée
dans `geometrie_de_planche`, par exemple) ne casserait aucun test fonctionnel
existant — ceux-ci vérifient la FORME du résultat, jamais sa durée.

CE QUI EST MESURÉ, ET COMMENT (LA BORNE N'EST PAS DEVINÉE)
------------------------------------------------------------
Chaque essai chronomètre la fonction de COMPOSITION pure (jamais le rendu
WeasyPrint lui-même — ARC11, `core.pdf.render_pdf` a ses propres essais et
son temps dépend d'une bibliothèque système absente de certains postes ; le
chronométrer ici ferait un test flaky qui mesure autre chose que CE module).
Mesuré en LOCAL le 20/09/2026 sur ``LAYOUT`` (moyenne de 20 exécutions,
``time.perf_counter``) :

    * ``svg_de_planche``      : ~33 ms
    * ``octets_dxf``          : ~175 ms
    * ``html_de_note_calcul`` : ~2 ms

Les bornes ci-dessous laissent une marge large (≥ 3×) pour l'écart machine/CI
— un dépassement signale donc une VRAIE régression de complexité, pas un
poste plus lent. Reléver la borne exige de re-mesurer et de documenter la
nouvelle valeur (même discipline que ``frontend/scripts/check_bundle_budget.mjs``),
jamais un chiffre élargi « pour respirer ».

ACON51 (C-ACON-063) — la MÊME composition bornée aussi à 2 000 modules (4 pans
× 500, plafond admis le 23/10) : mesure du 08/11/2026 (sonde
``docs/audits/sondes/ACON/C-ACON-063.py``, deux runs, pile locale) —
géométrie + SVG ≈ 10 ms, ``octets_dxf`` 320-380 ms ; bornes = 3 × la mesure
(3 × 10 ms ; 3 × 380 ms). Le layout de 2 modules garde ses bornes.

Run :
    python manage.py test apps.calepinage.tests.test_cal224_perf -v2
"""
import math
import copy
import json
import pathlib
import time

from django.test import SimpleTestCase

from apps.calepinage.services.export_dxf import octets_dxf
from apps.calepinage.services.note_calcul import (
    _construire_note_calcul,
    _html_de_note_calcul,
)
from apps.calepinage.services.planche import (
    geometrie_de_planche,
    svg_de_planche,
)

from .test_cal171_planche import LAYOUT

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
RESULTAT_ECHANTILLON = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))['exemple']

SITE = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle',
        'source': 'roof_point', 'pin': None, 'outline': None}

#: Bornes en secondes — MESURÉES (voir en-tête), avec une marge ≥ 3×.
BORNE_PLANCHE_S = 0.30
BORNE_DXF_S = 1.00
BORNE_NOTE_S = 0.15
#: ACON51 — bornes « 2 000 modules » (mesure 08/11/2026, voir en-tête).
BORNE_PLANCHE_2000_S = 0.03
BORNE_DXF_2000_S = 1.14

#: Nombre de répétitions pour amortir le bruit d'une seule mesure (la première
#: exécution paye l'import/JIT-like warmup de certains modules).
REPETITIONS = 5


def _layout_synthetique(pans, par_pan):
    """ACON51 — ``pans`` pans de ``par_pan`` cellules réelles (grille 25 colonnes,
    pas 1,15 × 2,30 m), côte à côte, géoréférencés autour de Bouskoura."""
    m_lat, m_lng = 111320.0, 111320.0 * math.cos(math.radians(33.5))

    def deg(x, y):
        return [-7.6 + x / m_lng, 33.5 + y / m_lat]
    zones, x0 = [], 0.0
    largeur, hauteur = 25 * 1.15 + 2.0, math.ceil(par_pan / 25) * 2.30 + 2.0
    for p in range(pans):
        zones.append({'id': f'z{p + 1}', 'label': f'Pan {p + 1}', 'vertices': [
            deg(x0, 0), deg(x0 + largeur, 0), deg(x0 + largeur, hauteur), deg(x0, hauteur)],
            'geometry': {'azimuthDeg': 180.0, 'tiltDeg': 10.0, 'count': par_pan, 'origin': deg(x0, 0),
                         'panels': [{'cx': 1.575 + (i % 25) * 1.15, 'cy': 2.15 + (i // 25) * 2.30}
                                    for i in range(par_pan)]}})
        x0 += largeur + 5.0
    contour = [deg(0, 0), deg(x0, 0), deg(x0, hauteur), deg(0, hauteur)]  # [lng, lat]
    return {'version': 2, 'panelWatt': 550, 'zones': zones, 'outline': [[lat, lng] for lng, lat in contour]}


LAYOUT_2000 = _layout_synthetique(4, 500)


def _resultat():
    return copy.deepcopy(RESULTAT_ECHANTILLON)


def _chronometre(fonction, repetitions=REPETITIONS):
    """Le temps MOYEN d'un appel, après un tour de chauffe ignoré."""
    fonction()  # chauffe — hors mesure, comme tout micro-banc honnête.
    debut = time.perf_counter()
    for _ in range(repetitions):
        fonction()
    return (time.perf_counter() - debut) / repetitions


class PerfPlancheTest(SimpleTestCase):
    """La composition SVG de la planche — jamais le rendu WeasyPrint."""

    def test_svg_de_planche_reste_sous_la_borne_mesuree(self):
        geometrie = geometrie_de_planche(LAYOUT)
        moyenne = _chronometre(
            lambda: svg_de_planche(geometrie, titre='Référence CAL224',
                                   pied='Calepinage CAL224'))
        self.assertLess(
            moyenne, BORNE_PLANCHE_S,
            f'svg_de_planche : {moyenne * 1000:.1f} ms (moyenne sur '
            f'{REPETITIONS}) > borne {BORNE_PLANCHE_S * 1000:.0f} ms '
            '(mesure de référence 2026-09-20 : ~33 ms).')

    def test_geometrie_de_planche_seule_reste_sous_la_borne(self):
        """La PROJECTION (repère local, ENU) est le poste le plus sensible à
        une régression O(n²) sur un layout à plusieurs pans/obstacles."""
        moyenne = _chronometre(lambda: geometrie_de_planche(LAYOUT))
        self.assertLess(moyenne, BORNE_PLANCHE_S)

    def test_composition_a_2000_modules_reste_sous_la_borne(self):
        """ACON51 — géométrie + SVG d'un 4 × 500 (une boucle O(n²) échoue ici, pas à 2)."""
        moyenne = _chronometre(lambda: svg_de_planche(
            geometrie_de_planche(LAYOUT_2000), titre='ACON51', pied='ACON51'))
        self.assertLess(moyenne, BORNE_PLANCHE_2000_S,
                        f'planche 2 000 modules : {moyenne * 1000:.1f} ms (mesure 08/11/2026 : ~10 ms).')


class PerfDxfTest(SimpleTestCase):
    def test_octets_dxf_reste_sous_la_borne_mesuree(self):
        geometrie = geometrie_de_planche(LAYOUT)
        moyenne = _chronometre(lambda: octets_dxf(geometrie))
        self.assertLess(
            moyenne, BORNE_DXF_S,
            f'octets_dxf : {moyenne * 1000:.1f} ms (moyenne sur '
            f'{REPETITIONS}) > borne {BORNE_DXF_S * 1000:.0f} ms '
            '(mesure de référence 2026-09-20 : ~175 ms).')

    def test_octets_dxf_a_2000_modules_reste_sous_la_borne(self):
        geometrie = geometrie_de_planche(LAYOUT_2000)
        moyenne = _chronometre(lambda: octets_dxf(geometrie))
        self.assertLess(moyenne, BORNE_DXF_2000_S,
                        f'DXF 2 000 modules : {moyenne * 1000:.1f} ms (mesure 08/11/2026 : 320-380 ms).')


class PerfNoteCalculTest(SimpleTestCase):
    """La composition HTML — jamais le rendu PDF (``core.pdf.render_pdf``,
    ARC11, ses propres essais couvrent sa durée)."""

    def test_note_calcul_reste_sous_la_borne_mesuree(self):
        def composer():
            note = _construire_note_calcul(_resultat(), site=SITE)
            return _html_de_note_calcul(note)

        moyenne = _chronometre(composer)
        self.assertLess(
            moyenne, BORNE_NOTE_S,
            f'note de calcul : {moyenne * 1000:.1f} ms (moyenne sur '
            f'{REPETITIONS}) > borne {BORNE_NOTE_S * 1000:.0f} ms '
            '(mesure de référence 2026-09-20 : ~2 ms).')
