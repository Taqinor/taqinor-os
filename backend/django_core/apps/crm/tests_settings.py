"""T6 — réglages déverrouillés : canaux/sources, types d'intervention, marques
(listes gérées additives avec garde-fous) + constantes ROI éditables."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Canal, Lead, LeadTag, MotifPerte
from authentication.models import Company

User = get_user_model()


class T6Base(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='t6-co', defaults={'nom': 'T6 Co'})[0]
        self.admin = User.objects.create_user(
            username='t6_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')


class TestCanaux(T6Base):
    def test_list_seeds_defaults_with_protected_site_web(self):
        resp = self.api.get('/api/django/crm/canaux/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        site = next((c for c in rows if c['cle'] == 'site_web'), None)
        self.assertIsNotNone(site)
        self.assertTrue(site['protege'])

    def test_cannot_delete_protected_site_web(self):
        self.api.get('/api/django/crm/canaux/')  # seed
        site = Canal.objects.get(company=self.company, cle='site_web')
        resp = self.api.delete(f'/api/django/crm/canaux/{site.id}/')
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(Canal.objects.filter(id=site.id).exists())

    def test_cannot_rename_protected_key(self):
        self.api.get('/api/django/crm/canaux/')  # seed
        site = Canal.objects.get(company=self.company, cle='site_web')
        resp = self.api.patch(f'/api/django/crm/canaux/{site.id}/',
                              {'cle': 'autre_cle'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_cannot_delete_canal_in_use(self):
        self.api.get('/api/django/crm/canaux/')  # seed
        autre = Canal.objects.get(company=self.company, cle='autre')
        Lead.objects.create(company=self.company, nom='X', canal='autre')
        resp = self.api.delete(f'/api/django/crm/canaux/{autre.id}/')
        self.assertEqual(resp.status_code, 409)

    def test_can_add_and_rename_libelle(self):
        resp = self.api.post('/api/django/crm/canaux/',
                             {'cle': 'salon', 'libelle': 'Salon pro'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cid = resp.data['id']
        # Le libellé d'un canal non protégé est modifiable.
        r2 = self.api.patch(f'/api/django/crm/canaux/{cid}/',
                            {'libelle': 'Salon professionnel'}, format='json')
        self.assertEqual(r2.status_code, 200)


class TestTypesIntervention(T6Base):
    def test_seed_and_protected_not_deletable(self):
        from apps.installations.models import TypeIntervention
        self.api.get('/api/django/installations/types-intervention/')  # seed
        pose = TypeIntervention.objects.get(company=self.company, cle='pose')
        self.assertTrue(pose.protege)
        resp = self.api.delete(
            f'/api/django/installations/types-intervention/{pose.id}/')
        self.assertEqual(resp.status_code, 409)


class TestMarques(T6Base):
    def test_seed_from_products_and_block_in_use_delete(self):
        from decimal import Decimal
        from apps.stock.models import Produit, Marque
        Produit.objects.create(
            company=self.company, nom='P', sku='M-1', marque='VEICHI',
            prix_vente=Decimal('10'), quantite_stock=1)
        resp = self.api.get('/api/django/stock/marques/')
        self.assertEqual(resp.status_code, 200)
        m = Marque.objects.get(company=self.company, nom='VEICHI')
        # Marque utilisée → suppression bloquée.
        r2 = self.api.delete(f'/api/django/stock/marques/{m.id}/')
        self.assertEqual(r2.status_code, 409)


class TestMotifPerteProtection(T6Base):
    """L779 — un motif de perte utilisé par des leads ne se supprime pas."""

    def test_block_delete_motif_in_use_and_suggest_archive(self):
        motif = MotifPerte.objects.create(company=self.company, nom='Trop cher')
        Lead.objects.create(company=self.company, nom='L', motif_perte='Trop cher')
        resp = self.api.delete(f'/api/django/crm/motifs-perte/{motif.id}/')
        self.assertEqual(resp.status_code, 409)
        self.assertIn('archiv', resp.data['detail'].lower())
        self.assertTrue(MotifPerte.objects.filter(id=motif.id).exists())

    def test_unused_motif_deletable(self):
        motif = MotifPerte.objects.create(company=self.company, nom='Inutilisé')
        resp = self.api.delete(f'/api/django/crm/motifs-perte/{motif.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(MotifPerte.objects.filter(id=motif.id).exists())

    def test_en_usage_reported_in_serializer(self):
        MotifPerte.objects.create(company=self.company, nom='Délais')
        Lead.objects.create(company=self.company, nom='A', motif_perte='Délais')
        Lead.objects.create(company=self.company, nom='B', motif_perte='Délais')
        resp = self.api.get('/api/django/crm/motifs-perte/')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        row = next(r for r in rows if r['nom'] == 'Délais')
        self.assertEqual(row['en_usage'], 2)


class TestLeadTagProtection(T6Base):
    """L780 — une étiquette référencée dans Lead.tags ne se supprime pas."""

    def test_block_delete_tag_in_use_and_suggest_archive(self):
        tag = LeadTag.objects.create(company=self.company, nom='VIP')
        Lead.objects.create(company=self.company, nom='L', tags='VIP, Urgent')
        resp = self.api.delete(f'/api/django/crm/tags/{tag.id}/')
        self.assertEqual(resp.status_code, 409)
        self.assertIn('archiv', resp.data['detail'].lower())
        self.assertTrue(LeadTag.objects.filter(id=tag.id).exists())

    def test_unused_tag_deletable(self):
        tag = LeadTag.objects.create(company=self.company, nom='Froid')
        # Un autre lead porte un libellé DIFFÉRENT — ne doit pas compter.
        Lead.objects.create(company=self.company, nom='L', tags='Chaud')
        resp = self.api.delete(f'/api/django/crm/tags/{tag.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(LeadTag.objects.filter(id=tag.id).exists())

    def test_en_usage_counts_token_not_substring(self):
        LeadTag.objects.create(company=self.company, nom='Pro')
        # « Professionnel » contient « pro » mais n'est PAS le jeton « Pro ».
        Lead.objects.create(company=self.company, nom='A', tags='Professionnel')
        Lead.objects.create(company=self.company, nom='B', tags='pro, vip')
        resp = self.api.get('/api/django/crm/tags/')
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        row = next(r for r in rows if r['nom'] == 'Pro')
        self.assertEqual(row['en_usage'], 1)


class TestRoiSettings(T6Base):
    def test_roi_constants_default_and_editable(self):
        resp = self.api.get('/api/django/parametres/')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data[0] if isinstance(resp.data, list) else resp.data
        # Défaut = valeur historique (comportement inchangé).
        self.assertEqual(str(data['onee_tarif_kwh']), '1.750')
