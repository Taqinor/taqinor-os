"""WIR217 — l'échec DÉFINITIF d'une génération de PDF de devis est consigné,
lisible, et le sondage du frontend peut enfin s'arrêter.

Le constat : ``task_generate_devis_pdf`` retentait 3 fois puis mourait en
silence. Le sondage de ``DevisList`` ne lisait que ``fichier_pdf`` : il tournait
donc INDÉFINIMENT, en répétant son toast « toujours en cours », et
l'utilisateur n'apprenait jamais qu'il n'y aurait pas de PDF.

Ce module vérifie :
  1. la tâche ne consigne RIEN tant qu'un retry reste (échec transitoire) ;
  2. elle consigne l'échec quand les retries sont épuisés (patron EXPORT_JOB) ;
  3. un rendu réussi — comme une nouvelle demande — PURGE l'échec ;
  4. ``GET /ventes/devis/<id>/etat-pdf/`` rend les trois états, et le PDF prêt
     l'emporte sur un échec plus ancien ;
  5. la réponse a EXACTEMENT la forme de l'exemple de contrat committé
     (``contract_samples/devis_etat_pdf.json``, PACT10) — le même fichier que
     le test frontend importe, donc les deux moitiés ne peuvent plus diverger ;
  6. l'état d'une AUTRE société n'est jamais lisible (404 + garde en profondeur).
"""
import json
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes import tasks as ventes_tasks
from apps.ventes.models import Devis

User = get_user_model()
ECHANTILLON = (Path(__file__).resolve().parent.parent
               / 'contract_samples' / 'devis_etat_pdf.json')


def _contrat(variante='exemple'):
    return json.loads(ECHANTILLON.read_text(encoding='utf-8'))[variante]


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='WIR217 Co')
        self.user = User.objects.create_user(
            username='wir217-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='WIR217',
            telephone='+212600021701')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_obj,
            reference='DEV-WIR217-1')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def url(self, devis=None):
        return f'/api/django/ventes/devis/{(devis or self.devis).pk}/etat-pdf/'


class ConsignationEchecTests(_Base):
    def test_rien_de_consigne_tant_qu_un_retry_reste(self):
        ventes_tasks.consigner_echec_pdf_devis  # présent
        cle = ventes_tasks.pdf_job_cache_key(self.devis.pk)
        self.assertIsNone(cache.get(cle))
        # Un échec TRANSITOIRE est encore « en cours » pour l'utilisateur.
        resp = self.api.get(self.url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'en_cours')

    def test_echec_definitif_consigne_avec_la_societe(self):
        ventes_tasks.consigner_echec_pdf_devis(
            self.devis.pk, ValueError("Aucun onduleur."))
        job = cache.get(ventes_tasks.pdf_job_cache_key(self.devis.pk))
        self.assertEqual(job['status'], 'error')
        self.assertEqual(job['company_id'], self.company.id)
        self.assertIn('onduleur', job['error'])
        self.assertTrue(job['at'])

    def test_un_rendu_reussi_purge_l_echec(self):
        ventes_tasks.consigner_echec_pdf_devis(self.devis.pk, 'boum')
        ventes_tasks.oublier_echec_pdf_devis(self.devis.pk)
        self.assertIsNone(
            cache.get(ventes_tasks.pdf_job_cache_key(self.devis.pk)))

    def test_relancer_la_generation_efface_l_echec(self):
        ventes_tasks.consigner_echec_pdf_devis(self.devis.pk, 'boum')
        with patch('apps.ventes.tasks.task_generate_devis_pdf.delay') as delay:
            delay.return_value.id = 'tache-1'
            resp = self.api.post(
                f'/api/django/ventes/devis/{self.devis.pk}/generer-pdf/',
                {}, format='json')
        self.assertEqual(resp.status_code, 202, resp.data)
        self.assertIsNone(
            cache.get(ventes_tasks.pdf_job_cache_key(self.devis.pk)))


class EtatPdfEndpointTests(_Base):
    def test_en_cours_par_defaut(self):
        resp = self.api.get(self.url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'en_cours')
        self.assertFalse(resp.data['fichier_pdf'])
        self.assertIsNone(resp.data['erreur'])
        self.assertIsNone(resp.data['date'])

    def test_echec_expose_le_message_du_serveur(self):
        ventes_tasks.consigner_echec_pdf_devis(
            self.devis.pk, "Aucune option de ce devis ne porte d'onduleur")
        resp = self.api.get(self.url())
        self.assertEqual(resp.data['statut'], 'echec')
        self.assertIn('onduleur', resp.data['erreur'])
        self.assertTrue(resp.data['date'])

    def test_pdf_pret_l_emporte_sur_un_echec_plus_ancien(self):
        ventes_tasks.consigner_echec_pdf_devis(self.devis.pk, 'ancien')
        self.devis.fichier_pdf = 'devis/1/DEV-WIR217-1.pdf'
        self.devis.save(update_fields=['fichier_pdf'])
        resp = self.api.get(self.url())
        self.assertEqual(resp.data['statut'], 'pret')
        self.assertTrue(resp.data['fichier_pdf'])
        self.assertIsNone(resp.data['erreur'])

    # ── PACT10 — la forme EXACTE de l'exemple committé ───────────────────────
    def test_forme_identique_a_l_exemple_de_contrat(self):
        ventes_tasks.consigner_echec_pdf_devis(self.devis.pk, 'boum')
        resp = self.api.get(self.url())
        self.assertEqual(
            sorted(resp.data.keys()), sorted(_contrat().keys()))
        self.assertEqual(resp.data['statut'], _contrat()['statut'])

    def test_les_trois_variantes_du_contrat_ont_la_meme_forme(self):
        reference = sorted(_contrat().keys())
        for variante in ('exemple', 'exemple_pret', 'exemple_en_cours'):
            self.assertEqual(
                sorted(_contrat(variante).keys()), reference, variante)

    def test_etat_pret_identique_a_la_variante_du_contrat(self):
        self.devis.fichier_pdf = 'devis/1/DEV-WIR217-1.pdf'
        self.devis.save(update_fields=['fichier_pdf'])
        resp = self.api.get(self.url())
        attendu = _contrat('exemple_pret')
        self.assertEqual(resp.data['statut'], attendu['statut'])
        self.assertEqual(resp.data['fichier_pdf'], attendu['fichier_pdf'])
        self.assertEqual(resp.data['erreur'], attendu['erreur'])


class IsolationTests(_Base):
    def test_devis_d_une_autre_societe_404(self):
        autre = Company.objects.create(nom='WIR217 Autre')
        autre_user = User.objects.create_user(
            username='wir217-autre', password='x', role_legacy='responsable',
            company=autre)
        api = APIClient()
        api.force_authenticate(autre_user)
        self.assertEqual(api.get(self.url()).status_code, 404)

    def test_un_job_d_une_autre_societe_est_ignore(self):
        # Défense en profondeur : même si une clé venait à porter une société
        # étrangère, l'endpoint ne la relaie JAMAIS.
        cache.set(ventes_tasks.pdf_job_cache_key(self.devis.pk), {
            'company_id': self.company.id + 9999,
            'status': 'error', 'error': 'fuite', 'at': '2026-01-01T00:00:00Z',
        }, 60)
        resp = self.api.get(self.url())
        self.assertEqual(resp.data['statut'], 'en_cours')
        self.assertIsNone(resp.data['erreur'])
