"""NTFPA20 — CommentaireVariance : chaque écart significatif peut porter une
explication traçable (qui, quand, pourquoi) consultable."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.fpa.models import Categorie, CommentaireVariance, CycleBudgetaire, Departement

User = get_user_model()


class TestCommentaireVariance(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa20-co', defaults={'nom': 'NTFPA20 Co'})
        self.user = User.objects.create_user(
            username='ntfpa20-u', password='x', company=self.company,
            is_superuser=True)
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        self.dept = Departement.objects.create(
            company=self.company, code='MKT', nom='Marketing')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_creation_pose_auteur_et_societe_server_side(self):
        resp = self.client.post('/api/django/fpa/commentaires-variance/', {
            'cycle': self.cycle.pk, 'departement': self.dept.pk,
            'categorie': Categorie.MARKETING, 'mois': 3,
            'texte': 'Campagne exceptionnelle non budgétée.',
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        commentaire = CommentaireVariance.objects.get()
        self.assertEqual(commentaire.auteur, self.user)
        self.assertEqual(commentaire.company, self.company)

    def test_filtre_par_cellule(self):
        CommentaireVariance.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.MARKETING, mois=3, auteur=self.user, texte='A')
        resp = self.client.get(
            '/api/django/fpa/commentaires-variance/',
            {'cycle': self.cycle.pk, 'mois': 3})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        rows = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(rows), 1)
