"""NTDATA13 — alertes KPI branchées sur les métriques sémantiques.

Couvre :
  * RÉTRO-COMPATIBILITÉ : `source` vaut `catalogue` par défaut et une alerte
    existante (kpi du catalogue fermé) se comporte exactement comme avant ;
  * une alerte `mrr < 10000` sur une MetricDefinition SE DÉCLENCHE ;
  * la dédup (`deja_notifie`) et le ré-armement fonctionnent pareil ;
  * une métrique supprimée (SET_NULL) n'évalue rien plutôt que de mentir ;
  * la validation nomme le CHAMP fautif et refuse une métrique d'une autre
    société.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.crm.models import Client
from apps.reporting.kpi_alertes import evaluate_kpi_alerte
from apps.reporting.models import KpiAlerte
from apps.sav.models import ContratMaintenance
from apps.semantic.models import MetricDefinition
from authentication.models import Company

User = get_user_model()


class AlerteSurMetriqueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA13 SA',
                                             slug='ntdata13-sa')
        cls.autre = Company.objects.create(nom='NTDATA13 Autre',
                                           slug='ntdata13-autre')
        cls.user = User.objects.create_user(
            username='ntdata13_u', password='x', company=cls.company,
            role_legacy='admin')
        cls.client_obj = Client.objects.create(company=cls.company,
                                               nom='ClientNTDATA13')
        # MRR = Σ(valeur annuelle des contrats actifs) / 12.
        # Un contrat ANNUEL à 12 000 MAD ⇒ MRR = 1 000 < 10 000.
        ContratMaintenance.objects.create(
            company=cls.company, client=cls.client_obj,
            periodicite=ContratMaintenance.Periodicite.ANNUEL,
            date_debut=date(2026, 1, 1), prix=Decimal('12000.00'))
        cls.metrique = MetricDefinition.objects.create(
            company=cls.company, cle='mrr', libelle='MRR',
            dataset='sav_contrats',
            mesure={
                'formula': 'annuel / 12',
                'aggregates': [{'alias': 'annuel', 'fn': 'sum',
                                'field': 'valeur_annuelle'}],
            },
            filtres={'actif': True},
            unite=MetricDefinition.Unite.MAD)

    def _alerte(self, **kw):
        defaults = dict(
            company=self.company, nom='MRR bas',
            source=KpiAlerte.Source.METRIQUE,
            metric_definition=self.metrique,
            operateur=KpiAlerte.Operateur.INF, seuil=Decimal('10000.00'),
            destinataire_role='admin')
        defaults.update(kw)
        return KpiAlerte.objects.create(**defaults)

    def test_source_par_defaut_est_le_catalogue(self):
        alerte = KpiAlerte.objects.create(
            company=self.company, kpi=KpiAlerte.Kpi.DSO,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('60'))
        self.assertEqual(alerte.source, KpiAlerte.Source.CATALOGUE)
        # Chemin historique : évaluable, sans toucher à la couche sémantique.
        valeur, franchi, _notifie = evaluate_kpi_alerte(alerte)
        self.assertFalse(franchi)
        self.assertIsNotNone(valeur)

    def test_alerte_mrr_sous_le_seuil_se_declenche(self):
        alerte = self._alerte()
        with mock.patch(
                'apps.reporting.kpi_alertes._notify_kpi_alerte') as notifier:
            valeur, franchi, notifie = evaluate_kpi_alerte(alerte)
        self.assertEqual(valeur, Decimal('1000'))
        self.assertTrue(franchi)
        self.assertTrue(notifie)
        notifier.assert_called_once()
        alerte.refresh_from_db()
        self.assertTrue(alerte.deja_notifie)

    def test_dedup_puis_rearmement(self):
        alerte = self._alerte()
        with mock.patch('apps.reporting.kpi_alertes._notify_kpi_alerte'):
            evaluate_kpi_alerte(alerte)
            # Deuxième passage : toujours franchi, mais PAS de re-notification.
            _valeur, franchi, notifie = evaluate_kpi_alerte(alerte)
        self.assertTrue(franchi)
        self.assertFalse(notifie)
        # Le seuil descend sous la valeur → repasse du bon côté → ré-armement.
        alerte.seuil = Decimal('100.00')
        alerte.save(update_fields=['seuil'])
        with mock.patch('apps.reporting.kpi_alertes._notify_kpi_alerte'):
            _valeur, franchi, _notifie = evaluate_kpi_alerte(alerte)
        self.assertFalse(franchi)
        alerte.refresh_from_db()
        self.assertFalse(alerte.deja_notifie)

    def test_metrique_supprimee_n_evalue_rien(self):
        alerte = self._alerte()
        self.metrique.delete()
        alerte.refresh_from_db()
        self.assertIsNone(alerte.metric_definition_id)
        valeur, franchi, notifie = evaluate_kpi_alerte(alerte)
        self.assertIsNone(valeur)
        self.assertFalse(franchi)
        self.assertFalse(notifie)

    def test_metrique_inactive_n_evalue_rien(self):
        alerte = self._alerte()
        MetricDefinition.objects.filter(pk=self.metrique.pk).update(actif=False)
        valeur, franchi, _notifie = evaluate_kpi_alerte(alerte)
        self.assertIsNone(valeur)
        self.assertFalse(franchi)

    def test_validation_nomme_le_champ_fautif(self):
        alerte = KpiAlerte(company=self.company,
                           source=KpiAlerte.Source.METRIQUE,
                           operateur=KpiAlerte.Operateur.INF,
                           seuil=Decimal('1'))
        with self.assertRaises(ValidationError) as ctx:
            alerte.clean()
        self.assertIn('metric_definition', ctx.exception.message_dict)

        sans_kpi = KpiAlerte(company=self.company,
                             source=KpiAlerte.Source.CATALOGUE,
                             operateur=KpiAlerte.Operateur.SUP,
                             seuil=Decimal('1'))
        with self.assertRaises(ValidationError) as ctx:
            sans_kpi.clean()
        self.assertIn('kpi', ctx.exception.message_dict)

    def test_metrique_d_une_autre_societe_refusee(self):
        etrangere = MetricDefinition.objects.create(
            company=self.autre, cle='mrr', libelle='MRR',
            dataset='sav_contrats', mesure={'agg': 'count'})
        alerte = KpiAlerte(company=self.company,
                           source=KpiAlerte.Source.METRIQUE,
                           metric_definition=etrangere,
                           operateur=KpiAlerte.Operateur.INF,
                           seuil=Decimal('1'))
        with self.assertRaises(ValidationError) as ctx:
            alerte.clean()
        self.assertIn('metric_definition', ctx.exception.message_dict)
