"""NTLOG49 (volet douane) — ``DossierExport`` devient une cible suivable
(``records.Follower``/``Comment``/``Tag``) via ``apps/douane/platform.py``
(``record_targets``).

Le volet ``apps/transport`` (``OrdreTransport``/``DossierImport``) est HORS
PÉRIMÈTRE de ce test (lane concurrente, voir ``docs/plans/PLAN_SUPPLY.md``
NTLOG49). Critère d'acceptation adapté au volet EXPORT réellement construit
dans cette app : suivre un ``DossierExport`` via ``records.Follower`` fait
apparaître ses changements de statut dans le flux d'activité générique
(``records.Activity``), sans dupliquer de journal maison propre à ce module
(il n'en a aucun).

Run :
    python manage.py test apps.douane.tests.test_ntlog49_chatter_follower -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.douane.models import DossierExport
from apps.douane.services import cloturer_dossier_export
from apps.records.services import chatter_qs

User = get_user_model()
_seq = itertools.count(1)
BASE_DOUANE = '/api/django/douane'
BASE_RECORDS = '/api/django/records'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntlog49-co-{n}', defaults={'nom': f'NTLOG49 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntlog49-{next(_seq)}', password='x',
        role_legacy=role, company=company)


class TestDossierExportEstUneCibleGenerique(TestCase):
    """Enregistrement au registre (``apps.douane.platform.PLATFORM``) —
    ``douane.dossierexport`` doit être un ``records.ALLOWED_TARGETS``
    valide, sinon les endpoints génériques ci-dessous renverraient tous 400
    (« Type de cible non autorisé »)."""

    def test_declare_dans_le_manifeste_plateforme_douane(self):
        from apps.douane.platform import PLATFORM
        self.assertIn('douane.dossierexport', PLATFORM['record_targets'])

    def test_douane_dossierexport_dans_allowed_targets(self):
        from apps.records.models import ALLOWED_TARGETS
        self.assertIn(('douane', 'dossierexport'), ALLOWED_TARGETS)


class TestDossierExportEstSuivable(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.dossier = DossierExport.objects.create(
            company=self.company, numero='EXP-NTLOG49-1',
            statut=DossierExport.Statut.LEVE)

    def test_suivre_le_dossier_via_l_api_followers(self):
        r = self.api.post(f'{BASE_RECORDS}/followers/', {
            'model': 'douane.dossierexport', 'id': self.dossier.id})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

    def test_tag_libre_applicable_au_dossier(self):
        tag_resp = self.api.post(f'{BASE_RECORDS}/tags/', {'nom': 'urgent'})
        self.assertEqual(
            tag_resp.status_code, status.HTTP_201_CREATED, tag_resp.data)
        r = self.api.post(f'{BASE_RECORDS}/tagged-items/', {
            'model': 'douane.dossierexport', 'id': self.dossier.id,
            'tag': tag_resp.data['id']})
        self.assertIn(
            r.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED), r.data)

    def test_commentaire_generique_sur_le_dossier(self):
        r = self.api.post(f'{BASE_RECORDS}/comments/', {
            'model': 'douane.dossierexport', 'id': self.dossier.id,
            'body': 'Pièces manquantes, relancer le client.'})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

    def test_chatter_historique_et_noter_accessibles(self):
        """ChatterViewSetMixin (NTLOG49) — mêmes deux actions que
        ``transport.OrdreTransportViewSet``."""
        r = self.api.get(
            f'{BASE_DOUANE}/dossiers-export/{self.dossier.id}/chatter/historique/')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

        r2 = self.api.post(
            f'{BASE_DOUANE}/dossiers-export/{self.dossier.id}/chatter/noter/',
            {'body': 'Relance transitaire envoyée.'})
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED, r2.data)

    def test_changement_de_statut_visible_dans_le_flux_generique(self):
        """Critère d'acceptation NTLOG49 (adapté export) : le changement de
        statut du dossier apparaît dans le flux d'activité générique — sans
        dupliquer un journal maison (ce module n'en a aucun)."""
        cloturer_dossier_export(self.dossier, user=self.user)

        entree = chatter_qs(self.dossier, company=self.company).filter(
            field='statut').first()
        self.assertIsNotNone(entree)
        self.assertEqual(entree.new_value, 'Clôturé')

    def test_patch_statut_direct_trace_aussi_le_changement(self):
        """Le champ ``statut`` reste écrivable par PATCH direct (pas
        seulement via l'action ``cloturer``) — la trace doit couvrir ce
        chemin EXISTANT aussi (voir DossierExportViewSet.perform_update)."""
        r = self.api.patch(
            f'{BASE_DOUANE}/dossiers-export/{self.dossier.id}/',
            {'statut': 'cloture'})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

        entree = chatter_qs(self.dossier, company=self.company).filter(
            field='statut').first()
        self.assertIsNotNone(entree)
