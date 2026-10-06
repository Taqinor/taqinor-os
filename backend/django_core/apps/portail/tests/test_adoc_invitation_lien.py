"""ADOC116 — le lien d'invitation d'équipe pointe sur l'hôte ERP de la requête.

Constat (C-ADOC-049, sonde #94) : ``_envoyer_invitation_portail`` construisait
le lien sur ``SITE_URL`` (``https://taqinor.ma/portail/invitation/accepter``)
— le site public Astro, qui n'a AUCUNE page portail : l'invité tombait sur
une 404 et ne pouvait jamais rejoindre l'équipe.

Correctif (patron WIR216) : la vue passe ``request.build_absolute_uri('/')``
au service ; sans base explicite, l'invitation est créée mais aucun e-mail
ne part (plutôt qu'un lien vers un autre hôte).

Run :
    python manage.py test apps.portail.tests.test_adoc_invitation_lien -v2
"""
import itertools

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.portail.models import InvitationPortail
from apps.portail.services import (
    inviter_membre_portail,
    provisionner_compte_portail_client,
)
from authentication.models import Company

_seq = itertools.count(1)


@override_settings(
    ALLOWED_HOSTS=['erp.exemple.test', 'testserver'],
    SITE_URL='https://taqinor.ma',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class InvitationLienTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc116-{n}', defaults={'nom': f'ADOC116 {n}'})
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client', prenom='ADOC116',
            email=f'adoc116-{n}@example.invalid')
        self.admin, _ = provisionner_compte_portail_client(
            self.co, self.client_crm.id)
        self.admin.must_change_password = False
        self.admin.save(update_fields=['must_change_password'])
        mail.outbox = []

    def test_lien_sur_hote_erp(self):
        api = APIClient()
        api.force_authenticate(user=self.admin)
        res = api.post('/api/django/portail/mon-equipe/', {
            'email': 'm@x.ma', 'role': 'lecture',
        }, format='json', HTTP_HOST='erp.exemple.test')
        self.assertEqual(res.status_code, 201, res.content)

        invitation = InvitationPortail.objects.get(
            company=self.co, email='m@x.ma')
        self.assertEqual(invitation.statut,
                         InvitationPortail.Statut.EN_ATTENTE)
        self.assertEqual(len(mail.outbox), 1)
        corps = mail.outbox[0].body
        self.assertIn(
            'http://erp.exemple.test/portail/invitation/accepter'
            f'?token={invitation.token_invitation}', corps)
        self.assertNotIn('taqinor.ma', corps)

    def test_sans_base_aucun_email(self):
        invitation = inviter_membre_portail(
            self.co, self.client_crm.id, 'prog@x.ma', 'lecture')
        self.assertIsNotNone(invitation)
        self.assertEqual(len(mail.outbox), 0)
