# -*- coding: utf-8 -*-
"""AGNR9 (C-AGNR-013) — l'instantané restaurable porte CHAQUE clé d'entrée
ÉCRAN du schéma (clé absente du devis ⇒ ``None``), y compris un instantané
stocké avant, au moment où on le sert.

Avant : ``_etude_contenu`` ne gardait que ``cle in etude``. Un ×4
(``nombre_proprietes``) posé APRÈS V1 n'était pas dans l'instantané V1 ;
« Revenir à cette version » rejouait ``etude_params`` sans lui et le ×4
survivait (V_VB p_lgen3_4 : total ×4 au lieu de celui de V1).

Le test rejoue l'appel de l'écran : ``POST replace-lines {lignes,
etude_params: <étude de l'instantané V1>}``.

Test-du-test : remettre le filtre ``and cle in etude`` ⇒ ×4 conservé et
``test_restaurer_retire_les_cles_apparues`` échoue.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.etude_schema import ECRAN, ENTREE, SCHEMA, ecrire
from apps.ventes.domain.historique_config import (
    capturer_configuration_devis, configuration_devis_contenu)
from apps.ventes.models import ConfigurationDevisSnapshot, Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')

CLES_ECRAN = [cle for cle, regle in SCHEMA.items()
              if regle.get('nature') == ENTREE
              and regle.get('proprietaire') == ECRAN]


class RestaurationEtudeTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='AGNR9 Co', slug='agnr9-co')
        self.user = User.objects.create_user(
            username='agnr9_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AGNR9',
            telephone='+212600000009')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='AGNR9-PV', prix_vente=Decimal('1000'),
            quantite_stock=100)
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0009',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), created_by=self.user)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('10'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'),
            taux_tva=Decimal('20'), ordre=0)

    def test_instantane_porte_chaque_cle_ecran(self):
        etude = configuration_devis_contenu(self.devis)['etude']
        self.assertEqual(set(etude), set(CLES_ECRAN))
        self.assertIn('nombre_proprietes', etude)
        self.assertIsNone(etude['nombre_proprietes'])

    def test_restaurer_retire_les_cles_apparues(self):
        v1 = capturer_configuration_devis(self.devis, user=self.user)
        self.assertIsNotNone(v1)
        totaux_v1 = v1.contenu['totaux']
        frais = Devis.objects.get(pk=self.devis.pk)
        ecrire(frais, proprietaire=ECRAN, nombre_proprietes=4,
               kit_retire=['batterie'])
        frais = Devis.objects.get(pk=self.devis.pk)
        x4 = configuration_devis_contenu(frais)['totaux']
        self.assertEqual(Decimal(x4['ttc']), Decimal(totaux_v1['ttc']) * 4)

        lignes = []
        for ligne in v1.contenu['lignes']:
            copie = dict(ligne)
            copie.pop('lot', None)
            lignes.append(copie)
        r = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': lignes, 'etude_params': v1.contenu['etude']},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)

        # CLAUSE PERSISTANCE : relire en base.
        restaure = Devis.objects.get(pk=self.devis.pk)
        etude = restaure.etude_params or {}
        self.assertNotIn('nombre_proprietes', etude)
        self.assertNotIn('kit_retire', etude)
        self.assertEqual(configuration_devis_contenu(restaure)['totaux'],
                         totaux_v1)
        self.assertEqual(configuration_devis_contenu(restaure)['etude'],
                         v1.contenu['etude'])

    def test_instantane_stocke_avant_normalise_a_la_lecture(self):
        ancien = {'lignes': [], 'remise_globale': '0.00',
                  'echeancier': None, 'etude': {'scenario': 'Sans batterie'},
                  'totaux': {'ht_net': None, 'ttc': None}}
        snap = ConfigurationDevisSnapshot.objects.create(
            company=self.company, devis=self.devis, contenu=ancien,
            auteur=self.user)
        r = self.api.get(
            f'/api/django/ventes/devis/{self.devis.id}/'
            'historique-configuration/')
        self.assertEqual(r.status_code, 200, r.content)
        servi = next(s for s in r.data['snapshots'] if s['id'] == snap.id)
        etude = servi['contenu']['etude']
        self.assertEqual(set(etude), set(CLES_ECRAN))
        self.assertEqual(etude['scenario'], 'Sans batterie')
        self.assertIsNone(etude['nombre_proprietes'])
        # Lecture seule : l'objet stocké n'est pas réécrit.
        snap.refresh_from_db()
        self.assertEqual(snap.contenu, ancien)
