"""AGNR11 — le profil société sert ``bareme_effectif`` du contrat AGNR3."""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models_tariff import DEFAULT_RESIDENTIAL_TIERS, TariffSettings

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).parent / 'contract_samples' / 'bareme_effectif.json')
    .read_text(encoding='utf-8'))


def _client(slug):
    company = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})[0]
    user = User.objects.create_user(
        username=f'{slug}_admin', password='x', role_legacy='admin',
        company=company)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return company, api


def _lire(api):
    reponse = api.get('/api/django/parametres/')
    assert reponse.status_code == 200, reponse.content
    return json.loads(json.dumps(reponse.data['bareme_effectif']))


class BaremeEffectifProfilTests(TestCase):
    def test_profil_sert_le_bareme_du_contrat(self):
        societe, api_societe = _client('agnr11-a')
        tiers = [dict(t) for t in DEFAULT_RESIDENTIAL_TIERS]
        tiers[-1]['prix_kwh_ttc'] = '1.5958'
        reglages = TariffSettings.get(company=societe)
        reglages.residential_tiers = tiers
        reglages.redevance_compteur_mad_mois = Decimal('45')
        reglages.save()
        _, api_nationale = _client('agnr11-b')

        self.assertEqual(_lire(api_societe),
                         CONTRAT['exemple']['bareme_effectif'])
        self.assertEqual(_lire(api_nationale),
                         CONTRAT['exemple_national']['bareme_effectif'])

    def test_une_societe_ne_lit_pas_le_reglage_d_une_autre(self):
        societe, _ = _client('agnr11-c')
        reglages = TariffSettings.get(company=societe)
        reglages.redevance_compteur_mad_mois = Decimal('45')
        reglages.save()
        _, api_autre = _client('agnr11-d')
        self.assertEqual(_lire(api_autre)['source'], 'national')

    def test_redevance_seule_est_une_source_societe(self):
        societe, api = _client('agnr11-e')
        reglages = TariffSettings.get(company=societe)
        reglages.redevance_compteur_mad_mois = Decimal('45')
        reglages.save()
        lu = _lire(api)
        self.assertEqual(lu['source'], 'societe')
        self.assertEqual(lu['redevance_compteur_mad_mois'], 45)
