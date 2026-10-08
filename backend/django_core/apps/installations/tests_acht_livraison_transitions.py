"""ACHT19 (C-ACHT-017) — table de transitions des livraisons (planifiée → en
transit → livrée ; annulation seulement avant livraison) lue par
`expedier`, `livrer`, `annuler`, et notification client + webhook « livrée »
envoyés une seule fois (`notifie_livree_le`).

Rejoue CKIT-3 : 6 gestes hors séquence à 200 ; notifications [livree,
webhook, livree, webhook] pour deux `livrer`.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_livraison_transitions"
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.installations.models import Installation, Livraison
from apps.publicapi.models import ApiEvent

User = get_user_model()
BASE = '/api/django/installations/livraisons'
S = Livraison.Statut


class LivraisonTransitionsTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht19', defaults={'nom': 'Co ACHT19'})
        self.user = User.objects.create_user(
            username='resp-acht19', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Client ACHT19',
            email='client-acht19@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, client=client, reference='CH-ACHT19')
        self._n = 0

    def _liv(self, statut):
        self._n += 1
        return Livraison.objects.create(
            company=self.company, installation=self.inst,
            reference=f'LIV-ACHT19-{self._n}', statut=statut)

    def _post(self, liv, action):
        return self.api.post(f'{BASE}/{liv.id}/{action}/', {}, format='json')

    def _assert_refus(self, liv, action, message=None):
        avant = (liv.statut, liv.stock_mouvemente, liv.notifie_livree_le)
        r = self._post(liv, action)
        self.assertEqual(r.status_code, 400, (liv.statut, action, r.data))
        if message:
            self.assertIn(message, str(r.data))
        liv.refresh_from_db()
        self.assertEqual(
            (liv.statut, liv.stock_mouvemente, liv.notifie_livree_le), avant)

    def test_livrer_sans_expedition_refuse(self):
        self._assert_refus(self._liv(S.PLANIFIEE), 'livrer',
                           "Expédiez d'abord la livraison")

    def test_matrice_hors_sequence(self):
        livree = self._liv(S.LIVREE)
        self._assert_refus(livree, 'expedier')
        self._assert_refus(livree, 'annuler',
                           "Livraison livrée : impossible de l'annuler")
        annulee = self._liv(S.ANNULEE)
        self._assert_refus(annulee, 'livrer')
        self._assert_refus(annulee, 'expedier',
                           "Livraison annulée : impossible de l'expédier")

    def test_chemin_nominal(self):
        liv = self._liv(S.PLANIFIEE)
        self.assertEqual(self._post(liv, 'expedier').status_code, 200)
        self.assertEqual(self._post(liv, 'livrer').status_code, 200)
        autre = self._liv(S.PLANIFIEE)
        self.assertEqual(self._post(autre, 'annuler').status_code, 200)

    def test_notification_livree_unique(self):
        liv = self._liv(S.EN_TRANSIT)
        r = self._post(liv, 'livrer')
        self.assertEqual(r.status_code, 200, r.data)
        liv.refresh_from_db()
        self.assertIsNotNone(liv.notifie_livree_le)
        mails = len(mail.outbox)
        evenements = ApiEvent.objects.filter(
            company=self.company, type='livraison.livree').count()
        self.assertEqual(evenements, 1)
        r = self._post(liv, 'livrer')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(len(mail.outbox), mails)
        self.assertEqual(ApiEvent.objects.filter(
            company=self.company, type='livraison.livree').count(), 1)
