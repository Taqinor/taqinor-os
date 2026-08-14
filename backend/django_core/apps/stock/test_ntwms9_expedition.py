"""NTWMS9 — expédition multi-transporteurs, étiquette réelle GATED.

Vérifie le point le plus important de la tâche : SANS intégration configurée,
rien n'appelle l'extérieur et l'expédition reste possible (connecteur NoOp,
étiquette interne) ; AVEC une intégration configurée mais SANS secret, le
connecteur reste ignoré (gating) ; AVEC secret, il est proposé.

Le rendu PDF réel (WeasyPrint) et le dépôt MinIO sont hors périmètre de ces
tests : le connecteur est mocké pour rester hermétique et rapide.

Run :
    python manage.py test apps.stock.test_ntwms9_expedition -v 2
"""
import os
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import ExpeditionTransporteur, Produit
from apps.stock.providers import (
    NoOpProvider, TransportProvider, provider_pour_societe,
    providers_configures,
)
from apps.stock.services import (
    ajouter_ligne_unite_logistique, creer_expedition_transporteur,
    creer_unite_logistique, generer_etiquette_expedition,
    sceller_unite_logistique,
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


class Ntwms9Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms9-co', 'NTWMS9 Co')
        self.autre = make_company('ntwms9-autre', 'NTWMS9 Autre')
        self.admin = User.objects.create_user(
            username='ntwms9_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 8kW', sku='OND8-NTWMS9',
            prix_achat=Decimal('700'), prix_vente=Decimal('1000'),
            quantite_stock=10)
        self.colis = creer_unite_logistique(company=self.company)
        ajouter_ligne_unite_logistique(
            company=self.company, unite=self.colis, produit=self.produit,
            quantite=2)
        self.api = auth(self.admin)

    def _colis_scelle(self):
        sceller_unite_logistique(unite=self.colis, user=self.admin)
        self.colis.refresh_from_db()
        return self.colis


class TestGatingProviders(Ntwms9Base):
    def test_sans_integration_seul_le_noop(self):
        codes = [code for code, _ in providers_configures(self.company)]
        self.assertEqual(codes, ['aucun'])

    def test_noop_toujours_configure_et_sans_tarif(self):
        provider = NoOpProvider()
        self.assertTrue(provider.is_configured())
        # Aucun tarif inventé : le comparateur NTWMS10 retombera sur le
        # tarif_base du référentiel interne.
        self.assertIsNone(provider.estimer_tarif(poids_kg=12))

    def test_integration_sans_secret_reste_ignoree(self):
        """GATING : une intégration déclarée mais dont la clé d'API est absente
        de l'environnement ne doit JAMAIS être proposée (ni appelée)."""
        from core.models import IntegrationConfig

        IntegrationConfig.objects.create(
            company=self.company, integration_type='transport',
            provider='faux_transporteur', actif=True,
            secret_ref='NTWMS9_CLE_ABSENTE')
        self.assertIsNone(os.environ.get('NTWMS9_CLE_ABSENTE'))
        codes = [code for code, _ in providers_configures(self.company)]
        self.assertEqual(codes, ['aucun'])

    def test_provider_inconnu_retombe_sur_le_noop(self):
        provider = provider_pour_societe(self.company, 'dhl')
        self.assertIsInstance(provider, NoOpProvider)

    def test_provider_gated_visible_quand_le_secret_existe(self):
        from core.integrations import register_provider
        from core.models import IntegrationConfig

        @register_provider
        class ProviderTest(TransportProvider):
            code = 'ntwms9_test'
            label = 'Transporteur de test'

            def creer_expedition(self, unite):
                return f'TEST-{unite.sscc}', b''

            def estimer_tarif(self, poids_kg=None, dimensions='',
                              destination=''):
                return {'cout': Decimal('42.00'), 'delai_jours': 2,
                        'devise': 'MAD'}

        IntegrationConfig.objects.create(
            company=self.company, integration_type='transport',
            provider='ntwms9_test', actif=True,
            secret_ref='NTWMS9_CLE_TEST')
        with mock.patch.dict(os.environ, {'NTWMS9_CLE_TEST': 'secret'}):
            codes = [code for code, _ in providers_configures(self.company)]
        self.assertIn('ntwms9_test', codes)


class TestCreationExpedition(Ntwms9Base):
    def test_unite_non_scellee_refusee(self):
        with self.assertRaises(ValueError):
            creer_expedition_transporteur(
                company=self.company, unite=self.colis)

    def test_creation_sur_unite_scellee(self):
        colis = self._colis_scelle()
        expedition = creer_expedition_transporteur(
            company=self.company, unite=colis, destination='Casablanca')
        self.assertEqual(expedition.statut,
                         ExpeditionTransporteur.Statut.BROUILLON)
        self.assertEqual(expedition.transporteur_provider, 'aucun')

    def test_unite_d_une_autre_societe_refusee(self):
        etranger = creer_unite_logistique(company=self.autre)
        with self.assertRaises(ValueError):
            creer_expedition_transporteur(
                company=self.company, unite=etranger)

    def test_provider_inconnu_refuse(self):
        colis = self._colis_scelle()
        with self.assertRaises(ValueError):
            creer_expedition_transporteur(
                company=self.company, unite=colis, provider_code='fedex')


class TestGenerationEtiquette(Ntwms9Base):
    def _expedition(self):
        return creer_expedition_transporteur(
            company=self.company, unite=self._colis_scelle())

    @mock.patch.object(NoOpProvider, 'creer_expedition')
    def test_etiquette_interne_sans_appel_externe(self, creer_mock):
        expedition = self._expedition()
        creer_mock.return_value = (f'INT-{expedition.unite_logistique.sscc}',
                                   b'')
        generer_etiquette_expedition(expedition=expedition, user=self.admin)
        expedition.refresh_from_db()
        self.assertEqual(expedition.statut,
                         ExpeditionTransporteur.Statut.ETIQUETTE)
        self.assertTrue(expedition.numero_suivi.startswith('INT-'))
        self.assertIsNotNone(expedition.date_expedition)
        self.assertEqual(creer_mock.call_count, 1)

    @mock.patch.object(NoOpProvider, 'creer_expedition')
    def test_generation_idempotente(self, creer_mock):
        expedition = self._expedition()
        creer_mock.return_value = ('INT-XYZ', b'')
        generer_etiquette_expedition(expedition=expedition, user=self.admin)
        # Sans octets d'étiquette, la clé reste vide : on la simule pour
        # vérifier la garde d'idempotence sur (numéro + clé).
        expedition.etiquette_pdf_key = 'stock/1/etiquettes/abc.pdf'
        expedition.save(update_fields=['etiquette_pdf_key'])
        generer_etiquette_expedition(expedition=expedition, user=self.admin)
        self.assertEqual(creer_mock.call_count, 1)

    @mock.patch.object(NoOpProvider, 'creer_expedition')
    def test_expedition_annulee_refusee(self, creer_mock):
        expedition = self._expedition()
        expedition.statut = ExpeditionTransporteur.Statut.ANNULE
        expedition.save(update_fields=['statut'])
        with self.assertRaises(ValueError):
            generer_etiquette_expedition(expedition=expedition)
        self.assertEqual(creer_mock.call_count, 0)


class TestEndpointsExpedition(Ntwms9Base):
    def test_creation_et_tracking(self):
        colis = self._colis_scelle()
        resp = self.api.post('/api/django/stock/expeditions/', {
            'unite_logistique': colis.id, 'destination': 'Rabat',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['sscc'], colis.sscc)
        self.assertFalse(resp.data['a_une_etiquette'])

        resp = self.api.get(
            f"/api/django/stock/expeditions/{resp.data['id']}/tracking/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], 'brouillon')
        # La clé MinIO n'est JAMAIS exposée.
        self.assertNotIn('etiquette_pdf_key', resp.data)

    def test_unite_non_scellee_400(self):
        resp = self.api.post('/api/django/stock/expeditions/', {
            'unite_logistique': self.colis.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe(self):
        colis = self._colis_scelle()
        expedition = creer_expedition_transporteur(
            company=self.company, unite=colis)
        intrus = User.objects.create_user(
            username='ntwms9_intrus', password='x', role_legacy='admin',
            company=self.autre)
        resp = auth(intrus).get(
            f'/api/django/stock/expeditions/{expedition.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_cle_minio_jamais_serialisee(self):
        colis = self._colis_scelle()
        expedition = creer_expedition_transporteur(
            company=self.company, unite=colis)
        expedition.etiquette_pdf_key = 'stock/1/etiquettes/secret.pdf'
        expedition.save(update_fields=['etiquette_pdf_key'])
        resp = self.api.get(
            f'/api/django/stock/expeditions/{expedition.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('etiquette_pdf_key', resp.data)
        self.assertTrue(resp.data['a_une_etiquette'])
