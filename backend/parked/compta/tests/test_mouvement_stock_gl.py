"""XACC6 — Écritures de stock automatiques (inventaire permanent).

Couvre :

* toggle OFF (défaut) : ``poster_mouvement_stock`` ne poste rien (non-
  régression) ;
* toggle ON : une SORTIE de stock valorisée poste une écriture équilibrée
  (6114 débit / 3111 crédit), une ENTRÉE l'inverse ;
* idempotence par mouvement (rejouer le même ``mouvement_ref`` ne duplique
  pas) ;
* le verrou de période est respecté ;
* la valorisation résout ``Produit.prix_achat`` via ``stock.selectors``
  quand ``valeur_unitaire`` n'est pas fournie explicitement.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import EcritureComptable, PlanComptable
from apps.stock.models import Produit


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class PosterMouvementStockTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc6', 'XACC6 Co')
        self.plan = services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau 450W', prix_vente=Decimal('1500'),
            prix_achat=Decimal('900'))

    def _activer_inventaire_permanent(self):
        self.plan.inventaire_permanent = True
        self.plan.save(update_fields=['inventaire_permanent'])

    def test_toggle_off_ne_poste_rien(self):
        res = services.poster_mouvement_stock(
            self.co, mouvement_ref=1, produit_id=self.produit.id,
            sens='sortie', quantite=5, date_mouvement=date(2026, 2, 10))
        self.assertIsNone(res)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='mouvement_stock').count(), 0)

    def test_toggle_on_sortie_poste_ecriture_equilibree(self):
        self._activer_inventaire_permanent()
        ecr = services.poster_mouvement_stock(
            self.co, mouvement_ref=10, produit_id=self.produit.id,
            sens='sortie', quantite=5, date_mouvement=date(2026, 2, 10))
        self.assertIsNotNone(ecr)
        self.assertTrue(ecr.est_equilibree)
        # 5 × 900 = 4500.
        self.assertEqual(ecr.total_debit, Decimal('4500'))
        variation = ecr.lignes.get(compte__numero='6114')
        stock = ecr.lignes.get(compte__numero='3111')
        self.assertEqual(variation.debit, Decimal('4500'))
        self.assertEqual(stock.credit, Decimal('4500'))

    def test_toggle_on_entree_poste_ecriture_inverse(self):
        self._activer_inventaire_permanent()
        ecr = services.poster_mouvement_stock(
            self.co, mouvement_ref=11, produit_id=self.produit.id,
            sens='entree', quantite=3, date_mouvement=date(2026, 2, 11))
        stock = ecr.lignes.get(compte__numero='3111')
        variation = ecr.lignes.get(compte__numero='6114')
        self.assertEqual(stock.debit, Decimal('2700'))  # 3 × 900.
        self.assertEqual(variation.credit, Decimal('2700'))

    def test_valeur_unitaire_explicite_prevaut_sur_prix_achat(self):
        self._activer_inventaire_permanent()
        ecr = services.poster_mouvement_stock(
            self.co, mouvement_ref=12, produit_id=self.produit.id,
            sens='sortie', quantite=2, valeur_unitaire=Decimal('100'),
            date_mouvement=date(2026, 2, 12))
        self.assertEqual(ecr.total_debit, Decimal('200'))

    def test_idempotent_meme_mouvement(self):
        self._activer_inventaire_permanent()
        a = services.poster_mouvement_stock(
            self.co, mouvement_ref=20, produit_id=self.produit.id,
            sens='sortie', quantite=1, date_mouvement=date(2026, 2, 13))
        b = services.poster_mouvement_stock(
            self.co, mouvement_ref=20, produit_id=self.produit.id,
            sens='sortie', quantite=1, date_mouvement=date(2026, 2, 13))
        self.assertEqual(a.id, b.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='mouvement_stock').count(), 1)

    def test_valeur_nulle_ne_poste_rien(self):
        self._activer_inventaire_permanent()
        produit_gratuit = Produit.objects.create(
            company=self.co, nom='Accessoire offert',
            prix_vente=Decimal('0'), prix_achat=Decimal('0'))
        res = services.poster_mouvement_stock(
            self.co, mouvement_ref=30, produit_id=produit_gratuit.id,
            sens='sortie', quantite=10, date_mouvement=date(2026, 2, 14))
        self.assertIsNone(res)

    def test_sens_invalide_leve_erreur(self):
        self._activer_inventaire_permanent()
        with self.assertRaises(ValidationError):
            services.poster_mouvement_stock(
                self.co, mouvement_ref=40, produit_id=self.produit.id,
                sens='transfert', quantite=1, date_mouvement=date(2026, 2, 15))

    def test_verrou_de_periode_respecte(self):
        self._activer_inventaire_permanent()
        periode = services.creer_periode(
            self.co, date(2026, 2, 1), date(2026, 2, 28), libelle='Février 2026')
        services.cloturer_periode(periode)
        with self.assertRaises(ValidationError):
            services.poster_mouvement_stock(
                self.co, mouvement_ref=50, produit_id=self.produit.id,
                sens='sortie', quantite=1, date_mouvement=date(2026, 2, 20))

    def test_inventaire_permanent_actif_seme_le_plan_au_besoin(self):
        co2 = make_company('xacc6-defaut', 'XACC6 Défaut Co')
        self.assertFalse(services.inventaire_permanent_actif(co2))
        self.assertTrue(PlanComptable.objects.filter(company=co2).exists())
