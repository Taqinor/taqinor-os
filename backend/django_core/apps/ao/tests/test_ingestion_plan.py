"""AOF71 — job d'ingestion d'un support de plan + service de calibration.

Ce que ces tests VERROUILLENT :

* le job est suivi par ``BackgroundJob`` (progression réelle, issue unique) et
  échoue PROPREMENT — motif français — quand la bibliothèque de rendu manque ;
* l'ingestion est IDEMPOTENTE : rejouer ne téléverse pas un second rendu ;
* une échelle qui impliquerait un bâtiment de 3 km est REFUSÉE, pas acceptée
  en silence ;
* un recalibrage ne perd RIEN : le tracé existant reste tel quel et le
  ré-échelonnage est PROPOSÉ, jamais appliqué en douce.

Run :
    python manage.py test apps.ao.tests.test_ingestion_plan -v2
"""
import io
import sys
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from apps.ao import ingestion_service
from apps.ao.ingestion_service import (
    CalibrationInvraisemblable, IngestionImpossible, appliquer_reechelonnage,
    calibrer, normaliser_image, rasteriser_pdf, verifier_vraisemblance,
)
from apps.ao.ingestion_tasks import (
    KIND_INGESTION_PLAN, ingerer_plan, lancer_ingestion_plan,
)
from apps.ao.models import (
    AppelOffre, BatimentAO, ObstacleAO, PlanSource, ToitureAO,
)
from apps.records.models import Attachment
from authentication.models import Company
from core.models import BackgroundJob

User = get_user_model()


def _pdf(pages=1):
    import fitz

    document = fitz.open()
    for _ in range(pages):
        document.new_page(width=595, height=842)
    octets = document.tobytes()
    document.close()
    return octets


def _png(largeur=120, hauteur=80):
    from PIL import Image

    tampon = io.BytesIO()
    Image.new('RGB', (largeur, hauteur), 'white').save(tampon, format='PNG')
    return tampon.getvalue()


def _stockage_factice(octets_source):
    """Remplace MinIO : lecture du source, écriture du rendu."""
    ecrits = []

    def fetch(cle):
        return octets_source, None

    def store(fichier, audio=False, company=None):
        donnees = fichier.read()
        ecrits.append(donnees)
        return ({'file_key': 'attachments/%s/rendu-%d.png'
                 % (getattr(company, 'id', 0), len(ecrits)),
                 'filename': getattr(fichier, 'name', 'rendu.png'),
                 'size': len(donnees), 'mime': 'image/png'}, None)

    return fetch, store, ecrits


class LaVraisemblanceDUneEchelle(SimpleTestCase):
    def test_une_echelle_plausible_ne_leve_aucun_motif(self):
        # planche A3 à 150 dpi : ~1754 px pour ~50 m => 0,0285 m/px
        self.assertEqual(
            verifier_vraisemblance(0.0285, largeur_px=1754, hauteur_px=1240,
                                   distance_px=800, distance_reelle_m=22.8),
            [])

    def test_un_batiment_de_3_km_est_signale(self):
        motifs = verifier_vraisemblance(3.0, largeur_px=1000,
                                        distance_px=100,
                                        distance_reelle_m=300)
        self.assertTrue(motifs)
        self.assertTrue(any('m/px' in m for m in motifs))

    def test_un_plan_plus_petit_qu_une_porte_est_signale(self):
        motifs = verifier_vraisemblance(0.0001, largeur_px=1000)
        self.assertTrue(any('porte' in m for m in motifs))

    def test_un_segment_de_calibration_trop_court_est_signale(self):
        motifs = verifier_vraisemblance(0.03, distance_px=2.0)
        self.assertTrue(any('pointage' in m for m in motifs))

    def test_une_echelle_absente_est_signalee(self):
        self.assertTrue(verifier_vraisemblance(None))
        self.assertTrue(verifier_vraisemblance(0))


