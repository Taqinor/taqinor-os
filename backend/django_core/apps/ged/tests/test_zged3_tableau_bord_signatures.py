"""ZGED3 — Tableau de bord des demandes de signature (kanban par statut +
suivi de progression).

Couvre :
  * le tableau liste les demandes par statut avec avancement et signataires ;
  * filtrable par émetteur/période ; drill-down vers la demande ;
  * non-gestionnaire -> 403 ; scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import selectors, services
from apps.ged.models import Cabinet, Document, Folder

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


class ZGed3Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged3-a', 'Zged3 A')
        self.admin_a = make_user(self.co_a, 'zged3-admin-a', 'admin')
        self.autre_a = make_user(self.co_a, 'zged3-autre-a', 'normal')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='contrat.pdf')


class SelectorTests(ZGed3Base):
    def test_kanban_groupe_par_statut_avec_avancement(self):
        demande = services.creer_demande_multi_signataires(
            self.doc, destinataires=[
                {'nom': 'Client A', 'email': 'a@example.com'},
                {'nom': 'Client B', 'email': 'b@example.com'},
            ], company=self.co_a, created_by=self.admin_a)
        result = selectors.tableau_bord_signatures(self.co_a)
        self.assertEqual(result['total'], 1)
        self.assertIn('en_attente', result['colonnes'])
        ligne = result['colonnes']['en_attente'][0]
        self.assertEqual(ligne['id'], demande.pk)
        self.assertEqual(len(ligne['signataires']), 2)
        self.assertEqual(ligne['pourcentage_completion'], 0.0)

    def test_signature_partielle_pourcentage(self):
        demande = services.creer_demande_multi_signataires(
            self.doc, destinataires=[
                {'nom': 'Client A', 'email': 'a@example.com'},
                {'nom': 'Client B', 'email': 'b@example.com'},
            ], company=self.co_a, created_by=self.admin_a)
        premier = demande.signataires.first()
        services.signer_signataire(
            premier, consentement=True, signature_texte='Client A')
        result = selectors.tableau_bord_signatures(self.co_a)
        toutes_lignes = [
            ligne for lignes in result['colonnes'].values() for ligne in lignes]
        ligne = next(
            item for item in toutes_lignes if item['id'] == demande.pk)
        self.assertEqual(ligne['pourcentage_completion'], 50.0)

    def test_retrocompatible_mono_signataire_sans_signatairedemande(self):
        demande = services.demander_signature(
            self.doc, signataire_nom='Solo', signataire_email='solo@example.com',
            company=self.co_a, created_by=self.admin_a)
        result = selectors.tableau_bord_signatures(self.co_a)
        ligne = result['colonnes']['en_attente'][0]
        self.assertEqual(ligne['id'], demande.pk)
        self.assertEqual(len(ligne['signataires']), 1)
        self.assertEqual(ligne['signataires'][0]['nom'], 'Solo')

    def test_filtre_par_emetteur(self):
        autre_admin = make_user(self.co_a, 'zged3-admin2-a', 'admin')
        services.demander_signature(
            self.doc, signataire_nom='A', signataire_email='a@example.com',
            company=self.co_a, created_by=self.admin_a)
        services.demander_signature(
            self.doc, signataire_nom='B', signataire_email='b@example.com',
            company=self.co_a, created_by=autre_admin)
        result = selectors.tableau_bord_signatures(
            self.co_a, emetteur=self.admin_a.pk)
        self.assertEqual(result['total'], 1)

    def test_isolation_societe(self):
        co_b = make_company('zged3-b', 'Zged3 B')
        admin_b = make_user(co_b, 'zged3-admin-b', 'admin')
        cab_b = Cabinet.objects.create(company=co_b, nom='Admin B')
        folder_b = Folder.objects.create(
            company=co_b, cabinet=cab_b, nom='Contrats B')
        doc_b = Document.objects.create(
            company=co_b, folder=folder_b, nom='contrat-b.pdf')
        services.demander_signature(
            doc_b, signataire_nom='B', signataire_email='b@example.com',
            company=co_b, created_by=admin_b)
        result_a = selectors.tableau_bord_signatures(self.co_a)
        self.assertEqual(result_a['total'], 0)


class ViewTests(ZGed3Base):
    def test_endpoint_gestionnaire_ok(self):
        services.demander_signature(
            self.doc, signataire_nom='A', signataire_email='a@example.com',
            company=self.co_a, created_by=self.admin_a)
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/demandes-signature/tableau-bord/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('colonnes', resp.data)
        self.assertEqual(resp.data['total'], 1)

    def test_endpoint_non_gestionnaire_403(self):
        api = auth(self.autre_a)
        resp = api.get('/api/django/ged/demandes-signature/tableau-bord/')
        self.assertEqual(resp.status_code, 403)
