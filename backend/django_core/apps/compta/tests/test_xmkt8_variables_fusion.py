"""XMKT8 — Variables de fusion dans les campagnes avec fallback.

Couvre : substitution des variables connues depuis le lead, fallback par
variable quand le champ est vide, variable inconnue = erreur claire à la
validation, aperçu fusionné pour un contact d'exemple, jamais de donnée
interne (prix_achat) disponible.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Campagne
from apps.crm.models import Lead

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


class VariablesFusionTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt8', 'XMKT8')
        self.user = make_user(self.co, 'xmkt8-user')

    def test_rendu_substitue_les_champs_connus(self):
        lead = Lead.objects.create(
            company=self.co, nom='Alami', prenom='Youssef', ville='Rabat')
        rendu = services.rendre_variables_fusion(
            'Bonjour {prenom}, offre spéciale à {ville} !', self.co, lead.id)
        self.assertEqual(rendu, 'Bonjour Youssef, offre spéciale à Rabat !')

    def test_fallback_quand_champ_vide(self):
        lead = Lead.objects.create(company=self.co, nom='Alami')  # pas de ville
        rendu = services.rendre_variables_fusion(
            'Bonjour de {ville}', self.co, lead.id, fallback='notre équipe')
        self.assertEqual(rendu, 'Bonjour de notre équipe')

    def test_variable_inconnue_leve_erreur(self):
        with self.assertRaises(ValueError):
            services.valider_variables_fusion('Bonjour {prix_achat}')

    def test_prix_achat_jamais_disponible(self):
        self.assertNotIn('prix_achat', services.MERGE_VARIABLES)

    def test_lead_dune_autre_societe_renvoie_champs_vides(self):
        other = make_company('xmkt8-b', 'XMKT8-B')
        lead = Lead.objects.create(company=other, nom='Autre', prenom='X')
        rendu = services.rendre_variables_fusion(
            'Bonjour {prenom}', self.co, lead.id, fallback='cher client')
        self.assertEqual(rendu, 'Bonjour cher client')

    def test_apercu_fusion_endpoint(self):
        lead = Lead.objects.create(
            company=self.co, nom='Alami', prenom='Youssef')
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL,
            corps='Bonjour {prenom} !')
        api = auth(self.user)
        resp = api.get(
            f'/api/django/compta/campagnes/{camp.id}/apercu_fusion/'
            f'?lead_id={lead.id}')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['corps_fusionne'], 'Bonjour Youssef !')

    def test_creation_campagne_rejette_variable_inconnue(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/campagnes/', {
            'nom': 'C', 'canal': 'email', 'corps': 'Bonjour {prix_achat}',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
