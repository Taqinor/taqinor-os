"""
XMFG12 — Ordre de démontage (unbuild) : composite → composants.

Couvre :
  * la création copie la BOM du kit en lignes de démontage (attendue =
    récupérée par défaut) ;
  * clôturer démonte N kits : sort le composite, restocke les composants
    récupérés (édités) exactement une fois ;
  * quantité récupérée < attendue = perte (pas de sur-restockage, déclarable
    en rebut séparément) ;
  * idempotence : re-clôture sans double mouvement ;
  * kit sans produit_compose rejeté proprement.

Run :
    python manage.py test apps.installations.tests_xmfg12_demontage -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Kit, KitComposant, OrdreDemontage

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xmfg12-co-{n}', defaults={'nom': nom or f'XMFG12 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg12-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=0,
        quantite_stock=stock)


class TestOrdreDemontage(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=5)
        self.comp1 = make_produit(self.company, nom='Onduleur', stock=0)
        self.comp2 = make_produit(self.company, nom='Presse-étoupe', stock=0)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=1)
        KitComposant.objects.create(kit=self.kit, produit=self.comp2, quantite=4)

    def test_creation_copie_bom_en_lignes(self):
        resp = self.api.post(f'{BASE}/ordres-demontage/', {
            'kit': self.kit.id, 'quantite': 2,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ordre = OrdreDemontage.objects.get(id=resp.data['id'])
        self.assertTrue(ordre.reference.startswith('DSM-'))
        lignes = list(ordre.lignes.all())
        self.assertEqual(len(lignes), 2)
        by_produit = {ligne.produit_id: ligne for ligne in lignes}
        self.assertEqual(by_produit[self.comp1.id].quantite_attendue, 2)
        self.assertEqual(by_produit[self.comp1.id].quantite_recuperee, 2)
        self.assertEqual(by_produit[self.comp2.id].quantite_attendue, 8)

    def test_terminer_restocke_composants_et_sort_composite(self):
        resp = self.api.post(f'{BASE}/ordres-demontage/', {
            'kit': self.kit.id, 'quantite': 2,
        }, format='json')
        ordre_id = resp.data['id']

        r = self.api.post(
            f'{BASE}/ordres-demontage/{ordre_id}/terminer/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.composite.refresh_from_db()
        self.comp1.refresh_from_db()
        self.comp2.refresh_from_db()
        self.assertEqual(self.composite.quantite_stock, 5 - 2)
        self.assertEqual(self.comp1.quantite_stock, 2)
        self.assertEqual(self.comp2.quantite_stock, 8)

        # Re-clôture : aucun second mouvement.
        r2 = self.api.post(
            f'{BASE}/ordres-demontage/{ordre_id}/terminer/', {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        self.composite.refresh_from_db()
        self.comp1.refresh_from_db()
        self.assertEqual(self.composite.quantite_stock, 5 - 2)
        self.assertEqual(self.comp1.quantite_stock, 2)

    def test_quantite_recuperee_editee_ne_sur_restocke_pas(self):
        resp = self.api.post(f'{BASE}/ordres-demontage/', {
            'kit': self.kit.id, 'quantite': 1,
        }, format='json')
        ordre_id = resp.data['id']
        ordre = OrdreDemontage.objects.get(id=ordre_id)
        ligne_comp1 = ordre.lignes.get(produit=self.comp1)
        # 1 unité attendue mais cassée au démontage : rien à restocker.
        edit_resp = self.api.patch(
            f'{BASE}/ordre-demontage-lignes/{ligne_comp1.id}/',
            {'quantite_recuperee': 0}, format='json')
        self.assertEqual(edit_resp.status_code, 200, edit_resp.content)

        self.api.post(
            f'{BASE}/ordres-demontage/{ordre_id}/terminer/', {}, format='json')
        self.comp1.refresh_from_db()
        self.assertEqual(self.comp1.quantite_stock, 0)

    def test_kit_sans_produit_compose_rejete(self):
        kit_incomplet = Kit.objects.create(company=self.company, nom='Sans article')
        KitComposant.objects.create(
            kit=kit_incomplet, produit=self.comp1, quantite=1)
        ordre = OrdreDemontage.objects.create(
            company=self.company, reference='DSM-X', kit=kit_incomplet,
            quantite=1)
        resp = self.api.post(
            f'{BASE}/ordres-demontage/{ordre.id}/terminer/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
