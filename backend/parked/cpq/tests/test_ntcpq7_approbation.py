"""NTCPQ7 — matrice d'approbation par profondeur de remise + blocage envoi."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.cpq.models import RegleApprobationRemise, EtapeApprobationDevis
from apps.cpq import services, selectors
from apps.ventes.services import mark_devis_sent
from testkit.factories import CompanyFactory, DevisFactory


class TestApprobationRemise(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        # Palier : remise 20-100% → 2 approbateurs niveau direction.
        RegleApprobationRemise.objects.create(
            company=self.company, libelle='Remise forte',
            remise_min_pct=Decimal('20'), remise_max_pct=Decimal('100'),
            niveau_approbation=RegleApprobationRemise.NiveauApprobation.DIRECTION,
            nombre_approbateurs=2)

    def test_devis_25pct_route_vers_2_approbateurs(self):
        devis = DevisFactory(
            company=self.company, remise_globale=Decimal('25'))
        etapes = services.lancer_approbation_devis(devis)
        self.assertEqual(len(etapes), 2)
        self.assertEqual(
            etapes[0].niveau_approbation,
            RegleApprobationRemise.NiveauApprobation.DIRECTION)

    def test_devis_8pct_aucune_approbation(self):
        devis = DevisFactory(
            company=self.company, remise_globale=Decimal('8'))
        etapes = services.lancer_approbation_devis(devis)
        self.assertEqual(etapes, [])

    def test_envoi_bloque_tant_que_etape_en_attente(self):
        devis = DevisFactory(
            company=self.company, remise_globale=Decimal('25'))
        services.lancer_approbation_devis(devis)
        with self.assertRaises(ValidationError):
            mark_devis_sent(devis=devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'brouillon')  # jamais envoyé

    def test_envoi_libre_apres_approbation(self):
        devis = DevisFactory(
            company=self.company, remise_globale=Decimal('25'))
        etapes = services.lancer_approbation_devis(devis)
        for e in etapes:
            e.statut = EtapeApprobationDevis.Statut.APPROUVE
            e.save()
        self.assertIsNone(selectors.premiere_etape_en_attente(devis))
        mark_devis_sent(devis=devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'envoye')

    def test_lancer_idempotent(self):
        devis = DevisFactory(
            company=self.company, remise_globale=Decimal('25'))
        services.lancer_approbation_devis(devis)
        services.lancer_approbation_devis(devis)
        self.assertEqual(
            EtapeApprobationDevis.objects.filter(devis=devis).count(), 2)
