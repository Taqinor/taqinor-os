"""
XMFG2 — Réservation & contrôle de disponibilité des composants sur l'ordre
d'assemblage.

Couvre :
  * créer un ordre réserve les composants (visibles dans le disponible du
    produit) ;
  * l'action `disponibilite` montre la dispo par ligne ;
  * `demarrer` avec un manque n'échoue pas (warning non bloquant) ;
  * la clôture (XMFG1) marque les réservations `consomme=True` ;
  * `stock.services.available_quantity` reflète la réservation d'assemblage.

Run :
    python manage.py test apps.installations.tests_xmfg2_reservation -v2
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
        slug=slug or f'xmfg2-co-{n}', defaults={'nom': nom or f'XMFG2 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg2-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=0,
        quantite_stock=stock)


class TestReservationAssemblage(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(self.company, nom='Disjoncteur', stock=10)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=3)

    def test_create_ordre_reserve_composants(self):
        resp = self.api.post(f'{BASE}/ordres-assemblage/', {
            'kit': self.kit.id, 'quantite': 2,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ordre = OrdreAssemblage.objects.get(id=resp.data['id'])
        resa = ReservationAssemblage.objects.get(ordre=ordre, produit=self.comp1)
        self.assertEqual(resa.quantite, 6)
        self.assertTrue(resa.active)
        self.assertFalse(resa.consomme)

        from apps.stock.services import available_quantity
        self.comp1.refresh_from_db()
        self.assertEqual(available_quantity(self.comp1), 10 - 6)

    def test_disponibilite_action(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-D1', kit=self.kit, quantite=5)
        from apps.installations.services import seed_reservations_assemblage
        seed_reservations_assemblage(ordre)
        resp = self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/disponibilite/')
        self.assertEqual(resp.status_code, 200, resp.content)
        lignes = resp.data
        self.assertEqual(len(lignes), 1)
        ligne = lignes[0]
        self.assertEqual(ligne['requis'], 15)
        # 10 en stock, rien d'autre réservé → manquant (15 > 10)
        self.assertEqual(ligne['statut'], 'manquant')

    def test_demarrer_avec_manque_non_bloquant(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-D2', kit=self.kit, quantite=5)
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/demarrer/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreAssemblage.Statut.EN_COURS)

    def test_terminer_marque_reservations_consommees(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-D3', kit=self.kit, quantite=1)
        from apps.installations.services import seed_reservations_assemblage
        seed_reservations_assemblage(ordre)
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        resa = ReservationAssemblage.objects.get(ordre=ordre, produit=self.comp1)
        self.assertTrue(resa.consomme)

    def test_release_liberates_non_consumed(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-D4', kit=self.kit, quantite=1)
        from apps.installations.services import (
            seed_reservations_assemblage, release_reservations_assemblage,
        )
        seed_reservations_assemblage(ordre)
        released = release_reservations_assemblage(ordre)
        self.assertEqual(released, 1)
        resa = ReservationAssemblage.objects.get(ordre=ordre, produit=self.comp1)
        self.assertFalse(resa.active)
