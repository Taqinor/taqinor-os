"""AUD405 — le secret HMAC d'un Webhook ne sort JAMAIS par l'admin Django.

Défaut audité : ``WebhookAdmin.readonly_fields`` contenait ``'secret'`` — or un
champ en lecture seule reste RENDU, pas caché. ``Webhook.secret`` étant un
``EncryptedCharField`` déchiffré à chaque chargement ORM, la vue de changement
affichait en clair le secret qui signe TOUS les webhooks sortants de la société
(``X-Taqinor-Signature``) : de quoi forger de faux ``facture.paid`` /
``devis.accepted`` vers l'intégration du client. ``ApiKeyAdmin``, lui, n'expose
qu'un ``key_hash`` irréversible.

Le test central est ROUGE avant le correctif (le secret apparaît dans le HTML)
et VERT après (absent).
"""
from django.contrib import admin as dj_admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from authentication.models import Company
from .models import Webhook

User = get_user_model()

SECRET = 'sup3r-s3cret-hmac-value-aud405'


class Aud405WebhookSecretAdminTests(TestCase):
    def _request(self, user):
        request = RequestFactory().get('/')
        request.user = user
        return request

    @property
    def model_admin(self):
        return dj_admin.site._registry[Webhook]

    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD405 Co', slug='aud405-co')
        self.autre = Company.objects.create(
            nom='AUD405 Autre', slug='aud405-autre')
        self.hook = Webhook.objects.create(
            company=self.company, target_url='https://example.test/hook',
            secret=SECRET, events=[], enabled=True)
        self.hook_autre = Webhook.objects.create(
            company=self.autre, target_url='https://autre.test/hook',
            secret='secret-de-lautre-societe', events=[], enabled=True)
        self.staff = User.objects.create_superuser(
            username='staff405', email='s@aud405.ma', password='pw-aud405-x1')
        self.staff.company = self.company
        self.staff.save(update_fields=['company'])
        self.client.force_login(self.staff)

    def _change_url(self, hook):
        return reverse('admin:publicapi_webhook_change', args=[hook.pk])

    # ── Le constat de l'audit ─────────────────────────────────────────────
    def test_le_secret_nest_plus_rendu_dans_la_vue_de_changement(self):
        resp = self.client.get(self._change_url(self.hook))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(SECRET, resp.content.decode('utf-8'))

    def test_le_secret_nest_plus_un_champ_du_formulaire(self):
        champs = self.model_admin.get_fields(
            self._request(self.staff), self.hook)
        self.assertNotIn('secret', champs)
        self.assertNotIn('secret', self.model_admin.readonly_fields)

    def test_un_temoin_masque_reste_affiche(self):
        """L'opérateur voit que le secret existe, jamais sa valeur."""
        resp = self.client.get(self._change_url(self.hook))
        self.assertIn('masqué', resp.content.decode('utf-8'))

    # ── Scoping société (défense en profondeur) ───────────────────────────
    def test_le_staff_ne_liste_que_les_webhooks_de_sa_societe(self):
        qs = self.model_admin.get_queryset(self._request(self.staff))
        self.assertIn(self.hook, qs)
        self.assertNotIn(self.hook_autre, qs)

    def test_un_operateur_sans_societe_garde_la_vue_complete(self):
        plateforme = User.objects.create_superuser(
            username='plateforme405', email='p@aud405.ma',
            password='pw-aud405-x2')
        qs = self.model_admin.get_queryset(self._request(plateforme))
        self.assertIn(self.hook, qs)
        self.assertIn(self.hook_autre, qs)

    # ── Rotation explicite (patron ApiKey.rotate) ─────────────────────────
    def test_action_de_regeneration_change_le_secret(self):
        model_admin = self.model_admin
        self.assertIn('regenerer_secret', model_admin.actions)

        messages = []
        original = model_admin.message_user
        self.addCleanup(setattr, model_admin, 'message_user', original)
        model_admin.message_user = (
            lambda request, message, *a, **kw: messages.append(message))
        model_admin.regenerer_secret(
            self._request(self.staff),
            Webhook.objects.filter(pk=self.hook.pk))

        self.hook.refresh_from_db()
        self.assertNotEqual(self.hook.secret, SECRET)
        self.assertTrue(self.hook.secret)
        # La nouvelle valeur est montrée UNE fois, à l'opérateur qui l'a
        # demandée — jamais re-affichée ensuite.
        self.assertTrue(any(self.hook.secret in m for m in messages))

    def test_creation_par_ladmin_genere_un_secret_serveur(self):
        """Le champ étant exclu du formulaire, le serveur le pose lui-même."""
        neuf = Webhook(
            company=self.company, target_url='https://neuf.test/hook',
            events=[], enabled=True)
        self.model_admin.save_model(
            self._request(self.staff), neuf, None, False)
        neuf.refresh_from_db()
        self.assertTrue(neuf.secret)
