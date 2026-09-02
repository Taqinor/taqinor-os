"""N107 — commande de gestion `import_odoo_leads` : import idempotent des leads
Odoo (CSV + JSON), société forcée côté serveur, rapprochement email/téléphone.

Aucune donnée réelle : les fixtures sont 100 % synthétiques et écrites dans des
fichiers temporaires (jamais committées).

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_import_odoo -v 2
"""
import io
import json
import os
import tempfile

from django.core.management import call_command
from django.test import TestCase

from apps.crm import services as crm_services
from apps.crm import stages
from apps.crm.management.commands.import_odoo_leads import _find_existing
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

# CRX9 — deux lignes limites : valeurs plus longues que leur colonne, et un
# téléphone aberrant (26 chiffres) que `Lead.telephone` (varchar 50) et
# `phone_normalise` (varchar 20) ne peuvent pas porter.
CSV_BORNES = (
    "id,name,email_from,phone,city,partner_name,stage_id,description\n"
    "301,Test Long,long@example.test,0612000301,"
    + 'V' * 200 + "," + 'S' * 300 + ",New,Note L\n"
    "302,Test Aberrant,,00000000000000000000000000,Casablanca,,New,\n"
)

# CRX10 — les cas Meta que seul le chemin JSON-2 savait nettoyer : email
# bouche-trou (qui fusionnait 243 leads sur une fiche), fausse raison sociale,
# et réponses du formulaire rangées dans l'adresse postale.
CSV_META = (
    "id,name,email_from,phone,city,partner_name,street,stage_id,description\n"
    "601,Meta Un,no-email@example.com,0612000601,Casablanca,"
    "Facebook Lead,entre_2000_dh_-_4000dh,New,\n"
    "602,Meta Deux,no-email@example.com,0612000602,Rabat,"
    "Facebook Lead,plus_de_5000_dh,New,\n"
)

# CRX10 — deux lignes Odoo qui désignent le même lead (même email).
CSV_DOUBLONS = (
    "id,name,email_from,phone,city,partner_name,stage_id,description\n"
    "401,Test Doublon A,dup@example.test,0612000401,Casablanca,,New,\n"
    "402,Test Doublon B,dup@example.test,0612000402,Rabat,,New,\n"
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


class TestColonnesDeriveesEtLongueurs(ImportOdooBase):
    """CRX9 — le chemin RÉCONCILIATION borne ses valeurs et persiste les
    colonnes dérivées ; un téléphone aberrant n'atteint jamais la colonne."""

    def test_reconciliation_persists_derived_dedup_columns(self):
        existing = Lead.objects.create(
            company=self.company, nom='Fiche Nue', stage=stages.NEW,
            external_system='odoo', external_id='101')
        self.assertEqual(existing.phone_normalise, '')

        path = self._file('.csv', CSV_EXPORT)
        call_command('import_odoo_leads', path, '--company', self.company.slug)

        existing.refresh_from_db()
        self.assertEqual(existing.telephone, '0612000001')
        self.assertEqual(existing.email, 'alpha@example.test')
        # Colonnes INDEXÉES de dédup (QW10) réellement écrites en base : sans
        # elles dans `update_fields`, elles restaient vides et la dédup était
        # aveugle sur ce lead.
        self.assertEqual(existing.phone_normalise,
                         crm_services.normalize_phone('0612000001'))
        self.assertEqual(existing.email_normalise,
                         crm_services.normalize_email('alpha@example.test'))
        self.assertTrue(Lead.objects.filter(
            company=self.company,
            phone_normalise=existing.phone_normalise).exists())

    def test_reconciliation_clamps_values_to_column_length(self):
        existing = Lead.objects.create(
            company=self.company, nom='À Compléter', stage=stages.NEW,
            external_system='odoo', external_id='301')

        path = self._file('.csv', CSV_BORNES)
        call_command('import_odoo_leads', path, '--company', self.company.slug)

        existing.refresh_from_db()
        # Avant : l'UPDATE dépassait varchar(120)/varchar(255) et faisait
        # échouer TOUT l'import (transaction unique).
        self.assertEqual(len(existing.ville), 120)
        self.assertEqual(len(existing.societe), 255)

    def test_aberrant_phone_never_reaches_the_column_and_lands_in_the_note(self):
        path = self._file('.csv', CSV_BORNES)
        call_command('import_odoo_leads', path, '--company', self.company.slug)

        aberrant = Lead.objects.get(company=self.company, external_id='302')
        self.assertIsNone(aberrant.telephone)      # varchar(50)/varchar(20)
        self.assertEqual(aberrant.phone_normalise, '')
        self.assertIn('Téléphone Odoo invalide: 000', aberrant.note)


class TestSoftDeleteReconciliation(ImportOdooBase):
    """CRX7 — un lead mis à la corbeille ne bricke plus l'import.

    Avant : ``_find_existing`` interrogeait ``Lead.objects`` (vivants), donc un
    lead soft-supprimé restait INVISIBLE alors que sa clé externe occupait
    toujours la contrainte ``uniq_lead_external_ref`` — l'import tentait une
    création, l'``IntegrityError`` remontait dans le ``transaction.atomic()``
    global et TOUT l'import échouait. Désormais : rapprochement sur
    ``all_objects``, ligne ignorée et comptée, zéro restauration silencieuse.
    """

    def test_reimport_after_soft_delete_skips_and_never_resurrects(self):
        path = self._file('.csv', CSV_EXPORT)
        call_command('import_odoo_leads', path, '--company', self.company.slug)
        alpha = Lead.objects.get(company=self.company, external_id='101')
        alpha.soft_delete()

        out = io.StringIO()
        call_command('import_odoo_leads', path,
                     '--company', self.company.slug, stdout=out)

        # Aucun doublon : la ligne 101 a été rapprochée sur le lead en
        # corbeille et ignorée (avant, la création tuait toute la transaction).
        self.assertEqual(
            Lead.all_objects.filter(company=self.company).count(), 3)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 2)
        alpha.refresh_from_db()
        self.assertTrue(alpha.is_deleted)          # jamais restauré
        sortie = out.getvalue()
        self.assertIn('1 en corbeille', sortie)
        self.assertIn('Corbeille — ignoré (jamais restauré)', sortie)

    def test_find_existing_sees_soft_deleted_lead(self):
        lead = Lead.objects.create(
            company=self.company, nom='Dans la corbeille',
            email='alpha@example.test', stage=stages.NEW)
        lead.soft_delete()
        trouve, ambigu = _find_existing(
            self.company, None, {'email': 'alpha@example.test'})
        self.assertIsNotNone(trouve)
        self.assertEqual(trouve.pk, lead.pk)
        self.assertTrue(trouve.is_deleted)
        self.assertFalse(ambigu)

    def test_live_lead_wins_over_soft_deleted_twin(self):
        mort = Lead.objects.create(
            company=self.company, nom='Ancien',
            email='alpha@example.test', stage=stages.NEW)
        mort.soft_delete()
        vivant = Lead.objects.create(
            company=self.company, nom='Actuel',
            email='alpha@example.test', stage=stages.NEW)
        trouve, _ambigu = _find_existing(
            self.company, None, {'email': 'alpha@example.test'})
        self.assertEqual(trouve.pk, vivant.pk)

        # Même préférence sur le rapprochement par téléphone.
        mort_tel = Lead.objects.create(
            company=self.company, nom='Ancien Tel',
            telephone='0612000009', stage=stages.NEW)
        mort_tel.soft_delete()
        vivant_tel = Lead.objects.create(
            company=self.company, nom='Actuel Tel',
            telephone='+212612000009', stage=stages.NEW)
        trouve_tel, _ambigu_tel = _find_existing(
            self.company, None, {'telephone': '0612000009'})
        self.assertEqual(trouve_tel.pk, vivant_tel.pk)


