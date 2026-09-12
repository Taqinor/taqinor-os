"""NTSRV43 — Import CSV en masse de catégories/compétences requises.

Critère d'acceptation : un CSV avec une compétence RH inexistante rapporte une
erreur de LIGNE précise, jamais un échec silencieux global.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv43 -v 2
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import Competence
from apps.rh.selectors import competences_par_code
from apps.sav.imports import CIBLE, importer, previsualiser
from apps.sav.models import CategorieTicket

User = get_user_model()

URL = '/api/django/sav/categories-ticket/importer-competences/'


def csv_octets(lignes):
    return ('\n'.join(lignes) + '\n').encode('utf-8')


class NTSRV43ImportTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv43', defaults={'nom': 'Sav Co NTSRV43'})
        self.admin = User.objects.create_user(
            username='ntsrv43_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.competence = Competence.objects.create(
            company=self.company, code='raccordement_ac',
            libelle='Raccordement AC',
            domaine=Competence.Domaine.RACCORDEMENT_AC)
        self.competence2 = Competence.objects.create(
            company=self.company, code='mes_onduleur',
            libelle='MES onduleur',
            domaine=Competence.Domaine.MES_ONDULEUR)
        self.categorie = CategorieTicket.objects.create(
            company=self.company, libelle='Onduleur Huawei')

    # ── Critère d'acceptation ────────────────────────────────────────────
    def test_competence_inconnue_rapportee_ligne_par_ligne(self):
        octets = csv_octets([
            'categorie,competence,niveau',
            'Onduleur Huawei,raccordement_ac,2',
            'Onduleur Huawei,competence_fantome,2',
            'Onduleur Huawei,mes_onduleur,2',
        ])
        recap = importer(self.company, octets, 'matrice.csv')
        self.assertEqual(recap['total_lignes'], 3)
        self.assertEqual(recap['rejetees'], 1)
        self.assertEqual(recap['valides'], 2)
        fautive = [ligne for ligne in recap['lignes'] if ligne['erreurs']]
        self.assertEqual(len(fautive), 1)
        self.assertEqual(fautive[0]['numero'], 3)
        self.assertIn('competence_fantome', fautive[0]['erreurs'][0])
        self.assertIn('competence', fautive[0]['erreurs'][0])
        # Les 2 lignes saines ont bien été appliquées : jamais un rollback
        # global à cause d'une seule ligne fautive.
        self.categorie.refresh_from_db()
        self.assertEqual(
            set(self.categorie.competences_requises_ids()),
            {self.competence.pk, self.competence2.pk})

    # ── Aperçu : ne touche JAMAIS la base ────────────────────────────────
    def test_apercu_ne_touche_pas_la_base(self):
        octets = csv_octets([
            'categorie,competence,niveau',
            'Onduleur Huawei,raccordement_ac,3',
        ])
        recap = previsualiser(self.company, octets, 'matrice.csv')
        self.assertEqual(recap['cible'], CIBLE)
        self.assertEqual(recap['valides'], 1)
        self.assertEqual(recap['appliquees'], 0)
        self.categorie.refresh_from_db()
        self.assertEqual(self.categorie.competences_requises_ids(), [])
        self.assertEqual(self.categorie.niveau_competence_min, 1)

    # ── Écriture réelle ──────────────────────────────────────────────────
    def test_import_pose_competence_et_niveau(self):
        octets = csv_octets([
            'categorie,competence,niveau_min',
            'Onduleur Huawei,raccordement_ac,3',
        ])
        recap = importer(self.company, octets, 'matrice.csv')
        self.assertEqual(recap['appliquees'], 1)
        self.categorie.refresh_from_db()
        self.assertEqual(self.categorie.competences_requises_ids(),
                         [self.competence.pk])
        self.assertEqual(self.categorie.niveau_competence_min, 3)

    def test_import_idempotent(self):
        octets = csv_octets([
            'categorie,competence,niveau',
            'Onduleur Huawei,raccordement_ac,2',
        ])
        importer(self.company, octets, 'matrice.csv')
        importer(self.company, octets, 'matrice.csv')
        self.categorie.refresh_from_db()
        self.assertEqual(self.categorie.competences_requises_ids(),
                         [self.competence.pk])

    def test_import_additif_ne_retire_rien(self):
        self.categorie.competences_requises.add(self.competence2)
        octets = csv_octets([
            'categorie,competence',
            'Onduleur Huawei,raccordement_ac',
        ])
        importer(self.company, octets, 'matrice.csv')
        self.categorie.refresh_from_db()
        self.assertEqual(
            set(self.categorie.competences_requises_ids()),
            {self.competence.pk, self.competence2.pk})

    # ── Autres motifs de rejet, tous NOMMÉS ──────────────────────────────
    def test_categorie_inconnue_rapportee(self):
        octets = csv_octets([
            'categorie,competence',
            'Categorie fantome,raccordement_ac',
        ])
        recap = importer(self.company, octets, 'matrice.csv')
        self.assertEqual(recap['rejetees'], 1)
        self.assertIn('categorie', recap['lignes'][0]['erreurs'][0])

    def test_niveau_hors_echelle_rapporte(self):
        octets = csv_octets([
            'categorie,competence,niveau',
            'Onduleur Huawei,raccordement_ac,9',
        ])
        recap = importer(self.company, octets, 'matrice.csv')
        self.assertEqual(recap['rejetees'], 1)
        self.assertIn('niveau_min', recap['lignes'][0]['erreurs'][0])

    def test_niveaux_contradictoires_dans_le_meme_fichier(self):
        octets = csv_octets([
            'categorie,competence,niveau',
            'Onduleur Huawei,raccordement_ac,2',
            'Onduleur Huawei,mes_onduleur,4',
        ])
        recap = importer(self.company, octets, 'matrice.csv')
        self.assertEqual(recap['appliquees'], 1)
        self.assertEqual(recap['rejetees'], 1)
        self.categorie.refresh_from_db()
        self.assertEqual(self.categorie.niveau_competence_min, 2)

    def test_champs_manquants_rapportes(self):
        octets = csv_octets(['categorie,competence', ',raccordement_ac'])
        recap = importer(self.company, octets, 'matrice.csv')
        self.assertEqual(recap['rejetees'], 1)

    # ── Multi-tenant ─────────────────────────────────────────────────────
    def test_competence_dune_autre_societe_inconnue(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv43-bis', defaults={'nom': 'Autre NTSRV43'})
        Competence.objects.create(
            company=autre, code='soudure', libelle='Soudure',
            domaine=Competence.Domaine.SOUDURE)
        octets = csv_octets([
            'categorie,competence', 'Onduleur Huawei,soudure'])
        recap = importer(self.company, octets, 'matrice.csv')
        self.assertEqual(recap['rejetees'], 1)

    def test_selecteur_rh_scope_societe(self):
        resolus = competences_par_code(self.company, ['RACCORDEMENT_AC'])
        self.assertEqual(resolus, {'raccordement_ac': self.competence.pk})
        self.assertEqual(competences_par_code(self.company, []), {})

    # ── Cible déclarée au registre plateforme ────────────────────────────
    def test_cible_declaree_au_registre(self):
        from apps.dataimport.services import TARGETS
        self.assertIn(CIBLE, TARGETS)

    def test_cible_refusee_par_limport_generique_avec_un_message_clair(self):
        from apps.dataimport.services import verifier_cible_importable
        with self.assertRaises(ValueError) as ctx:
            verifier_cible_importable(CIBLE)
        self.assertIn('sav', str(ctx.exception))

    # ── Endpoint ─────────────────────────────────────────────────────────
    def test_endpoint_apercu(self):
        fichier = SimpleUploadedFile(
            'matrice.csv',
            csv_octets(['categorie,competence,niveau',
                        'Onduleur Huawei,raccordement_ac,2']),
            content_type='text/csv')
        resp = self.api.post(f'{URL}?apercu=1', {'file': fichier},
                             format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['appliquees'], 0)
        self.categorie.refresh_from_db()
        self.assertEqual(self.categorie.competences_requises_ids(), [])

    def test_endpoint_import(self):
        fichier = SimpleUploadedFile(
            'matrice.csv',
            csv_octets(['categorie,competence,niveau',
                        'Onduleur Huawei,raccordement_ac,2']),
            content_type='text/csv')
        resp = self.api.post(URL, {'file': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['appliquees'], 1)

    def test_endpoint_sans_fichier(self):
        resp = self.api.post(URL, {}, format='multipart')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('file', resp.json())

    def test_endpoint_refuse_un_role_lecture_seule(self):
        lecteur = User.objects.create_user(
            username='ntsrv43_lecteur', password='x', role_legacy='normal',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(lecteur)}')
        fichier = SimpleUploadedFile(
            'matrice.csv', csv_octets(['categorie,competence', 'x,y']),
            content_type='text/csv')
        resp = api.post(URL, {'file': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 403, resp.content)
