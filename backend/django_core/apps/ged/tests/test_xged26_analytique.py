"""XGED26 — Analytique workflow & signature.

Couvre :
  * les KPIs se calculent sur des données réelles (temps de cycle, taux de
    complétion, délai envoi->signature, compte par statut/émetteur) ;
  * divide-by-zero gardé (aucune donnée -> moyennes None, pas de 500) ;
  * période filtrable (date_debut/date_fin) ;
  * non-gestionnaire -> 403 ; isolation société.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import selectors, services
from apps.ged.models import (
    Cabinet, DemandeApprobation, DemandeSignatureDocument, Document, Folder,
)

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


class XGed26Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged26-a', 'Xged26 A')
        self.admin_a = make_user(self.co_a, 'xged26-admin-a', 'admin')
        self.autre_a = make_user(self.co_a, 'xged26-autre-a', 'normal')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')


class AnalytiqueApprobationsTests(XGed26Base):
    def test_aucune_donnee_moyennes_none(self):
        result = selectors.analytique_approbations(self.co_a)
        self.assertIsNone(result['temps_cycle_moyen_jours'])
        self.assertEqual(result['total'], 0)
        self.assertEqual(result['par_statut'], {})

    def test_temps_cycle_moyen_et_compteurs(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='devis.pdf')
        demande = services.request_review(doc, user=self.admin_a)
        # Force un created_at dans le passé pour un delta mesurable.
        DemandeApprobation.objects.filter(pk=demande.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=2))
        demande.refresh_from_db()
        services.approve_demande(demande, user=self.admin_a)

        result = selectors.analytique_approbations(self.co_a)
        self.assertEqual(result['total'], 1)
        self.assertIsNotNone(result['temps_cycle_moyen_jours'])
        self.assertGreater(result['temps_cycle_moyen_jours'], 1.9)
        self.assertEqual(result['par_statut'].get('approuve'), 1)
        self.assertEqual(result['par_emetteur'].get('xged26-admin-a'), 1)

    def test_periode_filtrable(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='devis.pdf')
        demande = services.request_review(doc, user=self.admin_a)
        vieille_date = timezone.now() - datetime.timedelta(days=100)
        DemandeApprobation.objects.filter(pk=demande.pk).update(
            created_at=vieille_date)
        result = selectors.analytique_approbations(
            self.co_a, date_debut=timezone.now().date() - datetime.timedelta(days=1))
        self.assertEqual(result['total'], 0)


class AnalytiqueSignaturesTests(XGed26Base):
    def test_aucune_donnee_taux_none(self):
        result = selectors.analytique_signatures(self.co_a)
        self.assertIsNone(result['taux_completion'])
        self.assertEqual(result['total'], 0)

    def test_taux_completion_et_delai(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='contrat.pdf')
        d1 = DemandeSignatureDocument.objects.create(
            company=self.co_a, document=doc, signataire_nom='Client A',
            signataire_email='a@example.com', statut='signe',
            created_by=self.admin_a)
        DemandeSignatureDocument.objects.filter(pk=d1.pk).update(
            date_demande=timezone.now() - datetime.timedelta(days=3),
            date_signature=timezone.now())
        DemandeSignatureDocument.objects.create(
            company=self.co_a, document=doc, signataire_nom='Client B',
            signataire_email='b@example.com', statut='en_attente',
            created_by=self.admin_a)

        result = selectors.analytique_signatures(self.co_a)
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['taux_completion'], 50.0)
        self.assertIsNotNone(result['delai_moyen_envoi_signature_jours'])
        self.assertGreater(result['delai_moyen_envoi_signature_jours'], 2.9)


class AnalytiqueViewTests(XGed26Base):
    def test_endpoint_gestionnaire_ok(self):
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/analytique/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('approbations', resp.data)
        self.assertIn('signatures', resp.data)

    def test_endpoint_non_gestionnaire_403(self):
        api = auth(self.autre_a)
        resp = api.get('/api/django/ged/analytique/')
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe(self):
        co_b = make_company('xged26-b', 'Xged26 B')
        cab_b = Cabinet.objects.create(company=co_b, nom='Admin B')
        folder_b = Folder.objects.create(
            company=co_b, cabinet=cab_b, nom='Dossier B')
        admin_b = make_user(co_b, 'xged26-admin-b', 'admin')
        doc_b = Document.objects.create(
            company=co_b, folder=folder_b, nom='devis-b.pdf')
        services.request_review(doc_b, user=admin_b)

        result_a = selectors.analytique_approbations(self.co_a)
        self.assertEqual(result_a['total'], 0)
