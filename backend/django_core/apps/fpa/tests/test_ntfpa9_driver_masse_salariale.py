"""NTFPA9 — driver effectifs → masse salariale : ajouter des recrutements/
départs recalcule la courbe mensuelle de masse salariale chargée."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import ParametrePaie, ProfilPaie
from apps.rh.models import DossierEmploye
from apps.fpa.services import projeter_masse_salariale


class TestProjeterMasseSalariale(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa9-co', defaults={'nom': 'NTFPA9 Co'})
        ParametrePaie.objects.create(
            company=self.company, taux_cnss_patronal=Decimal('8.98'),
            taux_amo_patronal=Decimal('2.26'),
            taux_allocations_familiales=Decimal('6.4'),
            taux_formation_pro=Decimal('1.6'))
        dossier = DossierEmploye.objects.create(
            company=self.company, matricule='NTFPA9-1', nom='Test', prenom='FPA')
        ProfilPaie.objects.create(
            company=self.company, employe=dossier,
            salaire_base=Decimal('10000'), actif=True)

    def test_recrutements_et_depart_recalculent_la_courbe(self):
        hypotheses = [
            {'salaire_brut_estime': 5000, 'date_effet': date(2027, 3, 1),
             'type_mouvement': 'embauche'},
            {'salaire_brut_estime': 4000, 'date_effet': date(2027, 3, 1),
             'type_mouvement': 'embauche'},
            {'salaire_brut_estime': 3000, 'date_effet': date(2027, 6, 1),
             'type_mouvement': 'depart'},
        ]
        rows = projeter_masse_salariale(
            self.company, None, date(2027, 1, 1), date(2027, 12, 1),
            hypothese_recrutements=hypotheses)
        self.assertEqual(len(rows), 12)
        # Facteur de charge = 1 + (8.98+2.26+6.4+1.6)/100 = 1.1924.
        facteur = Decimal('1.1924')
        # Janvier : base 10000 seul.
        jan = rows[0]['masse_salariale_chargee']
        self.assertEqual(jan, (Decimal('10000') * facteur).quantize(Decimal('0.01')))
        # Mars : base + 5000 + 4000 = 19000.
        mars = rows[2]['masse_salariale_chargee']
        self.assertEqual(mars, (Decimal('19000') * facteur).quantize(Decimal('0.01')))
        # Juin : 19000 - 3000 = 16000.
        juin = rows[5]['masse_salariale_chargee']
        self.assertEqual(juin, (Decimal('16000') * facteur).quantize(Decimal('0.01')))
