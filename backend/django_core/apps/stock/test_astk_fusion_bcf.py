"""ASTK66 — `fusionner_bcf` refuse des BCF aux rattachements différents
(chantier d'origine/de livraison, destination, devise, taux) et reporte sur
la cible ces champs, l'acheteur, la date prévue, les frais annexes et les PU
devise ; `dupliquer_bcf` réutilise la même liste.

Constat C-ASTK-016 (sonde BCF-10) : sources chantier_origine [81, 80] →
cible.chantier_origine=None ; la cible perdait destination, devise et frais.

Run :
    python manage.py test apps.stock.test_astk_fusion_bcf -v 2
"""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models_installation import Installation
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, EmplacementStock, Fournisseur, Produit,
)
from apps.stock.services import dupliquer_bcf, ensure_emplacements
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
URL = '/api/django/stock/bons-commande-fournisseur/fusionner/'


class FusionBcfTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            slug=f'astk66-co-{n}', nom=f'ASTK66 Co {n}')
        role = Role.objects.create(
            company=self.company, nom=f'r-astk66-{n}',
            permissions=['stock_modifier', 'stock_voir',
                         # ASTK17-20 (D-ASTK-3) : l'acheteur porte les codes achats.
                         'achats_commander', 'achats_receptionner',
                         'achats_payer', 'catalogue_prix_modifier'])
        self.user = User.objects.create_user(
            username=f'astk66-{n}', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK66')
        self.produit = Produit.objects.create(
            company=self.company, nom='Câble ASTK66', sku=f'ASTK66-{n}',
            prix_vente=Decimal('20'), prix_achat=Decimal('5'))
        client = Client.objects.create(
            company=self.company, nom='Client ASTK66', prenom='Test')
        self.ch80 = Installation.objects.create(
            company=self.company, reference=f'CH-ASTK66-A-{n}', client=client)
        self.ch81 = Installation.objects.create(
            company=self.company, reference=f'CH-ASTK66-B-{n}', client=client)
        ensure_emplacements(self.company)
        self.camionnette = EmplacementStock.objects.get(
            company=self.company, nom='Camionnette')

    def _bcf(self, frais='0', **extra):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK66-{next(_seq)}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON, **extra)
        bc.lignes.create(
            produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('108'),
            prix_achat_unitaire_devise=Decimal('10'),
            frais_annexes=Decimal(frais))
        return bc

    def test_chantiers_differents_refuse(self):
        bc1 = self._bcf(chantier_origine=self.ch81)
        bc2 = self._bcf(chantier_origine=self.ch80)
        resp = self.api.post(
            URL, {'bons_commande': [bc1.id, bc2.id]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('rattachements différents (chantier)', str(resp.data))
        for bc in (bc1, bc2):
            bc.refresh_from_db()
            self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.BROUILLON)

    def test_cible_porte_rattachements_frais_et_pu_devise(self):
        commun = dict(
            chantier_origine=self.ch80,
            emplacement_destination=self.camionnette,
            devise='EUR', taux_change=Decimal('10.8'))
        bc1 = self._bcf(frais='500', acheteur=self.user,
                        date_livraison_prevue=datetime.date(2026, 11, 20),
                        **commun)
        bc2 = self._bcf(date_livraison_prevue=datetime.date(2026, 11, 10),
                        **commun)
        resp = self.api.post(
            URL, {'bons_commande': [bc1.id, bc2.id]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        cible = BonCommandeFournisseur.objects.get(pk=resp.data['id'])
        self.assertEqual(cible.chantier_origine_id, self.ch80.id)
        self.assertEqual(cible.emplacement_destination_id, self.camionnette.id)
        self.assertEqual(cible.devise, 'EUR')
        self.assertEqual(cible.taux_change, Decimal('10.8'))
        self.assertEqual(cible.acheteur_id, self.user.id)
        self.assertEqual(cible.date_livraison_prevue,
                         datetime.date(2026, 11, 10))
        ligne = cible.lignes.get()
        self.assertEqual(ligne.quantite, 20)
        self.assertEqual(ligne.frais_annexes, Decimal('500'))
        self.assertEqual(ligne.prix_achat_unitaire_devise, Decimal('10'))

    def test_devises_differentes_refuse(self):
        bc1 = self._bcf(devise='EUR', taux_change=Decimal('10.8'))
        bc2 = self._bcf()
        resp = self.api.post(
            URL, {'bons_commande': [bc1.id, bc2.id]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_dupliquer_porte_les_memes_champs(self):
        bc = self._bcf(chantier_origine=self.ch80,
                       emplacement_destination=self.camionnette,
                       devise='EUR', taux_change=Decimal('10.8'))
        clone = dupliquer_bcf(self.company, self.user, bc)
        self.assertEqual(clone.chantier_origine_id, self.ch80.id)
        self.assertEqual(clone.emplacement_destination_id, self.camionnette.id)
        self.assertEqual(clone.devise, 'EUR')
        self.assertEqual(clone.lignes.get().prix_achat_unitaire_devise,
                         Decimal('10'))
