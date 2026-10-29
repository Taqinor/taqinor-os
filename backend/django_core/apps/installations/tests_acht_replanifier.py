"""ACHT38 (C-ACHT-035) — service unique `replanifier` : date parsée et
validée (400 sous le champ, jamais de 500), compteur de reports, confirmation
du RDV remise à zéro, trace au chatter, pour `confirmer-rdv`, le PATCH de
`date_prevue` et la replanification de masse.

Rejoue CINT-12 (500 puis TransactionManagementError ; `rdv_confirme` True,
compteur 0).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_replanifier"
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations import services
from apps.installations.models import Installation, Intervention

User = get_user_model()
BASE = '/api/django/installations/interventions'


class ReplanifierTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht38', defaults={'nom': 'Co ACHT38'})
        self.user = User.objects.create_user(
            username='resp-acht38', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT38')
        self.iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, date_prevue=datetime.date(2026, 11, 2),
            rdv_confirme=True)

    def test_date_invalide_400(self):
        r = self.api.post(f'{BASE}/{self.iv.id}/confirmer-rdv/',
                          {'date_prevue': 'demain'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('date_prevue', r.data)
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.date_prevue, datetime.date(2026, 11, 2))
        self.assertTrue(self.iv.rdv_confirme)
        self.assertEqual(self.iv.rdv_reschedule_count, 0)

    def test_date_prevue_publiee_en_date(self):
        """api-fuzz-full 27/10 (ENF11) : `date_prevue` est publiée au format
        DATE (une chaîne libre y était « conforme » puis refusée 400) ; une
        chaîne vide n'est pas une date → 400 aussi (elle passait en simple
        confirmation) ; `null` = simple confirmation."""
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        from apps.installations import urls as installations_urls
        schema = SchemaGenerator(patterns=[
            path('api/django/installations/', include(installations_urls)),
        ]).get_schema(request=None, public=True)
        champ = schema['components']['schemas']['ConfirmerRdvRequeteRequest'][
            'properties']['date_prevue']
        self.assertEqual(champ['format'], 'date')
        self.assertTrue(champ['nullable'])
        # api-fuzz-full 29/10 : `motif` publie le motif sans NUL (refusé 400).
        from core.champs_stricts import MOTIF_SANS_NUL
        motif = schema['components']['schemas']['ConfirmerRdvRequeteRequest'][
            'properties']['motif']
        self.assertEqual(motif['pattern'], MOTIF_SANS_NUL)
        r = self.api.post(f'{BASE}/{self.iv.id}/confirmer-rdv/',
                          {'date_prevue': ''}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        r = self.api.post(f'{BASE}/{self.iv.id}/confirmer-rdv/',
                          {'date_prevue': None, 'confirme': True},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.rdv_reschedule_count, 0)

    def test_patch_date_reinitialise_confirmation(self):
        r = self.api.patch(f'{BASE}/{self.iv.id}/',
                           {'date_prevue': '2026-11-09'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.iv.refresh_from_db()
        self.assertFalse(self.iv.rdv_confirme)
        self.assertEqual(self.iv.rdv_reschedule_count, 1)
        self.assertTrue(self.iv.activites.filter(
            kind='note', body__contains='RDV reporté').exists())

    def test_masse_reinitialise_confirmation(self):
        # Le service est le point d'écriture commun de la masse.
        self.assertTrue(services.replanifier(
            self.iv, '2026-11-10', 'Pluie', self.user, technicien_id=None,
            trace=False))
        self.iv.refresh_from_db()
        self.assertFalse(self.iv.rdv_confirme)
        self.assertEqual(self.iv.rdv_reschedule_count, 1)
        self.assertEqual(self.iv.date_prevue, datetime.date(2026, 11, 10))
        with self.assertRaises(ValueError):
            services.replanifier(self.iv, 'n-importe-quoi', '', self.user)

    def test_confirmer_avec_nouvelle_date_confirme_la_nouvelle(self):
        r = self.api.post(f'{BASE}/{self.iv.id}/confirmer-rdv/',
                          {'date_prevue': '2026-11-20', 'confirme': True},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.iv.refresh_from_db()
        self.assertTrue(self.iv.rdv_confirme)
        self.assertEqual(self.iv.rdv_reschedule_count, 1)

    def test_types_du_corps_400(self):
        """api-fuzz-full 29/10 : `motif` publié texte et `confirme` booléen —
        un tableau ou une chaîne répond 400, rien n'est écrit."""
        for corps in ({'motif': [[True]], 'date_prevue': None},
                      {'confirme': 'oui'}, {'confirme': None}):
            r = self.api.post(f'{BASE}/{self.iv.id}/confirmer-rdv/', corps,
                              format='json')
            self.assertEqual(r.status_code, 400, r.data)
        self.iv.refresh_from_db()
        self.assertTrue(self.iv.rdv_confirme)
