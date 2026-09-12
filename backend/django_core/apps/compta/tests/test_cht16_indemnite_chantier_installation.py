"""Tests CHT16 — Indemnités de frais rattachées au vrai chantier.

Couvre : `installation_id` (loose ref vers `installations.Installation`,
migration ADDITIVE apps/frais — jamais une FK, jamais un import de
`installations.models` depuis `compta`/`frais`), validé société via
`installations.selectors.installation_scoped` (400 si le chantier n'existe
pas / appartient à une autre société — le contre-exemple gestion_projet,
loose ref jamais validée, n'est PAS reproduit ici), persistance de bout en
bout (création ET modification, `apps.compta.services.
creer_indemnite_chantier` + `IndemniteChantierViewSet.create`), non-
régression des enregistrements antérieurs à CHT16 (créés sans
`installation_id`, `libelle_chantier` en repli intact), et le contrat
partagé `apps/compta/contract_samples/indemnite_chantier.json` (PACT10) — le
même exemple que le test frontend importe.
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import BaremeIndemnite, IndemniteChantier
from apps.compta.serializers import IndemniteChantierSerializer

User = get_user_model()

# PACT10 — l'exemple de réponse committé, porteur du contrat front <-> back.
ECHANTILLON = (
    Path(__file__).resolve().parent.parent
    / 'contract_samples' / 'indemnite_chantier.json')


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _FakeRequest:
    """Contexte minimal pour appeler le serializer hors d'une vraie requête."""

    def __init__(self, user):
        self.user = user


