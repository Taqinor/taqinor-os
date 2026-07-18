"""NTESG13 — Politique RSE & documents publiés (registre déclaratif encadré).

Critère d'acceptation : les documents se déposent/versionnent simplement,
apparaissent en annexe du rapport avec leur date de dernière revue, tests.
Le FICHIER se dépose via ``records.Attachment`` (générique) : ce module
teste les métadonnées de cycle de vie + l'enregistrement de la cible
chatter/pièce-jointe (``apps/esg/platform.py``).
"""
from datetime import date

from testkit.base import TenantAPITestCase

from apps.esg.models import DocumentPolitiqueESG
from apps.records.models import ALLOWED_TARGETS


class DocumentPolitiqueESGRegistryTests(TenantAPITestCase):
    def test_target_registered_via_platform_manifest(self):
        """La cible chatter/pièce-jointe est déclarée UNIQUEMENT via
        ``apps/esg/platform.py`` — apparaît dans ``ALLOWED_TARGETS`` sans
        toucher ``apps/records/models.py``."""
        self.assertIn(('esg', 'documentpolitiqueesg'), ALLOWED_TARGETS)


class DocumentPolitiqueESGApiTests(TenantAPITestCase):
    BASE = '/api/django/esg/documents-politique-esg/'

    def test_create_forces_company_server_side_defaults_brouillon(self):
        r = self.client_as().post(
            self.BASE,
            {'libelle': 'Charte éthique 2026',
             'type_document': 'charte_ethique'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        doc = DocumentPolitiqueESG.objects.get(id=r.data['id'])
        self.assertEqual(doc.company_id, self.company.id)
        self.assertEqual(doc.statut, DocumentPolitiqueESG.Statut.BROUILLON)

    def test_publish_and_review_dates_update(self):
        doc = DocumentPolitiqueESG.objects.create(
            company=self.company, libelle='Politique environnementale',
            type_document='politique_environnementale')
        r = self.client_as().patch(
            f'{self.BASE}{doc.id}/',
            {'statut': 'publiee', 'date_publication': '2026-01-15',
             'date_revue': '2026-07-01'},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        doc.refresh_from_db()
        self.assertEqual(doc.statut, DocumentPolitiqueESG.Statut.PUBLIEE)
        self.assertEqual(doc.date_publication, date(2026, 1, 15))
        self.assertEqual(doc.date_revue, date(2026, 7, 1))

    def test_list_scoped_to_company(self):
        DocumentPolitiqueESG.objects.create(
            company=self.company, libelle='Code fournisseur',
            type_document='code_fournisseur')
        DocumentPolitiqueESG.objects.create(
            company=self.other_company, libelle='Autre société',
            type_document='code_fournisseur')
        r = self.client_as().get(self.BASE)
        self.assertEqual(r.status_code, 200)
        libelles = [row['libelle'] for row in r.data.get('results', r.data)]
        self.assertIn('Code fournisseur', libelles)
        self.assertNotIn('Autre société', libelles)

    def test_cross_tenant_isolation(self):
        foreign = DocumentPolitiqueESG.objects.create(
            company=self.other_company, libelle='Autre société',
            type_document='code_fournisseur')
        r = self.client_as().get(f'{self.BASE}{foreign.id}/')
        self.assertIn(r.status_code, (403, 404))
