"""ALEA16 — ``LeadSerializer.entite`` bornée à la société, ``tiers`` en
lecture seule (miroir serveur ARC56).

Rejoue la sonde V3 LFICHE-2 / V4 LCOUT-5 : un PATCH {entite: <EntiteB>} puis
{tiers: <TiersB>} rendait 200 et STOCKAIT les ids d'une autre société.
"""
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from authentication.models import Company

User = get_user_model()

ID_ABSENT = 99999999


def _entite(company, code):
    return django_apps.get_model('entites', 'Entite').objects.create(
        company=company, nom=f'Entité {code}', code=code)


def _tiers(company, nom):
    return django_apps.get_model('tiers', 'Tiers').objects.create(
        company=company, nom=nom)


class LeadFkSocieteTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='ALEA16 A', slug='alea16-a')
        self.b = Company.objects.create(nom='ALEA16 B', slug='alea16-b')
        role = Role.objects.create(
            company=self.a, nom='Administrateur ALEA16',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Administrateur']))
        self.admin = User.objects.create_user(
            username='alea16-admin', password='x', company=self.a,
            role_legacy='admin', role=role)
        self.tiers_a = _tiers(self.a, 'Tiers maison')
        self.lead = Lead.objects.create(company=self.a, nom='Lead A',
                                        tiers=self.tiers_a)
        self.entite_b = _entite(self.b, 'B1')
        self.tiers_b = _tiers(self.b, 'Tiers voisin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.url = f'/api/django/crm/leads/{self.lead.id}/'

    def _message(self, resp, champ, pk):
        self.assertEqual(resp.status_code, 400, resp.data)
        return [str(m).replace(str(pk), '<id>') for m in resp.data[champ]]

    def test_entite_etrangere_refusee_comme_absente(self):
        etrangere = self.api.patch(self.url, {'entite': self.entite_b.id},
                                   format='json')
        absente = self.api.patch(self.url, {'entite': ID_ABSENT},
                                 format='json')
        self.assertEqual(self._message(etrangere, 'entite', self.entite_b.id),
                         self._message(absente, 'entite', ID_ABSENT))
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.entite_id)
        self.assertFalse(
            Lead.objects.filter(company=self.a)
            .exclude(entite__company=self.a).exclude(entite=None).exists())

    def test_tiers_lecture_seule(self):
        resp = self.api.patch(self.url, {'tiers': self.tiers_b.id},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['tiers'], self.tiers_a.id)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.tiers_id, self.tiers_a.id)

    def test_entite_propre_acceptee(self):
        entite_a = _entite(self.a, 'A1')
        resp = self.api.patch(self.url, {'entite': entite_a.id},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.entite_id, entite_a.id)
