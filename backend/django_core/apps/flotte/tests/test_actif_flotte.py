"""Tests FLOTTE5 — référence d'actif unifiée (ActifFlotte).

Couvre :
- Création d'un ActifFlotte pour un Vehicule et pour un EnginRoulant.
- Validation : exactement un des deux FKs doit être renseigné.
- Isolation multi-tenant : un utilisateur de société B ne voit pas les actifs
  de société A.
- La société est posée côté serveur (jamais lue du corps de requête).
- Filtre ``?type_actif=vehicule`` / ``?type_actif=engin``.
- Propriétés ``type_actif`` et ``label`` calculées sur le modèle.
- Sélecteurs ``actifs_de_la_societe``, ``actif_par_vehicule``,
  ``actif_par_engin``.
- Cascade DELETE : supprimer le Vehicule supprime son ActifFlotte.
"""
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import ActifFlotte, EnginRoulant, Vehicule
from apps.flotte.selectors import (
    actif_par_engin,
    actif_par_vehicule,
    actifs_de_la_societe,
)

User = get_user_model()


# ── Helpers ────────────────────────────────────────────────────────────────


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def make_vehicule(company, immatriculation='AAA-1'):
    return Vehicule.objects.create(
        company=company, immatriculation=immatriculation,
        marque='Dacia', energie='diesel')


def make_engin(company, nom='Nacelle'):
    return EnginRoulant.objects.create(
        company=company, nom=nom, type_engin='nacelle')


# ── Modèle (unité) ─────────────────────────────────────────────────────────


class ActifFlotteModelTests(TestCase):
    def setUp(self):
        self.co_a = make_company('af-model-a', 'AF Model A')
        self.co_b = make_company('af-model-b', 'AF Model B')

    def test_create_for_vehicule(self):
        veh = make_vehicule(self.co_a, 'V-MODEL-1')
        actif = ActifFlotte.objects.create(
            company=self.co_a, vehicule=veh)
        self.assertEqual(actif.type_actif, ActifFlotte.TYPE_VEHICULE)
        self.assertIn('V-MODEL-1', actif.label)
        self.assertEqual(str(actif), f'ActifFlotte(vehicule) — {veh}')

    def test_create_for_engin(self):
        engin = make_engin(self.co_a, 'Groupe 50kVA')
        actif = ActifFlotte.objects.create(
            company=self.co_a, engin=engin)
        self.assertEqual(actif.type_actif, ActifFlotte.TYPE_ENGIN)
        self.assertIn('Groupe 50kVA', actif.label)

    def test_both_fks_raises(self):
        veh = make_vehicule(self.co_a, 'V-BOTH')
        engin = make_engin(self.co_a, 'E-BOTH')
        with self.assertRaises(ValidationError):
            ActifFlotte(
                company=self.co_a, vehicule=veh, engin=engin).full_clean()

    def test_no_fk_raises(self):
        with self.assertRaises(ValidationError):
            ActifFlotte(company=self.co_a).full_clean()

    def test_cross_company_vehicule_raises(self):
        veh_b = make_vehicule(self.co_b, 'V-CROSS')
        with self.assertRaises(ValidationError):
            ActifFlotte(
                company=self.co_a, vehicule=veh_b).full_clean()

    def test_cross_company_engin_raises(self):
        engin_b = make_engin(self.co_b, 'E-CROSS')
        with self.assertRaises(ValidationError):
            ActifFlotte(
                company=self.co_a, engin=engin_b).full_clean()

    def test_cascade_delete_vehicule(self):
        veh = make_vehicule(self.co_a, 'V-CASCADE')
        actif = ActifFlotte.objects.create(company=self.co_a, vehicule=veh)
        veh.delete()
        self.assertFalse(ActifFlotte.objects.filter(pk=actif.pk).exists())

    def test_cascade_delete_engin(self):
        engin = make_engin(self.co_a, 'E-CASCADE')
        actif = ActifFlotte.objects.create(company=self.co_a, engin=engin)
        engin.delete()
        self.assertFalse(ActifFlotte.objects.filter(pk=actif.pk).exists())

    def test_one_to_one_uniqueness(self):
        """Un même véhicule ne peut avoir qu'un seul ActifFlotte."""
        veh = make_vehicule(self.co_a, 'V-UNIQUE')
        ActifFlotte.objects.create(company=self.co_a, vehicule=veh)
        with self.assertRaises(Exception):
            # La contrainte OneToOne lève une IntegrityError / ValidationError.
            ActifFlotte.objects.create(company=self.co_a, vehicule=veh)


# ── Sélecteurs ─────────────────────────────────────────────────────────────


class ActifFlotteSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('af-sel-a', 'AF Sel A')
        self.co_b = make_company('af-sel-b', 'AF Sel B')
        self.veh_a = make_vehicule(self.co_a, 'V-SEL-A')
        self.engin_a = make_engin(self.co_a, 'E-SEL-A')
        self.veh_b = make_vehicule(self.co_b, 'V-SEL-B')
        self.actif_veh = ActifFlotte.objects.create(
            company=self.co_a, vehicule=self.veh_a)
        self.actif_engin = ActifFlotte.objects.create(
            company=self.co_a, engin=self.engin_a)

    def test_actifs_de_la_societe_scope(self):
        qs = actifs_de_la_societe(self.co_a)
        self.assertEqual(qs.count(), 2)
        qs_b = actifs_de_la_societe(self.co_b)
        self.assertEqual(qs_b.count(), 0)

    def test_actif_par_vehicule_found(self):
        result = actif_par_vehicule(self.co_a, self.veh_a.id)
        self.assertEqual(result, self.actif_veh)

    def test_actif_par_vehicule_wrong_company(self):
        result = actif_par_vehicule(self.co_b, self.veh_a.id)
        self.assertIsNone(result)

    def test_actif_par_vehicule_not_found(self):
        result = actif_par_vehicule(self.co_a, 999999)
        self.assertIsNone(result)

    def test_actif_par_engin_found(self):
        result = actif_par_engin(self.co_a, self.engin_a.id)
        self.assertEqual(result, self.actif_engin)

    def test_actif_par_engin_not_found(self):
        result = actif_par_engin(self.co_a, 999999)
        self.assertIsNone(result)


