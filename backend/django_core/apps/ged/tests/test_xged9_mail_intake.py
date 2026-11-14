"""XGED9 — Ingestion par email → GED (alias par cabinet/dossier).

Couvre :
  * alias extrait d'une adresse plus-adressée OU d'un objet `[alias]` ;
  * un email avec PJ vers un alias configuré crée le document dans le bon
    dossier ;
  * un re-traitement (même Message-ID) ne duplique pas (idempotence) ;
  * sans alias résolu, le message est ignoré (rien n'est déposé au hasard) ;
  * sans le flag `GED_MAIL_INTAKE_ENABLED`, `handler_mail_intake` est un no-op
    (ACEL94 : relevé par la seule `core.email_intake.poll_mailbox`).
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

    def test_alias_avec_point_route_vers_le_dossier(self):
        """ADOC187 — un alias accepté par le dialogue (point compris) est routé
        par l'ingestion, en adresse « + » comme en objet `[alias]` ; l'alias
        sans point garde son dossier."""
        dossier_point = Folder.objects.create(
            company=self.co, cabinet=self.cab, nom='Compta 2026',
            alias_email='compta.2026')
        for raw in (
                _build_email(to_addr='ged+compta.2026@taqinor.ma',
                             message_id='<pt-1@x.com>'),
                _build_email(to_addr='ged@taqinor.ma',
                             subject='[compta.2026] Facture',
                             message_id='<pt-2@x.com>')):
            created = services.importer_message_email(raw, company=self.co)
            self.assertEqual(len(created), 1)
            relu = Document.objects.get(pk=created[0].pk)
            self.assertEqual(relu.folder_id, dossier_point.pk)
        created = services.importer_message_email(
            _build_email(to_addr='ged+compta@taqinor.ma',
                         message_id='<pt-3@x.com>'), company=self.co)
        self.assertEqual(created[0].folder_id, self.folder.pk)


class _FauxImapMarquage:
    """Connexion IMAP de marquage : enregistre les `\\Seen` posés par UID."""

    def __init__(self):
        self.stores = []

    def uid(self, commande, uid, *args):
        self.stores.append((commande, uid, args))

    def logout(self):
        pass


class GatingTests(TestCase):
    """ACEL94 — la GED n'a plus de relève IMAP : son handler est abonné au
    bus `core.email_intake` (`GedConfig.ready`) et `poll_mailbox` le sert."""

    def setUp(self):
        from core import email_intake
        self.co = make_company('xged9-b', 'Xged9 B')
        self.assertIn(services.handler_mail_intake, email_intake._HANDLERS)
        avant = list(email_intake._HANDLERS)
        self.addCleanup(email_intake._HANDLERS.extend, avant)
        self.addCleanup(email_intake._HANDLERS.clear)
        email_intake._HANDLERS[:] = [services.handler_mail_intake]

    def _messages(self, *bruts):
        from core.email_intake import _parse_email_message
        messages = [_parse_email_message(brut) for brut in bruts]
        for uid, msg in enumerate(messages, 1):
            msg.imap_uid = str(uid).encode()
        return messages

    def _poll(self, messages):
        from unittest import mock

        from core.email_intake import poll_mailbox
        conn = _FauxImapMarquage()
        with mock.patch('core.email_intake._active_imap_config', return_value=object()), \
                mock.patch('core.email_intake.fetch_messages', return_value=messages), \
                mock.patch('core.email_intake._imap', return_value=conn):
            return poll_mailbox(self.co), conn

    @override_settings(GED_MAIL_INTAKE_ENABLED=False)
    def test_poll_disabled_is_noop(self):
        Folder.objects.create(
            company=self.co, cabinet=Cabinet.objects.create(company=self.co, nom='C'),
            nom='Compta', alias_email='compta')
        self._poll(self._messages(_build_email(to_addr='ged+compta@taqinor.ma')))
        self.assertEqual(Document.objects.filter(company=self.co).count(), 0)

    @override_settings(GED_MAIL_INTAKE_ENABLED=True)
    def test_poll_enabled_without_config_is_noop(self):
        from core.email_intake import poll_mailbox
        self.assertEqual(poll_mailbox(self.co), {'fetched': 0, 'handled': 0})
        self.assertEqual(Document.objects.filter(company=self.co).count(), 0)

    @override_settings(GED_MAIL_INTAKE_ENABLED=True)
    def test_message_en_echec_reste_non_lu(self):
        """ACEL84 — `\\Seen` posé seulement après un import réussi (ACEL17 :
        par `poll_mailbox`, sur les seuls messages qu'aucun handler n'a fait lever)."""
        from unittest import mock

        def importer(raw, company):
            if b'<un@x.com>' in raw:
                raise ValueError('boom')
            return [object()]

        messages = self._messages(_build_email(message_id='<un@x.com>'),
                                  _build_email(message_id='<deux@x.com>'))
        with mock.patch.object(services, 'importer_message_email', side_effect=importer):
            result, conn = self._poll(messages)
        self.assertEqual(result, {'fetched': 2, 'handled': 1})
        self.assertEqual(conn.stores, [('STORE', b'2', ('+FLAGS', '(\\Seen)'))])

    @override_settings(GED_MAIL_INTAKE_ENABLED=True)
    def test_une_seule_releve_pour_la_ged_et_le_sav(self):
        """ACEL94 (C-ACEL-VER2-204) — un message à l'alias GED et un message
        client de la même boîte, relevés UNE fois par `poll_mailbox` : 1
        document GED, le handler SAV servi pour les deux, chacun marqué lu une
        fois ; rejouer ne duplique pas (Message-ID). Mutant : retirer
        `register_handler` de `GedConfig.ready` ⇒ échec."""
        from unittest import mock

        from core import email_intake
        Folder.objects.create(
            company=self.co, cabinet=Cabinet.objects.create(company=self.co, nom='Compta'),
            nom='Factures fournisseurs', alias_email='compta')
        sav = mock.Mock()
        email_intake._HANDLERS.append(sav)
        messages = self._messages(
            _build_email(to_addr='ged+compta@taqinor.ma', message_id='<ged-1@x.com>'),
            _build_email(to_addr='sav@taqinor.ma', message_id='<client-1@x.com>'))
        result, conn = self._poll(messages)
        self.assertEqual(Document.objects.filter(company=self.co).count(), 1)
        self.assertEqual([c.args[0].message_id for c in sav.call_args_list],
                         ['ged-1@x.com', 'client-1@x.com'])
        self.assertEqual([s[1] for s in conn.stores], [b'1', b'2'])
        self.assertEqual(result, {'fetched': 2, 'handled': 4})
        self._poll(messages)
        self.assertEqual(Document.objects.filter(company=self.co).count(), 1)
