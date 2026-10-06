"""ACAL53 — plusieurs pans : météo AVANT les chaînes, phase ONDULEUR sur la
SOMME, cascade et PR de la somme.

Constats C-ACAL-077 / C-ACAL-078. Avant : ``contexte['meteo']`` n'était posé
qu'APRÈS la boucle des pans — chaque chaîne de pan tournait sans
``meteo.heure`` (IAM, horizon, inter-rangées, accès module omis en silence) ;
chaque pan passait SEUL dans l'onduleur de tout le site (écrêtage, η(P) et
fenêtre MPPT jugés sur la puissance d'un pan) ; la cascade publiée était
celle du pan le plus puissant et le PR celui de sa série au kWc total.

Désormais (``services/simulation.py::_chaine_par_phases``) : phase PAN pan
par pan, phase ONDULEUR sur la somme DC des pans rattachés, phase SITE ;
cascade, PR et écart PVcalc décrivent la SOMME. Un toit à UN pan est
strictement inchangé.

Chaîne RÉELLE (``simuler_calepinage``), météo REJOUÉE par un client double
qui répond une série DISTINCTE par orientation demandée — aucun mock de la
chaîne. Le golden est régénéré UNIQUEMENT à la main :

    python -m apps.calepinage.tests.test_acal_multi_pans --write

Run :
    python manage.py test apps.calepinage.tests.test_acal_multi_pans -v2
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys
from unittest import mock

if __name__ == '__main__':  # pragma: no cover — chemin « --write » seulement
    import os

    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'erp_agentique.settings.dev')
    import django

    django.setup()

from django.test import SimpleTestCase  # noqa: E402

from apps.calepinage.services import chaine_pertes, simulation  # noqa: E402
from apps.calepinage.services.chaine_pertes import (  # noqa: E402
    ChaineInvalide, ETAPES_PAN, appliquer_chaine,
)
from apps.calepinage.services.simulation import (  # noqa: E402
    MOTIF_ECRETAGE_SANS_AFFECTATION, simuler_calepinage,
)
from apps.calepinage.services.validation import ecart_vs_pvcalc  # noqa: E402
from apps.calepinage.tests.test_calx5_simulation import (  # noqa: E402
    MATERIEL, REGLAGES, _Calepinage, _reponse_meteo,
)

GOLDEN = (pathlib.Path(__file__).resolve().parent / 'golden_simulation'
          / 'multi_pans_est_ouest_un_onduleur.json')

REFERENCE_CAS = 'Cas figé ACAL53 — réglages de TEST, aucune valeur produit'

#: Des postes SAISIS et sourcés : la cascade du cas travaille vraiment.
POSTES = [
    {'poste': 'salissure', 'pct': 2.0, 'source': 'societe',
     'reference': REFERENCE_CAS},
    {'poste': 'mismatch', 'pct': 2.0, 'source': 'societe',
     'reference': REFERENCE_CAS},
    {'poste': 'onduleur', 'pct': 3.0, 'source': 'societe',
     'reference': REFERENCE_CAS},
    {'poste': 'indisponibilite', 'pct': 3.0, 'source': 'societe',
     'reference': REFERENCE_CAS},
]

#: σ SAISIS (modèle, biais météo) — ils doivent s'appliquer par pan.
REGLAGES_SIGMAS = copy.deepcopy(REGLAGES)
REGLAGES_SIGMAS['simulation'].update({
    'sigma_modele_pct': {'valeur': 3.0, 'source': 'societe',
                         'reference': REFERENCE_CAS},
    'sigma_biais_meteo_pct': {'valeur': 1.0, 'source': 'societe',
                              'reference': REFERENCE_CAS},
})


def _materiel(ac_kw):
    materiel = copy.deepcopy(MATERIEL)
    materiel['onduleur']['ac_kw'] = ac_kw
    return materiel


def _zone(rang, modules, azimut=180.0):
    return {'id': 'z%d' % rang, 'label': 'PAN-%d' % rang,
            'geometry': {'count': modules, 'azimuthDeg': azimut,
                         'tiltDeg': 15.0, 'family': 'surimposition'}}


def _layout(*zones):
    return {'version': 2, 'pin': {'lat': 33.5731, 'lng': -7.5898},
            'zones': list(zones)}


def _reponse(crete=700.0, decalage=0.0):
    """La réponse rejouée, crête ``crete`` W/m² décalée de ``decalage`` h."""
    reponse = _reponse_meteo()
    for point in reponse['points']:
        ecart = abs(point['heure'] - (13 + decalage))
        globale = max(0.0, crete - ecart * crete / 7.7)
        point.update(gi_w_m2=globale, gb_i_w_m2=globale * 0.8,
                     gd_i_w_m2=globale * 0.18, gr_i_w_m2=globale * 0.02)
    return reponse


class _ClientParOrientation:
    """Un client double qui répond une série PROPRE à chaque orientation :
    est (aspect −90) le matin, ouest (+90) l'après-midi, sud au midi."""

    def __init__(self, crete=700.0):
        self.crete = crete
        self.demandes = []

    def serie_irradiance(self, **parametres):
        self.demandes.append(parametres)
        aspect = parametres.get('aspect_deg') or 0.0
        decalage = -3.0 if aspect < -45 else (3.0 if aspect > 45 else 0.0)
        return _reponse(self.crete, decalage)


