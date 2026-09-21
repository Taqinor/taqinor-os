"""NTMAR16 — Tableau de bord conformité fiscale (feu tricolore par obligation).

Critère : le tableau renvoie un statut coloré par obligation reflétant les
déclarations réellement déposées."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.fiscal.models import EcheanceFiscale, ObligationFiscale
from apps.fiscal.selectors import tableau_conformite

from ._fixtures import make_company


class TableauConformiteTests(TestCase):
    def setUp(self):
        self.company = make_company('fiscal-tab', 'Fiscal Tab')
        self.obligation = ObligationFiscale.objects.create(
            company=self.company, type_obligation=ObligationFiscale.Type.TVA,
            libelle='TVA', periodicite=ObligationFiscale.Periodicite.MENSUELLE,
            regle_echeance='20 du mois suivant')

    def test_en_retard_when_deadline_passed_undeposed(self):
        today = timezone.localdate()
        EcheanceFiscale.objects.create(
            company=self.company, obligation=self.obligation,
            periode_debut=today - timedelta(days=60),
            periode_fin=today - timedelta(days=30),
            date_limite=today - timedelta(days=5))
        lignes = tableau_conformite(self.company)
        ligne = next(
            row for row in lignes
            if row['obligation_id'] == self.obligation.id)
        self.assertEqual(ligne['statut'], 'en_retard')

    def test_a_jour_when_deposed(self):
        today = timezone.localdate()
        EcheanceFiscale.objects.create(
            company=self.company, obligation=self.obligation,
            periode_debut=today - timedelta(days=60),
            periode_fin=today - timedelta(days=30),
            date_limite=today - timedelta(days=25),
            statut=EcheanceFiscale.Statut.DEPOSEE)
        lignes = tableau_conformite(self.company)
        ligne = next(
            row for row in lignes
            if row['obligation_id'] == self.obligation.id)
        self.assertEqual(ligne['statut'], 'a_jour')
        self.assertIsNotNone(ligne['derniere_declaration'])

    def test_echeance_proche(self):
        today = timezone.localdate()
        EcheanceFiscale.objects.create(
            company=self.company, obligation=self.obligation,
            periode_debut=today, periode_fin=today,
            date_limite=today + timedelta(days=5))
        lignes = tableau_conformite(self.company)
        ligne = next(
            row for row in lignes
            if row['obligation_id'] == self.obligation.id)
        self.assertEqual(ligne['statut'], 'echeance_proche')
