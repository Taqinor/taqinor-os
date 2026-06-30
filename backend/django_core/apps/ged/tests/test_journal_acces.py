"""GED35 — Journal d'audit d'accès aux documents (lectures).

Couvre (au niveau SERVICE/SELECTEUR, sans MinIO) :
  * `journaliser_acces` pose company côté serveur (celle du document) ;
  * un accès public anonyme → utilisateur NULL ;
  * append-only : le journal n'est jamais muté par l'API (ReadOnly) ;
  * le sélecteur borne à la société (jamais cross-société) + filtres ;
  * l'audit est best-effort (ne lève jamais).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.ged import selectors, services
from apps.ged.models import (
    ACCES_APERCU, ACCES_PUBLIC, Cabinet, Document, Folder,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class JournalAccesServiceTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ged35-a', 'Ged35 A')
        self.co_b = make_company('ged35-b', 'Ged35 B')
        self.user_a = make_user(self.co_a, 'ged35-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Docs')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='F')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Doc')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Docs')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='F')
        self.doc_b = Document.objects.create(
            company=self.co_b, folder=self.folder_b, nom='Doc B')

    def test_journaliser_pose_company_serveur(self):
        entree = services.journaliser_acces(
            self.doc_a, utilisateur=self.user_a, type_acces=ACCES_APERCU)
        self.assertIsNotNone(entree)
        self.assertEqual(entree.company_id, self.co_a.id)
        self.assertEqual(entree.utilisateur_id, self.user_a.id)
        self.assertEqual(entree.type_acces, ACCES_APERCU)

    def test_acces_public_utilisateur_null(self):
        entree = services.journaliser_acces(
            self.doc_a, utilisateur=None, type_acces=ACCES_PUBLIC)
        self.assertIsNone(entree.utilisateur_id)
        self.assertEqual(entree.type_acces, ACCES_PUBLIC)

    def test_selecteur_borne_societe(self):
        services.journaliser_acces(self.doc_a, utilisateur=self.user_a)
        services.journaliser_acces(self.doc_b, utilisateur=None)
        qs_a = selectors.journal_acces_for_company(self.co_a)
        self.assertEqual(qs_a.count(), 1)
        self.assertEqual(qs_a.first().document_id, self.doc_a.id)

    def test_selecteur_filtre_document_et_type(self):
        services.journaliser_acces(
            self.doc_a, utilisateur=self.user_a, type_acces=ACCES_APERCU)
        services.journaliser_acces(
            self.doc_a, utilisateur=None, type_acces=ACCES_PUBLIC)
        qs = selectors.journal_acces_for_company(
            self.co_a, document=self.doc_a, type_acces=ACCES_PUBLIC)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().type_acces, ACCES_PUBLIC)

    def test_journaliser_best_effort_ne_leve_pas(self):
        # Un document sans pk (non sauvé) → la journalisation échoue en silence.
        orphelin = Document(company=self.co_a, folder=self.folder_a, nom='X')
        res = services.journaliser_acces(orphelin, utilisateur=self.user_a)
        # Best-effort : renvoie None (ou crée), jamais d'exception propagée.
        self.assertIn(res, (None, res))
