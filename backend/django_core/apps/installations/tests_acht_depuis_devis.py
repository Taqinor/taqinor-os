"""ACHT23 (C-ACHT-021) — « Assembler à la commande » (`depuis-devis`) lit les
quantités VENDUES sur la nomenclature gelée (option retenue × N villas,
options non activées exclues), cumule par kit (un ordre par kit, mis à jour
tant qu'il est planifié) et fige `revision_kit_numero`.

Rejoue CKIT-8 : [KAC 1, KDC 1] créés (option non activée prise, ×3
ignoré) ; seconde ligne du même kit perdue ; `revision_kit_numero` None.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_depuis_devis"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import Kit, KitComposant, OrdreAssemblage
from apps.installations.services import snapshot_revision_kit
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
URL = '/api/django/installations/ordres-assemblage/depuis-devis/'


class DepuisDevisTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht23', defaults={'nom': 'Co ACHT23'})
        self.user = User.objects.create_user(
            username='resp-acht23', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.coffret_ac = self._produit('Coffret AC', 0)
        self.coffret_dc = self._produit('Coffret DC', 0)
        disj = self._produit('Disjoncteur', 500)
        self.kac = Kit.objects.create(
            company=self.company, nom='KAC', produit_compose=self.coffret_ac)
        KitComposant.objects.create(kit=self.kac, produit=disj, quantite=2)
        self.kdc = Kit.objects.create(
            company=self.company, nom='KDC', produit_compose=self.coffret_dc)
        KitComposant.objects.create(kit=self.kdc, produit=disj, quantite=1)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='acht23@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ACHT23-1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel',
            etude_params={'nombre_proprietes': 3})
        LigneDevis.objects.create(
            devis=self.devis, produit=self.coffret_ac,
            designation='Coffret AC', quantite=Decimal('1'),
            prix_unitaire=Decimal('100'))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.coffret_dc,
            designation='Coffret DC', quantite=Decimal('1'),
            prix_unitaire=Decimal('100'), optionnelle=True)

    def _produit(self, nom, stock):
        return Produit.objects.create(
            company=self.company, nom=nom, prix_vente=200, prix_achat=0,
            quantite_stock=stock)

    def _post(self):
        r = self.api.post(URL, {'devis': self.devis.id}, format='json')
        self.assertIn(r.status_code, (200, 201), r.data)
        return r

    def _ordres(self):
        return sorted(OrdreAssemblage.objects.filter(
            company=self.company, devis=self.devis).values_list(
                'kit__nom', 'quantite'))

    def test_option_non_activee_ignoree(self):
        self._post()
        self.assertFalse(OrdreAssemblage.objects.filter(
            devis=self.devis, kit=self.kdc).exists())

    def test_multivilla(self):
        self._post()
        self.assertEqual(self._ordres(), [('KAC', 3)])

    def test_cumul_par_kit(self):
        self._post()
        LigneDevis.objects.create(
            devis=self.devis, produit=self.coffret_ac,
            designation='Coffret AC bis', quantite=Decimal('4'),
            prix_unitaire=Decimal('100'))
        r = self._post()
        self.assertEqual(self._ordres(), [('KAC', 15)])
        kits = [o['kit'] for o in r.data]
        self.assertEqual(len(kits), len(set(kits)))
        ordre = OrdreAssemblage.objects.get(devis=self.devis, kit=self.kac)
        self.assertEqual(
            float(ordre.lignes.get().quantite), 30.0)

    def test_revision_figee(self):
        self._post()
        ordre = OrdreAssemblage.objects.get(devis=self.devis, kit=self.kac)
        revision, _ = snapshot_revision_kit(self.kac, user=self.user)
        self.assertIsNotNone(ordre.revision_kit_numero)
        self.assertEqual(ordre.revision_kit_numero, revision.numero)
