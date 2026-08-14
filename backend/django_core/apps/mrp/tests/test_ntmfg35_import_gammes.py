"""NTMFG35 — Import CSV/XLSX de gammes opératoires en masse.

Critère : un fichier de 50 lignes avec 3 erreurs volontaires importe les 47
lignes valides et rapporte les 3 rejets avec motif précis, idempotent
(ré-import du même fichier ne duplique pas)."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.dataimport.models import ImportJob, ImportJobRow
from apps.mrp.models import Gamme, OperationGamme, PosteDeCharge
from apps.mrp.services import importer_gammes_csv
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


def ligne(produit_id, ordre, poste_code, libelle='Op', prepa='5', unitaire='2'):
    return {
        'produit': str(produit_id), 'ordre': str(ordre),
        'poste_charge': poste_code, 'libelle': libelle,
        'temps_prepa_min': prepa, 'temps_unitaire_min': unitaire,
    }


class ImporterGammesCsvServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg35-1', 'MRP NTMFG35 1')
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-35', nom='Poste 35')

    def test_import_47_valides_3_rejets_sur_50_lignes(self):
        rows = []
        for i in range(1, 48):  # 47 lignes valides.
            rows.append(ligne(self.produit.id, i, self.poste.code, f'Op {i}'))
        # 3 lignes volontairement invalides.
        rows.append(ligne(999999, 48, self.poste.code))  # produit inconnu.
        rows.append(ligne(self.produit.id, 49, 'POSTE-INCONNU'))  # poste inconnu.
        rows.append(ligne(self.produit.id, 50, self.poste.code, libelle=''))  # libellé vide.

        resultat = importer_gammes_csv(self.company, rows)

        self.assertEqual(resultat['total_lignes'], 50)
        self.assertEqual(resultat['created_count'], 47)
        self.assertEqual(resultat['error_count'], 3)
        motifs = [e['motif'] for e in resultat['erreurs']]
        self.assertTrue(any('Produit inconnu' in m for m in motifs))
        self.assertTrue(any('Poste de charge inconnu' in m for m in motifs))
        self.assertTrue(any('Libellé' in m for m in motifs))
        self.assertEqual(
            OperationGamme.objects.filter(gamme__produit=self.produit).count(), 47)

    def test_creation_gamme_si_absente(self):
        self.assertFalse(Gamme.objects.filter(produit=self.produit).exists())
        importer_gammes_csv(
            self.company, [ligne(self.produit.id, 1, self.poste.code)])
        gamme = Gamme.objects.get(produit=self.produit)
        self.assertEqual(gamme.operations.count(), 1)

    def test_reimport_meme_fichier_idempotent_pas_de_duplication(self):
        rows = [ligne(self.produit.id, 1, self.poste.code, libelle='V1')]
        importer_gammes_csv(self.company, rows)
        importer_gammes_csv(self.company, rows)
        gamme = Gamme.objects.get(produit=self.produit)
        self.assertEqual(gamme.operations.count(), 1)  # jamais dupliqué.

    def test_reimport_met_a_jour_le_libelle(self):
        importer_gammes_csv(
            self.company, [ligne(self.produit.id, 1, self.poste.code, libelle='V1')])
        importer_gammes_csv(
            self.company, [ligne(self.produit.id, 1, self.poste.code, libelle='V2')])
        operation = OperationGamme.objects.get(gamme__produit=self.produit, ordre=1)
        self.assertEqual(operation.libelle, 'V2')

    def test_bookkeeping_import_job(self):
        rows = [
            ligne(self.produit.id, 1, self.poste.code),
            ligne(999999, 2, self.poste.code),
        ]
        resultat = importer_gammes_csv(self.company, rows, filename='gammes.csv')
        job = ImportJob.objects.get(pk=resultat['job_id'])
        self.assertEqual(job.company_id, self.company.id)
        self.assertEqual(job.target, 'mrp_gammes')
        self.assertEqual(job.error_count, 1)
        self.assertEqual(
            ImportJobRow.objects.filter(job=job).count(), 1)

    def test_isolation_tenant_poste_dune_autre_societe_refuse(self):
        autre_company = make_company('mrp-ntmfg35-2', 'MRP NTMFG35 2')
        autre_poste = PosteDeCharge.objects.create(
            company=autre_company, code='P-35', nom='Poste autre société')
        resultat = importer_gammes_csv(
            self.company, [ligne(self.produit.id, 1, autre_poste.code)])
        self.assertEqual(resultat['error_count'], 1)
        self.assertIn('Poste de charge inconnu', resultat['erreurs'][0]['motif'])


class ImporterGammesApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg35-api-1', 'MRP NTMFG35 API 1')
        self.responsable = make_user(
            self.company, 'mrp-ntmfg35-resp', role='responsable')
        self.technicien = make_user(
            self.company, 'mrp-ntmfg35-tech', role='normal')
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-35API', nom='Poste API')

    def _csv_bytes(self):
        contenu = (
            'produit,ordre,poste_charge,libelle,temps_prepa_min,temps_unitaire_min\n'
            f'{self.produit.id},1,{self.poste.code},Découpe,10,2\n'
            '999999,2,POSTE-X,Ligne invalide,5,1\n'
        )
        return contenu.encode('utf-8')

    def test_import_endpoint(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        upload = SimpleUploadedFile(
            'gammes.csv', self._csv_bytes(), content_type='text/csv')
        resp = auth(self.responsable).post(
            '/api/django/mrp/gammes/import/', {'file': upload}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created_count'], 1)
        self.assertEqual(resp.data['error_count'], 1)

    def test_technicien_403_sur_import(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        upload = SimpleUploadedFile(
            'gammes.csv', self._csv_bytes(), content_type='text/csv')
        resp = auth(self.technicien).post(
            '/api/django/mrp/gammes/import/', {'file': upload}, format='multipart')
        self.assertEqual(resp.status_code, 403)

    def test_erreurs_download_scope_societe(self):
        rows = [ligne(999999, 1, self.poste.code)]
        resultat = importer_gammes_csv(self.company, rows)
        job_id = resultat['job_id']

        resp = auth(self.responsable).get(
            f'/api/django/mrp/gammes/import/{job_id}/erreurs/')
        self.assertEqual(resp.status_code, 200)

        autre_company = make_company('mrp-ntmfg35-api-2', 'MRP NTMFG35 API 2')
        autre_resp_user = make_user(
            autre_company, 'mrp-ntmfg35-autre-resp', role='responsable')
        resp = auth(autre_resp_user).get(
            f'/api/django/mrp/gammes/import/{job_id}/erreurs/')
        self.assertEqual(resp.status_code, 404)
