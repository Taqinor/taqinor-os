"""ACAL49 — la complétude de la simulation : « borne haute » et quantiles
masqués tant que le socle physique n'est pas saisi (D-ACAL-7).

Constat C-ACAL-076 : une société sans réglages de pertes publiait un PR de
100 % et un P90 calculés sur une chaîne où salissure, LID, mismatch, ohmique,
qualité module et indisponibilité étaient OMIS — un chiffre optimiste
présenté comme une production bancable.

Désormais (source UNIQUE : ``chaine_pertes.completude_de_la_chaine``, lue
par ``_bloc_production``) : ``cascade.etapes_omises`` (toutes les chaînes,
pans compris), ``production.total.complete`` / ``socle_manquant`` /
``mention`` (« borne haute — N pertes non renseignées »), PR, P75, P90 et
P95 à ``null`` avec leur motif (au total, par pan, et dans le bloc
``incertitude``), et l'avertissement EN TÊTE. Le P50 reste publié.

Chaîne RÉELLE (``simuler_calepinage``, client rejoué CALX5), aucun mock de
la chaîne.

Run :
    python manage.py test apps.calepinage.tests.test_acal_completude_simulation -v2
"""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from apps.calepinage.services.chaine_pertes import (
    CLE_CASCADES_PAR_PAN, SOCLE_PHYSIQUE, appliquer_chaine,
    cascade_de_la_somme, completude_de_la_chaine,
)
from apps.calepinage.services.simulation import simuler_calepinage

from .test_acal_multi_pans import _ClientParOrientation, _layout, _zone
from .test_calx5_simulation import (
    LAYOUT, MATERIEL, REGLAGES, _Calepinage, _ClientRejoue,
)

REFERENCE = 'Cas de TEST ACAL49 — aucune valeur produit'


def _poste(nom, pct):
    return {'poste': nom, 'pct': pct, 'source': 'societe',
            'reference': REFERENCE}


#: Le SOCLE entièrement saisi et sourcé (noms du catalogue des postes).
SOCLE_SAISI = [
    _poste('salissure', 2.0), _poste('mismatch', 1.5), _poste('lid', 1.0),
    _poste('ohmique_dc', 1.0), _poste('ohmique_ac', 0.5),
    _poste('qualite_module', 0.5), _poste('indisponibilite', 1.0),
]

REGLAGES_SIGMAS = copy.deepcopy(REGLAGES)
REGLAGES_SIGMAS['simulation'].update({
    'sigma_modele_pct': {'valeur': 3.0, 'source': 'societe',
                         'reference': REFERENCE},
    'sigma_biais_meteo_pct': {'valeur': 1.0, 'source': 'societe',
                              'reference': REFERENCE},
})


def _compte(mention):
    """Le N de « borne haute — N pertes non renseignées » (0 sans mention)."""
    if not mention:
        return 0
    return int(mention.split('—')[1].split()[0])


def _simuler(*, pertes=None, layout=None, reglages=None, client=None):
    calepinage = _Calepinage(layout=copy.deepcopy(layout or LAYOUT),
                             pertes=pertes)
    return simuler_calepinage(
        calepinage, client=client or _ClientRejoue(), materiel=MATERIEL,
        reglages=reglages or REGLAGES_SIGMAS, enregistrer=False)['blocs']


