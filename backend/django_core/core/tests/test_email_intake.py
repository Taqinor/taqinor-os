"""Tests FG373 — email entrant IMAP → leads/tickets (fondation).

Couvre :
  * parsing RFC 822 → InboundMessage (from, sujet, body, message-id) ;
  * threading : thread_root via References / In-Reply-To / self ;
  * registre de handlers + dispatch (un handler défaillant n'arrête pas) ;
  * fetch_messages no-op quand non configuré ;
  * poll_mailbox no-op sans config société ;
  * découplage : aucun import d'app domaine.
"""
from django.test import TestCase

from authentication.models import Company
from core import email_intake, integrations
from core.models import IntegrationConfig


class ParseTests(TestCase):
    def test_parse_simple_message(self):
        raw = (b'From: Ali Ben <ali@example.com>\r\n'
               b'Subject: Demande devis\r\n'
               b'Message-ID: <abc@x>\r\n'
               b'\r\n'
               b'Bonjour, je veux un devis.\r\n')
        msg = email_intake._parse_email_message(raw)
        self.assertEqual(msg.from_email, 'ali@example.com')
        self.assertEqual(msg.from_name, 'Ali Ben')
        self.assertEqual(msg.subject, 'Demande devis')
        self.assertEqual(msg.message_id, 'abc@x')
        self.assertIn('devis', msg.body)

    def test_thread_root_prefers_references(self):
        m = email_intake.InboundMessage(
            message_id='c', in_reply_to='b', references='root mid2')
        self.assertEqual(m.thread_root, 'root')
        m2 = email_intake.InboundMessage(message_id='c', in_reply_to='b')
        self.assertEqual(m2.thread_root, 'b')
        m3 = email_intake.InboundMessage(message_id='c')
        self.assertEqual(m3.thread_root, 'c')


class HandlerRegistryTests(TestCase):
    def setUp(self):
        email_intake._HANDLERS.clear()

    def tearDown(self):
        email_intake._HANDLERS.clear()

    def test_register_and_dispatch(self):
        seen = []
        email_intake.register_handler(lambda m, c: seen.append((m, c)))
        msg = email_intake.InboundMessage(message_id='x')
        n = email_intake._dispatch([msg], company='C')
        self.assertEqual(n, 1)
        self.assertEqual(seen[0][1], 'C')

    def test_failing_handler_does_not_break_others(self):
        ok = []

        def boom(m, c):
            raise RuntimeError('nope')

        email_intake.register_handler(boom)
        email_intake.register_handler(lambda m, c: ok.append(1))
        n = email_intake._dispatch(
            [email_intake.InboundMessage(message_id='x')], company='C')
        self.assertEqual(ok, [1])
        self.assertEqual(n, 1)

    def test_register_handler_idempotent(self):
        def fn(m, c):
            return None
        email_intake.register_handler(fn)
        email_intake.register_handler(fn)
        self.assertEqual(email_intake._HANDLERS.count(fn), 1)


class FetchAndPollTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME')

    def test_fetch_noop_when_unconfigured(self):
        cfg = IntegrationConfig.objects.create(
            company=self.company, integration_type=integrations.TYPE_EMAIL_IN,
            provider='imap', actif=True, settings={})
        self.assertEqual(email_intake.fetch_messages(cfg), [])

    def _boite_imap(self, messages, entre_connexions=None):
        """ACEL85 — faux serveur IMAP à état partagé entre les connexions
        (UID + numéros de séquence) ; ``entre_connexions(msgs)`` joue avant la 2e."""
        from unittest import mock

        IntegrationConfig.objects.create(
            company=self.company, integration_type=integrations.TYPE_EMAIL_IN,
            provider='imap', actif=True, secret_ref='ACEL17_IMAP_MDP',
            settings={'host': 'imap.example.invalid', 'user': 'boite'})
        etat = {'msgs': [dict(m, seen=False) for m in messages], 'appels': []}
        connexions = []

        def connexion(*args, **kwargs):
            if connexions and entre_connexions:
                entre_connexions(etat['msgs'])
            connexions.append(kwargs)
            return _FauxImap(etat)

        avant = list(email_intake._HANDLERS)
        email_intake._HANDLERS.clear()
        self.addCleanup(email_intake._HANDLERS.extend, avant)
        self.addCleanup(email_intake._HANDLERS.clear)
        self.addCleanup(mock.patch.stopall)
        mock.patch.dict('os.environ', {'ACEL17_IMAP_MDP': 'x'}).start()
        mock.patch('imaplib.IMAP4_SSL', side_effect=connexion).start()
        return etat, connexions

    def test_message_non_traite_reste_non_lu(self):
        """ACEL17 — relève sans poser `\\Seen` ; seul le message traité sans
        erreur est marqué lu ; connexion bornée par un délai (ACEL85 : par UID)."""
        etat, connexions = self._boite_imap([
            {'uid': 1, 'raw': b'Message-ID: <un@x>\r\nSubject: un\r\n\r\ncorps'},
            {'uid': 2, 'raw': b'Message-ID: <deux@x>\r\nSubject: deux\r\n\r\ncorps'}])

        def handler(msg, company):
            if msg.message_id == 'un@x':
                raise RuntimeError('ticket SAV impossible')

        email_intake.register_handler(handler)
        email_intake.poll_mailbox(self.company)
        lectures = [a for a in etat['appels'] if a[0] == 'FETCH']
        self.assertEqual(len(lectures), 2)
        self.assertTrue(all(a[2] == '(BODY.PEEK[])' for a in lectures))
        self.assertEqual({m['uid']: m['seen'] for m in etat['msgs']},
                         {1: False, 2: True})
        self.assertEqual(connexions[0].get('timeout'), 30)

    def test_marquage_par_uid_apres_expunge(self):
        """ACEL85 — un EXPUNGE entre la relève et le marquage (et un message
        arrivé entre-temps) ne fait jamais marquer lu un autre message."""
        def expunge(msgs):
            msgs.pop(0)  # UID 10 supprimé par Outlook / une règle serveur
            msgs.append({'uid': 13, 'raw': b'Message-ID: <m13@x>\r\n\r\nc',
                         'seen': False})  # arrivé après la relève, jamais traité

        etat, _ = self._boite_imap(
            [{'uid': u, 'raw': b'Message-ID: <m%d@x>\r\n\r\nc' % u}
             for u in (10, 11, 12)], entre_connexions=expunge)
        recus = []
        email_intake.register_handler(lambda m, c: recus.append(m.message_id))
        res = email_intake.poll_mailbox(self.company)
        self.assertEqual(recus, ['m10@x', 'm11@x', 'm12@x'])
        self.assertEqual(res['fetched'], 3)
        self.assertEqual({m['uid']: m['seen'] for m in etat['msgs']},
                         {11: True, 12: True, 13: False})

    def test_poll_noop_without_config(self):
        res = email_intake.poll_mailbox(self.company)
        self.assertEqual(res, {'fetched': 0, 'handled': 0})


class _FauxImap:
    """ACEL85 — connexion IMAP factice sur un état partagé : ``uid(...)``
    adresse par UID, ``search``/``fetch``/``store`` par numéro de séquence."""

    def __init__(self, etat):
        self.etat = etat

    def login(self, *args):
        return 'OK', [b'']

    select = logout = login

    def _cherche(self, cle, val):
        msgs = self.etat['msgs']
        if cle == 'seq':
            i = int(val) - 1
            return msgs[i] if 0 <= i < len(msgs) else None
        return next((m for m in msgs if m['uid'] == int(val)), None)

    def _non_lus(self, cle):
        ids = [str(i + 1 if cle == 'seq' else m['uid'])
               for i, m in enumerate(self.etat['msgs']) if not m['seen']]
        return 'OK', [' '.join(ids).encode()]

    def _fetch(self, cle, val, quoi):
        self.etat['appels'].append(('FETCH', val, quoi))
        m = self._cherche(cle, val)
        return 'OK', [(b'', m['raw']) if m else None]

    def _store(self, cle, val, drapeau):
        m = self._cherche(cle, val)
        if m and 'Seen' in drapeau:
            m['seen'] = True
        return 'OK', [None]

    def search(self, charset, critere):
        return self._non_lus('seq')

    def fetch(self, num, quoi):
        return self._fetch('seq', num, quoi)

    def store(self, num, op, drapeau):
        return self._store('seq', num, drapeau)

    def uid(self, commande, *args):
        if commande == 'SEARCH':
            return self._non_lus('uid')
        if commande == 'FETCH':
            return self._fetch('uid', args[0], args[1])
        return self._store('uid', args[0], args[2])
