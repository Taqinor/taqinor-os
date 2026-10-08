"""APAR7 — prédicat d'état MÉTIER des déclencheurs temporels.

Constat C-APAR-007 : FACTURE_OVERDUE (signal, balayage, reprise après
approbation) ne regardait que la date d'échéance et ``statut != 'payee'`` :
annuler une facture échue la RELANÇAIT (le signal tirait sur le changement de
statut), un brouillon échu était relancé par le balayage. DATE_ECHEANCE_CHAMP
sur devis demandait « toujours d'actualité ? » à un devis déjà accepté.

Test-du-test : remettre ``.exclude(statut='payee')`` seul dans
``beat_tasks._trigger_facture_overdue`` ⇒ ``test_balayage_*`` redevient rouge.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.automation import engine
from apps.automation.beat_tasks import (
    MARQUEUR_PREFIXE, _trigger_date_echeance_champ, _trigger_facture_overdue,
)
from apps.automation.models import (
    ActionType, AutomationApproval, AutomationRule, AutomationRun, TriggerType,
)
from apps.crm.models import Client
from apps.ventes.models import Devis, Facture
from authentication.models import Company


def _runs_action(company, target_id=None):
    """Runs NON marqueurs (les marqueurs d'idempotence ne sont pas des actions)."""
    qs = AutomationRun.objects.filter(company=company).exclude(
        message__startswith=MARQUEUR_PREFIXE).exclude(
        message__startswith='XPLT3:')
    if target_id is not None:
        qs = qs.filter(target_id=target_id)
    return qs


class PredicatsEtatTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='apar7-co', defaults={'nom': 'APAR7'})
        self.client_obj = Client.objects.create(
            company=self.co, nom='Cli APAR7', email='apar7@example.invalid')
        self.echue = timezone.localdate() - timedelta(days=5)

    def _regle_overdue(self, **extra):
        return AutomationRule.objects.create(
            company=self.co, nom='Relance retard',
            trigger_type=TriggerType.FACTURE_OVERDUE, trigger_config={},
            action_type=ActionType.WAIT, action_config={}, enabled=True,
            **extra)

    def _facture(self, ref, statut, montant='1200'):
        return Facture.objects.create(
            company=self.co, client=self.client_obj, reference=ref,
            statut=statut, date_echeance=self.echue,
            montant_ttc=Decimal(montant))

    # ── FACTURE_OVERDUE ───────────────────────────────────────────────────

    def test_annuler_une_facture_echue_ne_relance_pas(self):
        self._regle_overdue()
        facture = self._facture('FAC-APAR7-120', Facture.Statut.EMISE)
        avant = _runs_action(self.co, facture.pk).count()
        facture.statut = Facture.Statut.ANNULEE
        facture.save()
        self.assertEqual(_runs_action(self.co, facture.pk).count(), avant)

    def test_balayage_ne_cible_que_les_factures_emises_a_reste_du(self):
        # Factures créées AVANT la règle : le signal de création ne tire pas.
        emise = self._facture('FAC-APAR7-E', Facture.Statut.EMISE)
        brouillon = self._facture('FAC-APAR7-44', Facture.Statut.BROUILLON)
        annulee = self._facture('FAC-APAR7-A', Facture.Statut.ANNULEE)
        soldee = self._facture('FAC-APAR7-S', Facture.Statut.EMISE, '0')
        self._regle_overdue()
        self.assertEqual(_trigger_facture_overdue(self.co), 1)
        self.assertEqual(_runs_action(self.co, emise.pk).count(), 1)
        for f in (brouillon, annulee, soldee):
            self.assertEqual(
                AutomationRun.objects.filter(
                    company=self.co, target_id=f.pk,
                    target_model__in=('ventes.facture', 'facturation.facture'),
                ).count(), 0, f.reference)
        # Deuxième passage : la facture émise n'est pas relancée deux fois.
        self.assertEqual(_trigger_facture_overdue(self.co), 0)

    def test_approbation_decidee_sur_facture_payee_entre_temps(self):
        self._regle_overdue(requires_approval=True)
        facture = self._facture('FAC-APAR7-P', Facture.Statut.EMISE)
        _trigger_facture_overdue(self.co)
        approval = AutomationApproval.objects.get(company=self.co)
        Facture.objects.filter(pk=facture.pk).update(
            statut=Facture.Statut.PAYEE)
        engine.run_approved(approval)
        dernier = AutomationRun.objects.filter(
            company=self.co, target_id=facture.pk).order_by('-id').first()
        self.assertEqual(dernier.status, AutomationRun.Status.SKIPPED)
        self.assertIn('Facture soldée', dernier.message)

    def test_predicat_unique(self):
        f = Facture(statut='emise', montant_ttc=Decimal('10'))
        self.assertIsNone(
            engine.motif_etat_metier(TriggerType.FACTURE_OVERDUE, f))
        for statut in ('brouillon', 'annulee', 'payee'):
            f.statut = statut
            self.assertTrue(
                engine.motif_etat_metier(TriggerType.FACTURE_OVERDUE, f))

    # ── DATE_ECHEANCE_CHAMP sur devis ─────────────────────────────────────

    def test_seul_le_devis_envoye_est_relance(self):
        AutomationRule.objects.create(
            company=self.co, nom='J+3',
            trigger_type=TriggerType.DATE_ECHEANCE_CHAMP,
            trigger_config={'model': 'ventes.devis', 'champ': 'date_validite',
                            'offset_jours': 3},
            action_type=ActionType.WAIT, action_config={}, enabled=True)
        cible = timezone.localdate() - timedelta(days=3)
        devis = {}
        for statut in ('accepte', 'refuse', 'brouillon', 'envoye'):
            devis[statut] = Devis.objects.create(
                company=self.co, client=self.client_obj,
                reference=f'DEV-APAR7-{statut}', statut=statut,
                date_validite=cible)
        self.assertEqual(_trigger_date_echeance_champ(self.co), 1)
        cibles = set(_runs_action(self.co).filter(
            rule__trigger_type=TriggerType.DATE_ECHEANCE_CHAMP).values_list(
            'target_id', flat=True))
        self.assertEqual(cibles, {devis['envoye'].pk})


class DateLocaleTests(TestCase):
    """Garde-fou : l'échéance d'aujourd'hui n'est pas « échue »."""

    def test_echeance_du_jour_non_ciblee(self):
        co, _ = Company.objects.get_or_create(
            slug='apar7-co2', defaults={'nom': 'APAR7 bis'})
        client = Client.objects.create(
            company=co, nom='C2', email='apar7b@example.invalid')
        Facture.objects.create(
            company=co, client=client, reference='FAC-APAR7-J',
            statut='emise', date_echeance=date.today() + timedelta(days=1),
            montant_ttc=Decimal('100'))
        self.assertEqual(_trigger_facture_overdue(co), 0)
