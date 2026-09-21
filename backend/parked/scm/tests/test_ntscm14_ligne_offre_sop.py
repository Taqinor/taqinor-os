"""NTSCM14 — Snapshot capacité/offre par cycle S&OP.

Critère d'acceptation : un produit avec demande finale 500 et offre 300
apparaît en tête de liste avec écart -200, test vérifie le tri.

``Produit``/``Fournisseur`` créés directement via ``apps.stock.models``
UNIQUEMENT pour construire la fixture de test (frontière cross-app,
CLAUDE.md)."""
from decimal import Decimal

from django.test import TestCase

from apps.scm.models import CyclePlanificationSOP, LigneDemandeSOP, LigneOffreSOP
from apps.scm.services import calculer_offre_cycle
from apps.stock.models import Fournisseur, Produit
from apps.stock.services import creer_bcf_depuis_lignes

from .helpers import auth, make_company, make_user


class CalculerOffreCycleTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-offre', 'Supply Offre')
        self.admin = make_user(self.company, 'scm-offre-admin', 'admin')
        self.cycle = CyclePlanificationSOP.objects.create(
            company=self.company, periode='2026-09')

        # Pénurie sévère : demande 500, stock disponible 300 -> écart -200.
        self.produit_penurie = Produit.objects.create(
            company=self.company, nom='Onduleur pénurie', prix_vente=8000,
            quantite_stock=300)
        # Équilibré : demande 100, stock 100 -> écart 0.
        self.produit_equilibre = Produit.objects.create(
            company=self.company, nom='Câble équilibré', prix_vente=5,
            quantite_stock=100)
        # Surstock : demande 50, stock 200 -> écart +150.
        self.produit_surstock = Produit.objects.create(
            company=self.company, nom='Vis surstock', prix_vente=2,
            quantite_stock=200)

        for produit, demande in (
            (self.produit_penurie, 500), (self.produit_equilibre, 100),
            (self.produit_surstock, 50),
        ):
            LigneDemandeSOP.objects.create(
                company=self.company, cycle=self.cycle, produit=produit,
                quantite_prevision_systeme=Decimal(str(demande)))

    def test_shortage_product_sorted_first_with_correct_ecart(self):
        lignes = calculer_offre_cycle(self.cycle)
        self.assertEqual(len(lignes), 3)

        # Triées par écart croissant (pénurie la plus sévère en tête).
        self.assertEqual(lignes[0].produit_id, self.produit_penurie.id)
        self.assertEqual(lignes[0].ecart_offre_demande, Decimal('-200.00'))
        self.assertEqual(lignes[1].produit_id, self.produit_equilibre.id)
        self.assertEqual(lignes[1].ecart_offre_demande, Decimal('0.00'))
        self.assertEqual(lignes[2].produit_id, self.produit_surstock.id)
        self.assertEqual(lignes[2].ecart_offre_demande, Decimal('150.00'))

    def test_capacite_appro_includes_open_purchase_order_quantity(self):
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Test')
        creer_bcf_depuis_lignes(
            company=self.company, user=self.admin, fournisseur=fournisseur,
            lignes=[(self.produit_penurie.id, 'Réappro urgent', 150, 3000)])

        lignes = calculer_offre_cycle(self.cycle)
        ligne_penurie = next(
            ligne for ligne in lignes if ligne.produit_id == self.produit_penurie.id)
        self.assertEqual(ligne_penurie.capacite_appro_fournisseur_estimee, Decimal('150.00'))
        # 300 (stock) + 150 (en commande) - 500 (demande) = -50.
        self.assertEqual(ligne_penurie.ecart_offre_demande, Decimal('-50.00'))

    def test_ecarts_endpoint_is_sorted(self):
        calculer_offre_cycle(self.cycle)
        resp = auth(self.admin).get(
            f'/api/django/scm/cycles-sop/{self.cycle.id}/ecarts/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data[0]['produit'], self.produit_penurie.id)
        self.assertEqual(resp.data[0]['ecart_offre_demande'], '-200.00')

    def test_recalcul_is_idempotent(self):
        calculer_offre_cycle(self.cycle)
        first_count = LigneOffreSOP.objects.filter(cycle=self.cycle).count()
        calculer_offre_cycle(self.cycle)
        second_count = LigneOffreSOP.objects.filter(cycle=self.cycle).count()
        self.assertEqual(first_count, second_count)
        self.assertEqual(first_count, 3)
