"""Tests XRH18 — Chatter candidature + détection de doublons.

Couvre :
* changer d'étape écrit une ligne old→new (chatter automatique) ;
* créer un doublon d'email renvoie l'avertissement (``check-duplicates``,
  non bloquant) ;
* la fusion conserve l'historique (activités déplacées) ;
* note manuelle via ``noter`` ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import Candidature, CandidatureActivity, OuverturePoste

User = get_user_model()

CANDIDATURES = '/api/django/rh/candidatures/'


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


class ChatterDoublonsCandidatureTests(TestCase):
    def setUp(self):
        self.co = make_company('chat-a', 'A')
        self.rh = make_user(self.co, 'chat-rh')
        # YHIRE14 — le statut par défaut du modèle est désormais 'brouillon'
        # (cycle d'approbation amont) ; ce test poste des candidatures sur
        # l'ouverture, qui doit donc être 'ouvert' au recrutement.
        self.ouverture = OuverturePoste.objects.create(
            company=self.co, intitule='Commercial terrain',
            statut=OuverturePoste.Statut.OUVERT)
        self.cand = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture, nom='Nadia Alaoui',
            email='nadia@example.com', telephone='0612345678')

    def test_changer_etape_ecrit_ligne_chatter(self):
        resp = auth(self.rh).patch(
            f'{CANDIDATURES}{self.cand.id}/',
            {'etape': Candidature.Etape.PRESELECTION})
        self.assertEqual(resp.status_code, 200, resp.data)

        resp = auth(self.rh).get(f'{CANDIDATURES}{self.cand.id}/historique/')
        self.assertEqual(resp.status_code, 200)
        logs = [r for r in resp.data if r['type'] == 'log']
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['field'], 'etape')
        self.assertEqual(logs[0]['old_value'], 'recu')
        self.assertEqual(logs[0]['new_value'], 'preselection')

    def test_pas_de_log_si_pas_de_changement_etape(self):
        resp = auth(self.rh).patch(
            f'{CANDIDATURES}{self.cand.id}/', {'note': 'RAS'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            CandidatureActivity.objects.filter(
                candidature=self.cand, type='log').count(), 0)

    def test_note_manuelle(self):
        resp = auth(self.rh).post(
            f'{CANDIDATURES}{self.cand.id}/noter/',
            {'message': 'Bon profil, à recontacter.'})
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = auth(self.rh).get(f'{CANDIDATURES}{self.cand.id}/historique/')
        notes = [r for r in resp.data if r['type'] == 'note']
        self.assertEqual(len(notes), 1)

    def test_check_duplicates_email_avertissement_non_bloquant(self):
        resp = auth(self.rh).get(
            f'{CANDIDATURES}check-duplicates/',
            {'email': 'Nadia@Example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['id'], self.cand.id)

        # Créer quand même un nouveau candidat avec le même email n'est
        # jamais bloqué (avertissement seulement).
        resp = auth(self.rh).post(CANDIDATURES, {
            'ouverture': self.ouverture.id, 'nom': 'Nadia Doublon',
            'email': 'nadia@example.com',
        })
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_check_duplicates_exclude(self):
        resp = auth(self.rh).get(
            f'{CANDIDATURES}check-duplicates/',
            {'email': 'nadia@example.com', 'exclude': str(self.cand.id)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_fusion_conserve_historique(self):
        source = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture, nom='Nadia Doublon',
            email='nadia@example.com')
        CandidatureActivity.objects.create(
            company=self.co, candidature=source, type='note',
            message='Note historique sur le doublon.')

        resp = auth(self.rh).post(
            f'{CANDIDATURES}{self.cand.id}/fusionner/',
            {'source': source.id})
        self.assertEqual(resp.status_code, 200, resp.data)

        source.refresh_from_db()
        self.assertEqual(source.etape, Candidature.Etape.REJETE)
        self.assertEqual(
            CandidatureActivity.objects.filter(candidature=self.cand).count(),
            2)  # note historique déplacée + note de fusion
        self.assertEqual(
            CandidatureActivity.objects.filter(candidature=source).count(), 0)

    def test_isolation_societe(self):
        co_b = make_company('chat-b', 'B')
        rh_b = make_user(co_b, 'chat-rh-b')
        resp = auth(rh_b).get(f'{CANDIDATURES}{self.cand.id}/historique/')
        self.assertEqual(resp.status_code, 404)
