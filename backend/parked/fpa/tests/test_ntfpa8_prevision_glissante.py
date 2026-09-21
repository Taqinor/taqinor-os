"""NTFPA8 — PrevisionGlissante : régénération préserve les ajustements manuels
(source=manuel jamais écrasée)."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.fpa.models import (
    Categorie, LignePrevisionGlissante, PrevisionGlissante, SourcePrevision,
)
from apps.fpa.services import generer_prevision_glissante


class TestPrevisionGlissante(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa8-fpa-co', defaults={'nom': 'NTFPA8 FPA Co'})
        self.prevision = PrevisionGlissante.objects.create(
            company=self.company, date_reference=date(2027, 4, 1),
            horizon_mois=12)

    def test_generation_cree_les_points(self):
        generer_prevision_glissante(self.prevision)
        # 12 mois × 6 catégories.
        self.assertEqual(
            LignePrevisionGlissante.objects.filter(prevision=self.prevision).count(),
            12 * len(Categorie.choices))

    def test_regeneration_preserve_ajustement_manuel(self):
        generer_prevision_glissante(self.prevision)
        ligne = LignePrevisionGlissante.objects.filter(
            prevision=self.prevision, mois_relatif=1,
            categorie=Categorie.MARKETING).first()
        ligne.montant_prevu = Decimal('55555')
        ligne.source = SourcePrevision.MANUEL
        ligne.save()

        generer_prevision_glissante(self.prevision)
        ligne.refresh_from_db()
        self.assertEqual(ligne.montant_prevu, Decimal('55555'))
        self.assertEqual(ligne.source, SourcePrevision.MANUEL)
