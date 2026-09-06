"""AUD822 — idempotence quotidienne des déclencheurs temporels de l'automation.

Défaut corrigé : `beat_tasks._trigger_warranty_expiring` /
`_trigger_maintenance_due` / `_trigger_facture_overdue` bouclaient
QUOTIDIENNEMENT et appelaient `engine.evaluate()` sans vérifier qu'une
évaluation avait déjà eu lieu — contrairement à `_trigger_date_echeance_champ`
(XPLT3) qui posait et vérifiait déjà un marqueur `AutomationRun`. Une facture
impayée depuis 60 jours envoyait donc au client le MÊME email de relance 60
fois (le preset officiel `email_on_facture_overdue` a `requires_approval=False`),
et une règle `CREATE_SAV_TICKET` sur `MAINTENANCE_DUE` créait un ticket SAV par
jour tant que le contrat restait dû.

Test ROUGE d'abord : sur l'arbre d'avant AUD822, deux appels successifs de
`_trigger_facture_overdue` le même jour sur la même facture déclenchaient DEUX
`SEND_EMAIL` (deux mails dans `mail.outbox`).
"""
from datetime import date, timedelta

from django.core import mail
from django.test import TestCase

from apps.automation.beat_tasks import (
    MARQUEUR_PREFIXE, _marqueur, _trigger_facture_overdue,
    _trigger_maintenance_due, _trigger_warranty_expiring, time_triggers_daily,
)
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType,
)
from apps.crm.models import Client
from authentication.models import Company


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class _Base(TestCase):
    def setUp(self):
        self.co = make_company('aud822-co', 'AUD822')

    def _regle(self, trigger_type, action_type=ActionType.CREATE_ACTIVITY,
               action_config=None):
        return AutomationRule.objects.create(
            company=self.co, nom=f'AUD822 {trigger_type}',
            trigger_type=trigger_type, trigger_config={},
            action_type=action_type,
            action_config=action_config or {'body': 'relance'},
            enabled=True)

    def _marqueurs(self):
        return AutomationRun.objects.filter(
            company=self.co, message__startswith=MARQUEUR_PREFIXE)


class FactureOverdueIdempotenceTests(_Base):
    def _facture(self, reference='F-AUD822'):
        from apps.ventes.models import Facture
        client = Client.objects.create(
            company=self.co, nom='Cli822', email='cli822@example.com')
        return Facture.objects.create(
            company=self.co, client=client, reference=reference,
            statut='envoye', date_echeance=date.today() - timedelta(days=30))

    def test_deux_passages_le_meme_jour_ne_declenchent_quune_fois(self):
        self._regle(TriggerType.FACTURE_OVERDUE)
        self._facture()
        self.assertEqual(_trigger_facture_overdue(self.co), 1)
        self.assertEqual(_trigger_facture_overdue(self.co), 0)

    def test_un_seul_email_de_relance_par_jour(self):
        """Le scénario réel : la facture impayée ne spamme plus le client."""
        self._regle(TriggerType.FACTURE_OVERDUE,
                    action_type=ActionType.SEND_EMAIL,
                    action_config={'subject': 'Relance', 'body': 'Bonjour'})
        self._facture()
        mail.outbox = []
        _trigger_facture_overdue(self.co)
        _trigger_facture_overdue(self.co)
        _trigger_facture_overdue(self.co)
        self.assertEqual(len(mail.outbox), 1)

    def test_le_marqueur_porte_le_jour_et_lobjet(self):
        self._regle(TriggerType.FACTURE_OVERDUE)
        facture = self._facture()
        _trigger_facture_overdue(self.co)
        attendu = _marqueur(TriggerType.FACTURE_OVERDUE, 'ventes.facture',
                            facture.pk, date.today())
        marqueur = self._marqueurs().get()
        self.assertTrue(marqueur.message.startswith(attendu))
        self.assertIsNone(marqueur.rule_id)
        self.assertEqual(marqueur.status, AutomationRun.Status.NOOP)

    def test_le_lendemain_la_relance_repart(self):
        """Le marqueur est daté : un NOUVEAU jour redéclenche."""
        self._regle(TriggerType.FACTURE_OVERDUE)
        self._facture()
        _trigger_facture_overdue(self.co)
        # Simule le passage au lendemain en vieillissant le marqueur d'un jour.
        marqueur = self._marqueurs().get()
        hier = (date.today() - timedelta(days=1)).isoformat()
        marqueur.message = marqueur.message.replace(
            date.today().isoformat(), hier)
        marqueur.save(update_fields=['message'])
        self.assertEqual(_trigger_facture_overdue(self.co), 1)

    def test_deux_factures_sont_traitees_independamment(self):
        self._regle(TriggerType.FACTURE_OVERDUE)
        self._facture('F-AUD822-A')
        self._facture('F-AUD822-B')
        self.assertEqual(_trigger_facture_overdue(self.co), 2)
        self.assertEqual(_trigger_facture_overdue(self.co), 0)
        self.assertEqual(self._marqueurs().count(), 2)

    def test_sans_regle_aucun_marqueur_nest_pose(self):
        """Rien à rendre idempotent : le journal des sociétés sans règle reste vide."""
        self._facture()
        self.assertEqual(_trigger_facture_overdue(self.co), 1)
        self.assertEqual(AutomationRun.objects.filter(company=self.co).count(), 0)

    def test_la_tache_beat_complete_est_idempotente(self):
        self._regle(TriggerType.FACTURE_OVERDUE)
        self._facture()
        premier = time_triggers_daily()
        second = time_triggers_daily()
        self.assertGreaterEqual(premier, 1)
        self.assertEqual(second, 0)


class MaintenanceDueIdempotenceTests(_Base):
    def test_un_seul_ticket_sav_par_jour(self):
        from apps.sav.models import ContratMaintenance, Ticket

        self._regle(TriggerType.MAINTENANCE_DUE,
                    action_type=ActionType.CREATE_SAV_TICKET,
                    action_config={'description': 'Visite due'})
        client = Client.objects.create(company=self.co, nom='CliM822')
        ContratMaintenance.objects.create(
            company=self.co, client=client, actif=True,
            date_debut=date.today() - timedelta(days=400),
            periodicite='annuel')
        self.assertEqual(_trigger_maintenance_due(self.co), 1)
        self.assertEqual(_trigger_maintenance_due(self.co), 0)
        self.assertEqual(Ticket.objects.filter(company=self.co).count(), 1)


class WarrantyExpiringIdempotenceTests(_Base):
    def test_deux_passages_le_meme_jour_ne_declenchent_quune_fois(self):
        from apps.installations.models import Installation
        from apps.sav.models import Equipement
        from apps.stock.models import Produit

        self._regle(TriggerType.WARRANTY_EXPIRING)
        client = Client.objects.create(company=self.co, nom='CliW822')
        chantier = Installation.objects.create(
            company=self.co, client=client, reference='CH-AUD822')
        produit = Produit.objects.create(
            company=self.co, nom='Onduleur 822', prix_vente=0)
        Equipement.objects.create(
            company=self.co, produit=produit, installation=chantier,
            statut=Equipement.Statut.EN_SERVICE,
            date_fin_garantie=date.today() + timedelta(days=30))
        self.assertEqual(_trigger_warranty_expiring(self.co), 1)
        self.assertEqual(_trigger_warranty_expiring(self.co), 0)
