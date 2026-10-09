"""ACHT4 (C-ACHT-004) — un seul chantier par affaire (devis et toute sa chaîne
de révisions) : `creer-depuis-devis` sur une version remplacée renvoie le
chantier de l'affaire, `devis` est en lecture seule dans
`InstallationSerializer`, et une contrainte unique partielle
(company, devis) protège la base.

Rejoue CCRE-4 : V1 acceptée (chantier CHT-1) → V2 acceptée (chantier
rattaché à la V2) ; creer-depuis-devis V1 répondait 201 created=true (22
panneaux réservés), le POST et le PATCH `devis` créaient d'autres chantiers
sur le même devis.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_chantier_unique"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import Installation, StockReservation
from apps.stock.models import Produit
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()
BASE = '/api/django/installations/chantiers/'


class ChantierUniqueTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht4', defaults={'nom': 'Co ACHT4'})
        self.user = User.objects.create_user(
            username='resp-acht4', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ACHT4', sku='PAN-ACHT4',
            prix_vente=Decimal('100'), quantite_stock=100)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='acht4@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        self.v1 = Devis.objects.create(
            company=self.company, reference='DEV-ACHT4-1',
            client=self.client_obj, lead=lead,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=self.v1, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'))
        self._accepter(self.v1)
        self.cht1 = Installation.objects.get(devis=self.v1)
        v2 = reviser_devis(self.v1, user=self.user)
        LigneDevis.objects.filter(devis=v2, produit=self.panneau).update(
            quantite=Decimal('12'))
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ACCEPTE)
        self.v2 = Devis.objects.get(pk=v2.pk)
        self._accepter(self.v2)
        self.v1.refresh_from_db()
        self.cht1.refresh_from_db()
        self.assertEqual(self.cht1.devis_id, self.v2.pk)

    def _accepter(self, devis):
        devis_accepted.send(sender=None, devis=devis, user=self.user,
                            ancien_statut='envoye')

    def _panneaux_reserves(self):
        return sum(StockReservation.objects.filter(
            installation__company=self.company, produit=self.panneau,
            active=True, consomme=False).values_list('quantite', flat=True))

    def test_creer_depuis_v1_remplacee(self):
        r = self.api.post(f'{BASE}creer-depuis-devis/', {'devis': self.v1.id},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['created'])
        self.assertEqual(r.data['id'], self.cht1.id)
        self.assertEqual(
            Installation.objects.filter(company=self.company).count(), 1)
        self.assertEqual(self._panneaux_reserves(), 12)

    def test_post_devis_deja_pourvu(self):
        r = self.api.post(BASE, {'devis': self.v2.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        cree = Installation.objects.get(pk=r.data['id'])
        self.assertIsNone(cree.devis_id)
        self.assertEqual(
            Installation.objects.filter(devis=self.v2).count(), 1)

    def test_patch_devis_ignore(self):
        autre = Installation.objects.create(
            company=self.company, reference='CHT-ACHT4-AUTRE',
            client=self.client_obj)
        r = self.api.patch(f'{BASE}{autre.id}/', {'devis': self.v2.id},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        autre.refresh_from_db()
        self.assertIsNone(autre.devis_id)
        self.assertEqual(
            Installation.objects.filter(devis=self.v2).count(), 1)
        self.assertEqual(self._panneaux_reserves(), 12)

    def test_contrainte_base(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Installation.objects.create(
                    company=self.company, reference='CHT-ACHT4-DOUBLON',
                    client=self.client_obj, devis=self.v2)
        # Plusieurs chantiers SANS devis restent permis (contrainte partielle).
        Installation.objects.create(
            company=self.company, reference='CHT-ACHT4-L1')
        Installation.objects.create(
            company=self.company, reference='CHT-ACHT4-L2')