class TestCheminFichierRejointJson2(ImportOdooBase):
    """CRX10 — l'export FICHIER applique enfin les règles du chemin JSON-2."""

    def test_file_path_applies_the_same_meta_cleanup(self):
        path = self._file('.csv', CSV_META)
        call_command('import_odoo_leads', path, '--company', self.company.slug)

        # DEUX fiches : avant, l'email bouche-trou les fusionnait en une seule
        # (243 leads réels partageaient no-email@example.com).
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 2)
        un = Lead.objects.get(company=self.company, external_id='601')
        self.assertIsNone(un.email)            # bouche-trou purgé
        self.assertIsNone(un.societe)          # « Facebook Lead » ≠ société
        self.assertIsNone(un.adresse)          # réponses de formulaire
        self.assertIn('Formulaire Meta: entre_2000_dh_-_4000dh', un.note)

    def test_phone_match_uses_the_indexed_column(self):
        # QW10 — la colonne INDEXÉE `phone_normalise` est le matcher (fin du
        # scan Python de TOUS les leads pour CHAQUE ligne d'export). Preuve :
        # une colonne dérivée désynchronisée à la main (UPDATE brut, hors
        # `save()`) n'est plus rapprochée, là où le scan Python l'aurait vue.
        lead = Lead.objects.create(
            company=self.company, nom='Colonne Désynchronisée',
            telephone='0612000701', stage=stages.NEW)
        self.assertNotEqual(lead.phone_normalise, '')
        Lead.objects.filter(pk=lead.pk).update(phone_normalise='')

        trouve, _ambigu = _find_existing(
            self.company, None, {'telephone': '0612000701'})
        self.assertIsNone(trouve)

    def test_ambiguous_match_reports_and_never_stamps_the_external_key(self):
        jumeau_a = Lead.objects.create(
            company=self.company, nom='Jumeau A',
            telephone='0612000501', stage=stages.NEW)
        jumeau_b = Lead.objects.create(
            company=self.company, nom='Jumeau B',
            telephone='+212612000501', stage=stages.NEW)
        path = self._file('.csv', (
            "id,name,email_from,phone,city,partner_name,stage_id,description\n"
            "501,Test Ambigu,,0612000501,Casablanca,,New,\n"))

        out = io.StringIO()
        call_command('import_odoo_leads', path,
                     '--company', self.company.slug, stdout=out)

        jumeau_a.refresh_from_db()
        jumeau_b.refresh_from_db()
        # Lier la ligne Odoo à l'une des deux serait un choix arbitraire ET
        # durable (clé technique de rapprochement) : on signale, on ne lie pas.
        self.assertIsNone(jumeau_a.external_id)
        self.assertIsNone(jumeau_b.external_id)
        sortie = out.getvalue()
        self.assertIn('Rapprochement ambigu', sortie)
        self.assertIn('1 ambigu(s)', sortie)
        # Et aucun doublon n'est créé pour autant.
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 2)

    def test_dry_run_does_not_double_count_duplicate_rows(self):
        path = self._file('.csv', CSV_DOUBLONS)

        blanc = io.StringIO()
        call_command('import_odoo_leads', path, '--company',
                     self.company.slug, '--dry-run', stdout=blanc)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 0)
        # Avant : « 2 créé(s) » annoncés pour un seul lead réellement créé.
        self.assertIn('1 créé(s)', blanc.getvalue())

        reel = io.StringIO()
        call_command('import_odoo_leads', path,
                     '--company', self.company.slug, stdout=reel)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)
        self.assertIn('1 créé(s)', reel.getvalue())


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
