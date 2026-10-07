"""ASTK25 — une réception fournisseur CONFIRMÉE/ANNULÉE et un retour
fournisseur VALIDÉ/ANNULÉ sont figés : tout PUT/PATCH répond 400
« … : non modifiable » (verrou unique `DocumentFigeMixin`).

Rejoue BCF-12 de l'audit stock du 2026-10-06 : avant correction, PATCH
{date_reception: '2020-01-01'} d'une réception confirmée → 200 (appliqué,
valorisation à date et OTD faussés) et PATCH {bon_commande: <autre BCF>}
→ 200 (la réception changeait de BCF après avoir avancé le premier).

Run:
    python manage.py test apps.stock.test_astk_reception_figee -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneRetourFournisseur, Produit, ReceptionFournisseur, RetourFournisseur,
)
from apps.stock.services import apply_retour_fournisseur

User = get_user_model()

BASE = '/api/django/stock/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ReceptionFigeeTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='astk25', slug='astk25')
        self.user = User.objects.create_user(
            username='astk25-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = _api(self.user)
        self.f = Fournisseur.objects.create(company=self.co, nom='F ASTK25')
        self.f2 = Fournisseur.objects.create(company=self.co, nom='F2 ASTK25')
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau ASTK25', sku='PAN-ASTK25',
            prix_vente=Decimal('100'), prix_achat=Decimal('60'),
            quantite_stock=0)
        self.bc177 = self._bcf('BCF-177')
        self.bc178 = self._bcf('BCF-178')

    def _bcf(self, ref):
        bc = BonCommandeFournisseur.objects.create(
            company=self.co, reference=ref, fournisseur=self.f,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('60'))
        return bc

    def _reception(self, confirmer=True):
        ligne = self.bc177.lignes.get()
        r = self.api.post(f'{BASE}receptions-fournisseur/', {
            'bon_commande': self.bc177.pk, 'date_reception': '2026-10-06',
            'lignes': [{'ligne_commande': ligne.pk, 'quantite': 4}],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        rid = r.json()['id']
        if confirmer:
            r = self.api.post(f'{BASE}receptions-fournisseur/{rid}/confirmer/')
            self.assertEqual(r.status_code, 200, r.content)
        return ReceptionFournisseur.objects.get(pk=rid)

    def test_patch_date_refuse(self):
        rec = self._reception()
        url = f'{BASE}receptions-fournisseur/{rec.pk}/'
        r = self.api.patch(url, {'date_reception': '2020-01-01'},
                           format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('non modifiable', r.json()['detail'])
        rec.refresh_from_db()
        self.assertEqual(rec.date_reception, datetime.date(2026, 10, 6))

    def test_patch_bon_commande_et_put_lignes_refuses(self):
        rec = self._reception()
        url = f'{BASE}receptions-fournisseur/{rec.pk}/'
        r = self.api.patch(url, {'bon_commande': self.bc178.pk},
                           format='json')
        self.assertEqual(r.status_code, 400, r.content)
        ligne = self.bc178.lignes.get()
        r = self.api.put(url, {
            'bon_commande': self.bc178.pk, 'date_reception': '2020-01-01',
            'recu_par': self.user.pk,
            'lignes': [{'ligne_commande': ligne.pk, 'quantite': 9}],
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        rec.refresh_from_db()
        self.assertEqual(rec.bon_commande_id, self.bc177.pk)
        self.assertEqual(rec.date_reception, datetime.date(2026, 10, 6))
        self.assertEqual(self.bc178.lignes.get().quantite_recue, 0)

    def test_reception_annulee_figee(self):
        rec = self._reception(confirmer=False)
        ReceptionFournisseur.objects.filter(pk=rec.pk).update(
            statut=ReceptionFournisseur.Statut.ANNULE)
        r = self.api.patch(f'{BASE}receptions-fournisseur/{rec.pk}/',
                           {'note': 'x'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_reception_brouillon_reste_modifiable(self):
        rec = self._reception(confirmer=False)
        r = self.api.patch(f'{BASE}receptions-fournisseur/{rec.pk}/',
                           {'date_reception': '2026-10-05'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        rec.refresh_from_db()
        self.assertEqual(rec.date_reception, datetime.date(2026, 10, 5))

    def test_retour_valide_fige(self):
        self.produit.quantite_stock = 10
        self.produit.save(update_fields=['quantite_stock'])
        retour = RetourFournisseur.objects.create(
            company=self.co, reference='RF-ASTK25', fournisseur=self.f)
        LigneRetourFournisseur.objects.create(
            retour=retour, produit=self.produit, quantite=2, motif='x')
        apply_retour_fournisseur(retour, self.user)
        retour.refresh_from_db()
        self.assertEqual(retour.statut, RetourFournisseur.Statut.VALIDE)
        r = self.api.patch(f'{BASE}retours-fournisseur/{retour.pk}/',
                           {'fournisseur': self.f2.pk}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('non modifiable', r.json()['detail'])
        retour.refresh_from_db()
        self.assertEqual(retour.fournisseur_id, self.f.pk)
