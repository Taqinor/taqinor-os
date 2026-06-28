"""
FG297 — Contrôle documentaire de projet (plans & révisions).

Couvre :
  * DocumentProjet : CRUD via l'API, filtrage par chantier et type_doc,
    scope société, garde tenant sur le chantier ciblé.
  * RevisionDocument : création avec auteur posé côté serveur, indice unique
    par document, scope société, garde tenant sur le document ciblé.

Run :
    python manage.py test apps.installations.tests_document -v2
"""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import DocumentProjet, RevisionDocument
from apps.installations.services import create_installation_from_devis

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    slug = slug or f'doc-co-{n}'
    nom = nom or f'Doc Co {n}'
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_chantier(company, user, type_installation='residentiel'):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Doc', prenom='Client',
        email=f'doc-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Doc', prenom='Client', stage='SIGNED',
        type_installation=type_installation)
    devis = Devis.objects.create(
        company=company, reference=f'DEV-DOC-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation=type_installation)
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


# ── FG297 — DocumentProjet ────────────────────────────────────────────────────

class TestFG297DocumentProjet(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'd297-{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def test_create_document_sets_company_server_side(self):
        """FG297 — la société est posée côté serveur, jamais lue du corps."""
        other = make_company()
        r = self.api.post(f'{BASE}/documents-projet/', {
            'installation': self.inst.id,
            'type_doc': 'schema_unifilaire',
            'titre': 'SLD principal',
            'company': other.id,  # ignoré côté serveur
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        doc = DocumentProjet.objects.get(id=r.data['id'])
        self.assertEqual(doc.company_id, self.company.id)
        self.assertEqual(doc.type_doc, 'schema_unifilaire')
        self.assertEqual(doc.titre, 'SLD principal')

    def test_type_doc_display_in_payload(self):
        """FG297 — le libellé français du type est exposé en lecture."""
        r = self.api.post(f'{BASE}/documents-projet/', {
            'installation': self.inst.id,
            'type_doc': 'note_calcul',
            'titre': "Note de dimensionnement",
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['type_doc_display'], "Note de calcul")

    def test_filter_by_installation(self):
        """FG297 — la liste se filtre par chantier."""
        inst2 = make_chantier(self.company, self.user)
        DocumentProjet.objects.create(
            company=self.company, installation=self.inst,
            type_doc='calepinage', titre='Calepinage A')
        DocumentProjet.objects.create(
            company=self.company, installation=inst2,
            type_doc='calepinage', titre='Calepinage B')
        r = self.api.get(f'{BASE}/documents-projet/',
                         {'installation': self.inst.id})
        self.assertEqual(r.status_code, 200)
        titres = [d['titre'] for d in r.data['results']]
        self.assertIn('Calepinage A', titres)
        self.assertNotIn('Calepinage B', titres)

    def test_filter_by_type_doc(self):
        """FG297 — la liste se filtre par type_doc."""
        DocumentProjet.objects.create(
            company=self.company, installation=self.inst,
            type_doc='schema_unifilaire', titre='SLD')
        DocumentProjet.objects.create(
            company=self.company, installation=self.inst,
            type_doc='calepinage', titre='CAL')
        r = self.api.get(f'{BASE}/documents-projet/',
                         {'type_doc': 'schema_unifilaire'})
        self.assertEqual(r.status_code, 200)
        titres = [d['titre'] for d in r.data['results']]
        self.assertIn('SLD', titres)
        self.assertNotIn('CAL', titres)

    def test_company_isolation(self):
        """FG297 — la société B ne voit pas les documents de A."""
        DocumentProjet.objects.create(
            company=self.company, installation=self.inst,
            type_doc='autre', titre='Secret A')
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'd297b-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        r = auth(user_b).get(f'{BASE}/documents-projet/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_cross_company_installation_rejected(self):
        """FG297 — impossible de rattacher un document au chantier d'une autre
        société."""
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'd297c-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        inst_b = make_chantier(company_b, user_b)
        r = self.api.post(f'{BASE}/documents-projet/', {
            'installation': inst_b.id,
            'type_doc': 'autre', 'titre': 'Intrus',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_revisions_nested_in_document(self):
        """FG297 — les révisions d'un document sont imbriquées en lecture."""
        doc = DocumentProjet.objects.create(
            company=self.company, installation=self.inst,
            type_doc='schema_unifilaire', titre='SLD avec révisions')
        RevisionDocument.objects.create(
            company=self.company, document=doc, indice='A',
            date_revision=datetime.date(2026, 6, 1), auteur=self.user)
        RevisionDocument.objects.create(
            company=self.company, document=doc, indice='B',
            date_revision=datetime.date(2026, 6, 15), auteur=self.user)
        r = self.api.get(f'{BASE}/documents-projet/{doc.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['nb_revisions'], 2)
        self.assertEqual(len(r.data['inst_revisions']), 2)

    def test_update_titre(self):
        """FG297 — on peut mettre à jour le titre par PATCH."""
        doc = DocumentProjet.objects.create(
            company=self.company, installation=self.inst,
            type_doc='calepinage', titre='v0')
        r = self.api.patch(f'{BASE}/documents-projet/{doc.id}/', {
            'titre': 'v1 corrigé',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        doc.refresh_from_db()
        self.assertEqual(doc.titre, 'v1 corrigé')


# ── FG297 — RevisionDocument ──────────────────────────────────────────────────

class TestFG297RevisionDocument(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'r297-{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)
        self.doc = DocumentProjet.objects.create(
            company=self.company, installation=self.inst,
            type_doc='note_calcul', titre='Note dimensionnement')

    def test_create_revision_sets_auteur_server_side(self):
        """FG297 — l'auteur est posé côté serveur (user courant), jamais du
        corps."""
        other_user = User.objects.create_user(
            username=f'r297x-{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        r = self.api.post(f'{BASE}/revisions-document/', {
            'document': self.doc.id,
            'indice': 'A',
            'date_revision': '2026-06-01',
            'auteur': other_user.id,  # ignoré côté serveur
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        rev = RevisionDocument.objects.get(id=r.data['id'])
        self.assertEqual(rev.auteur_id, self.user.id)
        self.assertEqual(rev.indice, 'A')
        self.assertEqual(str(rev.date_revision), '2026-06-01')

    def test_revision_company_set_server_side(self):
        """FG297 — la société est posée côté serveur sur la révision."""
        other = make_company()
        r = self.api.post(f'{BASE}/revisions-document/', {
            'document': self.doc.id,
            'indice': 'A',
            'date_revision': '2026-06-01',
            'company': other.id,  # ignoré
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        rev = RevisionDocument.objects.get(id=r.data['id'])
        self.assertEqual(rev.company_id, self.company.id)

    def test_auteur_nom_in_payload(self):
        """FG297 — le nom d'utilisateur de l'auteur est exposé en lecture."""
        r = self.api.post(f'{BASE}/revisions-document/', {
            'document': self.doc.id,
            'indice': 'A',
            'date_revision': '2026-06-01',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['auteur_nom'], self.user.username)

    def test_unique_indice_per_document(self):
        """FG297 — deux révisions du même document ne peuvent pas avoir le même
        indice."""
        RevisionDocument.objects.create(
            company=self.company, document=self.doc, indice='A',
            date_revision=datetime.date(2026, 6, 1), auteur=self.user)
        r = self.api.post(f'{BASE}/revisions-document/', {
            'document': self.doc.id,
            'indice': 'A',
            'date_revision': '2026-06-10',
        }, format='json')
        self.assertIn(r.status_code, [400, 409], r.data)

    def test_same_indice_allowed_across_documents(self):
        """FG297 — le même indice peut exister dans des documents distincts."""
        doc2 = DocumentProjet.objects.create(
            company=self.company, installation=self.inst,
            type_doc='calepinage', titre='CAL')
        RevisionDocument.objects.create(
            company=self.company, document=self.doc, indice='A',
            date_revision=datetime.date(2026, 6, 1), auteur=self.user)
        r = self.api.post(f'{BASE}/revisions-document/', {
            'document': doc2.id,
            'indice': 'A',
            'date_revision': '2026-06-01',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_filter_by_document(self):
        """FG297 — la liste des révisions se filtre par document."""
        doc2 = DocumentProjet.objects.create(
            company=self.company, installation=self.inst,
            type_doc='calepinage', titre='CAL2')
        RevisionDocument.objects.create(
            company=self.company, document=self.doc, indice='A',
            date_revision=datetime.date(2026, 6, 1), auteur=self.user)
        RevisionDocument.objects.create(
            company=self.company, document=doc2, indice='A',
            date_revision=datetime.date(2026, 6, 2), auteur=self.user)
        r = self.api.get(f'{BASE}/revisions-document/',
                         {'document': self.doc.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['indice'], 'A')

    def test_company_isolation(self):
        """FG297 — la société B ne voit pas les révisions de A."""
        RevisionDocument.objects.create(
            company=self.company, document=self.doc, indice='A',
            date_revision=datetime.date(2026, 6, 1), auteur=self.user)
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'r297b-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        r = auth(user_b).get(f'{BASE}/revisions-document/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_cross_company_document_rejected(self):
        """FG297 — impossible de rattacher une révision au document d'une autre
        société."""
        company_b = make_company()
        user_b = User.objects.create_user(
            username=f'r297c-{next(_seq)}', password='x',
            role_legacy='responsable', company=company_b)
        inst_b = make_chantier(company_b, user_b)
        doc_b = DocumentProjet.objects.create(
            company=company_b, installation=inst_b,
            type_doc='autre', titre='Secret B')
        # user de la société A tente de viser le document de B.
        r = self.api.post(f'{BASE}/revisions-document/', {
            'document': doc_b.id,
            'indice': 'A',
            'date_revision': '2026-06-01',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_multiple_revisions_ordering(self):
        """FG297 — les révisions sont triées par date décroissante (plus récente
        en premier)."""
        RevisionDocument.objects.create(
            company=self.company, document=self.doc, indice='A',
            date_revision=datetime.date(2026, 6, 1), auteur=self.user)
        RevisionDocument.objects.create(
            company=self.company, document=self.doc, indice='B',
            date_revision=datetime.date(2026, 6, 15), auteur=self.user)
        r = self.api.get(f'{BASE}/revisions-document/',
                         {'document': self.doc.id})
        self.assertEqual(r.status_code, 200)
        indices = [rv['indice'] for rv in r.data['results']]
        # B (date plus récente) doit apparaître en premier.
        self.assertEqual(indices[0], 'B')
        self.assertEqual(indices[1], 'A')
