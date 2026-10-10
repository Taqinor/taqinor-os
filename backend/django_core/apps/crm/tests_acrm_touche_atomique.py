"""ACRM22 (C-ACRM-015) — les gestes de touche sont ATOMIQUES.

Sondes V_VA LVIEW2-2 et V_VB LSVC5-6 : une panne du 2ᵉ appel d'un geste
(report de la prochaine touche après « Fait », enregistrement de la pièce
reçue, premier contact après une note) rendait 500 en laissant la touche
close, une ligne de chatter « faite » et une pièce jointe orpheline.
Désormais tout est annulé, la réponse le dit (5xx explicite), et sans panne
le comportement est inchangé.

Doublures de panne DÉCLARÉES sur ces seules dépendances ; stockage MinIO de
test du harnais (horloge réelle : la signature S3 la lit).
"""
import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.records.models import Attachment

User = get_user_model()
_FAUX_PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 40


class ToucheAtomiqueTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM22 Solaire', slug='acrm22-atomique')
        self.user = User.objects.create_user(
            username='acrm22-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Atomique', owner=self.user,
            stage=stages.CONTACTED, telephone='+212661222222')
        RelanceEtape.objects.filter(lead=self.lead).delete()
        quand = timezone.now() + datetime.timedelta(hours=1)
        self.touche = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=1,
            canal=RelanceEtape.Canal.WHATSAPP, libelle="Message d'identité",
            due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date())
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        self.url = f'/api/django/crm/relance-etapes/{self.touche.pk}/'

    def _empreinte(self):
        self.touche.refresh_from_db()
        return (self.touche.statut,
                LeadActivity.objects.filter(lead=self.lead).count(),
                Attachment.objects.filter(
                    company=self.company, object_id=self.lead.pk).count())

    def test_fait_panne_report_rien_ecrit(self):
        avant = self._empreinte()
        demain = (timezone.localdate() + datetime.timedelta(days=2))
        with patch('apps.crm.services.reporter_prochaine_touche',
                   side_effect=RuntimeError('panne déclarée')):
            resp = self.api.post(f'{self.url}fait/',
                                 {'rappel_le': demain.isoformat()},
                                 format='json')
        self.assertGreaterEqual(resp.status_code, 500)
        self.assertEqual(resp.data.get('code', 'geste_touche_echoue'),
                         'geste_touche_echoue')
        self.assertEqual(self._empreinte(), avant)
        self.assertEqual(self.touche.statut, RelanceEtape.Statut.A_FAIRE)

    def test_piece_recue_panne_aucune_piece(self):
        avant = self._empreinte()
        fichier = SimpleUploadedFile('facture.png', _FAUX_PNG,
                                     content_type='image/png')
        with patch('apps.crm.cadence_reponses.enregistrer_piece_recue',
                   side_effect=RuntimeError('panne déclarée')):
            resp = self.api.post(f'{self.url}piece-recue/',
                                 {'type_piece': 'facture',
                                  'fichier': fichier}, format='multipart')
        self.assertGreaterEqual(resp.status_code, 500)
        self.assertEqual(self._empreinte(), avant)

    def test_noter_panne_rien_ecrit(self):
        avant = self._empreinte()
        with patch('apps.crm.leads_premier_contact.marquer_premier_contact',
                   side_effect=RuntimeError('panne déclarée')):
            resp = self.api.post(
                f'/api/django/crm/leads/{self.lead.pk}/noter/',
                {'body': 'Client rappelé'}, format='json')
        self.assertGreaterEqual(resp.status_code, 500)
        self.assertEqual(self._empreinte(), avant)

    def test_sans_panne_inchange(self):
        resp = self.api.post(f'{self.url}fait/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.touche.refresh_from_db()
        self.assertEqual(self.touche.statut, RelanceEtape.Statut.FAIT)
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/noter/',
            {'body': 'Client rappelé'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
