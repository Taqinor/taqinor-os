"""NTHOT17 — Événements/banquets : devis d'événement via le flux devis
existant.

Done = générer un devis d'événement crée exactement un Devis ventes qui
apparaît dans /ventes/devis, suit le cycle standard existant, jamais de PDF
alternatif, tests avec mock du selector ventes.
"""
from unittest import mock

from django.test import TestCase

from apps.hospitality import services
from apps.hospitality.models import EvenementBanquet, Recette, SalleEvenement

from .helpers import auth, make_company, make_user


class GenererDevisEvenementTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client

        self.co = make_company('hot-evt-devis', 'Hôtel')
        self.user = make_user(self.co, 'hot-evt-devis-user', role='responsable')
        self.client_crm = Client.objects.create(company=self.co, nom='Client Mariage')
        self.salle = SalleEvenement.objects.create(
            company=self.co, nom='Salle Atlas', capacite_max=150)
        self.recette = Recette.objects.create(
            company=self.co, nom_plat='Tagine royal', prix_vente_ht='120')
        self.evenement = EvenementBanquet.objects.create(
            company=self.co, nom_evenement='Mariage Karim', client=self.client_crm,
            salle=self.salle, nb_convives=100,
            date_debut='2026-09-01T10:00:00Z', date_fin='2026-09-01T22:00:00Z',
        )
        self.evenement.menu_recettes.add(self.recette)

    def test_sans_client_leve_erreur(self):
        evenement_sans_client = EvenementBanquet.objects.create(
            company=self.co, nom_evenement='Sans client',
            date_debut='2026-10-01T10:00:00Z', date_fin='2026-10-01T22:00:00Z',
        )
        with self.assertRaises(services.GenerationDevisEvenementError):
            services.generer_devis_evenement(evenement_sans_client, user=self.user)

    @mock.patch('apps.ventes.services.create_devis_pour_ticket')
    def test_genere_exactement_un_devis_brouillon(self, mock_create):
        fake_devis = mock.Mock(id=555, reference='DEV-2026-000555')
        mock_create.return_value = fake_devis

        devis = services.generer_devis_evenement(self.evenement, user=self.user)

        self.assertEqual(devis, fake_devis)
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['company'], self.co)
        self.assertEqual(kwargs['client_id'], self.client_crm.pk)
        self.assertIn('Mariage Karim', kwargs['note'])
        self.assertIn('Tagine royal', kwargs['note'])

        self.evenement.refresh_from_db()
        self.assertEqual(self.evenement.devis_ventes_id, 555)

    @mock.patch('apps.ventes.services.create_devis_pour_ticket')
    def test_double_generation_refusee(self, mock_create):
        mock_create.return_value = mock.Mock(id=1, reference='DEV-1')
        services.generer_devis_evenement(self.evenement, user=self.user)
        with self.assertRaises(services.GenerationDevisEvenementError):
            services.generer_devis_evenement(self.evenement, user=self.user)
        mock_create.assert_called_once()


class GenererDevisEvenementApiTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client

        self.co = make_company('hot-evt-devis-api', 'Hôtel')
        self.resp = make_user(self.co, 'hot-evt-devis-api-resp', role='responsable')
        self.normal = make_user(self.co, 'hot-evt-devis-api-normal', role='normal')
        self.client_crm = Client.objects.create(company=self.co, nom='Client API')
        self.evenement = EvenementBanquet.objects.create(
            company=self.co, nom_evenement='Anniversaire', client=self.client_crm,
            date_debut='2026-09-01T10:00:00Z', date_fin='2026-09-01T22:00:00Z',
        )

    @mock.patch('apps.ventes.services.create_devis_pour_ticket')
    def test_action_genere_le_devis(self, mock_create):
        mock_create.return_value = mock.Mock(id=42, reference='DEV-42')
        resp = auth(self.resp).post(
            f'/api/django/hospitality/evenements/{self.evenement.pk}/generer-devis/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['devis_id'], 42)
        self.assertEqual(resp.data['devis_reference'], 'DEV-42')

    def test_refuse_pour_role_normal(self):
        resp = auth(self.normal).post(
            f'/api/django/hospitality/evenements/{self.evenement.pk}/generer-devis/')
        self.assertEqual(resp.status_code, 403)
