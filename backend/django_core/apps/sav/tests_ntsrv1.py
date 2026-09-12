"""NTSRV1 — Ingestion e-mail entrant → ticket, avec THREADING réel.

Couvre le critère d'acceptation :
  * deux e-mails du MÊME fil (même ``thread_root``) atterrissent sur le MÊME
    ticket — jamais deux tickets dupliqués ;
  * ``apps/sav`` ne réimplémente AUCUNE connexion IMAP (grep négatif sur
    ``imaplib`` dans le paquet) — le handler est simplement abonné au registre
    générique ``core/email_intake.py`` (FG373) ;
  * idempotence par ``Message-ID`` (re-poll / redélivrance) ;
  * expéditeur inconnu → aucun ticket orphelin ;
  * réponse sortante depuis le ticket : fil journalisé + en-têtes de fil.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv1 -v 2
"""
import pathlib

from django.core import mail
from django.test import TestCase, override_settings

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import Ticket, TicketActivity, TicketEmailThread
from apps.sav.services import (
    handler_ticket_entrant, repondre_par_email, ticket_du_fil_email,
)
from core.email_intake import InboundMessage, _HANDLERS

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def make_company(slug='sav-ntsrv1', nom='Sav Co NTSRV1'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _message(message_id, *, in_reply_to='', references='',
             from_email='client@example.invalid', subject='Panne onduleur',
             body='Ça ne démarre plus.'):
    return InboundMessage(
        message_id=message_id, in_reply_to=in_reply_to, references=references,
        subject=subject, from_email=from_email, from_name='Client Test',
        body=body, raw_headers={'From': from_email})


class NTSRV1ThreadingTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV1',
            email='client@example.invalid')

    # ── Critère d'acceptation principal ──────────────────────────────────
    def test_deux_emails_du_meme_fil_vont_sur_le_meme_ticket(self):
        premier = handler_ticket_entrant(_message('m1@example.invalid'),
                                         self.company)
        self.assertIsNotNone(premier)
        self.assertEqual(Ticket.objects.count(), 1)

        reponse = _message(
            'm2@example.invalid', in_reply_to='m1@example.invalid',
            references='m1@example.invalid', subject='Re: Panne onduleur',
            body='Toujours rien après le redémarrage.')
        second = handler_ticket_entrant(reponse, self.company)

        self.assertEqual(second.pk, premier.pk)
        self.assertEqual(Ticket.objects.count(), 1, 'un fil = un seul ticket')
        self.assertEqual(
            TicketEmailThread.objects.filter(ticket=premier).count(), 2)

    def test_fil_different_ouvre_un_second_ticket(self):
        handler_ticket_entrant(_message('a1@example.invalid'), self.company)
        handler_ticket_entrant(
            _message('b1@example.invalid', subject='Autre sujet'),
            self.company)
        self.assertEqual(Ticket.objects.count(), 2)

    def test_meme_message_id_est_idempotent(self):
        msg = _message('dup@example.invalid')
        handler_ticket_entrant(msg, self.company)
        self.assertIsNone(handler_ticket_entrant(msg, self.company))
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(TicketEmailThread.objects.count(), 1)

    def test_expediteur_inconnu_ne_cree_aucun_ticket(self):
        result = handler_ticket_entrant(
            _message('x1@example.invalid', from_email='inconnu@example.invalid'),
            self.company)
        self.assertIsNone(result)
        self.assertEqual(Ticket.objects.count(), 0)
        self.assertEqual(TicketEmailThread.objects.count(), 0)

    def test_ticket_cree_porte_le_canal_email_et_une_note_chatter(self):
        ticket = handler_ticket_entrant(_message('c1@example.invalid'),
                                        self.company)
        self.assertEqual(ticket.canal_ouverture, Ticket.CanalOuverture.EMAIL)
        self.assertEqual(ticket.statut, Ticket.Statut.NOUVEAU)
        self.assertTrue(TicketActivity.objects.filter(
            ticket=ticket, kind=TicketActivity.Kind.EMAIL).exists())

    def test_fil_scope_par_societe(self):
        autre = make_company(slug='sav-ntsrv1-b', nom='Autre Co')
        Client.objects.create(company=autre, nom='Client', prenom='B',
                              email='client@example.invalid')
        handler_ticket_entrant(_message('s1@example.invalid'), self.company)
        # Même Message-ID reçu par une AUTRE société : fil distinct.
        self.assertIsNone(ticket_du_fil_email(
            autre, _message('s1@example.invalid')))
        handler_ticket_entrant(_message('s1@example.invalid'), autre)
        self.assertEqual(Ticket.objects.filter(company=autre).count(), 1)

    def test_handler_enregistre_sur_le_registre_generique(self):
        self.assertIn(handler_ticket_entrant, _HANDLERS)

    def test_aucune_connexion_imap_dans_apps_sav(self):
        """Le registre core fait l'IMAP ; ``apps/sav`` ne le refait jamais."""
        racine = pathlib.Path(__file__).resolve().parent
        fautifs = [
            str(f.relative_to(racine)) for f in racine.rglob('*.py')
            if f.name != pathlib.Path(__file__).name
            and 'imaplib' in f.read_text(encoding='utf-8')
        ]
        self.assertEqual(fautifs, [], f'imaplib trouvé dans apps/sav : {fautifs}')


