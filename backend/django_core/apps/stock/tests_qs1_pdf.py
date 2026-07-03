"""QS1 — Bouton « PDF (interne) » du bon de commande fournisseur.

Le bug : l'action ``generer_pdf`` (GET .../pdf/) était rangée avec les
actions d'ÉCRITURE (IsResponsableOrAdmin) alors que ``retrieve`` expose
les mêmes données à tout rôle authentifié (IsAnyRole). Un utilisateur
« normal » qui ouvrait la fiche BCF voyait le bouton PDF mais recevait un
403 — avalé côté front en « PDF indisponible. ».

Ici on fige le correctif :
  * tout rôle authentifié de la société obtient le PDF (200, content-type
    application/pdf, inline) ;
  * le multi-tenant reste étanche (404 pour une autre société).

Run:
    python manage.py test apps.stock.tests_qs1_pdf -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
)

User = get_user_model()


def _company(slug):
    from authentication.models import Company
    return Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})[0]


def _user(company, username, role='normal'):
    return User.objects.get_or_create(
        username=username,
        defaults={'company': company, 'role_legacy': role})[0]


def _client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class TestBcfPdfPermission(TestCase):
    def setUp(self):
        self.company = _company('qs1-co')
        self.admin = _user(self.company, 'qs1_admin', role='admin')
        self.normal = _user(self.company, 'qs1_normal', role='normal')
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur QS1')
        produit = Produit.objects.create(
            company=self.company, nom='Panneau QS1',
            prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
            quantite_stock=10)
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-QS1-001',
            fournisseur=fournisseur, created_by=self.admin)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=produit,
            quantite=2, prix_achat_unitaire=Decimal('700'))

    def test_normal_role_gets_the_pdf(self):
        """Le rôle normal (qui voit déjà le BCF via retrieve) obtient le PDF
        au lieu du 403 historique — la vraie cause du « PDF indisponible »."""
        r = _client(self.normal).get(
            f'/api/django/stock/bons-commande-fournisseur/{self.bcf.id}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertIn('BCF-QS1-001.pdf', r['Content-Disposition'])
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_admin_still_gets_the_pdf(self):
        r = _client(self.admin).get(
            f'/api/django/stock/bons-commande-fournisseur/{self.bcf.id}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_cross_tenant_stays_sealed(self):
        """Élargir la permission ne doit PAS élargir le périmètre société :
        un utilisateur d'une autre société reste sur un 404."""
        other = _user(_company('qs1-co-b'), 'qs1_other', role='admin')
        r = _client(other).get(
            f'/api/django/stock/bons-commande-fournisseur/{self.bcf.id}/pdf/')
        self.assertEqual(r.status_code, 404)
