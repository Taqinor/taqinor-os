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

    def test_lead_non_perdu_sans_entree(self):
        lead, devis = self._devis(perdu=False, num=2)
        self._accepter(devis)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.SIGNED)
        self.assertFalse(LeadActivity.objects.filter(
            lead=lead, body__contains='relevé de Perdu').exists())
