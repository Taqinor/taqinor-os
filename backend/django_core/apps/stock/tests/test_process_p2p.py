"""YTEST6 — E2E processus procure-to-pay complet (achat → règlement).

Parcourt LA chaîne réelle, par les endpoints existants :
  1. Bon de commande fournisseur (BCF) créé avec ses lignes ;
  2. Réception confirmée → MouvementStock ENTREE par ligne, stock
     incrémenté, lot (LotEntrepot) et séries (installations.SerieEntrepot,
     lu via SON selector) alimentés, valorisation au coût moyen pondéré ;
  3. Facture fournisseur générée depuis la réception (`facturer`) →
     écriture comptable d'achat (61xx/3455 → 4411) générée par le bus
     d'événements (YLEDG2), solde fournisseur = TTC ;
  4. Règlement (PaiementFournisseur) → écriture de règlement (4411 →
     trésorerie), facture PAYÉE, solde fournisseur soldé à 0.

Frontières : compta lu UNIQUEMENT via ``apps.compta.selectors`` ;
installations UNIQUEMENT via ``apps.installations.selectors`` — jamais un
import des models d'une autre app. ``COMPTA_AUTO_ECRITURES=True`` active la
génération d'écritures (toggle YLEDG2).

Run :
    python manage.py test apps.stock.tests.test_process_p2p -v2
"""
from decimal import Decimal

from django.test import override_settings

from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, LotEntrepot, MouvementStock,
)
from apps.stock.services import average_cost_with_source
from testkit.base import TenantAPITestCase

BASE = '/api/django/stock'


