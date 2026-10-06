"""ADOC123 — pas d'accès portail CLIENT pour un client sans e-mail.

Constat (C-ADOC-052, sonde #95) : ``provisionner-acces`` sur un client sans
e-mail répondait 200 « … mot de passe temporaire envoyé par email » alors
qu'aucun e-mail ne partait (send_mail 0 fois) et créait un compte
``email=''`` — mot de passe inconnu de tous, « mot de passe oublié »
impossible.

Correctif : 400 nommé, aucun compte, aucun e-mail ;
``provisionner_compte_partenaire(..., exiger_email=True)`` lève
``ProvisionnementSansEmail`` (activé par ADOC124), défaut inchangé.

Run :
    python manage.py test apps.portail.tests.test_adoc_provisionnement_sans_email -v2
"""
import itertools

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.crm.models import Client, Partenaire
from apps.portail.models import ComptePortailClient
from apps.portail.services import (
    ProvisionnementSansEmail,
    provisionner_compte_partenaire,
)
from apps.roles.models import Role
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

MESSAGE = ("Ajoutez l'adresse e-mail du client avant d'ouvrir son accès "
           "portail : le mot de passe temporaire part par e-mail.")


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ProvisionnementSansEmailTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc123-{n}', defaults={'nom': f'ADOC123 {n}'})
        role, _ = Role.objects.get_or_create(
            company=self.co, nom=f'adoc123-admin-{n}',
            defaults={'permissions': ['roles_gerer', 'crm_voir'],
                      'est_systeme': True})
        self.admin = CustomUser.objects.create_user(
            username=f'adoc123-admin-{n}', password='motdepasse-test-1234',
            company=self.co, role=role)
        self.client_crm = Client.objects.create(
            company=self.co, nom='Client', prenom=f'ADOC123-{n}', email='')
        self.compte = ComptePortailClient.objects.create(
            company=self.co, client=self.client_crm,
            token_acces=f'token-adoc123-{n}')
        self.url = ('/api/django/portail/comptes-portail/'
                    f'{self.compte.id}/provisionner-acces/')
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)
        mail.outbox = []

    def _comptes_portail(self):
        return CustomUser.objects.filter(
            company=self.co, portee=CustomUser.PORTEE_PORTAIL_CLIENT,
            portail_client_id=self.client_crm.id)

    def test_client_sans_email_refuse(self):
        res = self.api.post(self.url, {}, format='json')

        self.assertEqual(res.status_code, 400, res.content)
        self.assertEqual(res.json(), {'detail': MESSAGE})
        self.assertFalse(self._comptes_portail().exists())
        self.assertEqual(len(mail.outbox), 0)

        # Après ajout de l'e-mail, le comportement d'avant est intact.
        self.client_crm.email = 'client-adoc123@example.invalid'
        self.client_crm.save(update_fields=['email'])
        res = self.api.post(self.url, {}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.json()['cree'])
        self.assertIn('envoyé par email', res.json()['detail'])
        user = self._comptes_portail().get()
        self.assertEqual(user.email, 'client-adoc123@example.invalid')
        self.assertEqual(len(mail.outbox), 1)

    def test_partenaire_exiger_email_leve(self):
        n = next(_seq)
        partenaire = Partenaire.objects.create(
            company=self.co, nom=f'Partenaire ADOC123-{n}', email='',
            token_acces=f'tok-adoc123-{n}')
        with self.assertRaises(ProvisionnementSansEmail):
            provisionner_compte_partenaire(
                self.co, partenaire.id, exiger_email=True)
        self.assertFalse(CustomUser.objects.filter(
            portail_partenaire_id=partenaire.id).exists())

        # Sans le paramètre : comportement actuel conservé (compte créé).
        user, cree = provisionner_compte_partenaire(self.co, partenaire.id)
        self.assertTrue(cree)
        self.assertEqual(user.portail_partenaire_id, partenaire.id)
