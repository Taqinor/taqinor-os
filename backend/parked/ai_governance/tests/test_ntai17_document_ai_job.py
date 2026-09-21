"""NTAI17 — Tests de la file de traitement document AI.

Couvre :
  * la file est ÉTEINTE par défaut (aucun job créé au dépôt d'une pièce) ;
  * activée, déposer une pièce GED crée un job « en attente » (idempotent) ;
  * le traitement classe (heuristique GED34 gratuite) puis remplit
    ``resultat_json`` ; sans provider OCR l'extraction est un no-op propre
    (``extraction_disponible`` faux, aucun octet lu du stockage) ;
  * un échec est CAPTURÉ (statut « erreur ») et ne casse jamais la GED ;
  * scoping société + cascade à la suppression du document ;
  * la tâche Celery est tolérante à un job disparu.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from authentication.models import Company
from apps.ged.models import Cabinet, Document, Folder

from ..models import DocumentAiJob
from ..services import (creer_document_ai_job, document_jobs_enabled,
                        schema_pour_categorie, traiter_document_ai_job)
from ..tasks import traiter_document_ai_job_task


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Ntai17FileEteinteTests(TestCase):
    """Sans le flag, le dépôt d'une pièce est byte-identique à avant."""

    def setUp(self):
        self.co = make_company('ntai17a', 'NTAI17 A')
        cab = Cabinet.objects.create(company=self.co, nom='Docs')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='Entrants')

    def test_flag_eteint_par_defaut(self):
        self.assertFalse(document_jobs_enabled())

    def test_aucun_job_sans_le_flag(self):
        Document.objects.create(
            company=self.co, folder=self.folder, nom='Facture ONEE.pdf')
        self.assertEqual(DocumentAiJob.objects.count(), 0)


@override_settings(AI_DOCUMENT_JOBS_ENABLED=True)
class Ntai17CreationJobTests(TestCase):
    def setUp(self):
        self.co = make_company('ntai17b', 'NTAI17 B')
        cab = Cabinet.objects.create(company=self.co, nom='Docs')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='Entrants')

    def _doc(self, nom):
        return Document.objects.create(
            company=self.co, folder=self.folder, nom=nom)

    def test_depot_cree_un_job_en_attente(self):
        doc = self._doc('Contrat de maintenance.pdf')
        job = DocumentAiJob.objects.get(document=doc)
        self.assertEqual(job.statut, DocumentAiJob.STATUT_EN_ATTENTE)
        self.assertEqual(job.company_id, self.co.id)
        self.assertEqual(job.resultat_json, {})

    def test_creation_idempotente(self):
        doc = self._doc('Contrat de maintenance.pdf')
        # Un second appel ne crée pas un doublon tant que le job est en attente.
        creer_document_ai_job(doc)
        creer_document_ai_job(doc)
        self.assertEqual(DocumentAiJob.objects.filter(document=doc).count(), 1)

    def test_mise_a_jour_ne_cree_pas_de_job(self):
        doc = self._doc('Contrat de maintenance.pdf')
        doc.nom = 'Contrat de maintenance v2.pdf'
        doc.save()
        self.assertEqual(DocumentAiJob.objects.filter(document=doc).count(), 1)

    def test_document_sans_societe_ignore(self):
        # Sans société, le scoping serait impossible : aucun job, aucune erreur.
        doc = Document.objects.create(folder=self.folder, nom='Sans société.pdf')
        self.assertIsNone(doc.company_id)
        self.assertIsNone(creer_document_ai_job(doc))
        self.assertEqual(DocumentAiJob.objects.filter(document=doc).count(), 0)

    def test_cascade_suppression_document(self):
        doc = self._doc('Contrat.pdf')
        self.assertEqual(DocumentAiJob.objects.count(), 1)
        doc.delete()
        self.assertEqual(DocumentAiJob.objects.count(), 0)

    def test_scoping_societe(self):
        self._doc('Contrat.pdf')
        autre = make_company('ntai17c', 'NTAI17 C')
        cab = Cabinet.objects.create(company=autre, nom='Docs')
        folder = Folder.objects.create(company=autre, cabinet=cab, nom='E')
        Document.objects.create(company=autre, folder=folder, nom='Contrat.pdf')
        self.assertEqual(
            DocumentAiJob.objects.filter(company=self.co).count(), 1)
        self.assertEqual(
            DocumentAiJob.objects.filter(company=autre).count(), 1)


