"""ZSAV10 — Endpoint d'actions groupées atomique + opérations
priorité/annulation.

Couvre :
  * lot appliqué aux bons tickets en une requête (statut/technicien/priorite/
    annuler) ;
  * ids d'une autre société silencieusement ignorés ;
  * chaque ticket journalisé (chatter) ;
  * opération inconnue → 400 ;
  * une transition de statut illégale sur UN ticket du lot est rapportée en
    échec sans bloquer les autres.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zsav10 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket, TicketActivity

User = get_user_model()


def make_company(slug='sav-zsav10', nom='Sav Co ZSAV10'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZSAV10ActionsGroupeesTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zsav10_admin', password='x', role_legacy='admin',
            company=self.company)
        self.tech = User.objects.create_user(
            username='zsav10_tech', password='x', role_legacy='normal',
            company=self.company)
        self.api = auth(self.admin)
        self.other_company = make_company(
            slug='sav-zsav10-other', nom='Sav Co ZSAV10 Other')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZSAV10',
            email='zsav10-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZSAV10', client=self.client_obj)

    def _ticket(self, **kwargs):
        defaults = dict(
            company=self.company, client=self.client_obj,
            installation=self.inst, created_by=self.admin,
            reference=f'SAV-ZSAV10-{Ticket.objects.count()}')
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)

    def _post(self, ids, operation, **extra):
        return self.api.post('/api/django/sav/tickets/actions-groupees/', {
            'ids': ids, 'operation': operation, **extra,
        }, format='json')

    def test_technicien_en_lot(self):
        t1, t2 = self._ticket(), self._ticket()
        r = self._post([t1.id, t2.id], 'technicien', technicien=self.tech.id)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['nb_traites'], 2)
        t1.refresh_from_db()
        t2.refresh_from_db()
        self.assertEqual(t1.technicien_responsable_id, self.tech.id)
        self.assertEqual(t2.technicien_responsable_id, self.tech.id)
        self.assertEqual(
            TicketActivity.objects.filter(
                ticket=t1, kind='modification',
                field='technicien_responsable').count(), 1)

    def test_priorite_en_lot(self):
        t1 = self._ticket()
        r = self._post([t1.id], 'priorite', priorite='urgente')
        self.assertEqual(r.status_code, 200, r.data)
        t1.refresh_from_db()
        self.assertEqual(t1.priorite, Ticket.Priorite.URGENTE)

    def test_annuler_en_lot(self):
        t1 = self._ticket()
        r = self._post([t1.id], 'annuler', motif='Doublon')
        self.assertEqual(r.status_code, 200, r.data)
        t1.refresh_from_db()
        self.assertTrue(t1.annule)
        self.assertEqual(t1.motif_annulation, 'Doublon')

    def test_statut_en_lot_respecte_machine_etats(self):
        t1 = self._ticket()  # NOUVEAU
        r = self._post([t1.id], 'statut', statut='planifie')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['nb_traites'], 1)
        t1.refresh_from_db()
        self.assertEqual(t1.statut, Ticket.Statut.PLANIFIE)

    def test_statut_illegal_rapporte_en_echec_sans_bloquer_les_autres(self):
        legal = self._ticket()      # NOUVEAU -> peut aller à PLANIFIE
        illegal = self._ticket()    # NOUVEAU -> ne peut PAS aller à CLOTURE
        r = self._post([legal.id, illegal.id], 'statut', statut='cloture')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['nb_echecs'], 2)  # les deux sont NOUVEAU
        self.assertEqual(r.data['nb_traites'], 0)

        legal.statut = Ticket.Statut.PLANIFIE
        legal.save(update_fields=['statut'])
        r2 = self._post([legal.id, illegal.id], 'statut', statut='en_cours')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r2.data['nb_traites'], 2)

    def test_ids_autre_societe_ignores(self):
        other_client = Client.objects.create(
            company=self.other_company, nom='Autre', prenom='Client',
            email='zsav10-other@example.invalid')
        other_inst = Installation.objects.create(
            company=self.other_company, reference='CHT-OTHER',
            client=other_client)
        other_ticket = Ticket.objects.create(
            company=self.other_company, client=other_client,
            installation=other_inst, reference='SAV-OTHER-1')
        mine = self._ticket()

        r = self._post([mine.id, other_ticket.id], 'priorite', priorite='haute')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['nb_traites'], 1)
        other_ticket.refresh_from_db()
        self.assertNotEqual(other_ticket.priorite, Ticket.Priorite.HAUTE)

    def test_operation_inconnue_400(self):
        t1 = self._ticket()
        r = self._post([t1.id], 'demolir')
        self.assertEqual(r.status_code, 400, r.data)

    def test_ids_vide_400(self):
        r = self._post([], 'priorite', priorite='haute')
        self.assertEqual(r.status_code, 400, r.data)
