"""Tests XPRJ24 — export/import du plan de tâches.

Couvre : aller-retour export→import reconstruit le même arbre (hiérarchie +
dépendances FS), lignes invalides rapportées SANS RIEN écrire en dry-run
(défaut), écriture atomique avec ``?confirm=1``, et les endpoints.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import DependanceTache, Projet, Tache
from apps.gestion_projet.services import exporter_taches, importer_taches

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


class ExporterTachesTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj24-exp', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X24', nom='Projet X24')

    def test_export_ligne_avec_parent_et_dependance(self):
        racine = Tache.objects.create(
            company=self.co, projet=self.projet, code_wbs='1',
            libelle='Lot 1', charge_estimee=Decimal('5'))
        enfant = Tache.objects.create(
            company=self.co, projet=self.projet, code_wbs='1.1',
            libelle='Sous-tâche', parent=racine)
        Tache.objects.create(
            company=self.co, projet=self.projet, code_wbs='2',
            libelle='Lot 2')
        DependanceTache.objects.create(
            company=self.co, predecesseur=racine, successeur=enfant,
            type_dependance='fs')

        lignes = exporter_taches(self.projet)
        par_code = {ligne['code_wbs']: ligne for ligne in lignes}
        self.assertEqual(par_code['1.1']['parent_wbs'], '1')
        self.assertEqual(par_code['1.1']['dependances_fs'], '1')
        self.assertEqual(par_code['1']['parent_wbs'], '')
        # DecimalField(decimal_places=2) round-trips '5' -> '5.00' (la
        # valeur numérique, pas le format d'affichage, est ce qui compte
        # pour la reconstruction de l'arbre — voir round-trip ci-dessous).
        self.assertEqual(par_code['1']['charge_estimee'], '5.00')


class ImporterTachesRoundTripTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj24-imp', 'S')
        self.projet_source = Projet.objects.create(
            company=self.co, code='P-X24-SRC', nom='Projet source')
        self.projet_cible = Projet.objects.create(
            company=self.co, code='P-X24-DST', nom='Projet cible')

        racine = Tache.objects.create(
            company=self.co, projet=self.projet_source, code_wbs='1',
            libelle='Lot 1', charge_estimee=Decimal('5'))
        enfant = Tache.objects.create(
            company=self.co, projet=self.projet_source, code_wbs='1.1',
            libelle='Sous-tâche', parent=racine)
        DependanceTache.objects.create(
            company=self.co, predecesseur=racine, successeur=enfant,
            type_dependance='fs')

    def test_aller_retour_reconstruit_le_meme_arbre(self):
        lignes = exporter_taches(self.projet_source)
        resultat = importer_taches(
            self.projet_cible, lignes, confirm=True)
        self.assertEqual(resultat['erreurs'], [])
        self.assertEqual(resultat['nb_creees'], 2)
        self.assertEqual(resultat['nb_deps'], 1)

        lignes_reexport = exporter_taches(self.projet_cible)
        par_code = {ligne['code_wbs']: ligne for ligne in lignes_reexport}
        self.assertEqual(par_code['1.1']['parent_wbs'], '1')
        self.assertEqual(par_code['1.1']['dependances_fs'], '1')
        # DecimalField(decimal_places=2) round-trips '5' -> '5.00'.
        self.assertEqual(par_code['1']['charge_estimee'], '5.00')

    def test_dry_run_defaut_ne_cree_rien(self):
        lignes = exporter_taches(self.projet_source)
        resultat = importer_taches(self.projet_cible, lignes)
        self.assertEqual(resultat['nb_creees'], 0)
        self.assertEqual(
            Tache.objects.filter(projet=self.projet_cible).count(), 0)

    def test_ligne_invalide_rapportee_sans_rien_ecrire(self):
        lignes = [
            {'code_wbs': '1', 'libelle': '', 'parent_wbs': ''},  # libellé manquant
            {'code_wbs': '2', 'libelle': 'OK', 'parent_wbs': '99'},  # parent inconnu
        ]
        resultat = importer_taches(self.projet_cible, lignes, confirm=True)
        self.assertGreater(len(resultat['erreurs']), 0)
        self.assertEqual(resultat['nb_creees'], 0)
        self.assertEqual(
            Tache.objects.filter(projet=self.projet_cible).count(), 0)

    def test_code_wbs_manquant_erreur(self):
        lignes = [{'code_wbs': '', 'libelle': 'X'}]
        resultat = importer_taches(self.projet_cible, lignes, confirm=True)
        self.assertGreater(len(resultat['erreurs']), 0)

    def test_code_wbs_duplique_erreur(self):
        lignes = [
            {'code_wbs': '1', 'libelle': 'A'},
            {'code_wbs': '1', 'libelle': 'B'},
        ]
        resultat = importer_taches(self.projet_cible, lignes, confirm=True)
        self.assertGreater(len(resultat['erreurs']), 0)
        self.assertEqual(
            Tache.objects.filter(projet=self.projet_cible).count(), 0)


class ExportImportEndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj24-api', 'S')
        self.user = make_user(self.co, 'resp-xprj24')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X24-API', nom='Projet API')
        Tache.objects.create(
            company=self.co, projet=self.projet, code_wbs='1',
            libelle='Tâche API')

    def test_export_json_par_defaut(self):
        api = auth(self.user)
        resp = api.get(
            f'/api/django/gestion-projet/projets/{self.projet.id}/taches/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, list)

    def test_export_xlsx(self):
        api = auth(self.user)
        resp = api.get(
            f'/api/django/gestion-projet/projets/{self.projet.id}/'
            f'taches/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument'
            '.spreadsheetml.sheet')

    def test_import_dry_run_endpoint(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/gestion-projet/projets/{self.projet.id}/'
            f'importer-taches/',
            {'lignes': [{'code_wbs': '9', 'libelle': 'Nouvelle'}]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_creees'], 0)
        self.assertFalse(
            Tache.objects.filter(
                projet=self.projet, code_wbs='9').exists())

    def test_import_confirm_endpoint_ecrit(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/gestion-projet/projets/{self.projet.id}/'
            f'importer-taches/?confirm=1',
            {'lignes': [{'code_wbs': '9', 'libelle': 'Nouvelle'}]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_creees'], 1)
        self.assertTrue(
            Tache.objects.filter(
                projet=self.projet, code_wbs='9').exists())

    def test_import_404_autre_societe(self):
        autre_co = make_company('gp-xprj24-autre', 'Autre')
        autre_user = make_user(autre_co, 'user-autre-x24')
        api = auth(autre_user)
        resp = api.post(
            f'/api/django/gestion-projet/projets/{self.projet.id}/'
            f'importer-taches/',
            {'lignes': [{'code_wbs': '9', 'libelle': 'X'}]}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_import_lignes_vide_400(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/gestion-projet/projets/{self.projet.id}/'
            f'importer-taches/',
            {'lignes': []}, format='json')
        self.assertEqual(resp.status_code, 400)
