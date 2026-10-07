"""ADOC124 — pas d'accès portail PARTENAIRE pour un partenaire sans e-mail.

Constat (C-ADOC-052) : ``POST /api/django/crm/partenaires/<id>/provisionner-
acces/`` sur un partenaire sans e-mail répondait 200 « … mot de passe
temporaire envoyé par email » alors qu'aucun e-mail ne partait et créait un
compte au mot de passe connu de personne. Jumeau de la vue client (ADOC123) :
même message, même règle — la vue crm active ``exiger_email=True`` et traduit
``ProvisionnementSansEmail`` en 400 nommé.

Run :
    python manage.py test apps.portail.tests.test_adoc_provisionnement_partenaire_sans_email -v2
"""
import itertools

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.crm.models import Partenaire
from apps.roles.models import Role
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

MESSAGE = ("Ajoutez l'adresse e-mail du partenaire avant d'ouvrir son accès "
           "portail : le mot de passe temporaire part par e-mail.")


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ProvisionnementPartenaireSansEmailTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc124-{n}', defaults={'nom': f'ADOC124 {n}'})
        role, _ = Role.objects.get_or_create(
            company=self.co, nom=f'adoc124-admin-{n}',
            defaults={'permissions': ['roles_gerer', 'crm_voir'],
                      'est_systeme': True})
        self.admin = CustomUser.objects.create_user(
            username=f'adoc124-admin-{n}', password='motdepasse-test-1234',
            company=self.co, role=role)
        self.partenaire = Partenaire.objects.create(
            company=self.co, nom=f'Partenaire ADOC124-{n}', email='',
            token_acces=f'tok-adoc124-{n}')
        self.url = ('/api/django/crm/partenaires/'
                    f'{self.partenaire.id}/provisionner-acces/')
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)
        mail.outbox = []

    def _comptes_portail(self):
        return CustomUser.objects.filter(
            company=self.co, portee=CustomUser.PORTEE_PORTAIL_PARTENAIRE,
            portail_partenaire_id=self.partenaire.id)

    def test_partenaire_sans_email_400(self):
        res = self.api.post(self.url, {}, format='json')

        self.assertEqual(res.status_code, 400, res.content)
        self.assertEqual(res.json(), {'detail': MESSAGE})
        # Persistance : relecture — aucun compte créé, aucun e-mail.
        self.assertFalse(self._comptes_portail().exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_partenaire_avec_email_200_inchange(self):
        self.partenaire.email = 'partenaire-adoc124@example.invalid'
        self.partenaire.save(update_fields=['email'])

        res = self.api.post(self.url, {}, format='json')

        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.json()['cree'])
        self.assertTrue(self._comptes_portail().exists())
