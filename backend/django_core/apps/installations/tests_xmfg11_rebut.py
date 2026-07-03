"""
XMFG11 — Gestion des rebuts de production + taux de perte par composant.

Couvre :
  * `declarer-rebut` crée un mouvement SORTIE motivé de type REBUT, rattaché à
    l'ordre (reference) ;
  * `KitComposant.taux_perte_pct` gonfle le besoin planifié (lignes + réservation) ;
  * le rapport agrégé rebuts par produit/motif fonctionne.

Run :
    python manage.py test apps.installations.tests_xmfg11_rebut -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, ReservationAssemblage,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xmfg11-co-{n}', defaults={'nom': nom or f'XMFG11 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg11-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=0,
        quantite_stock=stock)


class TestRebut(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(self.company, nom='Panneau', stock=50)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=2)
        self.ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-R1', kit=self.kit, quantite=1)

    def test_declarer_rebut_cree_mouvement_motive(self):
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/declarer-rebut/', {
                'produit': self.comp1.id, 'quantite': 3, 'motif': 'casse',
                'note': 'Panneau fêlé au montage',
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        from apps.stock.models import MouvementStock
        mvt = MouvementStock.objects.get(
            reference=self.ordre.reference,
            type_mouvement=MouvementStock.TypeMouvement.REBUT)
        self.assertEqual(mvt.quantite, 3)
        self.assertEqual(mvt.motif_rebut, 'casse')
        self.comp1.refresh_from_db()
        self.assertEqual(self.comp1.quantite_stock, 50 - 3)

    def test_declarer_rebut_motif_invalide_rejete(self):
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/declarer-rebut/', {
                'produit': self.comp1.id, 'quantite': 1, 'motif': 'invalide',
            }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_taux_perte_gonfle_besoin_planifie(self):
        composant = self.kit.composants.get(produit=self.comp1)
        composant.taux_perte_pct = 10
        composant.save(update_fields=['taux_perte_pct'])
        ordre2 = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-R2', kit=self.kit, quantite=10)
        from apps.installations.services import seed_reservations_assemblage
        seed_reservations_assemblage(ordre2)
        resa = ReservationAssemblage.objects.get(ordre=ordre2, produit=self.comp1)
        # besoin brut = 2*10 = 20 ; +10% = 22
        self.assertEqual(resa.quantite, 22)

    def test_taux_perte_zero_inchange(self):
        ordre3 = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-R3', kit=self.kit, quantite=5)
        from apps.installations.services import seed_reservations_assemblage
        seed_reservations_assemblage(ordre3)
        resa = ReservationAssemblage.objects.get(ordre=ordre3, produit=self.comp1)
        self.assertEqual(resa.quantite, 10)

    def test_rapport_rebuts_agrege(self):
        self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/declarer-rebut/', {
                'produit': self.comp1.id, 'quantite': 2, 'motif': 'casse',
            }, format='json')
        self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/declarer-rebut/', {
                'produit': self.comp1.id, 'quantite': 1, 'motif': 'defaut',
            }, format='json')
        resp = self.api.get(f'{BASE}/ordres-assemblage/rapport-rebuts/')
        self.assertEqual(resp.status_code, 200, resp.content)
        entry = next(r for r in resp.data if r['produit_id'] == self.comp1.id)
        self.assertEqual(entry['quantite_totale'], 3)
        self.assertEqual(entry['motifs']['casse'], 2)
        self.assertEqual(entry['motifs']['defaut'], 1)
