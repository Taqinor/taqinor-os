"""DC4 — CompanyProfile.tva_panneaux devient le défaut société du taux panneaux.

Avant : le champ était écrit/validé mais lu nulle part ; le 10 % venait de
Produit.tva ou d'un littéral. Désormais, une ligne PANNEAU sans taux explicite
ni produit taxé retombe sur CompanyProfile.tva_panneaux (défaut 10 %), tandis
que Produit.tva reste AUTORITAIRE par ligne (DC7).
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.serializers import LigneDevisSerializer
from apps.ventes.tests.test_quote_engine import make_company, make_user


class TestDC4TvaPanneaux(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='C', prenom='D', email='c@d.ma')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-DC4-1', client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'), created_by=self.user)

    def _produit(self, nom, tva=None):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=f'sku-{nom[:8]}',
            prix_vente=Decimal('1000'), prix_achat=Decimal('1'),
            quantite_stock=10, tva=tva)

    def _create_line(self, designation, produit):
        s = LigneDevisSerializer()
        return s.create({
            'devis': self.devis, 'produit': produit,
            'designation': designation, 'quantite': Decimal('1'),
            'prix_unitaire': Decimal('1000'), 'remise': Decimal('0'),
        })

    def test_panneau_fallback_uses_company_tva_panneaux(self):
        from apps.parametres.models import CompanyProfile
        p = CompanyProfile.get(company=self.company)
        p.tva_panneaux = Decimal('7')
        p.save()
        produit = self._produit('Panneau 710W', tva=None)
        ligne = self._create_line('Panneau 710W', produit)
        self.assertEqual(ligne.taux_tva, Decimal('7'))

    def test_non_panneau_fallback_uses_standard(self):
        produit = self._produit('Onduleur réseau', tva=None)
        ligne = self._create_line('Onduleur réseau', produit)
        self.assertEqual(ligne.taux_tva, Decimal('20'))

    def test_produit_tva_is_authoritative(self):
        # DC7 — même pour un panneau, Produit.tva prime sur le défaut société.
        produit = self._produit('Panneau 710W', tva=Decimal('14'))
        ligne = self._create_line('Panneau 710W', produit)
        self.assertEqual(ligne.taux_tva, Decimal('14'))