@override_settings(EMAIL_BACKEND=LOCMEM)
class NTSRV1ReponseSortanteTest(TestCase):
    def setUp(self):
        self.company = make_company(slug='sav-ntsrv1-out', nom='Sav Out')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Out',
            email='client@example.invalid')
        self.ticket = handler_ticket_entrant(
            _message('in1@example.invalid'), self.company)
        mail.outbox = []

    def test_reponse_reprend_les_entetes_du_fil(self):
        ligne = repondre_par_email(self.ticket, corps='Nous intervenons demain.')
        self.assertEqual(ligne.direction, TicketEmailThread.Direction.SORTANT)
        self.assertEqual(ligne.thread_root, 'in1@example.invalid')
        self.assertEqual(ligne.destinataire, 'client@example.invalid')
        self.assertEqual(len(mail.outbox), 1)
        entetes = mail.outbox[0].extra_headers
        self.assertEqual(entetes['In-Reply-To'], '<in1@example.invalid>')
        self.assertEqual(entetes['References'], '<in1@example.invalid>')
        self.assertTrue(mail.outbox[0].subject.startswith('Re:'))

    def test_reponse_est_journalisee_au_chatter(self):
        repondre_par_email(self.ticket, corps='Bonjour', user=None)
        self.assertEqual(TicketActivity.objects.filter(
            ticket=self.ticket, kind=TicketActivity.Kind.EMAIL).count(), 2)

    def test_corps_vide_refuse_en_nommant_le_champ(self):
        with self.assertRaises(ValueError) as ctx:
            repondre_par_email(self.ticket, corps='   ')
        self.assertTrue(str(ctx.exception).startswith('corps:'))

    def test_sans_adresse_client_le_champ_fautif_est_nomme(self):
        self.client_obj.email = ''
        self.client_obj.save(update_fields=['email'])
        self.ticket.refresh_from_db()
        with self.assertRaises(ValueError) as ctx:
            repondre_par_email(self.ticket, corps='Bonjour')
        self.assertTrue(str(ctx.exception).startswith('destinataire:'))

    def test_une_reponse_du_client_revient_sur_le_meme_ticket(self):
        ligne = repondre_par_email(self.ticket, corps='Nous intervenons demain.')
        retour = _message(
            'in2@example.invalid', in_reply_to=ligne.message_id,
            references=f'{ligne.thread_root} {ligne.message_id}',
            subject='Re: Panne onduleur', body='Parfait, merci.')
        ticket = handler_ticket_entrant(retour, self.company)
        self.assertEqual(ticket.pk, self.ticket.pk)
        self.assertEqual(Ticket.objects.count(), 1)
