"""Tests XACC14 — Emprunts & crédits-bails (financements de la société).

Couvre : génération du tableau d'amortissement complet (somme des principaux
= capital), posting d'une échéance en écriture GL équilibrée idempotente,
l'encours restant dû dans la position de trésorerie, et l'injection des
échéances futures dans le prévisionnel 13 semaines (FG126).
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import Emprunt, LigneEcriture


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TableauAmortissementTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc14-svc', 'XACC14 Svc')

    def test_tableau_complet_somme_principal_egale_capital(self):
        emprunt = Emprunt.objects.create(
            company=self.co, banque='Banque Populaire',
            type_financement=Emprunt.Type.EMPRUNT,
            capital=Decimal('120000'), taux_annuel=Decimal('6.000'),
            duree_mois=12, date_debut=date(2026, 1, 1),
        )
        echeances = services.generer_tableau_amortissement(emprunt)
        self.assertEqual(len(echeances), 12)
        total_principal = sum((e.principal for e in echeances), Decimal('0'))
        self.assertEqual(total_principal, Decimal('120000.00'))
        # Le capital restant dû de la dernière échéance doit être nul.
        self.assertEqual(echeances[-1].capital_restant_du, Decimal('0.00'))

    def test_taux_zero_division_simple(self):
        emprunt = Emprunt.objects.create(
            company=self.co, banque='Leasing Co',
            type_financement=Emprunt.Type.LEASING,
            capital=Decimal('12000'), taux_annuel=Decimal('0'),
            duree_mois=12, date_debut=date(2026, 1, 1),
        )
        echeances = services.generer_tableau_amortissement(emprunt)
        total_principal = sum((e.principal for e in echeances), Decimal('0'))
        self.assertEqual(total_principal, Decimal('12000.00'))
        self.assertTrue(all(e.interets == Decimal('0.00') for e in echeances))

    def test_regeneration_refusee_si_echeance_postee(self):
        emprunt = Emprunt.objects.create(
            company=self.co, banque='Banque X',
            capital=Decimal('10000'), taux_annuel=Decimal('5'),
            duree_mois=6, date_debut=date(2026, 1, 1),
        )
        services.generer_tableau_amortissement(emprunt)
        premiere = emprunt.echeances.order_by('numero').first()
        services.poster_echeance_emprunt(premiere)
        with self.assertRaises(ValidationError):
            services.generer_tableau_amortissement(emprunt)


class PosterEcheanceTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc14-post', 'XACC14 Post')
        self.emprunt = Emprunt.objects.create(
            company=self.co, banque='Banque Populaire',
            capital=Decimal('60000'), taux_annuel=Decimal('4.5'),
            duree_mois=6, date_debut=date(2026, 1, 1),
        )
        services.generer_tableau_amortissement(self.emprunt)

    def test_poster_echeance_ecriture_equilibree(self):
        echeance = self.emprunt.echeances.order_by('numero').first()
        ecriture = services.poster_echeance_emprunt(echeance)
        lignes = LigneEcriture.objects.filter(ecriture=ecriture)
        debit = sum((line.debit for line in lignes), Decimal('0'))
        credit = sum((line.credit for line in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertEqual(debit, echeance.mensualite)
        numeros = {line.compte.numero for line in lignes}
        self.assertIn('1481', numeros)
        self.assertIn('5141', numeros)

    def test_poster_idempotent(self):
        echeance = self.emprunt.echeances.order_by('numero').first()
        ec1 = services.poster_echeance_emprunt(echeance)
        echeance.refresh_from_db()
        ec2 = services.poster_echeance_emprunt(echeance)
        self.assertEqual(ec1.id, ec2.id)

    def test_leasing_utilise_compte_1671(self):
        emprunt_leasing = Emprunt.objects.create(
            company=self.co, banque='Wafabail',
            type_financement=Emprunt.Type.LEASING,
            capital=Decimal('30000'), taux_annuel=Decimal('5'),
            duree_mois=6, date_debut=date(2026, 1, 1),
        )
        services.generer_tableau_amortissement(emprunt_leasing)
        echeance = emprunt_leasing.echeances.order_by('numero').first()
        ecriture = services.poster_echeance_emprunt(echeance)
        numeros = {
            line.compte.numero
            for line in LigneEcriture.objects.filter(ecriture=ecriture)}
        self.assertIn('1671', numeros)


class EncoursEtPrevisionnelTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc14-treso', 'XACC14 Treso')
        self.emprunt = Emprunt.objects.create(
            company=self.co, banque='Banque Populaire',
            capital=Decimal('24000'), taux_annuel=Decimal('0'),
            duree_mois=12, date_debut=date(2026, 1, 1),
        )
        services.generer_tableau_amortissement(self.emprunt)

    def test_encours_restant_du_diminue_apres_posting(self):
        # Rien de postée encore : encours = capital initial intact.
        self.assertEqual(self.emprunt.encours_restant_du, Decimal('24000.00'))
        premiere = self.emprunt.echeances.order_by('numero').first()
        services.poster_echeance_emprunt(premiere)
        self.emprunt.refresh_from_db()
        self.assertEqual(
            self.emprunt.encours_restant_du,
            Decimal('24000.00') - premiere.principal)

    def test_encours_apparait_dans_position_tresorerie(self):
        position = selectors.position_tresorerie(self.co)
        self.assertIn('encours_emprunts', position)

    def test_injection_previsionnel_echeances_futures(self):
        from datetime import date as d
        lignes = services.injecter_echeances_previsionnel(
            self.co, date_debut=d(2026, 1, 1), nb_semaines=13)
        self.assertTrue(len(lignes) > 0)
        self.assertTrue(all(ligne['montant'] < 0 for ligne in lignes))
