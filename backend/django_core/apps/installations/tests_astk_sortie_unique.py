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

    # ── ASTK263 (C-ASTK-VER4-060) — facture annulée ⇒ réservation rouverte ─

    def _vente_acompte(self, n):
        """Devis accepté de 10 (stock 20, chantier, résa 10), acompte émis
        par l'API (réservation soldée) ; renvoie (devis, chantier, produit,
        facture, client API admin)."""
        from rest_framework.test import APIClient
        admin = User.objects.create_user(
            username=f'admin-astk263-{n}', password='x',
            company=self.company, role_legacy='admin')
        api = APIClient()
        api.force_authenticate(admin)
        produit = Produit.objects.create(
            company=self.company, nom=f'Panneau ASTK263-{n}',
            sku=f'SKU-ASTK263-{n}', prix_vente=Decimal('100'),
            quantite_stock=20, tva=Decimal('20.00'))
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom=f'Client {n}',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASTK263-{n}',
            client=self.devis.client, lead=lead,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'),
            taux_tva=Decimal('20.00'))
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        r = api.post(f'/api/django/ventes/devis/{devis.id}/generer-facture/',
                     {}, format='json')
        self.assertLess(r.status_code, 400, getattr(r, 'data', r))
        fac = devis.factures.order_by('id').first()
        if fac.statut == 'brouillon':
            r = api.post(f'/api/django/ventes/factures/{fac.id}/emettre/',
                         {}, format='json')
            self.assertLess(r.status_code, 400, getattr(r, 'data', r))
        resa = StockReservation.objects.get(installation=inst, produit=produit)
        self.assertTrue(resa.consomme)
        return devis, inst, produit, fac, api

    def _etat(self, inst, produit):
        resa = StockReservation.objects.get(installation=inst, produit=produit)
        produit.refresh_from_db()
        sorti = MouvementStock.objects.filter(
            produit=produit, type_mouvement=mouvement_type_sortie()).aggregate(
                t=Sum('quantite'))['t'] or 0
        return resa.quantite, resa.consomme, produit.quantite_stock, sorti

    def test_facture_annulee_rouvre_la_reservation(self):
        from apps.crm import stages
        from apps.installations.services_solde_vente import (
            rouvrir_reservations_vente,
        )
        from apps.ventes.models import Facture
        with self.subTest('a — annulée puis lead hors « Signé »'):
            devis, inst, produit, fac, api = self._vente_acompte(1)
            r = api.post(f'/api/django/ventes/factures/{fac.id}/annuler/', {},
                         format='json')
            self.assertEqual(r.status_code, 200, r.data)
            self.assertEqual(self._etat(inst, produit), (10, False, 20, 10))
            # Persistance : rejouer le récepteur ⇒ 0 modifiée.
            inst.refresh_from_db()
            self.assertEqual(rouvrir_reservations_vente(
                inst, devis.reference), 0)
            r = api.patch(f'/api/django/crm/leads/{devis.lead_id}/',
                          {'stage': stages.QUOTE_SENT, 'confirme_recul': True},
                          format='json')
            self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
            inst.refresh_from_db()
            self.assertTrue(inst.annule)
            produit.refresh_from_db()
            self.assertEqual(produit.quantite_stock, 20)
        with self.subTest('b — annulée, nouvelle facture, « Installé »'):
            devis, inst, produit, fac, api = self._vente_acompte(2)
            api.post(f'/api/django/ventes/factures/{fac.id}/annuler/', {},
                     format='json')
            r = api.post(
                f'/api/django/ventes/devis/{devis.id}/generer-facture/', {},
                format='json')
            self.assertLess(r.status_code, 400, getattr(r, 'data', r))
            nouvelle = devis.factures.exclude(pk=fac.pk).order_by('id').last()
            if nouvelle.statut == 'brouillon':
                api.post(f'/api/django/ventes/factures/{nouvelle.id}/emettre/',
                         {}, format='json')
            self.assertEqual(self._etat(inst, produit), (0, True, 10, 20))
            inst.refresh_from_db()
            changer_statut_chantier(inst, Installation.Statut.INSTALLE,
                                    self.user, verifier_gates=False)
            self.assertEqual(self._etat(inst, produit)[2:], (10, 20))
        with self.subTest('c — une autre tranche vivante : rien rouvert'):
            devis, inst, produit, fac, api = self._vente_acompte(3)
            Facture.objects.create(
                company=self.company, reference=f'FAC-ASTK263-{devis.id}',
                devis=devis, client=devis.client, statut='emise',
                type_facture='solde', montant_ht=Decimal('1'),
                montant_tva=Decimal('0'), montant_ttc=Decimal('1'))
            api.post(f'/api/django/ventes/factures/{fac.id}/annuler/', {},
                     format='json')
            self.assertEqual(self._etat(inst, produit), (0, True, 10, 10))
            r = api.patch(f'/api/django/crm/leads/{devis.lead_id}/',
                          {'stage': stages.QUOTE_SENT, 'confirme_recul': True},
                          format='json')
            self.assertEqual(r.status_code, 409, getattr(r, 'data', r))
