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
     SHA-256) au lieu d'en stocker un doublon.

Run :
    python manage.py test apps.ao.tests.test_plan_source -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models as dj_models
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import AppelOffre, BatimentAO, PlanSource, ToitureAO
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/plans-source/'


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


class TestEmpreinteFichier(TestCase):
    def test_empreinte_stable(self):
        self.assertEqual(
            services.empreinte_fichier(b'planche 05H'),
            services.empreinte_fichier(b'planche 05H'))
        self.assertNotEqual(
            services.empreinte_fichier(b'planche 05H'),
            services.empreinte_fichier(b'planche 06H'))