def _simuler(layout, *, materiel=None, reglages=None, crete=700.0,
             pertes=None):
    calepinage = _Calepinage(layout=copy.deepcopy(layout), pertes=pertes)
    rendu = simuler_calepinage(
        calepinage, client=_ClientParOrientation(crete),
        materiel=materiel or _materiel(30.0), reglages=reglages or REGLAGES,
        enregistrer=False)
    return rendu['blocs']


def _etape(cascade, nom):
    return next(etape for etape in cascade['etapes'] if etape['etape'] == nom)


class DeuxPansTest(SimpleTestCase):

    def test_deux_pans_identiques_egalent_un_pan(self):
        # Un onduleur large (aucun écrêtage) : seule la mécanique des pans
        # est jugée.
        mono = _simuler(_layout(_zone(1, 12)))
        deux = _simuler(_layout(_zone(1, 12), _zone(2, 12)))

        p50_mono = mono['production']['total']['p50_kwh']
        for ligne in deux['production']['par_pan']:
            self.assertAlmostEqual(ligne['p50_kwh'], p50_mono, delta=0.2)
        self.assertAlmostEqual(deux['production']['total']['p50_kwh'],
                               2 * p50_mono, delta=0.2)

    def test_chaque_chaine_de_pan_recoit_meteo_heure(self):
        vues = []
        reelle = chaine_pertes.appliquer_chaine

        def espion(serie, contexte=None, *args, **kwargs):
            if kwargs.get('phase') == 'pan':
                vues.append(copy.deepcopy((contexte or {}).get('meteo')))
            return reelle(serie, contexte, *args, **kwargs)

        with mock.patch.object(simulation, 'appliquer_chaine', espion):
            deux = _simuler(_layout(_zone(1, 12, 90.0), _zone(2, 12, 270.0)))
        self.assertEqual(len(vues), 2)
        for meteo in vues:
            self.assertIn('heure', meteo)
        # Les étapes de chaque pan ont le même état que la chaîne d'un pan
        # seul de même orientation (la météo y est donc bien arrivée).
        mono = _simuler(_layout(_zone(1, 12, 90.0)))
        cascade_mono = mono['ombrage']['par_pan'][0]['cascade']
        cascade_est = deux['ombrage']['par_pan'][0]['cascade']
        self.assertEqual(
            [(e['etape'], bool(e['motif_omission']))
             for e in cascade_est['etapes']],
            [(e['etape'], bool(e['motif_omission']))
             for e in cascade_mono['etapes']])

    def test_une_chaine_de_pan_sans_meteo_est_refusee(self):
        with self.assertRaises(ChaineInvalide) as refus:
            appliquer_chaine({'pas_minutes': 60, 'points': []}, {},
                             phase='pan')
        self.assertEqual(refus.exception.etape, 'meteo')

    def test_deux_pans_un_onduleur_ecretage_sur_la_somme(self):
        materiel = _materiel(3.0)
        unique = _simuler(_layout(_zone(1, 12)), materiel=materiel,
                          crete=1000.0)
        deux = _simuler(_layout(_zone(1, 6), _zone(2, 6)), materiel=materiel,
                        crete=1000.0)

        ecretage = _etape(deux['cascade'], 'ecretage')
        self.assertFalse(ecretage['motif_omission'])
        self.assertGreater(ecretage['perte_kwh'], 0.0)
        p50_unique = unique['production']['total']['p50_kwh']
        self.assertAlmostEqual(deux['production']['total']['p50_kwh'],
                               p50_unique, delta=p50_unique * 0.001)

    def test_sans_table_d_affectation_l_ecretage_est_omis_motive(self):
        with mock.patch(
                'apps.calepinage.services.agregation_electrique.'
                'affectation_du_calepinage',
                return_value={'affectation': (), 'motif': 'aucune table',
                              'avertissements': ()}):
            deux = _simuler(_layout(_zone(1, 6), _zone(2, 6)),
                            materiel=_materiel(3.0), crete=1000.0)
        ecretage = _etape(deux['cascade'], 'ecretage')
        self.assertEqual(ecretage['motif_omission'],
                         MOTIF_ECRETAGE_SANS_AFFECTATION)
        self.assertIsNone(ecretage['perte_pct'])

    def test_cascade_publiee_decrit_la_somme(self):
        deux = _simuler(_layout(_zone(1, 10, 90.0), _zone(2, 6, 270.0)),
                        pertes=POSTES)
        cascade = deux['cascade']
        par_pan = [ligne['cascade'] for ligne in deux['ombrage']['par_pan']]

        self.assertEqual(cascade['ordre'],
                         list(chaine_pertes.ORDRE_ETAPES))
        for nom in ETAPES_PAN:
            somme = sum(_etape(c, nom)['kwh_avant'] for c in par_pan)
            self.assertAlmostEqual(_etape(cascade, nom)['kwh_avant'], somme,
                                   delta=0.01, msg=nom)
        salissure = _etape(cascade, 'salissure')
        self.assertFalse(salissure['motif_omission'])
        self.assertAlmostEqual(salissure['perte_pct'], 2.0, delta=0.01)
        self.assertEqual(deux['production']['total']['total_loss_pct'],
                         cascade['total_pct'])
        for ligne in deux['ombrage']['par_pan']:
            self.assertIn('perte_ombrage_pct', ligne)
            self.assertIsInstance(ligne['cascade']['etapes'], list)
        self.assertNotIn(
            'cascade et la série horaire publiées sont celles du pan',
            ' '.join(deux.get('avertissements') or []))

    def test_pr_et_ecart_sur_la_somme(self):
        deux = _simuler(_layout(_zone(1, 10, 90.0), _zone(2, 6, 270.0)),
                        pertes=POSTES)
        self.assertEqual(deux['performance']['pr'],
                         deux['production']['total']['performance_ratio'])

        # L'écart PVcalc lit la sortie du SITE fournie, sans rejouer un pan.
        sortie = {'pas_minutes': 60, 'colonne_energie': 'p_ac_kw',
                  'points': [{'annee': 2020, 'mois': 1, 'jour': 1,
                              'heure': 12, 'p_ac_kw': 2.0}]}
        perte = sum(poste['pct'] for poste in POSTES)
        reponse = {'inputs': {'pv_module': {'peak_power': 5.0,
                                            'system_loss': perte}},
                   'outputs': {'monthly': {'fixed': [
                       {'month': 1, 'E_m': 2.0}]}}}
        bloc = ecart_vs_pvcalc({'points': []}, {}, reponse, kwc=5.0,
                               sortie=sortie,
                               cascade={'total_pct': perte, 'etapes': []})
        self.assertEqual(bloc['total_chaine_locale_kwh'], 2.0)

    def test_par_pan_p90_avec_sigmas_saisis(self):
        # ACAL49 : le socle physique saisi (sinon P90 masqué, borne haute).
        socle = [dict(POSTES[0], poste=nom, pct=1.0) for nom in (
            'salissure', 'mismatch', 'lid', 'ohmique_dc', 'ohmique_ac',
            'qualite_module', 'indisponibilite')]
        deux = _simuler(_layout(_zone(1, 10, 90.0), _zone(2, 6, 270.0)),
                        reglages=REGLAGES_SIGMAS, pertes=socle)
        for ligne in deux['production']['par_pan']:
            self.assertIsNotNone(ligne['p90_kwh'], ligne['pan'])
            self.assertLess(ligne['p90_kwh'], ligne['p50_kwh'])

    def test_un_pan_reste_strictement_inchange(self):
        # Mono-pan : une seule passe, toute la chaîne d'affilée.
        appels = []
        reelle = chaine_pertes.appliquer_chaine

        def espion(serie, contexte=None, *args, **kwargs):
            appels.append(kwargs.get('phase'))
            return reelle(serie, contexte, *args, **kwargs)

        with mock.patch.object(simulation, 'appliquer_chaine', espion):
            _simuler(_layout(_zone(1, 12)), pertes=POSTES)
        self.assertEqual(appels, [None])


