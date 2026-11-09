"""ASTK31 (C-ASTK-004) — une unité logistique scellée est immuable et un
``parent`` cyclique est refusé : plus jamais de 500 au déplacement.

Sonde WMS-14 d'origine : PATCH parent=self → 200, puis ``deplacer`` → 500
(``RecursionError`` dans ``_unites_a_deplacer``) ; PATCH poids/type après
scellage → 200 (l'étiquette SSCC imprimée ne correspondait plus).

Run :
    python manage.py test apps.stock.test_astk_ul_scellee -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import EmplacementStock, Produit
from apps.stock.models_wms import UniteLogistique
from apps.stock.services import (
    ajouter_ligne_unite_logistique, creer_unite_logistique,
    sceller_unite_logistique,
)

User = get_user_model()

URL = '/api/django/stock/unites-logistiques/'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class UniteLogistiqueScelleeTests(TestCase):
    def setUp(self):
        from apps.installations.models import BinLocation

        self.co = make_company('astk31-co', 'ASTK31 Co')
        self.resp = User.objects.create_user(
            username='astk31_resp', password='x', role_legacy='responsable',
            company=self.co)
        self.api = auth_client(self.resp)
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau ASTK31', sku='ASTK31-P',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=50)
        emp = EmplacementStock.objects.create(
            company=self.co, nom='Dépôt ASTK31', is_principal=True)
        self.bin = BinLocation.objects.create(
            company=self.co, emplacement=emp, code='A-31-01')
        # U : unité scellée.
        self.u = creer_unite_logistique(company=self.co, poids_kg=12)
        ajouter_ligne_unite_logistique(
            company=self.co, unite=self.u, produit=self.produit, quantite=2)
        sceller_unite_logistique(unite=self.u, user=self.resp)
        self.u.refresh_from_db()
        # V, W : unités ouvertes.
        self.v = creer_unite_logistique(company=self.co, type_unite='palette')
        self.w = creer_unite_logistique(company=self.co, type_unite='palette')

    def _etat_u(self):
        self.u.refresh_from_db()
        return (self.u.poids_kg, self.u.type_unite, self.u.parent_id,
                self.u.dimensions)

    def test_patch_scellee_refuse(self):
        avant = self._etat_u()
        for corps in ({'poids_kg': '99'}, {'type_unite': 'palette'},
                      {'dimensions': '1 × 1 × 1'}, {'parent': self.v.id}):
            r = self.api.patch(f'{URL}{self.u.id}/', corps, format='json')
            # api-fuzz stock (vague 8) : corps conforme, unité scellée =
            # refus d'ÉTAT 409 (plus un 400).
            self.assertEqual(r.status_code, 409, (corps, r.content))
            self.assertIn('scellée', str(r.data), (corps, r.content))
        r = self.api.patch(
            f'{URL}{self.u.id}/', {'parent': self.u.id}, format='json')
        # Le cycle (unité parente d'elle-même) est un refus d'ÉTAT : 409
        # (api-fuzz-full 24/10), rendu avant le verrou « scellée » du viewset.
        self.assertEqual(r.status_code, 409, r.content)
        # Persistance relue : U inchangée.
        self.assertEqual(self._etat_u(), avant)
        self.assertEqual(self.u.poids_kg, Decimal('12'))

    def test_parent_egal_a_soi_refuse(self):
        r = self.api.patch(
            f'{URL}{self.v.id}/', {'parent': self.v.id}, format='json')
        self.assertEqual(r.status_code, 409, r.content)  # ENF11 : cycle = état
        self.assertIn('cycle', str(r.data))
        self.v.refresh_from_db()
        self.assertIsNone(self.v.parent_id)

    def test_parent_cyclique_refuse(self):
        r = self.api.patch(
            f'{URL}{self.w.id}/', {'parent': self.v.id}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        r = self.api.patch(
            f'{URL}{self.v.id}/', {'parent': self.w.id}, format='json')
        self.assertEqual(r.status_code, 409, r.content)  # ENF11 : cycle = état
        self.assertIn('cycle', str(r.data))
        self.v.refresh_from_db()
        self.assertIsNone(self.v.parent_id)

    def test_deplacer_cycle_pas_500(self):
        """Cycle hérité injecté en base (d'avant la garde) : le déplacement
        répond 200 ou 400 lisible, jamais 500."""
        ajouter_ligne_unite_logistique(
            company=self.co, unite=self.v, produit=self.produit, quantite=1)
        UniteLogistique.objects.filter(pk=self.v.pk).update(parent=self.w)
        UniteLogistique.objects.filter(pk=self.w.pk).update(parent=self.v)
        r = self.api.post(f'{URL}{self.v.id}/deplacer/',
                          {'bin_destination': self.bin.id}, format='json')
        self.assertIn(r.status_code, (200, 400, 409), r.content)
        if r.status_code == 200:
            self.assertEqual(sorted(r.data['unites_deplacees']),
                             sorted([self.v.id, self.w.id]))
        # Parent = soi-même.
        UniteLogistique.objects.filter(pk=self.w.pk).update(parent=self.w)
        r = self.api.post(f'{URL}{self.w.id}/deplacer/',
                          {'bin_destination': self.bin.id}, format='json')
        self.assertIn(r.status_code, (200, 400, 409), r.content)

    def test_palette_scellee_fige_sa_descendance(self):
        """ASTK261 (C-ASTK-VER4-050) — palette scellée P contenant un colis
        ouvert C1 : rattacher V à P, ajouter une ligne à C1, détacher C1 et
        rattacher W à un simple colis C2 répondent 409 (sonde : 200/201/200/200)."""
        from apps.stock.models_wms import UniteLogistiqueLigne
        pal = creer_unite_logistique(company=self.co, type_unite='palette')
        c1 = creer_unite_logistique(company=self.co, parent=pal)
        ajouter_ligne_unite_logistique(
            company=self.co, unite=c1, produit=self.produit, quantite=2)
        sceller_unite_logistique(unite=pal, user=self.resp)
        v = creer_unite_logistique(company=self.co)
        ajouter_ligne_unite_logistique(
            company=self.co, unite=v, produit=self.produit, quantite=5)
        w = creer_unite_logistique(company=self.co)
        c2 = creer_unite_logistique(company=self.co)
        enfants_avant = sorted(pal.enfants.values_list('pk', flat=True))

        gestes = [
            self.api.patch(f'{URL}{v.id}/', {'parent': pal.id}, format='json'),
            self.api.post(f'{URL}{c1.id}/lignes/',
                          {'produit': self.produit.id, 'quantite': 3},
                          format='json'),
            self.api.patch(f'{URL}{c1.id}/', {'parent': None}, format='json'),
            self.api.patch(f'{URL}{w.id}/', {'parent': c2.id}, format='json'),
        ]
        self.assertEqual([r.status_code for r in gestes], [409] * 4,
                         [r.content for r in gestes])
        # Persistance relue : descendance et contenu inchangés.
        self.assertEqual(sorted(UniteLogistique.objects.filter(
            parent=pal).values_list('pk', flat=True)), enfants_avant)
        self.assertEqual(
            UniteLogistiqueLigne.objects.get(unite=c1).quantite, 2)
        w.refresh_from_db()
        self.assertIsNone(w.parent_id)
        # Témoin : un colis ouvert hors palette reste modifiable.
        r = self.api.patch(f'{URL}{c2.id}/', {'dimensions': '40 × 30 × 20'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.content)
