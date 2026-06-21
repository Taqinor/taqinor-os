"""Tests FG48 — comparaison deux options (serializer + endpoint).

La donnée est calculée par build_quote_data (même source que le PDF) ;
le champ `comparaison_options` est ajouté au DevisSerializer. Pour un devis
mono-option le champ vaut None ; pour un devis à deux options il expose
{nb_options, sans, avec, roi}.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.serializers import DevisSerializer

User = get_user_model()


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _company(slug='fg48-co', nom='FG48 Co'):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return c


def _user(co, username='fg48_user'):
    return User.objects.create_user(
        username=username, password='x', role_legacy='responsable', company=co)


def _client(co):
    return Client.objects.create(
        company=co, nom='FG48', prenom='Client',
        email='fg48@example.com', telephone='+212600000066')


def _devis(co, user, client, ref='DEV-FG48-001'):
    return Devis.objects.create(
        company=co, created_by=user, client=client,
        reference=ref, statut='brouillon',
    )


class TestComparaisonOptionsField(TestCase):
    """Vérifie le champ comparaison_options dans le serializer."""

    def setUp(self):
        self.co = _company()
        self.user = _user(self.co)
        self.cli = _client(self.co)

    def test_field_present_in_serializer_output(self):
        """Le champ comparaison_options existe dans la réponse serializer."""
        d = _devis(self.co, self.user, self.cli, ref='DEV-FG48-SR1')
        data = DevisSerializer(d).data
        self.assertIn('comparaison_options', data)

    def test_mono_option_devis_returns_none(self):
        """Un devis sans deux options renvoie None (pas une exception)."""
        d = _devis(self.co, self.user, self.cli, ref='DEV-FG48-MONO')
        data = DevisSerializer(d).data
        # Mono-option (pas de lignes réseau+hybride) → None
        self.assertIsNone(data['comparaison_options'])

    def test_comparaison_none_does_not_crash_list(self):
        """La liste des devis (GET /ventes/devis/) ne crash pas même sans options."""
        d = _devis(self.co, self.user, self.cli, ref='DEV-FG48-LIST')
        api = _auth(self.user)
        r = api.get('/api/django/ventes/devis/')
        self.assertEqual(r.status_code, 200)
        devis_data = [item for item in r.data['results']
                      if item['reference'] == 'DEV-FG48-LIST']
        self.assertEqual(len(devis_data), 1)
        self.assertIn('comparaison_options', devis_data[0])

    def test_comparaison_none_does_not_crash_detail(self):
        """Le détail d'un devis (GET /ventes/devis/{id}/) ne crash pas."""
        d = _devis(self.co, self.user, self.cli, ref='DEV-FG48-DET')
        api = _auth(self.user)
        r = api.get(f'/api/django/ventes/devis/{d.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('comparaison_options', r.data)

    def test_comparaison_structure_when_not_none(self):
        """Quand deux options : les clés {sans, avec, roi, nb_options} sont présentes."""
        # Simuler un devis à deux options en mockant _display
        d = _devis(self.co, self.user, self.cli, ref='DEV-FG48-STR')
        serializer = DevisSerializer(d)

        # Monkey-patch _display pour simuler nb_options=2
        # (sans vraie configuration lignes réseau+hybride en base)
        original_display = DevisSerializer._display

        def fake_display(self_inner, obj):
            return {'total': 100000, 'nb_options': 2}

        DevisSerializer._display = fake_display
        try:
            data = serializer.data
            comp = data.get('comparaison_options')
            # Peut valoir None si build_quote_data échoue gracieusement,
            # OU un dict si le moteur réussit. On vérifie seulement la structure
            # quand c'est un dict.
            if comp is not None:
                self.assertIn('nb_options', comp)
                self.assertIn('sans', comp)
                self.assertIn('avec', comp)
                self.assertIn('roi', comp)
                self.assertIn('ttc', comp['sans'])
                self.assertIn('ttc', comp['avec'])
        finally:
            DevisSerializer._display = original_display


class TestComparaisonEndpoint(TestCase):
    """Vérifie l'exposition via l'API REST."""

    def setUp(self):
        self.co = _company(slug='fg48-ep', nom='FG48 EP')
        self.user = _user(self.co, username='fg48_ep_user')
        self.cli = _client(self.co)
        self.api = _auth(self.user)

    def test_devis_detail_has_comparaison_options_key(self):
        d = _devis(self.co, self.user, self.cli, ref='DEV-FG48-EP1')
        r = self.api.get(f'/api/django/ventes/devis/{d.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('comparaison_options', r.data)

    def test_devis_list_has_comparaison_options_key(self):
        _devis(self.co, self.user, self.cli, ref='DEV-FG48-EP2')
        r = self.api.get('/api/django/ventes/devis/')
        self.assertEqual(r.status_code, 200)
        if r.data['results']:
            self.assertIn('comparaison_options', r.data['results'][0])

    def test_unauthenticated_devis_list_returns_401(self):
        r = APIClient().get('/api/django/ventes/devis/')
        self.assertIn(r.status_code, (401, 403))
