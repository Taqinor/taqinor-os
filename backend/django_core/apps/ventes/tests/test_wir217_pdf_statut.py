"""WIR217 — l'échec DÉFINITIF d'une génération de PDF de devis devient visible.

`task_generate_devis_pdf` retentait 3 fois puis abandonnait EN SILENCE : rien
n'était consigné nulle part, si bien que l'écran sondait `fichier_pdf`
indéfiniment pour un PDF qui ne viendrait jamais (sondage sans fin, toast
« toujours en cours » répété, aucun échec terminal visible ni actionnable).

Ce test AFFIRME l'exemple committé dans
``apps/ventes/contract_samples/devis_pdf_statut.json`` — le MÊME fichier que le
test frontend importe (jamais un payload écrit à la main de chaque côté : c'est
exactement la double source de vérité que PACT10 supprime).
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.tasks import (
    enregistrer_echec_pdf_devis, oublier_echec_pdf_devis, pdf_job_cache_key)

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parents[1]
     / 'contract_samples' / 'devis_pdf_statut.json').read_text(encoding='utf-8'))


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PdfStatutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.get_or_create(
            slug='wir217-co', defaults={'nom': 'WIR217 Co'})[0]
        self.user = User.objects.create_user(
            username='wir217-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='WIR217',
            telephone='+212600021701')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_obj, reference='DEV-WIR217')

    def _url(self, devis=None):
        return f'/api/django/ventes/devis/{(devis or self.devis).pk}/pdf-statut/'

    # ── Le contrat committé EST la réponse du serveur ───────────────────────

    def test_les_cles_sont_exactement_celles_du_contrat(self):
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            set(resp.data.keys()), set(CONTRAT['exemple'].keys()))

    def test_etat_en_cours_conforme_a_exemple_en_cours(self):
        attendu = CONTRAT['exemple_en_cours']
        resp = self.api.get(self._url())
        self.assertEqual(resp.data['statut'], attendu['statut'])
        self.assertEqual(resp.data['erreur'], attendu['erreur'])
        self.assertEqual(resp.data['fichier_pdf'], attendu['fichier_pdf'])

    def test_etat_echec_conforme_a_exemple(self):
        enregistrer_echec_pdf_devis(self.devis.pk, 'Rendu impossible.')
        resp = self.api.get(self._url())
        self.assertEqual(resp.data['statut'], CONTRAT['exemple']['statut'])
        self.assertEqual(resp.data['erreur'], 'Rendu impossible.')
        self.assertFalse(resp.data['fichier_pdf'])

    def test_etat_pret_conforme_a_exemple_pret(self):
        attendu = CONTRAT['exemple_pret']
        self.devis.fichier_pdf = 'devis/DEV-WIR217.pdf'
        self.devis.save(update_fields=['fichier_pdf'])
        resp = self.api.get(self._url())
        self.assertEqual(resp.data['statut'], attendu['statut'])
        self.assertTrue(resp.data['fichier_pdf'])

    def test_pret_prime_sur_un_echec_consigne(self):
        """Un PDF finalement présent n'est JAMAIS annoncé « en échec »."""
        enregistrer_echec_pdf_devis(self.devis.pk, 'Boum')
        self.devis.fichier_pdf = 'devis/DEV-WIR217.pdf'
        self.devis.save(update_fields=['fichier_pdf'])
        self.assertEqual(self.api.get(self._url()).data['statut'], 'pret')

    # ── Le relancement efface l'échec (sinon 24 h d'échec fantôme) ──────────

    def test_oublier_echec_remet_en_cours(self):
        enregistrer_echec_pdf_devis(self.devis.pk, 'Boum')
        oublier_echec_pdf_devis(self.devis.pk)
        self.assertEqual(self.api.get(self._url()).data['statut'], 'en_cours')

    # ── Isolation société : jamais l'échec d'un autre tenant ───────────────

    def test_entree_de_cache_d_une_autre_societe_ignoree(self):
        cache.set(pdf_job_cache_key(self.devis.pk), {
            'company_id': -1, 'devis_id': self.devis.pk,
            'statut': 'echec', 'erreur': "Fuite d'un autre tenant",
        }, 60)
        resp = self.api.get(self._url())
        self.assertEqual(resp.data['statut'], 'en_cours')
        self.assertEqual(resp.data['erreur'], '')

    def test_devis_d_une_autre_societe_404(self):
        autre = Company.objects.get_or_create(
            slug='wir217-autre', defaults={'nom': 'Autre WIR217'})[0]
        autre_user = User.objects.create_user(
            username='wir217-autre-admin', password='x', company=autre,
            role_legacy='admin')
        self.assertEqual(auth(autre_user).get(self._url()).status_code, 404)
