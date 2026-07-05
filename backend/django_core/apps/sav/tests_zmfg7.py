"""ZMFG7 — Alias e-mail par catégorie d'équipement → création auto de demande.

Couvre :
  * e-mail vers un alias configuré + expéditeur connu → ticket correctif créé,
    pré-catégorisé (catégorie + équipe responsable si posée) ;
  * alias inconnu → aucun ticket créé (route FG373 générique inchangée) ;
  * expéditeur inconnu → no-op (aucun ticket orphelin) ;
  * ré-émission du même message (même Message-ID) → pas de second ticket
    (idempotence) ;
  * le handler est bien enregistré auprès de ``core.email_intake``.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zmfg7 -v 2
"""
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import CategorieEquipement, EquipeMaintenance, Ticket
from apps.sav.services import creer_ticket_depuis_email_alias
from core.email_intake import InboundMessage, _HANDLERS


def make_company(slug='sav-zmfg7', nom='Sav Co ZMFG7'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _message(to='alias@example.invalid', from_email='client@example.invalid',
             subject='Panne onduleur', body='Ça ne démarre plus.',
             message_id='<msg-1@example.invalid>'):
    return InboundMessage(
        message_id=message_id, subject=subject, from_email=from_email,
        from_name='Client Test', body=body,
        raw_headers={'To': to, 'From': from_email})


class ZMFG7EmailAliasTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZMFG7',
            email='client@example.invalid')
        self.equipe = EquipeMaintenance.objects.create(
            company=self.company, nom='Équipe Onduleurs')
        self.categorie = CategorieEquipement.objects.create(
            company=self.company, nom='Onduleurs',
            alias_email='onduleurs@example.invalid',
            equipe_responsable=self.equipe)

    def test_email_to_alias_creates_precategorized_ticket(self):
        msg = _message(to='onduleurs@example.invalid')
        ticket = creer_ticket_depuis_email_alias(msg, self.company)
        self.assertIsNotNone(ticket)
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(ticket.categorie_equipement, self.categorie)
        self.assertEqual(ticket.equipe, self.equipe)
        self.assertEqual(ticket.type, Ticket.Type.CORRECTIF)
        self.assertEqual(ticket.client, self.client_obj)

    def test_unknown_alias_creates_nothing(self):
        msg = _message(to='inconnu@example.invalid')
        result = creer_ticket_depuis_email_alias(msg, self.company)
        self.assertIsNone(result)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_unknown_sender_creates_nothing(self):
        msg = _message(
            to='onduleurs@example.invalid', from_email='inconnu@example.invalid')
        result = creer_ticket_depuis_email_alias(msg, self.company)
        self.assertIsNone(result)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_same_message_id_is_idempotent(self):
        msg = _message(to='onduleurs@example.invalid', message_id='<dup@example.invalid>')
        t1 = creer_ticket_depuis_email_alias(msg, self.company)
        t2 = creer_ticket_depuis_email_alias(msg, self.company)
        self.assertEqual(t1.pk, t2.pk)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_category_without_equipe_leaves_ticket_equipe_null(self):
        categorie_sans_equipe = CategorieEquipement.objects.create(
            company=self.company, nom='Pompes',
            alias_email='pompes@example.invalid')
        msg = _message(to='pompes@example.invalid', message_id='<msg-2@example.invalid>')
        ticket = creer_ticket_depuis_email_alias(msg, self.company)
        self.assertEqual(ticket.categorie_equipement, categorie_sans_equipe)
        self.assertIsNone(ticket.equipe)

    def test_handler_is_registered_on_the_email_intake_bus(self):
        self.assertIn(creer_ticket_depuis_email_alias, _HANDLERS)
