"""ASTK214 (C-ASTK-045, CAT-8) — les champs maîtres lus par des consommateurs
(classe_danger, quantite_reappro_cible, louable, tarif_location_*,
est_recurrent, periodicite_defaut) sont lisibles ET écrivables par l'API.

Reproduction CAT-8 : PATCH produits/<id>/ {"est_recurrent": true} → 200 sans
effet (champ absent de ProduitSerializer.Meta.fields, ignoré en silence).

Run :
    python manage.py test apps.stock.test_astk_champs_maitres -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.stock.models import Produit

User = get_user_model()
CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'produit_champs_maitres.json').read_text(encoding='utf-8'))


class ChampsMaitresTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='astk214', slug='astk214')
        self.admin = User.objects.create_user(
            username='astk214-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 5 kWh', sku='ASTK214-BAT',
            prix_vente=Decimal('7200'), prix_achat=Decimal('5000'),
            quantite_stock=3)
        self.url = f'/api/django/stock/produits/{self.produit.id}/'

    def _patch(self, corps):
        return self.api.patch(self.url, corps, format='json')

    def test_patch_ecrit_les_champs(self):
        corps = {
            'est_recurrent': True, 'periodicite_defaut': 'mensuel',
            'classe_danger': 'BATTERIE_LITHIUM', 'quantite_reappro_cible': 20,
            'louable': True, 'tarif_location_jour': '150.00',
            'tarif_location_semaine': '900.00', 'tarif_location_mois': '3000.00',
        }
        resp = self._patch(corps)
        self.assertEqual(resp.status_code, 200, resp.content)
        relu = self.api.get(self.url).json()
        for cle, valeur in corps.items():
            self.assertEqual(relu[cle], valeur, cle)
        p = Produit.objects.get(pk=self.produit.pk)
        self.assertTrue(p.est_recurrent)
        self.assertEqual(p.periodicite_defaut, 'mensuel')
        self.assertEqual(p.classe_danger, 'BATTERIE_LITHIUM')
        self.assertEqual(p.quantite_reappro_cible, 20)
        self.assertTrue(p.louable)
        self.assertEqual(p.tarif_location_jour, Decimal('150.00'))

    def test_patch_sans_ces_cles_ne_les_remet_pas_a_zero(self):
        self._patch({'est_recurrent': True, 'quantite_reappro_cible': 20,
                     'classe_danger': 'INFLAMMABLE'})
        resp = self._patch({'nom': 'Batterie 5 kWh v2'})
        self.assertEqual(resp.status_code, 200, resp.content)
        p = Produit.objects.get(pk=self.produit.pk)
        self.assertTrue(p.est_recurrent)
        self.assertEqual(p.quantite_reappro_cible, 20)
        self.assertEqual(p.classe_danger, 'INFLAMMABLE')

    def test_choix_invalide_400(self):
        resp = self._patch({'classe_danger': 'radioactif',
                            'periodicite_defaut': 'hebdo'})
        self.assertEqual(resp.status_code, 400, resp.content)
        corps = resp.json()
        self.assertIn('classe_danger', corps)
        self.assertIn('periodicite_defaut', corps)
        p = Produit.objects.get(pk=self.produit.pk)
        self.assertEqual(p.classe_danger, 'AUCUNE')

    def test_tarif_negatif_400(self):
        resp = self._patch({'tarif_location_jour': '-1.00'})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['tarif_location_jour'],
                         ['Le tarif de location ne peut pas être négatif.'])
        self.assertIsNone(
            Produit.objects.get(pk=self.produit.pk).tarif_location_jour)

    def test_conforme_contrat(self):
        relu = self.api.get(self.url).json()
        attendues = (set(CONTRAT['exemple'])
                     | set(CONTRAT['exemple_nouveau_astk214']))
        self.assertEqual(attendues - set(relu), set())
        self.assertEqual(set(CONTRAT['cles_nouvelles_astk214']) - set(relu),
                         set())
        # Les valeurs de choix du contrat sont celles du modèle.
        for cle in ('classe_danger', 'periodicite_defaut'):
            valeurs = [v for v, _ in CONTRAT['choices'][cle]['valeurs']]
            modele = [v for v, _ in Produit._meta.get_field(cle).choices]
            self.assertEqual(valeurs, modele, cle)
