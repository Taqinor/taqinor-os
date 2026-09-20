"""AUTOMATION-TRIGGERS — quatre TriggerType de plus (NTP2P38, NTI18N43,
NTWFL18), abonnés au BUS ``core.events``, même patron que ``DEVIS_ACCEPTED``
(AUD823, voir ``test_aud823_devis_accepted_bus.py``) : jamais un post_save
brut, l'émission est déjà gardée par le service propriétaire.

Test LÉGER : vérifie le câblage (dispatch_uid connecté + un
``AutomationRun`` journalisé par déclenchement), pas la logique métier des
émetteurs (déjà testée où ``emettre_demande_achat_approuvee``/
``marquer_rfq_attribuee``/``core.dossiers.notifier_echeances_depassees``
sont définis)."""
from django.test import TestCase

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType,
)
from authentication.models import Company
from core.events import (
    demande_achat_approuvee, dossier_echeance_depassee, langue_changed,
    rfq_attribuee,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class _Minimal:
    """Un jeton d'objet métier : le point testé est le câblage du signal au
    moteur, pas un modèle réel (``evaluate``/``_log_run`` restent robustes à
    une instance sans ``_meta``)."""

    def __init__(self, pk=1):
        self.pk = pk


class AutomationTriggersBusTests(TestCase):
    def setUp(self):
        self.co = make_company('at-triggers-co', 'AT Triggers Co')

    def _rule(self, trigger_type, nom):
        return AutomationRule.objects.create(
            company=self.co, nom=nom, trigger_type=trigger_type,
            trigger_config={}, action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'x'}, enabled=True)

    def _runs(self, rule):
        return AutomationRun.objects.filter(company=self.co, rule=rule)

    def test_demande_achat_approuvee_declenche_une_regle(self):
        rule = self._rule(
            TriggerType.DEMANDE_ACHAT_APPROUVEE, "DA approuvée")
        demande_achat_approuvee.send(
            sender='x', demande=_Minimal(), company=self.co, user=None,
            montant_estime=1000)
        self.assertEqual(self._runs(rule).count(), 1)

    def test_rfq_attribuee_declenche_une_regle(self):
        rule = self._rule(TriggerType.RFQ_ATTRIBUEE, 'RFQ attribuée')
        rfq_attribuee.send(
            sender='x', rfq=_Minimal(), offre=_Minimal(pk=2),
            company=self.co, user=None, bon_commande_id=5)
        self.assertEqual(self._runs(rule).count(), 1)

    def test_langue_changed_declenche_une_regle(self):
        rule = self._rule(TriggerType.LANGUE_CHANGED, 'Langue changée')
        langue_changed.send(
            sender='x', company=self.co, portee='client', client_id=7,
            ancienne_langue='fr', nouvelle_langue='ar', user=None)
        self.assertEqual(self._runs(rule).count(), 1)

    def test_dossier_echeance_depassee_declenche_une_regle(self):
        rule = self._rule(
            TriggerType.DOSSIER_ECHEANCE_DEPASSEE, 'Dossier en retard')
        dossier_echeance_depassee.send(
            sender='x', dossier=_Minimal(), company=self.co,
            proprietaire=None)
        self.assertEqual(self._runs(rule).count(), 1)

    def test_un_evenement_sans_societe_est_ignore(self):
        rule = self._rule(
            TriggerType.DEMANDE_ACHAT_APPROUVEE, "DA approuvée bis")
        demande_achat_approuvee.send(
            sender='x', demande=_Minimal(), company=None, user=None,
            montant_estime=None)
        self.assertEqual(self._runs(rule).count(), 0)

    def test_les_quatre_declencheurs_sont_abonnes_au_bus(self):
        cas = [
            (demande_achat_approuvee,
             'automation_on_demande_achat_approuvee'),
            (rfq_attribuee, 'automation_on_rfq_attribuee'),
            (langue_changed, 'automation_on_langue_changed'),
            (dossier_echeance_depassee,
             'automation_on_dossier_echeance_depassee'),
        ]
        for signal, uid in cas:
            uids = [entree[0][0] for entree in signal.receivers]
            self.assertIn(
                uid, uids, f'{uid} non câblé (récepteurs : {uids}).')