# ── le golden multi-pans dissymétrique ──────────────────────────────────

def _cas_golden():
    return _simuler(_layout(_zone(1, 10, 90.0), _zone(2, 6, 270.0)),
                    materiel=_materiel(3.0), crete=1000.0, pertes=POSTES,
                    reglages=REGLAGES_SIGMAS)


def _resume(blocs):
    total = blocs['production']['total']
    return {
        'total': {cle: total[cle] for cle in (
            'kwc', 'p50_kwh', 'p75_kwh', 'p90_kwh', 'performance_ratio',
            'specific_yield_kwh_kwc', 'total_loss_pct')},
        'par_pan': [{cle: ligne[cle] for cle in (
            'pan', 'kwc', 'p50_kwh', 'p75_kwh', 'p90_kwh')}
            for ligne in blocs['production']['par_pan']],
        'cascade': [{'etape': etape['etape'],
                     'omise': bool(etape['motif_omission']),
                     'kwh_avant': etape['kwh_avant'],
                     'kwh_apres': etape['kwh_apres'],
                     'perte_pct': etape['perte_pct']}
                    for etape in blocs['cascade']['etapes']],
        'ombrage_par_pan': [{'pan': ligne['pan'],
                             'perte_ombrage_pct': ligne['perte_ombrage_pct'],
                             'total_pct': ligne['cascade']['total_pct']}
                            for ligne in blocs['ombrage']['par_pan']],
    }


