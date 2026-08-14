"""NTWMS10 — comparateur de tarifs transporteurs (rate shopping).

Critère d'acceptation testé : avec au moins un connecteur GATED actif,
l'utilisateur voit un comparatif de coûts avant de sceller son choix. Le point
de non-régression est aussi vérifié : SANS connecteur configuré, la réponse est
exactement le référentiel interne (`Transporteur.tarif_base`), jamais vide,
jamais une erreur, jamais un appel externe.

Run :
    python manage.py test apps.stock.test_ntwms10_rate_shopping -v 2
"""
import os
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit
from apps.stock.providers import TransportProvider
from apps.stock.selectors import comparer_tarifs_transporteurs
from apps.stock.services import (
    ajouter_ligne_unite_logistique, creer_unite_logistique,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms10Base(TestCase):
    def setUp(self):
        from apps.installations.models import Transporteur

        self.company = make_company('ntwms10-co', 'NTWMS10 Co')
        self.autre = make_company('ntwms10-autre', 'NTWMS10 Autre')
        self.admin = User.objects.create_user(
            username='ntwms10_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 10kWh', sku='BAT10-NTWMS10',
            prix_achat=Decimal('500'), prix_vente=Decimal('800'),
            quantite_stock=5)
        self.colis = creer_unite_logistique(
            company=self.company, poids_kg=Decimal('18.500'),
            dimensions='60 × 40 × 30')
        ajouter_ligne_unite_logistique(
            company=self.company, unite=self.colis, produit=self.produit,
            quantite=1)
        self.cher = Transporteur.objects.create(
            company=self.company, nom='Transporteur cher',
            tarif_base=Decimal('300.00'))
        self.economique = Transporteur.objects.create(
            company=self.company, nom='Transporteur économique',
            tarif_base=Decimal('120.00'))
        Transporteur.objects.create(
            company=self.autre, nom='Transporteur étranger',
            tarif_base=Decimal('1.00'))
        self.api = auth(self.admin)


class TestReplitGracieux(Ntwms10Base):
    def test_sans_connecteur_le_referentiel_interne_suffit(self):
        offres = comparer_tarifs_transporteurs(self.colis)
        self.assertEqual([o['source'] for o in offres], ['interne', 'interne'])
        # Trié du moins cher au plus cher.
        self.assertEqual(offres[0]['libelle'], 'Transporteur économique')
        self.assertEqual(offres[0]['cout'], Decimal('120.00'))

    def test_transporteur_d_une_autre_societe_absent(self):
        libelles = [o['libelle'] for o in comparer_tarifs_transporteurs(
            self.colis)]
        self.assertNotIn('Transporteur étranger', libelles)

    def test_transporteur_inactif_exclu(self):
        self.cher.active = False
        self.cher.save(update_fields=['active'])
        libelles = [o['libelle'] for o in comparer_tarifs_transporteurs(
            self.colis)]
        self.assertEqual(libelles, ['Transporteur économique'])

    def test_unite_absente(self):
        self.assertEqual(comparer_tarifs_transporteurs(None), [])


class TestConnecteurGate(Ntwms10Base):
    def setUp(self):
        super().setUp()
        from core.integrations import register_provider

        @register_provider
        class ProviderCotant(TransportProvider):
            code = 'ntwms10_cotant'
            label = 'Express Test'
            # Le connecteur reçoit le poids RÉEL du colis : on le capture pour
            # prouver qu'il n'est pas appelé « à vide ».
            poids_recu = []

            def creer_expedition(self, unite):
                return f'EXP-{unite.sscc}', b''

            def estimer_tarif(self, poids_kg=None, dimensions='',
                              destination=''):
                ProviderCotant.poids_recu.append(poids_kg)
                return {'cout': Decimal('75.00'), 'delai_jours': 1,
                        'devise': 'MAD'}

        self.provider_cls = ProviderCotant
        ProviderCotant.poids_recu = []

    def _configurer(self, secret_present=True):
        from core.models import IntegrationConfig
        IntegrationConfig.objects.create(
            company=self.company, integration_type='transport',
            provider='ntwms10_cotant', actif=True,
            secret_ref='NTWMS10_CLE')
        env = {'NTWMS10_CLE': 'secret'} if secret_present else {}
        return mock.patch.dict(os.environ, env, clear=not secret_present)

    def test_connecteur_gate_apparait_en_tete_du_comparatif(self):
        with self._configurer():
            offres = comparer_tarifs_transporteurs(
                self.colis, destination='Marrakech')
        self.assertEqual(offres[0]['source'], 'provider')
        self.assertEqual(offres[0]['libelle'], 'Express Test')
        self.assertEqual(offres[0]['cout'], Decimal('75.00'))
        self.assertEqual(offres[0]['delai_jours'], 1)
        # Le référentiel interne reste présent : aucune régression.
        self.assertIn('interne', [o['source'] for o in offres])

    def test_le_connecteur_recoit_le_poids_reel(self):
        with self._configurer():
            comparer_tarifs_transporteurs(self.colis)
        self.assertEqual(self.provider_cls.poids_recu, [Decimal('18.500')])

    def test_sans_secret_le_connecteur_n_est_jamais_appele(self):
        with self._configurer(secret_present=False):
            offres = comparer_tarifs_transporteurs(self.colis)
        self.assertEqual(self.provider_cls.poids_recu, [])
        self.assertEqual({o['source'] for o in offres}, {'interne'})


class TestEndpointTarifs(Ntwms10Base):
    def test_endpoint_renvoie_le_comparatif(self):
        resp = self.api.get(
            '/api/django/stock/expeditions/tarifs/'
            f'?unite_logistique={self.colis.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['offres']), 2)
        self.assertEqual(resp.data['offres'][0]['cout'], Decimal('120.00'))

    def test_unite_inconnue_400(self):
        resp = self.api.get(
            '/api/django/stock/expeditions/tarifs/?unite_logistique=999999')
        self.assertEqual(resp.status_code, 400)

    def test_unite_d_une_autre_societe_400(self):
        etranger = creer_unite_logistique(company=self.autre)
        resp = self.api.get(
            '/api/django/stock/expeditions/tarifs/'
            f'?unite_logistique={etranger.id}')
        self.assertEqual(resp.status_code, 400)
