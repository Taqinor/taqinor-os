"""ASAV4 (D-ASAV-6) — la couverture d'un ticket (garantie ET contrat) se juge
à la date d'OUVERTURE du ticket, jamais au jour de la lecture/facturation.

Run :
    python manage.py test apps.sav.tests_asav4_couverture_date_ouverture -v2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.dateutils import add_months
from apps.sav.models import (
    ContratMaintenance, Equipement, PieceConsommee, SavSlaSettings, Ticket)
from apps.stock.models import Produit
from apps.ventes.models import Facture

User = get_user_model()


class CouvertureDateOuvertureTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav4-co', defaults={'nom': 'ASAV4 Co'})
        self.user = User.objects.create_user(
            username='asav4_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV4')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV4',
            client=self.client_obj)
        self.today = timezone.localdate()

    def _equipement(self, mois_pose):
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASAV4',
            prix_achat=0, prix_vente=5000)
        eq = Equipement.objects.create(
            company=self.company, produit=produit, installation=self.inst,
            numero_serie='ASAV4-SN',
            date_pose=add_months(self.today, -mois_pose))
        eq.recompute_garanties()
        eq.save(update_fields=['date_fin_garantie',
                               'date_fin_garantie_production'])
        return eq

    def _ticket(self, ref, *, jours, equipement=None):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            installation=self.inst, equipement=equipement,
            type=Ticket.Type.CORRECTIF, created_by=self.user,
            date_ouverture=self.today - timedelta(days=jours))

    def test_garantie_jugee_a_l_ouverture(self):
        # Légale (12 mois) échue depuis ~2 mois ; ticket ouvert il y a 4 mois.
        eq = self._equipement(mois_pose=14)
        ticket = self._ticket('SAV-A4-1', jours=120, equipement=eq)
        self.assertEqual(ticket.sous_garantie_calcule,
                         Ticket.SousGarantie.OUI)
        self.assertEqual(ticket.couverture_calculee(),
                         Ticket.Couverture.GARANTIE)

    def test_contrat_juge_a_l_ouverture(self):
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, actif=True,
            date_debut=self.today - timedelta(days=14 * 30), duree_mois=12)
        ticket = self._ticket('SAV-A4-2', jours=90)
        self.assertEqual(ticket.couverture_calculee(),
                         Ticket.Couverture.CONTRAT)

    def test_ouvert_apres_echeance_facturable(self):
        eq = self._equipement(mois_pose=14)
        ticket = self._ticket('SAV-A4-3', jours=5, equipement=eq)
        self.assertEqual(ticket.sous_garantie_calcule,
                         Ticket.SousGarantie.NON)
        self.assertEqual(ticket.couverture_calculee(),
                         Ticket.Couverture.FACTURABLE)

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        return api

    def _facturer(self, api, ticket):
        PieceConsommee.objects.create(
            company=self.company, ticket=ticket,
            produit=ticket.equipement.produit, quantite=Decimal('1'),
            created_by=self.user)
        r = api.post(f'/api/django/sav/tickets/{ticket.pk}/facturer/', {},
                     format='json')
        self.assertEqual(r.status_code, 201, r.content)
        relu = Ticket.objects.get(pk=ticket.pk)
        facture = Facture.objects.get(pk=relu.facture_id_ext)
        prix = [ligne.prix_unitaire for ligne in facture.lignes.all()]
        return r.data['couverture'], prix, relu

    def test_contrat_posterieur_ouverture_facture_http(self):
        """ASAV105 — un contrat débuté APRÈS l'ouverture du ticket ne le
        couvre pas (cas A, 5000.00) ; débuté avant, il le couvre (cas B)."""
        api = self._api()
        eq = self._equipement(mois_pose=30)
        # Cas A : ticket ouvert à J-60, contrat débuté aujourd'hui.
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, actif=True, date_debut=self.today)
        ticket_a = self._ticket('SAV-A105-A', jours=60, equipement=eq)
        couverture, prix, relu = self._facturer(api, ticket_a)
        self.assertEqual(couverture, Ticket.Couverture.FACTURABLE)
        self.assertEqual(prix, [Decimal('5000')])
        self.assertEqual(relu.couverture_calculee(),
                         Ticket.Couverture.FACTURABLE)
        # Cas B : contrat débuté à J-90, avant l'ouverture à J-60.
        ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, actif=True,
            date_debut=self.today - timedelta(days=90))
        ticket_b = self._ticket('SAV-A105-B', jours=60, equipement=eq)
        couverture, prix, relu = self._facturer(api, ticket_b)
        self.assertEqual(couverture, Ticket.Couverture.CONTRAT)
        self.assertEqual(prix, [Decimal('0')])
        self.assertEqual(relu.couverture_calculee(),
                         Ticket.Couverture.CONTRAT)

    def test_contrat_futur_n_impose_pas_sla(self):
        """ASAV105 — un contrat qui débute dans 30 jours n'impose pas
        aujourd'hui son SLA : l'échéance suit le SLA société."""
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.sla_jours_ouvres = False
        sla.sla_resolution_days = 7
        sla.save()
        autre = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV105-futur')
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=autre, actif=True,
            date_debut=self.today + timedelta(days=30), duree_mois=12,
            sla_resolution_days=1)
        self.assertFalse(contrat.est_actif())
        self.assertIsNone(ContratMaintenance.actif_pour_client(autre))
        r = self._api().post('/api/django/sav/tickets/', {
            'client': autre.pk, 'description': 'Panne ASAV105',
            'priorite': 'normale'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        ticket = Ticket.objects.get(pk=r.data['id'])
        self.assertEqual((ticket.sla_due_at - ticket.date_ouverture).days, 7)