@override_settings(AI_DOCUMENT_JOBS_ENABLED=True)
class Ntai17TraitementTests(TestCase):
    def setUp(self):
        self.co = make_company('ntai17d', 'NTAI17 D')
        cab = Cabinet.objects.create(company=self.co, nom='Docs')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='Entrants')

    def _job(self, nom):
        doc = Document.objects.create(
            company=self.co, folder=self.folder, nom=nom)
        return DocumentAiJob.objects.get(document=doc)

    def test_classification_puis_extraction_no_op_sans_cle(self):
        job = self._job('Contrat de maintenance annuelle.pdf')
        traiter_document_ai_job(job)
        job.refresh_from_db()
        self.assertEqual(job.statut, DocumentAiJob.STATUT_TRAITE)
        # Classification : l'heuristique GED34 (gratuite) a reconnu le contrat.
        self.assertEqual(job.categorie, 'contrat')
        self.assertEqual(job.schema, 'contrat')
        self.assertFalse(job.resultat_json['extraction_disponible'])
        self.assertEqual(job.resultat_json['champs'], {})
        # Rien n'est appliqué à un modèle métier.
        self.assertFalse(job.resultat_json['applique'])
        self.assertIsNotNone(job.traite_le)

    def test_sans_provider_ocr_aucun_octet_lu(self):
        job = self._job('Contrat de maintenance.pdf')
        with patch('apps.ai_governance.services._octets_du_document') as lecture:
            traiter_document_ai_job(job)
        lecture.assert_not_called()

    def test_categorie_inconnue_ne_donne_aucun_schema(self):
        job = self._job('Document sans mot-clé.pdf')
        traiter_document_ai_job(job)
        job.refresh_from_db()
        self.assertEqual(job.statut, DocumentAiJob.STATUT_TRAITE)
        self.assertEqual(job.categorie, '')
        self.assertEqual(job.schema, '')

    def test_echec_capture_sans_planter(self):
        job = self._job('Contrat.pdf')
        with patch('apps.ged.services.classer_document',
                   side_effect=RuntimeError('provider HS')):
            traiter_document_ai_job(job)
        job.refresh_from_db()
        self.assertEqual(job.statut, DocumentAiJob.STATUT_ERREUR)
        self.assertIn('provider HS', job.message)

    def test_tache_tolere_un_job_disparu(self):
        self.assertIsNone(traiter_document_ai_job_task(999999))

    def test_tache_traite_le_job(self):
        job = self._job('Contrat de maintenance.pdf')
        statut = traiter_document_ai_job_task(job.id)
        self.assertEqual(statut, DocumentAiJob.STATUT_TRAITE)


class Ntai17SchemaMappingTests(TestCase):
    """Le mapping catégorie→gabarit ne renvoie QUE des gabarits existants."""

    def test_categories_connues(self):
        self.assertEqual(schema_pour_categorie('contrat'), 'contrat')
        self.assertEqual(schema_pour_categorie('CIN'), 'cin')
        self.assertEqual(schema_pour_categorie('bon_livraison'), 'bon_livraison')

    def test_categorie_sans_gabarit_disponible(self):
        # « facture » attend le gabarit NTAI16 : tant qu'il n'existe pas, on
        # renvoie '' plutôt qu'un nom de gabarit introuvable.
        from core.ai.schemas import available_schemas
        attendu = ('facture_fournisseur'
                   if 'facture_fournisseur' in available_schemas() else '')
        self.assertEqual(schema_pour_categorie('facture'), attendu)

    def test_categorie_vide_ou_inconnue(self):
        self.assertEqual(schema_pour_categorie(''), '')
        self.assertEqual(schema_pour_categorie('photo'), '')
        self.assertEqual(schema_pour_categorie(None), '')
