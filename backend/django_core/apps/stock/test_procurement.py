"""Tests approvisionnement fournisseur (N11/N12/N13).

Couvre :
  - création BCF + référence sans trou (highest+1, jamais count+1) ;
  - réception partielle → stock augmenté du reçu SEULEMENT + idempotence ;
  - réception totale → statut Reçu ;
  - besoin matériel : calcul des manques + scoping société ;
  - le prix d'achat n'apparaît jamais dans un contexte client.

Run :
    python manage.py test apps.stock.test_procurement -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import (
    Produit, Fournisseur, MouvementStock, BonCommandeFournisseur,
    LigneBonCommandeFournisseur,
)
from apps.installations.models import Installation
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='proc-co', nom='Proc Co'):
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


class ProcurementBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Grossiste Solaire')
        self.resp = User.objects.create_user(
            username='proc_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.resp)


class TestBCFCreation(ProcurementBase):
    def _create_payload(self, produit, qte=10, prix='90'):
        return {
            'fournisseur': self.fournisseur.id,
            'lignes': [
                {'produit': produit.id, 'quantite': qte,
                 'prix_achat_unitaire': prix},
            ],
        }

    def test_create_bcf_assigns_company_and_reference(self):
        produit = make_produit(self.company, 'SKU-A')
        r = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/',
            self._create_payload(produit), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['reference'].startswith(f'BCF-{MONTH}-'))
        bon = BonCommandeFournisseur.objects.get(id=r.data['id'])
        self.assertEqual(bon.company_id, self.company.id)
        self.assertEqual(bon.created_by_id, self.resp.id)
        self.assertEqual(bon.statut, BonCommandeFournisseur.Statut.BROUILLON)

    def test_reference_is_gapless_highest_plus_one(self):
        produit = make_produit(self.company, 'SKU-B')
        refs = []
        for _ in range(3):
            r = self.api.post(
                '/api/django/stock/bons-commande-fournisseur/',
                self._create_payload(produit), format='json')
            self.assertEqual(r.status_code, 201, r.data)
            refs.append(r.data['reference'])
        self.assertEqual(refs, [
            f'BCF-{MONTH}-0001', f'BCF-{MONTH}-0002', f'BCF-{MONTH}-0003'])
        # Supprimer le dernier puis recréer : highest+1 (jamais count+1, qui
        # collisionnerait en réutilisant 0003).
        BonCommandeFournisseur.objects.get(reference=refs[-1]).delete()
        r = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/',
            self._create_payload(produit), format='json')
        self.assertEqual(r.data['reference'], f'BCF-{MONTH}-0003')

    def test_create_rejects_cross_tenant_produit(self):
        other = make_company(slug='other-co', nom='Other')
        foreign = make_produit(other, 'SKU-X')
        r = self.api.post(
            '/api/django/stock/bons-commande-fournisseur/',
            self._create_payload(foreign), format='json')
        self.assertEqual(r.status_code, 400)


class TestReception(ProcurementBase):
    def _make_bon(self, produit, qte=10, statut=None):
        bon = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{MONTH}-5001',
            fournisseur=self.fournisseur,
            statut=statut or BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bon, produit=produit, quantite=qte,
            prix_achat_unitaire=Decimal('90'))
        return bon, ligne

    def test_partial_reception_increases_stock_by_received_only(self):
        produit = make_produit(self.company, 'SKU-R', stock=5)
        bon, ligne = self._make_bon(produit, qte=10)
        r = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bon.id}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 4}]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        produit.refresh_from_db()
        ligne.refresh_from_db()
        bon.refresh_from_db()
        # Stock augmenté de 4 seulement (5 → 9), pas des 10 commandés.
        self.assertEqual(produit.quantite_stock, 9)
        self.assertEqual(ligne.quantite_recue, 4)
        self.assertEqual(bon.statut, BonCommandeFournisseur.Statut.ENVOYE)
        # Un mouvement ENTREE tracé.
        mv = MouvementStock.objects.get(reference=bon.reference)
        self.assertEqual(mv.type_mouvement, MouvementStock.TypeMouvement.ENTREE)
        self.assertEqual(mv.quantite, 4)

    def test_over_reception_caps_at_remaining_idempotent(self):
        produit = make_produit(self.company, 'SKU-C', stock=0)
        bon, ligne = self._make_bon(produit, qte=10)
        # Recevoir 8.
        self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bon.id}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 8}]},
            format='json')
        # Demander 100 de plus : plafonné au reste (2), jamais 100.
        r = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bon.id}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 100}]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        produit.refresh_from_db()
        ligne.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 10)  # 8 + 2
        self.assertEqual(ligne.quantite_recue, 10)

    def test_full_reception_marks_recu(self):
        produit = make_produit(self.company, 'SKU-F', stock=0)
        bon, ligne = self._make_bon(produit, qte=6)
        r = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bon.id}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 6}]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        bon.refresh_from_db()
        produit.refresh_from_db()
        self.assertEqual(bon.statut, BonCommandeFournisseur.Statut.RECU)
        self.assertEqual(produit.quantite_stock, 6)

    def test_reception_already_full_is_safe(self):
        produit = make_produit(self.company, 'SKU-D', stock=0)
        bon, ligne = self._make_bon(produit, qte=3)
        self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bon.id}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 3}]},
            format='json')
        # Le BCF est maintenant Reçu : nouvelle réception rejetée proprement.
        r = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bon.id}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 1}]},
            format='json')
        self.assertEqual(r.status_code, 400)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 3)  # inchangé


class TestBesoinMateriel(ProcurementBase):
    def _chantier_with_devis(self, lignes_spec):
        cl = Client.objects.create(
            company=self.company, nom='Cl', prenom='Ient',
            email='cl@example.com', telephone='+212600000001')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-7001', client=cl,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        for produit, qte in lignes_spec:
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal(qte), prix_unitaire=produit.prix_vente)
        inst = Installation.objects.create(
            company=self.company, reference=f'CH-{MONTH}-0001',
            client=cl, devis=devis)
        return inst

    def test_shortfall_computed(self):
        p1 = make_produit(self.company, 'SKU-P1', stock=3)  # besoin 10 → manque 7
        p2 = make_produit(self.company, 'SKU-P2', stock=20)  # besoin 5 → ok
        inst = self._chantier_with_devis([(p1, 10), (p2, 5)])
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/besoin-materiel/')
        self.assertEqual(r.status_code, 200, r.data)
        by_sku = {it['sku']: it for it in r.data['items']}
        self.assertEqual(by_sku['SKU-P1']['requis'], 10)
        self.assertEqual(by_sku['SKU-P1']['disponible'], 3)
        self.assertEqual(by_sku['SKU-P1']['manque'], 7)
        self.assertEqual(by_sku['SKU-P2']['manque'], 0)
        self.assertEqual(r.data['nb_manques'], 1)

    def test_duplicate_lines_aggregate(self):
        p1 = make_produit(self.company, 'SKU-AGG', stock=2)
        inst = self._chantier_with_devis([(p1, 4), (p1, 5)])
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/besoin-materiel/')
        item = r.data['items'][0]
        self.assertEqual(item['requis'], 9)
        self.assertEqual(item['manque'], 7)

    def test_company_scoping_blocks_other_tenant_chantier(self):
        other = make_company(slug='other2', nom='Other2')
        cl = Client.objects.create(
            company=other, nom='X', prenom='Y', email='x@x.com',
            telephone='+212600000099')
        inst = Installation.objects.create(
            company=other, reference=f'CH-{MONTH}-9999', client=cl)
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/besoin-materiel/')
        self.assertEqual(r.status_code, 404)

    def test_commander_besoin_drafts_bcf_for_shortfall(self):
        p1 = make_produit(self.company, 'SKU-CMD', stock=1, prix_achat='80')
        inst = self._chantier_with_devis([(p1, 10)])
        r = self.api.post(
            f'/api/django/installations/chantiers/{inst.id}/commander-besoin/',
            {'fournisseur': self.fournisseur.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['statut'], 'brouillon')
        self.assertEqual(len(r.data['lignes']), 1)
        ligne = r.data['lignes'][0]
        self.assertEqual(ligne['quantite'], 9)  # manque
        self.assertEqual(Decimal(ligne['prix_achat_unitaire']), Decimal('80'))


class TestBuyPriceConfidentiality(ProcurementBase):
    def test_buy_price_never_in_client_facing_devis_pdf_context(self):
        """Le prix d'achat ne doit jamais apparaître dans le contexte d'un
        document CLIENT. On vérifie que le moteur de PDF de devis n'expose
        aucun prix_achat sur ses lignes."""
        cl = Client.objects.create(
            company=self.company, nom='Cl', prenom='I',
            email='c@c.com', telephone='+212600000002')
        produit = make_produit(
            self.company, 'SKU-CONF', stock=5, prix_achat='999',
            prix_vente='1500')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-7777', client=cl,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal('1'), prix_unitaire=produit.prix_vente)
        # Le modèle LigneDevis n'a aucun champ prix_achat ; le prix d'achat
        # vit uniquement sur Produit. La sérialisation client du devis ne doit
        # pas relayer prix_achat.
        from apps.ventes.serializers import DevisSerializer
        data = DevisSerializer(devis, context={'request': None}).data
        serialized = str(data)
        self.assertNotIn('999', serialized)
        self.assertNotIn('prix_achat', serialized)

    def test_supplier_pdf_shows_buy_price(self):
        """Le PDF FOURNISSEUR (interne) montre légitimement le prix d'achat."""
        from apps.stock.utils.pdf_fournisseur import build_bcf_context
        produit = make_produit(
            self.company, 'SKU-SUP', stock=0, prix_achat='123.45')
        bon = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{MONTH}-6001',
            fournisseur=self.fournisseur)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bon, produit=produit, quantite=2,
            prix_achat_unitaire=Decimal('123.45'))
        ctx = build_bcf_context(bon)
        self.assertEqual(ctx['lignes'][0].prix_achat_unitaire,
                         Decimal('123.45'))
        self.assertEqual(ctx['total_achat'], Decimal('246.90'))


