"""ADEV63 (D-ADEV-5 = (a)) — la signature du devis d'un lead PERDU lève
« Perdu » (entrée de chatter « relevé de Perdu : devis signé … ») et passe
le lead à Signé.

Sonde VA p5 d'origine : ``HTTP 200 | perdu True | stage CONTACTED |
chantier True``. Geste réel : l'acceptation par l'API (signal
``devis_accepted``), aucun mock.

Test-du-test : retirer ``_lever_perdu_sur_signature`` du récepteur ⇒
``test_signature_leve_perdu`` échoue (perdu reste vrai, étape CONTACTED).

Run :
    docker compose exec django_core python manage.py test \
        apps.crm.tests_adev63_signature_lead_perdu -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

import apps.crm.stages as stages
from apps.crm.models import Client, Lead, LeadActivity
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class SignatureLeadPerduTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ADEV63', slug='taqinor-adev63')
        self.user = User.objects.create_user(
            username='adev63-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Perdu',
            email='perdu63@example.com', telephone='+212600006363')

    def _devis(self, *, perdu, num):
        lead = Lead.objects.create(
            company=self.company, nom=f'Lead {num}', stage=stages.CONTACTED,
            perdu=perdu, motif_perte='Prix' if perdu else None)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{6300 + num}',
            client=self.client_obj, lead=lead,
            statut=Devis.Statut.ENVOYE, date_envoi=timezone.now(),
            taux_tva=Decimal('20'))
        return lead, devis

    def _accepter(self, devis):
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'M. Client'}, format='json')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))

    def test_signature_leve_perdu(self):
        lead, devis = self._devis(perdu=True, num=1)
        self._accepter(devis)
        lead.refresh_from_db()
        self.assertFalse(lead.perdu)
        self.assertEqual(lead.stage, stages.SIGNED)
        notes = LeadActivity.objects.filter(
            lead=lead, body__contains='relevé de Perdu : devis signé')
        self.assertEqual(notes.count(), 1)
        self.assertIn(devis.reference, notes.first().body)

    def test_signature_desarchive_le_lead(self):
        """ASUP49 — le lead ARCHIVÉ d'un devis signé est désarchivé (3 champs),
        passe Signé, avec UNE entrée ; non archivé ou second accepté : rien."""
        from apps.crm.selectors import est_lead_signe
        lead, devis = self._devis(perdu=False, num=3)
        Lead.objects.filter(pk=lead.pk).update(
            is_archived=True, archived_by=self.user, archived_at=timezone.now())
        self._accepter(devis)
        lead.refresh_from_db()
        self.assertEqual((lead.is_archived, lead.archived_by, lead.archived_at),
                         (False, None, None))
        self.assertEqual(lead.stage, stages.SIGNED)
        self.assertTrue(est_lead_signe(lead))
        notes = LeadActivity.objects.filter(lead=lead, body__contains='désarchivé : devis signé')
        self.assertEqual([n.body for n in notes], [f'désarchivé : devis signé {devis.reference}'])
        self.assertIn(lead, Lead.objects.filter(is_archived=False))
        from apps.crm.receivers import _avancer_stage_on_devis_accepted
        Lead.objects.filter(pk=lead.pk).update(is_archived=True)
        devis.refresh_from_db()  # second accepté sans changement de statut : rien
        _avancer_stage_on_devis_accepted(None, devis=devis, user=self.user, ancien_statut=devis.statut)
        self.assertTrue(Lead.objects.get(pk=lead.pk).is_archived)
        autre, devis2 = self._devis(perdu=False, num=4)
        self._accepter(devis2)
        self.assertEqual(LeadActivity.objects.filter(
            lead__in=[lead, autre], body__contains='désarchivé').count(), 1)

    def test_lead_non_perdu_sans_entree(self):
        lead, devis = self._devis(perdu=False, num=2)
        self._accepter(devis)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.SIGNED)
        self.assertFalse(LeadActivity.objects.filter(
            lead=lead, body__contains='relevé de Perdu').exists())
