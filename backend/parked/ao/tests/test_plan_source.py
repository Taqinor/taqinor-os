"""AOF20 — ``PlanSource`` : les 3 portes d'entrée sont UN CHAMP.

Plan fourni (PDF/DXF/image calibré à deux points), tracé manuel et reprise
depuis un lecteur de cartes produisent le MÊME objet et ouvrent le MÊME
éditeur : c'est ``origine`` qui les distingue, pas trois chemins de données —
trois chemins signifieraient trois éditeurs à maintenir.

Invariants verrouillés :
  1. l'échelle est RECALCULÉE dès qu'un point de calibration bouge (une
     échelle figée fausserait silencieusement toutes les cotes déduites) ;
  2. plusieurs supports sont CUMULABLES sur une même toiture (« plan fourni
     MAIS à compléter ») ;
  3. le fichier passe par ``records.Attachment`` — aucun ``FileField`` neuf
     (garde ARC26, ``check_platform.py``) ;
  4. un même fichier reçu deux fois RÉUTILISE l'attachement (empreinte
     SHA-256) au lieu d'en stocker un doublon ;
  5. ce rangement a une PORTE D'ENTRÉE HTTP (``upload``, multipart) — le
     service existait mais n'avait aucun appelant, donc aucun plan fourni ne
     pouvait entrer par l'API.

Run :
    python manage.py test apps.ao.tests.test_plan_source -v2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models as dj_models
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import AppelOffre, BatimentAO, PlanSource, ToitureAO
from apps.records.models import Attachment
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/plans-source/'

#: Un PDF minimal : ce sont les octets magiques qui décident du format côté
#: stockage partagé, jamais l'extension du nom de fichier.
PDF = b'%PDF-1.4\nplan de toiture 05H\n%%EOF\n'


def _stockage_factice(mime='application/pdf'):
    """Remplace MinIO : compte les téléversements RÉELS, sans réseau."""
    ecrits = []

    def store(fichier, audio=False, company=None):
        donnees = fichier.read()
        ecrits.append(donnees)
        return ({'file_key': 'attachments/%s/plan-%d'
                 % (getattr(company, 'id', 0), len(ecrits)),
                 'filename': getattr(fichier, 'name', 'plan.pdf'),
                 'size': len(donnees), 'mime': mime}, None)

    return store, ecrits


class TestModelePlanSource(SimpleTestCase):
    def test_les_trois_portes_sont_un_champ(self):
        valeurs = {v for v, _ in PlanSource.Origine.choices}
        self.assertEqual(valeurs, {'plan_fourni', 'trace_manuel', 'carte'})

    def test_aucun_filefield(self):
        """ARC26 — la pièce passe par ``records.Attachment``."""
        for champ in PlanSource._meta.local_fields:
            self.assertNotIsInstance(champ, dj_models.FileField, champ.name)
        attachment = PlanSource._meta.get_field('attachment')
        self.assertEqual(
            attachment.remote_field.model._meta.label_lower,
            'records.attachment')

    def test_les_noms_portent_les_unites(self):
        noms = {f.name for f in PlanSource._meta.local_fields}
        for attendu in ('calib_point_a_px', 'calib_point_b_px',
                        'calib_distance_reelle_m', 'echelle_m_par_px',
                        'origine_px'):
            self.assertIn(attendu, noms, attendu)


class TestCalibration(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF20 Co', slug='aof20-co')
        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-20-1', objet='Plans')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=ao, code='A')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)

    def _plan(self, **kwargs):
        return PlanSource.objects.create(
            company=self.company, toiture=self.toiture, **kwargs)

    def test_echelle_derivee_des_deux_points(self):
        plan = self._plan(
            calib_point_a_px=[0, 0], calib_point_b_px=[100, 0],
            calib_distance_reelle_m=Decimal('10.000'))
        plan.recalculer_echelle()
        self.assertEqual(plan.echelle_m_par_px, Decimal('0.10000000'))
        self.assertEqual(plan.etat, PlanSource.Etat.CALIBRE)

    def test_echelle_recalculee_quand_un_point_bouge(self):
        plan = self._plan(
            calib_point_a_px=[0, 0], calib_point_b_px=[100, 0],
            calib_distance_reelle_m=Decimal('10.000'))
        services.recalibrer_plan_source(plan)
        self.assertEqual(plan.echelle_m_par_px, Decimal('0.10000000'))
        services.recalibrer_plan_source(plan, point_b_px=[200, 0])
        plan.refresh_from_db()
        self.assertEqual(plan.echelle_m_par_px, Decimal('0.05000000'))

    def test_calibration_partielle_ne_produit_pas_d_echelle(self):
        plan = self._plan(calib_point_a_px=[0, 0])
        plan.recalculer_echelle()
        self.assertIsNone(plan.echelle_m_par_px)
        self.assertEqual(plan.etat, PlanSource.Etat.BRUT)

    def test_distance_diagonale(self):
        plan = self._plan(
            calib_point_a_px=[0, 0], calib_point_b_px=[30, 40],
            calib_distance_reelle_m=Decimal('5.000'))
        self.assertAlmostEqual(plan.distance_calibration_px, 50.0)
        plan.recalculer_echelle()
        self.assertEqual(plan.echelle_m_par_px, Decimal('0.10000000'))

    def test_plusieurs_supports_cumulables(self):
        """« Plan fourni MAIS à compléter » : un plan + des tracés additifs."""
        self._plan(origine=PlanSource.Origine.PLAN_FOURNI,
                   type_fichier=PlanSource.TypeFichier.PDF)
        self._plan(origine=PlanSource.Origine.TRACE_MANUEL)
        self._plan(origine=PlanSource.Origine.CARTE)
        self.assertEqual(self.toiture.plans_source.count(), 3)

    def test_rattachement_obligatoire(self):
        plan = PlanSource(company=self.company)
        with self.assertRaises(ValidationError) as ctx:
            plan.clean()
        self.assertIn('toiture', ctx.exception.message_dict)

    def test_rattachement_au_batiment_suffit(self):
        batiment = self.toiture.batiment
        PlanSource(company=self.company, batiment=batiment).clean()


class TestApiPlanSource(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF20 API', slug='aof20-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof20_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-20-API', objet='API')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=ao, code='B')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)

    def test_creation_calibre_cote_serveur(self):
        r = self.api.post(URL, {
            'toiture': self.toiture.id, 'origine': 'plan_fourni',
            'type_fichier': 'pdf', 'calib_point_a_px': [0, 0],
            'calib_point_b_px': [100, 0], 'calib_distance_reelle_m': '10.000',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        plan = PlanSource.objects.get(id=r.data['id'])
        self.assertEqual(plan.echelle_m_par_px, Decimal('0.10000000'))
        self.assertEqual(plan.etat, PlanSource.Etat.CALIBRE)
        self.assertEqual(plan.company_id, self.company.id)

    def test_modification_d_un_point_recalcule_l_echelle(self):
        r = self.api.post(URL, {
            'toiture': self.toiture.id, 'calib_point_a_px': [0, 0],
            'calib_point_b_px': [100, 0], 'calib_distance_reelle_m': '10.000',
        }, format='json')
        plan_id = r.data['id']
        r2 = self.api.patch(f'{URL}{plan_id}/',
                            {'calib_point_b_px': [50, 0]}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        plan = PlanSource.objects.get(id=plan_id)
        self.assertEqual(plan.echelle_m_par_px, Decimal('0.20000000'))

    def test_rattachement_absent_refuse(self):
        r = self.api.post(URL, {'origine': 'trace_manuel'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('toiture', r.data)

    def test_echelle_non_modifiable_depuis_le_corps(self):
        """``echelle_m_par_px`` est DÉRIVÉE : une saisie est ignorée."""
        r = self.api.post(URL, {
            'toiture': self.toiture.id, 'calib_point_a_px': [0, 0],
            'calib_point_b_px': [100, 0], 'calib_distance_reelle_m': '10.000',
            'echelle_m_par_px': '99.00000000',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        plan = PlanSource.objects.get(id=r.data['id'])
        self.assertEqual(plan.echelle_m_par_px, Decimal('0.10000000'))

    def test_filtre_par_toiture_et_par_origine(self):
        PlanSource.objects.create(
            company=self.company, toiture=self.toiture,
            origine=PlanSource.Origine.CARTE)
        PlanSource.objects.create(
            company=self.company, toiture=self.toiture,
            origine=PlanSource.Origine.TRACE_MANUEL)
        r = self.api.get(URL, {'toiture': self.toiture.id,
                               'origine': 'carte'})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(len(lignes), 1)

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF20 X', slug='aof20-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-20-X', objet='X')
        batiment = BatimentAO.objects.create(
            company=autre, appel_offre=ao, code='X')
        toiture = ToitureAO.objects.create(company=autre, batiment=batiment)
        PlanSource.objects.create(company=autre, toiture=toiture)
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(lignes, [])


class TestApiUploadPlanSource(TestCase):
    """AOF20 — ``POST /plans-source/{id}/upload/`` (multipart).

    Constat qui motive ces tests : ``attacher_fichier_plan_source`` rangeait
    déjà proprement le binaire (empreinte + dédup + ``records.Attachment``),
    mais AUCUNE route ne l'appelait — l'écran d'import n'avait donc pas
    d'endpoint et le plan fourni ne pouvait pas entrer.
    """

    def setUp(self):
        self.company = Company.objects.create(nom='AOF20 Up', slug='aof20-up')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof20_up', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-20-UP', objet='Upload')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=ao, code='U')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment)
        self.plan = self._plan()

    def _plan(self, company=None, toiture=None):
        return PlanSource.objects.create(
            company=company or self.company,
            toiture=toiture or self.toiture,
            origine=PlanSource.Origine.PLAN_FOURNI,
            type_fichier=PlanSource.TypeFichier.PDF)

    @staticmethod
    def _fichier(contenu=PDF, nom='plan.pdf'):
        return SimpleUploadedFile(nom, contenu, content_type='application/pdf')

    def _upload(self, plan, store, contenu=PDF, nom='plan.pdf'):
        with patch('apps.records.storage.store_attachment', store):
            return self.api.post(
                f'{URL}{plan.id}/upload/',
                {'fichier': self._fichier(contenu, nom)}, format='multipart')

    def test_un_pdf_produit_un_attachment_reference(self):
        store, ecrits = _stockage_factice()
        r = self._upload(self.plan, store)
        self.assertEqual(r.status_code, 200, r.data)
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.attachment_id)
        self.assertEqual(r.data['attachment'], self.plan.attachment_id)
        self.assertEqual(self.plan.empreinte_sha256,
                         services.empreinte_fichier(PDF))
        attachement = Attachment.objects.get(pk=self.plan.attachment_id)
        self.assertEqual(attachement.company_id, self.company.id)
        self.assertEqual(attachement.object_id, self.plan.pk)
        self.assertEqual(attachement.uploaded_by_id, self.user.id)
        self.assertEqual(len(ecrits), 1)

    def test_un_second_envoi_du_meme_contenu_reutilise_l_attachment(self):
        """Dédup : l'erratum re-téléversé ne stocke PAS un second binaire."""
        store, ecrits = _stockage_factice()
        premier = self._upload(self.plan, store)
        second_plan = self._plan()
        second = self._upload(second_plan, store)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data['attachment'],
                         premier.data['attachment'])
        self.assertEqual(len(ecrits), 1)
        self.assertEqual(
            Attachment.objects.filter(company=self.company).count(), 1)

    def test_un_contenu_different_stocke_bien_un_second_attachment(self):
        """Contrôle négatif : la dédup ne confond pas deux plans distincts."""
        store, ecrits = _stockage_factice()
        premier = self._upload(self.plan, store)
        autre_plan = self._plan()
        second = self._upload(autre_plan, store,
                              contenu=b'%PDF-1.4\nplan 06H\n%%EOF\n')
        self.assertEqual(second.status_code, 200, second.data)
        self.assertNotEqual(second.data['attachment'],
                            premier.data['attachment'])
        self.assertEqual(len(ecrits), 2)

    def test_l_empreinte_n_est_pas_saisissable_depuis_le_corps(self):
        """``empreinte_sha256`` est POSÉE côté serveur, jamais reçue."""
        store, _ecrits = _stockage_factice()
        with patch('apps.records.storage.store_attachment', store):
            r = self.api.post(
                f'{URL}{self.plan.id}/upload/',
                {'fichier': self._fichier(),
                 'empreinte_sha256': 'a' * 64}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.empreinte_sha256,
                         services.empreinte_fichier(PDF))

    def test_sans_fichier_l_appel_est_un_400_motive(self):
        r = self.api.post(f'{URL}{self.plan.id}/upload/',
                          {'fourni_par': 'Le maître d\'ouvrage'},
                          format='multipart')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('fichier', r.data)
        self.plan.refresh_from_db()
        self.assertIsNone(self.plan.attachment_id)

    def test_un_format_refuse_par_le_stockage_donne_un_400_motive(self):
        """Un DXF n'est pas dans l'allowlist du stockage PARTAGÉ.

        Le refus vient de ``records.storage`` (octets magiques), AVANT tout
        réseau : le motif remonte en français, jamais un 500 muet. Élargir
        cette allowlist est une décision de ``apps/records``, pas d'``ao``.
        """
        r = self.api.post(
            f'{URL}{self.plan.id}/upload/',
            {'fichier': SimpleUploadedFile(
                'toiture.dxf', b'0\nSECTION\n2\nHEADER\n',
                content_type='application/dxf')},
            format='multipart')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('fichier', r.data)
        self.assertIn('Format non supporté', str(r.data['fichier']))
        self.plan.refresh_from_db()
        self.assertIsNone(self.plan.attachment_id)
        self.assertFalse(Attachment.objects.exists())

    def test_le_plan_d_une_autre_societe_est_introuvable(self):
        autre = Company.objects.create(nom='AOF20 UX', slug='aof20-ux')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-20-UX', objet='X')
        batiment = BatimentAO.objects.create(
            company=autre, appel_offre=ao, code='X')
        toiture = ToitureAO.objects.create(company=autre, batiment=batiment)
        plan = self._plan(company=autre, toiture=toiture)
        store, ecrits = _stockage_factice()
        r = self._upload(plan, store)
        self.assertEqual(r.status_code, 404, r.data)
        self.assertEqual(ecrits, [])
        plan.refresh_from_db()
        self.assertIsNone(plan.attachment_id)


class TestEmpreinteFichier(TestCase):
    def test_empreinte_stable(self):
        self.assertEqual(
            services.empreinte_fichier(b'planche 05H'),
            services.empreinte_fichier(b'planche 05H'))
        self.assertNotEqual(
            services.empreinte_fichier(b'planche 05H'),
            services.empreinte_fichier(b'planche 06H'))
