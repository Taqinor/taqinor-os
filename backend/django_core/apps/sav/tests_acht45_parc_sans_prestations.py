"""ACHT45 (D-ACHT-1 a) — le balayage de nomenclature à la réception n'amène
au parc que les biens à garantie suivis à l'unité : prestations et
consommables (câbles, structures, protections, accessoires) restent dehors ;
une catégorie sans type entre toujours.

Run :
    python manage.py test apps.sav.tests_acht45_parc_sans_prestations -v2
"""
from datetime import date

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.sav.services import sweep_bom_to_parc
from apps.stock.models import Categorie, Produit


class ParcSansPrestationsTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='acht45-co', defaults={'nom': 'ACHT45 Co'})
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ACHT45')
        self.produits = {}
        specs = [
            ('PAN-CS-710', 'panneau'), ('OND-R-HUA-5M', 'onduleur'),
            ('INST-CAT', 'service'), ('TRANS-CAT', 'service'),
            ('CAB-1', 'cable'), ('LIBRE-1', None),
        ]
        for i, (sku, type_eq) in enumerate(specs):
            cat = Categorie.objects.create(
                company=self.company, nom=f'Cat {i}', type_equipement=type_eq)
            self.produits[sku] = Produit.objects.create(
                company=self.company, nom=sku, sku=sku, prix_achat=0,
                prix_vente=10, categorie=cat)
        self.chantier = Installation.objects.create(
            company=self.company, reference='CHT-ACHT45', client=client,
            bom=[{'produit_id': p.id, 'designation': sku}
                 for sku, p in self.produits.items()])

    def _balayer(self):
        par_id = {p.id: p for p in self.produits.values()}
        return sweep_bom_to_parc(
            installation=self.chantier, company=self.company,
            date_pose=date(2026, 9, 1), created_by=None,
            resolve_produit=par_id.get)

    def test_prestations_et_consommables_exclus(self):
        resume = self._balayer()
        skus = set(Equipement.objects.filter(
            installation=self.chantier).values_list('produit__sku', flat=True))
        self.assertEqual(skus, {'PAN-CS-710', 'OND-R-HUA-5M', 'LIBRE-1'})
        self.assertEqual(resume['crees'], 3)
        self.assertEqual(len(resume['lignes']), 3)

    def test_second_passage_ne_cree_rien(self):
        self._balayer()
        resume = self._balayer()
        self.assertEqual(resume['crees'], 0)
        self.assertEqual(Equipement.objects.filter(
            installation=self.chantier).count(), 3)