class BasePlanSource(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF71 Co', slug='aof71-co')
        self.user = User.objects.create_user(
            username='aof71_op', password='x', company=self.company)
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-71-1', objet='Ingestion')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='05H',
            contour_local_m=[[0, 0], [20, 0], [20, 10], [0, 10]])
        self.obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='A',
            provenance=ObstacleAO.Provenance.MESURE,
            rect_x0_m=Decimal('2.000'), rect_x1_m=Decimal('4.000'),
            rect_y0_m=Decimal('2.000'), rect_y1_m=Decimal('3.000'))
        self.source = Attachment.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(PlanSource),
            object_id=0, file_key='attachments/%s/source.pdf'
            % self.company.pk, filename='plan.pdf', size=1024,
            mime='application/pdf')
        self.plan = PlanSource.objects.create(
            company=self.company, toiture=self.toiture,
            origine=PlanSource.Origine.PLAN_FOURNI,
            type_fichier=PlanSource.TypeFichier.PDF,
            attachment=self.source, page=1)


class LaCalibrationADeuxPoints(BasePlanSource):
    def test_une_calibration_plausible_pose_l_echelle(self):
        sortie = calibrer(self.plan, point_a_px=[100, 100],
                          point_b_px=[900, 100], distance_reelle_m=22.8,
                          largeur_px=1754, hauteur_px=1240)
        self.plan.refresh_from_db()
        self.assertAlmostEqual(sortie['echelle_m_par_px'], 22.8 / 800.0, 6)
        self.assertEqual(self.plan.etat, PlanSource.Etat.CALIBRE)
        self.assertIsNone(sortie['reechelonnage'])
        self.assertEqual(sortie['alertes'], [])

    def test_une_echelle_de_batiment_de_3_km_est_refusee(self):
        with self.assertRaises(CalibrationInvraisemblable) as capture:
            calibrer(self.plan, point_a_px=[0, 0], point_b_px=[100, 0],
                     distance_reelle_m=300, largeur_px=1000)
        self.assertTrue(str(capture.exception))
        self.plan.refresh_from_db()
        self.assertIsNone(self.plan.echelle_m_par_px)
        self.assertEqual(self.plan.etat, PlanSource.Etat.BRUT)

    def test_deux_points_confondus_sont_refuses(self):
        with self.assertRaises(CalibrationInvraisemblable):
            calibrer(self.plan, point_a_px=[10, 10], point_b_px=[10, 10],
                     distance_reelle_m=5)

    def test_une_distance_reelle_nulle_est_refusee(self):
        with self.assertRaises(CalibrationInvraisemblable):
            calibrer(self.plan, point_a_px=[0, 0], point_b_px=[800, 0],
                     distance_reelle_m=0)

    def test_forcer_accepte_mais_trace_l_alerte(self):
        sortie = calibrer(self.plan, point_a_px=[0, 0], point_b_px=[100, 0],
                          distance_reelle_m=300, largeur_px=1000,
                          forcer=True)
        self.assertTrue(sortie['alertes'])
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.echelle_m_par_px)


class LeRecalibrageNePerdRien(BasePlanSource):
    def _calibrer(self, distance):
        return calibrer(self.plan, point_a_px=[100, 100],
                        point_b_px=[900, 100], distance_reelle_m=distance,
                        largeur_px=1754, hauteur_px=1240)

    def test_le_reechelonnage_est_propose_jamais_applique(self):
        self._calibrer(22.8)
        contour_avant = list(self.toiture.contour_local_m)
        sortie = self._calibrer(25.0)
        proposition = sortie['reechelonnage']
        self.assertIsNotNone(proposition)
        self.assertFalse(proposition['applique'])
        self.assertAlmostEqual(proposition['facteur'], 25.0 / 22.8, 6)
        self.assertEqual(proposition['objets']['sommets_enveloppe'], 4)
        self.assertEqual(proposition['objets']['obstacles'], 1)
        self.toiture.refresh_from_db()
        self.assertEqual(self.toiture.contour_local_m, contour_avant)

    def test_appliquer_le_reechelonnage_est_un_second_appel_explicite(self):
        self._calibrer(22.8)
        sortie = self._calibrer(45.6)
        facteur = sortie['reechelonnage']['facteur']
        self.assertAlmostEqual(facteur, 2.0, 6)
        resultat = appliquer_reechelonnage(self.plan, facteur)
        self.assertTrue(resultat['applique'])
        self.toiture.refresh_from_db()
        self.obstacle.refresh_from_db()
        self.assertEqual(self.toiture.contour_local_m,
                         [[0, 0], [40, 0], [40, 20], [0, 20]])
        self.assertEqual(self.obstacle.rect_x0_m, Decimal('4.000'))
        self.assertEqual(self.obstacle.rect_x1_m, Decimal('8.000'))
        self.assertEqual(self.toiture.surface_m2, Decimal('800.000'))

    def test_un_facteur_nul_est_refuse(self):
        with self.assertRaises(CalibrationInvraisemblable):
            appliquer_reechelonnage(self.plan, 0)


