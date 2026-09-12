"""VT9 — Assemblage serveur des photos du toit : la MACHINE D'ÉTATS.

Ce qui est prouvé : ``aucun`` → ``en_cours`` → ``ok`` / ``echec``, et surtout
que l'échec est HONNÊTE — quand les photos ne se recouvrent pas assez, le
message le dit en français et propose la suite (reprendre des photos qui se
chevauchent, ou choisir UNE photo comme texture). Jamais un résultat inventé.

LE STITCHER EST TOUJOURS MOCKÉ : aucune vraie vision par ordinateur ne tourne
en test (lent, et dépendant d'une bibliothèque optionnelle). Ce qu'on teste
ici, c'est le CÂBLAGE et les états — pas OpenCV.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.visites.models import VisiteTerrain
from apps.visites.tasks import (
    ASSEMBLAGE_MESSAGES, assembler_photos_toit_task,
)
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
PERMISSIONS = ['crm_voir', 'visites_voir', 'visites_creer',
               'visites_modifier']


class AssemblageBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='VT9 Solaire', slug='vt9-a')
        self.user = User.objects.create_user(
            username='vt9-commercial', password='x', company=self.company,
            role_legacy='normal',
            role=Role.objects.create(company=self.company, nom='vt9-terrain',
                                     permissions=list(PERMISSIONS)))
        self.lead = Lead.objects.create(company=self.company, nom='Toit Démo')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = self.api.post('/api/django/visites/visites/',
                             {'lead': self.lead.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.visite_id = resp.data['id']

    def poster_photo(self, nom, slot='toiture_vue_generale'):
        upload = SimpleUploadedFile(nom, PNG, content_type='image/png')
        resp = self.api.post(
            f'/api/django/visites/visites/{self.visite_id}/photos/',
            {'slot_code': slot, 'fichier': upload}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)

    def visite(self):
        return VisiteTerrain.objects.get(pk=self.visite_id)


class MachineEtatsTests(AssemblageBase):
    def test_etat_initial_est_aucun(self):
        detail = self.api.get(f'/api/django/visites/visites/{self.visite_id}/')
        toit = detail.data['photo_toit']
        self.assertEqual(toit['assemblage_etat'],
                         VisiteTerrain.Assemblage.AUCUN)
        self.assertEqual(toit['assemblage_erreur'], '')
        self.assertIsNone(toit['url'])
        self.assertIsNone(toit['texture_calage'])

    def test_une_seule_photo_ne_sassemble_pas_et_le_dit(self):
        self.poster_photo('toit-1.png')
        resultat = assembler_photos_toit_task(self.visite_id)
        self.assertEqual(resultat['motif'], 'pas_assez')
        visite = self.visite()
        self.assertEqual(visite.assemblage_etat,
                         VisiteTerrain.Assemblage.ECHEC)
        self.assertEqual(visite.assemblage_erreur,
                         ASSEMBLAGE_MESSAGES['pas_assez'])
        self.assertIn('deux photos', visite.assemblage_erreur)

    def test_recouvrement_insuffisant_donne_un_message_honnete(self):
        self.poster_photo('toit-1.png')
        self.poster_photo('toit-2.png')
        with mock.patch('apps.visites.tasks._assembler',
                        return_value=(None, 'recouvrement')) as stitcher:
            assembler_photos_toit_task(self.visite_id)
        self.assertTrue(stitcher.called)
        visite = self.visite()
        self.assertEqual(visite.assemblage_etat,
                         VisiteTerrain.Assemblage.ECHEC)
        # Le message NOMME la cause ET propose les deux issues concrètes.
        self.assertIn('recouvrent pas assez', visite.assemblage_erreur)
        self.assertIn('UNE seule photo', visite.assemblage_erreur)
        self.assertEqual(visite.photo_toit_key, '')

    def test_assemblage_reussi_pose_la_cle_et_lurl(self):
        self.poster_photo('toit-1.png')
        self.poster_photo('toit-2.png')
        with mock.patch('apps.visites.tasks._assembler',
                        return_value=(PNG, None)):
            resultat = assembler_photos_toit_task(self.visite_id)
        self.assertEqual(resultat['etat'], 'ok')
        visite = self.visite()
        self.assertEqual(visite.assemblage_etat, VisiteTerrain.Assemblage.OK)
        self.assertEqual(visite.assemblage_erreur, '')
        self.assertTrue(visite.photo_toit_key)

        detail = self.api.get(f'/api/django/visites/visites/{self.visite_id}/')
        self.assertEqual(
            detail.data['photo_toit']['url'],
            f'/api/django/visites/visites/{self.visite_id}/photo-toit/')

    def test_opencv_absent_est_un_echec_annonce_pas_un_crash(self):
        self.poster_photo('toit-1.png')
        self.poster_photo('toit-2.png')
        with mock.patch('apps.visites.tasks._assembler',
                        return_value=(None, 'indisponible')):
            assembler_photos_toit_task(self.visite_id)
        self.assertEqual(self.visite().assemblage_erreur,
                         ASSEMBLAGE_MESSAGES['indisponible'])

    def test_une_exception_du_stitcher_ne_remonte_jamais(self):
        self.poster_photo('toit-1.png')
        self.poster_photo('toit-2.png')
        with mock.patch('apps.visites.tasks._assembler',
                        side_effect=RuntimeError('boom')):
            resultat = assembler_photos_toit_task(self.visite_id)
        self.assertEqual(resultat['etat'], 'echec')
        self.assertEqual(self.visite().assemblage_etat,
                         VisiteTerrain.Assemblage.ECHEC)

    def test_visite_introuvable_ne_crashe_pas(self):
        self.assertEqual(
            assembler_photos_toit_task(999999)['etat'], 'introuvable')


class ActionApiTests(AssemblageBase):
    def test_laction_lance_la_tache_et_le_get_sert_de_polling(self):
        self.poster_photo('toit-1.png')
        self.poster_photo('toit-2.png')
        with mock.patch(
                'apps.visites.tasks.assembler_photos_toit_task.delay') as envoi:
            resp = self.api.post(
                f'/api/django/visites/visites/{self.visite_id}/assembler-photos/',
                {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        envoi.assert_called_once_with(self.visite_id)
        # La réponse immédiate annonce « en cours » ; le GET suit l'avancement.
        self.assertEqual(resp.data['photo_toit']['assemblage_etat'],
                         VisiteTerrain.Assemblage.EN_COURS)
        detail = self.api.get(f'/api/django/visites/visites/{self.visite_id}/')
        self.assertEqual(detail.data['photo_toit']['assemblage_etat'],
                         VisiteTerrain.Assemblage.EN_COURS)

    def test_photo_toit_absente_renvoie_404(self):
        resp = self.api.get(
            f'/api/django/visites/visites/{self.visite_id}/photo-toit/')
        self.assertEqual(resp.status_code, 404, resp.data)

    def test_calage_exige_quatre_coins(self):
        resp = self.api.patch(
            f'/api/django/visites/visites/{self.visite_id}/calage/',
            {'texture_calage': {'coins': [[33.5, -7.6], [33.5, -7.5]]}},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('texture_calage', resp.data['erreurs'])

    def test_calage_enregistre_les_quatre_coins(self):
        coins = [[33.5731, -7.5898], [33.5732, -7.5898],
                 [33.5732, -7.5897], [33.5731, -7.5897]]
        resp = self.api.patch(
            f'/api/django/visites/visites/{self.visite_id}/calage/',
            {'texture_calage': {'coins': coins}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['photo_toit']['texture_calage'],
                         {'coins': coins})
        self.assertEqual(self.visite().texture_calage, {'coins': coins})
