"""ACAL63 (C-ACAL-042) — le devis vend le module DÉSIGNÉ par le calepinage :
une ligne panneau par modèle (produit explicite prioritaire), kWc des lignes
= kWc du dessin, resynchro ligne par ligne, fiche non tarifée refusée.
ACAL353 (C-ACAL-VER-001) — la resynchro (``sync-layout`` puis ``sync-devis``
du module) refuse en 409 nommé, sans rien écrire au devis, un document dont
une surface pavée n'a pas de ``moduleWc`` ou dont un pan désigne un module
absent de ``modules[]``. ACAL354 (C-ACAL-VER-002) — de même une fiche
désignée SANS ligne au devis et non tarifée (« tarifez la fiche … »).

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

from apps.calepinage.models import Calepinage
from apps.crm.models import Client
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
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

    def _toit_douze(self, **extra):
        return dict({'scenario': 'reseau', 'panelWatt': 550, 'zones': [{
            'id': 'z', 'label': 'Toit', 'geometry': {
                'count': 12, 'kwc': 6.6, 'azimuthDeg': 180,
                'tiltDeg': 30}}]}, **extra)

    def _etat(self, devis_id):
        devis = Devis.objects.get(pk=devis_id)
        return self._panneaux(devis_id), devis.total_ttc, devis.layout_hash

    def _api_directeur(self):
        """Le module calepinage exige ``calepinage_gerer`` (rôle Directeur)."""
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        directeur = User.objects.create_user(
            username='acal353-dir', password='x', company=self.company,
            role=role, role_legacy='responsable')
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(directeur)}')
        return api

    def _refus_aux_deux_routes(self, initial, document, attendus,
                               api_module):
        """Né de ``from-layout`` (``initial``), puis ``document`` posté par
        ``sync-layout`` ET par ``sync-devis`` du module : 409 nommé aux deux,
        devis relu identique. Rend l'id du devis."""
        r = self._from_layout(initial)
        self.assertEqual(r.status_code, 201, r.data)
        devis_id = r.data['id']
        avant = self._etat(devis_id)
        self.assertEqual(sum(avant[0].values()), 12)
        sync = self.api.post(
            f'/api/django/ventes/devis/{devis_id}/sync-layout/', document,
            format='json')
        calepinage, _ = Calepinage.objects.update_or_create(
            company=self.company, devis_id=devis_id,
            defaults={'client': self.client_obj, 'roof_layout': document})
        module = api_module.post(
            f'/api/django/calepinage/calepinages/{calepinage.pk}/sync-devis/',
            {}, format='json')
        for reponse in (sync, module):
            self.assertEqual(reponse.status_code, 409, reponse.data)
            self.assertIn('revision_possible', reponse.data)
            for attendu in attendus:
                self.assertIn(attendu, reponse.data['detail'])
        # Le refus précède toute écriture : lignes, TTC, empreinte relus.
        self.assertEqual(self._etat(devis_id), avant)
        return devis_id

    def test_resynchro_refuse_surface_sans_puissance_et_module_non_resolu(
            self):
        Produit.objects.create(
            company=self.company, nom='Onduleur réseau Growatt 50kW',
            sku='A63-OND50', prix_vente=Decimal('30000'),
            prix_achat=Decimal('1'), quantite_stock=100)
        api_module = self._api_directeur()
        surface = {'id': 's1', 'kind': 'sol', 'label': 'Champ au sol',
                   'rowAzimuthDeg': 90, 'tiltDeg': 25,
                   'engine': {'modules': 40}}
        self._refus_aux_deux_routes(
            self._toit_douze(), self._toit_douze(poseSurfaces=[surface]),
            ('Surface de pose « Champ au sol »', 'moduleWc'), api_module)
        pan_orphelin = self._toit_douze()
        pan_orphelin['zones'][0]['geometry']['moduleId'] = 'mX'
        self._refus_aux_deux_routes(
            self._toit_douze(), pan_orphelin,
            ('Pan « Toit »', 'le module « mX » ne figure pas dans « modules »'),
            api_module)

    def test_resynchro_vers_fiche_non_tarifee_refusee(self):
        initial = self._layout([_pan('A', 12, 'm1')],
                               [_module('m1', self.p550, 550)])
        premium = self._layout([_pan('A', 12, 'm2')],
                               [_module('m2', self.p550_premium, 550)])
        Produit.objects.filter(pk=self.p550_premium.pk).update(
            prix_vente=Decimal('0'))
        devis_id = self._refus_aux_deux_routes(
            initial, premium,
            ("Le module désigné par le calepinage n'est pas tarifé : "
             "tarifez la fiche « Panneau mono 550W premium » (prix de vente) "
             "puis relancez.",), self._api_directeur())
        self.assertEqual(self._panneaux(devis_id), {self.p550.pk: 12})
        # Fiche tarifée : la même resynchro crée la ligne premium et ramène
        # l'ancienne à 0 (ACAL63 conservé).
        Produit.objects.filter(pk=self.p550_premium.pk).update(
            prix_vente=Decimal('3500'))
        sync = self.api.post(
            f'/api/django/ventes/devis/{devis_id}/sync-layout/', premium,
            format='json')
        self.assertEqual(sync.status_code, 200, sync.data)
        self.assertEqual(self._panneaux(devis_id),
                         {self.p550_premium.pk: 12})
