"""CRX20 — plus aucun chemin d'étape « muet ».

Constat de l'audit L3 du 02/09 : trois points d'entrée déplaçaient
``Lead.stage`` par une affectation nue suivie d'un ``save()``, sans passer par
l'émetteur ``core.events.lead_stage_changed`` :

  * l'action en masse ``set_stage`` (``crm.services.apply_bulk_action``) ;
  * l'ouverture publique du devis (``avancer_stage_sur_ouverture_devis``) ;
  * l'expiration des devis (``ventes.domain.recouvrement._advance_lead_on_expiry``).

Conséquence RÉELLE : les deux abonnés du signal — génération des tâches de
playbook (NTCRM12, ``crm.receivers``) et inscription aux séquences de relance
(XMKT1/PACT161, ``compta.receivers``) — partaient pour un PATCH unitaire mais
JAMAIS pour un bulk, une ouverture de devis ou une expiration. Ce module
vérifie les récepteurs de bout en bout (jamais un simple assert sur le signal
pour le bulk : c'est l'effet métier qui manquait).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.compta.models import InscriptionSequence, SequenceRelance
from apps.crm import stages
from apps.crm.models import (
    Lead, LeadPlaybookProgress, Playbook, PlaybookEtape, PlaybookTache,
)
from apps.crm.services import apply_bulk_action, avancer_stage_sur_ouverture_devis
from apps.roles.models import Role
from authentication.models import Company
from core.events import lead_stage_changed

User = get_user_model()


def brancher_capture(test_case):
    """Branche un collecteur d'émissions ``lead_stage_changed`` sur la durée du
    test (déconnexion garantie par ``addCleanup``) et renvoie la liste, qui se
    remplit au fil des émissions. Même patron que ``tests_odoo_sync.py``."""
    emissions = []

    def _capture(sender, lead, old_stage, new_stage, user, **kwargs):
        emissions.append(
            {'lead': lead.pk, 'old': old_stage, 'new': new_stage, 'user': user})

    lead_stage_changed.connect(_capture, weak=False)
    test_case.addCleanup(lead_stage_changed.disconnect, _capture)
    return emissions


class BulkSetStageEmetLesEffetsTests(TestCase):
    """Le bulk ``set_stage`` déclenche playbook ET séquence de relance."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX20 bulk', slug='taqinor-crx20-bulk')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial CRX20',
            permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_crx20_bulk', password='x', company=self.company,
            role=self.role)
        # Abonné n°1 : playbook NTCRM12 sur QUOTE_SENT.
        self.playbook = Playbook.objects.create(
            company=self.company, nom='Playbook CRX20', actif=True)
        self.etape = PlaybookEtape.objects.create(
            playbook=self.playbook, stage=stages.QUOTE_SENT, ordre=1)
        self.tache = PlaybookTache.objects.create(
            etape=self.etape, libelle='Appeler le client', obligatoire=True,
            ordre=1)
        # Abonné n°2 : séquence de relance XMKT1 sur QUOTE_SENT.
        self.sequence = SequenceRelance.objects.create(
            company=self.company, nom='Relance CRX20',
            stage_declencheur=stages.QUOTE_SENT, actif=True)
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead CRX20 bulk', stage=stages.NEW)

    def _bulk_vers_quote_sent(self):
        return apply_bulk_action(
            company=self.company, user=self.user, lead_ids=[self.lead.pk],
            op='set_stage', params={'stage': stages.QUOTE_SENT})

    def test_bulk_set_stage_ecrit_bien_l_etape(self):
        resume = self._bulk_vers_quote_sent()
        self.assertEqual(resume['updated'], 1, resume)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)

    def test_bulk_set_stage_genere_les_taches_de_playbook(self):
        self._bulk_vers_quote_sent()
        self.assertEqual(
            LeadPlaybookProgress.objects.filter(
                lead=self.lead, tache=self.tache).count(),
            1)

    def test_bulk_set_stage_inscrit_a_la_sequence_de_relance(self):
        self._bulk_vers_quote_sent()
        inscription = InscriptionSequence.objects.filter(
            company=self.company, sequence=self.sequence,
            lead_id=self.lead.pk).first()
        self.assertIsNotNone(inscription)
        self.assertEqual(inscription.statut, InscriptionSequence.Statut.ACTIF)

    def test_bulk_set_stage_emet_le_signal_avec_l_utilisateur(self):
        emissions = brancher_capture(self)

        self._bulk_vers_quote_sent()

        self.assertEqual(len(emissions), 1, emissions)
        emission = emissions[0]
        self.assertEqual(emission['lead'], self.lead.pk)
        self.assertEqual(emission['old'], stages.NEW)
        self.assertEqual(emission['new'], stages.QUOTE_SENT)
        self.assertEqual(emission['user'], self.user)

    def test_bulk_ignore_n_emet_rien(self):
        """Un lead déjà à l'étape cible est « unchanged » : aucune émission."""
        self.lead.stage = stages.QUOTE_SENT
        self.lead.save(update_fields=['stage'])
        emissions = brancher_capture(self)

        resume = self._bulk_vers_quote_sent()

        self.assertEqual(resume['updated'], 0, resume)
        self.assertEqual(emissions, [])


