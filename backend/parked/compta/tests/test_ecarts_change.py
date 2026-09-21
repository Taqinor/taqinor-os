"""Tests XACC18 — Écarts de change réalisés & réévaluation de clôture.

Couvre : une facture EUR payée à un autre taux poste l'écart exact (gain/perte
733/633), le run de réévaluation de clôture réévalue les items ouverts et
s'extourne à l'ouverture suivante, et aucune écriture n'est postée si tout
reste en MAD ou si le taux n'a pas bougé.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import ItemOuvertDevise, LigneEcriture


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class EcartChangeTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc18-svc', 'XACC18 Svc')

    def test_facture_eur_payee_taux_different_poste_ecart_exact(self):
        item = services.enregistrer_item_ouvert_devise(
            self.co, type_document=ItemOuvertDevise.TypeDocument.FACTURE_CLIENT,
            document_id=1, document_reference='FA-001',
            devise='EUR', montant_devise=Decimal('1000'),
            taux_origine=Decimal('10.80'), date_origine=date(2026, 6, 1))
        ecart = services.constater_ecart_change(
            item, date_reglement=date(2026, 6, 15),
            taux_reglement=Decimal('11.00'))
        # (11.00 - 10.80) * 1000 = 200 MAD de gain.
        self.assertEqual(ecart.difference, Decimal('200.00'))
        lignes = LigneEcriture.objects.filter(ecriture=ecart.ecriture)
        debit = sum((line.debit for line in lignes), Decimal('0'))
        credit = sum((line.credit for line in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        numeros = {line.compte.numero for line in lignes}
        self.assertIn('733', numeros)

    def test_perte_de_change_poste_633(self):
        item = services.enregistrer_item_ouvert_devise(
            self.co, type_document=ItemOuvertDevise.TypeDocument.FACTURE_CLIENT,
            document_id=2, document_reference='FA-002',
            devise='EUR', montant_devise=Decimal('1000'),
            taux_origine=Decimal('11.00'), date_origine=date(2026, 6, 1))
        ecart = services.constater_ecart_change(
            item, date_reglement=date(2026, 6, 15),
            taux_reglement=Decimal('10.80'))
        self.assertEqual(ecart.difference, Decimal('-200.00'))
        numeros = {
            line.compte.numero
            for line in LigneEcriture.objects.filter(ecriture=ecart.ecriture)}
        self.assertIn('633', numeros)

    def test_aucune_ecriture_si_taux_identique(self):
        item = services.enregistrer_item_ouvert_devise(
            self.co, type_document=ItemOuvertDevise.TypeDocument.FACTURE_CLIENT,
            document_id=3, document_reference='FA-003',
            devise='EUR', montant_devise=Decimal('1000'),
            taux_origine=Decimal('10.80'), date_origine=date(2026, 6, 1))
        ecart = services.constater_ecart_change(
            item, date_reglement=date(2026, 6, 15),
            taux_reglement=Decimal('10.80'))
        self.assertEqual(ecart.difference, Decimal('0.00'))
        self.assertIsNone(ecart.ecriture_id)

    def test_idempotent(self):
        item = services.enregistrer_item_ouvert_devise(
            self.co, type_document=ItemOuvertDevise.TypeDocument.FACTURE_CLIENT,
            document_id=4, document_reference='FA-004',
            devise='EUR', montant_devise=Decimal('1000'),
            taux_origine=Decimal('10.80'), date_origine=date(2026, 6, 1))
        e1 = services.constater_ecart_change(
            item, date_reglement=date(2026, 6, 15),
            taux_reglement=Decimal('11.00'))
        item.refresh_from_db()
        e2 = services.constater_ecart_change(
            item, date_reglement=date(2026, 6, 20),
            taux_reglement=Decimal('12.00'))
        self.assertEqual(e1.id, e2.id)
        self.assertEqual(e2.difference, Decimal('200.00'))

    def test_mad_ne_necessite_pas_de_suivi(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            services.enregistrer_item_ouvert_devise(
                self.co, type_document=ItemOuvertDevise.TypeDocument.FACTURE_CLIENT,
                document_id=5, devise='MAD', montant_devise=Decimal('1000'),
                taux_origine=Decimal('1'), date_origine=date(2026, 6, 1))


class ReevaluationClotureTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc18-cloture', 'XACC18 Cloture')

    def test_run_reevalue_items_ouverts_et_sextourne(self):
        services.enregistrer_item_ouvert_devise(
            self.co, type_document=ItemOuvertDevise.TypeDocument.FACTURE_CLIENT,
            document_id=10, document_reference='FA-010',
            devise='EUR', montant_devise=Decimal('1000'),
            taux_origine=Decimal('10.80'), date_origine=date(2026, 1, 1))
        services.enregistrer_taux_devise(
            self.co, devise='EUR', date_taux=date(2026, 12, 31),
            taux_vers_mad=Decimal('11.00'))
        run = services.reevaluer_cloture(self.co, date_cloture=date(2026, 12, 31))
        self.assertEqual(run.total_ecart, Decimal('200.00'))
        self.assertIsNotNone(run.ecriture_id)
        self.assertIsNotNone(run.ecriture_extourne_id)
        self.assertEqual(run.date_extourne, date(2027, 1, 1))
        # L'écriture d'extourne inverse exactement l'écriture de clôture.
        lignes_orig = LigneEcriture.objects.filter(ecriture=run.ecriture)
        lignes_ext = LigneEcriture.objects.filter(ecriture=run.ecriture_extourne)
        debit_orig = sum((ln.debit for ln in lignes_orig), Decimal('0'))
        credit_ext = sum((ln.credit for ln in lignes_ext), Decimal('0'))
        self.assertEqual(debit_orig, credit_ext)

    def test_aucune_ecriture_si_tout_en_mad(self):
        run = services.reevaluer_cloture(self.co, date_cloture=date(2026, 12, 31))
        self.assertEqual(run.total_ecart, Decimal('0.00'))
        self.assertIsNone(run.ecriture_id)

    def test_item_solde_ignore_par_le_run(self):
        item = services.enregistrer_item_ouvert_devise(
            self.co, type_document=ItemOuvertDevise.TypeDocument.FACTURE_CLIENT,
            document_id=11, document_reference='FA-011',
            devise='EUR', montant_devise=Decimal('1000'),
            taux_origine=Decimal('10.80'), date_origine=date(2026, 1, 1))
        services.constater_ecart_change(
            item, date_reglement=date(2026, 3, 1),
            taux_reglement=Decimal('11.00'))
        services.enregistrer_taux_devise(
            self.co, devise='EUR', date_taux=date(2026, 12, 31),
            taux_vers_mad=Decimal('12.00'))
        run = services.reevaluer_cloture(self.co, date_cloture=date(2026, 12, 31))
        self.assertEqual(run.total_ecart, Decimal('0.00'))
