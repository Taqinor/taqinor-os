"""AUD529 — escalade d'un ticket SAV en réclamation formelle (apps.litiges).

Constat d'audit (le ROUGE figé ici) : ``docs/module-map.md`` documente
``apps.litiges`` comme l'équivalent « escalade Helpdesk » de SAV, mais AUCUNE
référence n'existait entre les deux apps (grep négatif : ``apps.sav`` ne citait
jamais ``litiges``, et ``litiges.services.creer_reclamation`` n'avait aucun
appelant SAV). Un ticket grave ne pouvait devenir une réclamation qu'à la
re-saisie manuelle.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_aud529 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.litiges.models import Reclamation, ReclamationActivity
from apps.sav.models import Ticket, TicketActivity

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AUD529EscaladeSavVersLitigesTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-aud529', defaults={'nom': 'Sav Co AUD529'})
        self.admin = User.objects.create_user(
            username='aud529_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD529',
            email='aud529-client@example.invalid')

    def _ticket(self, ref='SAV-AUD529-1', **extra):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            type=Ticket.Type.CORRECTIF, description='Onduleur en défaut',
            created_by=self.admin, **extra)

    def test_action_cree_la_reclamation_liee_des_deux_cotes(self):
        ticket = self._ticket()
        resp = auth(self.admin).post(
            f'/api/django/sav/tickets/{ticket.pk}/escalader-reclamation/', {},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['cree'])

        reclamation = Reclamation.objects.get(pk=resp.data['reclamation_id'])
        # Lien litiges → ticket (couple souple source_type/source_id).
        self.assertEqual(reclamation.source_type, 'ticket')
        self.assertEqual(reclamation.source_id, ticket.pk)
        self.assertEqual(reclamation.company_id, self.company.id)
        # Lien de RETOUR ticket → réclamation.
        ticket.refresh_from_db()
        self.assertEqual(ticket.reclamation_id_ext, reclamation.pk)
        # Une réclamation qualité SAV ne suspend pas les relances (LITIGE3).
        self.assertFalse(reclamation.bloque_relances)

    def test_trace_dans_les_deux_chatters(self):
        ticket = self._ticket('SAV-AUD529-2')
        auth(self.admin).post(
            f'/api/django/sav/tickets/{ticket.pk}/escalader-reclamation/', {},
            format='json')
        reclamation = Reclamation.objects.get(source_id=ticket.pk)
        notes_sav = TicketActivity.objects.filter(
            ticket=ticket, kind=TicketActivity.Kind.NOTE)
        self.assertTrue(
            any('réclamation' in (n.body or '').lower() for n in notes_sav))
        notes_litiges = ReclamationActivity.objects.filter(
            reclamation=reclamation, type=ReclamationActivity.Kind.NOTE)
        self.assertTrue(
            any(ticket.reference in (n.message or '') for n in notes_litiges))

    def test_idempotent_pas_de_second_dossier(self):
        ticket = self._ticket('SAV-AUD529-3')
        api = auth(self.admin)
        url = f'/api/django/sav/tickets/{ticket.pk}/escalader-reclamation/'
        premier = api.post(url, {}, format='json')
        self.assertEqual(premier.status_code, 201, premier.data)
        second = api.post(url, {}, format='json')
        self.assertEqual(second.status_code, 200, second.data)
        self.assertFalse(second.data['cree'])
        self.assertEqual(
            second.data['reclamation_id'], premier.data['reclamation_id'])
        self.assertEqual(
            Reclamation.objects.filter(source_id=ticket.pk).count(), 1)

    def test_ticket_annule_refuse(self):
        ticket = self._ticket('SAV-AUD529-4', annule=True)
        resp = auth(self.admin).post(
            f'/api/django/sav/tickets/{ticket.pk}/escalader-reclamation/', {},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(Reclamation.objects.count(), 0)

    def test_gravite_derivee_de_la_priorite(self):
        ticket = self._ticket(
            'SAV-AUD529-5', priorite=Ticket.Priorite.URGENTE)
        resp = auth(self.admin).post(
            f'/api/django/sav/tickets/{ticket.pk}/escalader-reclamation/', {},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['gravite'], Reclamation.Gravite.ELEVEE)

    def test_corps_optionnel_respecte(self):
        ticket = self._ticket('SAV-AUD529-6')
        resp = auth(self.admin).post(
            f'/api/django/sav/tickets/{ticket.pk}/escalader-reclamation/', {
                'type_reclamation': Reclamation.TypeReclamation.DELAI,
                'objet': 'Retard de remise en service',
                'gravite': Reclamation.Gravite.FAIBLE,
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        reclamation = Reclamation.objects.get(pk=resp.data['reclamation_id'])
        self.assertEqual(
            reclamation.type_reclamation, Reclamation.TypeReclamation.DELAI)
        self.assertEqual(reclamation.objet, 'Retard de remise en service')
        self.assertEqual(reclamation.gravite, Reclamation.Gravite.FAIBLE)

    def test_lien_reclamation_non_ecrivable_par_patch(self):
        """Multi-tenant/intégrité : le lien est posé par l'action serveur,
        jamais depuis le corps d'un PATCH."""
        ticket = self._ticket('SAV-AUD529-7')
        resp = auth(self.admin).patch(
            f'/api/django/sav/tickets/{ticket.pk}/',
            {'reclamation_id_ext': 4242}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.reclamation_id_ext)
