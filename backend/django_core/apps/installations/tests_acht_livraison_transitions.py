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
import threading
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.installations.models import Installation, Livraison
from apps.publicapi.models import ApiEvent
from core.test_utils import WideTeardownTimeoutMixin
from testkit.verrous import attendre_un_ecrivain_bloque

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
        # api-fuzz full : transition interdite = refus d'ETAT, 409.
        self.assertEqual(r.status_code, 409, (liv.statut, action, r.data))
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
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(len(mail.outbox), mails)
        self.assertEqual(ApiEvent.objects.filter(
            company=self.company, type='livraison.livree').count(), 1)


class LivrerConcurrenceTests(WideTeardownTimeoutMixin, TransactionTestCase):
    """ACNC59 — deux « Livrer » croisés (deux VRAIES connexions) : A tient sa
    transaction dans ``_exiger_transition_livraison`` ; une seule notification
    client « livrée », un seul webhook, le second répond 409."""

    def test_deux_livraisons_croisees_une_seule_notification(self):
        from apps.installations.views import livraison as vue
        company = Company.objects.create(slug='co-acnc59', nom='Co ACNC59')
        user = User.objects.create_user(
            username='resp-acnc59', password='x', company=company,
            role_legacy='responsable')
        client = Client.objects.create(
            company=company, nom='Client ACNC59',
            email='client-acnc59@example.invalid')
        liv = Livraison.objects.create(
            company=company, reference='LIV-ACNC59-1', statut=S.EN_TRANSIT,
            installation=Installation.objects.create(
                company=company, client=client, reference='CH-ACNC59'))
        original = vue._exiger_transition_livraison
        a_tient, b_tente, b_fini, res = (
            threading.Event(), threading.Event(), threading.Event(), {})

        def exiger_lent(*args):
            if not a_tient.is_set():  # A : tient la livraison verrouillée
                a_tient.set()
                b_tente.wait(5)
                attendre_un_ecrivain_bloque(ou_bien=b_fini)
            return original(*args)

        def fil(nom):
            if nom == 'b':
                a_tient.wait(5)
                b_tente.set()
            api = APIClient()
            api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
            res[nom] = api.post(f'{BASE}/{liv.id}/livrer/', {}, format='json').status_code
            if nom == 'b':
                b_fini.set()
            connection.close()

        with mock.patch.object(vue, '_exiger_transition_livraison', side_effect=exiger_lent), \
                mock.patch('apps.publicapi.services.notify_livraison_livree') as webhook, \
                mock.patch('apps.installations.livraison_client_notify.notify_livraison_transition',
                           return_value={}) as notif:
            fils = [threading.Thread(target=fil, args=(n,)) for n in ('a', 'b')]
            for f in fils:
                f.start()
            for f in fils:
                f.join(20)
        self.assertEqual(sorted(res.values()), [200, 409], res)
        self.assertEqual(webhook.call_count, 1)
        self.assertEqual([c.args[1] for c in notif.call_args_list], ['livree'])
        liv.refresh_from_db()
        self.assertEqual(liv.statut, S.LIVREE)
        self.assertIsNotNone(liv.notifie_livree_le)
