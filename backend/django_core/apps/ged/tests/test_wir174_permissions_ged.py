"""Tests WIR174 — gouvernance documentaire réservée à la direction.

Caviarder une pièce, poser ou LEVER une rétention légale (legal hold) et fixer
une politique de rétention sont des actes à PORTÉE JURIDIQUE. Ils n'étaient
gardés que par ``IsResponsableOrAdmin``, c'est-à-dire par tout porteur d'UNE
permission d'écriture — même hors GED.

Couvre :
* les trois codes sont au catalogue, ``ged_gouvernance`` est ÉLEVÉE ;
* un Technicien (écritures SAV/stock, aucun code GED) : 403 sur les trois
  actions de gouvernance, mais garde liste / recherche / téléchargement ZIP ;
* ``ged_gerer`` SANS ``ged_gouvernance`` : écrit un document mais reçoit 403
  sur la gouvernance (le cœur de la tâche) ;
* ``ged_gouvernance`` pose et lève un legal hold ;
* défense en PROFONDEUR : le service ``placer_legal_hold`` refuse aussi, sans
  passer par la vue ;
* légacy inchangé (compte sans rôle fin) ;
* l'ACL coffre-fort n'est pas touchée.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Coffre, Document, Folder, LegalHold
from apps.roles.models import ALL_PERMISSIONS, ELEVATED_PERMISSIONS, Role

User = get_user_model()

URL_DOCUMENTS = '/api/django/ged/documents/'
URL_LEGAL_HOLDS = '/api/django/ged/legal-holds/'
URL_POLITIQUES = '/api/django/ged/politiques-retention/'

# Un Technicien type : des écritures réelles, aucune dans la GED.
TECHNICIEN = ['sav_voir', 'sav_gerer', 'stock_voir', 'stock_mouvement']


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CatalogueGedTests(TestCase):
    def test_les_trois_codes_sont_au_catalogue(self):
        for code in ('ged_voir', 'ged_gerer', 'ged_gouvernance'):
            self.assertIn(code, ALL_PERMISSIONS, code)

    def test_gouvernance_est_elevee(self):
        """Octroi réservé à l'administrateur (comme marge/prix d'achat)."""
        self.assertIn('ged_gouvernance', ELEVATED_PERMISSIONS)
        self.assertNotIn('ged_gerer', ELEVATED_PERMISSIONS)


class GouvernanceGedTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='WIR174 Co', slug='wir174-co')
        self.folder = Folder.objects.create(
            company=self.co, nom='Racine', path='/Racine')
        self.doc = Document.objects.create(
            company=self.co, folder=self.folder, nom='Contrat')

    def _user(self, username, permissions):
        role = Role.objects.create(
            company=self.co, nom=f'role-{username}',
            permissions=list(permissions))
        return User.objects.create_user(
            username=username, password='x', company=self.co, role=role)

    def _legacy(self, username, role_legacy):
        return User.objects.create_user(
            username=username, password='x', company=self.co,
            role_legacy=role_legacy)

    def _urls_gouvernance(self):
        base = f'{URL_DOCUMENTS}{self.doc.pk}/'
        return (f'{base}placer-legal-hold/', f'{base}lever-legal-hold/',
                f'{base}caviarder/')

    # ── Le resserrement ───────────────────────────────────────────────────
    def test_technicien_403_sur_les_trois_actions_de_gouvernance(self):
        technicien = self._user('wir174-technicien', TECHNICIEN)
        api = auth(technicien)
        for url in self._urls_gouvernance():
            self.assertEqual(api.post(url).status_code, 403, url)

    def test_technicien_garde_liste_recherche_et_zip(self):
        """Le Done de la tâche : la LECTURE ordinaire reste ouverte."""
        technicien = self._user('wir174-technicien-lecture', TECHNICIEN)
        api = auth(technicien)
        self.assertEqual(api.get(URL_DOCUMENTS).status_code, 200)
        self.assertEqual(
            api.get(f'{URL_DOCUMENTS}recherche/', {'q': 'Contrat'})
            .status_code, 200)
        resp = api.post(
            f'{URL_DOCUMENTS}operations-lot/',
            {'operation': 'telecharger_zip', 'documents': [self.doc.pk]},
            format='json')
        self.assertNotEqual(resp.status_code, 403)

    def test_ged_gerer_ecrit_mais_ne_gouverne_pas(self):
        gestionnaire = self._user(
            'wir174-gestionnaire', ['ged_voir', 'ged_gerer'])
        api = auth(gestionnaire)
        resp = api.post(
            URL_DOCUMENTS, {'nom': 'Note', 'folder': self.folder.pk})
        self.assertEqual(resp.status_code, 201)
        for url in self._urls_gouvernance():
            self.assertEqual(api.post(url).status_code, 403, url)
        # Le registre de rétention lui reste aussi fermé en écriture.
        resp = api.post(
            URL_POLITIQUES,
            {'nom': 'P1', 'duree_conservation_jours': 30})
        self.assertEqual(resp.status_code, 403)

    def test_gouvernance_pose_et_leve_un_legal_hold(self):
        direction = self._user(
            'wir174-direction', ['ged_voir', 'ged_gerer', 'ged_gouvernance'])
        api = auth(direction)
        base = f'{URL_DOCUMENTS}{self.doc.pk}/'
        self.assertEqual(
            api.post(f'{base}placer-legal-hold/').status_code, 201)
        self.assertTrue(
            LegalHold.objects.filter(document=self.doc, actif=True).exists())
        self.assertEqual(api.post(f'{base}lever-legal-hold/').status_code, 200)
        self.assertFalse(
            LegalHold.objects.filter(document=self.doc, actif=True).exists())

    def test_registre_legal_holds_exige_ged_voir(self):
        intrus = self._user('wir174-intrus-registre', TECHNICIEN)
        self.assertEqual(auth(intrus).get(URL_LEGAL_HOLDS).status_code, 403)
        lecteur = self._user('wir174-lecteur-registre', ['ged_voir'])
        self.assertEqual(auth(lecteur).get(URL_LEGAL_HOLDS).status_code, 200)

    # ── Défense en profondeur ─────────────────────────────────────────────
    def test_le_service_refuse_aussi_sans_passer_par_la_vue(self):
        technicien = self._user('wir174-service', TECHNICIEN)
        with self.assertRaises(PermissionError):
            services.placer_legal_hold(self.doc, user=technicien, motif='x')
        self.assertFalse(LegalHold.objects.filter(document=self.doc).exists())

    def test_le_service_leve_refuse_aussi(self):
        direction = self._user('wir174-dir-service', ['ged_gouvernance'])
        services.placer_legal_hold(self.doc, user=direction, motif='x')
        technicien = self._user('wir174-service-lever', TECHNICIEN)
        with self.assertRaises(PermissionError):
            services.lever_legal_hold(self.doc, user=technicien)
        self.assertTrue(
            LegalHold.objects.filter(document=self.doc, actif=True).exists())

    # ── Légacy inchangé ───────────────────────────────────────────────────
    def test_legacy_admin_inchange(self):
        legacy = self._legacy('wir174-legacy-admin', 'admin')
        resp = auth(legacy).post(
            f'{URL_DOCUMENTS}{self.doc.pk}/placer-legal-hold/')
        self.assertEqual(resp.status_code, 201)

    def test_legacy_normal_toujours_refuse(self):
        legacy = self._legacy('wir174-legacy-normal', 'normal')
        resp = auth(legacy).post(
            f'{URL_DOCUMENTS}{self.doc.pk}/placer-legal-hold/')
        self.assertEqual(resp.status_code, 403)

    # ── L'ACL coffre-fort n'est pas touchée ───────────────────────────────
    def test_acl_coffre_fort_inchangee(self):
        """Un document en coffre reste invisible hors de son propriétaire,
        même pour un porteur ``ged_voir``/``ged_gerer``."""
        proprietaire = self._legacy('wir174-proprio', 'normal')
        coffre = Coffre.objects.create(
            company=self.co, nom='Coffre RH', proprietaire=proprietaire)
        secret = Document.objects.create(
            company=self.co, folder=self.folder, nom='Secret', coffre=coffre)
        gestionnaire = self._user(
            'wir174-gest-coffre', ['ged_voir', 'ged_gerer'])
        resp = auth(gestionnaire).get(f'{URL_DOCUMENTS}{secret.pk}/')
        self.assertEqual(resp.status_code, 404)
