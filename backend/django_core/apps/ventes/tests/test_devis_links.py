"""U5/U8 — factures liées + état du bon de commande sur le serializer Devis.

U5 : le serializer expose `factures_liees` (référence + statut des factures
générées depuis le devis) et `bon_commande_etat` (référence + statut du BC lié).
U8 : `bon_commande_etat.mismatch` vaut True quand le devis est « accepté » mais
que son BC est annulé — ou qu'aucun BC n'existe. Tout est en LECTURE SEULE,
borné à la société par le devis lui-même.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import BonCommande, Devis, Facture
from apps.ventes.serializers import DevisSerializer

User = get_user_model()


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDevisLinksSerializer(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='ulink-co', defaults={'nom': 'Ulink Co'})[0]
        self.user = User.objects.create_user(
            username='ulink_u', password='x', role_legacy='responsable',
            company=self.co)
        self.cli = Client.objects.create(
            company=self.co, nom='Client', prenom='U')
        self.devis = Devis.objects.create(
            company=self.co, reference='DEV-ULINK-0001', client=self.cli,
            statut='accepte', taux_tva=Decimal('20'))

    # ── U5 — factures liées ───────────────────────────────────────────────────
    def test_factures_liees_empty_when_no_facture(self):
        data = DevisSerializer(self.devis).data
        self.assertIn('factures_liees', data)
        self.assertEqual(data['factures_liees'], [])

    def test_factures_liees_lists_generated_facture(self):
        f = Facture.objects.create(
            company=self.co, reference='FAC-ULINK-0001', client=self.cli,
            devis=self.devis, statut='emise', type_facture='acompte')
        data = DevisSerializer(self.devis).data
        refs = [x['reference'] for x in data['factures_liees']]
        self.assertIn('FAC-ULINK-0001', refs)
        entry = next(x for x in data['factures_liees']
                     if x['reference'] == 'FAC-ULINK-0001')
        self.assertEqual(entry['id'], f.id)
        self.assertEqual(entry['statut'], 'emise')
        self.assertEqual(entry['statut_display'], 'Émise')
        self.assertEqual(entry['type_facture'], 'acompte')

    def test_factures_liees_multiple_sorted(self):
        Facture.objects.create(
            company=self.co, reference='FAC-ULINK-0002', client=self.cli,
            devis=self.devis, statut='emise')
        Facture.objects.create(
            company=self.co, reference='FAC-ULINK-0001', client=self.cli,
            devis=self.devis, statut='payee')
        data = DevisSerializer(self.devis).data
        refs = [x['reference'] for x in data['factures_liees']]
        self.assertEqual(refs, ['FAC-ULINK-0001', 'FAC-ULINK-0002'])

    # ── U5/U8 — état du bon de commande ───────────────────────────────────────
    def test_bc_etat_absent_on_accepte_devis_is_mismatch(self):
        # Devis accepté sans BC → incohérence signalée (U8).
        data = DevisSerializer(self.devis).data
        self.assertIn('bon_commande_etat', data)
        bc = data['bon_commande_etat']
        self.assertFalse(bc['exists'])
        self.assertIsNone(bc['reference'])
        self.assertTrue(bc['mismatch'])

    def test_bc_etat_absent_on_non_accepte_devis_is_no_mismatch(self):
        self.devis.statut = 'brouillon'
        self.devis.save(update_fields=['statut'])
        bc = DevisSerializer(self.devis).data['bon_commande_etat']
        self.assertFalse(bc['exists'])
        self.assertFalse(bc['mismatch'])

    def test_bc_etat_present_confirme_no_mismatch(self):
        BonCommande.objects.create(
            company=self.co, reference='BC-ULINK-0001', devis=self.devis,
            client=self.cli, statut=BonCommande.Statut.CONFIRME)
        bc = DevisSerializer(self.devis).data['bon_commande_etat']
        self.assertTrue(bc['exists'])
        self.assertEqual(bc['reference'], 'BC-ULINK-0001')
        self.assertEqual(bc['statut'], 'confirme')
        self.assertEqual(bc['statut_display'], 'Confirmé')
        self.assertFalse(bc['mismatch'])

    def test_bc_etat_annule_on_accepte_devis_is_mismatch(self):
        # U8 — devis accepté + BC annulé → incohérence signalée.
        BonCommande.objects.create(
            company=self.co, reference='BC-ULINK-0002', devis=self.devis,
            client=self.cli, statut=BonCommande.Statut.ANNULE)
        bc = DevisSerializer(self.devis).data['bon_commande_etat']
        self.assertTrue(bc['exists'])
        self.assertEqual(bc['statut'], 'annule')
        self.assertTrue(bc['mismatch'])

    def test_bc_etat_annule_on_brouillon_devis_no_mismatch(self):
        # BC annulé mais devis non accepté → pas une incohérence à signaler.
        self.devis.statut = 'brouillon'
        self.devis.save(update_fields=['statut'])
        BonCommande.objects.create(
            company=self.co, reference='BC-ULINK-0003', devis=self.devis,
            client=self.cli, statut=BonCommande.Statut.ANNULE)
        bc = DevisSerializer(self.devis).data['bon_commande_etat']
        self.assertFalse(bc['mismatch'])

    # ── Exposition via l'API REST (company-scoped) ────────────────────────────
    def test_endpoint_exposes_both_blocks(self):
        Facture.objects.create(
            company=self.co, reference='FAC-ULINK-EP1', client=self.cli,
            devis=self.devis, statut='emise')
        api = _auth(self.user)
        r = api.get(f'/api/django/ventes/devis/{self.devis.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('factures_liees', r.data)
        self.assertIn('bon_commande_etat', r.data)
        self.assertEqual(
            [x['reference'] for x in r.data['factures_liees']],
            ['FAC-ULINK-EP1'])

    def test_list_endpoint_does_not_crash(self):
        api = _auth(self.user)
        r = api.get('/api/django/ventes/devis/')
        self.assertEqual(r.status_code, 200)
        rows = [x for x in r.data['results']
                if x['reference'] == 'DEV-ULINK-0001']
        self.assertEqual(len(rows), 1)
        self.assertIn('factures_liees', rows[0])
        self.assertIn('bon_commande_etat', rows[0])


class TestDevisLeadMetaAdIdSerializer(TestCase):
    """PUB53 — `lead_meta_ad_id` : liens retour Devis → annonce Meta d'origine.

    Même motif que `lead_facture_hiver`/`lead_type_installation` : lecture
    seule de l'attribution (ADSENG1) déjà stockée sur le lead lié, exposée
    pour que le badge « Vient de la pub » côté frontend n'ait rien à
    résoudre elle-même."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='umeta-co', defaults={'nom': 'Umeta Co'})[0]
        self.user = User.objects.create_user(
            username='umeta_u', password='x', role_legacy='responsable',
            company=self.co)
        self.cli = Client.objects.create(
            company=self.co, nom='Client', prenom='M')

    def test_none_when_no_lead(self):
        devis = Devis.objects.create(
            company=self.co, reference='DEV-UMETA-0001', client=self.cli,
            statut='brouillon', taux_tva=Decimal('20'))
        data = DevisSerializer(devis).data
        self.assertIn('lead_meta_ad_id', data)
        self.assertIsNone(data['lead_meta_ad_id'])

    def test_none_when_lead_has_no_meta_ad_id(self):
        lead = Lead.objects.create(
            company=self.co, nom='Sans', prenom='Pub', email='sanspub@ex.com')
        devis = Devis.objects.create(
            company=self.co, reference='DEV-UMETA-0002', client=self.cli,
            lead=lead, statut='brouillon', taux_tva=Decimal('20'))
        data = DevisSerializer(devis).data
        self.assertIsNone(data['lead_meta_ad_id'])

    def test_exposes_meta_ad_id_from_linked_lead(self):
        lead = Lead.objects.create(
            company=self.co, nom='Meta', prenom='Pub', email='metapub@ex.com',
            meta_ad_id='120210000000001')
        devis = Devis.objects.create(
            company=self.co, reference='DEV-UMETA-0003', client=self.cli,
            lead=lead, statut='brouillon', taux_tva=Decimal('20'))
        data = DevisSerializer(devis).data
        self.assertEqual(data['lead_meta_ad_id'], '120210000000001')

    def test_endpoint_exposes_lead_meta_ad_id(self):
        lead = Lead.objects.create(
            company=self.co, nom='Meta', prenom='Ep', email='metaep@ex.com',
            meta_ad_id='120210000000002')
        devis = Devis.objects.create(
            company=self.co, reference='DEV-UMETA-0004', client=self.cli,
            lead=lead, statut='brouillon', taux_tva=Decimal('20'))
        api = _auth(self.user)
        r = api.get(f'/api/django/ventes/devis/{devis.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['lead_meta_ad_id'], '120210000000002')
