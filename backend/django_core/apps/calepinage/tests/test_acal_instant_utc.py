"""ACAL131 — un seul lecteur d'instant UTC par point, Ramadan compris.

Constat C-ACAL-066 : sur un site marocain (fuseau Africa/Casablanca), la
ré-indexation publie ``meteo.heure.decalage_minutes = [0, 60]`` dès que la
fenêtre couvre le Ramadan (UTC+0 pendant, UTC+1 hors Ramadan jusqu'au
décret de septembre 2026). L'IAM et l'horizon n'acceptaient qu'UNE valeur
(étape omise : « base de temps non déclarée ») et l'inter-rangées n'acceptait
que la base « locale_standard » (omise après ré-indexation).

Désormais la ré-indexation pose SUR CHAQUE POINT son décalage UTC légal
(``etapes.CLE_DECALAGE_POINT``) et ``etapes.instant_utc`` est LE lecteur des
trois étapes — jamais un décalage moyen.

Base IANA réelle (tzdata épinglé), chaîne réelle, aucun mock. Le golden est
régénéré UNIQUEMENT à la main :

    python -m apps.calepinage.tests.test_acal_instant_utc --write

Run :
    python manage.py test apps.calepinage.tests.test_acal_instant_utc -v2
"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys

if __name__ == '__main__':  # pragma: no cover — chemin « --write » seulement
    import os

    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'erp_agentique.settings.dev')
    import django

    django.setup()

from django.test import SimpleTestCase  # noqa: E402

from apps.calepinage.services import etapes  # noqa: E402
from apps.calepinage.services.chaine_pertes import (  # noqa: E402
    appliquer_chaine,
)
from apps.calepinage.services.etapes import inter_rangees  # noqa: E402

GOLDEN = (pathlib.Path(__file__).resolve().parent / 'golden_simulation'
          / 'casablanca_ramadan.json')

#: Deux jours de 2024 : le 25 mars (Ramadan, UTC+0) et le 20 juin (UTC+1).
JOURS = ((2024, 3, 25), (2024, 6, 20))


def _serie(jours=JOURS):
    """Heures en base LOCALE STANDARD (PVGIS ``localtime=1``), composantes
    comprises — l'IAM et l'inter-rangées en ont besoin."""
    points = []
    for annee, mois, jour in jours:
        for heure in range(7, 20):
            globale = max(0.0, 900.0 - abs(heure - 13) * 140.0)
            points.append({
                'annee': annee, 'mois': mois, 'jour': jour, 'heure': heure,
                'p_w': 8.0 * globale, 'gi_w_m2': globale,
                'gb_i_w_m2': globale * 0.75, 'gd_i_w_m2': globale * 0.2,
                'gr_i_w_m2': globale * 0.05,
            })
    return {'pas_minutes': 60, 'colonne_energie': 'p_w', 'points': points}


def _contexte(fuseau='Africa/Casablanca'):
    plan = {'cle': 'A', 'pan': 'PAN-A', 'modules': 12, 'kwc': 8.0,
            'inclinaison_deg': 30.0, 'azimut_pvgis_deg': 0.0,
            'geometry': {'tiltDeg': 30.0, 'panelSlopeLenM': 2.3,
                         'rowPitchM': 3.2, 'rowCount': 3,
                         'kwc': 8.0, 'family': 'bacs_lestes'}}
    return {
        'site': {'lat': 33.5731, 'lon': -7.5898, 'fuseau': fuseau},
        'meteo': {'heure': {'base': 'locale_standard', 'fuseau_site': None,
                            'decalage_minutes': []}},
        'plan': plan,
        'plans': [plan],
        'hash_entree': 'acal131',
    }


def _etape(cascade, nom):
    return next(e for e in cascade['etapes'] if e['etape'] == nom)


class InstantUtcTest(SimpleTestCase):

    def test_iam_appliquee_casablanca_avec_ramadan(self):
        contexte = _contexte()
        _sortie, cascade = appliquer_chaine(_serie(), contexte)

        self.assertEqual(contexte['meteo']['heure']['decalage_minutes'],
                         [0, 60])
        iam = _etape(cascade, 'iam')
        self.assertEqual(iam['motif_omission'], '')
        self.assertGreater(iam['perte_pct'], 0.0)
        self.assertEqual(iam['entree']['decalage_minutes'], [0.0, 60.0])

    def test_instant_utc_par_periode(self):
        contexte = _contexte()
        sortie, _cascade = appliquer_chaine(_serie(), contexte)
        meteo = contexte['meteo']
        par_jour = {}
        for point in sortie['points']:
            if point['heure'] != 13:
                continue
            par_jour[(point['mois'], point['jour'])] = (
                point[etapes.CLE_DECALAGE_POINT],
                etapes.instant_utc(point, meteo))
        ramadan = par_jour[(3, 25)]
        ete = par_jour[(6, 20)]
        # 13 h légales : 13 h UTC pendant le Ramadan, 12 h UTC hors Ramadan.
        self.assertEqual(ramadan[0], 0)
        self.assertEqual(ramadan[1], datetime.datetime(
            2024, 3, 25, 13, tzinfo=datetime.timezone.utc))
        self.assertEqual(ete[0], 60)
        self.assertEqual(ete[1], datetime.datetime(
            2024, 6, 20, 12, tzinfo=datetime.timezone.utc))
        # Jamais un décalage moyen : (0 + 60) / 2 = 30 n'apparaît nulle part.
        decalages = {point[etapes.CLE_DECALAGE_POINT]
                     for point in sortie['points']}
        self.assertEqual(decalages, {0, 60})

    def test_horizon_et_inter_rangees_meme_lecteur(self):
        contexte = _contexte()
        contexte['horizon'] = {
            'source': 'saisie',
            'points': [{'azimut_face_deg': azimut, 'hauteur_deg': 12.0}
                       for azimut in range(0, 360, 30)]}
        _sortie, cascade = appliquer_chaine(_serie(), contexte)

        # Les trois étapes LISENT la même base de temps : aucune ne s'omet
        # faute de décalage unique.
        for nom in ('iam', 'horizon', 'inter_rangees'):
            etape = _etape(cascade, nom)
            self.assertNotIn('decalage_minutes', etape['motif_omission'],
                             nom)
            self.assertNotIn('meteo.heure.base', etape['motif_omission'],
                             nom)
        self.assertEqual(_etape(cascade, 'inter_rangees')['motif_omission'],
                         '')
        # Le lecteur est bien celui d'``etapes`` (plus de copie locale).
        for module in ('iam', 'horizon'):
            source = (pathlib.Path(etapes.__file__).parent
                      / f'{module}.py').read_text(encoding='utf-8')
            self.assertNotIn('def _instant_utc', source)
            self.assertNotIn('def _decalage_minutes', source)
        self.assertFalse(hasattr(inter_rangees, '_decalages'))

    def test_un_fuseau_a_decalage_fixe_reste_inchange(self):
        # « Etc/GMT-1 » (UTC+1 toute l'année) : un seul décalage, comme avant.
        contexte = _contexte('Etc/GMT-1')
        _sortie, cascade = appliquer_chaine(_serie(), contexte)
        self.assertEqual(contexte['meteo']['heure']['decalage_minutes'],
                         [60])
        iam = _etape(cascade, 'iam')
        self.assertEqual(iam['motif_omission'], '')
        self.assertEqual(iam['entree']['decalage_minutes'], 60.0)


def _resume():
    contexte = _contexte()
    _sortie, cascade = appliquer_chaine(_serie(), contexte)
    return {
        'decalage_minutes': contexte['meteo']['heure']['decalage_minutes'],
        'etapes': [{'etape': etape['etape'],
                    'omise': bool(etape['motif_omission']),
                    'kwh_avant': etape['kwh_avant'],
                    'kwh_apres': etape['kwh_apres'],
                    'perte_pct': etape['perte_pct']}
                   for etape in cascade['etapes']
                   if etape['etape'] in ('horizon', 'inter_rangees', 'iam')],
        'total_pct': cascade['total_pct'],
    }


class GoldenRamadanTest(SimpleTestCase):

    def test_le_golden_est_reproduit(self):
        attendu = json.loads(GOLDEN.read_text(encoding='utf-8'))['attendu']
        self.assertEqual(json.loads(json.dumps(_resume())), attendu)


def ecrire_le_golden():  # pragma: no cover — chemin « --write » seulement
    document = {
        '_provenance': {
            'tache': 'ACAL131',
            'produit_par': ('python -m apps.calepinage.tests.'
                            'test_acal_instant_utc --write'),
            'cas': ('Casablanca (33,5731 / −7,5898), fuseau '
                    'Africa/Casablanca, base locale standard ; deux jours de '
                    '2024 : 25 mars (Ramadan, UTC+0) et 20 juin (UTC+1) ; '
                    'pan 30° plein sud, 3 rangées au pas de 3,2 m.'),
            'comment_regenerer': (
                'Relancer la commande À LA MAIN, lire le diff, dire dans le '
                'message de commit POURQUOI la cascade a bougé.'),
        },
        'attendu': _resume(),
    }
    GOLDEN.write_text(json.dumps(document, ensure_ascii=False, indent=1)
                      + '\n', encoding='utf-8')
    return GOLDEN


if __name__ == '__main__':  # pragma: no cover — chemin « --write » seulement
    if '--write' not in sys.argv[1:]:
        raise SystemExit('--write est obligatoire : écrire écrase le golden.')
    print(ecrire_le_golden())
