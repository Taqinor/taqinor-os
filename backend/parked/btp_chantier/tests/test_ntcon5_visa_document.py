"""Tests NTCON5 — Visas de documents techniques (soumission→observations→
approbation).

Couvre :
* soumission d'un visa (référence race-safe) ;
* cycle complet : soumettre → soumettre-observations → approuver ;
* refuser un visa ;
* state machine stricte : agir sur un visa déjà décidé → 400 ;
* une nouvelle ``ged.DocumentVersion`` resoumet automatiquement le visa
  (statut → soumis, ré-ouverture tracée) ;
* cross-tenant refusé.
"""
from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import VisaDocument

from .helpers import auth, make_chantier, make_company, make_user

BASE = '/api/django/btp-chantier/visas/'


def make_visa(company, chantier, soumis_par, **kwargs):
    kwargs.setdefault('reference', 'VIS-TEST-0001')
    kwargs.setdefault('document_ged_id', 7)
    return VisaDocument.objects.create(
        company=company, chantier=chantier, soumis_par=soumis_par, **kwargs)


class VisaDocumentApiTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.soumetteur = make_user(self.co, username='soumetteur')
        self.revuseur = make_user(self.co, username='revuseur')
        self.chantier = make_chantier(self.co)

    def test_soumettre_visa(self):
        api = auth(self.soumetteur)
        resp = api.post(BASE, {
            'chantier': self.chantier.id,
            'document_ged_id': 12,
            'type_visa': 'plan_execution',
            'delai_revue_jours': 7,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['statut'], 'soumis')
        self.assertTrue(resp.data['reference'].startswith('VIS-'))
        self.assertIsNotNone(resp.data['date_limite'])

    def test_cycle_observations_puis_approbation(self):
        visa = make_visa(self.co, self.chantier, self.soumetteur)
        api = auth(self.revuseur)

        resp = api.post(
            f'{BASE}{visa.id}/soumettre-observations/',
            {'observations': 'Corriger le repère de niveau'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'en_revue')

        resp = api.post(
            f'{BASE}{visa.id}/approuver/',
            {'avec_observations': True, 'observations': 'RAS finalement'},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'approuve_avec_observations')

    def test_approuver_sans_reserve(self):
        visa = make_visa(self.co, self.chantier, self.soumetteur)
        api = auth(self.revuseur)
        resp = api.post(f'{BASE}{visa.id}/approuver/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'approuve_sans_reserve')

    def test_refuser_visa(self):
        visa = make_visa(self.co, self.chantier, self.soumetteur)
        api = auth(self.revuseur)
        resp = api.post(
            f'{BASE}{visa.id}/refuser/',
            {'observations': 'Non conforme'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['statut'], 'refuse')

    def test_agir_sur_visa_deja_decide_refuse(self):
        visa = make_visa(
            self.co, self.chantier, self.soumetteur,
            statut=VisaDocument.Statut.APPROUVE_SANS_RESERVE)
        api = auth(self.revuseur)
        resp = api.post(f'{BASE}{visa.id}/approuver/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        resp = api.post(f'{BASE}{visa.id}/refuser/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_tenant_refused(self):
        other_co = make_company()
        other_chantier = make_chantier(other_co)
        other_visa = make_visa(
            other_co, other_chantier, make_user(other_co))
        api = auth(self.soumetteur)
        resp = api.get(f'{BASE}{other_visa.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class VisaResoumissionTests(TestCase):
    """NTCON5 — resoumission automatique sur nouvelle ``ged.DocumentVersion``."""

    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)

    def _make_ged_document(self, nom='Plan RDC'):
        from apps.ged.models import Cabinet, Document, Folder
        # get_or_create : plusieurs documents de ce TestCase partagent le même
        # classeur/dossier GED — un second appel avec la même société ne doit
        # jamais retenter une création et violer l'unique (company, nom).
        cabinet, _ = Cabinet.objects.get_or_create(
            company=self.co, nom='BTP')
        folder, _ = Folder.objects.get_or_create(
            company=self.co, cabinet=cabinet, nom='Plans')
        return Document.objects.create(
            company=self.co, folder=folder, nom=nom)

    def test_nouvelle_version_reouvre_visa_approuve(self):
        document = self._make_ged_document()
        visa = make_visa(
            self.co, self.chantier, self.user,
            document_ged_id=document.id,
            statut=VisaDocument.Statut.APPROUVE_SANS_RESERVE,
            nb_resoumissions=0)

        from apps.ged.models import DocumentVersion
        DocumentVersion.objects.create(
            company=self.co, document=document, version=2,
            file_key='x', filename='plan.pdf', uploaded_by=self.user)

        visa.refresh_from_db()
        self.assertEqual(visa.statut, VisaDocument.Statut.SOUMIS)
        self.assertEqual(visa.nb_resoumissions, 1)

    def test_visa_dun_autre_document_non_affecte(self):
        document = self._make_ged_document()
        autre_document = self._make_ged_document()
        visa_autre = make_visa(
            self.co, self.chantier, self.user,
            reference='VIS-AUTRE-0001',
            document_ged_id=autre_document.id,
            statut=VisaDocument.Statut.APPROUVE_SANS_RESERVE)

        from apps.ged.models import DocumentVersion
        DocumentVersion.objects.create(
            company=self.co, document=document, version=2,
            file_key='x', filename='plan.pdf', uploaded_by=self.user)

        visa_autre.refresh_from_db()
        self.assertEqual(
            visa_autre.statut, VisaDocument.Statut.APPROUVE_SANS_RESERVE)
