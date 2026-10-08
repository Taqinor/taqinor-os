"""APAR8 — marqueur d'idempotence par OCCURRENCE métier (plus par jour).

Constat C-APAR-008 : le marqueur AUD822 était clé sur le JOUR du passage —
une facture impayée 30 jours recevait 30 relances, un équipement en fin de
garantie une demande d'approbation par jour. Désormais la clé est l'occurrence
(échéance de la facture, ``prochaine_visite()`` du contrat, fin de garantie) et
le signal ``_facture_saved`` lit le MÊME marqueur que le balayage.

Test-du-test : remettre ``jour.isoformat()`` (le jour du passage) dans la clé
de ``beat_tasks._marqueur`` ⇒ ``test_trente_passages_une_relance`` rouge.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.automation.beat_tasks import (
    MARQUEUR_PREFIXE, _trigger_facture_overdue, _trigger_maintenance_due,
    _trigger_warranty_expiring,
)
from apps.automation.models import (
    ActionType, AutomationApproval, AutomationRule, AutomationRun, TriggerType,
)
from apps.crm.models import Client
from apps.ventes.models import Facture
from authentication.models import Company


def _jour(n):
    """Patch de l'horloge locale : aujourd'hui + n jours."""
    return mock.patch('django.utils.timezone.localdate',
                      return_value=date.today() + timedelta(days=n))


class MarqueurOccurrenceTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='apar8-co', defaults={'nom': 'APAR8'})
        self.cli = Client.objects.create(
            company=self.co, nom='Cli APAR8', email='apar8@example.invalid')

    def _regle(self, trigger, **extra):
        return AutomationRule.objects.create(
            company=self.co, nom=f'APAR8 {trigger}', trigger_type=trigger,
            trigger_config={}, action_type=ActionType.WAIT, action_config={},
            enabled=True, **extra)

    def _runs(self, rule):
        return AutomationRun.objects.filter(company=self.co, rule=rule).exclude(
            message__startswith=MARQUEUR_PREFIXE)

    def _facture(self, statut='emise'):
        return Facture.objects.create(
            company=self.co, client=self.cli, reference='FAC-APAR8',
            statut=statut, date_echeance=date.today() - timedelta(days=3),
            montant_ttc=Decimal('900'))

    def test_trente_passages_une_relance(self):
        self._facture()
        regle = self._regle(TriggerType.FACTURE_OVERDUE)
        _trigger_facture_overdue(self.co)
        _trigger_facture_overdue(self.co)  # J bis
        for n in range(1, 31):
            with _jour(n):
                _trigger_facture_overdue(self.co)
            self.assertEqual(self._runs(regle).count(), 1, f'J+{n}')

    def test_nouvelle_echeance_relance_une_fois(self):
        facture = self._facture()
        regle = self._regle(TriggerType.FACTURE_OVERDUE)
        _trigger_facture_overdue(self.co)
        Facture.objects.filter(pk=facture.pk).update(
            date_echeance=date.today() - timedelta(days=1))
        _trigger_facture_overdue(self.co)
        _trigger_facture_overdue(self.co)
        self.assertEqual(self._runs(regle).count(), 2)

    def test_signal_puis_balayage_une_seule_relance(self):
        """Changement de statut à 07:00 (signal) puis balayage de 08:05."""
        facture = self._facture(statut='brouillon')
        regle = self._regle(TriggerType.FACTURE_OVERDUE)
        facture.statut = 'emise'
        facture.save()  # le signal tire et pose le marqueur d'occurrence
        self.assertEqual(self._runs(regle).count(), 1)
        _trigger_facture_overdue(self.co)
        self.assertEqual(self._runs(regle).count(), 1)

    def test_maintenance_une_fois_par_visite_due(self):
        from apps.sav.models import ContratMaintenance
        ContratMaintenance.objects.create(
            company=self.co, client=self.cli, actif=True,
            date_debut=date.today() - timedelta(days=400),
            periodicite='annuel')
        regle = self._regle(TriggerType.MAINTENANCE_DUE)
        for n in range(0, 5):
            with _jour(n):
                _trigger_maintenance_due(self.co)
        self.assertEqual(self._runs(regle).count(), 1)

    def test_garantie_une_approbation_par_equipement(self):
        from apps.installations.models import Installation
        from apps.sav.models import Equipement
        from apps.stock.models import Produit
        chantier = Installation.objects.create(
            company=self.co, client=self.cli, reference='CH-APAR8')
        produit = Produit.objects.create(
            company=self.co, nom='Onduleur APAR8', prix_vente=0)
        Equipement.objects.create(
            company=self.co, produit=produit, installation=chantier,
            statut=Equipement.Statut.EN_SERVICE,
            date_fin_garantie=timezone.localdate() + timedelta(days=60))
        self._regle(TriggerType.WARRANTY_EXPIRING, requires_approval=True)
        # Le balayage garantie lit ``date.today()`` : on simule trois jours
        # successifs en rejouant le balayage (la fenêtre reste ouverte).
        for _ in range(3):
            _trigger_warranty_expiring(self.co)
        self.assertEqual(
            AutomationApproval.objects.filter(company=self.co).count(), 1)
