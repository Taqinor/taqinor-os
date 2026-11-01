"""ACHT25 (C-ACHT-023) — aucun composite n'entre en stock sans consommation :
création / clôture d'un ordre sur un kit sans composant exploitable
(produit catalogue et quantité > 0) et activation d'un tel kit refusées
(409 « Nomenclature vide »).

Rejoue CKIT-10 : Fantome +7 et Fantome2 +2 entrés sans aucune consommation.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_kit_vide"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, OrdreAssemblageLigne,
)
from apps.stock.models import MouvementStock, Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
BASE = '/api/django/installations'
MSG = 'Nomenclature vide'


class KitVideTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht25', defaults={'nom': 'Co ACHT25'})
        self.user = User.objects.create_user(
            username='resp-acht25', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fantome = Produit.objects.create(
            company=self.company, nom='Fantome', prix_vente=10,
            prix_achat=0, quantite_stock=0)

    def _kit(self, nom, **extra):
        return Kit.objects.create(company=self.company, nom=nom,
                                  produit_compose=self.fantome, **extra)

    def _assert_rien_entre(self):
        self.fantome.refresh_from_db()
        self.assertEqual(self.fantome.quantite_stock, 0)
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.fantome).exists())

    def test_ordre_kit_vide_refuse(self):
        kit = self._kit('Kit vide')
        r = self.api.post(f'{BASE}/ordres-assemblage/',
                          {'kit': kit.id, 'quantite': 7}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(MSG, str(r.data))
        # Ordre hérité (créé avant la garde) : la clôture est refusée aussi.
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ACHT25-1', kit=kit,
            quantite=7)
        r = self.api.post(f'{BASE}/ordres-assemblage/{ordre.id}/terminer/',
                          {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(MSG, str(r.data))
        self._assert_rien_entre()

    def test_kit_designation_seule_refuse(self):
        kit = self._kit('Kit désignation')
        KitComposant.objects.create(kit=kit, produit=None,
                                    designation='Câble libre', quantite=4)
        r = self.api.post(f'{BASE}/ordres-assemblage/',
                          {'kit': kit.id, 'quantite': 2}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(MSG, str(r.data))
        r = self.api.post(f'{BASE}/ordres-demontage/',
                          {'kit': kit.id, 'quantite': 1}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self._assert_rien_entre()

    def test_activation_kit_vide_refusee(self):
        kit = self._kit('Kit inactif', active=False)
        r = self.api.patch(f'{BASE}/kits/{kit.id}/', {'active': True},
                           format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(MSG, str(r.data))
        kit.refresh_from_db()
        self.assertFalse(kit.active)

    # ACHT119 (C-ACHT-VER-010) — `depuis-devis` et lignes réelles de l'ordre.
    def test_depuis_devis_kit_vide_refuse(self):
        kit = self._kit('Kit vide devis')
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='acht119@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ACHT119-1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.fantome, designation='Fantome',
            quantite=Decimal('1'), prix_unitaire=Decimal('100'))
        r = self.api.post(f'{BASE}/ordres-assemblage/depuis-devis/',
                          {'devis': devis.id}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(MSG, str(r.data))
        self.assertFalse(OrdreAssemblage.objects.filter(
            company=self.company, devis=devis, kit=kit).exists())
        self._assert_rien_entre()

    def test_terminer_lignes_sans_produit_refuse(self):
        kit = self._kit('Kit lignes')
        vis = Produit.objects.create(
            company=self.company, nom='Vis', prix_vente=1, prix_achat=0,
            quantite_stock=50)
        KitComposant.objects.create(kit=kit, produit=vis, quantite=2)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ACHT119-1', kit=kit,
            quantite=1, statut=OrdreAssemblage.Statut.EN_COURS)
        OrdreAssemblageLigne.objects.filter(ordre=ordre).delete()
        OrdreAssemblageLigne.objects.create(
            ordre=ordre, produit=None, designation='Visserie', quantite=3)
        r = self.api.post(f'{BASE}/ordres-assemblage/{ordre.id}/terminer/',
                          {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn(MSG, str(r.data))
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreAssemblage.Statut.EN_COURS)
        self._assert_rien_entre()
        vis.refresh_from_db()
        self.assertEqual(vis.quantite_stock, 50)
