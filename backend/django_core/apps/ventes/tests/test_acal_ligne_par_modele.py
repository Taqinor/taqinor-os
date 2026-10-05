"""ACAL63 (C-ACAL-042) — le devis vend le module DÉSIGNÉ par le calepinage :
une ligne panneau par modèle (produit explicite prioritaire), kWc des lignes
= kWc du dessin, resynchro ligne par ligne, fiche non tarifée refusée.

Catalogue réel en base, aucun patch de ``_pick_product`` ; HTTP réel
(from-layout, sync-layout).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_ligne_par_modele"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.catalogue import _is_panel
from apps.ventes.domain.lignes import _classe_ligne
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


def _pan(identifiant, nombre, module_id):
    return {'id': identifiant, 'label': identifiant, 'geometry': {
        'moduleId': module_id, 'azimuthDeg': 180, 'tiltDeg': 20,
        'panels': [{'cx': i, 'cy': 0} for i in range(nombre)]}}


def _module(identifiant, produit, pmax):
    return {'id': identifiant, 'libelle': produit.nom, 'source': 'fiche',
            'produitId': produit.pk, 'pmaxWc': pmax}


class LigneParModele(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ACAL63 Co',
                                              slug='acal63-co')
        self.user = User.objects.create_user(
            username='acal63', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(company=self.company,
                                                nom='Client ACAL63')

        def produit(nom, sku, prix):
            return Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=Decimal(prix) if prix is not None else None,
                prix_achat=Decimal('1'), quantite_stock=100)
        self.p550 = produit('Panneau mono 550W', 'A63-550', '2290')
        self.p550_premium = produit('Panneau mono 550W premium',
                                    'A63-550P', '3500')
        self.p450 = produit('Panneau mono 450W', 'A63-450', '1900')
        produit('Onduleur réseau Growatt 10kW', 'A63-OND', '14000')

    def _layout(self, pans, modules):
        return {'scenario': 'reseau', 'panelWatt': 550, 'modules': modules,
                'zones': pans}

    def _from_layout(self, layout):
        return self.api.post('/api/django/ventes/devis/from-layout/',
                             {'layout': layout, 'client': self.client_obj.pk},
                             format='json')

    @staticmethod
    def _panneaux(devis_id):
        devis = Devis.objects.get(pk=devis_id)
        return {li.produit_id: int(li.quantite)
                for li in devis.lignes.all()
                if _classe_ligne(li, _is_panel) and int(li.quantite or 0)}

    def test_produit_designe_prime_sur_le_moins_cher(self):
        layout = self._layout(
            [_pan('A', 12, 'm1')],
            [_module('m1', self.p550_premium, 550)])
        r = self._from_layout(layout)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._panneaux(r.data['id']),
                         {self.p550_premium.pk: 12})

    def _deux_modeles(self, n450=4):
        return self._layout(
            [_pan('A', 8, 'm550'), _pan('B', n450, 'm450')],
            [_module('m550', self.p550, 550), _module('m450', self.p450, 450)])

    def test_deux_modeles_deux_lignes_kwc_egal(self):
        r = self._from_layout(self._deux_modeles())
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._panneaux(r.data['id']),
                         {self.p550.pk: 8, self.p450.pk: 4})
        kwc_lignes = (8 * 550 + 4 * 450) / 1000.0
        self.assertAlmostEqual(kwc_lignes, 6.2)
        from apps.ventes.domain.geometrie import lire_layout
        self.assertAlmostEqual(lire_layout(self._deux_modeles()).kwc,
                               kwc_lignes)

    def test_resynchro_ecart_sur_la_bonne_ligne(self):
        r = self._from_layout(self._deux_modeles())
        self.assertEqual(r.status_code, 201, r.data)
        devis_id = r.data['id']
        sync = self.api.post(
            f'/api/django/ventes/devis/{devis_id}/sync-layout/',
            self._deux_modeles(n450=6), format='json')
        self.assertEqual(sync.status_code, 200, sync.data)
        self.assertEqual(self._panneaux(devis_id),
                         {self.p550.pk: 8, self.p450.pk: 6})
        # Une seconde resynchro identique ne duplique rien.
        sync = self.api.post(
            f'/api/django/ventes/devis/{devis_id}/sync-layout/',
            self._deux_modeles(n450=6), format='json')
        self.assertEqual(sync.status_code, 200, sync.data)
        self.assertEqual(self._panneaux(devis_id),
                         {self.p550.pk: 8, self.p450.pk: 6})

    def test_produit_non_tarife_refuse(self):
        Produit.objects.filter(pk=self.p550_premium.pk).update(
            prix_vente=Decimal('0'))
        avant = Devis.objects.filter(company=self.company).count()
        r = self._from_layout(self._layout(
            [_pan('A', 12, 'm1')],
            [_module('m1', self.p550_premium, 550)]))
        self.assertEqual(r.status_code, 422, r.data)
        self.assertIn('tarifez la fiche', str(r.data))
        self.assertIn('Panneau mono 550W premium', str(r.data))
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
