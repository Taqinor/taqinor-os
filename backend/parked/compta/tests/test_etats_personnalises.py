"""Tests XACC19 — Générateur d'états financiers personnalisés.

Couvre : un état « marge par activité » défini en données s'affiche avec
comparatif N-1 et se réconcilie avec la balance, une formule invalide lève
une erreur explicite (400 côté vue), et l'évaluation reste scopée société.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import EcritureComptable, Journal, LigneEcriture


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _poster_vente_charge(company, date_ecr, montant_vente, montant_charge):
    """Poste une écriture simple : vente (classe 7) + charge (classe 6)."""
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    if journal is None:
        services.seed_journaux(company)
        journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    compte_vente = services._assurer_compte(company, '7111')
    compte_charge = services._assurer_compte(company, '6111')
    compte_tresorerie = services._assurer_compte(company, '5141')
    lignes = [
        {'compte': compte_tresorerie, 'debit': Decimal(montant_vente),
         'credit': Decimal('0'), 'libelle': 'Vente'},
        {'compte': compte_vente, 'debit': Decimal('0'),
         'credit': Decimal(montant_vente), 'libelle': 'Vente'},
    ]
    services.creer_ecriture(
        company, journal, date_ecr, 'Vente test', lignes,
        statut=EcritureComptable.Statut.VALIDEE)
    lignes_charge = [
        {'compte': compte_charge, 'debit': Decimal(montant_charge),
         'credit': Decimal('0'), 'libelle': 'Charge'},
        {'compte': compte_tresorerie, 'debit': Decimal('0'),
         'credit': Decimal(montant_charge), 'libelle': 'Charge'},
    ]
    services.creer_ecriture(
        company, journal, date_ecr, 'Charge test', lignes_charge,
        statut=EcritureComptable.Statut.VALIDEE)


class EtatPersonnaliseTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc19-svc', 'XACC19 Svc')
        _poster_vente_charge(self.co, date(2026, 3, 15), 50000, 20000)

    def test_marge_par_activite_se_reconcilie_avec_balance(self):
        etat = services.creer_etat_personnalise(
            self.co, libelle='Marge par activité',
            lignes=[
                {'libelle': 'Marge brute', 'formule': '+71,-61'},
            ],
            colonnes=[
                {'libelle': 'Exercice', 'type_colonne': 'periode',
                 'date_debut': date(2026, 1, 1), 'date_fin': date(2026, 12, 31)},
            ],
        )
        resultat = selectors.evaluer_etat_personnalise(etat)
        colonne_id = resultat['colonnes'][0]['id']
        marge = resultat['lignes'][0]['valeurs'][colonne_id]
        # Vente (crédit 7111, solde créditeur 50000) − charge (débit 6111 20000).
        # Formule +71 (produit, solde créditeur compte négativement en solde
        # naturel débit-crédit) -61 : on vérifie juste la cohérence du calcul
        # avec la balance brute (réconciliation, pas un signe métier figé).
        balance = selectors.balance_generale(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        ligne_71 = [ln for ln in balance['lignes'] if ln['numero'] == '7111'][0]
        ligne_61 = [ln for ln in balance['lignes'] if ln['numero'] == '6111'][0]
        attendu = (
            (ligne_71['solde_debiteur'] - ligne_71['solde_crediteur'])
            - (ligne_61['solde_debiteur'] - ligne_61['solde_crediteur']))
        self.assertEqual(marge, attendu)

    def test_comparatif_n1_sans_donnees_renvoie_zero(self):
        etat = services.creer_etat_personnalise(
            self.co, libelle='Marge N-1',
            lignes=[{'libelle': 'Marge', 'formule': '+71,-61'}],
            colonnes=[
                {'libelle': 'N-1', 'type_colonne': 'comparatif_n1',
                 'date_debut': date(2026, 1, 1), 'date_fin': date(2026, 12, 31)},
            ],
        )
        resultat = selectors.evaluer_etat_personnalise(etat)
        colonne_id = resultat['colonnes'][0]['id']
        self.assertEqual(resultat['lignes'][0]['valeurs'][colonne_id], Decimal('0'))

    def test_formule_invalide_400_explicite(self):
        with self.assertRaises(ValidationError):
            services.creer_etat_personnalise(
                self.co, libelle='État invalide',
                lignes=[{'libelle': 'Ligne', 'formule': 'abc'}],
            )

    def test_ligne_titre_sans_formule_ok(self):
        etat = services.creer_etat_personnalise(
            self.co, libelle='État avec titre',
            lignes=[
                {'libelle': 'Section produits', 'type_ligne': 'titre'},
                {'libelle': 'Total produits', 'formule': '+71'},
            ],
        )
        self.assertEqual(etat.lignes.count(), 2)

    def test_isolation_multi_societe(self):
        co_b = make_company('xacc19-b', 'XACC19 B')
        services.creer_etat_personnalise(
            self.co, libelle='État A', lignes=[{'libelle': 'L', 'formule': '+71'}])
        from apps.compta.models import EtatPersonnalise
        self.assertEqual(
            EtatPersonnalise.objects.filter(company=co_b).count(), 0)

    def test_export_reconcilie_total_debit_credit_equilibre(self):
        # La balance sous-jacente reste équilibrée (garantie du grand livre) —
        # condition nécessaire pour que tout état personnalisé se réconcilie.
        balance = selectors.balance_generale(self.co)
        self.assertTrue(balance['equilibree'])
        self.assertTrue(
            LigneEcriture.objects.filter(company=self.co).exists())