@override_settings(COMPTA_AUTO_ECRITURES=True)
class TestProcessP2P(TenantAPITestCase):
    """Le parcours procure-to-pay complet, en un seul fil (chaque étape
    asserte mouvement / valorisation / écriture / solde)."""

    def setUp(self):
        super().setUp()
        from apps.stock.models import Fournisseur, Produit
        self.api = self.client_as(role='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur P2P')
        self.produit_lot = Produit.objects.create(
            company=self.company, nom='Câble solaire 6mm²', sku='CAB6',
            prix_vente=Decimal('15'), prix_achat=Decimal('0'),
            quantite_stock=0, tva=Decimal('20'))
        self.produit_serie = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND5',
            prix_vente=Decimal('4500'), prix_achat=Decimal('0'),
            quantite_stock=0, tva=Decimal('20'))

    # ── Helpers d'étape (réutilisés par les tests ciblés) ────────────────

    def _creer_bcf(self, quantite_lot=10, prix_lot='100.00',
                   quantite_serie=2, prix_serie='500.00'):
        resp = self.api.post(f'{BASE}/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'date_commande': '2026-07-10',
            'lignes': [
                {'produit': self.produit_lot.id, 'quantite': quantite_lot,
                 'prix_achat_unitaire': prix_lot},
                {'produit': self.produit_serie.id,
                 'quantite': quantite_serie,
                 'prix_achat_unitaire': prix_serie},
            ],
        }, format='json')
        assert resp.status_code == 201, resp.content
        return BonCommandeFournisseur.objects.get(id=resp.json()['id'])

    def _recevoir(self, bcf, series=None, numero_lot='LOT-P2P-01'):
        lignes_bcf = {
            ligne.produit_id: ligne for ligne in bcf.lignes.all()}
        payload_lignes = [{
            'ligne_commande': lignes_bcf[self.produit_lot.id].id,
            'quantite': lignes_bcf[self.produit_lot.id].quantite,
            'numero_lot': numero_lot,
        }, {
            'ligne_commande': lignes_bcf[self.produit_serie.id].id,
            'quantite': lignes_bcf[self.produit_serie.id].quantite,
            'numeros_serie': series or ['SN-P2P-1', 'SN-P2P-2'],
        }]
        resp = self.api.post(f'{BASE}/receptions-fournisseur/', {
            'bon_commande': bcf.id,
            'date_reception': '2026-07-10',
            'lignes': payload_lignes,
        }, format='json')
        assert resp.status_code == 201, resp.content
        reception_id = resp.json()['id']
        resp = self.api.post(
            f'{BASE}/receptions-fournisseur/{reception_id}/confirmer/')
        assert resp.status_code == 200, resp.content
        return reception_id, resp.json()['reference']

    def _facturer(self, reception_id):
        resp = self.api.post(
            f'{BASE}/receptions-fournisseur/{reception_id}/facturer/')
        assert resp.status_code == 201, resp.content
        return FactureFournisseur.objects.get(id=resp.json()['id'])

    def _payer(self, facture, montant):
        resp = self.api.post(f'{BASE}/paiements-fournisseur/', {
            'facture': facture.id,
            'montant': str(montant),
            'date_paiement': '2026-07-10',
            'mode': 'virement',
        }, format='json')
        assert resp.status_code == 201, resp.content
        return resp.json()

    def _solde_fournisseur(self):
        # Cross-app : écritures/soldes lus via le SELECTOR compta uniquement.
        from apps.compta.selectors import releve_fournisseur
        releve = releve_fournisseur(self.company, self.fournisseur.id)
        return releve

    # ── Le parcours complet ───────────────────────────────────────────────

    def test_p2p_bc_reception_facture_reglement(self):
        # 1) BCF : 10 câbles @100 + 2 onduleurs @500.
        bcf = self._creer_bcf()
        self.assertEqual(bcf.lignes.count(), 2)

        # 2) Réception confirmée.
        reception_id, reception_ref = self._recevoir(bcf)

        #   → un MouvementStock ENTREE par ligne, référencé à la réception.
        mouvements = MouvementStock.objects.filter(
            company=self.company, reference=reception_ref,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE)
        self.assertEqual(mouvements.count(), 2)
        mvt_lot = mouvements.get(produit=self.produit_lot)
        self.assertEqual(mvt_lot.quantite, 10)
        self.assertEqual(mvt_lot.quantite_avant, 0)
        self.assertEqual(mvt_lot.quantite_apres, 10)

        #   → stock incrémenté.
        self.produit_lot.refresh_from_db()
        self.produit_serie.refresh_from_db()
        self.assertEqual(self.produit_lot.quantite_stock, 10)
        self.assertEqual(self.produit_serie.quantite_stock, 2)

        #   → valorisation au coût moyen (dérivée des réceptions, pas du
        #     catalogue).
        cout, source = average_cost_with_source(self.produit_lot)
        self.assertEqual(cout, Decimal('100.00'))
        self.assertEqual(source, 'achats')
        cout_serie, _ = average_cost_with_source(self.produit_serie)
        self.assertEqual(cout_serie, Decimal('500.00'))

        #   → lot alimenté (XSTK6, modèle du MÊME app).
        lot = LotEntrepot.objects.get(
            company=self.company, produit=self.produit_lot,
            numero_lot='LOT-P2P-01')
        self.assertEqual(lot.quantite_recue, 10)
        self.assertEqual(lot.quantite_restante, 10)

        #   → séries enregistrées à l'entrepôt (YSTCK7) — lues via LE
        #     selector installations (jamais son modèle).
        from apps.installations.selectors import (
            serie_entrepot_scoped_by_serial,
        )
        for numero in ('SN-P2P-1', 'SN-P2P-2'):
            serie = serie_entrepot_scoped_by_serial(
                self.company, self.produit_serie.id, numero)
            self.assertIsNotNone(serie, f'Série {numero} absente.')
            self.assertEqual(serie.statut, 'en_stock')

        #   → le BCF est entièrement reçu.
        bcf.refresh_from_db()
        self.assertEqual(bcf.statut, BonCommandeFournisseur.Statut.RECU)

        # 3) Facture fournisseur générée depuis la réception.
        facture = self._facturer(reception_id)
        # HT = 10×100 + 2×500 = 2000 ; TVA 20 % = 400 ; TTC = 2400.
        self.assertEqual(facture.montant_ht, Decimal('2000.00'))
        self.assertEqual(facture.montant_tva, Decimal('400.00'))
        self.assertEqual(facture.montant_ttc, Decimal('2400.00'))
        self.assertEqual(facture.statut, FactureFournisseur.Statut.A_PAYER)

        #   → écriture d'achat générée (YLEDG2) : le compte fournisseur
        #     (4411) porte la dette TTC — lu via le selector compta.
        releve = self._solde_fournisseur()
        self.assertEqual(releve['totaux']['credit'], Decimal('2400.00'))
        self.assertEqual(releve['totaux']['solde_du'], Decimal('2400.00'))
        self.assertEqual(len(releve['lignes']), 1)

        # 4) Règlement intégral → facture payée, solde soldé à 0.
        self._payer(facture, Decimal('2400.00'))
        facture.refresh_from_db()
        self.assertEqual(facture.statut, FactureFournisseur.Statut.PAYEE)

        releve = self._solde_fournisseur()
        self.assertEqual(releve['totaux']['debit'], Decimal('2400.00'))
        self.assertEqual(releve['totaux']['solde_du'], Decimal('0.00'))
        # Deux mouvements au relevé : la facture (crédit) + le règlement
        # (débit) — l'écriture de règlement existe bien.
        self.assertEqual(len(releve['lignes']), 2)

    def test_valorisation_cout_moyen_pondere_sur_deux_receptions(self):
        # Réception 1 : 10 @100 ; réception 2 : 10 @120 → moyenne 110.00.
        bcf1 = self._creer_bcf(quantite_lot=10, prix_lot='100.00',
                               quantite_serie=1, prix_serie='500.00')
        self._recevoir(bcf1, series=['SN-CMP-1'], numero_lot='LOT-CMP-1')
        bcf2 = self._creer_bcf(quantite_lot=10, prix_lot='120.00',
                               quantite_serie=1, prix_serie='500.00')
        self._recevoir(bcf2, series=['SN-CMP-2'], numero_lot='LOT-CMP-2')

        cout, source = average_cost_with_source(self.produit_lot)
        self.assertEqual(cout, Decimal('110.00'))
        self.assertEqual(source, 'achats')
        self.produit_lot.refresh_from_db()
        self.assertEqual(self.produit_lot.quantite_stock, 20)

    def test_isolation_multi_tenant(self):
        # Le parcours de la société A ne laisse RIEN voir/écrire chez B.
        bcf = self._creer_bcf()
        reception_id, _ = self._recevoir(bcf)
        facture = self._facturer(reception_id)
        self._payer(facture, Decimal('2400.00'))

        self.assertFalse(
            MouvementStock.objects.filter(
                company=self.other_company).exists())
        self.assertFalse(
            FactureFournisseur.objects.filter(
                company=self.other_company).exists())
        from apps.compta.selectors import releve_fournisseur
        releve_autre = releve_fournisseur(
            self.other_company, self.fournisseur.id)
        self.assertEqual(len(releve_autre['lignes']), 0)
        self.assertEqual(
            releve_autre['totaux']['solde_du'], Decimal('0'))
