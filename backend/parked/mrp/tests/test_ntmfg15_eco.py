"""NTMFG15 — PLM léger : versions produit + Ordres de Modification (ECO)
avec effectivité.

Critère : un ECO approuvé avec effectivité future s'applique automatiquement
à la date dite, les OF en cours ne sont jamais affectés rétroactivement,
rejet n'applique rien."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OrdreFabrication, OrdreModification
from apps.mrp.services import (
    appliquer_eco, approuver_eco, confirmer_of, rejeter_eco,
    sweep_ecos_effectivite,
)
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class EcoGammeTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-eco-1', 'MRP ECO 1')
        self.produit = make_produit(self.company)
        self.gamme_v1 = Gamme.objects.create(
            company=self.company, nom='Gamme v1', produit=self.produit,
            version=1, actif=True)
        self.gamme_v2 = Gamme.objects.create(
            company=self.company, nom='Gamme v2', produit=self.produit,
            version=2, actif=False)

    def test_approbation_sans_effectivite_applique_immediatement(self):
        eco = OrdreModification.objects.create(
            company=self.company, produit=self.produit, type_eco='gamme',
            changements={'gamme_id': self.gamme_v2.id})
        approuver_eco(eco)
        eco.refresh_from_db()
        self.assertEqual(eco.statut, 'applique')
        self.gamme_v1.refresh_from_db()
        self.gamme_v2.refresh_from_db()
        self.assertFalse(self.gamme_v1.actif)
        self.assertTrue(self.gamme_v2.actif)

    def test_approbation_avec_effectivite_future_reste_en_attente(self):
        demain = timezone.localdate() + timedelta(days=5)
        eco = OrdreModification.objects.create(
            company=self.company, produit=self.produit, type_eco='gamme',
            date_effectivite=demain, changements={'gamme_id': self.gamme_v2.id})
        approuver_eco(eco)
        eco.refresh_from_db()
        self.assertEqual(eco.statut, 'approuve')
        self.gamme_v2.refresh_from_db()
        self.assertFalse(self.gamme_v2.actif)

    def test_sweep_applique_a_la_date_atteinte(self):
        hier = timezone.localdate() - timedelta(days=1)
        eco = OrdreModification.objects.create(
            company=self.company, produit=self.produit, type_eco='gamme',
            statut='approuve', date_effectivite=hier,
            changements={'gamme_id': self.gamme_v2.id})
        appliques = sweep_ecos_effectivite(self.company)
        self.assertEqual(len(appliques), 1)
        eco.refresh_from_db()
        self.assertEqual(eco.statut, 'applique')
        self.gamme_v2.refresh_from_db()
        self.assertTrue(self.gamme_v2.actif)

    def test_sweep_isolation_tenant(self):
        autre_company = make_company('mrp-eco-2', 'MRP ECO 2')
        hier = timezone.localdate() - timedelta(days=1)
        OrdreModification.objects.create(
            company=self.company, produit=self.produit, type_eco='gamme',
            statut='approuve', date_effectivite=hier,
            changements={'gamme_id': self.gamme_v2.id})
        appliques = sweep_ecos_effectivite(autre_company)
        self.assertEqual(appliques, [])

    def test_rejet_n_applique_rien(self):
        eco = OrdreModification.objects.create(
            company=self.company, produit=self.produit, type_eco='gamme',
            statut='en_revue', changements={'gamme_id': self.gamme_v2.id})
        rejeter_eco(eco)
        eco.refresh_from_db()
        self.assertEqual(eco.statut, 'rejete')
        self.gamme_v2.refresh_from_db()
        self.assertFalse(self.gamme_v2.actif)

    def test_applique_deux_fois_est_idempotent(self):
        eco = OrdreModification.objects.create(
            company=self.company, produit=self.produit, type_eco='gamme',
            statut='approuve', changements={'gamme_id': self.gamme_v2.id})
        appliquer_eco(eco)
        premiere = eco.applique_le
        appliquer_eco(eco)  # Rejoué -> aucun effet supplémentaire.
        eco.refresh_from_db()
        self.assertEqual(eco.applique_le, premiere)

    def test_rejet_d_un_eco_deja_applique_refuse(self):
        eco = OrdreModification.objects.create(
            company=self.company, produit=self.produit, type_eco='gamme',
            statut='approuve', changements={'gamme_id': self.gamme_v2.id})
        appliquer_eco(eco)
        eco.refresh_from_db()
        with self.assertRaises(ValueError):
            rejeter_eco(eco)

    def test_of_lance_garde_sa_gamme_figee(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1,
            gamme=self.gamme_v1)
        confirmer_of(of)
        of.refresh_from_db()
        self.assertEqual(of.gamme_id, self.gamme_v1.id)

        eco = OrdreModification.objects.create(
            company=self.company, produit=self.produit, type_eco='gamme',
            statut='approuve', changements={'gamme_id': self.gamme_v2.id})
        appliquer_eco(eco)
        of.refresh_from_db()
        # L'OF garde sa gamme d'origine — aucune rétroactivité.
        self.assertEqual(of.gamme_id, self.gamme_v1.id)


class EcoApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-eco-api-1', 'MRP ECO API 1')
        self.user = make_user(self.company, 'mrp-eco-api-user')
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme API', produit=self.produit)

    def test_creation_pose_demandeur_serveur(self):
        resp = self.api.post('/api/django/mrp/ecos/', {
            'produit': self.produit.id, 'type_eco': 'gamme',
            'changements': {'gamme_id': self.gamme.id},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['demandeur'], self.user.id)
        self.assertEqual(resp.data['statut'], 'brouillon')

    def test_approuver_endpoint(self):
        resp = self.api.post('/api/django/mrp/ecos/', {
            'produit': self.produit.id, 'type_eco': 'gamme',
            'changements': {'gamme_id': self.gamme.id},
        }, format='json')
        eco_id = resp.data['id']
        resp = self.api.post(f'/api/django/mrp/ecos/{eco_id}/approuver/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'applique')
