"""ZGED6 — Centralisation des fichiers par module vers un dossier de
destination configurable.

Couvre :
  * un routage `paie_bulletin -> "Paie/{{ annee }}"` configuré : la génération
    d'un bulletin dépose son PDF dans le bon dossier avec les tags par défaut ;
  * sans routage, rien ne change (no-op) ;
  * idempotent par source+référence ;
  * résolution des jetons, tags, scoping.
"""
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.ged import services
from core.events import document_produit
from apps.ged.models import (
    Cabinet, Document, DocumentTag, RoutageDocumentaire,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def _fake_pdf(name='bulletin.pdf'):
    # En-tête %PDF- minimal reconnu par le détecteur de type de
    # `records.storage` (cf. `_ALLOWED`), pour passer la validation réelle.
    buf = BytesIO(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n' + b'0' * 100)
    buf.name = name
    buf.size = len(buf.getvalue())
    buf.seek(0)
    return buf


class ZGed6Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged6-a', 'Zged6 A')
        self.admin_a = make_user(self.co_a, 'zged6-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Paie')
        self.tag = DocumentTag.objects.create(
            company=self.co_a, nom='Bulletin', slug='bulletin')


class ServiceTests(ZGed6Base):
    def test_sans_routage_renvoie_none_no_op(self):
        result = services.router_document_module(
            'paie_bulletin', company=self.co_a, file=_fake_pdf(),
            filename='bulletin.pdf', reference='2026-07-001',
            contexte={'annee': 2026})
        self.assertIsNone(result)
        self.assertEqual(Document.objects.filter(company=self.co_a).count(), 0)

    def test_routage_configure_depose_dans_bon_dossier_avec_tags(self):
        routage = RoutageDocumentaire.objects.create(
            company=self.co_a, source='paie_bulletin',
            cabinet_cible=self.cab_a, dossier_cible='Paie/{{ annee }}')
        routage.tags_defaut.add(self.tag)

        document = services.router_document_module(
            'paie_bulletin', company=self.co_a, file=_fake_pdf(),
            filename='bulletin.pdf', reference='2026-07-001',
            contexte={'annee': 2026}, uploaded_by=self.admin_a)

        self.assertIsNotNone(document)
        self.assertEqual(document.folder.nom, '2026')
        self.assertEqual(document.folder.parent.nom, 'Paie')
        self.assertEqual(document.folder.cabinet_id, self.cab_a.pk)
        self.assertEqual(document.versions.count(), 1)
        tags = {a.tag.slug for a in document.tag_assignments.select_related('tag')}
        self.assertEqual(tags, {'bulletin'})

    def test_idempotent_par_source_reference(self):
        RoutageDocumentaire.objects.create(
            company=self.co_a, source='paie_bulletin',
            cabinet_cible=self.cab_a, dossier_cible='Paie/{{ annee }}')
        doc1 = services.router_document_module(
            'paie_bulletin', company=self.co_a, file=_fake_pdf(),
            filename='bulletin.pdf', reference='2026-07-001',
            contexte={'annee': 2026})
        doc2 = services.router_document_module(
            'paie_bulletin', company=self.co_a, file=_fake_pdf(),
            filename='bulletin.pdf', reference='2026-07-001',
            contexte={'annee': 2026})
        self.assertEqual(doc1.pk, doc2.pk)
        self.assertEqual(Document.objects.filter(company=self.co_a).count(), 1)

    def test_routage_inactif_est_ignore(self):
        RoutageDocumentaire.objects.create(
            company=self.co_a, source='paie_bulletin',
            cabinet_cible=self.cab_a, dossier_cible='Paie', actif=False)
        result = services.router_document_module(
            'paie_bulletin', company=self.co_a, file=_fake_pdf(),
            filename='bulletin.pdf')
        self.assertIsNone(result)

    def test_evenement_document_produit_declenche_le_routage(self):
        RoutageDocumentaire.objects.create(
            company=self.co_a, source='rh_document',
            cabinet_cible=self.cab_a, dossier_cible='RH')
        document_produit.send(
            sender=None, source='rh_document', company=self.co_a,
            file=_fake_pdf(), filename='attestation.pdf', reference='',
            contexte={}, uploaded_by=self.admin_a)
        self.assertEqual(
            Document.objects.filter(company=self.co_a, folder__nom='RH').count(),
            1)

    def test_scoping_societe(self):
        co_b = make_company('zged6-b', 'Zged6 B')
        cab_b = Cabinet.objects.create(company=co_b, nom='Paie B')
        RoutageDocumentaire.objects.create(
            company=co_b, source='paie_bulletin',
            cabinet_cible=cab_b, dossier_cible='Paie')
        # Aucun routage pour co_a sur cette source -> no-op malgré le routage
        # existant chez co_b.
        result = services.router_document_module(
            'paie_bulletin', company=self.co_a, file=_fake_pdf())
        self.assertIsNone(result)
