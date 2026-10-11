"""NTDMO12/WIR59 — auto-complétion des items via le bus core.events."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core.events import (
    devis_sent, facture_payee, intervention_completed, workflow_etape_activee,
)
from apps.onboarding.models import OnboardingChecklistItem, OnboardingProgress

User = get_user_model()


class _FakeDevis:
    """Stub porteur des attributs lus par le récepteur (pas un modèle)."""
    def __init__(self, company):
        self.company = company
        self.pk = 1


class _FakeFacture:
    def __init__(self, company, created_by):
        self.company = company
        self.created_by = created_by


class _FakeIntervention:
    def __init__(self):
        self.pk = 1


class OnboardingAutoCompleteTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Co', slug='co-ac')
        self.user = User.objects.create_user(
            'u', password='x', company=self.company)

    def _is_done(self, key):
        item = OnboardingChecklistItem.objects.get(key=key)
        p = OnboardingProgress.objects.filter(
            company=self.company, user=self.user, item=item).first()
        return bool(p and p.complete_le)

    # NB : ``send_robust`` isole le récepteur onboarding — les autres apps
    # (crm/notifications) écoutent aussi ces événements et lisent des attributs
    # (``devis.statut``/``facture.reference``) absents de ces stubs légers ;
    # ``send`` propagerait leur AttributeError alors qu'en prod l'objet réel
    # les porte. Le récepteur onboarding, lui, est déjà best-effort.
    def test_devis_sent_auto_completes_premier_devis(self):
        self.assertFalse(self._is_done('premier_devis'))
        devis_sent.send_robust(
            sender=None, devis=_FakeDevis(self.company), user=self.user,
            ancien_statut='brouillon')
        self.assertTrue(self._is_done('premier_devis'))

    def test_facture_payee_auto_completes_premier_paiement(self):
        facture_payee.send_robust(
            sender=None,
            instance=_FakeFacture(self.company, self.user),
            company=self.company)
        self.assertTrue(self._is_done('premier_paiement'))

    def test_idempotent_no_double_complete(self):
        d = _FakeDevis(self.company)
        devis_sent.send_robust(sender=None, devis=d, user=self.user,
                               ancien_statut='brouillon')
        devis_sent.send_robust(sender=None, devis=d, user=self.user,
                               ancien_statut='brouillon')
        item = OnboardingChecklistItem.objects.get(key='premier_devis')
        self.assertEqual(OnboardingProgress.objects.filter(
            user=self.user, item=item).count(), 1)

    # WIR59 — premier_chantier gagne un event_key réel ('chantier'), câblé sur
    # intervention_completed (apps.installations, YSERV2) : jusqu'ici cet item
    # ne se complétait JAMAIS (aucun event_key), seul « Ignorer » le masquait.
    def test_intervention_completed_auto_completes_premier_chantier(self):
        self.assertEqual(
            OnboardingChecklistItem.objects.get(key='premier_chantier')
            .event_key, 'chantier')
        self.assertFalse(self._is_done('premier_chantier'))
        intervention_completed.send_robust(
            sender=None, intervention=_FakeIntervention(),
            company=self.company, user=self.user)
        self.assertTrue(self._is_done('premier_chantier'))

    def test_intervention_completed_tolerates_missing_user(self):
        # ``user`` peut être None (action système) — best-effort, ne lève pas.
        intervention_completed.send_robust(
            sender=None, intervention=_FakeIntervention(),
            company=self.company, user=None)
        self.assertFalse(self._is_done('premier_chantier'))


# ═══════════════════════════════════════════════════════════════════════════
# APAR48 — abonnés annexes du bus en point de sauvegarde (@abonne_best_effort)
# ═══════════════════════════════════════════════════════════════════════════
# APAR48 (C-APAR-011) — tout abonné ANNEXE du bus porte
# ``@abonne_best_effort`` (``core.events``) : une panne SQL injectée dans l'un
# d'eux est journalisée (``logger.exception``) et n'empêche plus l'encaissement
# d'une facture, la clôture d'une intervention ni l'activation d'une étape BPM ;
# les autres abonnés du même signal ont tourné.
#
# Les abonnés sont DÉCOUVERTS sur les signaux réels (``_live_receivers``) de
# ``facture_payee``, ``intervention_completed`` et ``workflow_etape_activee`` :
# chacun doit être soit best-effort (classé dans ``BEST_EFFORT`` avec la cible de
# sa panne), soit nommé dans ``OBLIGATOIRES``. Aujourd'hui aucun abonné de ces
# trois signaux n'est obligatoire (le lettrage compta de ``facture_payee`` est
# parqué : ``apps/compta`` n'a plus de récepteur).
#
# Doublure DÉCLARÉE : seule la fonction fautive appelée par l'abonné est
# remplacée par une vraie erreur base (``SELECT 1/0``) ; signaux, émetteurs et
# autres abonnés sont réels.
#
# Test-du-test : retirer ``@abonne_best_effort`` d'un abonné ⇒ son cas lève
# (transaction interrompue) et ``test_abonnes_decouverts_et_classes`` échoue.

#: abonné best-effort → (scénario, cible de la panne injectée).
BEST_EFFORT = {
    'apps.onboarding.receivers._complete_on_facture_payee':
        ('paiement', 'apps.onboarding.receivers.completer_par_evenement'),
    'apps.notifications.signals.facture_payee_receiver':
        ('paiement', 'apps.notifications.signals.notify'),
    'apps.onboarding.receivers._complete_on_intervention_completed':
        ('intervention', 'apps.onboarding.receivers.completer_par_evenement'),
    'apps.sav.receivers._avancer_ticket_on_intervention_completed':
        ('intervention', 'apps.sav.services.appliquer_transition_ticket'),
    'apps.notifications.signals.workflow_etape_activee_receiver':
        ('workflow', 'apps.notifications.signals.notify'),
}

#: abonnés OBLIGATOIRES de ces trois signaux — une erreur y annule l'action.
OBLIGATOIRES = ()

#: abonnés best-effort des signaux stock/BC (installations) — marqueur exigé.
INSTALLATIONS_BEST_EFFORT = (
    '_provisionner_gr_ir_on_reception',
    '_peupler_series_entrepot_on_reception',
    '_reserver_stock_chantier_on_reception',
    '_extourner_gr_ir_on_reception_annulee',
    '_retourner_series_on_reception_annulee',
    '_replafonner_reservation_on_reception_annulee',
    '_rattacher_chantier_on_bon_commande_cree',
    '_lettrer_gr_ir_on_facture',
)


def _panne_sql(*args, **kwargs):
    """Une vraie erreur base : la transaction en cours est interrompue."""
    with connection.cursor() as curseur:
        curseur.execute('SELECT 1/0')


def _abonnes(signal):
    vivants = signal._live_receivers(None)
    if isinstance(vivants, tuple):  # Django 5 : (sync, async)
        vivants = list(vivants[0]) + list(vivants[1])
    return {
        f'{r.__module__}.{r.__qualname__}': r for r in vivants
        if r.__module__.startswith(('apps.', 'core.'))
        and 'test' not in r.__module__
    }


class AbonnesBusPointDeSauvegardeTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='apar48-co', defaults={'nom': 'APAR48 Co'})
        self.admin = User.objects.create_user(
            username='apar48_admin', password='x', role_legacy='admin',
            company=self.company)
        from apps.crm.models import Client
        self.client_obj = Client.objects.create(
            company=self.company, nom='APAR48', prenom='Client',
            email='apar48@example.invalid')
        self.n = 0

    # ── scénarios réels ────────────────────────────────────────────────────
    def _paiement(self):
        """Encaissement réel d'une facture émise (service unique)."""
        from apps.ventes.domain.encaissements import (
            affecter_encaissement_groupe,
        )
        from apps.ventes.models import Facture, Paiement
        self.n += 1
        ttc = Decimal('1200')
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-APAR48-{self.n:04d}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=ttc,
            created_by=self.admin)
        affecter_encaissement_groupe(
            company=self.company, client=self.client_obj, montant=ttc,
            mode='virement', date_paiement=timezone.localdate(),
            user=self.admin, factures=[facture])
        # CLAUSE PERSISTANCE : relecture possible (transaction saine).
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertTrue(Paiement.objects.filter(facture=facture).exists())

    def _intervention(self):
        """Clôture réelle d'une intervention liée à un ticket SAV."""
        from apps.installations.models import Installation, Intervention
        from apps.installations.services import changer_statut_intervention
        from apps.sav.models import Ticket
        self.n += 1
        inst = Installation.objects.create(
            company=self.company, reference=f'CHT-APAR48-{self.n}',
            client=self.client_obj)
        ticket = Ticket.objects.create(
            company=self.company, reference=f'SAV-APAR48-{self.n}',
            client=self.client_obj, installation=inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.EN_COURS,
            created_by=self.admin)
        interv = Intervention.objects.create(
            company=self.company, installation=inst, ticket=ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.SUR_SITE, created_by=self.admin)
        changer_statut_intervention(
            interv, Intervention.Statut.TERMINEE, self.admin)
        interv.refresh_from_db()
        self.assertEqual(interv.statut, Intervention.Statut.TERMINEE)
        self.assertIsNotNone(interv.cloturee_notifiee_le)

    def _workflow(self):
        """Démarrage réel d'un workflow BPM (étape manuelle activée)."""
        from core import workflow
        from core.models import WorkflowDefinition, WorkflowStepDefinition
        self.n += 1
        wf = WorkflowDefinition.objects.create(
            company=self.company, code=f'apar48-{self.n}', nom='APAR48')
        WorkflowStepDefinition.objects.create(
            definition=wf, ordre=1, nom='Validation')
        instance = workflow.demarrer_workflow(wf, self.company, self.company)
        instance.refresh_from_db()
        self.assertEqual(instance.etape_courante, 1)
        self.assertTrue(instance.step_instances.filter(ordre=1).exists())

    # ── tests ──────────────────────────────────────────────────────────────
    def test_abonnes_decouverts_et_classes(self):
        for signal in (facture_payee, intervention_completed,
                       workflow_etape_activee):
            for nom, recepteur in _abonnes(signal).items():
                with self.subTest(abonne=nom):
                    if nom in OBLIGATOIRES:
                        continue
                    self.assertIn(nom, BEST_EFFORT,
                                  f'abonné non classé : {nom}')
                    self.assertTrue(
                        getattr(recepteur, 'abonne_best_effort', False),
                        f'{nom} sans @abonne_best_effort')
        tous = set()
        for signal in (facture_payee, intervention_completed,
                       workflow_etape_activee):
            tous |= set(_abonnes(signal))
        for nom in BEST_EFFORT:
            self.assertIn(nom, tous)

    def test_abonnes_installations_marques(self):
        from apps.installations import receivers
        for nom in INSTALLATIONS_BEST_EFFORT:
            with self.subTest(abonne=nom):
                self.assertTrue(getattr(
                    getattr(receivers, nom), 'abonne_best_effort', False))

    def test_panne_isolee_par_abonne(self):
        for abonne, (scenario, cible) in sorted(BEST_EFFORT.items()):
            # Les AUTRES abonnés best-effort du même scénario sont espionnés
            # (comportement réel conservé) : ils doivent avoir tourné.
            autres = sorted({
                c for a, (s, c) in BEST_EFFORT.items()
                if s == scenario and c != cible})
            with self.subTest(abonne=abonne):
                espions = []
                with mock.patch(cible, side_effect=_panne_sql), \
                        self.assertLogs('core.events', 'ERROR') as journal:
                    patchs = [mock.patch(c, wraps=_resoudre(c))
                              for c in autres]
                    for p in patchs:
                        espions.append(p.start())
                    try:
                        getattr(self, f'_{scenario}')()
                    finally:
                        for p in patchs:
                            p.stop()
                self.assertTrue(any(abonne in ligne
                                    for ligne in journal.output),
                                journal.output)
                for espion in espions:
                    self.assertTrue(espion.called)

    def test_sans_panne_inchange(self):
        self._paiement()
        self._intervention()
        self._workflow()


def _resoudre(chemin):
    """Objet réel désigné par ``module.attribut`` (pour ``wraps=``)."""
    import importlib
    module, attribut = chemin.rsplit('.', 1)
    return getattr(importlib.import_module(module), attribut)
