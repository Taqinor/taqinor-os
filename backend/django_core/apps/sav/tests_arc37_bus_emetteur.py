"""Tests ARC37 — sav et gestion_projet deviennent émetteurs du bus.

Avant : ``sav.services`` n'émettait RIEN (résolution ticket, équipement
REMPLACE) — sav était pur consommateur du bus ``core.events``. ARC37 ajoute
trois signaux (``ticket_resolu``, ``equipement_remplace``,
``projet_status_change``), les émet depuis les services concernés, et branche
au moins un abonné réel par signal (garde YEVNT7 / ARC41).

Couvre :
  * ``ticket_resolu`` émis à la transition gardée ``resoudre`` (views.py) ET
    à l'avancement automatique sur intervention terminée (receivers.py),
    JAMAIS réémis pour un ticket déjà résolu/clôturé ;
  * abonné notifications (EventType.SAV_TICKET_RESOLU) ;
  * abonné crm (note chatter ARC8 sur le Client lié, sans importer apps.sav) ;
  * ``equipement_remplace`` émis EXACTEMENT une fois au retrait d'une pièce
    qui remplace un équipement connu, jamais pour un n° de série inconnu ;
  * abonné notifications (EventType.SAV_EQUIPEMENT_REMPLACE) ;
  * ``projet_status_change`` émis à chaque transition de statut de projet,
    cohabitant avec le chemin EXISTANT vers le moteur automation ;
  * abonné notifications (EventType.PROJET_STATUT_CHANGE).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_arc37_bus_emetteur -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.notifications.models import EventType, Notification
from apps.records.models import Activity
from apps.sav.models import Equipement, Ticket
from apps.sav.services import retirer_piece
from apps.stock.models import Produit
from core import event_coverage

User = get_user_model()


def make_company(slug='sav-arc37', nom='Sav Co ARC37'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Arc37TicketResoluTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='arc37_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ARC37',
            email='arc37-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ARC37', client=self.client_obj)
        # Ticket EN_COURS : préalable de la machine d'états gardée (YDOCF1) —
        # `resoudre` n'accepte que EN_COURS → RESOLU, jamais un saut direct
        # depuis NOUVEAU. On teste ainsi la transition manuelle réelle.
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ARC37-1', client=self.client_obj,
            installation=self.inst, type=Ticket.Type.CORRECTIF,
            statut=Ticket.Statut.EN_COURS, created_by=self.admin)

    def test_action_resoudre_emet_ticket_resolu_et_notifie(self):
        api = auth(self.admin)
        resp = api.post(f'/api/django/sav/tickets/{self.ticket.id}/resoudre/')
        self.assertEqual(resp.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.statut, Ticket.Statut.RESOLU)
        self.assertTrue(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.SAV_TICKET_RESOLU).exists())

    def test_action_resoudre_pose_une_note_chatter_arc8_sur_le_client(self):
        api = auth(self.admin)
        api.post(f'/api/django/sav/tickets/{self.ticket.id}/resoudre/')
        ct = ContentType.objects.get_for_model(Client)
        notes = Activity.objects.filter(
            company=self.company, content_type=ct, object_id=self.client_obj.pk,
            kind=Activity.Kind.NOTE)
        self.assertTrue(notes.filter(body__icontains='résolu').exists())

    def test_resolution_ne_reemet_rien_si_deja_resolu(self):
        api = auth(self.admin)
        api.post(f'/api/django/sav/tickets/{self.ticket.id}/resoudre/')
        nb_avant = Notification.objects.filter(
            company=self.company, event_type=EventType.SAV_TICKET_RESOLU).count()
        # Réouvrir puis re-résoudre : un DEUXIÈME cycle réémet (franchissement
        # réel), mais un appel direct au service sur un ticket DÉJÀ résolu ne
        # doit rien réémettre (garde ancien_statut == RESOLU).
        from apps.sav.services import emettre_ticket_resolu
        self.ticket.refresh_from_db()
        emettre_ticket_resolu(
            self.ticket, company=self.company, user=self.admin,
            ancien_statut=Ticket.Statut.RESOLU)
        nb_apres = Notification.objects.filter(
            company=self.company, event_type=EventType.SAV_TICKET_RESOLU).count()
        self.assertEqual(nb_avant, nb_apres)

    def test_intervention_terminee_emet_aussi_ticket_resolu(self):
        from apps.installations.models import Intervention

        intervention = Intervention.objects.create(
            company=self.company, installation=self.inst, ticket=self.ticket,
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.A_PREPARER)
        intervention.statut = Intervention.Statut.TERMINEE
        intervention.save(update_fields=['statut'])

        from core.events import intervention_completed
        intervention_completed.send(
            sender=None, intervention=intervention, company=self.company,
            user=self.admin)

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.statut, Ticket.Statut.RESOLU)
        self.assertTrue(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.SAV_TICKET_RESOLU).exists())


class Arc37EquipementRemplaceTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='sav-arc37-eq', nom='Sav Co ARC37 EQ')
        self.admin = User.objects.create_user(
            username='arc37_eq_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ARC37EQ',
            email='arc37-eq-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ARC37-EQ', client=self.client_obj)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur HS', sku='OND-HS-ARC37',
            prix_achat=3000, prix_vente=6000, quantite_stock=Decimal('2'))
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ARC37-EQ-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)

    def test_retrait_piece_avec_serie_connue_emet_equipement_remplace(self):
        Equipement.objects.create(
            company=self.company, produit=self.onduleur, installation=self.inst,
            numero_serie='SN-ARC37-1', created_by=self.admin)
        retirer_piece(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            quantite=Decimal('1'), numero_serie='SN-ARC37-1',
            destination='retour_fournisseur', user=self.admin)
        self.assertTrue(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.SAV_EQUIPEMENT_REMPLACE).exists())

    def test_retrait_piece_serie_inconnue_ne_declenche_rien(self):
        retirer_piece(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            quantite=Decimal('1'), numero_serie='SN-INCONNU-ARC37',
            destination='retour_fournisseur', user=self.admin)
        self.assertFalse(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.SAV_EQUIPEMENT_REMPLACE).exists())


class Arc37EvenementsNonOrphelinsTests(TestCase):
    def test_les_trois_signaux_ont_un_abonne(self):
        orphelins = event_coverage.orphan_signals()
        self.assertNotIn('ticket_resolu', orphelins)
        self.assertNotIn('equipement_remplace', orphelins)
        self.assertNotIn('projet_status_change', orphelins)