class TestInventaire(TestCase):
    """N16 — inventaire physique : comptage → ajustement audité (admin)."""

    def setUp(self):
        self.company = make_company(slug='inv-co', nom='Inv Co')
        self.admin = User.objects.create_user(
            username='inv_admin', password='x', role_legacy='admin',
            company=self.company)
        self.resp = User.objects.create_user(
            username='inv_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.p1 = make_produit(self.company, 'INV-1', stock=10)
        self.p2 = make_produit(self.company, 'INV-2', stock=5)

    def test_count_posts_adjustment_and_sets_stock(self):
        r = auth(self.admin).post('/api/django/stock/produits/inventaire/', {
            'motif': 'Comptage annuel',
            'lignes': [
                {'produit': self.p1.id, 'quantite_comptee': 8},
                {'produit': self.p2.id, 'quantite_comptee': 5},
            ],
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['ajustes'], 1)
        self.assertEqual(r.data['inchanges'], 1)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.quantite_stock, 8)
        self.assertTrue(MouvementStock.objects.filter(
            produit=self.p1, type_mouvement='ajustement').exists())

    def test_non_admin_forbidden(self):
        r = auth(self.resp).post('/api/django/stock/produits/inventaire/', {
            'lignes': [{'produit': self.p1.id, 'quantite_comptee': 3}],
        }, format='json')
        self.assertEqual(r.status_code, 403)
