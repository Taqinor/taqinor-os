"""AMOT62 (C-AMOT-052) — la synthèse C&I décrit UNE option.

Sonde VC lci8 : devis commercial « Les deux » à panneaux 50 ``sans`` / 70
``avec`` — ``option_servie sans``, ``kwc sans/avec 35.5 49.7``, mais
``etude_ci`` calculée pour 49,7 kWc ; la production 79 482 kWh était imprimée
à côté de 35,5 kWc (2 239 kWh/kWc).

Deux gardes :
  * ``rafraichir_etude_ci_devis`` calcule l'étude pour l'option SERVIE
    (CIQ302 : l'offre réseau seule, sauf option AVEC acceptée) ;
  * ``synthese._systeme`` / ``synthese_ci`` omettent production ET taux (motif
    publié) quand le kWc servi s'écarte de plus de 2 % de celui de l'étude.

PVGIS simulé (patron CIQ119/CIQ210) ; ``puissances_etude_horaire`` est
contraint aux puissances de la sonde (35,5 / 49,7) — c'est l'entrée réelle
qu'il rend sur ce devis, le moteur C&I lui-même n'est pas simulé.

Test-du-test : remettre ``kwc, _kwc_sans = puissances_etude_horaire(devis)``
sans usage de l'option servie ⇒ ``test_etude_calculee_pour_l_option_servie``
rougit (étude à 49,7).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_amot62_ci_options_divergentes -v 2
"""
from unittest import mock

from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.quote_engine.ci.synthese import (
    MOTIF_ETUDE_AUTRE_PUISSANCE, synthese_ci,
)
from apps.ventes.tests.test_ciq210_branchement import _BaseDevis

KWC_AVEC, KWC_SANS = 49.7, 35.5


class CiOptionsDivergentesTests(_BaseDevis):

    def _rafraichir(self, devis):
        from apps.ventes.domain.etude_ci import rafraichir_etude_ci_devis
        with mock.patch('apps.ventes.domain.etudes.puissances_etude_horaire',
                        return_value=(KWC_AVEC, KWC_SANS)):
            rafraichir_etude_ci_devis(devis, force=True)
        devis.refresh_from_db()
        return (devis.etude_params or {}).get('etude_ci') or {}

    def test_etude_calculee_pour_l_option_servie(self):
        devis = self._devis('DEV-AMOT62-0010', mode='commercial', tension='bt')
        etude = self._rafraichir(devis)
        self.assertEqual((etude.get('taille') or {}).get('retenue_kwc'),
                         KWC_SANS)
        # CLAUSE PERSISTANCE : rafraîchir deux fois → étude identique.
        self.assertEqual(self._rafraichir(devis), etude)

    def test_option_avec_acceptee_l_etude_suit(self):
        devis = self._devis('DEV-AMOT62-0020', mode='commercial', tension='bt')
        Devis.objects.filter(pk=devis.pk).update(
            option_acceptee='avec_batterie')
        devis.refresh_from_db()
        etude = self._rafraichir(devis)
        self.assertEqual((etude.get('taille') or {}).get('retenue_kwc'),
                         KWC_AVEC)


def _data(kwc_servi, kwc_etude):
    """Charge C&I minimale de ``synthese_ci`` : option SANS servie à
    ``kwc_servi``, étude calculée pour ``kwc_etude``."""
    return {
        'mode_installation': 'commercial',
        'option_servie': 'sans', 'sans_ok': True, 'avec_ok': True,
        'puissance_kwc': KWC_AVEC, 'puissance_kwc_sans': kwc_servi,
        'puissance_kwc_avec': KWC_AVEC,
        'nb_panneaux_sans': 50, 'nb_panneaux_avec': 70,
        'etude': {'etude_ci': {
            'taille': {'retenue_kwc': kwc_etude},
            'bilan': {'production_kwh': 79482, 'taux_autoconso': 0.6,
                      'taux_couverture': 0.4},
        }},
    }


class SyntheseUneOptionTests(TestCase):

    def test_kwc_divergent_production_et_taux_omis(self):
        synthese = synthese_ci(_data(KWC_SANS, KWC_AVEC))
        self.assertEqual(synthese['systeme']['kwc'], KWC_SANS)
        self.assertIsNone(synthese['systeme']['production_kwh_an'])
        self.assertNotIn('energie', synthese)
        motifs = {(o['bloc'], o['motif']) for o in synthese['omissions']}
        self.assertIn(('systeme.production_kwh_an',
                       MOTIF_ETUDE_AUTRE_PUISSANCE), motifs)
        self.assertIn(('energie', MOTIF_ETUDE_AUTRE_PUISSANCE), motifs)

    def test_meme_option_production_et_taux_servis(self):
        synthese = synthese_ci(_data(KWC_SANS, KWC_SANS))
        self.assertEqual(synthese['systeme']['production_kwh_an'], 79482)
        self.assertIn('energie', synthese)

    def test_tolerance_de_deux_pour_cent(self):
        self.assertIsNotNone(synthese_ci(_data(35.5, 36.0))['systeme'][
            'production_kwh_an'])
        self.assertIsNone(synthese_ci(_data(35.5, 37.0))['systeme'][
            'production_kwh_an'])
