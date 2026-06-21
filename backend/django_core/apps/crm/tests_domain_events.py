"""Bus d'événements métier (M6) — `core.events.devis_accepted` câblé au
récepteur CRM (`apps.crm.receivers`) qui avance l'étape du lead.

Couvre un trou réel : `test_acceptation.py` vérifie les métadonnées/chatter/
chantier de l'acceptation d'un devis, mais JAMAIS l'avancée d'étape du lead qui
en découle. On teste ici, à la fois :
  • le câblage de bout en bout (POST accepter/ → signal → récepteur → SIGNED) ;
  • le récepteur en isolation (émission directe du signal), ce qui garantit que
    l'abonnement (CrmConfig.ready) est bien en place ;
  • les garde-fous de `avancer_stage_pour_devis` : ne recule jamais, ignore les
    leads perdus.

Les clés d'étape ('QUOTE_SENT', 'SIGNED'…) suivent la convention des tests
existants (cf. test_acceptation.py) ; la source canonique reste STAGES.py.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity
from apps.ventes.models import Devis
from core.events import devis_accepted

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDevisAcceptedAdvancesLeadStage(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='evt-co', defaults={'nom': 'Evt Co'})
        self.user = User.objects.create_user(
            username='evt_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = _auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Evt',
            email='evt@example.com', telephone='+212600000009')

    def _devis(self, lead, num, statut=Devis.Statut.ENVOYE):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, lead=lead, statut=statut,
            taux_tva=Decimal('20'))

    def test_accepting_devis_advances_lead_to_signed(self):
        """Bout en bout : POST accepter/ émet le signal → l'étape passe à SIGNED
        et une entrée d'historique automatique est consignée sur le lead."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead Evt', stage='QUOTE_SENT')
        devis = self._devis(lead, num=1)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-10'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')
        auto = (LeadActivity.objects
                .filter(lead=lead, field='stage').order_by('-id').first())
        self.assertIsNotNone(auto)
        self.assertIn('auto', auto.body)

    def test_signal_directly_triggers_crm_receiver(self):
        """Récepteur en isolation : émettre `devis_accepted` suffit à avancer
        l'étape — preuve que l'abonnement (ready()) est câblé."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead Sig', stage='NEW')
        devis = self._devis(lead, num=2, statut=Devis.Statut.ACCEPTE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')

    def test_never_recedes_an_already_signed_lead(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead Signed', stage='SIGNED')
        devis = self._devis(lead, num=3, statut=Devis.Statut.ACCEPTE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')

    def test_ignores_lost_lead(self):
        """Lead marqué perdu : le funnel ne bouge plus automatiquement."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead Perdu', stage='QUOTE_SENT',
            perdu=True)
        devis = self._devis(lead, num=4, statut=Devis.Statut.ACCEPTE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'QUOTE_SENT')
