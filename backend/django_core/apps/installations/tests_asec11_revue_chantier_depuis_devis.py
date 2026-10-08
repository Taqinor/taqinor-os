"""ASEC11-revue — le passage devis → chantier reste ouvert aux rôles VENTES.

ASEC11 a résolu ``IsResponsableOrAdmin`` au module de la vue : les actions
``creer-depuis-devis`` (POST) et ``a-facturer`` (GET) du ChantierViewSet
relèvent du module ``installations``, que Commercial, Commercial responsable
et Admin Ventes ne portent pas → « Créer le chantier » (DevisList, onglet
Devis du CRM) répondait 403. Ces deux actions sont désormais gardées par le
code ventes ``ventes_creer`` (OU l'ancienne garde), sans ouvrir aux rôles
ventes les autres écritures du chantier.

Run :
    python manage.py test apps.installations.tests_asec11_revue_chantier_depuis_devis
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.installations.models import Installation
from apps.roles.models import Role
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

URL_CREER = '/api/django/installations/chantiers/creer-depuis-devis/'
URL_A_FACTURER = '/api/django/installations/chantiers/a-facturer/'
ROLES_VENTES = ('Commercial', 'Commercial responsable', 'Admin Ventes')


class ChantierDepuisDevisRolesVentesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='ASEC11 revue', slug='asec11-revue-co')
        call_command('init_roles', verbosity=0)
        cls.roles = {r.nom: r for r in Role.objects.filter(company=cls.company)}

    def _api(self, nom_role):
        user = User.objects.create_user(
            username=f'asec11r_{nom_role.replace(" ", "_").lower()}',
            password='x', company=self.company, role=self.roles[nom_role])
        api = APIClient()
        api.force_authenticate(user)
        return api

    def _devis_accepte(self, suffixe):
        client = Client.objects.create(
            company=self.company, nom='Client', prenom=suffixe,
            email=f'asec11r-{suffixe}@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Client', prenom=suffixe,
            stage='SIGNED', type_installation='residentiel')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-ASEC11R-{suffixe}',
            client=client, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')

    def test_chaque_role_ventes_cree_le_chantier(self):
        for i, nom_role in enumerate(ROLES_VENTES):
            with self.subTest(role=nom_role):
                devis = self._devis_accepte(f'v{i}')
                resp = self._api(nom_role).post(
                    URL_CREER, {'devis': devis.id}, format='json')
                self.assertEqual(resp.status_code, 201,
                                 getattr(resp, 'data', None))
                inst = Installation.objects.get(pk=resp.data['id'])
                self.assertEqual(inst.company_id, self.company.id)

    def test_chaque_role_ventes_lit_a_facturer(self):
        for nom_role in ROLES_VENTES:
            with self.subTest(role=nom_role):
                resp = self._api(nom_role).get(URL_A_FACTURER)
                self.assertEqual(resp.status_code, 200,
                                 getattr(resp, 'data', None))

    def test_roles_sans_ventes_toujours_refuses(self):
        # Commercial terrain / Viewer : ni code installations d'écriture ni
        # ``ventes_creer`` → la création reste refusée.
        for i, nom_role in enumerate(('Commercial terrain', 'Viewer')):
            with self.subTest(role=nom_role):
                devis = self._devis_accepte(f'r{i}')
                resp = self._api(nom_role).post(
                    URL_CREER, {'devis': devis.id}, format='json')
                self.assertEqual(resp.status_code, 403)

    def test_role_ventes_reste_refuse_sur_les_autres_ecritures(self):
        # Pas d'élargissement : l'annulation d'un chantier reste une écriture
        # du module installations.
        devis = self._devis_accepte('w')
        api = self._api('Commercial')
        cree = api.post(URL_CREER, {'devis': devis.id}, format='json')
        self.assertEqual(cree.status_code, 201, getattr(cree, 'data', None))
        resp = api.post(
            f'/api/django/installations/chantiers/{cree.data["id"]}/annuler/',
            {'motif': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)
