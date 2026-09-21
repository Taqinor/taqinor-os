"""Tests de la consommation matière vs BoM (PROJ25).

La BoM prévisionnelle est assimilée aux lignes de budget « matériel » du budget
de référence ; le consommé réel passe par un sélecteur cross-app (chantiers /
achats) et DÉGRADE proprement à 0 + note tant qu'aucune app cible n'expose ce
montant (frontière cross-app — aucun import des modèles d'une autre app).

Couvre : BoM = matériel budgété ; consommé dégradé à 0 + note (avec/sans liens) ;
écart et écart_pct (None si BoM nulle, garde division-par-zéro) ; endpoint ;
scoping société (404 cross-tenant) ; accès Administrateur/Responsable (403 pour
``normal``).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    BudgetProjet,
    LigneBudgetProjet,
    Projet,
    ProjetChantier,
)

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


class ConsommationMatiereSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-cm-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-CM', nom='Projet matière')

    def _budget_materiel(self, montant):
        budget = BudgetProjet.objects.create(
            company=self.co, projet=self.projet, version=1,
            statut=BudgetProjet.Statut.VALIDE)
        LigneBudgetProjet.objects.create(
            company=self.co, budget=budget,
            categorie=LigneBudgetProjet.Categorie.MATERIEL,
            libelle='Panneaux', montant_prevu=Decimal(montant))
        return budget

    def test_bom_depuis_budget_materiel(self):
        self._budget_materiel('50000')
        data = selectors.consommation_matiere_vs_bom(self.projet)
        self.assertEqual(data['bom_prevu'], Decimal('50000'))
        self.assertEqual(data['consomme'], Decimal('0'))
        self.assertEqual(data['ecart'], Decimal('50000'))
        # Écart % = (50000 - 0) / 50000 * 100 = 100.00.
        self.assertEqual(data['ecart_pct'], Decimal('100.00'))
        self.assertEqual(data['source'], 'degrade')

    def test_bom_nulle_ecart_pct_none(self):
        data = selectors.consommation_matiere_vs_bom(self.projet)
        self.assertEqual(data['bom_prevu'], Decimal('0'))
        self.assertIsNone(data['ecart_pct'])

    def test_note_avec_chantier_rattache(self):
        ProjetChantier.objects.create(
            company=self.co, projet=self.projet, chantier_id=42)
        data = selectors.consommation_matiere_vs_bom(self.projet)
        self.assertIn('chantier', data['note'])
        self.assertEqual(data['consomme'], Decimal('0'))


class ConsommationMatiereApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-cm-a', 'A')
        self.co_b = make_company('gp-cm-b', 'B')
        self.user_a = make_user(self.co_a, 'cm-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A')
        budget = BudgetProjet.objects.create(
            company=self.co_a, projet=self.projet, version=1,
            statut=BudgetProjet.Statut.VALIDE)
        LigneBudgetProjet.objects.create(
            company=self.co_a, budget=budget,
            categorie=LigneBudgetProjet.Categorie.MATERIEL,
            libelle='M', montant_prevu=Decimal('1000'))

    def test_endpoint(self):
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{self.projet.id}/consommation-matiere/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['bom_prevu'], '1000.00')
        self.assertEqual(resp.data['consomme'], '0')
        self.assertEqual(resp.data['source'], 'degrade')

    def test_cross_tenant_404(self):
        autre = Projet.objects.create(company=self.co_b, code='P-B', nom='B')
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{autre.id}/consommation-matiere/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'cm-normal', role='normal')
        api = auth(normal)
        resp = api.get(f'{self.BASE}{self.projet.id}/consommation-matiere/')
        self.assertEqual(resp.status_code, 403)
