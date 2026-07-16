"""XPOS17 — QR showroom → fiche produit publique (e-catalogue FG214).

Couvre :
  - impression d'étiquettes « showroom » (`etiquettes-showroom`) : le QR
    encode l'URL de la fiche PUBLIQUE du bon produit du bon tenant ; jeton
    de catalogue requis, validé société ; produits non exposés exclus ;
  - la fiche publique (HTML + JSON) : specs, prix TTC, garantie,
    disponibilité INDICATIVE — jamais prix_achat ni marge ;
  - résolution stricte : jeton invalide/expiré → 404 ; produit hors
    catalogue → 404 ; jamais de fuite cross-tenant ;
  - CTA « Être rappelé » (QJ27) : crée/dédupe un lead CRM ; honeypot ;
  - CTA « Demander un devis » (XPOS14, endpoint existant) : crée lead +
    devis depuis la fiche.

Run :
    python manage.py test apps.stock.test_xpos17_showroom -v2
"""
from decimal import Decimal

from apps.compta.models import ECatalogue
from apps.stock.models import Produit
from apps.stock import labels
from testkit.base import TenantAPITestCase


class ShowroomBase(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PV550',
            description='Module monocristallin haute performance.',
            marque='JA Solar', garantie='25 ans',
            prix_vente=Decimal('1500'), prix_achat=Decimal('937'),
            quantite_stock=12)
        self.hors_catalogue = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW',
            prix_vente=Decimal('4500'), prix_achat=Decimal('3000'))
        self.cat = ECatalogue.objects.create(
            company=self.company, titre='Showroom Casablanca',
            token='xpos17-tok-principal',
            produit_ids=[self.produit.id])
        # Catalogue d'une AUTRE société (isolation).
        self.produit_autre = Produit.objects.create(
            company=self.other_company, nom='Panneau 550W',
            prix_vente=Decimal('1500'), prix_achat=Decimal('937'))
        self.cat_autre = ECatalogue.objects.create(
            company=self.other_company, titre='Autre société',
            token='xpos17-tok-autre',
            produit_ids=[self.produit_autre.id])

    def _fiche_url(self, token=None, produit_id=None):
        token = token or self.cat.token
        produit_id = produit_id or self.produit.id
        return (f'/api/django/public/stock/showroom/{token}'
                f'/produit/{produit_id}/')


