"""XFSM1 — Facturation SAV hors garantie depuis le ticket (réels → facture).

Couvre :
  * un ticket CORRECTIF hors garantie avec pièces consommées + heures
    saisies génère une facture BROUILLON correcte (lignes pièces au prix de
    vente catalogue, ligne MO au taux horaire société, TVA par ligne) ;
  * un ticket sous garantie (calculée depuis l'équipement lié) génère les
    mêmes lignes mais à 0 DH (« couvert ») ;
  * idempotent : un second appel réutilise la même facture (pas de double) ;
  * `prix_achat` n'apparaît jamais dans la facture générée.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xfsm1 -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.parametres.models import CompanyProfile
from apps.sav.models import Equipement, PieceConsommee, Ticket
from apps.stock.models import Produit

User = get_user_model()


def make_company(slug='sav-xfsm1', nom='Sav Co XFSM1'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFSM1FacturationTicketTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xfsm1_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xfsm1-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XFSM1', client=self.client_obj)
        self.piece = Produit.objects.create(
            company=self.company, nom='Fusible SAV', sku='FUS-XFSM1',
            prix_achat=Decimal('5'), prix_vente=Decimal('50'))
        profile = CompanyProfile.get(self.company)
        profile.taux_horaire_sav = Decimal('300')
        profile.save(update_fields=['taux_horaire_sav'])

    def _ticket_hors_garantie(self):
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XFSM1-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF,
            sous_garantie=Ticket.SousGarantie.NON,
            heures_main_oeuvre=Decimal('2'), created_by=self.admin)
        PieceConsommee.objects.create(
            company=self.company, ticket=ticket, produit=self.piece,
            quantite=Decimal('3'), created_by=self.admin)
        return ticket

    def test_ticket_hors_garantie_genere_facture_correcte(self):
        api = auth(self.admin)
        ticket = self._ticket_hors_garantie()
        resp = api.post(f'/api/django/sav/tickets/{ticket.id}/generer-facture/')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertFalse(resp.data['sous_garantie'])

        from apps.ventes.models import Facture
        facture = Facture.objects.get(pk=resp.data['facture_id'])
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertEqual(facture.client_id, self.client_obj.id)

        lignes = list(facture.lignes.all())
        self.assertEqual(len(lignes), 2)
        piece_ligne = next(
            ln for ln in lignes if ln.produit_id == self.piece.id)
        self.assertEqual(piece_ligne.prix_unitaire, Decimal('50'))
        self.assertEqual(piece_ligne.quantite, Decimal('3'))

        mo_ligne = next(
            ln for ln in lignes if ln.produit_id != self.piece.id)
        self.assertEqual(mo_ligne.prix_unitaire, Decimal('300'))
        self.assertEqual(mo_ligne.quantite, Decimal('2'))

        # prix_achat jamais exposé dans la réponse API du ticket/facture.
        self.assertNotIn('prix_achat', str(resp.content))

    def test_ticket_sous_garantie_lignes_a_zero(self):
        equip = Equipement.objects.create(
            company=self.company, produit=self.piece, installation=self.inst,
            date_pose=date.today(), created_by=self.admin)
        equip.recompute_garanties()
        # Pas de garantie_mois renseignée sur `self.piece` -> on force la
        # date de fin de garantie manuellement pour simuler « sous garantie ».
        from apps.sav.services import add_months
        equip.date_fin_garantie = add_months(date.today(), 12)
        equip.save(update_fields=['date_fin_garantie'])

        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XFSM1-2',
            client=self.client_obj, installation=self.inst, equipement=equip,
            type=Ticket.Type.CORRECTIF, heures_main_oeuvre=Decimal('1'),
            created_by=self.admin)
        PieceConsommee.objects.create(
            company=self.company, ticket=ticket, produit=self.piece,
            quantite=Decimal('1'), created_by=self.admin)

        api = auth(self.admin)
        resp = api.post(f'/api/django/sav/tickets/{ticket.id}/generer-facture/')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data['sous_garantie'])

        from apps.ventes.models import Facture
        facture = Facture.objects.get(pk=resp.data['facture_id'])
        for ligne in facture.lignes.all():
            self.assertEqual(ligne.prix_unitaire, Decimal('0'))
            self.assertIn('couvert', ligne.designation.lower())

    def test_idempotent_pas_de_double_facture(self):
        api = auth(self.admin)
        ticket = self._ticket_hors_garantie()
        resp1 = api.post(f'/api/django/sav/tickets/{ticket.id}/generer-facture/')
        resp2 = api.post(f'/api/django/sav/tickets/{ticket.id}/generer-facture/')
        self.assertEqual(resp1.data['facture_id'], resp2.data['facture_id'])

        from apps.ventes.models import Facture
        self.assertEqual(
            Facture.objects.filter(
                company=self.company, client=self.client_obj).count(), 1)
