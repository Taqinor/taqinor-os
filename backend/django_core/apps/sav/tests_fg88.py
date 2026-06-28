"""FG88 — Planification de tournée maintenance préventive.

File des visites préventives DUES avec GPS du chantier, triée par proximité
(haversine, sans service externe), + affectation EN LOT date + technicien
(scopée société). Miroir du style de tests_maintenance.py.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket
from authentication.models import Company

User = get_user_model()

TOURNEE = '/api/django/sav/contrats-maintenance/tournee/'
PLANIFIER = '/api/django/sav/contrats-maintenance/planifier-tournee/'


def _preventif(company, client, installation, ref, **kw):
    kw.setdefault('statut', Ticket.Statut.NOUVEAU)
    kw.setdefault('date_ouverture', date.today())
    return Ticket.objects.create(
        company=company, client=client, installation=installation,
        reference=ref, type=Ticket.Type.PREVENTIF, **kw)


class TestTourneePreventive(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='fg88-co', defaults={'nom': 'FG88 Co'})[0]
        self.user = User.objects.create_user(
            username='fg88_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(company=self.company, nom='C')
        # Trois chantiers géolocalisés : Casablanca, un voisin proche, Rabat.
        self.casa = Installation.objects.create(
            company=self.company, reference='CHT-CASA', client=self.client_obj,
            gps_lat=Decimal('33.589886'), gps_lng=Decimal('-7.603869'))
        self.casa_voisin = Installation.objects.create(
            company=self.company, reference='CHT-CASA2', client=self.client_obj,
            gps_lat=Decimal('33.600000'), gps_lng=Decimal('-7.610000'))
        self.rabat = Installation.objects.create(
            company=self.company, reference='CHT-RBT', client=self.client_obj,
            gps_lat=Decimal('34.020882'), gps_lng=Decimal('-6.841650'))

    def test_tournee_lists_due_preventive_tickets_with_gps(self):
        _preventif(self.company, self.client_obj, self.casa, 'SAV-1')
        _preventif(self.company, self.client_obj, self.rabat, 'SAV-2')
        r = self.api.get(TOURNEE)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['count'], 2)
        refs = {row['reference'] for row in r.data['results']}
        self.assertEqual(refs, {'SAV-1', 'SAV-2'})
        # Le GPS du chantier est joint (lu via le sélecteur installations).
        casa_row = next(x for x in r.data['results'] if x['reference'] == 'SAV-1')
        self.assertIsNotNone(casa_row['gps_lat'])
        self.assertIsNotNone(casa_row['gps_lng'])

    def test_tournee_excludes_correctif_closed_and_cancelled(self):
        _preventif(self.company, self.client_obj, self.casa, 'SAV-OK')
        # Correctif → exclu.
        Ticket.objects.create(
            company=self.company, client=self.client_obj, installation=self.casa,
            reference='SAV-COR', type=Ticket.Type.CORRECTIF,
            statut=Ticket.Statut.NOUVEAU)
        # Préventif clôturé → exclu.
        _preventif(self.company, self.client_obj, self.casa, 'SAV-CLO',
                   statut=Ticket.Statut.CLOTURE)
        # Préventif annulé → exclu.
        _preventif(self.company, self.client_obj, self.casa, 'SAV-ANN',
                   annule=True)
        r = self.api.get(TOURNEE)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['reference'], 'SAV-OK')

    def test_proximity_sort_from_origin(self):
        # Origine = Casablanca : le voisin proche doit précéder Rabat.
        _preventif(self.company, self.client_obj, self.rabat, 'SAV-RBT')
        _preventif(self.company, self.client_obj, self.casa_voisin, 'SAV-PROCHE')
        r = self.api.get(TOURNEE + '?lat=33.589886&lng=-7.603869')
        order = [row['reference'] for row in r.data['results']]
        self.assertEqual(order, ['SAV-PROCHE', 'SAV-RBT'])
        proche = r.data['results'][0]
        rbt = r.data['results'][1]
        self.assertLess(proche['distance_km'], rbt['distance_km'])

    def test_tickets_without_gps_sorted_last(self):
        no_gps = Installation.objects.create(
            company=self.company, reference='CHT-NOGPS', client=self.client_obj)
        _preventif(self.company, self.client_obj, no_gps, 'SAV-NOGPS')
        _preventif(self.company, self.client_obj, self.casa, 'SAV-GEO')
        r = self.api.get(TOURNEE + '?lat=33.589886&lng=-7.603869')
        order = [row['reference'] for row in r.data['results']]
        self.assertEqual(order[-1], 'SAV-NOGPS')
        nogps = next(x for x in r.data['results'] if x['reference'] == 'SAV-NOGPS')
        self.assertIsNone(nogps['distance_km'])

    def test_tournee_company_isolation(self):
        other = Company.objects.get_or_create(
            slug='fg88-other', defaults={'nom': 'Other'})[0]
        other_client = Client.objects.create(company=other, nom='O')
        other_inst = Installation.objects.create(
            company=other, reference='CHT-O', client=other_client,
            gps_lat=Decimal('31.6'), gps_lng=Decimal('-8.0'))
        _preventif(other, other_client, other_inst, 'SAV-OTHER')
        _preventif(self.company, self.client_obj, self.casa, 'SAV-MINE')
        r = self.api.get(TOURNEE)
        refs = {row['reference'] for row in r.data['results']}
        self.assertEqual(refs, {'SAV-MINE'})


class TestPlanifierTournee(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='fg88p-co', defaults={'nom': 'FG88P Co'})[0]
        self.user = User.objects.create_user(
            username='fg88p_u', password='x', role_legacy='responsable',
            company=self.company)
        self.tech = User.objects.create_user(
            username='fg88p_tech', password='x', role_legacy='technicien',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(company=self.company, nom='C')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT', client=self.client_obj,
            gps_lat=Decimal('33.5'), gps_lng=Decimal('-7.6'))

    def test_bulk_assign_sets_date_technicien_and_planifie(self):
        t1 = _preventif(self.company, self.client_obj, self.inst, 'SAV-1')
        t2 = _preventif(self.company, self.client_obj, self.inst, 'SAV-2')
        when = (date.today() + timedelta(days=3)).isoformat()
        r = self.api.post(PLANIFIER, {
            'ticket_ids': [t1.id, t2.id], 'date_tournee': when,
            'technicien_id': self.tech.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['tickets_planifies'], 2)
        for t in (t1, t2):
            t.refresh_from_db()
            self.assertEqual(t.date_tournee.isoformat(), when)
            self.assertEqual(t.technicien_responsable_id, self.tech.id)
            # NOUVEAU → PLANIFIE.
            self.assertEqual(t.statut, Ticket.Statut.PLANIFIE)

    def test_assign_without_technicien_is_allowed(self):
        t1 = _preventif(self.company, self.client_obj, self.inst, 'SAV-1')
        when = date.today().isoformat()
        r = self.api.post(PLANIFIER, {
            'ticket_ids': [t1.id], 'date_tournee': when}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        t1.refresh_from_db()
        self.assertEqual(t1.date_tournee.isoformat(), when)
        self.assertIsNone(t1.technicien_responsable_id)

    def test_cannot_assign_foreign_technicien(self):
        other = Company.objects.get_or_create(
            slug='fg88p-other', defaults={'nom': 'Other'})[0]
        foreign_tech = User.objects.create_user(
            username='foreign_tech', password='x', role_legacy='technicien',
            company=other)
        t1 = _preventif(self.company, self.client_obj, self.inst, 'SAV-1')
        r = self.api.post(PLANIFIER, {
            'ticket_ids': [t1.id], 'date_tournee': date.today().isoformat(),
            'technicien_id': foreign_tech.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        t1.refresh_from_db()
        self.assertIsNone(t1.date_tournee)

    def test_foreign_ticket_ids_ignored(self):
        other = Company.objects.get_or_create(
            slug='fg88p-other2', defaults={'nom': 'Other2'})[0]
        other_client = Client.objects.create(company=other, nom='O')
        other_inst = Installation.objects.create(
            company=other, reference='CHT-O', client=other_client)
        foreign = _preventif(other, other_client, other_inst, 'SAV-O')
        mine = _preventif(self.company, self.client_obj, self.inst, 'SAV-MINE')
        r = self.api.post(PLANIFIER, {
            'ticket_ids': [mine.id, foreign.id],
            'date_tournee': date.today().isoformat()}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # Seul le ticket de la société est touché.
        self.assertEqual(r.data['tickets_planifies'], 1)
        foreign.refresh_from_db()
        self.assertIsNone(foreign.date_tournee)

    def test_bad_request_without_ticket_ids_or_date(self):
        self.assertEqual(
            self.api.post(PLANIFIER, {
                'date_tournee': date.today().isoformat()},
                format='json').status_code, 400)
        t1 = _preventif(self.company, self.client_obj, self.inst, 'SAV-1')
        self.assertEqual(
            self.api.post(PLANIFIER, {
                'ticket_ids': [t1.id], 'date_tournee': 'pas-une-date'},
                format='json').status_code, 400)

    def test_date_tournee_is_read_only_on_ticket_update(self):
        # FG88 — date_tournee ne peut PAS être posée via PATCH direct du ticket
        # (read-only ; passe uniquement par l'action de planification).
        t1 = _preventif(self.company, self.client_obj, self.inst, 'SAV-1')
        self.api.patch(f'/api/django/sav/tickets/{t1.id}/', {
            'date_tournee': date.today().isoformat()}, format='json')
        # La requête peut réussir mais le champ reste ignoré.
        t1.refresh_from_db()
        self.assertIsNone(t1.date_tournee)
