"""ALEA17 — tous les DecimalField de ``Lead`` normalisés côté serveur.

Rejoue la sonde V3 LFICHE-1 (et le run Playwright du 07/10/2026, lead 113) :
un GPS à 7 décimales ou une facture « 450,555 » rendaient 400
``max_decimal_places`` et l'autosave bouclait. Règle fondateur « normaliser
plutôt que refuser » (08/09).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import DecimalField
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead, LeadActivity
from apps.crm.serializers import LeadSerializer
from authentication.models import Company

User = get_user_model()


class LeadDecimalNormaliseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ALEA17', slug='alea17')
        self.user = User.objects.create_user(
            username='alea17_user', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='ALEA17')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.url = f'/api/django/crm/leads/{self.lead.id}/'

    def test_gps_7_decimales_arrondi(self):
        resp = self.api.patch(self.url, {'gps_lat': '33.5731104',
                                         'gps_lng': '-7.5898434'},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.gps_lat, Decimal('33.573110'))
        self.assertEqual(self.lead.gps_lng, Decimal('-7.589843'))

    def test_facture_virgule_trois_decimales(self):
        resp = self.api.patch(self.url, {'facture_hiver': '450,555'},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.facture_hiver, Decimal('450.56'))

    def test_non_numerique_refuse(self):
        resp = self.api.patch(self.url, {'gps_lat': 'abc'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('gps_lat', resp.data)
        hors_bornes = self.api.patch(self.url, {'gps_lat': '95.1234567'},
                                     format='json')
        self.assertEqual(hors_bornes.status_code, 400, hors_bornes.data)
        self.assertIn('gps_lat', hors_bornes.data)

    def test_renvoyer_le_get_ne_derive_pas(self):
        """Persistance : GET puis PATCH du même corps sans toucher → 200,
        objet identique, aucune ligne de chatter."""
        self.api.patch(self.url, {'gps_lat': '33.5731104',
                                  'facture_hiver': '450,555'}, format='json')
        lu = self.api.get(self.url).data
        avant = LeadActivity.objects.filter(lead=self.lead).count()
        resp = self.api.patch(self.url, {'gps_lat': lu['gps_lat'],
                                         'facture_hiver': lu['facture_hiver']},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.gps_lat, Decimal('33.573110'))
        self.assertEqual(self.lead.facture_hiver, Decimal('450.56'))
        self.assertEqual(LeadActivity.objects.filter(lead=self.lead).count(),
                         avant)


def _valeur_avec_une_decimale_de_trop(champ_modele):
    """Une valeur à ``decimal_places + 1`` décimales, dans les bornes du
    champ : 1 (ou la borne basse si elle est plus haute) + 4·10^-(dp+1), qui
    s'arrondit à cette base — 1 plutôt que 0 car certains champs exigent une
    valeur strictement positive (``cos_phi``)."""
    dp = champ_modele.decimal_places
    entiers = (champ_modele.max_digits or 0) - dp
    base = Decimal(1) if entiers >= 1 else Decimal(0)
    for validateur in champ_modele.validators:
        borne = getattr(validateur, 'limit_value', None)
        if type(validateur).__name__ == 'MinValueValidator' and borne is not None:
            base = max(base, Decimal(str(borne)))
    return str(base + Decimal(4).scaleb(-(dp + 1)))


class LeadDecimalGardeTests(SimpleTestCase):
    def test_tous_les_decimalfields_acceptent_une_decimale_de_trop(self):
        champs = LeadSerializer().fields
        vus = 0
        for champ_modele in Lead._meta.concrete_fields:
            if not isinstance(champ_modele, DecimalField):
                continue
            champ = champs.get(champ_modele.name)
            if champ is None or champ.read_only:
                continue
            vus += 1
            valeur = _valeur_avec_une_decimale_de_trop(champ_modele)
            with self.subTest(champ=champ_modele.name, valeur=valeur):
                try:
                    champ.run_validation(valeur)
                except Exception as exc:  # noqa: BLE001 — on nomme le champ
                    self.fail(f'Lead.{champ_modele.name} refuse {valeur} : '
                              f'{exc}')
        self.assertGreater(vus, 5)  # anti-faux-vert
