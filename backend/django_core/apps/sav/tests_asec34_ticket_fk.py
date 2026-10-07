"""ASEC34 — ticket SAV : FK inscriptibles bornées à la société, champs posés
par le serveur figés.

Constat C-ASEC-005 site (g) + C-ASEC-009 volet ticket : ``TicketSerializer``
acceptait l'id d'un technicien, d'une catégorie de ticket ou d'une catégorie
d'équipement d'une AUTRE société, et laissait PATCHer ``non_facturable``,
``est_recidive`` et ``cout``. Attendu : un id d'ailleurs reçoit la même
réponse qu'un id absent (400), et les trois champs serveur restent inchangés
en base après un PATCH.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.sav.models import CategorieEquipement, CategorieTicket, Ticket
from authentication.models import Company

User = get_user_model()

URL = '/api/django/sav/tickets/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TicketFkEtChampsServeurTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='ASEC34 A', slug='asec34-a')
        self.b = Company.objects.create(nom='ASEC34 B', slug='asec34-b')
        self.user_a = User.objects.create_user(
            username='asec34_admin_a', password='x', role_legacy='admin',
            company=self.a)
        self.tech_a = User.objects.create_user(
            username='asec34_tech_a', password='x',
            role_legacy='normal', company=self.a)
        self.tech_b = User.objects.create_user(
            username='asec34_tech_b', password='x',
            role_legacy='normal', company=self.b)
        self.cat_a = CategorieTicket.objects.create(
            company=self.a, libelle='Panne A')
        self.cat_b = CategorieTicket.objects.create(
            company=self.b, libelle='Panne B secrète')
        self.cateq_a = CategorieEquipement.objects.create(
            company=self.a, nom='Onduleurs A')
        self.cateq_b = CategorieEquipement.objects.create(
            company=self.b, nom='Pompes B secrètes')
        self.client_a = Client.objects.create(company=self.a, nom='Client A')
        self.ticket = Ticket.objects.create(
            company=self.a, reference='ASEC34-1', client=self.client_a,
            cout=Decimal('100.00'))
        self.api = _api(self.user_a)

    def _patch(self, body):
        return self.api.patch(f'{URL}{self.ticket.id}/', body, format='json')

    def _assert_refus(self, champ, valeur):
        r = self._patch({champ: valeur})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(champ, r.data)
        self.assertNotIn('secrète', str(r.data))
        self.ticket.refresh_from_db()
        self.assertIsNone(getattr(self.ticket, f'{champ}_id'))
        # Création refusée aussi.
        avant = Ticket.objects.count()
        r2 = self.api.post(URL, {
            'client': self.client_a.id, 'type': 'correctif',
            'description': 'x', champ: valeur}, format='json')
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertIn(champ, r2.data)
        self.assertEqual(Ticket.objects.count(), avant)

    def test_technicien_etranger_400(self):
        self._assert_refus('technicien_responsable', self.tech_b.id)

    def test_categorie_etrangere_400(self):
        self._assert_refus('categorie', self.cat_b.id)

    def test_categorie_equipement_etrangere_400(self):
        self._assert_refus('categorie_equipement', self.cateq_b.id)

    def test_id_inexistant_meme_reponse(self):
        r_etr = self._patch({'categorie': self.cat_b.id})
        r_abs = self._patch({'categorie': 999999})
        self.assertEqual(r_abs.status_code, 400)
        self.assertEqual(
            str(r_etr.data['categorie'][0]).replace(str(self.cat_b.id), '?'),
            str(r_abs.data['categorie'][0]).replace('999999', '?'))

    def test_non_facturable_fige(self):
        r = self._patch({'non_facturable': True, 'est_recidive': True})
        self.assertEqual(r.status_code, 200, r.data)
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.non_facturable)
        self.assertFalse(self.ticket.est_recidive)

    def test_cout_fige(self):
        r = self._patch({'cout': '999.00'})
        self.assertEqual(r.status_code, 200, r.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.cout, Decimal('100.00'))

    def test_ids_societe_ok(self):
        r = self._patch({
            'technicien_responsable': self.tech_a.id,
            'categorie': self.cat_a.id,
            'categorie_equipement': self.cateq_a.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.technicien_responsable_id, self.tech_a.id)
        self.assertEqual(self.ticket.categorie_id, self.cat_a.id)
        self.assertEqual(self.ticket.categorie_equipement_id, self.cateq_a.id)
        r2 = self.api.post(URL, {
            'client': self.client_a.id, 'type': 'correctif',
            'description': 'ok', 'technicien_responsable': self.tech_a.id,
            'categorie': self.cat_a.id}, format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
