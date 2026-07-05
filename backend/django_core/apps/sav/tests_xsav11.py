"""XSAV11 — Suivi des réouvertures + taux de réouverture.

Couvre :
  * résolu/clôturé → statut ouvert incrémente reopen_count exactement une
    fois par transition ;
  * jamais décrémenté (repasser ouvert→ouvert ou résolu→résolu ne touche pas
    le compteur) ;
  * plusieurs réouvertures successives cumulent ;
  * taux de réouverture par technicien et par type calculé correctement.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav11 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket
from apps.sav.selectors import taux_reouverture

User = get_user_model()


def make_company(slug='sav-xsav11', nom='Sav Co XSAV11'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV11ReopenTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xsav11_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.tech = User.objects.create_user(
            username='xsav11_tech', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav11-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV11', client=self.client_obj)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV11-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.RESOLU,
            technicien_responsable=self.tech, created_by=self.user)

    def test_resolu_vers_ouvert_incremente(self):
        # YDOCF1 — la réouverture passe par l'action guardée `planifier`
        # (RESOLU → PLANIFIE, permis par la machine d'états) qui ne recule
        # jamais elle-même vers NOUVEAU : on utilise `planifier` en tant que
        # transition « ouverte » (comptée comme réouverture par
        # `_CLOTURE_STATUTS`).
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/planifier/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['reopen_count'], 1)

    def test_cloture_vers_en_cours_incremente(self):
        self.ticket.statut = Ticket.Statut.CLOTURE
        self.ticket.save(update_fields=['statut'])
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/demarrer/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['reopen_count'], 1)

    def test_jamais_decremente(self):
        self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/planifier/',
            {}, format='json')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.reopen_count, 1)
        # Re-résoudre puis re-passer par des statuts ouverts NE compte
        # qu'à chaque transition RÉSOLU/CLÔTURÉ → OUVERT, jamais négatif.
        self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/demarrer/',
            {}, format='json')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.reopen_count, 1)  # ouvert→ouvert : rien.

    def test_plusieurs_reouvertures_cumulent(self):
        # Alterne RESOLU → EN_COURS (réouverture, +1) → RESOLU (pas une
        # réouverture) — 3 fois, pour vérifier le cumul (jamais décrémenté).
        for _ in range(3):
            self.api.post(
                f'/api/django/sav/tickets/{self.ticket.pk}/demarrer/',
                {}, format='json')
            self.api.post(
                f'/api/django/sav/tickets/{self.ticket.pk}/resoudre/',
                {}, format='json')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.reopen_count, 3)

    def test_taux_reouverture_par_technicien(self):
        self.ticket.reopen_count = 1
        self.ticket.save(update_fields=['reopen_count'])
        Ticket.objects.create(
            company=self.company, reference='SAV-XSAV11-2',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.RESOLU,
            technicien_responsable=self.tech, reopen_count=0,
            created_by=self.user)

        rows = taux_reouverture(self.company, group_by='technicien')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['nb_tickets'], 2)
        self.assertEqual(row['nb_reouverts'], 1)
        self.assertEqual(row['taux'], 50.0)

    def test_taux_reouverture_par_type(self):
        self.ticket.type = Ticket.Type.CORRECTIF
        self.ticket.reopen_count = 1
        self.ticket.save(update_fields=['type', 'reopen_count'])
        Ticket.objects.create(
            company=self.company, reference='SAV-XSAV11-3',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.PREVENTIF, statut=Ticket.Statut.RESOLU,
            reopen_count=0, created_by=self.user)

        rows = taux_reouverture(self.company, group_by='type')
        by_type = {r['cle']: r for r in rows}
        self.assertEqual(by_type['correctif']['taux'], 100.0)
        self.assertEqual(by_type['preventif']['taux'], 0.0)

    def test_migration_defaut_zero(self):
        t = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV11-MIG',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.user)
        self.assertEqual(t.reopen_count, 0)
