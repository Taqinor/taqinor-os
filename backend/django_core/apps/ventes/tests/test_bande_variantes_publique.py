"""QJR537 (Groupe QJR5) — la bande publique « Autres versions de ce devis »
ne montre plus les BROUILLONS : après une révision, la page de v1 exposait au
client la v2 en cours de correction, avec son total TTC. La ``note`` de
chaque sœur envoyée RESTE (D-QJR5-6 : texte client).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_bande_variantes_publique"
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class BandeVariantesPublique(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR537 Co', slug='qjr537-co')
        self.user = User.objects.create_user(
            username='qjr537_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR537',
            email='qjr537@example.test', telephone='+212600005370')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='QJR537-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        # Un devis sans onduleur n'a aucune option servable : la proposition
        # publique (format à options) le refuse (builder, règle de sécurité).
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 5kW',
            sku='QJR537-OND', prix_vente=Decimal('3000'),
            prix_achat=Decimal('2000'), quantite_stock=100)
        self.n = 0

    def _devis(self, statut, quantite, parent=None, note=''):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-537{self.n}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            created_by=self.user, version_parent=parent,
            version=(parent.version + self.n) if parent else 1, note=note)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation=self.produit.nom,
            quantite=Decimal(quantite), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=self.onduleur,
            designation=self.onduleur.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('3000'), remise=Decimal('0'))
        return devis

    def test_le_brouillon_soeur_n_est_jamais_expose(self):
        racine = self._devis(Devis.Statut.ENVOYE, '10')
        envoyee = self._devis(Devis.Statut.ENVOYE, '11', parent=racine,
                              note='Variante 11 panneaux')
        brouillon = self._devis(Devis.Statut.BROUILLON, '7', parent=racine,
                                note='En cours de correction')
        lien = ShareLink.for_devis(envoyee)
        r = APIClient().get(f'/api/django/ventes/proposal/{lien.token}/')
        self.assertEqual(r.status_code, 200, r.content)
        variantes = r.data['variants']
        refs = [v['reference'] for v in variantes]
        # La sœur ENVOYÉE (la racine) reste montrée, avec sa note.
        self.assertIn(racine.reference, refs)
        # Le brouillon : ni sa référence, ni son total, ni sa note.
        self.assertNotIn(brouillon.reference, refs)
        corps = json.dumps(variantes, default=str)
        self.assertNotIn(brouillon.reference, corps)
        # Total TTC du brouillon : (7 × 1 000 + 3 000) × 1,20 = 12 000.
        self.assertNotIn('12000', corps)
        self.assertNotIn('En cours de correction', corps)
