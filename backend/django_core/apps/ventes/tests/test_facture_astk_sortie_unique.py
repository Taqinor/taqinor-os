"""ASTK135 (C-ASTK-028) — « une vente = une sortie » côté facturation.

Sonde RESA-1 : devis de 10 panneaux accepté (chantier, réservation 10, stock
30). La facture directe sortait 10 (stock 20) sans solder la réservation du
chantier ; « Installé » ressortait 10 (stock 10). Même mécanisme pour la
livraison d'un BC toggle OFF (`marquer-livre`). Après ASTK135, la sortie de la
vente SOLDE la réservation (service chantiers ASTK120) dans la même
transaction. Aucun mock : services réels, endpoint réel.

ASTK244 (C-ASTK-VER-001) — mêmes garanties quels que soient l'ordre et la
référence des gestes (livrer-partiel, facture, livraison directe, F11,
« Installé ») : `test_compositions_une_vente_une_sortie`.

Run :
    python manage.py test apps.ventes.tests.test_facture_astk_sortie_unique
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import Installation, StockReservation
from apps.installations.services import (
    changer_statut_chantier, create_installation_from_devis,
)
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import mouvement_type_entree, mouvement_type_sortie
from apps.ventes.domain.facturation_ops import (
    facturer_devis_complet, reserver_stock_devis_facture,
)
from apps.ventes.models import BonCommande, Devis, LigneDevis, LivraisonBC

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class FactureSortieUniqueTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Co ASTK135', slug=f'co-astk135-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'resp-astk135-{_nxt()}', password='x',
            company=self.company, role_legacy='responsable')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ASTK135',
            sku=f'SKU-ASTK135-{_nxt()}', prix_vente=Decimal('100'),
            quantite_stock=30, tva=Decimal('20.00'))
        self.client_obj = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email=f'astk135-{_nxt()}@example.invalid')

    def _devis(self):
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASTK135-{_nxt()}',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'),
            taux_tva=Decimal('20.00'))
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        return devis, inst

    def _installer(self, inst):
        changer_statut_chantier(
            inst, Installation.Statut.INSTALLE, self.user,
            verifier_gates=False)

    def _sorties(self):
        return MouvementStock.objects.filter(
            produit=self.panneau, type_mouvement=mouvement_type_sortie())

    def _assert_une_sortie(self, inst, reference):
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        sorties = self._sorties()
        self.assertEqual(
            sorties.aggregate(t=Sum('quantite'))['t'], 10)
        self.assertEqual(list(sorties.values_list('reference', flat=True)),
                         [reference])
        resa = StockReservation.objects.get(
            installation=inst, produit=self.panneau)
        self.assertTrue(resa.consomme)

    def test_facture_directe_puis_installe_une_sortie(self):
        devis, inst = self._devis()
        self.assertEqual(StockReservation.objects.get(
            installation=inst, produit=self.panneau).quantite, 10)
        facturer_devis_complet(
            devis=devis, user=self.user, company=self.company, paiements=[])
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        self._installer(inst)
        self._assert_une_sortie(inst, devis.reference)

    def test_bc_livre_toggle_off_puis_installe_une_sortie(self):
        devis, inst = self._devis()
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-ASTK135-{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        self._installer(inst)
        self._assert_une_sortie(inst, bc.reference)

    def test_devis_sans_chantier_inchange(self):
        lead = Lead.objects.create(
            company=self.company, nom='Sans', prenom='Chantier',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASTK135-{_nxt()}',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'),
            taux_tva=Decimal('20.00'))
        facturer_devis_complet(
            devis=devis, user=self.user, company=self.company, paiements=[])
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        self.assertEqual(self._sorties().count(), 1)

    # ── ASTK244 (C-ASTK-VER-001) — toutes les compositions de gestes ──────
    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        return api

    def _livrer_partiel(self, devis, inst):
        bc = BonCommande.objects.get(devis=devis)
        ligne = LigneDevis.objects.get(devis=devis, produit=self.panneau)
        resp = self._api().post(
            f'/api/django/ventes/bons-commande/{bc.id}/livrer-partiel/',
            {'lignes': [{'ligne_devis': ligne.id, 'quantite': '4'}]},
            format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))

    def _facturer(self, devis, inst):
        facturer_devis_complet(
            devis=devis, user=self.user, company=self.company, paiements=[])

    def _generer_facture(self, devis, inst):
        resp = self._api().post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/')
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp))

    def _livraison_directe(self, devis, inst):
        from apps.stock.models import BonCommandeFournisseur, Fournisseur
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom=f'Fournisseur ASTK244-{_nxt()}')
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK244-{_nxt()}',
            fournisseur=fournisseur, chantier_livraison=inst,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = bcf.lignes.create(
            produit=self.panneau, quantite=10,
            prix_achat_unitaire=Decimal('60'))
        resp = self._api().post(
            f'/api/django/stock/bons-commande-fournisseur/{bcf.id}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 10}]},
            format='json')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))

    def _f11(self, devis, inst):
        from apps.installations import field_capture
        from apps.installations.models import Intervention
        intervention = Intervention.objects.create(
            company=self.company, installation=inst)
        field_capture.validate_consommation(
            field_capture.ensure_consommation(intervention), self.user)

    def _installe(self, devis, inst):
        inst.refresh_from_db()
        if inst.statut != Installation.Statut.INSTALLE:
            self._installer(inst)

    def test_compositions_une_vente_une_sortie(self):
        """ROUGE sur 5ea32b58b : (1) 14 sorties / stock 16 (sonde
        C-ASTK-VER-001). Σ SORTIE = 10 et stock = 30 + Σ ENTRÉE − 10
        partout ; la facture n'est jamais refusée ; la rejouer ne sort rien."""
        cas = {
            '1_partiel_puis_facture': (self._livrer_partiel, self._facturer),
            '2_facture_puis_partiel': (self._facturer, self._livrer_partiel),
            '3_directe_puis_facture': (
                self._livraison_directe, self._facturer),
            '4_f11_puis_facture': (self._f11, self._facturer),
            '5_partiel_puis_generer': (
                self._livrer_partiel, self._generer_facture),
            '6_installe_puis_facture': (self._installe, self._facturer),
        }
        for nom, gestes in cas.items():
            with self.subTest(cas=nom):
                self.panneau = Produit.objects.create(
                    company=self.company, nom=f'Panneau {nom}',
                    sku=f'SKU-ASTK244-{_nxt()}', prix_vente=Decimal('100'),
                    prix_achat=Decimal('60'), quantite_stock=30,
                    tva=Decimal('20.00'))
                devis, inst = self._devis()
                bc = BonCommande.objects.create(
                    company=self.company, reference=f'BC-ASTK244-{_nxt()}',
                    devis=devis, client=self.client_obj,
                    statut=BonCommande.Statut.CONFIRME)
                for geste in (*gestes, self._installe):
                    geste(devis, inst)
                reserver_stock_devis_facture(
                    devis=devis, user=self.user, company=self.company)
                mouvements = MouvementStock.objects.filter(
                    produit=self.panneau)
                sorties = mouvements.filter(
                    type_mouvement=mouvement_type_sortie()).aggregate(
                        t=Sum('quantite'))['t']
                entrees = mouvements.filter(
                    type_mouvement=mouvement_type_entree()).aggregate(
                        t=Sum('quantite'))['t'] or 0
                self.assertEqual(sorties, 10, nom)
                self.panneau.refresh_from_db()
                self.assertEqual(
                    self.panneau.quantite_stock, 30 + entrees - 10, nom)
                self.assertTrue(devis.factures.exists(), nom)
                if nom.startswith('2_'):
                    self.assertTrue(
                        LivraisonBC.objects.filter(bon_commande=bc).exists())
                    self.assertFalse(mouvements.filter(
                        reference=bc.reference).exists())
