"""Tests NTCON3 — RFI (Request For Information).

Couvre :
* création avec numéro race-safe par chantier + échéance en jours ouvrés ;
* un RFI sans réponse à échéance dépassée apparaît « en retard » (liste
  triée par échéance dépassée en premier) ;
* répondre clôt le cycle (statut → repondu) ;
* clore un RFI ferme le cycle ; ré-agir sur un RFI clos → 400 ;
* cross-tenant refusé.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from apps.btp_chantier.models import RFI

from .helpers import auth, make_chantier, make_company, make_user

BASE = '/api/django/btp-chantier/rfi/'


class RfiApiTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.destinataire = make_user(self.co, username='destinataire')
        self.chantier = make_chantier(self.co)

    def test_create_rfi_numero_and_echeance(self):
        api = auth(self.user)
        resp = api.post(BASE, {
            'chantier': self.chantier.id,
            'question': 'Quelle nuance de béton pour le radier ?',
            'destinataire_user': self.destinataire.id,
            'delai_jours': 3,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['numero'], 1)
        self.assertEqual(resp.data['statut'], 'ouvert')
        self.assertIsNotNone(resp.data['date_limite_reponse'])

        resp2 = api.post(BASE, {
            'chantier': self.chantier.id,
            'question': 'Deuxième question',
        }, format='json')
        self.assertEqual(resp2.data['numero'], 2)

    def test_rfi_en_retard_apparait_en_tete(self):
        hier = timezone.localdate() - timedelta(days=1)
        demain = timezone.localdate() + timedelta(days=5)
        en_retard = RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=1,
            question='Retard', date_limite_reponse=hier)
        RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=2,
            question='Dans les temps', date_limite_reponse=demain)

        api = auth(self.user)
        resp = api.get(BASE)
        rows = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertEqual(rows[0]['id'], en_retard.id)
        self.assertTrue(rows[0]['en_retard'])

    def test_rfi_repondu_ou_clos_exclu_du_retard(self):
        hier = timezone.localdate() - timedelta(days=1)
        RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=1,
            question='Répondu', date_limite_reponse=hier,
            statut=RFI.Statut.REPONDU)
        from apps.btp_chantier.selectors import rfi_en_retard
        self.assertEqual(rfi_en_retard(self.co).count(), 0)

    def test_repondre_clot_le_cycle(self):
        rfi = RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=1,
            question='Q', pose_par=self.user,
            date_limite_reponse=timezone.localdate())
        api = auth(self.user)
        resp = api.post(
            f'{BASE}{rfi.id}/repondre/', {'texte': 'C25/30'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'repondu')
        self.assertEqual(len(resp.data['reponses']), 1)

    def test_repondre_sans_texte_refuse(self):
        rfi = RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=1, question='Q')
        api = auth(self.user)
        resp = api.post(f'{BASE}{rfi.id}/repondre/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_clore_rfi(self):
        rfi = RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=1, question='Q')
        api = auth(self.user)
        resp = api.post(f'{BASE}{rfi.id}/clore/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['statut'], 'clos')

    def test_repondre_sur_rfi_clos_refuse(self):
        rfi = RFI.objects.create(
            company=self.co, chantier=self.chantier, numero=1, question='Q',
            statut=RFI.Statut.CLOS)
        api = auth(self.user)
        resp = api.post(
            f'{BASE}{rfi.id}/repondre/', {'texte': 'X'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_tenant_refused(self):
        other_co = make_company()
        other_chantier = make_chantier(other_co)
        other_rfi = RFI.objects.create(
            company=other_co, chantier=other_chantier, numero=1, question='Q')
        api = auth(self.user)
        resp = api.get(f'{BASE}{other_rfi.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class RfiPlatformTests(TestCase):
    def test_reponse_registered_as_record_target(self):
        from apps.records.models import ALLOWED_TARGETS
        self.assertIn(('btp_chantier', 'rfireponse'), ALLOWED_TARGETS)
