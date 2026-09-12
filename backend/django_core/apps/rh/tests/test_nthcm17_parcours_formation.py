"""Tests NTHCM17 — parcours de formation structurés (modules ordonnés).

Couvre :
* un parcours de 4 étapes (2 quiz + 1 session + 1 document KB) ;
* la progression se met à jour à CHAQUE étape cochée, ``pourcentage`` exact ;
* 100 % pose ``date_completion`` (horloge FIGÉE — aucune date « du jour »
  lue en vrai, cf. `check_test_determinism`) ;
* cocher deux fois la même étape est un no-op (idempotence) ;
* une étape d'un AUTRE parcours est refusée (400) ;
* le CRUD est scopé société.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    DossierEmploye,
    EtapeParcours,
    ParcoursFormation,
    ProgressionParcours,
    QuizFormation,
    SessionFormation,
)

User = get_user_model()

JOUR_FIGE = date(2026, 3, 17)


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


def lignes(reponse):
    donnees = reponse.data
    return donnees['results'] if isinstance(donnees, dict) else donnees


class ParcoursFormationTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm17-a', 'A')
        self.rh = make_user(self.co, 'nthcm17-rh')
        self.api = auth(self.rh)
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='P-001', nom='Idrissi', prenom='Imane')
        self.parcours = ParcoursFormation.objects.create(
            company=self.co, titre='Intégration poseur PV',
            obligatoire=True)
        self.quiz1 = QuizFormation.objects.create(
            company=self.co, intitule='Sécurité chantier')
        self.quiz2 = QuizFormation.objects.create(
            company=self.co, intitule='Électricité BT')
        self.session = SessionFormation.objects.create(
            company=self.co, intitule='Pose de modules',
            date_debut=date(2026, 2, 2))
        self.etapes = [
            EtapeParcours.objects.create(
                company=self.co, parcours=self.parcours, ordre=1,
                titre='Quiz sécurité', type_contenu='quiz',
                quiz_ref=self.quiz1),
            EtapeParcours.objects.create(
                company=self.co, parcours=self.parcours, ordre=2,
                titre='Quiz électricité', type_contenu='quiz',
                quiz_ref=self.quiz2),
            EtapeParcours.objects.create(
                company=self.co, parcours=self.parcours, ordre=3,
                titre='Session pose', type_contenu='session',
                session_ref=self.session),
            EtapeParcours.objects.create(
                company=self.co, parcours=self.parcours, ordre=4,
                titre='Notice constructeur', type_contenu='document_kb',
                document_kb_id=42),
        ]
        self.progression = ProgressionParcours.objects.create(
            company=self.co, parcours=self.parcours, employe=self.employe)

    # ── progression ───────────────────────────────────────────────────────
    def test_pourcentage_progresse_etape_par_etape(self):
        attendus = [25, 50, 75, 100]
        for etape, attendu in zip(self.etapes, attendus):
            services.marquer_etape_parcours(
                self.progression, etape, aujourdhui=JOUR_FIGE)
            self.progression.refresh_from_db()
            self.assertEqual(self.progression.pourcentage, attendu)

    def test_completion_pose_la_date_et_le_statut(self):
        for etape in self.etapes[:3]:
            services.marquer_etape_parcours(
                self.progression, etape, aujourdhui=JOUR_FIGE)
        self.progression.refresh_from_db()
        self.assertEqual(self.progression.statut, 'en_cours')
        self.assertIsNone(self.progression.date_completion)

        services.marquer_etape_parcours(
            self.progression, self.etapes[3], aujourdhui=JOUR_FIGE)
        self.progression.refresh_from_db()
        self.assertEqual(self.progression.statut, 'termine')
        self.assertEqual(self.progression.pourcentage, 100)
        self.assertEqual(self.progression.date_completion, JOUR_FIGE)

    def test_cocher_deux_fois_est_un_no_op(self):
        services.marquer_etape_parcours(
            self.progression, self.etapes[0], aujourdhui=JOUR_FIGE)
        services.marquer_etape_parcours(
            self.progression, self.etapes[0], aujourdhui=JOUR_FIGE)
        self.progression.refresh_from_db()
        self.assertEqual(self.progression.etapes_completees.count(), 1)
        self.assertEqual(self.progression.pourcentage, 25)

    def test_etape_facultative_ne_retient_pas_la_completion(self):
        # La 4e devient facultative : les 3 exigées suffisent à terminer,
        # mais le pourcentage reste 75 % (3 étapes sur 4).
        self.etapes[3].obligatoire_pour_completer = False
        self.etapes[3].save(update_fields=['obligatoire_pour_completer'])
        for etape in self.etapes[:3]:
            services.marquer_etape_parcours(
                self.progression, etape, aujourdhui=JOUR_FIGE)
        self.progression.refresh_from_db()
        self.assertEqual(self.progression.statut, 'termine')
        self.assertEqual(self.progression.pourcentage, 75)

    def test_parcours_sans_etape_reste_a_zero(self):
        vide = ParcoursFormation.objects.create(
            company=self.co, titre='Vide')
        progression = ProgressionParcours.objects.create(
            company=self.co, parcours=vide, employe=self.employe)
        services.recalculer_progression_parcours(
            progression, aujourdhui=JOUR_FIGE)
        progression.refresh_from_db()
        self.assertEqual(progression.pourcentage, 0)
        self.assertEqual(progression.statut, 'non_commence')

    def test_devalider_remet_la_date_de_completion_a_none(self):
        for etape in self.etapes:
            services.marquer_etape_parcours(
                self.progression, etape, aujourdhui=JOUR_FIGE)
        services.devalider_etape_parcours(
            self.progression, self.etapes[0], aujourdhui=JOUR_FIGE)
        self.progression.refresh_from_db()
        self.assertEqual(self.progression.statut, 'en_cours')
        self.assertIsNone(self.progression.date_completion)

    def test_etape_dun_autre_parcours_refusee(self):
        autre_parcours = ParcoursFormation.objects.create(
            company=self.co, titre='Autre')
        intruse = EtapeParcours.objects.create(
            company=self.co, parcours=autre_parcours, ordre=1,
            titre='Intruse', type_contenu='lien_externe',
            url_externe='https://exemple.ma/doc')
        with self.assertRaises(ValidationError):
            services.marquer_etape_parcours(self.progression, intruse)

    # ── modèle ────────────────────────────────────────────────────────────
    def test_etape_quiz_sans_quiz_refusee(self):
        etape = EtapeParcours(
            company=self.co, parcours=self.parcours, ordre=9,
            titre='Quiz orphelin', type_contenu='quiz')
        with self.assertRaises(ValidationError):
            etape.full_clean()

    def test_etape_lien_externe_sans_url_refusee(self):
        etape = EtapeParcours(
            company=self.co, parcours=self.parcours, ordre=9,
            titre='Lien vide', type_contenu='lien_externe')
        with self.assertRaises(ValidationError):
            etape.full_clean()

    # ── API ───────────────────────────────────────────────────────────────
    def test_api_completer_etape(self):
        reponse = self.api.post(
            f'/api/django/rh/progressions-parcours/'
            f'{self.progression.id}/completer-etape/',
            {'etape': self.etapes[0].id}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.data['pourcentage'], 25)
        self.assertEqual(reponse.data['statut'], 'en_cours')

    def test_api_completer_etape_inconnue_refusee(self):
        reponse = self.api.post(
            f'/api/django/rh/progressions-parcours/'
            f'{self.progression.id}/completer-etape/',
            {'etape': 999999}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.content)

    def test_api_liste_parcours_scopee_societe(self):
        autre = make_company('nthcm17-b', 'B')
        ParcoursFormation.objects.create(company=autre, titre='Chez le voisin')
        reponse = self.api.get('/api/django/rh/parcours-formation/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        titres = [ligne['titre'] for ligne in lignes(reponse)]
        self.assertEqual(titres, ['Intégration poseur PV'])

    def test_api_creation_parcours_pose_la_societe(self):
        reponse = self.api.post(
            '/api/django/rh/parcours-formation/',
            {'titre': 'Habilitation BR', 'obligatoire': True},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        cree = ParcoursFormation.objects.get(pk=reponse.data['id'])
        self.assertEqual(cree.company_id, self.co.id)

    def test_api_avancement_non_ecrivable(self):
        reponse = self.api.patch(
            f'/api/django/rh/progressions-parcours/{self.progression.id}/',
            {'pourcentage': 100, 'statut': 'termine'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.progression.refresh_from_db()
        self.assertEqual(self.progression.pourcentage, 0)
        self.assertEqual(self.progression.statut, 'non_commence')
