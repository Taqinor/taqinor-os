"""ASTK22 — un BCF n'atteint ENVOYE ou RECU que par ses gestes.

Rejoue BCF-4 (audit stock 06/10/2026) avec un seuil d'approbation actif :
`envoyer` = 400 MAIS PATCH {statut:'envoye'} = 200, PATCH {statut:'recu'} =
200 sans mouvement, annulé → brouillon par PATCH = 200, envoyer-email = 200
(statut envoyé), réception créée sur un BCF brouillon = 201.

Source réelle : `installations.selectors.bcf_approbation_valide` (lu par la vue,
non mocké).

Run :
    python manage.py test apps.stock.test_astk_bcf_statut -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models_approbation_bcf import SeuilApprobationBCF
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    MouvementStock, Produit, ReceptionFournisseur,
)
from apps.ventes.models import EmailLog
from authentication.models import Company

User = get_user_model()

BCF = '/api/django/stock/bons-commande-fournisseur/'
REC = '/api/django/stock/receptions-fournisseur/'


class BcfStatutTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK22', slug='astk22-co')
        role = Role.objects.create(
            company=self.company, nom='r-astk22',
            permissions=['stock_modifier', 'stock_voir', 'prix_achat_voir',
                         # ASTK17-20 (D-ASTK-3) : l'acheteur porte les codes achats.
                         'achats_commander', 'achats_receptionner',
                         'achats_payer', 'catalogue_prix_modifier'])
        self.user = User.objects.create_user(
            username='astk22-resp', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        SeuilApprobationBCF.objects.create(
            company=self.company, seuil_responsable=Decimal('500'),
            actif=True)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK22',
            telephone='0612345678', email='fournisseur@exemple.ma')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK22', sku='ASTK22-1',
            prix_vente=Decimal('1500'), prix_achat=Decimal('1000'),
            quantite_stock=0)
        self.brouillon = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK22-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        self.ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.brouillon, produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('1000'))
        self.annule = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK22-2',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ANNULE)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.annule, produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('1000'))

    def _statut(self, bc):
        bc.refresh_from_db()
        return bc.statut

    def _post(self, bc, geste, body=None):
        return self.api.post(f'{BCF}{bc.pk}/{geste}/', body or {},
                             format='json')

    def test_envoyer_refuse_sans_approbation(self):
        rep = self._post(self.brouillon, 'envoyer')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(self._statut(self.brouillon),
                         BonCommandeFournisseur.Statut.BROUILLON)

    def test_patch_statut_ignore(self):
        for cible in ('envoye', 'recu'):
            rep = self.api.patch(f'{BCF}{self.brouillon.pk}/',
                                 {'statut': cible}, format='json')
            self.assertIn(rep.status_code, (200, 400), rep.data)
            self.assertEqual(self._statut(self.brouillon),
                             BonCommandeFournisseur.Statut.BROUILLON)
        rep = self.api.patch(f'{BCF}{self.annule.pk}/',
                             {'statut': 'brouillon'}, format='json')
        self.assertIn(rep.status_code, (200, 400), rep.data)
        self.assertEqual(self._statut(self.annule),
                         BonCommandeFournisseur.Statut.ANNULE)
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.produit).exists())

    def test_email_sans_approbation_refuse(self):
        envoyer = self._post(self.brouillon, 'envoyer')
        rep = self._post(self.brouillon, 'envoyer-email')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.data['detail'], envoyer.data['detail'])
        self.assertEqual(self._statut(self.brouillon),
                         BonCommandeFournisseur.Statut.BROUILLON)
        self.assertFalse(EmailLog.objects.filter(
            company=self.company).exists())

    def test_whatsapp_sans_approbation_refuse(self):
        envoyer = self._post(self.brouillon, 'envoyer')
        rep = self._post(self.brouillon, 'whatsapp')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.data['detail'], envoyer.data['detail'])
        self.assertNotIn('wa_url', rep.data)
        self.assertEqual(self._statut(self.brouillon),
                         BonCommandeFournisseur.Statut.BROUILLON)

    def test_reception_sur_bcf_brouillon_refusee(self):
        rep = self.api.post(REC, {
            'bon_commande': self.brouillon.pk,
            'lignes': [{'ligne_commande': self.ligne.pk, 'quantite': 1}],
        }, format='json')
        self.assertEqual(rep.status_code, 400, rep.data)
        self.assertIn('BCF non envoyé', str(rep.data))
        self.assertFalse(ReceptionFournisseur.objects.filter(
            bon_commande=self.brouillon).exists())

    def test_confirmation_sur_bcf_brouillon_refusee(self):
        # Réception brouillon héritée (créée avant la garde).
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK22-1',
            bon_commande=self.brouillon,
            statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec.lignes.create(ligne_commande=self.ligne, produit=self.produit,
                          quantite=1)
        rep = self.api.post(f'{REC}{rec.pk}/confirmer/')
        self.assertEqual(rep.status_code, 400, rep.data)
        self.assertIn('BCF non envoyé', rep.data['detail'])
        rec.refresh_from_db()
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.BROUILLON)
        self.assertEqual(self._statut(self.brouillon),
                         BonCommandeFournisseur.Statut.BROUILLON)
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.produit).exists())
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)
