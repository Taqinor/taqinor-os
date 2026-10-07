"""ACAL102 — backfill 0132 de ``production_source`` + ``dryrun_acal102``.

* la règle de la migration reproduit l'ancienne égalité devinée
  (``_est_la_figure_du_calepinage`` @ 818241faa) : marquée ⇔ au moins une
  figure recalée et aucune souveraine ; un cas mixte reste non marqué ;
* la migration marque un devis réel puis son retour retire la marque ;
* la commande de dry-run n'écrit rien et compte 0 écart sur un devis marqué.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal102_backfill"
"""
import importlib
from decimal import Decimal
from io import StringIO

from django.apps import apps as registre
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.ventes.models import Devis
from authentication.models import Company

M = importlib.import_module(
    'apps.ventes.migrations.0132_acal102_backfill_production_source')
LAYOUT = {'result': {'panels': 8, 'kwc': 5.76, 'annualKwh': 8843.66,
                     'savings': 7000}}


class RegleBackfillTest(SimpleTestCase):
    def test_egalite_ancienne_marquee(self):
        self.assertTrue(M.doit_marquer(
            {'production_annuelle': 8844, 'economies_annuelles': 7000},
            LAYOUT))

    def test_tronquee_souveraine_non_marquee(self):
        # 8843 (tronquée) ≠ 8844 : l'ancien moteur NE recalait PAS.
        self.assertFalse(M.doit_marquer({'production_annuelle': 8843},
                                        LAYOUT))

    def test_mixte_non_marque(self):
        etude = {'production_annuelle': 8843, 'economies_annuelles': 7000}
        self.assertFalse(M.doit_marquer(etude, LAYOUT))
        self.assertTrue(M.est_mixte(etude, LAYOUT))

    def test_sans_layout_ou_sans_figure(self):
        self.assertFalse(M.doit_marquer({'production_annuelle': 8844}, None))
        self.assertFalse(M.doit_marquer({}, LAYOUT))


class MigrationEtDryRunTest(TestCase):
    def setUp(self):
        company = Company.objects.create(nom='ACAL102b', slug='acal102b')
        client = Client.objects.create(company=company, nom='Client 102b')
        self.devis = Devis.objects.create(
            company=company, client=client, reference='DEV-102B-0001',
            statut='envoye', taux_tva=Decimal('20'), roof_layout=LAYOUT,
            etude_params={'production_annuelle': 8844,
                          'economies_annuelles': 7000})

    def test_marquer_puis_retirer(self):
        M.marquer(registre, None)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params['production_source'],
                         'calepinage')
        M.retirer(registre, None)
        self.devis.refresh_from_db()
        self.assertNotIn('production_source', self.devis.etude_params)
        self.assertNotIn('production_source_backfill',
                         self.devis.etude_params)

    def test_dryrun_zero_ecart_et_aucune_ecriture(self):
        avant = dict(self.devis.etude_params)
        sortie = StringIO()
        call_command('dryrun_acal102', stdout=sortie)
        self.assertIn('envoyé/accepté : 0', sortie.getvalue())
        self.assertIn('brouillon : 0', sortie.getvalue())
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params, avant)
