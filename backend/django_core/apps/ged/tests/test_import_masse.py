"""GED32 — Import en masse (CSV de métadonnées + ZIP de fichiers).

Couvre (au niveau SERVICE, sans MinIO — lignes SANS colonne `fichier`, donc
aucun binaire stocké ; + tests des helpers de parsing CSV/ZIP) :
  * parsing CSV → liste de dicts (en-têtes, strip, CSV vide) ;
  * parsing ZIP → {nom: octets} (ignore les dossiers, zip invalide → {}) ;
  * import : N lignes → N documents (nom requis, custom_data, société serveur) ;
  * ligne sans nom → erreur collectée, lot non interrompu ;
  * `fichier` référençant une entrée absente du ZIP → erreur de ligne ;
  * isolation société (dossier d'une autre société refusé).
"""
import io
import zipfile

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, DocumentVersion, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class CsvZipParsingTests(TestCase):
    def test_parser_csv_basic(self):
        csv_text = 'nom,description\nFacture A,Janvier\nFacture B,Février\n'
        lignes = services.parser_csv_metadonnees(csv_text)
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0]['nom'], 'Facture A')
        self.assertEqual(lignes[1]['description'], 'Février')

    def test_parser_csv_vide(self):
        self.assertEqual(services.parser_csv_metadonnees(''), [])
        self.assertEqual(services.parser_csv_metadonnees('   '), [])

    def test_zip_entries_ignore_dossiers(self):
        z = _zip({'a.txt': b'hello', 'sub/b.txt': b'world'})
        entries = services._zip_entries(z)
        self.assertEqual(entries['a.txt'], b'hello')
        self.assertEqual(entries['sub/b.txt'], b'world')

    def test_zip_invalide_renvoie_vide(self):
        self.assertEqual(services._zip_entries(b'not a zip'), {})
        self.assertEqual(services._zip_entries(None), {})


class ImportMasseServiceTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ged32-a', 'Ged32 A')
        self.co_b = make_company('ged32-b', 'Ged32 B')
        self.admin_a = make_user(self.co_a, 'ged32-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Import')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Lot')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Import')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Lot B')

    def test_import_cree_documents_metadonnees_seules(self):
        lignes = [
            {'nom': 'Doc 1', 'description': 'desc 1'},
            {'nom': 'Doc 2', 'description': ''},
        ]
        res = services.importer_en_masse(
            company=self.co_a, folder=self.folder_a, lignes=lignes,
            created_by=self.admin_a)
        self.assertEqual(res['crees'], 2)
        self.assertEqual(res['erreurs'], [])
        for doc in res['documents']:
            self.assertEqual(doc.company_id, self.co_a.id)
            self.assertEqual(doc.created_by_id, self.admin_a.id)
            self.assertEqual(
                DocumentVersion.objects.filter(document=doc).count(), 1)

    def test_ligne_sans_nom_erreur_sans_bloquer(self):
        lignes = [{'nom': ''}, {'nom': 'Valide'}]
        res = services.importer_en_masse(
            company=self.co_a, folder=self.folder_a, lignes=lignes,
            created_by=self.admin_a)
        self.assertEqual(res['crees'], 1)
        self.assertEqual(len(res['erreurs']), 1)
        self.assertEqual(res['erreurs'][0]['ligne'], 1)

    def test_fichier_absent_du_zip_erreur(self):
        lignes = [{'nom': 'Avec binaire', 'fichier': 'manquant.pdf'}]
        res = services.importer_en_masse(
            company=self.co_a, folder=self.folder_a, lignes=lignes,
            zip_bytes=_zip({'autre.pdf': b'x'}), created_by=self.admin_a)
        self.assertEqual(res['crees'], 0)
        self.assertEqual(len(res['erreurs']), 1)
        self.assertIn('manquant.pdf', res['erreurs'][0]['detail'])

    def test_custom_data_collecte(self):
        # Sans validateur fourni, les colonnes hors réservées vont en custom_data.
        lignes = [{'nom': 'Doc', 'type_document': 'facture', 'ref': 'F-001'}]
        res = services.importer_en_masse(
            company=self.co_a, folder=self.folder_a, lignes=lignes,
            created_by=self.admin_a)
        doc = res['documents'][0]
        doc.refresh_from_db()
        self.assertEqual(doc.custom_data.get('type_document'), 'facture')
        self.assertEqual(doc.custom_data.get('ref'), 'F-001')

    def test_dossier_autre_societe_refuse(self):
        with self.assertRaises(ValueError):
            services.importer_en_masse(
                company=self.co_a, folder=self.folder_b,
                lignes=[{'nom': 'X'}], created_by=self.admin_a)

    def test_lot_vide_ne_cree_rien(self):
        res = services.importer_en_masse(
            company=self.co_a, folder=self.folder_a, lignes=[],
            created_by=self.admin_a)
        self.assertEqual(res['crees'], 0)
        self.assertEqual(Document.objects.filter(company=self.co_a).count(), 0)
