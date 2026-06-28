"""Tests LITIGE4 — Litige qualité ↔ QHSE : lien NCR + audit fin de chantier.

Couvre :
- pose des liens lâches ``ncr_id`` / ``audit_id`` sur une Reclamation (set/read) ;
- résolution des aperçus QHSE via les sélecteurs QHSE (lecture cross-app par id,
  jamais un import de modèle) et exposition côté API (``ncr`` / ``audit``) ;
- isolation multi-société : un NCR / audit d'une autre société ne fuite pas dans
  l'aperçu d'un litige (le sélecteur scope par ``company``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.litiges.models import Reclamation
from apps.qhse.models import Audit, GrilleAudit, NonConformite
from apps.qhse.selectors import (
    audit_apercu, audit_by_id, ncr_apercu, ncr_by_id,
)

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


class Litige4SelectorTests(TestCase):
    """Sélecteurs QHSE de lecture (NCR / audit) consommés par litiges."""

    def setUp(self):
        self.co_a = make_company('litige4-sel-a', 'A')
        self.co_b = make_company('litige4-sel-b', 'B')
        self.ncr = NonConformite.objects.create(
            company=self.co_a, titre='Câblage non conforme',
            gravite=NonConformite.Gravite.MAJEURE)
        self.grille = GrilleAudit.objects.create(
            company=self.co_a, nom='Audit fin de chantier')
        self.audit = Audit.objects.create(
            company=self.co_a, grille=self.grille)

    # ── ncr_by_id / audit_by_id ──────────────────────────────────────────────
    def test_ncr_by_id_returns_instance(self):
        self.assertEqual(ncr_by_id(self.ncr.id, self.co_a), self.ncr)

    def test_audit_by_id_returns_instance(self):
        self.assertEqual(audit_by_id(self.audit.id, self.co_a), self.audit)

    def test_ncr_by_id_none_for_missing(self):
        self.assertIsNone(ncr_by_id(999999, self.co_a))

    def test_ncr_by_id_none_for_falsy(self):
        self.assertIsNone(ncr_by_id(None, self.co_a))

    def test_ncr_by_id_company_scoped(self):
        """Un NCR de A n'est pas lisible avec la société B."""
        self.assertIsNone(ncr_by_id(self.ncr.id, self.co_b))

    def test_audit_by_id_company_scoped(self):
        self.assertIsNone(audit_by_id(self.audit.id, self.co_b))

    # ── ncr_apercu / audit_apercu ────────────────────────────────────────────
    def test_ncr_apercu_shape(self):
        ap = ncr_apercu(self.ncr.id, self.co_a)
        self.assertEqual(ap['id'], self.ncr.id)
        self.assertEqual(ap['titre'], 'Câblage non conforme')
        self.assertEqual(ap['gravite'], NonConformite.Gravite.MAJEURE)
        self.assertEqual(ap['gravite_display'], 'Majeure')
        self.assertEqual(ap['statut'], NonConformite.Statut.OUVERTE)

    def test_audit_apercu_shape(self):
        ap = audit_apercu(self.audit.id, self.co_a)
        self.assertEqual(ap['id'], self.audit.id)
        self.assertEqual(ap['grille'], 'Audit fin de chantier')
        self.assertEqual(ap['statut'], Audit.Statut.BROUILLON)

    def test_apercu_none_cross_tenant(self):
        self.assertIsNone(ncr_apercu(self.ncr.id, self.co_b))
        self.assertIsNone(audit_apercu(self.audit.id, self.co_b))


class Litige4ModelTests(TestCase):
    """Pose et lecture des liens lâches sur la Reclamation."""

    def setUp(self):
        self.co = make_company('litige4-mod', 'M')

    def test_links_default_null(self):
        r = Reclamation.objects.create(
            company=self.co, objet='Litige qualité',
            type_reclamation=Reclamation.TypeReclamation.QUALITE)
        self.assertIsNone(r.ncr_id)
        self.assertIsNone(r.audit_id)

    def test_links_set_and_read(self):
        ncr = NonConformite.objects.create(company=self.co, titre='NCR')
        grille = GrilleAudit.objects.create(company=self.co, nom='G')
        audit = Audit.objects.create(company=self.co, grille=grille)
        r = Reclamation.objects.create(
            company=self.co, objet='Litige qualité',
            type_reclamation=Reclamation.TypeReclamation.QUALITE,
            ncr_id=ncr.id, audit_id=audit.id)
        r.refresh_from_db()
        self.assertEqual(r.ncr_id, ncr.id)
        self.assertEqual(r.audit_id, audit.id)


class Litige4ApiTests(TestCase):
    """L'API surface les aperçus QHSE et accepte le rattachement par id."""

    BASE = '/api/django/litiges/reclamations/'

    def setUp(self):
        self.co_a = make_company('litige4-api-a', 'A')
        self.co_b = make_company('litige4-api-b', 'B')
        self.user_a = make_user(self.co_a, 'litige4-api-a')
        self.ncr = NonConformite.objects.create(
            company=self.co_a, titre='Pose défectueuse')
        self.grille = GrilleAudit.objects.create(
            company=self.co_a, nom='Fin chantier')
        self.audit = Audit.objects.create(
            company=self.co_a, grille=self.grille)

    def test_create_with_qhse_links_forces_company(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'objet': 'Litige qualité',
            'type_reclamation': Reclamation.TypeReclamation.QUALITE,
            'ncr_id': self.ncr.id,
            'audit_id': self.audit.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Reclamation.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.ncr_id, self.ncr.id)
        self.assertEqual(obj.audit_id, self.audit.id)

    def test_detail_surfaces_qhse_apercu(self):
        r = Reclamation.objects.create(
            company=self.co_a, objet='Litige qualité',
            ncr_id=self.ncr.id, audit_id=self.audit.id)
        resp = auth(self.user_a).get(f'{self.BASE}{r.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['ncr']['titre'], 'Pose défectueuse')
        self.assertEqual(resp.data['audit']['grille'], 'Fin chantier')

    def test_apercu_null_when_unlinked(self):
        r = Reclamation.objects.create(company=self.co_a, objet='Sans lien')
        resp = auth(self.user_a).get(f'{self.BASE}{r.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['ncr'])
        self.assertIsNone(resp.data['audit'])

    def test_apercu_null_when_ncr_belongs_to_other_company(self):
        """Un id NCR pointant une autre société ne fuite aucun aperçu."""
        ncr_b = NonConformite.objects.create(company=self.co_b, titre='NCR B')
        r = Reclamation.objects.create(
            company=self.co_a, objet='Litige qualité', ncr_id=ncr_b.id)
        resp = auth(self.user_a).get(f'{self.BASE}{r.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['ncr'])
