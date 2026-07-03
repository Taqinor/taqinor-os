"""Tests XRH6 — historique d'emploi (timeline auditée du dossier employé).

Couvre :
* modifier le poste (ou tout champ suivi) crée une ligne ``DossierActivity``
  old→new horodatée (chatter automatique) ;
* la timeline (``employes/{id}/historique``) est triée récent-d'abord ;
* les notes manuelles (``employes/{id}/noter``) fonctionnent, auteur posé
  côté serveur ;
* isolation multi-société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.rh.models import DossierActivity, DossierEmploye, Poste

User = get_user_model()

EMPLOYES = '/api/django/rh/employes/'


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


class HistoriqueChatterTests(TestCase):
    def setUp(self):
        self.co_a = make_company('hist-a', 'A')
        self.co_b = make_company('hist-b', 'B')
        self.user_a = make_user(self.co_a, 'hist-a')
        self.user_b = make_user(self.co_b, 'hist-b')
        self.emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='E1', nom='X', prenom='Y',
            statut=DossierEmploye.Statut.EMBAUCHE)

    def test_changer_statut_cree_ligne_old_new(self):
        resp = auth(self.user_a).patch(
            f'{EMPLOYES}{self.emp.id}/',
            {'statut': DossierEmploye.Statut.ACTIF}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        act = DossierActivity.objects.get(employe=self.emp, field='statut')
        self.assertEqual(act.type, DossierActivity.Kind.LOG)
        self.assertEqual(act.old_value, 'Embauché')
        self.assertEqual(act.new_value, 'Actif')
        self.assertEqual(act.auteur_id, self.user_a.id)

    def test_changer_poste_cree_ligne(self):
        poste = Poste.objects.create(company=self.co_a, intitule='Poseur')
        resp = auth(self.user_a).patch(
            f'{EMPLOYES}{self.emp.id}/',
            {'poste_ref': poste.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            DossierActivity.objects.filter(
                employe=self.emp, field='poste_ref').exists())

    def test_sans_changement_aucune_ligne(self):
        resp = auth(self.user_a).patch(
            f'{EMPLOYES}{self.emp.id}/', {'nom': self.emp.nom}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            DossierActivity.objects.filter(employe=self.emp).count(), 0)

    def test_historique_trie_recent_dabord(self):
        DossierActivity.objects.create(
            company=self.co_a, employe=self.emp,
            type=DossierActivity.Kind.NOTE, message='Première note')
        DossierActivity.objects.create(
            company=self.co_a, employe=self.emp,
            type=DossierActivity.Kind.NOTE, message='Deuxième note')
        resp = auth(self.user_a).get(f'{EMPLOYES}{self.emp.id}/historique/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(resp.data[0]['message'], 'Deuxième note')

    def test_noter_cree_note_auteur_serveur(self):
        resp = auth(self.user_a).post(
            f'{EMPLOYES}{self.emp.id}/noter/',
            {'message': 'Appel RH ok'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['type'], 'note')
        self.assertEqual(resp.data['message'], 'Appel RH ok')
        act = DossierActivity.objects.get(id=resp.data['id'])
        self.assertEqual(act.auteur_id, self.user_a.id)

    def test_noter_vide_400(self):
        resp = auth(self.user_a).post(
            f'{EMPLOYES}{self.emp.id}/noter/', {'message': '  '}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_tenant_cross_company_404(self):
        resp = auth(self.user_b).get(f'{EMPLOYES}{self.emp.id}/historique/')
        self.assertEqual(resp.status_code, 404)

    def test_isolation_societe_liste(self):
        DossierActivity.objects.create(
            company=self.co_a, employe=self.emp,
            type=DossierActivity.Kind.NOTE, message='Note A')
        emp_b = DossierEmploye.objects.create(
            company=self.co_b, matricule='B1', nom='X', prenom='Y')
        DossierActivity.objects.create(
            company=self.co_b, employe=emp_b,
            type=DossierActivity.Kind.NOTE, message='Note B')
        resp = auth(self.user_a).get(f'{EMPLOYES}{self.emp.id}/historique/')
        messages = [row['message'] for row in resp.data]
        self.assertEqual(messages, ['Note A'])