class OuvertureDevisEmetLeSignalTests(TestCase):
    """YLEAD10 — l'ouverture publique du devis passe par le canon CRX20."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX20 ouverture', slug='taqinor-crx20-ouverture')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead CRX20 ouverture',
            stage=stages.QUOTE_SENT)

    def test_avance_emet_le_signal(self):
        emissions = brancher_capture(self)

        self.assertTrue(avancer_stage_sur_ouverture_devis(self.lead))

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.FOLLOW_UP)
        self.assertEqual(len(emissions), 1, emissions)
        self.assertEqual(emissions[0]['old'], stages.QUOTE_SENT)
        self.assertEqual(emissions[0]['new'], stages.FOLLOW_UP)
        # Chemin système : aucun utilisateur derrière une ouverture publique.
        self.assertIsNone(emissions[0]['user'])

    def test_seconde_ouverture_n_emet_pas_deux_fois(self):
        avancer_stage_sur_ouverture_devis(self.lead)
        emissions = brancher_capture(self)

        self.assertFalse(avancer_stage_sur_ouverture_devis(self.lead))
        self.assertEqual(emissions, [])


class ExpirationDevisEmetLeSignalTests(TestCase):
    """``ventes.domain.recouvrement`` : les deux avances passent par le canon
    et n'écrivent plus aucun littéral d'étape (règle #2)."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX20 expiration', slug='taqinor-crx20-expiration')

    def _avancer(self, lead):
        from datetime import timedelta

        from django.utils import timezone

        from apps.ventes.domain.recouvrement import _advance_lead_on_expiry

        # `today` très postérieur : garantit l'absence d'activité « récente ».
        return _advance_lead_on_expiry(
            lead, today=timezone.localdate() + timedelta(days=365))

    def test_quote_sent_vers_follow_up_emet_le_signal(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead expiré QS', stage=stages.QUOTE_SENT)
        emissions = brancher_capture(self)

        moved_fup, moved_cold = self._avancer(lead)

        self.assertTrue(moved_fup)
        self.assertFalse(moved_cold)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)
        self.assertEqual(len(emissions), 1, emissions)
        self.assertEqual(emissions[0]['new'], stages.FOLLOW_UP)

    def test_follow_up_vers_cold_emet_le_signal(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead expiré FU', stage=stages.FOLLOW_UP)
        emissions = brancher_capture(self)

        moved_fup, moved_cold = self._avancer(lead)

        self.assertFalse(moved_fup)
        self.assertTrue(moved_cold)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.COLD)
        self.assertEqual(len(emissions), 1, emissions)
        self.assertEqual(emissions[0]['new'], stages.COLD)

    def test_lead_perdu_intouche(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead perdu', stage=stages.QUOTE_SENT,
            perdu=True)
        emissions = brancher_capture(self)

        self.assertEqual(self._avancer(lead), (False, False))
        self.assertEqual(emissions, [])
