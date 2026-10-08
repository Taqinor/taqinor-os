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
from decimal import Decimal

from unittest import mock

from django.core import mail
from django.test import TestCase
from django.utils import timezone

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
        # CRX24 — email unique (insensible à la casse) par société : deux
        # appels de cette factory (test_deux_factures_sont_traitees_
        # independamment en crée deux) ne peuvent plus partager le même
        # e-mail de client, sinon IntegrityError sur
        # crx24_client_email_unique_ci. Dérivé de `reference`, qui varie déjà
        # à chaque appel dans ce fichier.
        email = f'{reference.lower().replace(" ", "-")}@example.com'
        client = Client.objects.create(
            company=self.co, nom='Cli822', email=email)
        return Facture.objects.create(
            company=self.co, client=client, reference=reference,
            statut='emise', montant_ttc=Decimal('1000'),  # APAR7 — relançable
            date_echeance=date.today() - timedelta(days=30))

    def test_deux_passages_le_meme_jour_ne_declenchent_quune_fois(self):
        # APAR8 — facture créée AVANT la règle : le signal de création (qui
        # partage désormais le marqueur) ne la consomme pas.
        self._facture()
        self._regle(TriggerType.FACTURE_OVERDUE)
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

    def test_le_marqueur_porte_lecheance_et_lobjet(self):
        """APAR8 — la clé est l'ÉCHÉANCE (occurrence métier), pas le jour."""
        facture = self._facture()
        self._regle(TriggerType.FACTURE_OVERDUE)
        _trigger_facture_overdue(self.co)
        attendu = _marqueur(TriggerType.FACTURE_OVERDUE, 'ventes.facture',
                            facture.pk, facture.date_echeance)
        marqueur = self._marqueurs().get()
        self.assertTrue(marqueur.message.startswith(attendu))
        self.assertIsNone(marqueur.rule_id)
        self.assertEqual(marqueur.status, AutomationRun.Status.NOOP)

    def test_le_lendemain_aucune_relance_pour_la_meme_echeance(self):
        """APAR8 — réécrit EXPLICITEMENT : ce test figeait le défaut (« le
        lendemain la relance repart » = un e-mail par jour). Le marqueur est
        clé sur l'échéance : le lendemain, même échéance ⇒ 0 relance ; une
        NOUVELLE échéance (facture rééchelonnée) relance une fois."""
        facture = self._facture()
        self._regle(TriggerType.FACTURE_OVERDUE)
        self.assertEqual(_trigger_facture_overdue(self.co), 1)
        with mock.patch('django.utils.timezone.localdate',
                        return_value=timezone.localdate() + timedelta(days=1)):
            self.assertEqual(_trigger_facture_overdue(self.co), 0)
        from apps.ventes.models import Facture
        Facture.objects.filter(pk=facture.pk).update(
            date_echeance=date.today() - timedelta(days=2))
        self.assertEqual(_trigger_facture_overdue(self.co), 1)

    def test_deux_factures_sont_traitees_independamment(self):
        self._facture('F-AUD822-A')
        self._facture('F-AUD822-B')
        self._regle(TriggerType.FACTURE_OVERDUE)
        self.assertEqual(_trigger_facture_overdue(self.co), 2)
        self.assertEqual(_trigger_facture_overdue(self.co), 0)
        self.assertEqual(self._marqueurs().count(), 2)

    def test_sans_regle_aucun_marqueur_nest_pose(self):
        """Rien à rendre idempotent : le journal des sociétés sans règle reste vide."""
        self._facture()
        self.assertEqual(_trigger_facture_overdue(self.co), 1)
        self.assertEqual(AutomationRun.objects.filter(company=self.co).count(), 0)

    def test_la_tache_beat_complete_est_idempotente(self):
        self._facture()
        self._regle(TriggerType.FACTURE_OVERDUE)
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
