"""ASTK2 — retour fournisseur et modèle de BCF bornés à la société ;
`generer` et `recevoir` relisent le produit dans la société du document.

Rejoue les sondes BCF-2 / BCF-3 / TEN-6 (4, 4b, 7) de l'audit stock du
2026-10-06 : avant correction, un retour sur le BCF reçu d'une autre société
= 201 (référence de B exposée) et sa validation rouvrait la ligne de B ; un
modèle sur le produit de B = 201, PU pré-rempli au prix d'achat de B, et la
réception du BCF généré faisait entrer du stock chez B.

Les deux préfixes (`/api/django/stock/` et `/api/django/achats/`, ODX20)
servent les mêmes viewsets : les refus sont vérifiés sur les deux.

Run:
    python manage.py test apps.stock.test_astk_fk_retour_modele_bcf -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    ModeleBonCommandeFournisseur, ModeleBonCommandeFournisseurLigne,
    Produit, RetourFournisseur,
)

User = get_user_model()

ID_ABSENT = 99999999
PREFIXES = ('/api/django/stock/', '/api/django/achats/')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _sans_id(corps, pk):
    return str(corps).replace(str(pk), '<ID>')


class FkRetourModeleBcfTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='astk2-a', slug='astk2-a')
        self.co_b = Company.objects.create(nom='astk2-b', slug='astk2-b')
        self.admin_a = User.objects.create_user(
            username='astk2-admin-a', password='x', company=self.co_a,
            role_legacy='admin')
        self.api = _api(self.admin_a)
        self.fa = Fournisseur.objects.create(company=self.co_a, nom='FA')
        self.fa2 = Fournisseur.objects.create(company=self.co_a, nom='FA2')
        self.fb = Fournisseur.objects.create(
            company=self.co_b, nom='FOURNISSEUR-B-SECRET')
        self.pa = Produit.objects.create(
            company=self.co_a, nom='Produit A', sku='ASTK2-PA',
            prix_vente=Decimal('30'), prix_achat=Decimal('11'),
            quantite_stock=10)
        self.pb = Produit.objects.create(
            company=self.co_b, nom='PRODUIT-B-SECRET', sku='ASTK2-PB',
            prix_vente=Decimal('120'), prix_achat=Decimal('77'),
            quantite_stock=0)
        self.bc_b = BonCommandeFournisseur.objects.create(
            company=self.co_b, reference='BCF-B-SECRET', fournisseur=self.fb,
            statut=BonCommandeFournisseur.Statut.RECU)
        self.ligne_b = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bc_b, produit=self.pb, quantite=20,
            prix_achat_unitaire=Decimal('77'), quantite_recue=20)

    def _assert_comme_absent(self, r, r_absent, pk):
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r_absent.status_code, 400, r_absent.content)
        self.assertEqual(_sans_id(r.json(), pk),
                         _sans_id(r_absent.json(), ID_ABSENT))
        corps = r.content.decode()
        for secret in ('BCF-B-SECRET', 'PRODUIT-B-SECRET',
                       'FOURNISSEUR-B-SECRET'):
            self.assertNotIn(secret, corps)

    def _invariants_b(self):
        self.ligne_b.refresh_from_db()
        self.bc_b.refresh_from_db()
        self.pb.refresh_from_db()
        self.assertEqual(self.ligne_b.quantite_recue, 20)
        self.assertEqual(self.bc_b.statut, BonCommandeFournisseur.Statut.RECU)
        self.assertEqual(self.pb.quantite_stock, 0)

    def test_retour_bcf_etranger_refuse(self):
        def _post(prefix, bc_id, produit_id):
            return self.api.post(f'{prefix}retours-fournisseur/', {
                'fournisseur': self.fa.pk, 'bon_commande': bc_id,
                'motif': 'défaut',
                'lignes': [{'produit': produit_id, 'quantite': 1,
                            'motif': 'x'}],
            }, format='json')

        for prefix in PREFIXES:
            self._assert_comme_absent(
                _post(prefix, self.bc_b.pk, self.pa.pk),
                _post(prefix, ID_ABSENT, self.pa.pk), self.bc_b.pk)
            self._assert_comme_absent(
                _post(prefix, None, self.pb.pk),
                _post(prefix, None, ID_ABSENT), self.pb.pk)
        self.assertFalse(RetourFournisseur.objects.exists())
        self._invariants_b()

    def test_retour_patch_fournisseur_etranger_refuse(self):
        retour = RetourFournisseur.objects.create(
            company=self.co_a, reference='RF-ASTK2', fournisseur=self.fa,
            statut=RetourFournisseur.Statut.BROUILLON)
        for prefix in PREFIXES:
            url = f'{prefix}retours-fournisseur/{retour.pk}/'
            self._assert_comme_absent(
                self.api.patch(url, {'fournisseur': self.fb.pk},
                               format='json'),
                self.api.patch(url, {'fournisseur': ID_ABSENT},
                               format='json'),
                self.fb.pk)
        retour.refresh_from_db()
        self.assertEqual(retour.fournisseur_id, self.fa.pk)
        # Un fournisseur de la même société reste accepté en brouillon.
        r = self.api.patch(
            f'/api/django/stock/retours-fournisseur/{retour.pk}/',
            {'fournisseur': self.fa2.pk}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_modele_fournisseur_etranger_refuse(self):
        url = '/api/django/stock/modeles-bcf/'
        self._assert_comme_absent(
            self.api.post(url, {'nom': 'M', 'fournisseur': self.fb.pk},
                          format='json'),
            self.api.post(url, {'nom': 'M', 'fournisseur': ID_ABSENT},
                          format='json'),
            self.fb.pk)
        self.assertFalse(ModeleBonCommandeFournisseur.objects.exists())

    def test_modele_produit_etranger_refuse(self):
        url = '/api/django/stock/modeles-bcf/'

        def _post(produit_id):
            return self.api.post(url, {
                'nom': 'M', 'fournisseur': self.fa.pk,
                'lignes': [{'produit': produit_id, 'quantite': 3}],
            }, format='json')

        self._assert_comme_absent(
            _post(self.pb.pk), _post(ID_ABSENT), self.pb.pk)
        self.assertFalse(ModeleBonCommandeFournisseur.objects.exists())

    def test_chaine_modele_recevoir_ne_touche_pas_B(self):
        # Modèle hérité (écrit hors API) mêlant un produit de B.
        modele = ModeleBonCommandeFournisseur.objects.create(
            company=self.co_a, nom='Hérité', fournisseur=self.fa)
        ModeleBonCommandeFournisseurLigne.objects.create(
            modele=modele, produit=self.pb, quantite=3)
        ModeleBonCommandeFournisseurLigne.objects.create(
            modele=modele, produit=self.pa, quantite=2)
        r = self.api.post(
            f'/api/django/stock/modeles-bcf/{modele.pk}/generer/', {},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        bon = BonCommandeFournisseur.objects.get(pk=r.json()['id'])
        self.assertEqual(
            list(bon.lignes.values_list('produit_id', flat=True)),
            [self.pa.pk])
        self.assertFalse(bon.lignes.filter(
            prix_achat_unitaire=Decimal('77')).exists())
        self.assertNotIn('PRODUIT-B-SECRET', r.content.decode())

        # BCF hérité de A envoyé, dont une ligne pointe le produit de B :
        # la réception le traite comme une ligne absente.
        bc = BonCommandeFournisseur.objects.create(
            company=self.co_a, reference='BCF-A-HERITE', fournisseur=self.fa,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.pb, quantite=3,
            prix_achat_unitaire=Decimal('77'))
        for prefix in PREFIXES:
            r = self.api.post(
                f'{prefix}bons-commande-fournisseur/{bc.pk}/recevoir/',
                {'receptions': [{'ligne': ligne.pk, 'quantite': 3}]},
                format='json')
            self.assertEqual(r.status_code, 400, r.content)
            self.assertIn('introuvable sur ce BCF', r.json()['detail'])
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 0)
        self._invariants_b()
