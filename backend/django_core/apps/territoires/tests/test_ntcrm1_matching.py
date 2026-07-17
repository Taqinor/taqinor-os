"""NTCRM1 — Moteur de territoires : matching + endpoint resoudre/.

3 cas d'acceptation : match géo, match segment, aucun match → repli XSAL11.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.services import default_responsable_for
from apps.roles.models import Role
from apps.territoires.models import Territoire, TerritoireMembre, TerritoireRegle
from apps.territoires.selectors import match_territoire, previsualiser_territoire

User = get_user_model()


def make_commercial(company, username, role):
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


class TerritoireMatchingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM1', slug='taqinor-ntcrm1')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer', 'crm_voir'])
        self.commercial = make_commercial(self.company, 'com_sud', self.role)

    def _territoire_geo(self):
        territoire = Territoire.objects.create(
            company=self.company, nom='Sud — résidentiel',
            type_territoire=Territoire.TypeTerritoire.GEO)
        TerritoireRegle.objects.create(
            territoire=territoire, ordre=1,
            condition={'op': 'and', 'conditions': [
                {'field': 'ville', 'operator': 'eq', 'value': 'Marrakech'},
                {'field': 'type_installation', 'operator': 'eq', 'value': 'residentiel'},
            ]})
        TerritoireMembre.objects.create(territoire=territoire, utilisateur=self.commercial)
        return territoire

    def test_match_geo_lead_marrakech_assigne_au_bon_commercial(self):
        territoire = self._territoire_geo()
        owner = default_responsable_for(self.company, lead_attrs={
            'ville': 'Marrakech', 'type_installation': 'residentiel',
        })
        self.assertEqual(owner, self.commercial)
        matched, membre = match_territoire(self.company, {
            'ville': 'Marrakech', 'type_installation': 'residentiel'})
        self.assertEqual(matched, territoire)

    def test_match_segment_tranche_ca(self):
        territoire = Territoire.objects.create(
            company=self.company, nom='Gros comptes',
            type_territoire=Territoire.TypeTerritoire.SEGMENT)
        TerritoireRegle.objects.create(
            territoire=territoire, ordre=1,
            condition={'field': 'montant_estime', 'operator': 'gte', 'value': 100000})
        membre_gros = make_commercial(self.company, 'com_gros', self.role)
        TerritoireMembre.objects.create(territoire=territoire, utilisateur=membre_gros)

        owner = default_responsable_for(self.company, lead_attrs={
            'montant_estime': 150000})
        self.assertEqual(owner, membre_gros)

    def test_aucun_match_replie_sur_round_robin(self):
        # Territoire actif existe mais ne matche PAS ces attributs.
        self._territoire_geo()
        make_commercial(self.company, 'com_fallback', self.role)
        # lead_attrs qui ne matchent aucune règle -> repli round-robin XSAL11
        # (pick_round_robin_owner exige la permission crm_creer, déjà posée).
        owner = default_responsable_for(self.company, lead_attrs={
            'ville': 'Casablanca', 'type_installation': 'industriel'})
        self.assertIsNotNone(owner)  # repli round-robin, jamais un blocage.

    def test_lead_attrs_none_comportement_inchange(self):
        # Sans lead_attrs, aucune consultation territoire — round-robin direct.
        self._territoire_geo()
        owner = default_responsable_for(self.company)
        self.assertIsNotNone(owner)


class ResoudreEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM1 API', slug='taqinor-ntcrm1-api')
        self.role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=['crm_creer', 'roles_gerer'])
        self.admin = User.objects.create_user(
            username='admin_ntcrm1', password='x', company=self.company,
            role=self.role)
        self.commercial = User.objects.create_user(
            username='com_ntcrm1', password='x', company=self.company, role=self.role)
        self.territoire = Territoire.objects.create(
            company=self.company, nom='Nord')
        TerritoireRegle.objects.create(
            territoire=self.territoire, ordre=1,
            condition={'field': 'ville', 'operator': 'eq', 'value': 'Tanger'})
        TerritoireMembre.objects.create(
            territoire=self.territoire, utilisateur=self.commercial)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.admin)

    def test_resoudre_sans_mutation_pour_un_lead_reel(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead Tanger', ville='Tanger')
        before = TerritoireMembre.objects.get(pk=self.commercial.territoires_membre.first().pk)
        resp = self.client_api.get(
            f'/api/django/territoires/territoires/{self.territoire.pk}/resoudre/',
            {'lead_id': lead.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['matched'])
        self.assertEqual(resp.data['assigne_id'], self.commercial.pk)
        after = TerritoireMembre.objects.get(pk=before.pk)
        self.assertEqual(before.nb_assignations, after.nb_assignations)  # sans mutation

    def test_resoudre_simulation_sans_lead(self):
        resp = self.client_api.get(
            f'/api/django/territoires/territoires/{self.territoire.pk}/resoudre/',
            {'ville': 'Tanger'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['matched'])

    def test_previsualiser_territoire_pure_helper(self):
        matched, membre = previsualiser_territoire(self.territoire, {'ville': 'Tanger'})
        self.assertTrue(matched)
        self.assertEqual(membre.utilisateur, self.commercial)
        matched2, membre2 = previsualiser_territoire(self.territoire, {'ville': 'Rabat'})
        self.assertFalse(matched2)
        self.assertIsNone(membre2)
