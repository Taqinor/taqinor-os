"""Tests XACC15 — Charges constatées d'avance (étalement des charges prépayées).

Couvre : une assurance annuelle étalée sur 12 mois génère 12 dotations égales
(arrondi géré sur la dernière), le solde 3491 = restant exact après posting
partiel, et l'écriture d'origine + de dotation sont équilibrées.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import ChargeConstateeAvance, LigneEcriture


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class EtalementChargeTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc15-svc', 'XACC15 Svc')

    def test_assurance_annuelle_12_dotations_egales(self):
        charge = services.etaler_charge_avance(
            self.co, montant_total=Decimal('12000.00'),
            date_debut=date(2026, 1, 1), nb_mois=12,
            libelle='Assurance flotte 2026')
        self.assertEqual(charge.dotations.count(), 12)
        total = sum((d.montant for d in charge.dotations.all()), Decimal('0'))
        self.assertEqual(total, Decimal('12000.00'))
        montants = [d.montant for d in charge.dotations.order_by('numero')]
        self.assertTrue(all(m == Decimal('1000.00') for m in montants))

    def test_arrondi_absorbe_par_derniere_dotation(self):
        charge = services.etaler_charge_avance(
            self.co, montant_total=Decimal('1000.00'),
            date_debut=date(2026, 1, 1), nb_mois=3,
            libelle='Loyer prépayé')
        montants = [d.montant for d in charge.dotations.order_by('numero')]
        total = sum(montants, Decimal('0'))
        self.assertEqual(total, Decimal('1000.00'))
        # 1000/3 = 333.33 x2 + reste sur la dernière.
        self.assertEqual(montants[0], Decimal('333.33'))
        self.assertEqual(montants[1], Decimal('333.33'))
        self.assertEqual(montants[2], Decimal('333.34'))

    def test_ecriture_origine_equilibree_3491(self):
        charge = services.etaler_charge_avance(
            self.co, montant_total=Decimal('6000.00'),
            date_debut=date(2026, 1, 1), nb_mois=6,
            libelle='Assurance semestrielle')
        self.assertIsNotNone(charge.ecriture_origine_id)
        lignes = LigneEcriture.objects.filter(ecriture=charge.ecriture_origine)
        debit = sum((line.debit for line in lignes), Decimal('0'))
        credit = sum((line.credit for line in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertEqual(debit, Decimal('6000.00'))
        numeros = {line.compte.numero for line in lignes}
        self.assertIn('3491', numeros)

    def test_poster_dotation_ecriture_equilibree_et_idempotente(self):
        charge = services.etaler_charge_avance(
            self.co, montant_total=Decimal('2400.00'),
            date_debut=date(2026, 1, 1), nb_mois=12,
            libelle='Assurance véhicule')
        dotation = charge.dotations.order_by('numero').first()
        ecriture = services.poster_dotation_etalement(dotation)
        lignes = LigneEcriture.objects.filter(ecriture=ecriture)
        debit = sum((line.debit for line in lignes), Decimal('0'))
        credit = sum((line.credit for line in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertEqual(debit, Decimal('200.00'))
        numeros = {line.compte.numero for line in lignes}
        self.assertIn('3491', numeros)
        dotation.refresh_from_db()
        ec2 = services.poster_dotation_etalement(dotation)
        self.assertEqual(ecriture.id, ec2.id)

    def test_solde_restant_a_etaler_exact(self):
        charge = services.etaler_charge_avance(
            self.co, montant_total=Decimal('1200.00'),
            date_debut=date(2026, 1, 1), nb_mois=12,
            libelle='Assurance')
        dotations = list(charge.dotations.order_by('numero'))
        # Poste les 3 premières dotations (300 en tout).
        for d in dotations[:3]:
            services.poster_dotation_etalement(d)
        rapport = selectors.solde_charges_constatees_avance(
            self.co, date_fin=date(2026, 4, 1))
        entree = [c for c in rapport['charges'] if c['id'] == charge.id][0]
        self.assertEqual(entree['solde_restant'], Decimal('900.00'))

    def test_isolation_multi_societe(self):
        co_b = make_company('xacc15-b', 'XACC15 B')
        services.etaler_charge_avance(
            self.co, montant_total=Decimal('1200.00'),
            date_debut=date(2026, 1, 1), nb_mois=12, libelle='A')
        self.assertEqual(
            ChargeConstateeAvance.objects.filter(company=co_b).count(), 0)
