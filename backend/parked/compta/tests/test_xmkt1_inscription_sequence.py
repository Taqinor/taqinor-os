"""PACT161 — le moteur de séquences (XMKT1) inscrit RÉELLEMENT un lead.

Constat qui a motivé la tâche : ``inscrire_leads_pour_stage``
(``apps/compta/services.py``) n'avait aucun appelant hors tests ;
``apps/compta/receivers.py`` n'avait aucun abonnement au changement d'étape
pipeline ; ``executer_sequences_relance_task`` n'exécute que des
``InscriptionSequence`` DÉJÀ créées — qui n'existaient donc jamais en
production. Une séquence active pouvait exister, être « cochée » construite,
et ne jamais s'exécuter faute de participant.

Ce module vérifie l'INTÉGRATION réelle : PATCH ``crm.Lead.stage`` via l'API
(comme ``crm/tests_ntcrm12_playbooks.py``) → signal ``core.events.
lead_stage_changed`` → récepteur ``compta.receivers.
_inscrire_sequences_on_lead_stage_changed`` → ``InscriptionSequence`` créée.
Jamais un appel direct à ``inscrire_leads_pour_stage`` (ça, c'est déjà
couvert par les tests unitaires XMKT1 existants) : c'est précisément le
signal→inscription qui manquait.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.compta.models import InscriptionSequence, SequenceRelance
from apps.crm import stages
from apps.crm.models import Lead
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()


class InscriptionSequenceSurChangementStageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor PACT161', slug='taqinor-pact161')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial PACT161',
            permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_pact161', password='x', company=self.company,
            role=self.role)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)
        self.sequence = SequenceRelance.objects.create(
            company=self.company, nom='Relance devis envoyé',
            stage_declencheur=stages.QUOTE_SENT, actif=True)
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead PACT161', stage=stages.NEW)

    def test_changement_de_stage_via_api_inscrit_le_lead_a_la_sequence_active(self):
        resp = self.client_api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'stage': stages.QUOTE_SENT})
        self.assertEqual(resp.status_code, 200, resp.data)

        inscription = InscriptionSequence.objects.filter(
            company=self.company, sequence=self.sequence,
            lead_id=self.lead.pk).first()
        self.assertIsNotNone(inscription)
        self.assertEqual(inscription.statut, InscriptionSequence.Statut.ACTIF)
        self.assertEqual(inscription.lead_reference, 'Lead PACT161')

    def test_changement_de_stage_rejoue_ne_duplique_pas_l_inscription(self):
        self.client_api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'stage': stages.QUOTE_SENT})
        self.lead.stage = stages.NEW
        self.lead.save(update_fields=['stage'])
        self.client_api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'stage': stages.QUOTE_SENT})

        self.assertEqual(
            InscriptionSequence.objects.filter(
                company=self.company, sequence=self.sequence,
                lead_id=self.lead.pk).count(),
            1)

    def test_sequence_inactive_n_inscrit_personne(self):
        self.sequence.actif = False
        self.sequence.save(update_fields=['actif'])

        resp = self.client_api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'stage': stages.QUOTE_SENT})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            InscriptionSequence.objects.filter(
                company=self.company, lead_id=self.lead.pk).exists())

    def test_changement_vers_une_etape_sans_sequence_n_inscrit_personne(self):
        resp = self.client_api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'stage': stages.COLD})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            InscriptionSequence.objects.filter(
                company=self.company, lead_id=self.lead.pk).exists())

    def test_autre_societe_n_est_jamais_inscrite(self):
        """Isolation multi-tenant : une séquence d'une AUTRE société, même
        déclenchée sur la même étape, ne doit jamais inscrire ce lead."""
        autre_company = Company.objects.create(
            nom='Autre Co PACT161', slug='autre-co-pact161')
        SequenceRelance.objects.create(
            company=autre_company, nom='Relance autre société',
            stage_declencheur=stages.QUOTE_SENT, actif=True)

        self.client_api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'stage': stages.QUOTE_SENT})

        self.assertFalse(
            InscriptionSequence.objects.filter(
                company=autre_company, lead_id=self.lead.pk).exists())
        self.assertEqual(
            InscriptionSequence.objects.filter(lead_id=self.lead.pk).count(),
            1)
