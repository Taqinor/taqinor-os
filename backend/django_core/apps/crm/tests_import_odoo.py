"""N107 — commande de gestion `import_odoo_leads` : import idempotent des leads
Odoo (CSV + JSON), société forcée côté serveur, rapprochement email/téléphone.

Aucune donnée réelle : les fixtures sont 100 % synthétiques et écrites dans des
fichiers temporaires (jamais committées).

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_import_odoo -v 2
"""
import json
import os
import tempfile

from django.core.management import call_command
from django.test import TestCase

from apps.crm import stages
from apps.crm.models import Lead
from authentication.models import Company


def _write(suffix, content):
    """Écrit un fichier temporaire et renvoie son chemin (nettoyé en tearDown)."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        fh.write(content)
    return path


# Trois faux leads Odoo synthétiques (CSV : en-têtes techniques Odoo).
CSV_EXPORT = (
    "id,name,email_from,phone,city,partner_name,stage_id,description\n"
    "101,Test Alpha,alpha@example.test,0612000001,Casablanca,Alpha SARL,New,Note A\n"
    "102,Test Beta,beta@example.test,+212 6 12-00-00-02,Rabat,,Won,Note B\n"
    "103,Test Gamma,,0612000003,Agadir,Gamma Co,Proposition,\n"
)

JSON_EXPORT = json.dumps([
    {"id": 201, "name": "Json Un", "email_from": "un@example.test",
     "phone": "0613000001", "city": "Fès", "stage_id": "Contacted"},
    {"id": 202, "name": "Json Deux", "email_from": "deux@example.test",
     "phone": "0613000002", "city": "Meknès", "stage_id": "Inconnu"},
])


class ImportOdooBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='odoo-imp-co', defaults={'nom': 'Odoo Imp Co'})[0]
        self._tmp = []

    def tearDown(self):
        for path in self._tmp:
            try:
                os.remove(path)
            except OSError:
                pass

    def _file(self, suffix, content):
        path = _write(suffix, content)
        self._tmp.append(path)
        return path


class TestCsvImport(ImportOdooBase):
    def test_creates_leads_with_company_forced_and_fields_mapped(self):
        path = self._file('.csv', CSV_EXPORT)
        call_command('import_odoo_leads', path, '--company', self.company.slug)

        leads = Lead.objects.filter(company=self.company)
        self.assertEqual(leads.count(), 3)

        # Société forcée côté serveur.
        for lead in leads:
            self.assertEqual(lead.company_id, self.company.id)
            self.assertEqual(lead.source, Lead.Source.ODOO_IMPORT_TEST)
            self.assertEqual(lead.external_system, 'odoo')

        alpha = leads.get(email='alpha@example.test')
        self.assertEqual(alpha.nom, 'Test Alpha')
        self.assertEqual(alpha.ville, 'Casablanca')
        self.assertEqual(alpha.societe, 'Alpha SARL')
        self.assertEqual(alpha.note, 'Note A')
        self.assertEqual(alpha.external_id, '101')
        self.assertEqual(alpha.stage, stages.NEW)

        # « Won » → SIGNED (clé canonique chargée depuis STAGES.py).
        beta = leads.get(email='beta@example.test')
        self.assertEqual(beta.stage, 'SIGNED')
        self.assertIn('SIGNED', stages.STAGES)

        # « Proposition » → QUOTE_SENT ; ligne sans email rapprochée par tel.
        gamma = leads.get(external_id='103')
        self.assertEqual(gamma.stage, 'QUOTE_SENT')
        self.assertEqual(gamma.telephone, '0612000003')

    def test_rerun_same_file_is_idempotent(self):
        path = self._file('.csv', CSV_EXPORT)
        call_command('import_odoo_leads', path, '--company', self.company.slug)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 3)

        # Deuxième passe : aucun doublon, rien recréé.
        call_command('import_odoo_leads', path, '--company', self.company.slug)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 3)


class TestJsonImport(ImportOdooBase):
    def test_json_export_imports_and_unknown_stage_falls_back_to_new(self):
        path = self._file('.json', JSON_EXPORT)
        call_command('import_odoo_leads', path, '--company', str(self.company.id))

        leads = Lead.objects.filter(company=self.company)
        self.assertEqual(leads.count(), 2)
        self.assertEqual(leads.get(external_id='201').stage, 'CONTACTED')
        # Étape Odoo inconnue → repli sur NEW (jamais d'invention d'étape).
        self.assertEqual(leads.get(external_id='202').stage, stages.NEW)

    def test_json_rerun_idempotent(self):
        path = self._file('.json', JSON_EXPORT)
        call_command('import_odoo_leads', path, '--company', self.company.slug)
        call_command('import_odoo_leads', path, '--company', self.company.slug)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 2)


class TestReconciliation(ImportOdooBase):
    def test_matches_existing_lead_by_email_instead_of_creating(self):
        existing = Lead.objects.create(
            company=self.company, nom='Déjà Là',
            email='alpha@example.test', stage=stages.NEW)
        path = self._file('.csv', CSV_EXPORT)
        call_command('import_odoo_leads', path, '--company', self.company.slug)

        # Toujours 3 leads (la ligne alpha a mis à jour la fiche existante).
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 3)
        existing.refresh_from_db()
        # Champ vide complété (ville), mais le nom déjà saisi n'est PAS écrasé.
        self.assertEqual(existing.ville, 'Casablanca')
        self.assertEqual(existing.nom, 'Déjà Là')

    def test_matches_existing_lead_by_phone(self):
        existing = Lead.objects.create(
            company=self.company, nom='Par Téléphone',
            telephone='+212612000003', stage=stages.NEW)
        path = self._file('.csv', CSV_EXPORT)
        call_command('import_odoo_leads', path, '--company', self.company.slug)

        # La ligne gamma (0612000003) rapproche la fiche existante : 3 au total.
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 3)
        existing.refresh_from_db()
        self.assertEqual(existing.ville, 'Agadir')


class TestNoOpAndGuards(ImportOdooBase):
    def test_no_path_does_nothing(self):
        call_command('import_odoo_leads', '--company', self.company.slug)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)

    def test_missing_file_does_nothing(self):
        call_command('import_odoo_leads', '/no/such/file.csv',
                     '--company', self.company.slug)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)

    def test_company_required(self):
        from django.core.management.base import CommandError
        path = self._file('.csv', CSV_EXPORT)
        with self.assertRaises(CommandError):
            call_command('import_odoo_leads', path)
        self.assertEqual(Lead.objects.count(), 0)

    def test_dry_run_writes_nothing(self):
        path = self._file('.csv', CSV_EXPORT)
        call_command('import_odoo_leads', path,
                     '--company', self.company.slug, '--dry-run')
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)
