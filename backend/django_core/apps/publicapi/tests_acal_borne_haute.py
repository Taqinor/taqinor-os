"""ACAL51 — l'API publique du calepinage publie la complétude de la simulation.

Constat C-ACAL-076 : une simulation INCOMPLÈTE (socle physique des pertes non
saisi, ACAL49 ``production.total.complete`` faux) est une borne haute. La
ressource publique ``GET calepinages/<id>/resultat/`` doit alors publier
``ratio_performance``/``p75_kwh``/``p90_kwh`` à ``null`` et deux champs
ADDITIFS ``complet`` et ``mention_production`` ; la charge du webhook
``calepinage.simule`` lit la même règle (PR ``null``).

Le résultat vient de la VRAIE chaîne : ``enregistrer_entree`` puis
``simuler_calepinage`` (météo rejouée en entrée, harnais ACAL214), lu par
``selectors.resultat_servi`` — aucune fixture écrite à la main, aucun mock de
la chaîne ni du code sous test (seuls les seams documentés du matériel).

Run :
    python manage.py test apps.publicapi.tests_acal_borne_haute -v2
"""
import copy
from unittest import mock

from django.test import SimpleTestCase

from .calepinage_event_receivers import charge_utile_simulation
from .public_serializers import (
    PublicCalepinageResultatSerializer, resultat_calepinage_public,
)


def _pivot_simule(pertes=None):
    """Un calepinage conçu, désigné puis SIMULÉ par les vrais écrivains."""
    from apps.calepinage.services.electrique import enregistrer_entree
    from apps.calepinage.services.simulation import simuler_calepinage
    from apps.calepinage.tests.acal_livrables_helpers import (
        LAYOUT_SIMULABLE, MATERIEL, PivotSansBase, patch_materiel,
    )
    from apps.calepinage.tests.test_calx5_simulation import _ClientRejoue

    pivot = PivotSansBase(copy.deepcopy(LAYOUT_SIMULABLE))
    pivot.pertes = copy.deepcopy(pertes or [])
    catalogue = mock.patch('apps.stock.selectors.get_produit_scoped',
                           side_effect=lambda company, pk: object())
    with patch_materiel(), catalogue:
        enregistrer_entree(pivot, {'module_produit': 1, 'onduleur_produit': 2})
        simuler_calepinage(pivot, client=_ClientRejoue(), materiel=MATERIEL,
                           enregistrer=True)
    return pivot


def _servi(pivot):
    from apps.calepinage import selectors
    from apps.calepinage.tests.acal_livrables_helpers import patch_materiel

    with patch_materiel():
        return selectors.resultat_servi(pivot)


def _publie(servi):
    return PublicCalepinageResultatSerializer(
        resultat_calepinage_public(1, servi)).data


class BorneHautePubliqueTest(SimpleTestCase):

    def test_ratio_performance_null_si_incomplet(self):
        pivot = _pivot_simule()
        servi = _servi(pivot)
        total = servi['production']['total']
        self.assertTrue(servi['simule'])
        self.assertIs(total['complete'], False)

        data = _publie(servi)
        self.assertTrue(data['simule'])
        self.assertIs(data['complet'], False)
        for cle in ('ratio_performance', 'p75_kwh', 'p90_kwh'):
            self.assertIsNone(data[cle], cle)
        # Le P50 reste publié (avec sa mention).
        self.assertIsNotNone(data['p50_kwh'])
        self.assertEqual(data['p50_kwh'], total['p50_kwh'])
        # Le webhook calepinage.simule lit la même règle.
        charge = charge_utile_simulation(pivot)
        self.assertIsNone(charge['performance_ratio'])
        self.assertEqual(charge['p50_kwh'], total['p50_kwh'])

    def test_mention_publiee(self):
        servi = _servi(_pivot_simule())
        mention = servi['production']['total']['mention']
        self.assertTrue(mention.startswith('borne haute — '), mention)

        data = _publie(servi)
        self.assertEqual(data['mention_production'], mention)
        self.assertIn('pertes non renseign', data['mention_production'])

    def test_complet_ratio_et_p90_inchanges(self):
        from apps.calepinage.tests.test_acal_completude_simulation import (
            SOCLE_SAISI,
        )

        pivot = _pivot_simule(pertes=SOCLE_SAISI)
        servi = _servi(pivot)
        total = servi['production']['total']
        self.assertIs(total['complete'], True, total.get('socle_manquant'))

        data = _publie(servi)
        self.assertIs(data['complet'], True)
        self.assertIsNotNone(data['ratio_performance'])
        self.assertEqual(data['ratio_performance'],
                         total['performance_ratio'])
        self.assertEqual(data['p90_kwh'], total['p90_kwh'])
        self.assertEqual(data['p75_kwh'], total['p75_kwh'])
        charge = charge_utile_simulation(pivot)
        self.assertEqual(charge['performance_ratio'],
                         total['performance_ratio'])

    def test_non_simule_complet_null_et_mention_vide(self):
        data = _publie({'simule': False, 'motif': ''})
        self.assertIsNone(data['complet'])
        self.assertEqual(data['mention_production'], '')

    def test_incomplet_ratio_non_nul_masque(self):
        """ACAL362 — tue le mutant « lire sans condition » : une simulation
        incomplète portant un PR non nul ne le publie ni en API ni en webhook."""
        for complete in (False, True):
            with self.subTest(complete=complete):
                pivot = _pivot_simule()
                servi = copy.deepcopy(_servi(pivot))
                posee = {'complete': complete, 'performance_ratio': 0.81,
                         'p75_kwh': 9500.0, 'p90_kwh': 9000.0}
                # Le même état forcé des deux côtés : le servi (API publique)
                # et le résultat stocké lu par la charge du webhook.
                servi['production']['total'].update(posee)
                pivot.resultat['production']['total'].update(posee)
                self.assertTrue(servi['simule'])
                data = _publie(servi)
                charge = charge_utile_simulation(pivot)
                if complete:
                    self.assertEqual(data['ratio_performance'], 0.81)
                    self.assertEqual(data['p75_kwh'], 9500.0)
                    self.assertEqual(data['p90_kwh'], 9000.0)
                    self.assertEqual(charge['performance_ratio'], 0.81)
                else:
                    for cle in ('ratio_performance', 'p75_kwh', 'p90_kwh'):
                        self.assertIsNone(data[cle], cle)
                    self.assertIsNone(charge['performance_ratio'])