class IndemniteChantierInstallationIdSerializerTests(TestCase):
    """`validate_installation_id` — validation société pure (sans HTTP)."""

    def setUp(self):
        self.co = make_company('cht16-ser', 'CHT16 Serializer')
        self.employe = make_user(self.co, 'cht16-ser-emp', role='normal')
        self.resp = make_user(self.co, 'cht16-ser-resp')
        BaremeIndemnite.objects.create(
            company=self.co, libelle='Barème CHT16', taux_km=Decimal('3'),
            per_diem=Decimal('100'), defaut=True)

    def _payload(self, **extra):
        payload = {
            'employe': self.employe.id,
            'date_deplacement': '2026-09-10',
            'nombre_jours': 1,
        }
        payload.update(extra)
        return payload

    def test_chantier_introuvable_refuse(self):
        serializer = IndemniteChantierSerializer(
            data=self._payload(installation_id=999),
            context={'request': _FakeRequest(self.resp)})
        with patch(
            'apps.installations.selectors.installation_scoped',
            return_value=None,
        ):
            self.assertFalse(serializer.is_valid())
        self.assertIn('installation_id', serializer.errors)

    def test_chantier_meme_societe_accepte(self):
        serializer = IndemniteChantierSerializer(
            data=self._payload(installation_id=42),
            context={'request': _FakeRequest(self.resp)})
        with patch(
            'apps.installations.selectors.installation_scoped',
            return_value=object(),
        ):
            self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['installation_id'], 42)

    def test_installation_id_absent_reste_optionnel(self):
        serializer = IndemniteChantierSerializer(
            data=self._payload(), context={'request': _FakeRequest(self.resp)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn('installation_id', serializer.validated_data)


class IndemniteChantierInstallationIdApiTests(TestCase):
    """Validation société + persistance de bout en bout, via l'API REST."""

    def setUp(self):
        self.co_a = make_company('cht16-api-a', 'CHT16 API A')
        self.co_b = make_company('cht16-api-b', 'CHT16 API B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        self.employe_a = make_user(self.co_a, 'cht16-emp-a', role='normal')
        self.resp_a = make_user(self.co_a, 'cht16-resp-a')
        BaremeIndemnite.objects.create(
            company=self.co_a, libelle='Barème A', taux_km=Decimal('3'),
            per_diem=Decimal('100'), defaut=True)

    def _payload(self, **extra):
        payload = {
            'employe': self.employe_a.id,
            'date_deplacement': '2026-09-10',
            'nombre_jours': 1,
        }
        payload.update(extra)
        return payload

    def test_endpoint_create_chantier_autre_societe_refuse(self):
        api = auth(self.resp_a)
        with patch(
            'apps.installations.selectors.installation_scoped',
            return_value=None,
        ):
            resp = api.post(
                '/api/django/compta/indemnites-chantier/',
                self._payload(installation_id=999), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(
            IndemniteChantier.objects.filter(company=self.co_a).exists())

    def test_endpoint_create_persiste_installation_id(self):
        """Régression du piège du CHT16 : un champ validé mais non reporté au
        service serait un « validateur mort » — `IndemniteChantierViewSet.
        create()` construit l'objet à la main (pas `serializer.save()`), il
        doit donc explicitement transmettre `installation_id`."""
        api = auth(self.resp_a)
        with patch(
            'apps.installations.selectors.installation_scoped',
            return_value=object(),
        ):
            resp = api.post(
                '/api/django/compta/indemnites-chantier/',
                self._payload(installation_id=42), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['installation_id'], 42)
        indem = IndemniteChantier.objects.get(id=resp.data['id'])
        self.assertEqual(indem.installation_id, 42)
        self.assertEqual(indem.company_id, self.co_a.id)

    def test_endpoint_update_recale_installation_id_sans_toucher_libelle(self):
        indem = services.creer_indemnite_chantier(
            self.co_a, employe=self.employe_a,
            date_deplacement=date(2026, 9, 1), nombre_jours=1,
            libelle_chantier='Chantier Rabat (legacy)', user=self.resp_a)
        api = auth(self.resp_a)
        with patch(
            'apps.installations.selectors.installation_scoped',
            return_value=object(),
        ):
            resp = api.patch(
                f'/api/django/compta/indemnites-chantier/{indem.id}/',
                {'installation_id': 77}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        indem.refresh_from_db()
        self.assertEqual(indem.installation_id, 77)
        # `libelle_chantier` (repli/héritage) n'est PAS écrasé par le patch.
        self.assertEqual(indem.libelle_chantier, 'Chantier Rabat (legacy)')

    def test_enregistrement_legacy_sans_installation_id_intact(self):
        """CHT16 est ADDITIF : une indemnité créée sans `installation_id`
        (comme toutes celles d'avant CHT16) reste lisible telle quelle."""
        indem = services.creer_indemnite_chantier(
            self.co_a, employe=self.employe_a,
            date_deplacement=date(2026, 1, 5), nombre_jours=1,
            libelle_chantier='Chantier historique', user=self.resp_a)
        self.assertIsNone(indem.installation_id)
        data = IndemniteChantierSerializer(indem).data
        self.assertIsNone(data['installation_id'])
        self.assertEqual(data['libelle_chantier'], 'Chantier historique')

    def test_isolation_societe_toujours_effective(self):
        """Non-régression : le scoping société standard (co_b ne voit pas les
        indemnités de co_a) n'est pas affecté par CHT16."""
        services.creer_indemnite_chantier(
            self.co_a, employe=self.employe_a,
            date_deplacement=date(2026, 9, 1), nombre_jours=1,
            installation_id=7)
        user_b = make_user(self.co_b, 'cht16-user-b')
        resp = auth(user_b).get('/api/django/compta/indemnites-chantier/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertEqual(len(rows), 0)


class ContratIndemniteChantierTests(TestCase):
    """PACT10 — l'exemple committé porte le VRAI contrat de la sérialisation."""

    def setUp(self):
        self.co = make_company('cht16-contrat', 'CHT16 Contrat')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.employe = make_user(self.co, 'cht16-c-emp', role='normal')
        self.resp = make_user(self.co, 'cht16-c-resp')
        BaremeIndemnite.objects.create(
            company=self.co, libelle='Barème', taux_km=Decimal('3'),
            per_diem=Decimal('100'), defaut=True)

    def test_forme_serialisee_egale_exemple_committe(self):
        indem = services.creer_indemnite_chantier(
            self.co, employe=self.employe, date_deplacement=date(2026, 9, 10),
            nombre_jours=1, installation_id=88, user=self.resp)
        contrat = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
        exemple = contrat['exemple']
        data = IndemniteChantierSerializer(indem).data
        # Comparaison par FORME (les clés) — id/employe/dates sont
        # dynamiques d'un run à l'autre (patron test_emprunts.py).
        self.assertEqual(sorted(exemple), sorted(data))
        self.assertIn('installation_id', data)
        self.assertEqual(data['installation_id'], 88)