class CompletudeTest(SimpleTestCase):

    def test_societe_sans_reglages_borne_haute(self):
        blocs = _simuler()
        total = blocs['production']['total']

        self.assertFalse(total['complete'])
        self.assertEqual(total['socle_manquant'], list(SOCLE_PHYSIQUE))
        self.assertTrue(total['mention'].startswith('borne haute — '))
        self.assertIn('pertes non renseignées', total['mention'])
        self.assertIsNotNone(total['p50_kwh'])
        for cle in ('performance_ratio', 'p75_kwh', 'p90_kwh', 'p95_kwh'):
            self.assertIsNone(total[cle], cle)
            self.assertTrue(total[f'{cle}_motif'], cle)
            self.assertIn('salissure', total[f'{cle}_motif'])
        for etape in SOCLE_PHYSIQUE:
            self.assertIn(etape, blocs['cascade']['etapes_omises'])
        self.assertTrue(blocs['avertissements'][0].startswith(
            'Production publiée en « borne haute'))
        quantiles = blocs['incertitude']['quantiles']
        for cle in ('p75_kwh', 'p90_kwh', 'p95_kwh'):
            self.assertIsNone(quantiles[cle], cle)
        self.assertEqual(blocs['incertitude']['motif_refus'],
                         total['performance_ratio_motif'])

    def test_socle_saisi_complet(self):
        blocs = _simuler(pertes=SOCLE_SAISI)
        total = blocs['production']['total']

        self.assertTrue(total['complete'], total['socle_manquant'])
        self.assertEqual(total['socle_manquant'], [])
        self.assertIsNotNone(total['performance_ratio'])
        self.assertIsNotNone(total['p90_kwh'])
        self.assertIsNotNone(total['p95_kwh'])
        self.assertEqual(total['performance_ratio_motif'], '')
        self.assertIsNotNone(blocs['incertitude']['quantiles']['p90_kwh'])
        # Les AUTRES omissions (IAM, horizon… sans entrée) restent comptées.
        autres = [nom for nom in blocs['cascade']['etapes_omises']
                  if nom not in ('spectral', 'diodes', 'neige')]
        if autres:
            self.assertTrue(total['mention'].startswith('borne haute — '))

    def test_omission_d_un_pan_comptee_dans_le_marqueur(self):
        # Deux chaînes de pan RÉELLES : l'IAM s'applique sur la première (un
        # poste « iam » saisi et sourcé), s'omet sur la seconde. La cascade de
        # la SOMME la dit appliquée — mais le marqueur la compte omise.
        serie = {'pas_minutes': 60, 'colonne_energie': 'p_w',
                 'points': [{'annee': 2020, 'mois': 6, 'jour': 21,
                             'heure': heure, 'p_w': 1000.0 * heure,
                             'gi_w_m2': 100.0 * heure}
                            for heure in range(8, 16)]}

        def chaine(postes):
            contexte = {'meteo': {'heure': {'base': None}},
                        'postes_saisis': postes,
                        'hash_entree': 'acal49'}
            return appliquer_chaine(serie, contexte, phase='pan')[1]

        avec_iam = chaine(SOCLE_SAISI + [_poste('iam', 3.0)])
        sans_iam = chaine(SOCLE_SAISI)
        self.assertNotIn('iam', avec_iam['etapes_omises'])
        self.assertIn('iam', sans_iam['etapes_omises'])

        somme = cascade_de_la_somme([avec_iam, sans_iam], None, None)
        iam = next(e for e in somme['etapes'] if e['etape'] == 'iam')
        self.assertFalse(iam['motif_omission'])
        self.assertIn('iam', somme['etapes_omises'])
        completude = completude_de_la_chaine(
            somme, {CLE_CASCADES_PAR_PAN: {'A': avec_iam, 'B': sans_iam}})
        seule_a = completude_de_la_chaine(avec_iam)
        # Le marqueur de la somme compte UNE omission de plus que la chaîne
        # qui a l'IAM : celle du pan qui ne l'a pas.
        self.assertGreater(_compte(completude['mention']),
                           _compte(seule_a['mention']))

    def test_p75_p95_masques_comme_p90(self):
        total = _simuler()['production']['total']
        motifs = {total[f'{cle}_motif'] for cle in
                  ('p75_kwh', 'p90_kwh', 'p95_kwh', 'performance_ratio')}
        self.assertEqual(len(motifs), 1)
        self.assertTrue(motifs.pop())

    def test_sigma_societe_par_pan(self):
        # Socle saisi : le P90 de chaque pan est publié, avec les σ saisis
        # (modèle + biais) même sans σ météo mesurable par pan.
        blocs = _simuler(pertes=SOCLE_SAISI,
                         layout=_layout(_zone(1, 8, 90.0),
                                        _zone(2, 8, 270.0)),
                         client=_ClientParOrientation())
        for ligne in blocs['production']['par_pan']:
            self.assertIsNotNone(ligne['p90_kwh'], ligne['pan'])
        # Socle manquant : masqué aussi par pan.
        masque = _simuler(layout=_layout(_zone(1, 8, 90.0),
                                         _zone(2, 8, 270.0)),
                          client=_ClientParOrientation())
        for ligne in masque['production']['par_pan']:
            self.assertIsNone(ligne['p90_kwh'])
            self.assertIsNone(ligne['performance_ratio'])
            self.assertIsNotNone(ligne['p50_kwh'])

    def test_relecture_identique(self):
        premier = _simuler()
        second = _simuler()
        self.assertEqual(premier['production']['total'],
                         second['production']['total'])
