"""ASTK120 — « une vente = une sortie » : `solder_reservations_vente`.

Rejoue la sonde RESA-1 : devis de 10 panneaux accepté (chantier, réservation
10, stock 30) ; la vente sort 10 (facture directe : stock 30 → 20) puis le
chantier passe « Installé » → stock 10 (attendu 20) : deux sorties de 10.
Après ASTK120, la sortie de la vente SOLDE la réservation via le service et
« Installé » ne sort que le reliquat.

La sortie de la vente est postée ici par le mécanisme réel
(`record_stock_movement`) ; le branchement des appelants (facture directe,
BC livré, livraison directe) est ASTK135 / ASTK98. Aucun mock.

Run :
    python manage.py test apps.installations.tests_astk_sortie_unique
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import (
    Installation, InstallationActivity, StockReservation,
)
from apps.installations.services import (
    changer_statut_chantier, create_installation_from_devis,
    solder_reservations_vente,
)
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import mouvement_type_sortie, record_stock_movement
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


class SortieUniqueTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-astk120', defaults={'nom': 'Co ASTK120'})
        self.user = User.objects.create_user(
            username='resp-astk120', password='x', company=self.company,
            role_legacy='responsable')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ASTK120', sku='SKU-ASTK120',
            prix_vente=Decimal('100'), quantite_stock=30)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='astk120@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ASTK120-1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=self.devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'))
        self.inst, _ = create_installation_from_devis(
            self.devis, self.user, self.company)

    def _resa(self):
        return StockReservation.objects.get(
            installation=self.inst, produit=self.panneau)

    def _vente_sort(self, qte):
        """Sortie de la vente (facture directe) puis solde de la résa."""
        self.panneau.refresh_from_db()
        avant = self.panneau.quantite_stock
        record_stock_movement(
            company=self.company, produit=self.panneau,
            type_mouvement=mouvement_type_sortie(), quantite=qte,
            quantite_avant=avant, quantite_apres=avant - qte,
            reference=self.devis.reference,
            note=f'Vente {self.devis.reference}', created_by=self.user)
        return solder_reservations_vente(
            self.inst, {self.panneau.id: qte}, self.devis.reference,
            user=self.user)

    def _installer(self):
        changer_statut_chantier(
            self.inst, Installation.Statut.INSTALLE, self.user,
            verifier_gates=False)
        self.inst.refresh_from_db()

    def _total_sorti(self):
        return MouvementStock.objects.filter(
            produit=self.panneau,
            type_mouvement=mouvement_type_sortie(),
        ).aggregate(t=Sum('quantite'))['t'] or 0

    def test_preconditions(self):
        resa = self._resa()
        self.assertEqual((resa.quantite, resa.active, resa.consomme),
                         (10, True, False))

    def test_solde_puis_installe_ne_ressort_pas(self):
        self.assertEqual(self._vente_sort(10), 1)
        resa = self._resa()
        self.assertEqual(resa.quantite, 0)
        self.assertTrue(resa.consomme)
        self.assertIsNotNone(resa.date_consommation)
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst, kind=InstallationActivity.Kind.NOTE,
            body__contains=f'soldée par {self.devis.reference}').exists())
        self._installer()
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        self.assertEqual(self._total_sorti(), 10)
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.panneau, reference=self.inst.reference).exists())

    def test_solde_partiel(self):
        self._vente_sort(4)
        resa = self._resa()
        self.assertEqual((resa.quantite, resa.consomme), (6, False))
        self._installer()
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        self.assertEqual(self._total_sorti(), 10)
        self.assertEqual(MouvementStock.objects.get(
            produit=self.panneau, reference=self.inst.reference).quantite, 6)

    def test_rejeu_idempotent(self):
        self._vente_sort(4)
        self.assertEqual(solder_reservations_vente(
            self.inst, {self.panneau.id: 4}, self.devis.reference,
            user=self.user), 0)
        self.assertEqual(self._resa().quantite, 6)

    def test_chantier_annule_no_op(self):
        Installation.objects.filter(pk=self.inst.pk).update(annule=True)
        self.inst.refresh_from_db()
        self.assertEqual(solder_reservations_vente(
            self.inst, {self.panneau.id: 10}, 'REF-X'), 0)
        self.assertEqual(self._resa().quantite, 10)

    def test_chantier_cloture_no_op(self):
        Installation.objects.filter(pk=self.inst.pk).update(
            statut=Installation.Statut.CLOTURE)
        self.inst.refresh_from_db()
        self.assertEqual(solder_reservations_vente(
            self.inst, {self.panneau.id: 10}, 'REF-X'), 0)
        self.assertEqual(self._resa().quantite, 10)
