"""Tests listes de prix multi-fournisseurs par SKU (N17).

Couvre (couche service, sans réseau) :
  - cheapest_prix_fournisseur : choisit le moins cher, ignore les prix nuls ;
  - record_purchase_price : upsert (création puis mise à jour) + date ;
  - compute_besoin_materiel : surface le fournisseur le moins cher par ligne ;
  - resolve_fournisseur : préfère le fournisseur le moins cher.

Le prix d'achat reste INTERNE (jamais client-facing).

Run :
    python manage.py test apps.stock.test_prix_fournisseur -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit, Fournisseur, PrixFournisseur
from apps.installations.models import Installation
from apps.ventes.models import Devis, LigneDevis
from apps.stock.services import (
    cheapest_prix_fournisseur, record_purchase_price,
    compute_besoin_materiel, resolve_fournisseur,
)

User = get_user_model()


def make_company(slug='pf-co', nom='PF Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class PrixFournisseurBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND5',
            prix_achat=Decimal('1000'), prix_vente=Decimal('1500'),
            quantite_stock=0)
        self.f_cher = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Cher')
        self.f_eco = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Éco')


class TestCheapest(PrixFournisseurBase):
    def test_picks_cheapest_ignores_zero(self):
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.f_cher, prix_achat=Decimal('900'))
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.f_eco, prix_achat=Decimal('820'))
        cheapest = cheapest_prix_fournisseur(self.produit)
        self.assertEqual(cheapest.fournisseur_id, self.f_eco.id)
        self.assertEqual(cheapest.prix_achat, Decimal('820'))

    def test_none_when_no_price(self):
        self.assertIsNone(cheapest_prix_fournisseur(self.produit))
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.f_eco, prix_achat=Decimal('0'))
        self.assertIsNone(cheapest_prix_fournisseur(self.produit))


class TestRecordPurchasePrice(PrixFournisseurBase):
    def test_upsert(self):
        d1 = datetime.date(2026, 1, 1)
        record_purchase_price(
            company=self.company, produit=self.produit,
            fournisseur=self.f_eco, prix_achat=Decimal('810'), date=d1)
        obj = PrixFournisseur.objects.get(
            produit=self.produit, fournisseur=self.f_eco)
        self.assertEqual(obj.prix_achat, Decimal('810'))
        self.assertEqual(obj.date_dernier_achat, d1)
        # Deuxième achat → même enregistrement ; ASTK90 : le tarif négocié
        # n'est PAS écrasé par le prix de réception, seule la date avance.
        d2 = datetime.date(2026, 6, 1)
        record_purchase_price(
            company=self.company, produit=self.produit,
            fournisseur=self.f_eco, prix_achat=Decimal('795'), date=d2)
        self.assertEqual(PrixFournisseur.objects.filter(
            produit=self.produit, fournisseur=self.f_eco).count(), 1)
        obj.refresh_from_db()
        self.assertEqual(obj.prix_achat, Decimal('810'))
        self.assertEqual(obj.date_dernier_achat, d2)


class TestBesoinSurfacesCheapest(PrixFournisseurBase):
    def _chantier(self, produit, qte):
        cl = Client.objects.create(
            company=self.company, nom='Cl', prenom='Ient',
            email='cl-pf@example.com', telephone='+212600000009')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-209901-9001', client=cl,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(qte), prix_unitaire=produit.prix_vente)
        return Installation.objects.create(
            company=self.company, reference='CH-209901-9001',
            client=cl, devis=devis)

    def test_besoin_includes_cheapest_supplier(self):
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.f_cher, prix_achat=Decimal('900'))
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.f_eco, prix_achat=Decimal('820'))
        inst = self._chantier(self.produit, 5)
        besoins = compute_besoin_materiel(inst)
        entry = next(b for b in besoins if b['produit_id'] == self.produit.id)
        self.assertEqual(entry['fournisseur_min_id'], self.f_eco.id)
        self.assertEqual(entry['prix_achat_min'], Decimal('820'))

    def test_brouillon_des_manques_au_tarif_en_vigueur(self):
        """AAPV16 — catalogue 1 000, éco expiré hier (moins cher), cher en
        vigueur avec palier 10+ : le brouillon des manques part chez « cher »
        au prix du palier, jamais au prix catalogue ni chez l'expiré."""
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from apps.stock.models import PalierPrixFournisseur
        from apps.stock.services import draft_bcfs_for_shortfall
        hier = timezone.localdate() - datetime.timedelta(days=1)
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit, fournisseur=self.f_eco,
            prix_achat=Decimal('700'), date_fin=hier)
        pf = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit, fournisseur=self.f_cher,
            prix_achat=Decimal('950'))
        PalierPrixFournisseur.objects.create(prix_fournisseur=pf, qte_min=10, prix=Decimal('900'))
        self.assertEqual(cheapest_prix_fournisseur(self.produit).fournisseur_id, self.f_cher.id)
        inst = self._chantier(self.produit, 10)
        user = get_user_model().objects.create_user(
            username='pf-aapv16', password='x', company=self.company, role_legacy='responsable')
        crees, _sans = draft_bcfs_for_shortfall(inst, user, self.company)
        self.assertEqual(len(crees), 1)
        bon = crees[0][0]
        self.assertEqual(bon.fournisseur_id, self.f_cher.id)
        self.assertEqual(bon.lignes.get().prix_achat_unitaire, Decimal('900'))

    def test_resolve_prefers_cheapest(self):
        # Fournisseur catalogue = cher ; liste de prix = éco moins cher.
        self.produit.fournisseur = self.f_cher
        self.produit.save(update_fields=['fournisseur'])
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.f_eco, prix_achat=Decimal('820'))
        inst = self._chantier(self.produit, 5)  # stock 0 → manque 5
        chosen = resolve_fournisseur(self.company, None, inst)
        self.assertEqual(chosen.id, self.f_eco.id)