class GoldenMultiPansTest(SimpleTestCase):
    """Est 10 modules + ouest 6 modules sur UN onduleur de 3 kW : écrêtage
    sur la somme, cascade de la somme, pans dissymétriques."""

    def test_le_golden_est_reproduit(self):
        attendu = json.loads(GOLDEN.read_text(encoding='utf-8'))['attendu']
        obtenu = json.loads(json.dumps(_resume(_cas_golden())))
        self.assertEqual(obtenu, attendu)


def ecrire_le_golden():  # pragma: no cover — chemin « --write » seulement
    document = {
        '_provenance': {
            'tache': 'ACAL53',
            'produit_par': ('python -m apps.calepinage.tests.'
                            'test_acal_multi_pans --write'),
            'cas': ('Est 10 modules (aspect -90) + ouest 6 modules (aspect '
                    '+90), 710 Wc, onduleur 3 kW, crête 1000 W/m² rejouée, '
                    'postes salissure 2 / mismatch 2 / onduleur 3 / '
                    'indisponibilité 3 %, σ modèle 3 % et biais 1 %.'),
            'comment_regenerer': (
                'Relancer la commande À LA MAIN, lire le diff, dire dans le '
                'message de commit POURQUOI la cascade a bougé.'),
        },
        'attendu': _resume(_cas_golden()),
    }
    GOLDEN.write_text(json.dumps(document, ensure_ascii=False, indent=1)
                      + '\n', encoding='utf-8')
    return GOLDEN


if __name__ == '__main__':  # pragma: no cover — chemin « --write » seulement
    if '--write' not in sys.argv[1:]:
        raise SystemExit('--write est obligatoire : écrire écrase le golden.')
    print(ecrire_le_golden())
