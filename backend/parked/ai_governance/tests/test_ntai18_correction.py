"""NTAI18 — Tests de la boucle de correction humaine des extractions.

Couvre :
  * ``POST documents-ai-jobs/<id>/corriger/`` enregistre l'ÉCART champ par
    champ et APPLIQUE la valeur validée au résultat du job ;
  * une validation à l'identique est journalisée mais ne compte pas comme
    correction ;
  * rien n'est jamais écrit dans un modèle métier (``applique`` reste faux) ;
  * ``GET documents-ai-jobs/taux-correction/`` expose la qualité par schéma ;
  * isolation société (job d'une autre société → 404) et charge invalide → 400.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged.models import Cabinet, Document, Folder

from ..models import DocumentAiJob, ExtractionCorrection
from ..services import taux_correction_par_schema

User = get_user_model()

BASE = '/api/django/ai/documents-ai-jobs/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


@override_settings(AI_DOCUMENT_JOBS_ENABLED=True)
class Ntai18CorrectionTests(TestCase):
    def setUp(self):
        self.co = make_company('ntai18a', 'NTAI18 A')
        self.user = User.objects.create_user(
            username='ntai18a', password='x', company=self.co,
            role_legacy='admin')
        cab = Cabinet.objects.create(company=self.co, nom='Docs')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='Entrants')
        self.api = auth(self.user)
        self.job = self._job('cin', {'numero_cin': 'AB1234', 'nom': 'ALAMI'})

    def _job(self, schema, champs, *, company=None):
        company = company or self.co
        doc = Document.objects.create(
            company=company, folder=self.folder, nom='piece.pdf')
        job = DocumentAiJob.objects.filter(document=doc).first()
        if job is None:
            job = DocumentAiJob.objects.create(company=company, document=doc)
        job.schema = schema
        job.statut = DocumentAiJob.STATUT_TRAITE
        job.resultat_json = {'categorie': schema, 'schema': schema,
                             'champs': dict(champs),
                             'extraction_disponible': True, 'applique': False}
        job.save()
        return job

    def test_corriger_enregistre_l_ecart_et_applique(self):
        rep = self.api.post(
            f'{BASE}{self.job.id}/corriger/',
            {'corrections': [
                {'champ': 'numero_cin', 'valeur_corrigee': 'AB1235'},
                {'champ': 'nom', 'valeur_corrigee': 'ALAMI'},
            ]}, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)

        corrections = ExtractionCorrection.objects.filter(job=self.job)
        self.assertEqual(corrections.count(), 2)
        cin = corrections.get(champ='numero_cin')
        self.assertEqual(cin.valeur_ia, 'AB1234')
        self.assertEqual(cin.valeur_corrigee, 'AB1235')
        self.assertTrue(cin.est_une_correction)
        self.assertEqual(cin.corrige_par_id, self.user.id)
        self.assertEqual(cin.company_id, self.co.id)
        # Une validation à l'identique est journalisée SANS être une correction.
        self.assertFalse(corrections.get(champ='nom').est_une_correction)

        self.job.refresh_from_db()
        self.assertEqual(self.job.resultat_json['champs']['numero_cin'],
                         'AB1235')
        self.assertTrue(self.job.resultat_json['revu_par_humain'])
        # Toujours AUCUNE écriture métier.
        self.assertFalse(self.job.resultat_json['applique'])

    def test_champ_a_plat_accepte(self):
        rep = self.api.post(
            f'{BASE}{self.job.id}/corriger/',
            {'champ': 'nom', 'valeur_corrigee': 'BENNANI'}, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.job.refresh_from_db()
        self.assertEqual(self.job.resultat_json['champs']['nom'], 'BENNANI')

    def test_charge_invalide_400(self):
        for charge in ({}, {'corrections': []}, {'corrections': ['x']},
                       {'corrections': [{'valeur_corrigee': 'x'}]}):
            rep = self.api.post(f'{BASE}{self.job.id}/corriger/', charge,
                                format='json')
            self.assertEqual(rep.status_code, 400, charge)
        self.assertEqual(ExtractionCorrection.objects.count(), 0)

    def test_job_d_une_autre_societe_invisible(self):
        autre = make_company('ntai18b', 'NTAI18 B')
        job_autre = self._job('cin', {'nom': 'X'}, company=autre)
        rep = self.api.post(
            f'{BASE}{job_autre.id}/corriger/',
            {'champ': 'nom', 'valeur_corrigee': 'Y'}, format='json')
        self.assertEqual(rep.status_code, 404)
        rep = self.api.get(BASE)
        resultats = rep.data['results'] if isinstance(rep.data, dict) else rep.data
        self.assertEqual([j['id'] for j in resultats], [self.job.id])

    def test_taux_correction_par_schema(self):
        self.api.post(
            f'{BASE}{self.job.id}/corriger/',
            {'corrections': [
                {'champ': 'numero_cin', 'valeur_corrigee': 'AB1235'},
                {'champ': 'nom', 'valeur_corrigee': 'ALAMI'},
            ]}, format='json')
        tableau = {ligne['schema']: ligne
                   for ligne in taux_correction_par_schema(self.co)}
        self.assertEqual(tableau['cin']['champs_revus'], 2)
        self.assertEqual(tableau['cin']['champs_corriges'], 1)
        self.assertEqual(tableau['cin']['taux_correction'], 0.5)

    def test_endpoint_taux_correction(self):
        rep = self.api.get(f'{BASE}taux-correction/')
        self.assertEqual(rep.status_code, 200)
        self.assertIsInstance(rep.data, list)
        self.assertIn('cin', [ligne['schema'] for ligne in rep.data])

    def test_taux_correction_scope_societe(self):
        autre = make_company('ntai18c', 'NTAI18 C')
        job_autre = self._job('contrat', {'reference': 'C1'}, company=autre)
        ExtractionCorrection.objects.create(
            company=autre, job=job_autre, champ='reference',
            valeur_ia='C1', valeur_corrigee='C2')
        schemas = [ligne['schema'] for ligne in taux_correction_par_schema(self.co)]
        self.assertNotIn('contrat', schemas)

    def test_job_en_lecture_seule(self):
        # Un job n'est jamais créé par un client HTTP (le pipeline s'en charge).
        rep = self.api.post(BASE, {'document': 1}, format='json')
        self.assertIn(rep.status_code, (403, 405))
