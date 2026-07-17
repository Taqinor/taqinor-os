"""NTFPA27 — audit des changements budgétaires : l'historique d'audit montre
qui a modifié quel montant, quand, avant/après valeur."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.audit.models import AuditLog
from apps.fpa.models import (
    Categorie, CycleBudgetaire, Departement, LigneBudgetDepartement,
)

User = get_user_model()


class TestAuditBudget(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa27-co', defaults={'nom': 'NTFPA27 Co'})
        self.user = User.objects.create_user(
            username='ntfpa27-u', password='x', company=self.company,
            is_superuser=True)
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31),
            statut=CycleBudgetaire.Statut.OUVERT_SAISIE)
        self.dept = Departement.objects.create(
            company=self.company, code='IT', nom='IT')
        self.ligne = LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.IT, mois=1, montant_prevu=Decimal('1000'))
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_modification_montant_journalisee_avant_apres(self):
        resp = self.client.patch(
            f'/api/django/fpa/lignes-budget-departement/{self.ligne.pk}/',
            {'montant_prevu': 2500})
        self.assertEqual(resp.status_code, 200, resp.content)
        ct = ContentType.objects.get_for_model(LigneBudgetDepartement)
        entry = AuditLog.objects.filter(
            company=self.company, content_type=ct,
            object_id=str(self.ligne.pk),
            action=AuditLog.Action.UPDATE).order_by('-id').first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.user, self.user)
        self.assertIn('1000', entry.detail)
        self.assertIn('2500', entry.detail)
