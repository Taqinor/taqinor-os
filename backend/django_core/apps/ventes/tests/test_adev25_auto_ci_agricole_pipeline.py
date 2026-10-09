"""ADEV25 (C-ADEV-036) — les devis automatiques commercial/industriel et
agricole sont écrits par le PIPELINE (``appliquer(MODE_ECRIRE)`` puis
``MODE_RAFRAICHIR``) sous ``transaction.atomic()``, comme le résidentiel :
kWc, marge interne, instantané et provenance posés, tout ou rien.

Rejoue VB p8b/p8c (commercial et agricole : marge None, kWc None,
0 instantané). Source réelle : pipeline et ``creation_auto`` ; le tarif C&I
et les profils pompage sont les seules doublures (comme ``test_ciq120`` /
``test_agr124``), plus une panne injectée pour le test « tout ou rien ».

Test-du-test : remettre la boucle ``creer_ligne`` ⇒
``test_commercial_kwc_marge_instantane`` échoue.
"""
from decimal import Decimal
from unittest import mock

from apps.ventes.models import ConfigurationDevisSnapshot, Devis
from apps.ventes.tests import test_agr124_devis_auto_agricole as agr124
from apps.ventes.tests import test_ciq120_devis_auto_ci as ciq120


class AutoCiAgricolePipelineTests(ciq120._Base):

    def _verifier(self, devis):
        devis.refresh_from_db()
        etude = devis.etude_params or {}
        self.assertIsNotNone(etude.get('puissance_kwc'))
        self.assertIsNotNone(devis.marge_snapshot)
        self.assertEqual(ConfigurationDevisSnapshot.objects.filter(
            devis=devis).count(), 1)
        self.assertIn('provenance', etude)

    def test_commercial_kwc_marge_instantane(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        devis = self._auto(lead)
        self._verifier(devis)

    def test_echec_au_milieu_aucun_devis(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        avant = Devis.objects.filter(company=self.co).count()
        with mock.patch('apps.ventes.domain.pipeline.ecrire_lignes',
                        side_effect=RuntimeError('panne au milieu')):
            with self.assertRaises(RuntimeError):
                self._auto(lead)
        self.assertEqual(Devis.objects.filter(company=self.co).count(), avant)


class AutoAgricolePipelineTests(agr124.DevisAutoAgricoleTests):
    """Hérite du montage AGR124 ; ses tests propres sont rejoués tels quels
    (même chemin, désormais par le pipeline)."""

    def test_agricole_kwc_marge_instantane(self):
        self._pompe('15000')
        lead = self._lead()
        rep = self._post(lead)
        self.assertEqual(rep.status_code, 201, rep.data)
        devis = Devis.objects.get(pk=rep.data['id'])
        AutoCiAgricolePipelineTests._verifier(self, devis)
