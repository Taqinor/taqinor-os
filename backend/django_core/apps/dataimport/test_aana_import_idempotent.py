"""AANA11 (C-AANA-030) — l'import de devis et de factures est idempotent.

Rouge figé par l'audit (05/10) : le même CSV devis d'une ligne importé deux
fois créait DEUX devis (``devis_count=2``) et consommait deux numéros — la
promesse « doublon » de ``ventes/domain/imports.py`` n'était tenue par
personne. Correctif : une ligne dont la référence externe est déjà rattachée
à un document vivant de la société est ignorée (``raison='doublon'``) AVANT
toute création."""
from apps.crm.models import Client
from apps.facturation.models import Facture
from apps.ventes.models import Devis

from .tests import ImportBase


class TestImportDocumentsIdempotent(ImportBase):
    def setUp(self):
        super().setUp()
        Client.objects.create(
            company=self.company, nom='Client Migre', email='cm@x.ma')

    def _importer(self, target, contenu):
        resp = self.api.post('/api/django/imports/commit/', {
            'file': self._csv(contenu), 'target': target,
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    def test_devis_importe_deux_fois(self):
        contenu = 'reference,client_nom,external_id\nSRC-1,Client Migre,EXT-D1\n'
        premier = self._importer('devis', contenu)
        self.assertEqual(premier['created'], 1, premier)
        avant = Devis.objects.filter(company=self.company).count()
        reference = Devis.objects.get(company=self.company).reference

        second = self._importer('devis', contenu)
        self.assertEqual(second['created'], 0, second)
        self.assertEqual(second['skipped'], [{'ligne': 1, 'raison': 'doublon'}])
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), avant)
        self.assertEqual(
            Devis.objects.get(company=self.company).reference, reference)

    def test_facture_importee_deux_fois(self):
        contenu = 'reference,client_nom,external_id\nF-SRC-1,Client Migre,EXT-F1\n'
        premier = self._importer('factures', contenu)
        self.assertEqual(premier['created'], 1, premier)

        second = self._importer('factures', contenu)
        self.assertEqual(second['created'], 0, second)
        self.assertEqual(second['skipped'], [{'ligne': 1, 'raison': 'doublon'}])
        self.assertEqual(
            Facture.objects.filter(company=self.company).count(), 1)

    def test_meme_ref_devis_et_facture_ne_se_bloquent_pas(self):
        # La référence est typée (AANA10) : un devis EXT-1 n'empêche pas une
        # facture EXT-1.
        self._importer(
            'devis', 'reference,client_nom,external_id\nS,Client Migre,EXT-1\n')
        facture = self._importer(
            'factures',
            'reference,client_nom,external_id\nS,Client Migre,EXT-1\n')
        self.assertEqual(facture['created'], 1, facture)
