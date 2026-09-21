"""NTMFG38 — Chatter (`records.Activity`/`Comment`) sur l'Ordre de
Fabrication.

Critère : chaque transition de statut d'OF crée une entrée d'activité
horodatée+utilisateur, une note manuelle est ajoutable depuis l'écran détail,
visible dans l'ordre chronologique."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.services import annuler_of, confirmer_of
from apps.records.models import Activity
from apps.records.services import chatter_qs
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class ChatterOfServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg38-1', 'MRP NTMFG38 1')
        self.user = make_user(self.company, 'mrp-ntmfg38-user')
        self.produit = make_produit(self.company)

    def test_confirmer_pose_une_entree_chatter(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1)
        confirmer_of(of, user=self.user)
        entries = list(chatter_qs(of))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].kind, Activity.Kind.MODIFICATION)
        self.assertEqual(entries[0].old_value, 'brouillon')
        self.assertEqual(entries[0].new_value, 'planifie')
        self.assertEqual(entries[0].created_by_id, self.user.id)

    def test_confirmer_idempotent_ne_duplique_pas_le_chatter(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1)
        confirmer_of(of, user=self.user)
        confirmer_of(of, user=self.user)  # rappel — déjà planifié.
        self.assertEqual(chatter_qs(of).count(), 1)

    def test_annuler_pose_une_entree_chatter(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1)
        confirmer_of(of, user=self.user)
        annuler_of(of, user=self.user, motif='Test')
        entries = list(chatter_qs(of))
        self.assertEqual(len(entries), 2)  # confirmer + annuler.
        self.assertEqual(entries[0].new_value, 'annule')  # plus récent d'abord.

    def test_note_manuelle_visible_dans_l_ordre_chronologique(self):
        from apps.records.services import log_note

        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1)
        confirmer_of(of, user=self.user)
        log_note(of, self.user, 'Note manuelle')
        entries = list(chatter_qs(of))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].body, 'Note manuelle')  # plus récent d'abord.
        self.assertEqual(entries[1].kind, Activity.Kind.MODIFICATION)


class ChatterOfApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg38-api-1', 'MRP NTMFG38 API 1')
        self.responsable = make_user(
            self.company, 'mrp-ntmfg38-resp', role='responsable')
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-38', nom='Poste 38')
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme 38', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste, libelle='Op',
            temps_prepa_min=Decimal('1'), temps_unitaire_min=Decimal('1'))

    def test_endpoint_historique_et_noter(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1,
            gamme=self.gamme)
        api = auth(self.responsable)
        resp = api.post(f'/api/django/mrp/ordres-fabrication/{of.id}/confirmer/')
        self.assertEqual(resp.status_code, 200, resp.data)

        resp = api.get(f'/api/django/mrp/ordres-fabrication/{of.id}/chatter/historique/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

        resp = api.post(
            f'/api/django/mrp/ordres-fabrication/{of.id}/chatter/noter/',
            {'body': 'Note via API'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = api.get(f'/api/django/mrp/ordres-fabrication/{of.id}/chatter/historique/')
        self.assertEqual(len(resp.data), 2)

    def test_isolation_tenant_chatter(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1)
        autre_company = make_company('mrp-ntmfg38-api-2', 'MRP NTMFG38 API 2')
        autre_resp = make_user(
            autre_company, 'mrp-ntmfg38-autre-resp', role='responsable')
        resp = auth(autre_resp).get(
            f'/api/django/mrp/ordres-fabrication/{of.id}/chatter/historique/')
        self.assertEqual(resp.status_code, 404)
