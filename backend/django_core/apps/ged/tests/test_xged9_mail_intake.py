"""XGED9 — Ingestion par email → GED (alias par cabinet/dossier).

Couvre :
  * alias extrait d'une adresse plus-adressée OU d'un objet `[alias]` ;
  * un email avec PJ vers un alias configuré crée le document dans le bon
    dossier ;
  * un re-traitement (même Message-ID) ne duplique pas (idempotence) ;
  * sans alias résolu, le message est ignoré (rien n'est déposé au hasard) ;
  * sans le flag `GED_MAIL_INTAKE_ENABLED`, `poll_mail_intake` est un no-op.
"""
from email.message import EmailMessage

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _build_email(*, to_addr='', subject='', message_id='<abc@x.com>',
                 attachment_name='piece.pdf'):
    msg = EmailMessage()
    msg['From'] = 'client@example.com'
    msg['To'] = to_addr or 'ged@taqinor.ma'
    msg['Subject'] = subject
    msg['Message-ID'] = message_id
    msg.set_content('Voir pièce jointe.')
    msg.add_attachment(
        b'%PDF-1.4\n%test\n%%EOF', maintype='application', subtype='pdf',
        filename=attachment_name)
    return msg.as_bytes()


class AliasExtractionTests(TestCase):
    def test_extrait_alias_plus_adresse(self):
        self.assertEqual(
            services.extraire_alias_email(to_addr='ged+compta@taqinor.ma'),
            'compta')

    def test_extrait_alias_objet(self):
        self.assertEqual(
            services.extraire_alias_email(subject='[rh] Bulletin de paie'),
            'rh')

    def test_sans_alias_renvoie_vide(self):
        self.assertEqual(
            services.extraire_alias_email(
                to_addr='contact@taqinor.ma', subject='Bonjour'),
            '')


class ImporterMessageTests(TestCase):
    def setUp(self):
        self.co = make_company('xged9-a', 'Xged9 A')
        self.cab = Cabinet.objects.create(company=self.co, nom='Compta')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='Factures fournisseurs',
            alias_email='compta')

    def test_importe_piece_jointe_vers_bon_dossier(self):
        raw = _build_email(to_addr='ged+compta@taqinor.ma')
        created = services.importer_message_email(raw, company=self.co)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].folder_id, self.folder.pk)

    def test_reimport_meme_message_id_ne_duplique_pas(self):
        raw = _build_email(
            to_addr='ged+compta@taqinor.ma', message_id='<dup-1@x.com>')
        services.importer_message_email(raw, company=self.co)
        second = services.importer_message_email(raw, company=self.co)
        self.assertEqual(second, [])
        self.assertEqual(
            Document.objects.filter(company=self.co).count(), 1)

    def test_sans_alias_resolu_ignore_le_message(self):
        raw = _build_email(to_addr='inconnu@taqinor.ma')
        created = services.importer_message_email(raw, company=self.co)
        self.assertEqual(created, [])
        self.assertEqual(Document.objects.filter(company=self.co).count(), 0)

    def test_objet_alias_route_correctement(self):
        raw = _build_email(
            to_addr='ged@taqinor.ma', subject='[compta] Facture 123',
            message_id='<subj-1@x.com>')
        created = services.importer_message_email(raw, company=self.co)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].folder_id, self.folder.pk)


class GatingTests(TestCase):
    def setUp(self):
        self.co = make_company('xged9-b', 'Xged9 B')

    @override_settings(GED_MAIL_INTAKE_ENABLED=False)
    def test_poll_disabled_is_noop(self):
        result = services.poll_mail_intake(self.co)
        self.assertEqual(result, {'fetched': 0, 'imported': 0})

    @override_settings(GED_MAIL_INTAKE_ENABLED=True)
    def test_poll_enabled_without_config_is_noop(self):
        result = services.poll_mail_intake(self.co)
        self.assertEqual(result, {'fetched': 0, 'imported': 0})