class LaRasterisationEtLaNormalisation(SimpleTestCase):
    def test_une_page_de_pdf_devient_un_png(self):
        octets, largeur, hauteur = rasteriser_pdf(_pdf(), page=1, dpi=72)
        self.assertTrue(octets.startswith(b'\x89PNG'))
        self.assertEqual((largeur, hauteur), (595, 842))

    def test_une_page_inexistante_est_refusee_avec_un_motif(self):
        with self.assertRaises(IngestionImpossible) as capture:
            rasteriser_pdf(_pdf(pages=1), page=4)
        self.assertIn('page', str(capture.exception))

    def test_sans_pymupdf_l_echec_est_propre(self):
        # Le PDF témoin est fabriqué AVANT de masquer ``fitz`` : construit à
        # l'intérieur du ``patch.dict``, c'était la FIXTURE — et non la
        # fonction sous test — qui échouait à importer PyMuPDF, si bien que
        # le test ne prouvait plus rien de l'échec propre visé.
        octets = _pdf()
        with patch.dict(sys.modules, {'fitz': None}):
            with self.assertRaises(IngestionImpossible) as capture:
                rasteriser_pdf(octets)
        self.assertIn('PyMuPDF', str(capture.exception))

    def test_une_image_est_normalisee_en_png(self):
        octets, largeur, hauteur = normaliser_image(_png(120, 80))
        self.assertTrue(octets.startswith(b'\x89PNG'))
        self.assertEqual((largeur, hauteur), (120, 80))

    def test_une_image_trop_large_est_bornee(self):
        source = _png(ingestion_service.LARGEUR_MAX_PX + 400, 200)
        _octets, largeur, _hauteur = normaliser_image(source)
        self.assertEqual(largeur, ingestion_service.LARGEUR_MAX_PX)

    def test_un_fichier_illisible_est_refuse_avec_un_motif(self):
        with self.assertRaises(IngestionImpossible) as capture:
            normaliser_image(b'ceci n est pas une image')
        self.assertIn('image', str(capture.exception))


