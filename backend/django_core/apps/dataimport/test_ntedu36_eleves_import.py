"""NTEDU36 — cible d'import ``eleves_education`` (migration élèves depuis
Excel/ancien système, apps/dataimport réutilisé EXCLUSIVEMENT, jamais un
moteur d'import maison).

Couvre :
- le service d'écriture délégué (``apps.education.services.creer_eleve_import``) :
  création, famille résolue/réutilisée, classe inconnue → erreur de ligne ;
- l'endpoint générique ``/api/django/imports/commit/`` bout en bout : une
  ligne en erreur (classe inconnue) ne bloque jamais les lignes valides et
  reste téléchargeable via le CSV des erreurs (XPLT2, réutilisé tel quel).
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.education.models import AnneeScolaire, Classe, Eleve, Famille, Niveau
from apps.education.services import creer_eleve_import

User = get_user_model()

URL_IMPORT_COMMIT = '/api/django/imports/commit/'


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


def make_csv(content, name='eleves.csv'):
    return SimpleUploadedFile(name, content.encode('utf-8'), content_type='text/csv')


class CreerEleveImportServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('imp-edu-svc', 'Imp Edu Svc')
        annee = AnneeScolaire.objects.create(
            company=self.co, libelle='2026-2027',
            date_debut='2026-09-01', date_fin='2027-06-30')
        niveau = Niveau.objects.create(
            company=self.co, nom='CE1', cycle=Niveau.Cycle.PRIMAIRE)
        self.classe = Classe.objects.create(
            company=self.co, annee_scolaire=annee, niveau=niveau, nom='CE1-A')

    def test_cree_depuis_ligne(self):
        statut, message = creer_eleve_import(self.co, {
            'nom': 'Alami', 'prenom': 'Sara', 'classe_nom': 'CE1-A',
            'famille_nom': 'Alami', 'parent1_telephone': '0600000000',
        })
        self.assertEqual(statut, 'cree')
        self.assertEqual(message, '')
        eleve = Eleve.objects.get(company=self.co, nom='Alami', prenom='Sara')
        self.assertEqual(eleve.classe_id, self.classe.id)
        self.assertTrue(eleve.numero_dossier)
        self.assertEqual(eleve.famille.nom, 'Alami')
        self.assertEqual(eleve.famille.parent1_telephone, '0600000000')

    def test_meme_famille_reutilisee_pour_fratrie(self):
        creer_eleve_import(self.co, {
            'nom': 'Bennani', 'prenom': 'Yassine', 'famille_nom': 'Bennani'})
        creer_eleve_import(self.co, {
            'nom': 'Bennani', 'prenom': 'Salma', 'famille_nom': 'Bennani'})
        self.assertEqual(
            Famille.objects.filter(company=self.co, nom='Bennani').count(), 1)
        self.assertEqual(
            Eleve.objects.filter(company=self.co, famille__nom='Bennani').count(), 2)

    def test_classe_inconnue_erreur_sans_creer(self):
        statut, message = creer_eleve_import(self.co, {
            'nom': 'Test', 'prenom': 'Classe', 'classe_nom': 'Inexistante',
        })
        self.assertEqual(statut, 'erreur')
        self.assertIn('classe inconnue', message)
        self.assertFalse(
            Eleve.objects.filter(company=self.co, nom='Test').exists())

    def test_sans_nom_prenom_erreur(self):
        statut, message = creer_eleve_import(self.co, {'nom': 'Seul'})
        self.assertEqual(statut, 'erreur')
        self.assertIsNotNone(message)

    def test_sans_famille_nom_genere_une_famille_par_defaut(self):
        statut, _ = creer_eleve_import(
            self.co, {'nom': 'Idrissi', 'prenom': 'Nadia'})
        self.assertEqual(statut, 'cree')
        eleve = Eleve.objects.get(company=self.co, nom='Idrissi')
        self.assertTrue(eleve.famille.nom)

    def test_date_naissance_formats(self):
        statut, _ = creer_eleve_import(self.co, {
            'nom': 'Tazi', 'prenom': 'Omar', 'date_naissance': '15/03/2015',
        })
        self.assertEqual(statut, 'cree')
        eleve = Eleve.objects.get(company=self.co, nom='Tazi')
        self.assertEqual(eleve.date_naissance.isoformat(), '2015-03-15')


class ImportElevesFrameworkApiTests(TestCase):
    def setUp(self):
        self.co = make_company('imp-edu-fw', 'Imp Edu Fw')
        self.user = make_user(self.co, 'imp-edu-fw-user')
        self.api = auth(self.user)
        annee = AnneeScolaire.objects.create(
            company=self.co, libelle='2026-2027',
            date_debut='2026-09-01', date_fin='2027-06-30')
        niveau = Niveau.objects.create(
            company=self.co, nom='CM2', cycle=Niveau.Cycle.PRIMAIRE)
        Classe.objects.create(
            company=self.co, annee_scolaire=annee, niveau=niveau, nom='CM2-B')

    def test_import_cree_lignes_valides_et_rapporte_erreurs_sans_bloquer(self):
        content = (
            'Nom,Prenom,Classe,Famille\n'
            'Fassi,Karim,CM2-B,Fassi\n'
            'Oiseau,Rare,ClasseInexistante,Oiseau\n'
        )
        resp = self.api.post(URL_IMPORT_COMMIT, {
            'file': make_csv(content), 'target': 'eleves_education',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
        self.assertEqual(len(resp.data['skipped']), 1)
        self.assertIn('classe inconnue', resp.data['skipped'][0]['raison'])
        self.assertEqual(
            Eleve.objects.filter(company=self.co, nom='Fassi').count(), 1)
        self.assertFalse(
            Eleve.objects.filter(company=self.co, nom='Oiseau').exists())

        # XPLT2 — le CSV des lignes en échec reste téléchargeable, jamais
        # bloquant pour les lignes valides déjà importées.
        job_id = resp.data['job_id']
        csv_resp = self.api.get(f'/api/django/imports/jobs/{job_id}/erreurs.csv')
        self.assertEqual(csv_resp.status_code, 200, csv_resp.content)
        self.assertIn(b'Oiseau', csv_resp.content)
