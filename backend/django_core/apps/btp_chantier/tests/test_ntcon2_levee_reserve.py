"""Tests NTCON2 — Levée de réserve avec preuve (photo + signature).

Couvre :
* lever sans photo « après » → 400 ;
* lever sans ``signataire_nom`` → 400 ;
* lever avec photo + signature → statut « levee », signature capturée avec
  IP/user-agent, horodatage/auteur serveur, historique de statuts tracé,
  notification best-effort au créateur ;
* contester une réserve NON levée → 400 (transition invalide) ;
* contester une réserve levée → réouverture avec motif tracé ;
* cross-tenant refusé (404).
"""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import ReserveChantier, SignatureBtp

from .helpers import attach, auth, make_chantier, make_company, make_user

BASE = '/api/django/btp-chantier/reserves-chantier/'


def make_reserve(company, chantier, created_by, **kwargs):
    kwargs.setdefault('description', 'Prise défectueuse')
    kwargs.setdefault('statut', ReserveChantier.Statut.OUVERTE)
    return ReserveChantier.objects.create(
        company=company, chantier=chantier, created_by=created_by, **kwargs)


class LeverReserveTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.createur = make_user(self.co, username='createur')
        self.leveur = make_user(self.co, username='leveur')
        self.chantier = make_chantier(self.co)
        self.reserve = make_reserve(self.co, self.chantier, self.createur)

    def test_lever_sans_photo_refuse(self):
        api = auth(self.leveur)
        resp = api.post(
            f'{BASE}{self.reserve.id}/lever/',
            {'signataire_nom': 'Ali Ben'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.reserve.refresh_from_db()
        self.assertEqual(self.reserve.statut, ReserveChantier.Statut.OUVERTE)

    def test_lever_sans_signataire_refuse(self):
        attach(self.co, self.leveur, self.reserve, phase='apres')
        api = auth(self.leveur)
        resp = api.post(f'{BASE}{self.reserve.id}/lever/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lever_avec_photo_et_signature(self):
        attach(self.co, self.leveur, self.reserve, phase='apres')
        api = auth(self.leveur)
        resp = api.post(
            f'{BASE}{self.reserve.id}/lever/',
            {'signataire_nom': 'Ali Ben Salah'}, format='json',
            HTTP_USER_AGENT='pytest-agent', REMOTE_ADDR='10.0.0.9')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['reserve']['statut'], 'levee')

        self.reserve.refresh_from_db()
        self.assertEqual(self.reserve.statut, ReserveChantier.Statut.LEVEE)
        self.assertEqual(self.reserve.leve_par_id, self.leveur.id)
        self.assertIsNotNone(self.reserve.date_levee)

        ct = ContentType.objects.get_for_model(ReserveChantier)
        sig = SignatureBtp.objects.get(
            content_type=ct, object_id=self.reserve.id,
            contexte='levee_reserve')
        self.assertEqual(sig.signataire_nom, 'Ali Ben Salah')
        self.assertEqual(sig.signataire_id, self.leveur.id)
        self.assertEqual(sig.ip_adresse, '10.0.0.9')
        self.assertEqual(sig.user_agent, 'pytest-agent')

        # Historique de statuts tracé (création + levée).
        statuts = list(
            self.reserve.historique.order_by('date_creation')
            .values_list('nouveau_statut', flat=True))
        self.assertEqual(statuts, ['ouverte', 'levee'])

        # Notification best-effort au créateur (in-app, toujours créée).
        from apps.notifications.models import Notification
        self.assertTrue(
            Notification.objects.filter(
                user=self.createur, event_type='approval_decided').exists())

    def test_lever_reserve_dune_autre_societe_404(self):
        other_co = make_company()
        other_chantier = make_chantier(other_co)
        other_reserve = make_reserve(
            other_co, other_chantier, make_user(other_co))
        api = auth(self.leveur)
        resp = api.post(
            f'{BASE}{other_reserve.id}/lever/',
            {'signataire_nom': 'X'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class ContesterReserveTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.createur = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.reserve = make_reserve(self.co, self.chantier, self.createur)

    def test_contester_reserve_non_levee_refuse(self):
        api = auth(self.createur)
        resp = api.post(
            f'{BASE}{self.reserve.id}/contester/',
            {'motif': 'Toujours défectueux'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_contester_sans_motif_refuse(self):
        self.reserve.statut = ReserveChantier.Statut.LEVEE
        self.reserve.save(update_fields=['statut'])
        api = auth(self.createur)
        resp = api.post(
            f'{BASE}{self.reserve.id}/contester/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_contester_reserve_levee_reouvre(self):
        self.reserve.statut = ReserveChantier.Statut.LEVEE
        self.reserve.save(update_fields=['statut'])
        api = auth(self.createur)
        resp = api.post(
            f'{BASE}{self.reserve.id}/contester/',
            {'motif': 'Toujours défectueux'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'contestee')
        self.assertEqual(resp.data['motif_contestation'], 'Toujours défectueux')

        self.reserve.refresh_from_db()
        self.assertEqual(self.reserve.statut, ReserveChantier.Statut.CONTESTEE)
        derniere = self.reserve.historique.order_by('-date_creation').first()
        self.assertEqual(derniere.nouveau_statut, 'contestee')
        self.assertEqual(derniere.motif, 'Toujours défectueux')
