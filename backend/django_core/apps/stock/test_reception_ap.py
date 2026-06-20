"""Tests G5 — réception fournisseur (goods-in) + factures fournisseur / AP.

Couvre :
  - réception : confirmation incrémente le stock (ENTREE) + idempotence ;
  - réception partielle vs totale → avancement du statut du BCF ;
  - référence de réception sans trou (préfixe REC) ;
  - facture fournisseur : solde dû = TTC − Σ paiements, statut recalculé ;
  - comptes à payer : liste des factures non soldées ;
  - scoping société : pas de fuite inter-tenant sur réception / facture /
    paiement.

Run :
    python manage.py test apps.stock.test_reception_ap -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    Produit, Fournisseur, MouvementStock, BonCommandeFournisseur,
    LigneBonCommandeFournisseur, ReceptionFournisseur,
    LigneReceptionFournisseur, FactureFournisseur, PaiementFournisseur,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='g5-co', nom='G5 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, sku, stock=0, prix_achat='100', prix_vente='150'):
    return Produit.objects.create(
        company=company, nom=f'Produit {sku}', sku=sku,
        prix_achat=Decimal(prix_achat), prix_vente=Decimal(prix_vente),
        quantite_stock=stock,
    )


class G5Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Grossiste G5')
        self.resp = User.objects.create_user(
            username='g5_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.resp)

    def _make_bon(self, produit, qte=10):
        bon = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{MONTH}-9001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bon, produit=produit, quantite=qte,
            prix_achat_unitaire=Decimal('90'))
        return bon, ligne


class TestReceptionFournisseur(G5Base):
    def _create_reception(self, bon, ligne, qte):
        return self.api.post(
            '/api/django/stock/receptions-fournisseur/',
            {'bon_commande': bon.id,
             'lignes': [{'ligne_commande': ligne.id, 'quantite': qte}]},
            format='json')

    def test_create_assigns_company_and_reference(self):
        produit = make_produit(self.company, 'REC-A', stock=0)
        bon, ligne = self._make_bon(produit, qte=10)
        r = self._create_reception(bon, ligne, 4)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['reference'].startswith(f'REC-{MONTH}-'))
        rec = ReceptionFournisseur.objects.get(id=r.data['id'])
        self.assertEqual(rec.company_id, self.company.id)
        self.assertEqual(rec.created_by_id, self.resp.id)
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.BROUILLON)
        # Produit dérivé serveur depuis la ligne de commande.
        self.assertEqual(rec.lignes.first().produit_id, produit.id)

    def test_confirm_increments_stock_and_is_idempotent(self):
        produit = make_produit(self.company, 'REC-B', stock=5)
        bon, ligne = self._make_bon(produit, qte=10)
        r = self._create_reception(bon, ligne, 4)
        rec_id = r.data['id']
        # Confirme → stock + 4 (5 → 9), un mouvement ENTREE de 4.
        r = self.api.post(
            f'/api/django/stock/receptions-fournisseur/{rec_id}/confirmer/')
        self.assertEqual(r.status_code, 200, r.data)
        produit.refresh_from_db()
        ligne.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 9)
        self.assertEqual(ligne.quantite_recue, 4)
        mvs = MouvementStock.objects.filter(reference=r.data['reference'])
        self.assertEqual(mvs.count(), 1)
        self.assertEqual(mvs.first().type_mouvement,
                         MouvementStock.TypeMouvement.ENTREE)
        self.assertEqual(mvs.first().quantite, 4)
        # Re-confirmer une réception déjà confirmée : refusé, jamais de
        # double-comptage du stock.
        r2 = self.api.post(
            f'/api/django/stock/receptions-fournisseur/{rec_id}/confirmer/')
        self.assertEqual(r2.status_code, 400)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 9)  # inchangé
        self.assertEqual(MouvementStock.objects.filter(
            reference=r.data['reference']).count(), 1)

    def test_partial_then_full_reception_advances_bcf_statut(self):
        produit = make_produit(self.company, 'REC-C', stock=0)
        bon, ligne = self._make_bon(produit, qte=10)
        # Réception partielle de 6.
        r = self._create_reception(bon, ligne, 6)
        self.api.post(
            f"/api/django/stock/receptions-fournisseur/{r.data['id']}/confirmer/")
        bon.refresh_from_db()
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 6)
        self.assertEqual(bon.statut, BonCommandeFournisseur.Statut.ENVOYE)
        # Réception du solde (4) → BCF entièrement reçu.
        r = self._create_reception(bon, ligne, 4)
        self.api.post(
            f"/api/django/stock/receptions-fournisseur/{r.data['id']}/confirmer/")
        bon.refresh_from_db()
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 10)
        self.assertEqual(bon.statut, BonCommandeFournisseur.Statut.RECU)

    def test_over_reception_caps_at_remaining(self):
        produit = make_produit(self.company, 'REC-D', stock=0)
        bon, ligne = self._make_bon(produit, qte=10)
        # Demande 100 reçus sur une ligne de 10 : plafonné à 10.
        r = self._create_reception(bon, ligne, 100)
        self.api.post(
            f"/api/django/stock/receptions-fournisseur/{r.data['id']}/confirmer/")
        produit.refresh_from_db()
        ligne.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 10)
        self.assertEqual(ligne.quantite_recue, 10)

    def test_reference_is_gapless(self):
        produit = make_produit(self.company, 'REC-E', stock=0)
        bon, ligne = self._make_bon(produit, qte=30)
        refs = []
        for _ in range(3):
            r = self._create_reception(bon, ligne, 1)
            refs.append(r.data['reference'])
        self.assertEqual(refs, [
            f'REC-{MONTH}-0001', f'REC-{MONTH}-0002', f'REC-{MONTH}-0003'])

    def test_cross_tenant_bon_rejected(self):
        other = make_company(slug='g5-other', nom='Other')
        foreign_p = make_produit(other, 'REC-X', stock=0)
        foreign_bon = BonCommandeFournisseur.objects.create(
            company=other, reference=f'BCF-{MONTH}-9999',
            fournisseur=Fournisseur.objects.create(company=other, nom='F'),
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        foreign_ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=foreign_bon, produit=foreign_p, quantite=5)
        r = self.api.post(
            '/api/django/stock/receptions-fournisseur/',
            {'bon_commande': foreign_bon.id,
             'lignes': [{'ligne_commande': foreign_ligne.id, 'quantite': 1}]},
            format='json')
        self.assertEqual(r.status_code, 400)

    def test_other_tenant_cannot_read_reception(self):
        produit = make_produit(self.company, 'REC-F', stock=0)
        bon, ligne = self._make_bon(produit, qte=5)
        r = self._create_reception(bon, ligne, 2)
        rec_id = r.data['id']
        other = make_company(slug='g5-other2', nom='Other2')
        intruder = User.objects.create_user(
            username='g5_intruder', password='x', role_legacy='responsable',
            company=other)
        r = auth(intruder).get(
            f'/api/django/stock/receptions-fournisseur/{rec_id}/')
        self.assertEqual(r.status_code, 404)


class TestFactureFournisseur(G5Base):
    def _create_facture(self, **over):
        payload = {
            'fournisseur': self.fournisseur.id,
            'date_facture': '2026-06-01',
            'date_echeance': '2026-07-01',
            'montant_ht': '1000.00',
            'montant_tva': '200.00',
            'montant_ttc': '1200.00',
        }
        payload.update(over)
        return self.api.post(
            '/api/django/stock/factures-fournisseur/', payload, format='json')

    def test_create_assigns_company_reference_and_statut(self):
        r = self._create_facture()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['reference'].startswith(f'FF-{MONTH}-'))
        self.assertEqual(r.data['statut'], 'a_payer')
        self.assertEqual(Decimal(r.data['solde_du']), Decimal('1200.00'))
        fac = FactureFournisseur.objects.get(id=r.data['id'])
        self.assertEqual(fac.company_id, self.company.id)
        self.assertEqual(fac.created_by_id, self.resp.id)

    def test_payments_reduce_balance_and_advance_statut(self):
        r = self._create_facture()
        fid = r.data['id']
        # Paiement partiel de 500 → partiellement payée, solde 700.
        r = self.api.post(
            f'/api/django/stock/factures-fournisseur/{fid}/paiements/',
            {'montant': '500.00', 'date_paiement': '2026-06-10',
             'mode': 'virement'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['statut'], 'partiellement_payee')
        self.assertEqual(Decimal(r.data['solde_du']), Decimal('700.00'))
        # Solde de 700 → payée, solde 0.
        r = self.api.post(
            f'/api/django/stock/factures-fournisseur/{fid}/paiements/',
            {'montant': '700.00', 'date_paiement': '2026-06-20',
             'mode': 'cheque'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['statut'], 'payee')
        self.assertEqual(Decimal(r.data['solde_du']), Decimal('0.00'))

    def test_deleting_payment_reopens_facture(self):
        r = self._create_facture()
        fid = r.data['id']
        self.api.post(
            f'/api/django/stock/factures-fournisseur/{fid}/paiements/',
            {'montant': '1200.00', 'mode': 'virement'}, format='json')
        fac = FactureFournisseur.objects.get(id=fid)
        self.assertEqual(fac.statut, FactureFournisseur.Statut.PAYEE)
        paiement = fac.paiements.first()
        # Suppression du paiement via le viewset paiements → facture rouverte.
        # Suppression réservée admin.
        admin = User.objects.create_user(
            username='g5_admin', password='x', role_legacy='admin',
            company=self.company)
        r = auth(admin).delete(
            f'/api/django/stock/paiements-fournisseur/{paiement.id}/')
        self.assertEqual(r.status_code, 204)
        fac.refresh_from_db()
        self.assertEqual(fac.statut, FactureFournisseur.Statut.A_PAYER)
        self.assertEqual(fac.solde_du, Decimal('1200.00'))

    def test_comptes_a_payer_lists_unpaid_only(self):
        # Une facture soldée + une partiellement payée + une à payer.
        r1 = self._create_facture(montant_ttc='100.00', montant_ht='100.00',
                                   montant_tva='0.00')
        self.api.post(
            f"/api/django/stock/factures-fournisseur/{r1.data['id']}/paiements/",
            {'montant': '100.00', 'mode': 'virement'}, format='json')  # payée
        self._create_facture(montant_ttc='200.00')  # à payer
        r3 = self._create_facture(montant_ttc='300.00')
        self.api.post(
            f"/api/django/stock/factures-fournisseur/{r3.data['id']}/paiements/",
            {'montant': '100.00', 'mode': 'virement'}, format='json')  # partiel
        r = self.api.get(
            '/api/django/stock/factures-fournisseur/comptes-a-payer/')
        self.assertEqual(r.status_code, 200, r.data)
        statuts = {f['statut'] for f in r.data['results']}
        self.assertNotIn('payee', statuts)
        self.assertEqual(len(r.data['results']), 2)
        # total dû = 200 (à payer) + 200 (300 − 100 partiel).
        self.assertEqual(Decimal(r.data['total_du']), Decimal('400.00'))

    def test_cross_tenant_fournisseur_rejected(self):
        other = make_company(slug='g5-other3', nom='Other3')
        foreign_f = Fournisseur.objects.create(company=other, nom='F3')
        r = self.api.post(
            '/api/django/stock/factures-fournisseur/',
            {'fournisseur': foreign_f.id, 'montant_ttc': '100.00'},
            format='json')
        self.assertEqual(r.status_code, 400)

    def test_other_tenant_cannot_read_facture(self):
        r = self._create_facture()
        fid = r.data['id']
        other = make_company(slug='g5-other4', nom='Other4')
        intruder = User.objects.create_user(
            username='g5_intruder2', password='x', role_legacy='responsable',
            company=other)
        r = auth(intruder).get(
            f'/api/django/stock/factures-fournisseur/{fid}/')
        self.assertEqual(r.status_code, 404)

    def test_payment_company_forced_server_side(self):
        """Le paiement ignore toute company envoyée dans le corps : il est
        toujours scopé à la société de l'utilisateur."""
        other = make_company(slug='g5-other5', nom='Other5')
        r = self._create_facture()
        fid = r.data['id']
        r = self.api.post(
            f'/api/django/stock/factures-fournisseur/{fid}/paiements/',
            {'montant': '100.00', 'mode': 'virement', 'company': other.id},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        paiement = PaiementFournisseur.objects.get(facture_id=fid)
        self.assertEqual(paiement.company_id, self.company.id)