# ── API ────────────────────────────────────────────────────────────────────


class ActifFlotteApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('af-api-a', 'AF API A')
        self.co_b = make_company('af-api-b', 'AF API B')
        self.admin_a = make_user(self.co_a, 'af-api-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'af-api-admin-b', 'admin')
        self.user_a = make_user(self.co_a, 'af-api-user-a', 'normal')
        self.veh_a = make_vehicule(self.co_a, 'V-API-A')
        self.engin_a = make_engin(self.co_a, 'E-API-A')
        self.veh_b = make_vehicule(self.co_b, 'V-API-B')

    def test_create_with_vehicule(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/actifs/', {
            'vehicule': self.veh_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['type_actif'], 'vehicule')
        self.assertIsNotNone(resp.data['label'])
        actif = ActifFlotte.objects.get(id=resp.data['id'])
        self.assertEqual(actif.company_id, self.co_a.id)

    def test_create_with_engin(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/actifs/', {
            'engin': self.engin_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['type_actif'], 'engin')
        actif = ActifFlotte.objects.get(id=resp.data['id'])
        self.assertEqual(actif.company_id, self.co_a.id)

    def test_create_forces_company_server_side(self):
        """L'injection d'une autre société dans le corps est ignorée."""
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/actifs/', {
            'vehicule': self.veh_a.id,
            'company': self.co_b.id,  # tentative d'injection
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        actif = ActifFlotte.objects.get(id=resp.data['id'])
        self.assertEqual(actif.company_id, self.co_a.id)

    def test_create_with_both_fks_rejected(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/actifs/', {
            'vehicule': self.veh_a.id,
            'engin': self.engin_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_create_with_no_fk_rejected(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/actifs/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_create_cross_company_vehicule_rejected(self):
        """Un véhicule d'une autre société est refusé."""
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/actifs/', {
            'vehicule': self.veh_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_tenant_isolation_list(self):
        ActifFlotte.objects.create(company=self.co_a, vehicule=self.veh_a)
        veh_b2 = make_vehicule(self.co_b, 'V-ISO-B')
        ActifFlotte.objects.create(company=self.co_b, vehicule=veh_b2)
        resp = auth(self.admin_a).get('/api/django/flotte/actifs/')
        data = rows(resp)
        ids = [r['id'] for r in data]
        # L'actif de co_a est visible.
        actif_a = ActifFlotte.objects.get(
            company=self.co_a, vehicule=self.veh_a)
        self.assertIn(actif_a.id, ids)
        # L'actif de co_b n'est PAS visible.
        actif_b = ActifFlotte.objects.get(company=self.co_b, vehicule=veh_b2)
        self.assertNotIn(actif_b.id, ids)

    def test_cannot_retrieve_other_company_actif(self):
        veh_b2 = make_vehicule(self.co_b, 'V-XRET-B')
        actif_b = ActifFlotte.objects.create(
            company=self.co_b, vehicule=veh_b2)
        resp = auth(self.admin_a).get(
            f'/api/django/flotte/actifs/{actif_b.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_filter_by_type_actif_vehicule(self):
        ActifFlotte.objects.create(company=self.co_a, vehicule=self.veh_a)
        ActifFlotte.objects.create(company=self.co_a, engin=self.engin_a)
        resp = auth(self.admin_a).get(
            '/api/django/flotte/actifs/?type_actif=vehicule')
        data = rows(resp)
        self.assertTrue(all(r['type_actif'] == 'vehicule' for r in data))
        self.assertTrue(len(data) >= 1)

    def test_filter_by_type_actif_engin(self):
        ActifFlotte.objects.create(company=self.co_a, vehicule=self.veh_a)
        ActifFlotte.objects.create(company=self.co_a, engin=self.engin_a)
        resp = auth(self.admin_a).get(
            '/api/django/flotte/actifs/?type_actif=engin')
        data = rows(resp)
        self.assertTrue(all(r['type_actif'] == 'engin' for r in data))
        self.assertTrue(len(data) >= 1)

    def test_read_allowed_for_any_role(self):
        ActifFlotte.objects.create(company=self.co_a, vehicule=self.veh_a)
        resp = auth(self.user_a).get('/api/django/flotte/actifs/')
        self.assertEqual(resp.status_code, 200)

    def test_write_requires_responsable_or_admin(self):
        resp = auth(self.user_a).post('/api/django/flotte/actifs/', {
            'vehicule': self.veh_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_delete_actif(self):
        actif = ActifFlotte.objects.create(
            company=self.co_a, vehicule=self.veh_a)
        resp = auth(self.admin_a).delete(
            f'/api/django/flotte/actifs/{actif.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(ActifFlotte.objects.filter(pk=actif.pk).exists())
        # Le véhicule cible ne doit PAS avoir été supprimé.
        self.assertTrue(Vehicule.objects.filter(pk=self.veh_a.pk).exists())