class LeJobDIngestion(BasePlanSource):
    def _lancer(self, octets_source, **kwargs):
        fetch, store, ecrits = _stockage_factice(octets_source)
        with patch('apps.records.storage.fetch_attachment', fetch), \
                patch('apps.records.storage.store_attachment', store):
            job = BackgroundJob.objects.create(
                company=self.company, user=self.user,
                kind=KIND_INGESTION_PLAN)
            sortie = ingerer_plan(job_id=job.pk, plan_source_id=self.plan.pk,
                                  **kwargs)
        job.refresh_from_db()
        return job, sortie, ecrits

    def test_le_job_va_jusqu_au_bout_et_publie_son_rendu(self):
        job, sortie, ecrits = self._lancer(_pdf(), dpi=72)
        self.assertEqual(sortie['statut'], 'done', sortie)
        self.assertEqual(job.statut, BackgroundJob.STATUT_DONE)
        self.assertEqual(job.progress_pct, 100)
        self.assertTrue(job.result_file_key)
        self.assertEqual(len(ecrits), 1)
        rendu = Attachment.objects.get(pk=sortie['attachment'])
        self.assertEqual(rendu.company_id, self.company.pk)
        self.assertEqual(rendu.filename, 'plan-%s-p1.png' % self.plan.pk)
        self.assertEqual(rendu.object_id, self.plan.pk)

    def test_rejouer_le_job_ne_televerse_pas_un_second_rendu(self):
        _job, une, _ecrits = self._lancer(_pdf(), dpi=72)
        job, deux, ecrits = self._lancer(_pdf(), dpi=72)
        self.assertEqual(deux['attachment'], une['attachment'])
        self.assertTrue(deux['reutilise'])
        self.assertEqual(ecrits, [])
        self.assertEqual(job.statut, BackgroundJob.STATUT_DONE)
        self.assertEqual(
            Attachment.objects.filter(
                object_id=self.plan.pk,
                filename='plan-%s-p1.png' % self.plan.pk).count(), 1)

    def test_une_image_passe_par_la_normalisation(self):
        self.plan.type_fichier = PlanSource.TypeFichier.IMAGE
        self.plan.save(update_fields=['type_fichier'])
        _job, sortie, ecrits = self._lancer(_png(200, 100))
        self.assertEqual(sortie['statut'], 'done', sortie)
        self.assertEqual((sortie['largeur_px'], sortie['hauteur_px']),
                         (200, 100))
        self.assertEqual(len(ecrits), 1)

    def test_sans_bibliotheque_le_job_echoue_proprement(self):
        fetch, store, _ecrits = _stockage_factice(_pdf())
        job = BackgroundJob.objects.create(
            company=self.company, user=self.user, kind=KIND_INGESTION_PLAN)
        with patch('apps.records.storage.fetch_attachment', fetch), \
                patch('apps.records.storage.store_attachment', store), \
                patch.dict(sys.modules, {'fitz': None}):
            sortie = ingerer_plan(job_id=job.pk, plan_source_id=self.plan.pk)
        job.refresh_from_db()
        self.assertEqual(sortie['statut'], 'failed')
        self.assertEqual(job.statut, BackgroundJob.STATUT_FAILED)
        self.assertIn('PyMuPDF', job.message_erreur)

    def test_un_dxf_est_refuse_avec_un_motif(self):
        self.plan.type_fichier = PlanSource.TypeFichier.DXF
        self.plan.save(update_fields=['type_fichier'])
        job, sortie, _ecrits = self._lancer(b'0\nSECTION\n')
        self.assertEqual(sortie['statut'], 'failed')
        self.assertIn('DXF', job.message_erreur)

    def test_un_support_sans_fichier_est_refuse(self):
        self.plan.attachment = None
        self.plan.save(update_fields=['attachment'])
        job, sortie, _ecrits = self._lancer(b'')
        self.assertEqual(sortie['statut'], 'failed')
        self.assertIn('aucun fichier', job.message_erreur)

    def test_un_plan_d_une_autre_societe_est_introuvable(self):
        autre = Company.objects.create(nom='Autre 71', slug='autre-71')
        job = BackgroundJob.objects.create(
            company=autre, user=self.user, kind=KIND_INGESTION_PLAN)
        sortie = ingerer_plan(job_id=job.pk, plan_source_id=self.plan.pk)
        job.refresh_from_db()
        self.assertEqual(sortie['statut'], 'failed')
        self.assertIn('introuvable', job.message_erreur)

    def test_le_dispatch_passe_par_core_jobs(self):
        """``lancer_ingestion_plan`` crée un ``BackgroundJob`` — jamais une
        file maison."""
        class TacheImmediate:
            def __init__(self):
                self.appels = []

            def delay(self, **kwargs):
                self.appels.append(kwargs)

        tache = TacheImmediate()
        with patch('apps.ao.ingestion_tasks.ingerer_plan', tache):
            job = lancer_ingestion_plan(self.plan, user=self.user, page=2)
        self.assertEqual(job.kind, KIND_INGESTION_PLAN)
        self.assertEqual(job.company_id, self.company.pk)
        self.assertEqual(job.user_id, self.user.pk)
        self.assertEqual(tache.appels[0]['plan_source_id'], self.plan.pk)
        self.assertEqual(tache.appels[0]['page'], 2)
        self.assertEqual(tache.appels[0]['job_id'], job.pk)