class TestEtiquettesShowroom(ShowroomBase):
    def _print(self, **params):
        base = {
            'ids': str(self.produit.id),
            'catalogue_token': self.cat.token,
            'sortie': 'html',
        }
        base.update(params)
        qs = '&'.join(f'{k}={v}' for k, v in base.items())
        return self.client_as().get(
            f'/api/django/stock/produits/etiquettes-showroom/?{qs}')

    def test_etiquette_encodes_public_fiche_url(self):
        resp = self._print()
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.content.decode()
        self.assertIn(
            f'/api/django/public/stock/showroom/{self.cat.token}'
            f'/produit/{self.produit.id}/',
            body)
        self.assertIn('Panneau 550W', body)

    def test_etiquette_never_exposes_prix_achat(self):
        resp = self._print()
        self.assertNotIn('937', resp.content.decode())

    def test_token_required(self):
        resp = self._print(catalogue_token='')
        self.assertEqual(resp.status_code, 400)

    def test_other_company_catalogue_rejected(self):
        resp = self._print(catalogue_token=self.cat_autre.token)
        self.assertEqual(resp.status_code, 404)

    def test_product_not_in_catalogue_excluded(self):
        resp = self._print(ids=str(self.hors_catalogue.id))
        self.assertEqual(resp.status_code, 404)

    def test_pdf_default_output(self):
        resp = self._print(sortie='pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_showroom_url_helper(self):
        url = labels.showroom_url('https://erp.example.ma/', 'tok', 42)
        self.assertEqual(
            url,
            'https://erp.example.ma/api/django/public/stock/showroom/'
            'tok/produit/42/')


class TestFichePublique(ShowroomBase):
    def test_json_exposes_specs_prix_ttc_garantie_dispo(self):
        resp = self.client.get(self._fiche_url() + '?sortie=json')
        self.assertEqual(resp.status_code, 200, resp.content)
        p = resp.json()['produit']
        self.assertEqual(p['nom'], 'Panneau 550W')
        self.assertEqual(p['prix_ttc'], '1500.00')
        self.assertEqual(p['garantie'], '25 ans')
        self.assertEqual(p['marque'], 'JA Solar')
        self.assertEqual(p['disponibilite'], 'En stock')

    def test_dispo_indicative_sur_commande(self):
        self.produit.quantite_stock = 0
        self.produit.save(update_fields=['quantite_stock'])
        resp = self.client.get(self._fiche_url() + '?sortie=json')
        self.assertEqual(
            resp.json()['produit']['disponibilite'], 'Sur commande')

    def test_never_exposes_prix_achat(self):
        for suffix in ('?sortie=json', ''):
            resp = self.client.get(self._fiche_url() + suffix)
            body = resp.content.decode()
            self.assertNotIn('937', body)
            self.assertNotIn('prix_achat', body)

    def test_html_page_contains_both_cta(self):
        resp = self.client.get(self._fiche_url())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/html', resp['Content-Type'])
        body = resp.content.decode()
        self.assertIn('Demander un devis', body)
        self.assertIn('Être rappelé', body)
        self.assertIn(
            f'/api/django/public/ecatalogue/{self.cat.token}'
            '/demander-devis/',
            body)
        self.assertIn(self._fiche_url() + 'etre-rappele/', body)

    def test_invalid_token_404(self):
        resp = self.client.get(self._fiche_url(token='inexistant'))
        self.assertEqual(resp.status_code, 404)

    def test_expired_catalogue_404(self):
        from datetime import timedelta
        from django.utils import timezone
        self.cat.expire_le = timezone.now() - timedelta(days=1)
        self.cat.save(update_fields=['expire_le'])
        resp = self.client.get(self._fiche_url())
        self.assertEqual(resp.status_code, 404)

    def test_product_not_exposed_404(self):
        resp = self.client.get(
            self._fiche_url(produit_id=self.hors_catalogue.id))
        self.assertEqual(resp.status_code, 404)

    def test_cross_tenant_product_via_token_404(self):
        # Le jeton de la société A ne résout JAMAIS un produit de la
        # société B (même si l'id était deviné).
        resp = self.client.get(
            self._fiche_url(produit_id=self.produit_autre.id))
        self.assertEqual(resp.status_code, 404)

    def test_resolves_right_tenant_product(self):
        resp = self.client.get(
            self._fiche_url(token=self.cat_autre.token,
                            produit_id=self.produit_autre.id)
            + '?sortie=json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()['catalogue']['titre'], 'Autre société')


class TestCtaEtreRappele(ShowroomBase):
    def _rappel(self, body=None, **kwargs):
        return self.client.post(
            self._fiche_url(**kwargs) + 'etre-rappele/',
            body if body is not None else {
                'nom': 'Client Showroom', 'telephone': '0661234567'},
            content_type='application/json')

    def test_creates_lead_in_catalogue_company(self):
        from apps.crm.models import Lead
        resp = self._rappel()
        self.assertEqual(resp.status_code, 201, resp.content)
        lead = Lead.objects.filter(
            company=self.company, telephone='0661234567').first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.nom, 'Client Showroom')
        self.assertFalse(
            Lead.objects.filter(company=self.other_company).exists())

    def test_honeypot_fake_201_creates_nothing(self):
        from apps.crm.models import Lead
        resp = self._rappel(body={
            'nom': 'Bot', 'telephone': '0600000000',
            'site_web': 'http://spam.example'})
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(
            Lead.objects.filter(telephone='0600000000').exists())

    def test_missing_contact_400(self):
        resp = self._rappel(body={'nom': 'Sans contact'})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_product_404(self):
        resp = self._rappel(produit_id=self.hors_catalogue.id)
        self.assertEqual(resp.status_code, 404)


class TestCtaDemanderDevis(ShowroomBase):
    def test_demander_devis_creates_lead_and_devis(self):
        from apps.crm.models import Lead
        from apps.ventes.models import Devis
        resp = self.client.post(
            f'/api/django/public/ecatalogue/{self.cat.token}'
            '/demander-devis/',
            {
                'nom': 'Visiteur Showroom',
                'telephone': '0662223344',
                'lignes': [{'produit': self.produit.id, 'quantite': 2}],
            },
            content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        lead = Lead.objects.filter(
            company=self.company, telephone='0662223344').first()
        self.assertIsNotNone(lead)
        self.assertTrue(
            Devis.objects.filter(company=self.company, lead=lead).exists())
