"""AUDV28 (DRAFT165-7/8, XKB27/XKB32) — rétention affichée + annulation d'un
rappel.

`get_retention_policy`/`cancel_reminder` existaient déjà côté service
(purge/rappel eux-mêmes testés ailleurs) mais AUCUN endpoint ne les exposait :
l'écran de conversation ne pouvait pas afficher la durée de conservation
applicable, et un rappel programmé par erreur ne pouvait pas être annulé.

Run:
    python manage.py test apps.chat.tests.test_audv28_retention_et_annulation_rappel -v 2
"""
from django.utils import timezone
from datetime import timedelta

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.chat import services
from apps.chat.models import Conversation, Message
from apps.chat.tests.test_chat import make_channel, make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ConversationRetentionActionTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, 'audv28_admin', role_legacy='admin')
        self.alice = make_user(self.company, 'audv28_alice')
        self.bob = make_user(self.company, 'audv28_bob')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])

    def _url(self, conv_id=None):
        return f'/api/django/chat/conversations/{conv_id or self.conv.id}/retention/'

    def test_sans_politique_non_applicable(self):
        resp = auth(self.alice).get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['conversation_kind'], Conversation.Kind.CHANNEL)
        self.assertIsNone(resp.data['retention_months'])
        self.assertFalse(resp.data['applicable'])

    def test_avec_politique_applicable(self):
        services.set_retention_policy(
            self.company, Conversation.Kind.CHANNEL, 6, self.admin)
        resp = auth(self.alice).get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['retention_months'], 6)
        self.assertTrue(resp.data['applicable'])

    def test_non_membre_404(self):
        outsider = make_user(self.company, 'audv28_outsider')
        resp = auth(outsider).get(self._url())
        self.assertEqual(resp.status_code, 404)

    def test_isolation_societe(self):
        autre_co = make_company()
        autre_user = make_user(autre_co, 'audv28_autre')
        resp = auth(autre_user).get(self._url())
        self.assertEqual(resp.status_code, 404)


class ReminderCancelActionTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.alice = make_user(self.company, 'audv28r_alice')
        self.bob = make_user(self.company, 'audv28r_bob')
        self.conv = make_channel(self.company, self.alice, members=[self.bob])
        self.msg = Message.objects.create(
            company=self.company, conversation=self.conv, sender=self.alice,
            body='Message à rappeler')

    def _reminder_for(self, user):
        future = timezone.now() + timedelta(hours=1)
        return services.remind_me(self.msg, user, future)

    def test_le_createur_annule_son_propre_rappel(self):
        rem = self._reminder_for(self.bob)
        resp = auth(self.bob).post(
            f'/api/django/chat/reminders/{rem.id}/annuler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rem.refresh_from_db()
        self.assertEqual(rem.status, 'cancelled')

    def test_un_autre_utilisateur_ne_voit_pas_le_rappel(self):
        """`get_queryset` scope à `user=request.user` : un rappel d'un autre
        utilisateur est INTROUVABLE (404), jamais un 403 qui confirmerait
        son existence."""
        rem = self._reminder_for(self.bob)
        resp = auth(self.alice).post(
            f'/api/django/chat/reminders/{rem.id}/annuler/')
        self.assertEqual(resp.status_code, 404)
        rem.refresh_from_db()
        self.assertEqual(rem.status, 'pending')

    def test_annuler_deux_fois_refuse_la_seconde(self):
        rem = self._reminder_for(self.bob)
        api = auth(self.bob)
        first = api.post(f'/api/django/chat/reminders/{rem.id}/annuler/')
        self.assertEqual(first.status_code, 200)
        second = api.post(f'/api/django/chat/reminders/{rem.id}/annuler/')
        self.assertEqual(second.status_code, 400)

    def test_liste_scopee_au_createur(self):
        rem_bob = self._reminder_for(self.bob)
        self._reminder_for(self.alice)
        resp = auth(self.bob).get('/api/django/chat/reminders/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        ids = {r['id'] for r in rows}
        self.assertEqual(ids, {rem_bob.id})
