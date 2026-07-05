"""Tests XACC27 — Plafonds de notes de frais par catégorie + OCR justificatif.

Couvre : une note au-dessus du plafond est flaggée ``hors_politique`` à la
création (warning, jamais de blocage) ; le justificatif devient obligatoire
au-delà du seuil configuré ; l'OCR pré-remplit sans écraser une saisie
manuelle et dégrade proprement (503) sans clé ; le doublon (même employé +
date + montant) est signalé sans bloquer.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import NoteFrais, PlafondNoteFrais

User = get_user_model()


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


class PlafondServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc27-svc', 'XACC27 Svc')
        self.user = make_user(self.co, 'xacc27-svc-user')
        self.employe = make_user(self.co, 'xacc27-employe', role='normal')

    def test_sans_plafond_jamais_hors_politique(self):
        note = services.creer_note_frais(
            self.co, employe=self.employe, date_frais=date(2026, 6, 1),
            montant=Decimal('999999'), motif='Sans plafond configuré',
            categorie=NoteFrais.Categorie.REPAS, user=self.user)
        self.assertFalse(note.hors_politique)

    def test_au_dessus_du_plafond_flaggee(self):
        PlafondNoteFrais.objects.create(
            company=self.co, categorie=NoteFrais.Categorie.REPAS,
            montant_max=Decimal('200'))
        note = services.creer_note_frais(
            self.co, employe=self.employe, date_frais=date(2026, 6, 1),
            montant=Decimal('350'), motif='Repas client',
            categorie=NoteFrais.Categorie.REPAS, user=self.user)
        self.assertTrue(note.hors_politique)

    def test_sous_le_plafond_non_flaggee(self):
        PlafondNoteFrais.objects.create(
            company=self.co, categorie=NoteFrais.Categorie.REPAS,
            montant_max=Decimal('200'))
        note = services.creer_note_frais(
            self.co, employe=self.employe, date_frais=date(2026, 6, 1),
            montant=Decimal('150'), motif='Repas ok',
            categorie=NoteFrais.Categorie.REPAS, user=self.user)
        self.assertFalse(note.hors_politique)

    def test_justificatif_obligatoire_au_dela_du_seuil(self):
        PlafondNoteFrais.objects.create(
            company=self.co, categorie=NoteFrais.Categorie.HEBERGEMENT,
            montant_max=Decimal('5000'),
            seuil_justificatif_obligatoire=Decimal('1000'))
        note = services.creer_note_frais(
            self.co, employe=self.employe, date_frais=date(2026, 6, 1),
            montant=Decimal('1500'), motif='Hôtel',
            categorie=NoteFrais.Categorie.HEBERGEMENT, user=self.user)
        services.soumettre_note_frais(note)
        with self.assertRaises(Exception):
            services.valider_note_frais(note, user=self.user)

    def test_doublon_detecte_sans_bloquer(self):
        services.creer_note_frais(
            self.co, employe=self.employe, date_frais=date(2026, 6, 1),
            montant=Decimal('100'), motif='Taxi',
            categorie=NoteFrais.Categorie.DEPLACEMENT, user=self.user)
        candidats = services.note_frais_doublon_possible(
            self.co, employe=self.employe, date_frais=date(2026, 6, 1),
            montant=Decimal('100'))
        self.assertEqual(candidats.count(), 1)
        # Créer la seconde note n'est jamais bloqué par le service.
        note2 = services.creer_note_frais(
            self.co, employe=self.employe, date_frais=date(2026, 6, 1),
            montant=Decimal('100'), motif='Taxi (doublon volontaire)',
            categorie=NoteFrais.Categorie.DEPLACEMENT, user=self.user)
        self.assertIsNotNone(note2.id)


class OcrNotesFraisServiceTests(TestCase):
    def test_inactive_par_defaut(self):
        self.assertFalse(services.ocr_notes_frais_active())

    def test_extraire_sans_cle_leve_runtime_error(self):
        with self.assertRaises(RuntimeError):
            services.extraire_justificatif_note_frais(b'fake-bytes')

    @override_settings(COMPTA_OCR_NOTES_FRAIS_ENABLED=True)
    def test_extraire_active_sans_provider_reste_noop(self):
        self.assertEqual(
            services.extraire_justificatif_note_frais(b'fake-bytes'), {})

    def test_mapper_champs_complets(self):
        champs = services.mapper_justificatif_vers_note_frais({
            'montant': '250.00', 'date': '2026-06-01',
            'fournisseur': 'Restaurant Le Sud',
        })
        self.assertEqual(champs['montant'], '250.00')
        self.assertEqual(champs['date_frais'], '2026-06-01')
        self.assertEqual(champs['motif'], 'Restaurant Le Sud')

    def test_mapper_vide_renvoie_vide(self):
        self.assertEqual(services.mapper_justificatif_vers_note_frais({}), {})
        self.assertEqual(services.mapper_justificatif_vers_note_frais(None), {})


class PlafondApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('xacc27-a', 'XACC27 A')
        self.co_b = make_company('xacc27-b', 'XACC27 B')
        self.user_a = make_user(self.co_a, 'xacc27-user-a')
        self.employe_a = make_user(self.co_a, 'xacc27-employe-a', role='normal')

    def test_create_plafond_pose_company(self):
        resp = auth(self.user_a).post(
            '/api/django/compta/plafonds-notes-frais/',
            {'categorie': NoteFrais.Categorie.CARBURANT, 'montant_max': '500',
             'company': self.co_b.id}, format='json')
        self.assertEqual(resp.status_code, 201)
        plafond = PlafondNoteFrais.objects.get(id=resp.data['id'])
        self.assertEqual(plafond.company_id, self.co_a.id)

    def test_doublon_categorie_refuse(self):
        PlafondNoteFrais.objects.create(
            company=self.co_a, categorie=NoteFrais.Categorie.CARBURANT,
            montant_max=Decimal('500'))
        resp = auth(self.user_a).post(
            '/api/django/compta/plafonds-notes-frais/',
            {'categorie': NoteFrais.Categorie.CARBURANT, 'montant_max': '600'},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_note_create_expose_hors_politique_et_doublon(self):
        PlafondNoteFrais.objects.create(
            company=self.co_a, categorie=NoteFrais.Categorie.REPAS,
            montant_max=Decimal('100'))
        resp = auth(self.user_a).post(
            '/api/django/compta/notes-frais/',
            {'employe': self.employe_a.id, 'date_frais': '2026-06-01',
             'montant': '300', 'motif': 'Repas', 'categorie': 'repas'},
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['hors_politique'])
        self.assertFalse(resp.data['doublon_possible'])

    def _photo(self):
        f = BytesIO(b'fake-jpeg-bytes')
        f.name = 'justificatif.jpg'
        return f

    def test_ocr_sans_cle_503(self):
        resp = auth(self.user_a).post(
            '/api/django/compta/notes-frais/ocr/',
            {'justificatif': self._photo()}, format='multipart')
        self.assertEqual(resp.status_code, 503)
        self.assertIn('OCR indisponible', resp.data['detail'])

    def test_ocr_fichier_manquant_400(self):
        resp = auth(self.user_a).post(
            '/api/django/compta/notes-frais/ocr/', {}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    @override_settings(COMPTA_OCR_NOTES_FRAIS_ENABLED=True)
    def test_ocr_avec_cle_mockee_prefill(self):
        mock_champs = {
            'montant': '250.00', 'date': '2026-06-01',
            'fournisseur': 'Restaurant Le Sud',
        }
        with patch(
            'apps.compta.services.extraire_justificatif_note_frais',
            return_value=mock_champs,
        ):
            resp = auth(self.user_a).post(
                '/api/django/compta/notes-frais/ocr/',
                {'justificatif': self._photo()}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['champs']['motif'], 'Restaurant Le Sud')

    def test_ocr_ne_cree_jamais_de_note(self):
        avant = NoteFrais.objects.count()
        auth(self.user_a).post(
            '/api/django/compta/notes-frais/ocr/',
            {'justificatif': self._photo()}, format='multipart')
        self.assertEqual(NoteFrais.objects.count(), avant)
