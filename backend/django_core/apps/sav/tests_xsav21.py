"""XSAV21 — Suggestion de tickets similaires résolus.

Couvre :
  * ranking déterministe : même produit > même cause > similarité texte ;
  * cross-tenant exclu ;
  * tickets ouverts exclus (seuls résolus/clôturés comptent) ;
  * le ticket lui-même jamais dans ses propres suggestions.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav21 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import CauseDefaillance, Equipement, Ticket

User = get_user_model()


def make_company(slug='sav-xsav21', nom='Sav Co XSAV21'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV21TicketsSimilairesTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other_company = make_company(slug='sav-xsav21-other', nom='Autre Co')
        self.admin = User.objects.create_user(
            username='xsav21_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav21-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV21', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur Sim', sku='OND-SIM-XSAV21',
            prix_achat=300, prix_vente=600)
        self.produit_autre = Produit.objects.create(
            company=self.company, nom='Onduleur Autre', sku='OND-AUTRE-XSAV21',
            prix_achat=300, prix_vente=600)
        self.equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            created_by=self.admin)
        self.equip_autre_produit = Equipement.objects.create(
            company=self.company, produit=self.produit_autre,
            installation=self.inst, created_by=self.admin)
        self.cause = CauseDefaillance.objects.create(
            company=self.company, nom='Défaut string')

    def _ticket(self, *, equipement=None, statut=Ticket.Statut.NOUVEAU,
                description='', cause=None):
        return Ticket.objects.create(
            company=self.company, reference=f'SAV-XSAV21-{Ticket.objects.count()}',
            client=self.client_obj, installation=self.inst,
            equipement=equipement, statut=statut, type=Ticket.Type.CORRECTIF,
            description=description, cause=cause, created_by=self.admin)

    def test_meme_produit_prioritaire(self):
        ref = self._ticket(
            equipement=self.equip, statut=Ticket.Statut.NOUVEAU,
            description='Onduleur affiche code erreur E07 string 3')
        meme_produit = self._ticket(
            equipement=self.equip, statut=Ticket.Statut.RESOLU,
            description='Panne différente, texte totalement autre.')
        autre_produit = self._ticket(
            equipement=self.equip_autre_produit, statut=Ticket.Statut.RESOLU,
            description='Onduleur affiche code erreur E07 string 3')

        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/tickets/{ref.id}/similaires/')
        self.assertEqual(resp.status_code, 200, resp.content)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(meme_produit.id, ids)
        self.assertIn(autre_produit.id, ids)
        # même produit (score +100) doit dépasser un texte + similaire mais
        # produit différent.
        self.assertLess(ids.index(meme_produit.id), ids.index(autre_produit.id))

    def test_meme_cause_devant_similarite_texte_seule(self):
        ref = self._ticket(
            equipement=self.equip_autre_produit, statut=Ticket.Statut.NOUVEAU,
            description='texte neutre', cause=self.cause)
        meme_cause = self._ticket(
            equipement=self.equip_autre_produit, statut=Ticket.Statut.RESOLU,
            description='autre texte sans rapport', cause=self.cause)
        texte_proche_sans_cause = self._ticket(
            equipement=self.equip_autre_produit, statut=Ticket.Statut.RESOLU,
            description='texte neutre', cause=None)

        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/tickets/{ref.id}/similaires/')
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(meme_cause.id, ids)
        self.assertLess(
            ids.index(meme_cause.id), ids.index(texte_proche_sans_cause.id))

    def test_tickets_ouverts_exclus(self):
        ref = self._ticket(
            equipement=self.equip, statut=Ticket.Statut.NOUVEAU,
            description='panne onduleur')
        ouvert = self._ticket(
            equipement=self.equip, statut=Ticket.Statut.EN_COURS,
            description='panne onduleur')

        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/tickets/{ref.id}/similaires/')
        ids = [r['id'] for r in resp.data['results']]
        self.assertNotIn(ouvert.id, ids)

    def test_ticket_lui_meme_jamais_suggere(self):
        ref = self._ticket(
            equipement=self.equip, statut=Ticket.Statut.RESOLU,
            description='panne onduleur')
        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/tickets/{ref.id}/similaires/')
        ids = [r['id'] for r in resp.data['results']]
        self.assertNotIn(ref.id, ids)

    def test_cross_tenant_exclu(self):
        other_user = User.objects.create_user(
            username='xsav21_other', password='x', role_legacy='admin',
            company=self.other_company)
        other_client = Client.objects.create(
            company=self.other_company, nom='Autre', prenom='Client',
            email='xsav21-other@example.invalid')
        other_inst = Installation.objects.create(
            company=self.other_company, reference='CHT-OTHER', client=other_client)
        other_produit = Produit.objects.create(
            company=self.other_company, nom='Onduleur Sim', sku='OND-OTHER-XSAV21',
            prix_achat=300, prix_vente=600)
        other_equip = Equipement.objects.create(
            company=self.other_company, produit=other_produit,
            installation=other_inst, created_by=other_user)
        Ticket.objects.create(
            company=self.other_company, reference='SAV-XSAV21-OTHER',
            client=other_client, installation=other_inst,
            equipement=other_equip, statut=Ticket.Statut.RESOLU,
            type=Ticket.Type.CORRECTIF,
            description='panne onduleur identique', created_by=other_user)

        ref = self._ticket(
            equipement=self.equip, statut=Ticket.Statut.NOUVEAU,
            description='panne onduleur identique')
        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/tickets/{ref.id}/similaires/')
        self.assertEqual(resp.status_code, 200, resp.content)
        for r in resp.data['results']:
            self.assertNotEqual(r['reference'], 'SAV-XSAV21-OTHER')
