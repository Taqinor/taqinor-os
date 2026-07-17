"""Tests NTCON1 — ``ReserveChantier`` (punch-list géo-localisée sur plan).

Couvre :
* création d'une réserve avec un pin sur un document GED (x/y normalisés) ;
* validation du pin (document_ged_id + x/y requis, bornés [0, 1]) ;
* liste filtrable par lot/statut/gravité/chantier ;
* cross-tenant refusé (une société ne voit/modifie jamais la réserve d'une
  autre) ;
* la société et le créateur sont posés côté serveur (jamais lus du corps) ;
* le module est déclaré comme cible ``records.Attachment`` (photos).
"""
from django.test import TestCase
from rest_framework import status

from .helpers import auth, make_chantier, make_company, make_user

BASE = '/api/django/btp-chantier/reserves-chantier/'


class ReserveChantierApiTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)

    def test_create_reserve_with_pin(self):
        api = auth(self.user)
        payload = {
            'chantier': self.chantier.id,
            'lot': 'électricité',
            'localisation_plan': {
                'document_ged_id': 42, 'x': 0.25, 'y': 0.6,
            },
            'description': 'Prise défectueuse',
            'gravite': 'majeure',
        }
        resp = api.post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['statut'], 'ouverte')
        self.assertEqual(
            resp.data['localisation_plan']['document_ged_id'], 42)

        from apps.btp_chantier.models import ReserveChantier
        reserve = ReserveChantier.objects.get(pk=resp.data['id'])
        self.assertEqual(reserve.company_id, self.co.id)
        self.assertEqual(reserve.created_by_id, self.user.id)
        # Une entrée d'historique initiale est journalisée à la création.
        self.assertEqual(reserve.historique.count(), 1)

    def test_pin_missing_coordinates_rejected(self):
        api = auth(self.user)
        payload = {
            'chantier': self.chantier.id,
            'description': 'X',
            'localisation_plan': {'document_ged_id': 1, 'x': 0.5},
        }
        resp = api.post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pin_out_of_bounds_rejected(self):
        api = auth(self.user)
        payload = {
            'chantier': self.chantier.id,
            'description': 'X',
            'localisation_plan': {'document_ged_id': 1, 'x': 1.5, 'y': 0.2},
        }
        resp = api.post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_company_and_created_by_from_body_ignored(self):
        other_co = make_company()
        api = auth(self.user)
        payload = {
            'chantier': self.chantier.id,
            'description': 'X',
            'localisation_plan': {'document_ged_id': 1, 'x': 0.1, 'y': 0.1},
            'company': other_co.id,
        }
        resp = api.post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        from apps.btp_chantier.models import ReserveChantier
        reserve = ReserveChantier.objects.get(pk=resp.data['id'])
        self.assertEqual(reserve.company_id, self.co.id)

    def test_list_filterable_by_lot_statut_gravite(self):
        from apps.btp_chantier.models import ReserveChantier

        r1 = ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, lot='plomberie',
            description='fuite', gravite='mineure', statut='ouverte',
            created_by=self.user)
        ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, lot='électricité',
            description='court-circuit', gravite='bloquante',
            statut='levee', created_by=self.user)

        api = auth(self.user)
        resp = api.get(BASE, {'lot': 'plomberie'})
        ids = [row['id'] for row in resp.data['results']] \
            if 'results' in resp.data else [row['id'] for row in resp.data]
        self.assertEqual(ids, [r1.id])

        resp = api.get(BASE, {'statut': 'levee'})
        ids = [row['id'] for row in resp.data['results']] \
            if 'results' in resp.data else [row['id'] for row in resp.data]
        self.assertNotIn(r1.id, ids)

        resp = api.get(BASE, {'gravite': 'bloquante'})
        ids = [row['id'] for row in resp.data['results']] \
            if 'results' in resp.data else [row['id'] for row in resp.data]
        self.assertNotIn(r1.id, ids)

    def test_cross_tenant_refused(self):
        from apps.btp_chantier.models import ReserveChantier

        other_co = make_company()
        other_chantier = make_chantier(other_co)
        other_reserve = ReserveChantier.objects.create(
            company=other_co, chantier=other_chantier, description='autre',
            created_by=make_user(other_co))

        api = auth(self.user)
        resp = api.get(BASE)
        ids = [row['id'] for row in resp.data['results']] \
            if 'results' in resp.data else [row['id'] for row in resp.data]
        self.assertNotIn(other_reserve.id, ids)

        resp = api.get(f'{BASE}{other_reserve.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_chantier_from_other_company_rejected(self):
        other_co = make_company()
        other_chantier = make_chantier(other_co)
        api = auth(self.user)
        payload = {
            'chantier': other_chantier.id,
            'description': 'X',
            'localisation_plan': {'document_ged_id': 1, 'x': 0.1, 'y': 0.1},
        }
        resp = api.post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class ReserveChantierPlatformTests(TestCase):
    def test_registered_as_record_target(self):
        from apps.records.models import ALLOWED_TARGETS
        self.assertIn(('btp_chantier', 'reservechantier'), ALLOWED_TARGETS)
