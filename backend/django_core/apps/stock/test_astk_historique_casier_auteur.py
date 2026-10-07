"""ASTK91 — l'historique de casier nomme l'auteur de la modification.

Run :
    python manage.py test apps.stock.test_astk_historique_casier_auteur -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import BinLocation
from apps.stock.models import EmplacementStock, HistoriqueCasier
from authentication.models import Company

User = get_user_model()


class HistoriqueCasierAuteurTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='astk91-co', defaults={'nom': 'ASTK91 Co'})
        self.user = User.objects.create_user(
            username='astk91_resp', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt ASTK91', is_principal=True)
        self.casier = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='H1', zone='', ordre=10)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_patch_casier_trace_l_auteur(self):
        r = self.api.patch(
            f'/api/django/installations/bin-locations/{self.casier.id}/',
            {'zone': 'Z9'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

        # Persistance : relu depuis la base puis via l'API.
        ligne = HistoriqueCasier.objects.get(
            bin=self.casier, champ='zone')
        self.assertEqual(ligne.nouvelle_valeur, 'Z9')
        self.assertEqual(ligne.auteur_id, self.user.id)
        hist = self.api.get(
            f'/api/django/stock/casiers/{self.casier.id}/historique/').json()
        modif = [x for x in hist['lignes'] if x['champ'] == 'zone'][0]
        self.assertEqual(modif['auteur'], self.user.username)

    def test_hors_requete_auteur_null(self):
        self.casier.zone = 'Q1'
        self.casier.save()
        ligne = HistoriqueCasier.objects.get(bin=self.casier, champ='zone')
        self.assertIsNone(ligne.auteur_id)
