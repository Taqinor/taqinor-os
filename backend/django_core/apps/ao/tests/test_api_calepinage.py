"""AOF61 — l'API de calepinage : calcul borné, job de fond, cache tenant.

Ce que ces tests VERROUILLENT :

* l'endpoint est SCOPÉ SOCIÉTÉ — la toiture d'un autre tenant rend 404 (pas
  403 : un 403 confirmerait son existence), et le job d'un autre tenant aussi ;
* un payload invalide rend un **400 NOMMÉ** (le champ fautif est dit) ;
* le second appel identique répond DEPUIS LE CACHE — prouvé par un compteur
  d'appels au moteur, pas par la durée ;
* au-delà du budget de calcul, l'API rend **202** et la consigne asynchrone
  au lieu de faire attendre ;
* le calcul lourd part par ``core.jobs.submit`` (``BackgroundJob``), jamais
  par une file maison, et son résultat se relit par ``resultat/<job_id>/``.

Run :
    python manage.py test apps.ao.tests.test_api_calepinage -v2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.calepinage_service import MoteurCalepinage
from apps.ao.calepinage_tasks import calculer_calepinage
from apps.ao.models import (
    AppelOffre, BatimentAO, KitCalepinage, ToitureAO, VarianteCalepinage,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company
from core.calepinage.perf import BudgetCalcul
from core.calepinage.version import VERSION_MOTEUR
from core.models import BackgroundJob

User = get_user_model()

CALCULER = '/api/django/ao/calepinage/calculer/'
LANCER = '/api/django/ao/calepinage/lancer/'
RESULTAT = '/api/django/ao/calepinage/resultat/%s/'

PARAMS = {
    'rive_laterale_m': 0.35,
    'rive_extremite_m': 0.35,
    'allee_min_m': 0.60,
    'degagements_par_provenance_m': {'MESURE': 0.30, 'DEVINE': 0.50},
    'kits_autorises': ['AO-TABLE-PORTRAIT'],
    'pas_recherche_m': 0.01,
}


class MoteurCompteur(MoteurCalepinage):
    """Moteur réel + compteur GLOBAL — la preuve du cache est un COMPTE."""

    total = 0

    def calculer(self, *args, **kwargs):
        MoteurCompteur.total += 1
        return super().calculer(*args, **kwargs)


class TacheImmediate:
    """Substitut de la tâche Celery : ``.delay()`` exécute tout de suite.

    Les tests ne parlent à AUCUN broker. Le CHEMIN testé reste le vrai —
    ``core.jobs.submit`` crée le ``BackgroundJob`` et appelle ``.delay`` — seul
    le transport est court-circuité.
    """

    def __init__(self):
        self.appels = []

    def delay(self, **kwargs):
        self.appels.append(kwargs)
        return calculer_calepinage(**kwargs)


class BaseApiCalepinage(TestCase):
    def setUp(self):
        cache.clear()
        MoteurCompteur.total = 0
        self.company = Company.objects.create(nom='AOF61 Co', slug='aof61-co')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof61_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-61-1', objet='API calepinage')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='05H',
            contour_local_m=[[0, 0], [30, 0], [30, 16], [0, 16]],
            parametres_calepinage=dict(PARAMS))
        self.kit = KitCalepinage.objects.create(
            company=self.company, code='AO-TABLE-PORTRAIT',
            libelle='Table dos-à-dos portrait', modules_par_kit=2,
            pas_rangee_m=Decimal('1.134'), longueur_pente_m=Decimal('2.382'),
            faitage_m=Decimal('0.098'), puissance_module_w=625,
            inclinaison_deg=Decimal('15.00'))
        self.kit.appliquer_emprise()
        self.kit.save()

    def _autre_societe(self):
        autre = Company.objects.create(nom='Autre AOF61', slug='autre-aof61')
        ao = AppelOffre.objects.create(company=autre, reference='AO-X',
                                       objet='Ailleurs')
        batiment = BatimentAO.objects.create(company=autre, appel_offre=ao,
                                             code='Z')
        toiture = ToitureAO.objects.create(
            company=autre, batiment=batiment,
            contour_local_m=[[0, 0], [10, 0], [10, 10], [0, 10]],
            parametres_calepinage=dict(PARAMS))
        return autre, toiture


class LeCalculSynchrone(BaseApiCalepinage):
    def test_calcul_par_toiture(self):
        with patch('apps.ao.calepinage_views.MoteurCalepinage',
                   MoteurCompteur):
            reponse = self.api.post(CALCULER, {'toiture': self.toiture.pk},
                                    format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertGreater(reponse.data['total_modules'], 0)
        self.assertEqual(reponse.data['version_moteur'], VERSION_MOTEUR)
        self.assertTrue(reponse.data['hash_entree'])
        self.assertFalse(reponse.data['depuis_cache'])
        self.assertTrue(reponse.data['preuve']['optimal'])

    def test_le_second_appel_identique_vient_du_cache(self):
        with patch('apps.ao.calepinage_views.MoteurCalepinage',
                   MoteurCompteur):
            une = self.api.post(CALCULER, {'toiture': self.toiture.pk},
                                format='json')
            deux = self.api.post(CALCULER, {'toiture': self.toiture.pk},
                                 format='json')
        self.assertEqual(une.status_code, 200)
        self.assertEqual(deux.status_code, 200)
        self.assertFalse(une.data['depuis_cache'])
        self.assertTrue(deux.data['depuis_cache'])
        self.assertEqual(deux.data['total_modules'], une.data['total_modules'])
        # UN SEUL passage par le moteur pour deux appels identiques.
        self.assertEqual(MoteurCompteur.total, 1)

    def test_le_cache_est_invalide_par_un_bump_de_version(self):
        with patch('apps.ao.calepinage_views.MoteurCalepinage',
                   MoteurCompteur):
            self.api.post(CALCULER, {'toiture': self.toiture.pk},
                          format='json')
            self.assertEqual(MoteurCompteur.total, 1)
            with patch('apps.ao.calepinage_service.VERSION_MOTEUR', '9.9.9'):
                self.api.post(CALCULER, {'toiture': self.toiture.pk},
                              format='json')
        # la version est DANS la clé : l'ancien cache est inatteignable.
        self.assertEqual(MoteurCompteur.total, 2)

    def test_le_cache_ne_traverse_jamais_une_societe(self):
        """Le MÊME document, calculé par deux sociétés, passe DEUX fois au
        moteur : la clé de cache est préfixée ``t:{company_id}:``."""
        from apps.ao import calepinage_io

        document = calepinage_io.document_entree(self.toiture)
        autre, _toiture = self._autre_societe()
        role = Role.objects.create(company=autre, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        voisin = User.objects.create_user(username='voisin61', password='x',
                                          company=autre, role=role)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(voisin)}')
        with patch('apps.ao.calepinage_views.MoteurCalepinage',
                   MoteurCompteur):
            mienne = self.api.post(CALCULER, {'entree': document},
                                   format='json')
            sienne = client.post(CALCULER, {'entree': document},
                                 format='json')
        self.assertEqual(mienne.status_code, 200, mienne.data)
        self.assertEqual(sienne.status_code, 200, sienne.data)
        self.assertFalse(sienne.data['depuis_cache'])
        self.assertEqual(MoteurCompteur.total, 2)

    def test_une_toiture_d_une_autre_societe_rend_404(self):
        _autre, toiture = self._autre_societe()
        reponse = self.api.post(CALCULER, {'toiture': toiture.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_au_dela_du_budget_202_et_consigne_asynchrone(self):
        with patch('apps.ao.calepinage_views.BUDGET',
                   BudgetCalcul(seuil_synchrone_ms=0.001)):
            reponse = self.api.post(CALCULER, {'toiture': self.toiture.pk},
                                    format='json')
        self.assertEqual(reponse.status_code, 202, reponse.data)
        self.assertIn('asynchrone', reponse.data)
        self.assertIn('cout_estime', reponse.data)
        self.assertGreater(reponse.data['cout_estime']['appels'], 0)


class LesPayloadsInvalides(BaseApiCalepinage):
    def test_ni_toiture_ni_entree(self):
        reponse = self.api.post(CALCULER, {}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('toiture', reponse.data)

    def test_toiture_et_entree_ensemble(self):
        reponse = self.api.post(
            CALCULER, {'toiture': self.toiture.pk, 'entree': {'a': 1}},
            format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('entree', reponse.data)

    def test_document_sans_version_de_schema(self):
        reponse = self.api.post(CALCULER, {'entree': {'repere': 'X'}},
                                format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('entree', reponse.data)

    def test_params_qui_ne_sont_pas_un_objet(self):
        reponse = self.api.post(
            CALCULER, {'toiture': self.toiture.pk, 'params': [1, 2]},
            format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('params', reponse.data)

    def test_toiture_sans_enveloppe_400_nomme(self):
        self.toiture.contour_local_m = []
        self.toiture.save(update_fields=['contour_local_m'])
        reponse = self.api.post(CALCULER, {'toiture': self.toiture.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('entree', reponse.data)


class LeJobDeFond(BaseApiCalepinage):
    def test_lancer_cree_un_background_job_et_calcule(self):
        tache = TacheImmediate()
        with patch('apps.ao.calepinage_views.calculer_calepinage', tache):
            reponse = self.api.post(
                LANCER, {'toiture': self.toiture.pk, 'persister': True},
                format='json')
        self.assertEqual(reponse.status_code, 202, reponse.data)
        job = BackgroundJob.objects.get(pk=reponse.data['id'])
        self.assertEqual(job.kind, 'ao_calepinage')
        self.assertEqual(job.company_id, self.company.pk)
        self.assertEqual(job.user_id, self.user.pk)
        self.assertEqual(job.statut, BackgroundJob.STATUT_DONE)
        self.assertEqual(VarianteCalepinage.objects.count(), 1)

    def test_le_resultat_se_relit_par_son_job(self):
        tache = TacheImmediate()
        with patch('apps.ao.calepinage_views.calculer_calepinage', tache):
            lance = self.api.post(LANCER, {'toiture': self.toiture.pk},
                                  format='json')
        reponse = self.api.get(RESULTAT % lance.data['id'])
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['statut'], BackgroundJob.STATUT_DONE)
        self.assertIsNotNone(reponse.data['resultat'])
        self.assertGreater(reponse.data['resultat']['total_modules'], 0)

    def test_un_job_d_une_autre_societe_rend_404(self):
        autre, _toiture = self._autre_societe()
        job = BackgroundJob.objects.create(
            company=autre, user=self.user, kind='ao_calepinage')
        reponse = self.api.get(RESULTAT % job.pk)
        self.assertEqual(reponse.status_code, 404)

    def test_lancer_sur_une_toiture_etrangere_rend_404_tout_de_suite(self):
        _autre, toiture = self._autre_societe()
        tache = TacheImmediate()
        with patch('apps.ao.calepinage_views.calculer_calepinage', tache):
            reponse = self.api.post(LANCER, {'toiture': toiture.pk},
                                    format='json')
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(tache.appels, [])
        self.assertEqual(BackgroundJob.objects.count(), 0)

    def test_persister_sans_toiture_est_refuse(self):
        reponse = self.api.post(
            LANCER, {'entree': {'schema_version': 1}, 'persister': True},
            format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('persister', reponse.data)

    def test_un_job_en_echec_porte_son_motif(self):
        self.toiture.contour_local_m = []
        self.toiture.save(update_fields=['contour_local_m'])
        tache = TacheImmediate()
        with patch('apps.ao.calepinage_views.calculer_calepinage', tache):
            lance = self.api.post(LANCER, {'toiture': self.toiture.pk},
                                  format='json')
        reponse = self.api.get(RESULTAT % lance.data['id'])
        self.assertEqual(reponse.data['statut'], BackgroundJob.STATUT_FAILED)
        self.assertIn('enveloppe', reponse.data['message_erreur'])

    def test_rejouer_la_tache_ne_cree_pas_une_seconde_variante(self):
        tache = TacheImmediate()
        with patch('apps.ao.calepinage_views.calculer_calepinage', tache):
            self.api.post(LANCER,
                          {'toiture': self.toiture.pk, 'persister': True},
                          format='json')
        premier = dict(tache.appels[0])
        calculer_calepinage(**premier)
        self.assertEqual(VarianteCalepinage.objects.count(), 1)


class LesGardesDAcces(BaseApiCalepinage):
    def test_un_anonyme_est_refuse(self):
        client = APIClient()
        reponse = client.post(CALCULER, {'toiture': self.toiture.pk},
                              format='json')
        self.assertIn(reponse.status_code, (401, 403))

    def test_un_role_sans_permission_ao_est_refuse(self):
        role = Role.objects.create(company=self.company, nom='Technicien',
                                   permissions=['stock_voir'])
        user = User.objects.create_user(username='tech61', password='x',
                                        company=self.company, role=role)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        reponse = client.post(CALCULER, {'toiture': self.toiture.pk},
                              format='json')
        self.assertEqual(reponse.status_code, 403)
