"""XQHS20 — Registre des aspects & impacts environnementaux (ISO 14001 6.1.2).

Couvre :
  * le registre cote (criticite = frequence × gravite) et marque les aspects
    significatifs (>= seuil configurable) ;
  * les liens procédure/objectif tiennent (même société) ;
  * la revue due relance (pattern QHSE38) ;
  * le seed est idempotent ;
  * le scoping société.
"""
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import AspectEnvironnemental, ObjectifQhse, ProcedureQualite
from apps.qhse.selectors import aspects_environnementaux_a_revoir

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CriticiteEtSignificativiteTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs20-crit', 'Xqhs20 Crit')

    def test_criticite_est_produit_frequence_gravite(self):
        aspect = AspectEnvironnemental.objects.create(
            company=self.company, activite='Transport', aspect='CO2',
            impact='Climat', frequence=4, gravite=3)
        self.assertEqual(aspect.criticite, 12)

    def test_significatif_au_dela_du_seuil(self):
        aspect = AspectEnvironnemental.objects.create(
            company=self.company, activite='Stockage batteries',
            aspect='Fuite électrolyte', impact='Pollution sol',
            frequence=4, gravite=4, seuil_significativite=12)
        self.assertTrue(aspect.significatif)

    def test_non_significatif_sous_le_seuil(self):
        aspect = AspectEnvironnemental.objects.create(
            company=self.company, activite='Nettoyage', aspect='Eau',
            impact='Ressource en eau', frequence=1, gravite=1,
            seuil_significativite=12)
        self.assertFalse(aspect.significatif)

    def test_seuil_configurable_par_societe(self):
        aspect = AspectEnvironnemental.objects.create(
            company=self.company, activite='Pose', aspect='Déchets',
            impact='Pollution', frequence=3, gravite=2,
            seuil_significativite=5)
        self.assertTrue(aspect.significatif)  # criticite=6 >= seuil=5


class LiensProcedureObjectifTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs20-liens', 'Xqhs20 Liens')

    def test_lien_procedure_meme_societe(self):
        procedure = ProcedureQualite.objects.create(
            company=self.company, reference='PRO-ENV-1', titre='Gestion déchets',
            version=1)
        aspect = AspectEnvironnemental.objects.create(
            company=self.company, activite='Déchets', aspect='Tri',
            impact='Pollution', procedure=procedure)
        self.assertEqual(aspect.procedure_id, procedure.pk)

    def test_lien_objectif_meme_societe(self):
        objectif = ObjectifQhse.objects.create(
            company=self.company, intitule='Réduire déchets non triés')
        aspect = AspectEnvironnemental.objects.create(
            company=self.company, activite='Déchets', aspect='Tri',
            impact='Pollution', objectif=objectif)
        self.assertEqual(aspect.objectif_id, objectif.pk)

    def test_api_rejette_procedure_autre_societe(self):
        other_co = make_company('xqhs20-liens-other', 'Xqhs20 Liens Other')
        other_procedure = ProcedureQualite.objects.create(
            company=other_co, reference='PRO-X', titre='X', version=1)
        user = make_user(self.company, 'xqhs20-liens-user')
        resp = auth(user).post(
            '/api/django/qhse/aspects-environnementaux/',
            {'activite': 'A', 'aspect': 'B', 'impact': 'C',
             'procedure': other_procedure.pk}, format='json')
        self.assertEqual(resp.status_code, 400)


class AspectsARevoirTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs20-revoir', 'Xqhs20 Revoir')

    def test_sans_date_revue_est_du(self):
        aspect = AspectEnvironnemental.objects.create(
            company=self.company, activite='A', aspect='B', impact='C')
        dus = aspects_environnementaux_a_revoir(self.company)
        self.assertIn(aspect, dus)

    def test_date_revue_future_pas_du(self):
        aspect = AspectEnvironnemental.objects.create(
            company=self.company, activite='A', aspect='B', impact='C',
            date_revue=timezone.localdate() + timedelta(days=30))
        dus = aspects_environnementaux_a_revoir(self.company)
        self.assertNotIn(aspect, dus)

    def test_date_revue_passee_est_du(self):
        aspect = AspectEnvironnemental.objects.create(
            company=self.company, activite='A', aspect='B', impact='C',
            date_revue=timezone.localdate() - timedelta(days=1))
        dus = aspects_environnementaux_a_revoir(self.company)
        self.assertIn(aspect, dus)

    def test_scope_societe(self):
        other_co = make_company('xqhs20-revoir-other', 'Xqhs20 Revoir Other')
        AspectEnvironnemental.objects.create(
            company=other_co, activite='A', aspect='B', impact='C')
        dus = aspects_environnementaux_a_revoir(self.company)
        self.assertEqual(len(dus), 0)


class SeedAspectsEnvironnementauxTests(TestCase):
    def test_seed_est_idempotent(self):
        company = make_company('xqhs20-seed', 'Xqhs20 Seed')
        out = StringIO()
        call_command(
            'seed_aspects_environnementaux_solaire',
            '--company', company.slug, stdout=out)
        count_after_first = AspectEnvironnemental.objects.filter(
            company=company).count()
        self.assertGreater(count_after_first, 0)

        call_command(
            'seed_aspects_environnementaux_solaire',
            '--company', company.slug, stdout=out)
        count_after_second = AspectEnvironnemental.objects.filter(
            company=company).count()
        self.assertEqual(count_after_first, count_after_second)

    def test_seed_ne_touche_pas_cotation_existante(self):
        company = make_company('xqhs20-seed-touch', 'Xqhs20 Seed Touch')
        call_command(
            'seed_aspects_environnementaux_solaire',
            '--company', company.slug, stdout=StringIO())
        aspect = AspectEnvironnemental.objects.filter(company=company).first()
        aspect.frequence = 5
        aspect.gravite = 5
        aspect.save()

        call_command(
            'seed_aspects_environnementaux_solaire',
            '--company', company.slug, stdout=StringIO())
        aspect.refresh_from_db()
        self.assertEqual(aspect.frequence, 5)
        self.assertEqual(aspect.gravite, 5)


class AspectEnvironnementalApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs20-api', 'Xqhs20 Api')
        self.user = make_user(self.company, 'xqhs20-user')

    def test_create_pose_company_serveur(self):
        resp = auth(self.user).post(
            '/api/django/qhse/aspects-environnementaux/',
            {'activite': 'Transport', 'aspect': 'CO2', 'impact': 'Climat'},
            format='json')
        self.assertEqual(resp.status_code, 201)
        aspect = AspectEnvironnemental.objects.get(id=resp.data['id'])
        self.assertEqual(aspect.company_id, self.company.pk)

    def test_a_revoir_endpoint(self):
        AspectEnvironnemental.objects.create(
            company=self.company, activite='A', aspect='B', impact='C')
        resp = auth(self.user).get(
            '/api/django/qhse/aspects-environnementaux/a-revoir/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_isolation_societe(self):
        other_co = make_company('xqhs20-api-other', 'Xqhs20 Api Other')
        other_user = make_user(other_co, 'xqhs20-other-user')
        AspectEnvironnemental.objects.create(
            company=self.company, activite='A', aspect='B', impact='C')
        resp = auth(other_user).get(
            '/api/django/qhse/aspects-environnementaux/')
        ids = [item['id'] for item in resp.data.get('results', resp.data)]
        self.assertEqual(len(ids), 0)
