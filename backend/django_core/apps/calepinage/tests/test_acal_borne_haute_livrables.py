"""ACAL50 — les livrables impriment la « borne haute » d'un résultat incomplet
(D-ACAL-7, constat C-ACAL-076).

La simulation publie depuis ACAL49 ``production.total.complete``, ``mention``
(« borne haute — N pertes non renseignées ») et PR / P75 / P90 / P95 à
``null`` avec leur motif. Le rapport d'étude (section Production), la
présentation compacte et la note de calcul LISENT ces clés : la mention mot
pour mot sous le P50, « non publié — <motif> » à la place du PR, du P75, du
P90 et du P95 — jamais 100 %, jamais 0. Un résultat complet imprime PR et P90
comme avant.

Les résultats viennent de la VRAIE chaîne (``simuler_calepinage``, client
rejoué CALX5) : le bloc ``production`` simulé remplace celui de l'échantillon
du contrat, qui ne fournit que le reste de la forme servie (pose,
électrique). Aucune complétude n'est écrite à la main.

Run :
    python manage.py test apps.calepinage.tests.test_acal_borne_haute_livrables -v2
"""
from __future__ import annotations

import copy
import json
import pathlib
import re
from html import escape
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.calepinage.services.documents.presentation_compacte import (
    _construire_presentation, _html_de_presentation,
)
from apps.calepinage.services.note_calcul import (
    _construire_note_calcul, _html_de_note_calcul,
)
from apps.calepinage.services.rapport import nombre_tel_que_servi
from apps.calepinage.services.rapport.production import html_de_section

from .test_acal_completude_simulation import SOCLE_SAISI, _simuler
from .test_cal171_planche import LAYOUT

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLON = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))

NU = SimpleNamespace(company=None, pk=None, titre='Villa Anfa',
                     roof_layout=LAYOUT, resultat=None, layout_hash='',
                     version_moteur='')
STYLES = {'nom_affiche': 'Soleil Atlas', 'logo_url': '',
          'couleur_primaire': '', 'couleur_secondaire': ''}
SITE = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle',
        'source': 'roof_point', 'pin': None, 'outline': None}

_CACHE = {}


def _servi(*, complet):
    """La forme servie, dont ``production`` et ``incertitude`` sortent de la
    simulation RÉELLE (socle saisi ou non)."""
    if complet not in _CACHE:
        blocs = _simuler(pertes=SOCLE_SAISI) if complet else _simuler()
        _CACHE[complet] = blocs
    blocs = copy.deepcopy(_CACHE[complet])
    resultat = copy.deepcopy(ECHANTILLON['exemple'])
    production = blocs['production']
    # La note exige la source de l'irradiance : celle du contrat quand la
    # simulation ne la nomme pas.
    base = dict((resultat.get('production') or {}).get('base') or {})
    base.update(production.get('base') or {})
    production['base'] = base
    resultat['production'] = production
    resultat['incertitude'] = blocs.get('incertitude') or {}
    return resultat


def _rapport(resultat):
    return html_de_section({'resultat': resultat, 'langue': 'fr',
                            'section': {'code': 'production',
                                        'motif_si_absent': ''}})


def _ligne(html, libelle):
    trouve = re.search(r'<tr><th>%s</th>.*?</tr>' % re.escape(libelle), html)
    assert trouve, libelle
    return trouve.group(0)


def _non_publie(total, cle):
    return 'non publié — %s' % total['%s_motif' % cle]


