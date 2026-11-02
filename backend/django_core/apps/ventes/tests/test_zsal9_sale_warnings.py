"""
ZSAL9 — Avertissements de vente configurables par produit / par client
(« sale warnings » façon Odoo).

Un produit/client porteur d'un ``avertissement_vente`` non bloquant n'empêche
rien (affiché à l'écran) ; un ``avertissement_bloquant`` refuse l'acceptation /
la génération de facture SAUF override responsable/admin, journalisé au chatter.
Champs vides = comportement historique inchangé. Scoping société vérifié.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zsal9_sale_warnings -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisActivity, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='zsal9-co', nom='ZSAL9 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZSAL9SaleWarningTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zsal9_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Acme', email='zsal9@example.com',
        )

    def _make_devis(self, produit):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-9001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), created_by=self.admin,
        )
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
        )
        return devis

    def _accepter(self, devis, **body):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', **body}, format='json')

    def test_facture_de_bc_et_consolidation_bloquees(self):
        """AARG32 (C-AARG-034) — client sous avertissement bloquant : facture de
        BC et consolidation 403 ; dérogation d'un admin 201 et journalisée ; le
        drapeau d'un Commercial ne passe pas. Rien n'est créé sur un refus."""
        from apps.ventes.models import BonCommande, Facture
        p = Produit.objects.create(
            company=self.company, nom='Kit', sku='ZSAL9-AARG32',
            prix_vente=Decimal('1000'), quantite_stock=10)
        d1, d2, d3 = [Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-93{i}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), created_by=self.admin)
            for i in range(3)]
        for devis in (d1, d2, d3):
            LigneDevis.objects.create(
                devis=devis, produit=p, designation='Kit',
                quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
                taux_tva=Decimal('20.00'))
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-9301', devis=d3,
            client=self.client_obj, statut=BonCommande.Statut.CONFIRME)
        Client.objects.filter(pk=self.client_obj.pk).update(
            avertissement_bloquant=True, avertissement_vente='Litige en cours')
        url_bc = f'/api/django/ventes/bons-commande/{bc.id}/creer-facture/'
        url_c = '/api/django/ventes/factures/consolider/'
        ids = [d1.id, d2.id]
        commercial = auth(User.objects.create_user(
            username='zsal9_com', password='x', role_legacy='commercial',
            company=self.company))
        for api, url, corps in (
                (self.api, url_bc, {}),
                (self.api, url_c, {'devis_ids': ids}),
                (commercial, url_bc, {'override_avertissement': True}),
                (commercial, url_c, {'devis_ids': ids,
                                     'override_avertissement': True})):
            r = api.post(url, corps, format='json')
            self.assertEqual(r.status_code, 403, r.data)
        for corps_ok in ({'override_avertissement': False}, {}):
            r = self.api.post(url_bc, corps_ok, format='json')
            self.assertEqual(r.data.get('code'), 'sale_warning', r.data)
        self.assertFalse(Facture.objects.filter(
            company=self.company).exists())
        r = self.api.post(url_bc, {'override_avertissement': True},
                          format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = self.api.post(url_c, {'devis_ids': ids,
                                  'override_avertissement': True},
                          format='json')
        self.assertEqual(r.status_code, 201, r.data)
        for devis in (d1, d2, d3):
            self.assertTrue(DevisActivity.objects.filter(
                devis=devis, field='avertissement_vente').exists())

    def test_no_warning_accepter_passes(self):
        p = Produit.objects.create(
            company=self.company, nom='Panneau', sku='ZSAL9-NONE',
            prix_vente=Decimal('1000'), quantite_stock=10)
        devis = self._make_devis(p)
        r = self._accepter(devis)
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_non_blocking_warning_does_not_block(self):
        p = Produit.objects.create(
            company=self.company, nom='Coffret', sku='ZSAL9-SOFT',
            prix_vente=Decimal('1000'), quantite_stock=10,
            avertissement_vente='Rupture prolongée', avertissement_bloquant=False)
        devis = self._make_devis(p)
        r = self._accepter(devis)
        self.assertEqual(r.status_code, 200, r.data)

    def test_blocking_product_warning_refuses_accepter(self):
        p = Produit.objects.create(
            company=self.company, nom='MC4', sku='ZSAL9-HARD',
            prix_vente=Decimal('1000'), quantite_stock=10,
            avertissement_vente='Produit interdit à la vente',
            avertissement_bloquant=True)
        devis = self._make_devis(p)
        r = self._accepter(devis)
        self.assertEqual(r.status_code, 403, r.data)
        self.assertTrue(r.data.get('sale_warning'))
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_blocking_override_passes_and_is_logged(self):
        p = Produit.objects.create(
            company=self.company, nom='MC4', sku='ZSAL9-OVR',
            prix_vente=Decimal('1000'), quantite_stock=10,
            avertissement_vente='Produit interdit à la vente',
            avertissement_bloquant=True)
        devis = self._make_devis(p)
        r = self._accepter(devis, override_avertissement=True)
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertTrue(DevisActivity.objects.filter(
            devis=devis, field='avertissement_vente').exists())

    def test_blocking_client_warning_refuses_accepter(self):
        blocked = Client.objects.create(
            company=self.company, nom='À comptant', email='zsal9c@example.com',
            avertissement_vente='Client à traiter au comptant',
            avertissement_bloquant=True)
        p = Produit.objects.create(
            company=self.company, nom='Panneau', sku='ZSAL9-CLI',
            prix_vente=Decimal('1000'), quantite_stock=10)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-9002',
            client=blocked, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), created_by=self.admin)
        LigneDevis.objects.create(
            devis=devis, produit=p, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        r = self._accepter(devis)
        self.assertEqual(r.status_code, 403, r.data)
        self.assertTrue(r.data.get('sale_warning'))

    def test_warning_is_company_scoped(self):
        # Un produit d'une AUTRE société avec le même warning bloquant ne doit
        # jamais influencer le devis de notre société (le sélecteur est scopé).
        other = make_company(slug='zsal9-other', nom='Other')
        Produit.objects.create(
            company=other, nom='Étranger', sku='ZSAL9-OTHER',
            prix_vente=Decimal('1000'), quantite_stock=10,
            avertissement_vente='Interdit', avertissement_bloquant=True)
        p = Produit.objects.create(
            company=self.company, nom='Panneau', sku='ZSAL9-SCOPE',
            prix_vente=Decimal('1000'), quantite_stock=10)
        devis = self._make_devis(p)
        r = self._accepter(devis)
        self.assertEqual(r.status_code, 200, r.data)

    def test_selector_returns_only_warned_products(self):
        from apps.stock import selectors
        p1 = Produit.objects.create(
            company=self.company, nom='Avec', sku='ZSAL9-SEL1',
            prix_vente=Decimal('1'), quantite_stock=1,
            avertissement_vente='msg', avertissement_bloquant=True)
        p2 = Produit.objects.create(
            company=self.company, nom='Sans', sku='ZSAL9-SEL2',
            prix_vente=Decimal('1'), quantite_stock=1)
        rows = selectors.produits_avertissements(
            self.company, [p1.id, p2.id])
        ids = {r['id'] for r in rows}
        self.assertIn(p1.id, ids)
        self.assertNotIn(p2.id, ids)
