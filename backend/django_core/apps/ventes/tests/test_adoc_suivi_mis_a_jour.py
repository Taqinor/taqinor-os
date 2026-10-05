"""ADOC130 — ``mis_a_jour_le`` du suivi public = date du dernier jalon fait.

« Mis à jour le » ne vaut plus la date de la requête : ``generated_at`` reste
l'horodatage technique (contrat ``suivi_public.json``, ADOC112).
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.services import create_installation_from_devis
from apps.portail.services import upsert_jalon_chantier
from apps.ventes.models import Devis, ShareLink
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'suivi_public.json')


class SuiviMisAJourTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ADOC130 Co')
        self.user = User.objects.create_user(
            username='adoc130', password='x', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADOC130',
            telephone='+212600000130')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-ADOC13001',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            date_acceptation=datetime.date(2026, 8, 26),
            taux_tva=Decimal('20'))
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _get(self):
        resp = self.api.get(f'/api/django/ventes/suivi/{self.link.token}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.data

    def test_mis_a_jour_le_stable_entre_deux_lectures(self):
        with freeze_time('2026-10-05 12:41:15'):
            d1 = self._get()
        with freeze_time('2026-10-05 12:41:16'):
            d2 = self._get()
        with freeze_time('2026-11-14 09:00:00'):
            d3 = self._get()
        self.assertNotEqual(d1['generated_at'], d2['generated_at'])
        self.assertEqual(d1['mis_a_jour_le'], '2026-08-26')
        self.assertEqual(d2['mis_a_jour_le'], '2026-08-26')
        self.assertEqual(d3['mis_a_jour_le'], '2026-08-26')

    def test_mis_a_jour_le_suit_le_dernier_jalon_fait(self):
        chantier, _ = create_installation_from_devis(
            self.devis, self.user, self.company)
        upsert_jalon_chantier(
            self.company, chantier.id, 'pose', 'Pose', atteint=True,
            date_jalon=datetime.date(2026, 10, 2))
        self.assertEqual(self._get()['mis_a_jour_le'], '2026-10-02')

    def test_null_sans_jalon_fait(self):
        self.devis.statut = Devis.Statut.ENVOYE
        self.devis.date_acceptation = None
        self.devis.save(update_fields=['statut', 'date_acceptation'])
        self.assertIsNone(self._get()['mis_a_jour_le'])

    def test_cles_conformes_au_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        self.assertEqual(contrat['forme_serveur'], 'complete')
        # ``detail`` est la clé des REFUS (403 otp_required / 404) : la carte
        # complète lue par scripts/check_api_shapes.py unit toutes les
        # réponses de la vue, l'exemple la déclare donc à null (même
        # convention que proposal_data.json). Un 200 ne la porte jamais.
        self.assertIsNone(contrat['exemple']['detail'])
        self.assertEqual(set(self._get()),
                         set(contrat['exemple']) - {'detail'})
