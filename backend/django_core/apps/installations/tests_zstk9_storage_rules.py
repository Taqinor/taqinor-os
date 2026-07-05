"""ZSTK9 — Capacité & compatibilité d'emplacement + règle de rangement
configurable (storage categories / putaway rules, Odoo parity).

FG319/320 posaient des casiers + une opération de put-away codée en dur.
Couvre :

  * une règle « panneaux → casier A » fait suggérer A à la réception d'un
    panneau ;
  * un casier plein (`qte_max` atteinte de sa catégorie) est écarté ;
  * un casier non compatible (`melange_autorise=False`, déjà occupé par un
    autre produit) est écarté ;
  * sans règle ni capacité, le comportement reste BYTE-IDENTIQUE à FG320
    (non-régression) ;
  * migrations additives, isolation tenant.

Run :
    python manage.py test apps.installations.tests_zstk9_storage_rules -v2
"""
import itertools

from django.test import TestCase

from apps.installations.models import (
    BinLocation, BinAffectation, CategorieStockage, RegleRangement,
)
from apps.installations.selectors import suggerer_bin_putaway

_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'zstk9-co-{n}', defaults={'nom': f'ZSTK9 Co {n}'})
    return company


def make_emplacement(company, nom='Dépôt'):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(company=company, nom=nom)


def make_produit(company, nom='Panneau'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1000, prix_achat=0)


class TestReglesRangement(TestCase):
    def setUp(self):
        self.company = make_company()
        self.emp = make_emplacement(self.company)
        self.produit = make_produit(self.company, nom='Panneau solaire')
        self.bin_a = BinLocation.objects.create(
            company=self.company, emplacement=self.emp, code='A-1-1', ordre=1)
        self.bin_b = BinLocation.objects.create(
            company=self.company, emplacement=self.emp, code='B-1-1', ordre=2)

    def test_regle_produit_fait_suggerer_le_casier_cible(self):
        RegleRangement.objects.create(
            company=self.company, produit=self.produit,
            bin_cible=self.bin_a, priorite=10)
        suggestion = suggerer_bin_putaway(
            self.company, self.produit.id, emplacement_id=self.emp.id,
            quantite=5)
        self.assertEqual(suggestion.id, self.bin_a.id)

    def test_regle_categorie_produit_fait_suggerer_le_casier_cible(self):
        from apps.stock.models import Categorie
        cat = Categorie.objects.create(company=self.company, nom='Panneaux')
        self.produit.categorie = cat
        self.produit.save(update_fields=['categorie'])
        RegleRangement.objects.create(
            company=self.company, categorie_produit='Panneaux',
            bin_cible=self.bin_a, priorite=10)
        suggestion = suggerer_bin_putaway(
            self.company, self.produit.id, emplacement_id=self.emp.id,
            quantite=5)
        self.assertEqual(suggestion.id, self.bin_a.id)

    def test_casier_plein_est_ecarte(self):
        cat = CategorieStockage.objects.create(
            company=self.company, nom='Petit casier', qte_max=5)
        self.bin_a.categorie = cat
        self.bin_a.save(update_fields=['categorie'])
        RegleRangement.objects.create(
            company=self.company, produit=self.produit,
            bin_cible=self.bin_a, priorite=10)
        # Déjà 4 en place ; en ajouter 3 dépasserait qte_max=5.
        BinAffectation.objects.create(
            company=self.company, bin=self.bin_a, produit=self.produit,
            quantite=4)
        suggestion = suggerer_bin_putaway(
            self.company, self.produit.id, emplacement_id=self.emp.id,
            quantite=3)
        self.assertNotEqual(getattr(suggestion, 'id', None), self.bin_a.id)

    def test_casier_incompatible_est_ecarte(self):
        cat = CategorieStockage.objects.create(
            company=self.company, nom='Sans melange', melange_autorise=False)
        self.bin_a.categorie = cat
        self.bin_a.save(update_fields=['categorie'])
        autre_produit = make_produit(self.company, nom='Onduleur')
        BinAffectation.objects.create(
            company=self.company, bin=self.bin_a, produit=autre_produit,
            quantite=2)
        RegleRangement.objects.create(
            company=self.company, produit=self.produit,
            bin_cible=self.bin_a, priorite=10)
        suggestion = suggerer_bin_putaway(
            self.company, self.produit.id, emplacement_id=self.emp.id,
            quantite=1)
        self.assertNotEqual(getattr(suggestion, 'id', None), self.bin_a.id)

    def test_sans_regle_ni_capacite_comportement_byte_identique(self):
        """FG320 historique : casier déjà affecté (le plus rempli), sinon
        premier casier non archivé par ordre — sans règle ni catégorie."""
        BinAffectation.objects.create(
            company=self.company, bin=self.bin_b, produit=self.produit,
            quantite=9)
        suggestion = suggerer_bin_putaway(
            self.company, self.produit.id, emplacement_id=self.emp.id)
        self.assertEqual(suggestion.id, self.bin_b.id)

        # Sans affectation ni règle : repli sur le premier casier par ordre.
        autre_produit = make_produit(self.company, nom='Autre')
        suggestion2 = suggerer_bin_putaway(
            self.company, autre_produit.id, emplacement_id=self.emp.id)
        self.assertEqual(suggestion2.id, self.bin_a.id)

    def test_isolation_tenant_regle(self):
        other_company = make_company()
        other_emp = make_emplacement(other_company)
        other_bin = BinLocation.objects.create(
            company=other_company, emplacement=other_emp, code='X-1-1')
        RegleRangement.objects.create(
            company=other_company, produit=self.produit,
            bin_cible=other_bin, priorite=1)
        # La règle d'une autre société ne doit jamais influencer la suggestion.
        suggestion = suggerer_bin_putaway(
            self.company, self.produit.id, emplacement_id=self.emp.id)
        self.assertNotEqual(getattr(suggestion, 'id', None), other_bin.id)