class BorneHauteLivrablesTest(SimpleTestCase):

    def test_rapport_imprime_la_mention_et_masque_le_pr(self):
        resultat = _servi(complet=False)
        total = resultat['production']['total']
        self.assertFalse(total['complete'])
        self.assertTrue(total['mention'].startswith('borne haute — '))
        html = _rapport(resultat)

        # La mention MOT POUR MOT sous le P50 (totaux ET quantiles).
        for libelle in ('Production annuelle P50 (kWh)', 'P50 (kWh)'):
            ligne = _ligne(html, libelle)
            self.assertIn(nombre_tel_que_servi(total['p50_kwh']), ligne)
            self.assertIn(escape(total['mention']), ligne)
        pr = _ligne(html, 'Ratio de performance (PR)')
        self.assertIn(escape(_non_publie(total, 'performance_ratio')), pr)
        self.assertNotIn('<td>1', pr)
        self.assertNotIn('<td>0', pr)

    def test_rapport_complet_imprime_pr_et_p90_comme_avant(self):
        resultat = _servi(complet=True)
        total = resultat['production']['total']
        self.assertTrue(total['complete'])
        html = _rapport(resultat)
        self.assertIn(nombre_tel_que_servi(total['performance_ratio']),
                      _ligne(html, 'Ratio de performance (PR)'))
        self.assertIn(nombre_tel_que_servi(total['p90_kwh']),
                      _ligne(html, 'P90 (kWh)'))
        self.assertNotIn('non publié', html)
        self.assertNotIn('mention-borne-haute', html)

    def test_presentation_compacte_sans_pr_100(self):
        resultat = _servi(complet=False)
        total = resultat['production']['total']
        html = _html_de_presentation(_construire_presentation(
            NU, resultat=resultat, roof_layout=LAYOUT, svg_planche='',
            styles=STYLES))
        self.assertIn(escape(total['mention']), html)
        pr = re.search(r'Ratio de performance \(PR\) : [^<]*', html).group(0)
        self.assertEqual(
            pr, 'Ratio de performance (PR) : %s'
            % escape(_non_publie(total, 'performance_ratio')))

        complet = _servi(complet=True)
        html_complet = _html_de_presentation(_construire_presentation(
            NU, resultat=complet, roof_layout=LAYOUT, svg_planche='',
            styles=STYLES))
        self.assertIn('Ratio de performance (PR) : %s' % nombre_tel_que_servi(
            complet['production']['total']['performance_ratio']),
            html_complet)
        self.assertNotIn('non publié', html_complet)

    def test_note_de_calcul_p90_non_publie(self):
        resultat = _servi(complet=False)
        total = resultat['production']['total']
        html = _html_de_note_calcul(_construire_note_calcul(resultat, site=SITE))
        self.assertIn('<th>Production annuelle P90</th><td>%s</td>'
                      % escape(_non_publie(total, 'p90_kwh')), html)
        self.assertIn('<th>Ratio de performance</th><td>%s</td>'
                      % escape(_non_publie(total, 'performance_ratio')), html)
        # La mention sous le P50, mot pour mot.
        p50 = html.index('<th>Production annuelle P50</th>')
        self.assertIn(escape(total['mention']), html[p50:p50 + 600])

        complet = _servi(complet=True)
        html_complet = _html_de_note_calcul(
            _construire_note_calcul(complet, site=SITE))
        self.assertNotIn('non publié', html_complet)
        self.assertNotIn('<th>Production annuelle P90</th><td>—</td>',
                         html_complet)

    def test_p75_p95_non_publies(self):
        resultat = _servi(complet=False)
        total = resultat['production']['total']
        rapport = _rapport(resultat)
        note = _html_de_note_calcul(_construire_note_calcul(resultat, site=SITE))
        for cle, libelle_rapport, libelle_note in (
                ('p75_kwh', 'P75 (kWh)', 'Production annuelle P75'),
                ('p90_kwh', 'P90 (kWh)', 'Production annuelle P90'),
                ('p95_kwh', 'P95 (kWh)', 'Production annuelle P95')):
            texte = escape(_non_publie(total, cle))
            self.assertIn(texte, _ligne(rapport, libelle_rapport), cle)
            self.assertIn('<th>%s</th><td>%s</td>' % (libelle_note, texte),
                          note, cle)
