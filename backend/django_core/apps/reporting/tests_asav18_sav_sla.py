"""ASAV18 (C-ASAV-012/013) — le rapport ``insights/sav-sla`` mesure la
résolution par ``sav.selectors.sla_respecte`` (pauses décomptées) et la
première réponse par l'échéance de RÉPONSE (``premiere_reponse_respectee``),
sans comparaison locale à ``sla_due_at``. Données réelles en base."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.sav.models import Ticket
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/insights/sav-sla/'


class SavSlaRapportTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='asav18-co', defaults={'nom': 'ASAV18 Co'})[0]
        self.user = User.objects.create_user(
            username='asav18_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_crm = Client.objects.create(
            company=self.company, nom='Cli ASAV18')
        self.today = timezone.localdate()

    def _ticket(self, ref, **champs):
        t = Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_crm)
        # update() : contourne tout recalcul de save() sur les échéances.
        Ticket.objects.filter(pk=t.pk).update(**champs)
        return t

    def _ligne(self, resp, priorite):
        self.assertEqual(resp.status_code, 200)
        return next(
            p for p in resp.data['par_priorite'] if p['priorite'] == priorite)

    def test_resolution_pause_respectee(self):
        # Échéance brute J-3, résolu aujourd'hui, 5 j de pause : l'échéance
        # effective (J+2) est tenue. Comparé au brut, le rapport dirait 0 %.
        self._ticket(
            'T-ASAV18-1', priorite=Ticket.Priorite.NORMALE,
            sla_due_at=self.today - timedelta(days=3),
            date_resolution=self.today, jours_pause=5)
        ligne = self._ligne(self.api.get(URL), Ticket.Priorite.NORMALE)
        self.assertEqual(ligne['pct_resolution_ok'], 100.0)

    def test_premiere_reponse_contre_delai_reponse(self):
        # Haute : réponse due à J-5 (1 j après ouverture à J-6), répondu
        # aujourd'hui (6 j après) ; la résolution (7 j) est encore dans les
        # temps, donc comparer à ``sla_due_at`` dirait 100 %.
        self._ticket(
            'T-ASAV18-2', priorite=Ticket.Priorite.HAUTE,
            date_ouverture=self.today - timedelta(days=6),
            sla_reponse_due_at=self.today - timedelta(days=5),
            sla_due_at=self.today + timedelta(days=1),
            date_premiere_reponse=timezone.now())
        resp = self.api.get(URL + '?priorite=haute')
        ligne = self._ligne(resp, Ticket.Priorite.HAUTE)
        self.assertEqual(ligne['pct_premiere_reponse_ok'], 0.0)
