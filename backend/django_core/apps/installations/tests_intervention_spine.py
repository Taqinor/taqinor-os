"""F3 — Intervention (sortie chantier) spine tests.

The intervention `statut` is its OWN state machine — changing it must never
touch the chantier status or the lead pipeline (STAGES.py).

Run:
    docker compose exec django_core python manage.py test apps.installations.tests_intervention_spine -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from authentication.models import Company

User = get_user_model()

INTERV = '/api/django/installations/interventions/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class InterventionSpineBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='itv-co', defaults={'nom': 'Itv Co'})[0]
        self.other = Company.objects.get_or_create(
            slug='itv-co-2', defaults={'nom': 'Other Co'})[0]
        self.admin = User.objects.create_user(
            username='itv_admin', password='x', role_legacy='admin',
            company=self.company)
        self.installer = User.objects.create_user(
            username='itv_poseur', password='x', role_legacy='normal',
            company=self.company)
        self.api = auth(self.admin)
        self.client_rec = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            email='k@example.invalid')
        self.chantier = Installation.objects.create(
            company=self.company, reference='CHT-1', client=self.client_rec,
            site_ville='Casablanca', gps_lat=Decimal('33.5731'),
            gps_lng=Decimal('-7.5898'),
            technicien_responsable=self.installer,
            statut=Installation.Statut.PLANIFIE)

    def chantier_other(self):
        c = Client.objects.create(company=self.other, nom='X', prenom='Y',
                                  email='x@example.invalid')
        return Installation.objects.create(
            company=self.other, reference='CHT-O', client=c)


class TestInterventionCreate(InterventionSpineBase):
    def test_defaults_statut_and_equipe_to_installer(self):
        resp = self.api.post(INTERV, {
            'installation': self.chantier.id, 'type_intervention': 'pose',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        interv = Intervention.objects.get(id=resp.data['id'])
        self.assertEqual(interv.statut, Intervention.Statut.A_PREPARER)
        # équipe defaults to the chantier installer (server-side)
        self.assertIn(self.installer, list(interv.equipe.all()))
        self.assertEqual(interv.company, self.company)
        # creation logged to the intervention chatter
        self.assertEqual(
            interv.activites.filter(kind='creation').count(), 1)

    def test_new_types_sav_and_visite_accepted(self):
        for t in ('sav', 'visite', 'mise_en_service'):
            r = self.api.post(INTERV, {
                'installation': self.chantier.id, 'type_intervention': t,
            }, format='json')
            self.assertEqual(r.status_code, 201, r.data)

    def test_derived_chantier_fields_exposed(self):
        r = self.api.post(INTERV, {
            'installation': self.chantier.id, 'type_intervention': 'pose',
        }, format='json')
        self.assertEqual(r.data['client_nom'], 'Karim Bennani')
        self.assertEqual(r.data['site_ville'], 'Casablanca')
        self.assertEqual(str(r.data['gps_lat']), '33.573100')

    def test_cannot_attach_to_other_company_chantier(self):
        foreign = self.chantier_other()
        r = self.api.post(INTERV, {
            'installation': foreign.id, 'type_intervention': 'pose',
        }, format='json')
        # cross-tenant chantier is invisible/invalid
        self.assertIn(r.status_code, (400, 404), r.data)


class TestInterventionStatutIsolation(InterventionSpineBase):
    def test_status_change_logs_and_never_touches_chantier(self):
        interv = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', statut='a_preparer',
            created_by=self.admin)
        chantier_statut_before = self.chantier.statut
        resp = self.api.patch(f'{INTERV}{interv.id}/',
                              {'statut': 'sur_site'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        interv.refresh_from_db()
        self.chantier.refresh_from_db()
        self.assertEqual(interv.statut, 'sur_site')
        # the chantier status is untouched by the intervention state machine
        self.assertEqual(self.chantier.statut, chantier_statut_before)
        # the change is recorded in the intervention chatter
        self.assertTrue(interv.activites.filter(
            kind='modification', field='statut',
            new_value='Sur site').exists())

    def test_filter_by_statut(self):
        Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', statut='a_preparer')
        Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='visite', statut='terminee')
        r = self.api.get(INTERV, {'statut': 'terminee'})
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertTrue(all(x['statut'] == 'terminee' for x in rows))
        self.assertEqual(len(rows), 1)


class TestInterventionChatter(InterventionSpineBase):
    def test_noter_and_historique(self):
        interv = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose')
        note = self.api.post(f'{INTERV}{interv.id}/noter/',
                             {'body': 'RAS sur place'}, format='json')
        self.assertEqual(note.status_code, 201, note.data)
        hist = self.api.get(f'{INTERV}{interv.id}/historique/')
        self.assertEqual(hist.status_code, 200)
        bodies = [a['body'] for a in hist.data]
        self.assertIn('RAS sur place', bodies)

    def test_company_scoped_list(self):
        Intervention.objects.create(
            company=self.other, installation=self.chantier_other(),
            type_intervention='pose')
        Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose')
        r = self.api.get(INTERV)
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual(len(rows), 1)
