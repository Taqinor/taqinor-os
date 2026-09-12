"""Tests NTHCM1 — ligne hiérarchique ``DossierEmploye.manager``.

Couvre :
* assigner un manager crée le lien ;
* un cycle A→B→A est rejeté 400 (et la chaîne complète, pas le lien direct) ;
* un manager d'une AUTRE société est rejeté 400 ;
* ``employes/{id}/subordonnes/`` liste les rattachés DIRECTS (non récursif) ;
* le changement de manager est journalisé au chatter (XRH6) ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierActivity, DossierEmploye

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_employe(company, matricule, nom='Test', prenom='Employe', **kwargs):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom=nom, prenom=prenom, **kwargs)


class ManagerModelTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm1-a', 'A')
        self.chef = make_employe(self.co, 'M-001', nom='Chef')
        self.employe = make_employe(self.co, 'M-002', nom='Employe')

    def test_assigner_manager_cree_le_lien(self):
        self.employe.manager = self.chef
        self.employe.clean()
        self.employe.save()
        self.assertEqual(
            list(self.chef.subordonnes.all()), [self.employe])

    def test_auto_manager_refuse(self):
        self.employe.manager = self.employe
        with self.assertRaises(ValidationError):
            self.employe.clean()

    def test_cycle_direct_refuse(self):
        self.employe.manager = self.chef
        self.employe.save()
        self.chef.manager = self.employe
        with self.assertRaises(ValidationError):
            self.chef.clean()

    def test_cycle_indirect_refuse(self):
        """A→B→C→A : la remontée doit parcourir TOUTE la chaîne."""
        c = make_employe(self.co, 'M-003', nom='Troisieme')
        self.employe.manager = self.chef
        self.employe.save()
        c.manager = self.employe
        c.save()
        self.chef.manager = c
        with self.assertRaises(ValidationError):
            self.chef.clean()

    def test_manager_autre_societe_refuse(self):
        co_b = make_company('nthcm1-b', 'B')
        etranger = make_employe(co_b, 'M-099', nom='Etranger')
        self.employe.manager = etranger
        with self.assertRaises(ValidationError):
            self.employe.clean()

    def test_manager_nul_reste_valide(self):
        self.employe.manager = None
        self.employe.clean()  # ne lève rien


class ManagerApiTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm1-api', 'API')
        self.rh = make_user(self.co, 'nthcm1-rh')
        self.api = auth(self.rh)
        self.chef = make_employe(self.co, 'A-001', nom='Chef')
        self.employe = make_employe(self.co, 'A-002', nom='Employe')

    def _patch(self, employe, data):
        return self.api.patch(
            f'/api/django/rh/employes/{employe.id}/', data, format='json')

    def test_assignation_manager_ok(self):
        resp = self._patch(self.employe, {'manager': self.chef.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employe.refresh_from_db()
        self.assertEqual(self.employe.manager_id, self.chef.id)

    def test_cycle_rejete_400(self):
        self._patch(self.employe, {'manager': self.chef.id})
        resp = self._patch(self.chef, {'manager': self.employe.id})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('manager', resp.data)

    def test_manager_autre_societe_rejete_400(self):
        co_b = make_company('nthcm1-api-b', 'B')
        etranger = make_employe(co_b, 'B-001', nom='Etranger')
        resp = self._patch(self.employe, {'manager': etranger.id})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('manager', resp.data)

    def test_subordonnes_liste_les_rattaches_directs(self):
        autre = make_employe(self.co, 'A-003', nom='Autre')
        petit_fils = make_employe(self.co, 'A-004', nom='PetitFils')
        self._patch(self.employe, {'manager': self.chef.id})
        self._patch(autre, {'manager': self.chef.id})
        self._patch(petit_fils, {'manager': self.employe.id})

        resp = self.api.get(
            f'/api/django/rh/employes/{self.chef.id}/subordonnes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {ligne['id'] for ligne in resp.data}
        # NON récursif : le petit-fils n'apparaît PAS.
        self.assertEqual(ids, {self.employe.id, autre.id})

    def test_subordonnes_vide_sans_rattachement(self):
        resp = self.api.get(
            f'/api/django/rh/employes/{self.employe.id}/subordonnes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(list(resp.data), [])

    def test_changement_manager_journalise_au_chatter(self):
        self._patch(self.employe, {'manager': self.chef.id})
        logs = DossierActivity.objects.filter(
            employe=self.employe, field='manager')
        self.assertEqual(logs.count(), 1)
        self.assertIn('Chef', logs.first().new_value)

    def test_isolation_societe_sur_subordonnes(self):
        co_b = make_company('nthcm1-api-c', 'C')
        rh_b = make_user(co_b, 'nthcm1-rh-c')
        resp = auth(rh_b).get(
            f'/api/django/rh/employes/{self.chef.id}/subordonnes/')
        self.assertEqual(resp.status_code, 404)
