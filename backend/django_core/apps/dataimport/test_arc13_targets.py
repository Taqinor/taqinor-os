"""ARC13 — cibles FIELD_MAPS additives (``contrats``, ``dossiers_rh``).

Couvre, pour chaque cible :
- le service d'écriture délégué (``creer_contrat_import`` /
  ``creer_dossier_employe_import``) : création, doublon sauté, ligne
  invalide en erreur ;
- l'endpoint générique ``/api/django/imports/commit/`` bout en bout ;
- l'IDEMPOTENCE : ré-importer le même fichier ne duplique rien.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats.models import Contrat
from apps.contrats.services import creer_contrat_import
from apps.rh.models import DossierEmploye
from apps.rh.services import creer_dossier_employe_import

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


def make_csv(content, name='data.csv'):
    return SimpleUploadedFile(name, content.encode('utf-8'), content_type='text/csv')


class CreerContratImportServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('imp-ctr-svc', 'Imp Ctr Svc')

    def test_cree_depuis_ligne(self):
        statut, message = creer_contrat_import(self.co, {
            'objet': 'Contrat maintenance PV', 'reference': 'CTR-1',
            'type_contrat': 'maintenance', 'montant': '15000',
        })
        self.assertEqual(statut, 'cree')
        self.assertIsNone(message)
        contrat = Contrat.objects.get(company=self.co, reference='CTR-1')
        self.assertEqual(contrat.objet, 'Contrat maintenance PV')
        self.assertEqual(contrat.type_contrat, 'maintenance')
        self.assertEqual(str(contrat.montant), '15000.00')

    def test_doublon_reference_saute(self):
        Contrat.objects.create(
            company=self.co, objet='Existant', reference='CTR-2')
        statut, _ = creer_contrat_import(
            self.co, {'objet': 'Nouveau', 'reference': 'CTR-2'})
        self.assertEqual(statut, 'doublon')
        self.assertEqual(
            Contrat.objects.filter(company=self.co, reference='CTR-2').count(), 1)

    def test_sans_objet_erreur(self):
        statut, message = creer_contrat_import(self.co, {'reference': 'CTR-3'})
        self.assertEqual(statut, 'erreur')
        self.assertIsNotNone(message)

    def test_sans_reference_toujours_cree(self):
        # Pas de clé d'idempotence disponible : deux lignes sans référence
        # créent chacune un contrat (comportement documenté).
        s1, _ = creer_contrat_import(self.co, {'objet': 'A'})
        s2, _ = creer_contrat_import(self.co, {'objet': 'B'})
        self.assertEqual(s1, 'cree')
        self.assertEqual(s2, 'cree')
        self.assertEqual(
            Contrat.objects.filter(company=self.co, reference='').count(), 2)

    def test_type_invalide_retombe_sur_autre(self):
        statut, _ = creer_contrat_import(self.co, {
            'objet': 'Test type', 'reference': 'CTR-4',
            'type_contrat': 'bidon-inexistant',
        })
        self.assertEqual(statut, 'cree')
        contrat = Contrat.objects.get(company=self.co, reference='CTR-4')
        self.assertEqual(contrat.type_contrat, Contrat.TypeContrat.AUTRE)

    def test_montant_avec_virgule_et_espace(self):
        statut, _ = creer_contrat_import(self.co, {
            'objet': 'Montant FR', 'reference': 'CTR-5', 'montant': '1 500,50',
        })
        self.assertEqual(statut, 'cree')
        contrat = Contrat.objects.get(company=self.co, reference='CTR-5')
        self.assertEqual(str(contrat.montant), '1500.50')


class CreerDossierEmployeImportServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('imp-rh-svc', 'Imp Rh Svc')

    def test_cree_depuis_ligne(self):
        statut, message = creer_dossier_employe_import(self.co, {
            'matricule': 'MAT-1', 'nom': 'Alaoui', 'prenom': 'Youssef',
            'email': 'y.alaoui@x.ma', 'type_contrat': 'cdi',
        })
        self.assertEqual(statut, 'cree')
        self.assertIsNone(message)
        dossier = DossierEmploye.objects.get(company=self.co, matricule='MAT-1')
        self.assertEqual(dossier.nom, 'Alaoui')
        self.assertEqual(dossier.prenom, 'Youssef')
        self.assertEqual(dossier.type_contrat, 'cdi')

    def test_doublon_matricule_saute(self):
        DossierEmploye.objects.create(
            company=self.co, matricule='MAT-2', nom='Existant')
        statut, _ = creer_dossier_employe_import(
            self.co, {'matricule': 'MAT-2', 'nom': 'Nouveau'})
        self.assertEqual(statut, 'doublon')
        self.assertEqual(
            DossierEmploye.objects.filter(
                company=self.co, matricule='MAT-2').count(), 1)

    def test_sans_matricule_erreur(self):
        statut, message = creer_dossier_employe_import(self.co, {'nom': 'X'})
        self.assertEqual(statut, 'erreur')
        self.assertIsNotNone(message)

    def test_sans_nom_erreur(self):
        statut, message = creer_dossier_employe_import(
            self.co, {'matricule': 'MAT-3'})
        self.assertEqual(statut, 'erreur')
        self.assertIsNotNone(message)

    def test_type_contrat_invalide_retombe_sur_cdi(self):
        statut, _ = creer_dossier_employe_import(self.co, {
            'matricule': 'MAT-4', 'nom': 'Test', 'type_contrat': 'inexistant',
        })
        self.assertEqual(statut, 'cree')
        dossier = DossierEmploye.objects.get(company=self.co, matricule='MAT-4')
        self.assertEqual(dossier.type_contrat, DossierEmploye.TypeContrat.CDI)

    def test_date_embauche_formats(self):
        statut, _ = creer_dossier_employe_import(self.co, {
            'matricule': 'MAT-5', 'nom': 'Test', 'date_embauche': '15/03/2024',
        })
        self.assertEqual(statut, 'cree')
        dossier = DossierEmploye.objects.get(company=self.co, matricule='MAT-5')
        self.assertEqual(dossier.date_embauche.isoformat(), '2024-03-15')


class ImportContratsFrameworkApiTests(TestCase):
    def setUp(self):
        self.co = make_company('imp-ctr-fw', 'Imp Ctr Fw')
        self.user = make_user(self.co, 'imp-ctr-fw-user')
        self.api = auth(self.user)

    def test_import_cree_et_saute_doublon(self):
        Contrat.objects.create(
            company=self.co, objet='Déjà là', reference='FWCTR-1')
        content = (
            'Reference,Objet,Type,Montant\n'
            'FWCTR-1,Doublon,vente,1000\n'
            'FWCTR-2,Nouveau contrat,vente,2000\n'
        )
        resp = self.api.post(URL_IMPORT_COMMIT, {
            'file': make_csv(content), 'target': 'contrats',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
        self.assertEqual(len(resp.data['skipped']), 1)
        self.assertEqual(Contrat.objects.filter(company=self.co).count(), 2)

    def test_reimport_meme_fichier_idempotent(self):
        content = (
            'Reference,Objet,Type,Montant\n'
            'FWCTR-IDEMP,Contrat idempotent,vente,500\n'
        )
        resp1 = self.api.post(URL_IMPORT_COMMIT, {
            'file': make_csv(content), 'target': 'contrats',
        }, format='multipart')
        self.assertEqual(resp1.status_code, 200, resp1.data)
        self.assertEqual(resp1.data['created'], 1)

        resp2 = self.api.post(URL_IMPORT_COMMIT, {
            'file': make_csv(content), 'target': 'contrats',
        }, format='multipart')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['created'], 0)
        self.assertEqual(len(resp2.data['skipped']), 1)
        self.assertEqual(
            Contrat.objects.filter(
                company=self.co, reference='FWCTR-IDEMP').count(), 1)


class ImportDossiersRhFrameworkApiTests(TestCase):
    def setUp(self):
        self.co = make_company('imp-rh-fw', 'Imp Rh Fw')
        self.user = make_user(self.co, 'imp-rh-fw-user')
        self.api = auth(self.user)

    def test_import_cree_et_saute_doublon(self):
        DossierEmploye.objects.create(
            company=self.co, matricule='FWRH-1', nom='Déjà là')
        content = (
            'Matricule,Nom,Prenom,Email\n'
            'FWRH-1,Doublon,X,dup@x.ma\n'
            'FWRH-2,Nouveau,Employe,new@x.ma\n'
        )
        resp = self.api.post(URL_IMPORT_COMMIT, {
            'file': make_csv(content), 'target': 'dossiers_rh',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1)
        self.assertEqual(len(resp.data['skipped']), 1)
        self.assertEqual(DossierEmploye.objects.filter(company=self.co).count(), 2)

    def test_reimport_meme_fichier_idempotent(self):
        content = (
            'Matricule,Nom,Prenom\n'
            'FWRH-IDEMP,Idempotent,Test\n'
        )
        resp1 = self.api.post(URL_IMPORT_COMMIT, {
            'file': make_csv(content), 'target': 'dossiers_rh',
        }, format='multipart')
        self.assertEqual(resp1.status_code, 200, resp1.data)
        self.assertEqual(resp1.data['created'], 1)

        resp2 = self.api.post(URL_IMPORT_COMMIT, {
            'file': make_csv(content), 'target': 'dossiers_rh',
        }, format='multipart')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['created'], 0)
        self.assertEqual(len(resp2.data['skipped']), 1)
        self.assertEqual(
            DossierEmploye.objects.filter(
                company=self.co, matricule='FWRH-IDEMP').count(), 1)
