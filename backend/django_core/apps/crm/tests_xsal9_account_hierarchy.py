"""XSAL9 — Hiérarchie de comptes (société mère / filiales) + consolidation.

Couvre :
  - ``Client.clean()`` rejette un cycle (A→B→A) et une auto-référence ;
  - ``clean()`` rejette une société mère d'une AUTRE société (cross-tenant) ;
  - ``ClientSerializer.validate_parent`` applique les mêmes gardes côté API ;
  - ``selectors.consolidation_client`` agrège CE client + descendants récursifs
    (filiales de filiales) ;
  - un client sans filiale renvoie un rollup dégradé (ses seuls chiffres) ;
  - jamais de fuite cross-société dans le rollup ;
  - l'endpoint ``GET /crm/clients/<id>/consolidation/`` répond correctement.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.crm.selectors import consolidation_client
from apps.crm.serializers import ClientSerializer
from apps.ventes.models import Devis

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ClientCleanAntiCycleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL9', slug='taqinor-xsal9')

    def test_auto_reference_rejetee(self):
        client = Client.objects.create(company=self.company, nom='Solo')
        client.parent = client
        with self.assertRaises(ValidationError):
            client.clean()

    def test_cycle_direct_rejete(self):
        a = Client.objects.create(company=self.company, nom='A')
        b = Client.objects.create(company=self.company, nom='B', parent=a)
        a.parent = b
        with self.assertRaises(ValidationError):
            a.clean()

    def test_hierarchie_valide_acceptee(self):
        a = Client.objects.create(company=self.company, nom='Mère')
        b = Client.objects.create(company=self.company, nom='Fille', parent=a)
        b.clean()  # ne lève pas

    def test_parent_autre_societe_rejete(self):
        other = Company.objects.create(nom='Autre XSAL9', slug='xsal9-autre')
        mere_autre = Client.objects.create(company=other, nom='Mère autre')
        fille = Client.objects.create(company=self.company, nom='Fille')
        fille.parent = mere_autre
        with self.assertRaises(ValidationError):
            fille.clean()


class ClientSerializerValidateParentTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL9 Serializer', slug='taqinor-xsal9-serializer')
        self.user = User.objects.create_user(
            username='xsal9_user', password='x', company=self.company,
            role_legacy='admin')

    def _ctx(self):
        class _Req:
            user = self.user
        return {'request': _Req()}

    def test_cycle_rejete_par_le_serializer(self):
        a = Client.objects.create(company=self.company, nom='A')
        b = Client.objects.create(company=self.company, nom='B', parent=a)
        serializer = ClientSerializer(instance=a, context=self._ctx())
        with self.assertRaises(Exception):
            serializer.validate_parent(b)

    def test_autre_societe_rejetee_par_le_serializer(self):
        other = Company.objects.create(nom='Autre XSAL9 S', slug='xsal9-s-autre')
        mere_autre = Client.objects.create(company=other, nom='Mère autre')
        fille = Client.objects.create(company=self.company, nom='Fille')
        serializer = ClientSerializer(instance=fille, context=self._ctx())
        with self.assertRaises(Exception):
            serializer.validate_parent(mere_autre)

    def test_valeur_valide_acceptee(self):
        mere = Client.objects.create(company=self.company, nom='Mère valide')
        fille = Client.objects.create(company=self.company, nom='Fille valide')
        serializer = ClientSerializer(instance=fille, context=self._ctx())
        self.assertEqual(serializer.validate_parent(mere), mere)


class ConsolidationClientTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL9 Consolidation', slug='taqinor-xsal9-consol')

    def _devis(self, client, total_lignes_ttc):
        from apps.ventes.models import LigneDevis
        from apps.stock.models import Produit
        devis = Devis.objects.create(
            company=self.company, client=client, reference=f'D-{client.id}-{total_lignes_ttc}')
        produit = Produit.objects.create(
            company=self.company, nom=f'Produit {client.id}',
            prix_vente=total_lignes_ttc, prix_achat=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=1, prix_unitaire=total_lignes_ttc)
        return devis

    def test_sans_filiale_rollup_degrade_a_ses_propres_chiffres(self):
        mere = Client.objects.create(company=self.company, nom='Mère seule')
        self._devis(mere, Decimal('1000'))
        rollup = consolidation_client(mere)
        self.assertEqual(rollup['filiales'], [])
        self.assertGreater(rollup['ca_devis_total'], Decimal('0'))

    def test_deux_filiales_montrent_ca_consolide(self):
        mere = Client.objects.create(company=self.company, nom='Holding')
        f1 = Client.objects.create(company=self.company, nom='Ferme 1', parent=mere)
        f2 = Client.objects.create(company=self.company, nom='Ferme 2', parent=mere)
        devis_mere = self._devis(mere, Decimal('1000'))
        devis_f1 = self._devis(f1, Decimal('2000'))
        devis_f2 = self._devis(f2, Decimal('3000'))
        attendu = devis_mere.total_ttc + devis_f1.total_ttc + devis_f2.total_ttc
        rollup = consolidation_client(mere)
        self.assertEqual(len(rollup['filiales']), 2)
        self.assertEqual(rollup['ca_devis_total'], attendu)
        self.assertEqual(rollup['nb_devis_total'], 3)

    def test_filiale_de_filiale_incluse_recursivement(self):
        mere = Client.objects.create(company=self.company, nom='Holding R')
        f1 = Client.objects.create(company=self.company, nom='Fille R', parent=mere)
        petite_fille = Client.objects.create(
            company=self.company, nom='Petite-fille R', parent=f1)
        devis_pf = self._devis(petite_fille, Decimal('500'))
        rollup = consolidation_client(mere)
        self.assertEqual(len(rollup['filiales']), 2)
        self.assertEqual(rollup['ca_devis_total'], devis_pf.total_ttc)

    def test_jamais_de_fuite_cross_societe(self):
        other = Company.objects.create(nom='Autre XSAL9 C', slug='xsal9-c-autre')
        mere = Client.objects.create(company=self.company, nom='Holding isole')
        client_autre = Client.objects.create(company=other, nom='Client autre societe')
        # Pas de lien parent possible cross-société (garde clean()), mais on
        # vérifie surtout que le sélecteur ventes ne mélange jamais les
        # sociétés même si on l'appelait avec des ids d'une autre société.
        from apps.ventes.selectors import ca_devis_factures_par_clients
        self._devis(client_autre, Decimal('999999'))
        result = ca_devis_factures_par_clients(self.company, [client_autre.id])
        self.assertEqual(result, {})
        rollup = consolidation_client(mere)
        self.assertEqual(rollup['ca_devis_total'], Decimal('0'))


class ConsolidationEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL9 Endpoint', slug='taqinor-xsal9-endpoint')
        self.user = User.objects.create_user(
            username='xsal9_endpoint', password='x', company=self.company,
            role_legacy='admin')

    def test_endpoint_renvoie_le_rollup(self):
        mere = Client.objects.create(company=self.company, nom='Holding E')
        Client.objects.create(company=self.company, nom='Filiale E', parent=mere)
        resp = auth(self.user).get(f'/api/django/crm/clients/{mere.id}/consolidation/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['filiales']), 1)
        self.assertIn('ca_devis_total', resp.data)

    def test_endpoint_isole_par_societe(self):
        other = Company.objects.create(nom='Autre XSAL9 E', slug='xsal9-e-autre')
        client_autre = Client.objects.create(company=other, nom='Client autre E')
        resp = auth(self.user).get(
            f'/api/django/crm/clients/{client_autre.id}/consolidation/')
        self.assertEqual(resp.status_code, 404)
