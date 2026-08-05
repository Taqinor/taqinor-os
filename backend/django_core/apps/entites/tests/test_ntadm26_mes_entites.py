"""NTADM26 — source de la bascule d'entité de l'en-tête (`mes-entites`).

L'endpoint alimente un filtre de CONFORT : il n'accorde aucun droit, il dit
seulement quelles entités actives l'appelant peut choisir d'afficher.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from ..services import creer_entite, desactiver_entite

User = get_user_model()

URL = '/api/django/entites/entites/mes-entites/'


def _company(nom, slug):
    """Nom ET slug EXPLICITEMENT distincts (le slug est UNIQUE)."""
    return Company.objects.create(nom=nom, slug=slug)


class Ntadm26MesEntitesTests(TestCase):
    def setUp(self):
        self.company = _company('NTADM26 Co', 'ntadm26-co')
        self.filiale_a = creer_entite(self.company, nom='Filiale A', code='FA')
        self.filiale_b = creer_entite(self.company, nom='Filiale B', code='FB')
        self.normal = User.objects.create_user(
            username='ntadm26_normal', password='pw', company=self.company,
            role_legacy='normal')
        self.api = APIClient()
        self.api.force_authenticate(self.normal)

    def test_ouvert_a_tout_collaborateur_interne(self):
        """Le reste du viewset est Administrateur ; cette lecture ne l'est pas."""
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([e['code'] for e in resp.data], ['FA', 'FB'])

    def test_les_entites_desactivees_sont_exclues(self):
        desactiver_entite(self.filiale_b)
        resp = self.api.get(URL)
        self.assertEqual([e['code'] for e in resp.data], ['FA'])

    def test_isolation_multi_tenant(self):
        autre = _company('NTADM26 Autre Co', 'ntadm26-autre-co')
        creer_entite(autre, nom='Étrangère', code='ETR')
        resp = self.api.get(URL)
        self.assertEqual([e['code'] for e in resp.data], ['FA', 'FB'])

    def test_un_role_restreint_ne_voit_que_son_perimetre(self):
        from apps.roles.models import Role

        role = Role.objects.create(
            company=self.company, nom='Commercial Filiale A',
            permissions=['crm_voir'])
        role.entites_visibles.add(self.filiale_a)
        restreint = User.objects.create_user(
            username='ntadm26_restreint', password='pw',
            company=self.company, role=role, role_legacy='normal')
        api = APIClient()
        api.force_authenticate(restreint)
        resp = api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([e['code'] for e in resp.data], ['FA'])

    def test_anonyme_refuse(self):
        resp = APIClient().get(URL)
        self.assertIn(resp.status_code, (401, 403))
