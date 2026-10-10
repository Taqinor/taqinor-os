"""AUD506 — ``BonCommande.statut`` writable en PATCH, zéro ``perform_update`` :
LIVRE atteignable sans réservation stock ni preuve de livraison.

LE TROU FERMÉ. ``BonCommandeSerializer`` ne verrouillait pas ``statut``
(``fields = '__all__'`` sans ``statut`` en ``read_only_fields``) et
``BonCommandeViewSet`` n'a AUCUN ``perform_update`` (comportement DRF par
défaut : le PATCH écrit tel quel). ``confirmer`` crée la réservation stock,
``marquer_livre`` la consomme et capture ``pv_livraison`` (FG51) — aucune des
deux n'était appelée par un PATCH brut : un BC pouvait passer directement
``en_attente`` → ``livre`` sans qu'aucun mouvement de stock n'existe (même
famille que AUD322).

Ce module prouve : un PATCH {statut: 'livre'} est désormais refusé (le champ
est ignoré, DRF répond 200 sans rien changer — comportement identique aux
autres champs read-only du même sérialiseur, cf. FG51 pv_livraison/
date_livraison_reelle) et le statut ne bouge QUE via les actions dédiées.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_aud506_bon_commande_statut_dedie"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit, MouvementStock
from apps.ventes.models import BonCommande, Devis, LigneDevis

User = get_user_model()


def _company():
    return Company.objects.get_or_create(
        slug='aud506-co', defaults={'nom': 'AUD506 Co'})[0]


class PatchStatutIgnoreSansMouvementStock(TestCase):
    """Le PATCH brut n'a plus aucun effet sur le statut ni sur le stock."""

    def setUp(self):
        self.company = _company()
        self.user = User.objects.create_user(
            username='aud506_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD506',
            telephone='+212600000506')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau AUD506', sku='AUD506-P',
            prix_vente=Decimal('1000'), quantite_stock=20,
            tva=Decimal('20.00'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-AUD506-0001',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Panneau',
            quantite=Decimal('5'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        self.bc = BonCommande.objects.create(
            company=self.company, reference='BC-AUD506-0001',
            client=self.client_obj, devis=self.devis,
            statut=BonCommande.Statut.EN_ATTENTE)

    def test_patch_statut_livre_est_ignore(self):
        """Avant le fix ce PATCH faisait passer le BC à `livre` (200) sans
        aucune réservation ni mouvement de stock, ni `pv_livraison` — le
        prouver ici en confirmant l'état APRÈS fix : le champ est ignoré."""
        resp = self.api.patch(
            f'/api/django/ventes/bons-commande/{self.bc.id}/',
            {'statut': 'livre'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.EN_ATTENTE)
        self.assertIsNone(self.bc.date_livraison_reelle)
        self.assertFalse(self.bc.has_proof_of_delivery)
        self.assertEqual(MouvementStock.objects.count(), 0)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 20)

    def test_patch_statut_confirme_est_ignore(self):
        resp = self.api.patch(
            f'/api/django/ventes/bons-commande/{self.bc.id}/',
            {'statut': 'confirme'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.EN_ATTENTE)

    def test_le_chemin_dedie_confirmer_fonctionne_toujours(self):
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/confirmer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.CONFIRME)

    def test_le_chemin_dedie_marquer_livre_fonctionne_toujours(self):
        self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/confirmer/')
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/marquer-livre/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.LIVRE)
        self.assertIsNotNone(self.bc.date_livraison_reelle)
        self.assertEqual(MouvementStock.objects.count(), 1)


class ConvertirEnBcTests(TestCase):
    """AMET6 (C-AMET-008) — « Convertir en BC » crée le BC par LA porte
    unique `facturation_ops.creer_bon_commande` (AMET5) : même contrôle
    « BC existant », même message, même événement, émis une seule fois."""

    def setUp(self):
        self.company = _company()
        self.user = User.objects.create_user(
            username='amet6_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AMET6',
            telephone='+212600000606')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-AMET6-0001',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'))

    def test_convertir_en_bc_passe_par_creer_bon_commande(self):
        from unittest import mock
        from apps.ventes.domain import facturation_ops
        from core.events import bon_commande_cree
        recus = []

        def _recepteur(sender, instance=None, **kwargs):
            recus.append(instance.pk)
        bon_commande_cree.connect(_recepteur, weak=False)
        self.addCleanup(bon_commande_cree.disconnect, _recepteur)
        url = f'/api/django/ventes/devis/{self.devis.id}/convertir-bc/'
        with mock.patch.object(
                facturation_ops, 'creer_bon_commande',
                wraps=facturation_ops.creer_bon_commande) as porte:
            r = self.api.post(url)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(porte.call_count, 1)
        bc = BonCommande.objects.get(devis=self.devis)
        self.assertEqual(r.data['reference'], bc.reference)
        self.assertEqual(bc.company_id, self.company.id)
        self.assertEqual(bc.statut, BonCommande.Statut.EN_ATTENTE)
        self.assertEqual(recus, [bc.pk])  # événement émis une seule fois

        # Doublon : même message par les deux portes, aucun second BC
        # ni second événement.
        message = facturation_ops.MESSAGE_BC_EXISTANT
        r2 = self.api.post(url)
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertEqual(r2.data['detail'], message)
        r3 = self.api.post(
            '/api/django/ventes/bons-commande/',
            {'client': self.client_obj.id, 'devis': self.devis.id},
            format='json')
        self.assertEqual(r3.status_code, 400, r3.data)
        self.assertIn(message, str(r3.data))
        self.assertEqual(BonCommande.objects.filter(devis=self.devis).count(),
                         1)
        self.assertEqual(recus, [bc.pk])
