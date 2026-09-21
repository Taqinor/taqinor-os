"""NTFPA17 — promouvoir_scenario_en_base : promouvoir un scénario en base crée
un audit-log de la bascule et fige l'ancien budget de base en scénario
archivé, en appliquant les deltas aux lignes réelles."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.audit.models import AuditLog
from apps.fpa.models import (
    Categorie, CycleBudgetaire, Departement, LigneBudgetDepartement,
    LigneScenario, ScenarioBudgetaire,
)
from apps.fpa.services import promouvoir_scenario_en_base

User = get_user_model()


class TestPromouvoirScenario(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa17-co', defaults={'nom': 'NTFPA17 Co'})
        self.user = User.objects.create_user(
            username='ntfpa17-fpa', password='x', company=self.company)
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        self.dept = Departement.objects.create(
            company=self.company, code='CO', nom='Commercial')
        self.ligne = LigneBudgetDepartement.objects.create(
            company=self.company, cycle=self.cycle, departement=self.dept,
            categorie=Categorie.MARKETING, mois=1, montant_prevu=Decimal('100000'))

    def test_promotion_applique_deltas_archive_ancien_et_audite(self):
        ancien = ScenarioBudgetaire.objects.create(
            company=self.company, cycle=self.cycle, nom='Ancienne base',
            est_scenario_base=True)
        nouveau = ScenarioBudgetaire.objects.create(
            company=self.company, cycle=self.cycle, nom='-10% marketing')
        LigneScenario.objects.create(
            company=self.company, scenario=nouveau,
            categorie=Categorie.MARKETING, delta_pct=Decimal('-10'))

        promouvoir_scenario_en_base(nouveau, self.user)

        # La ligne réelle a été modifiée (100000 → 90000).
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.montant_prevu, Decimal('90000'))

        # L'ancien scénario de base est archivé et n'est plus base.
        ancien.refresh_from_db()
        self.assertFalse(ancien.est_scenario_base)
        self.assertEqual(ancien.statut, ScenarioBudgetaire.Statut.ARCHIVE)

        # Le nouveau est base + actif.
        nouveau.refresh_from_db()
        self.assertTrue(nouveau.est_scenario_base)

        # Un audit-log de la bascule existe.
        ct = ContentType.objects.get_for_model(ScenarioBudgetaire)
        self.assertTrue(AuditLog.objects.filter(
            company=self.company, content_type=ct,
            object_id=str(nouveau.pk)).exists())
